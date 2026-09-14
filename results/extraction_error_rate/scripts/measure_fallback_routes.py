r"""Which figures carry a `rag_triangle` route although the RAG step used no triangle, and what the loader makes of them.

The driver records `_pyd_route.source = "rag_triangle"` whenever the RAG step returned a figure,
whatever the method (test_gemini.py, the `_record_pyd_route` calls after "Apply to both models"):
a deterministic triangle, but also the provisions fallback, provisions text, the reserves-movement
note, the narrative parsers and the loss-ratio grid. The triangle keys are written only when a
triangle came back, so a route without them names a triangle that does not exist. 1994/2024 and
4020/2023 in the error-rate sample are two: their replay logs print "No triangle, but found 1
reserve text page(s)" and "Using provisions PYD as fallback".

Where such a figure differed from the model's by 0.5m or more, the driver also wrote
"[RAG OVERRIDE: ... RAG triangle computed ...]", which the loader reads as a triangle route
(pyd_cohort_scope: cohort-enforced; pyd_basis step 1b: the basis of whatever triangle the block
holds). Whether that happens is measured here, not assumed.

Over every record the loader reads, and over the working sample:
  - rag_triangle routes with and without their triangle keys, per model block;
  - the RAG method each record's own replay log prints;
  - for routes without a triangle: the route note, whether an override annotation matches the
    figure, and the loader's cohort scope and basis on the observation.
Read-only and offline. Writes fallback-routes.json.

    python measure_fallback_routes.py
"""
import glob
import io
import json
import os
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

AN = Path(r"D:/dev/IME-Lloyds-exposure-composition")
EX = Path(r"D:/dev/lloyds_reserve_stress_testing")
SCR = Path(__file__).resolve().parent
OUT = SCR / "fallback-routes.json"
sys.path.insert(0, str(AN / "src"))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import run_analysis as ra  # noqa: E402
import adopted_model  # noqa: E402

HEADER = re.compile(r"^\[\d+/\d+\] Syndicate (\S+) / (\d{4})\b")
TRIANGLE_KEYS = ("triangle_type", "triangle_units", "triangle_source_page")
# what the RAG step prints when its figure did not come from a claims triangle
NON_TRIANGLE = (
    ("provisions_fallback", "Using provisions PYD as fallback"),
    # printed by the in-RAG sign check: "Triangle PYD (...) disagrees in sign with provisions (...) -- using provisions"
    ("provisions_over_triangle", "using provisions"),
    ("reserves_movement", "Reserves movement note overrides first-year"),
    ("provisions_text", "[RAG] Provisions text PYD:"),
    ("pl_narrative", "[RAG] P&L narrative PYD:"),
    ("yoa_narrative", "[RAG] YOA narrative PYD:"),
    ("general_narrative", "[RAG] General narrative PYD:"),
    ("loss_ratio_triangle", "[RAG] Loss ratio triangle PYD:"),
)


def load(p):
    return json.load(io.open(str(p), encoding="utf-8"))


def text(notes):
    return notes if isinstance(notes, str) else " ".join(map(str, notes or []))


def log_blocks():
    """stem -> [(log file, lines)] in file-name order, one entry per time the replay reached it."""
    blocks = defaultdict(list)
    for p in sorted(glob.glob(str(SCR / "r193-replay-*.log"))):
        cur, lines = None, []
        for ln in io.open(p, encoding="utf-8", errors="replace"):
            m = HEADER.match(ln)
            if m:
                if cur:
                    blocks[cur].append((os.path.basename(p), lines))
                cur, lines = "syndicate_%s_%s" % (m.group(1), m.group(2)), []
            elif cur:
                lines.append(ln.rstrip("\n"))
        if cur:
            blocks[cur].append((os.path.basename(p), lines))
    return blocks


def methods(lines):
    return [name for name, marker in NON_TRIANGLE if any(marker in ln for ln in lines)]


def tag_matches(notes, figure):
    tags = ra.OVERRIDE_TAG.findall(text(notes))
    if not tags or figure is None:
        return None
    computed = ra.safe_float(tags[-1][1])
    if computed is None:
        return None
    return {"tag": tags[-1], "matches": abs(abs(computed) - abs(figure)) <= max(0.01, 0.005 * abs(figure))}


S, R, H, yr, syn, ritc = adopted_model.load_sample()
sample = {"syndicate_%s_%s" % (s, y) for s, y in zip(syn, yr)}
results = load(AN / "model" / "exposure_results.json")
obs = {"syndicate_%s_%s" % (o["syndicate"], o["year"]): o for o in results["observations"]}
vetoed = {r["stem"] for r in load(EX / "pdf_extraction" / "audit" / "triangle_overruled_by_sign_veto.json")
          ["sign_veto_overrides"]["records"]}
blocks = log_blocks()

