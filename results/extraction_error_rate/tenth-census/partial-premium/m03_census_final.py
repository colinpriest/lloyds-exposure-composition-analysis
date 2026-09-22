"""Final M03 census table (read-only).  Inputs: m03_census_rows.json (m03_census.py) and
m03_census_flagged.csv (m03_census_grade2.py).  Adds, per flagged record, the mechanism
from the adopted Azure grid (m03_mechanism.py logic) or, for text-fallback mixes, whether
the adopted amounts are rows of the premium table the models read (PARTIAL) or amounts
from some other table (NOT-PREMIUM).  Prints coverage of the check over the working
sample and writes m03_census_final.csv and a markdown table."""
import collections
import csv
import json
import os
import re
import sys

EX = r"D:\dev\lloyds_reserve_stress_testing"
AN = r"D:\dev\IME-Lloyds-exposure-composition"
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, EX)
sys.path.insert(0, HERE)
import table_extraction as te  # noqa: E402

rows = {r["stem"]: r for r in json.load(open(os.path.join(HERE, "m03_census_rows.json"), encoding="utf-8"))}
flag = list(csv.DictReader(open(os.path.join(HERE, "m03_census_flagged.csv"), encoding="utf-8")))


def gwp_col_of(grid):
    for r in grid[:3]:
        for i, c in enumerate(r):
            cl = (c or "").lower()
            if ("written" in cl and "premium" in cl) or cl.strip().startswith("gross written"):
                return i
    return 1


def report_year_rows(grid, year):
    in_sec, seen, out = True, False, []
    for r in grid[1:]:
        lab = (r[0] or "").strip() if r else ""
        if lab and re.match(r"^(19|20)\d{2}$", lab) and all(not (c or "").strip() for c in r[1:]):
            seen, in_sec = True, int(lab) == year
            continue
        if seen and not in_sec:
            continue
        out.append(r)
    return out


def det_mechanism(stem, yr, mix, T):
    labels = [e["line_of_business"].strip() for e in mix]
    cache = json.load(open(os.path.join(EX, "pdf_extraction", "azure_output", stem + "_azure.json"), encoding="utf-8"))
    best = None
    for ti, t in enumerate(cache["tables"]):
        first = {(row[0] or "").strip() for row in t["grid"] if row}
        hit = len(set(labels) & first)
        if hit and (best is None or hit > best[0]):
            best = (hit, ti, t["grid"])
    if best is None:
        return "GRID-NOT-FOUND", ""
    _, ti, g = best
    gc = gwp_col_of(g)
    kinds, notes, cands = [], [], []
    blank_after_label = False
    for r in report_year_rows(g, yr):
        if not r:
            continue
        lab = (r[0] or "").strip()
        raw = r[gc] if gc < len(r) else ""
        v = te._clean_cell(raw)
        ll = lab.lower().rstrip(":")
        if ll in te._SECTION_HEADERS and ll.startswith("reinsurance"):
            kinds.append("RI-ACCEPT")
            notes.append(f"'{lab}' {raw}")
        if not isinstance(v, (int, float)) or v == 0:
            if lab and not te._is_total_label(ll) and ll not in te._SECTION_HEADERS and all(
                    not (c or "").strip() for c in r[1:]):
                blank_after_label = True
            continue
        if not lab and blank_after_label:
            kinds.append("SPLIT-ROW")
            notes.append(f"unlabelled row {raw} under a label-only row")
        blank_after_label = False
        if lab and ll not in te._SECTION_HEADERS and ll not in te._SKIP_ROW_LABELS and not te._is_total_label(ll):
            cands.append({"line_of_business": lab, "amount_raw": abs(v)})
    _, dropped = te._drop_subtotal_rows([dict(c) for c in cands])
    for e in dropped:
        if not re.search(r"direct", e["line_of_business"], re.I):
            kinds.append("SUBTOTAL-DROP")
            notes.append(f"'{e['line_of_business']}' {e['amount_raw']:,.1f}")
    nums = [te._clean_cell(c) for r in g for c in r[1:]]
    nums = [abs(x) for x in nums if isinstance(x, (int, float))]
    if not any(abs(x * s - T) <= 0.02 * T for x in nums for s in (1.0, 0.001, 0.000001)) and not kinds:
        kinds.append("WRONG-TABLE")
        notes.append(f"t{ti} has no row near the report total")
    return "+".join(dict.fromkeys(kinds)) or "UNEXPLAINED", f"t{ti}: " + "; ".join(notes)


llm_index = collections.defaultdict(list)
for f in os.listdir(os.path.join(EX, "pdf_extraction", "llm_cache")):
    d = json.load(open(os.path.join(EX, "pdf_extraction", "llm_cache", f), encoding="utf-8"))
    m = d.get("_cache_meta") or {}
    if m.get("syndicate") is None or not isinstance(d.get("data"), dict):
        continue
    llm_index[(int(m["syndicate"]), int(m["year"]), m.get("prompt_version"))].append(d["data"])