rows = []
scanned = 0
for p in sorted(glob.glob(str(AN / "pdf_extraction" / "syndicate_*.json"))):
    stem = os.path.basename(p)[:-5]
    if stem.count("_") != 2:
        continue
    try:
        rec = load(p)
    except (ValueError, OSError):
        continue
    scanned += 1
    per_block = {}
    for mk, m in sorted((rec.get("models") or {}).items()):
        route = m.get("_pyd_route") or {}
        if route.get("source") != "rag_triangle":
            continue
        figure = ra.safe_float(m.get("prior_year_development_gbp_m"))
        per_block[mk] = {
            "triangle_keys": any(k in route for k in TRIANGLE_KEYS),
            "note": route.get("note"),
            "route_value": route.get("value"),
            "model_value": route.get("model_value"),
            "figure": figure,
            "override_annotation": tag_matches(m.get("data_quality_notes"), figure),
            "stored_rag_triangle": bool(m.get("_rag_triangle")),
            "claims_triangle_type": (m.get("_claims_triangle") or {}).get("type"),
        }
    if not per_block:
        continue
    lb = blocks.get(stem) or []
    o = obs.get(stem)
    keys = {v["triangle_keys"] for v in per_block.values()}
    rows.append({
        "stem": stem,
        "in_working_sample": stem in sample,
        "kind": ("triangle" if keys == {True} else "no-triangle" if keys == {False} else "blocks-disagree"),
        "blocks": per_block,
        "replay_log": lb[-1][0] if lb else None,
        "replay_blocks": len(lb),
        "non_triangle_methods_in_log": methods(lb[-1][1]) if lb else None,
        "in_sign_veto_register": stem in vetoed,
        "loader": ({k: o.get(k) for k in ("pyd_cohort_scope", "pyd_cohort_route", "pyd_basis", "pyd_basis_source")}
                   if o else None),
    })


def report(rs, label):
    print("\n== %s: %d records with a rag_triangle route" % (label, len(rs)))
    kinds = Counter(r["kind"] for r in rs)
    print("   by triangle keys: %s" % dict(kinds))
    for kind in ("no-triangle", "triangle", "blocks-disagree"):
        sub = [r for r in rs if r["kind"] == kind]
        if not sub:
            continue
        c = Counter(("NO REPLAY LOG" if r["non_triangle_methods_in_log"] is None else
                     ",".join(r["non_triangle_methods_in_log"]) or "(no non-triangle method printed)") for r in sub)
        print("   %s -- the method the replay log prints:" % kind)
        for k, v in c.most_common():
            print("      %-46s %d" % (k, v))
        if kind == "triangle":
            odd = [r for r in sub if r["non_triangle_methods_in_log"]]
            print("      of which in the sign-veto register: %d of %d printing a non-triangle method"
                  % (sum(1 for r in odd if r["in_sign_veto_register"]), len(odd)))
            print("      not in the register: %s" % [r["stem"] for r in odd if not r["in_sign_veto_register"]][:20])
    nt = [r for r in rs if r["kind"] == "no-triangle"]
    if nt:
        notes = Counter(" | ".join(sorted({str(v["note"]) for v in r["blocks"].values()})) for r in nt)
        print("   no-triangle routes by route note: %s" % dict(notes))
        tagged = [r for r in nt if any((v["override_annotation"] or {}).get("matches") for v in r["blocks"].values())]
        print("   no-triangle routes carrying an override annotation that matches the figure: %d" % len(tagged))
        with_loader = [r for r in nt if r["loader"]]
        print("   loader cohort scope on the observation: %s"
              % dict(Counter(str(r["loader"]["pyd_cohort_scope"]) for r in with_loader)))
        print("   loader basis source on the observation: %s"
              % dict(Counter(str(r["loader"]["pyd_basis_source"]) for r in with_loader)))


report(rows, "every record the loader reads (%d scanned)" % scanned)
report([r for r in rows if r["in_working_sample"]], "working sample (%d records)" % len(sample))
ws_nt = [r for r in rows if r["in_working_sample"] and r["kind"] != "triangle"]
print("\nworking-sample records whose rag_triangle route carries no triangle:")
for r in ws_nt:
    b = next(iter(r["blocks"].values()))
    print("  %-22s methods %-28s note %-30s figure %9s annotation %-5s loader %s"
          % (r["stem"], ",".join(r["non_triangle_methods_in_log"] or []) or str(r["non_triangle_methods_in_log"]),
             b["note"], b["figure"], (b["override_annotation"] or {}).get("matches"),
             (r["loader"] or {}).get("pyd_cohort_scope")))
io.open(str(OUT), "w", encoding="utf-8").write(json.dumps(
    {"scanned": scanned, "working_sample_n": len(sample), "rows": rows}, indent=1, ensure_ascii=False))
print("\nwritten: %s" % OUT.name)