def text_mechanism(stem, syn, yr, mix, pv):
    amounts = []
    for dd in llm_index.get((syn, yr, pv), []):
        for e in dd.get("gross_premium_mix") or []:
            a = e.get("amount_gbp_m")
            if isinstance(a, (int, float)):
                amounts.append(abs(a))
    if not amounts:
        return "TEXT", "no model mix to compare"
    hits = sum(1 for e in mix if any(abs(abs(e["amount_gbp_m"]) - a) <= max(0.051, 0.01 * a) for a in amounts))
    kind = "TEXT-PARTIAL" if hits == len(mix) else ("TEXT-NOT-PREMIUM" if hits == 0 else "TEXT-MIXED")
    return kind, f"{hits}/{len(mix)} adopted amounts are rows of the models' premium table"


final = []
for f in flag:
    stem = f["stem"]
    syn, yr = (int(x) for x in stem.split("_")[1:3])
    d = json.load(open(os.path.join(AN, "pdf_extraction", stem + ".json"), encoding="utf-8"))
    ck = sorted(d["models"])[0]
    if not (d.get("validation") or {}).get("passed") and f["route"].startswith("llm:"):
        ck = f["route"].split(":", 1)[1]
    cm = d["models"][ck]
    mix = (cm.get("_adobe_lob") or {}).get("gross_premium_mix") or cm.get("gross_premium_mix") or []
    if f["route"] == "det:azure":
        mech, note = det_mechanism(stem, yr, mix, float(f["T"]))
    elif f["route"] == "det:azure_text_fallback":
        mech, note = text_mechanism(stem, syn, yr, mix, d["spec"]["prompt_version"])
    else:
        mech, note = "LLM", "the model's own mix; loader reconciles=" + f["loader_reconciles"]
    final.append({**f, "mechanism": mech, "detail": note})

with open(os.path.join(HERE, "m03_census_final.csv"), "w", encoding="utf-8", newline="") as fh:
    w = csv.DictWriter(fh, fieldnames=list(final[0].keys()))
    w.writeheader()
    w.writerows(final)

ws = [x for x in final if x["working_sample"] == "True"]
print(f"flagged {len(final)}, in working sample {len(ws)}")
c_all = collections.Counter(x["mechanism"] for x in final)
c_ws = collections.Counter(x["mechanism"] for x in ws)
for k, n in c_all.most_common():
    print(f"   {k:<28} {n:>4} (working sample {c_ws.get(k, 0)})")

# coverage of the check over the working sample
wsrows = [r for r in rows.values() if r.get("status") == "ok" and r.get("working_sample")]
def sources(r):  # same rule as m03_census_grade2.py
    out = []
    for src, v in r["llm"]:
        model = src.split()[1]
        kind = "gpw" if "gross_premiums_written" in src else "mix"
        if v and v > 0:
            out.append((f"{model}:{kind}", model, v))
    for a in r["azure"]:
        out.append((f"azure:t{a['table']}", "azure", a["value_m"]))
    return out


def corroborated(src, tol=0.02):  # same rule as m03_census_grade2.py
    best = None
    for i, (na, ga, a) in enumerate(src):
        sup = [nb for j, (nb, gb, b) in enumerate(src)
               if j != i and ga != gb and not (ga == "azure" and gb == "azure")
               and abs(a - b) <= tol * max(a, b)]
        if sup and (best is None or a > best[1]):
            best = (sorted({na, *sup}), a)
    return best


covered = [r for r in wsrows if r["class_total"] and corroborated(sources(r))]
print(f"working-sample records with a class total: {sum(1 for r in wsrows if r['class_total'])}; "
      f"with an independently corroborated premium total: {len(covered)}")
uncov = [r for r in wsrows if r["class_total"] and not corroborated(sources(r))]
print("working-sample records the check could not corroborate:", len(uncov))
for r in uncov:
    print("   ", r["stem"], r["route"], r["class_total"], [(s[:34], round(v, 3)) for s, v in r["llm"]][:4],
          [round(a["value_m"], 3) for a in r["azure"]][:4])

# markdown table
md = ["| stem | route | mechanism | classes | adopted class total (m) | larger total T (m) | T read by | ratio | working sample |",
      "|---|---|---|---:|---:|---:|---|---:|:-:|"]
order = {"TEXT": 0}
for x in sorted(final, key=lambda x: (x["mechanism"], float(x["ratio"]))):
    md.append(f"| {x['stem']} | {x['route'].replace('det:', '')} | {x['mechanism']} | {x['n_classes']} | "
              f"{float(x['class_total']):,.3f} | {float(x['T']):,.3f} | {x['T_sources']} | {float(x['ratio']):.3f} | "
              f"{'yes' if x['working_sample'] == 'True' else 'no'} |")
open(os.path.join(HERE, "m03_census_table.md"), "w", encoding="utf-8").write("\n".join(md) + "\n")
print("markdown rows:", len(md) - 2)
