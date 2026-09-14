r"""Scan every extraction record for the mechanisms the records found in passing showed (read-only).

Reads the committed records at the extraction repo's HEAD through `git cat-file --batch`, so the running replay cannot
hand it a half-written file, and marks each hit that is in the working sample (error-rate-population-698.json).

M1  a model's stored triangle starts later than the pipeline's deterministic triangle: the model dropped the oldest
    column(s), as both models did for 1225/2022 (the single year 2017, taken for the '2017 & Prior' column of another
    table). Listed with the deterministic figure the note quotes and whether it was applied.
M2  a CODE OVERRIDE computed the figure from a model's stored triangle that looks shifted one column (the latest
    year's first-row cell empty while every other first-row cell is filled) or that is stored as money while another
    reading of the same record says percentage or loss ratio, as for 623/2014.
M3  a rag_provisions route overrode the model's value, as for 1206/2014: listed, not diagnosed.
M4  a RAG direction override from a loss-ratio triangle, as for 623/2022: listed, not diagnosed.

The scan refuses to report unless it finds the record that defines each of M1-M4.

    python scan_mechanism_variants.py
"""
import io
import json
import re
import subprocess
import sys
from pathlib import Path

SCR = Path(__file__).resolve().parent
EXT = Path(r"D:/dev/lloyds_reserve_stress_testing")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
DET = re.compile(r"deterministic figure ([+-]?\d+(?:\.\d+)?)m")
SRC = re.compile(r"OVERRIDE from ([\w.\-]+) triangle")
RATIO_UNITS = ("percentage", "percent", "%", "ratio")


def working_sample():
    d = json.load(io.open(str(SCR / "error-rate-population-698.json"), encoding="utf-8"))
    if isinstance(d, dict):
        for key in ("stems", "population", "working_sample", "records", "rows"):
            if key in d:
                d = d[key]
                break
    stems = set(d) if isinstance(d, dict) else {r if isinstance(r, str) else r["stem"] for r in d}
    if len(stems) != 698:
        raise SystemExit("the population file gives %d stems, not 698" % len(stems))
    return stems


def years(t):
    return (t or {}).get("underwriting_years") or []


def first_row(t):
    rows = (t or {}).get("development_rows") or []
    return rows[0] if rows else []


def committed_records():
    names = subprocess.run(["git", "-C", str(EXT), "ls-tree", "--name-only", "HEAD", "pdf_extraction/"],
                           capture_output=True, text=True, check=True).stdout.split()
    names = [n for n in names if re.fullmatch(r"pdf_extraction/syndicate_\d+_\d{4}\.json", n)]
    p = subprocess.Popen(["git", "-C", str(EXT), "cat-file", "--batch"], stdin=subprocess.PIPE, stdout=subprocess.PIPE)
    for n in names:
        p.stdin.write(("HEAD:%s\n" % n).encode())
        p.stdin.flush()
        header = p.stdout.readline().split()
        if len(header) < 3 or header[1] != b"blob":
            raise SystemExit("git cat-file gave %r for %s" % (header, n))
        body = p.stdout.read(int(header[2]))
        p.stdout.read(1)
        yield Path(n).stem, json.loads(body.decode("utf-8"))
    p.stdin.close()
    p.wait()


ws = working_sample()
m1, m2, m3, m4 = {}, {}, {}, {}
n_records = 0
for stem, rec in committed_records():
    n_records += 1
    models = rec.get("models") or {}
    for m, md in models.items():
        notes = md.get("data_quality_notes") or ""
        adopted = md.get("prior_year_development_gbp_m")
        t, r = md.get("_claims_triangle"), md.get("_rag_triangle")
        ty, ry = years(t), years(r)
        if ty and ry and min(ry) < min(ty):
            fr = first_row(r)
            single = (len(fr) > 1 and fr[0] is not None and fr[1] is not None and abs(fr[0]) <= 3 * abs(fr[1]))
            e = m1.setdefault(stem, {"stem": stem, "in_working_sample": stem in ws, "models": {}})
            e["models"][m] = {"adopted": adopted, "model_years": [min(ty), max(ty)], "rag_years": [min(ry), max(ry)],
                              "dropped": sorted(set(ry) - set(ty)), "deterministic": DET.findall(notes),
                              "rag_not_applied": "RAG PYD NOT APPLIED" in notes,
                              "oldest_rag_column_single_year_like": single}
        if "CODE OVERRIDE" in notes:
            hit = SRC.search(notes)
            src = hit.group(1) if hit else None
            sources = list(models) if src in (None, "agreed") else [src]
            for sm in sources:
                st = (models.get(sm) or {}).get("_claims_triangle") or {}
                fr, sy = first_row(st), years(st)
                shifted = bool(fr and sy and fr[-1] is None and fr[0] is not None
                               and sum(v is not None for v in fr) == len(sy) - 1)
                readings = {mm: ((mdd.get("_claims_triangle") or {}).get("units"),
                                 (mdd.get("_claims_triangle") or {}).get("type"),
                                 (mdd.get("_rag_triangle") or {}).get("type")) for mm, mdd in models.items()}
                ratio_elsewhere = any((u or "").lower() in RATIO_UNITS or "ratio" in (ct or "") or "ratio" in (rt or "")
                                      for u, ct, rt in readings.values())
                stored_as_money = (st.get("units") or "").lower() not in RATIO_UNITS and "ratio" not in (st.get("type") or "")
                if shifted or (ratio_elsewhere and stored_as_money):
                    e = m2.setdefault(stem, {"stem": stem, "in_working_sample": stem in ws, "hits": {}})
                    e["hits"][m] = {"adopted": adopted, "source_triangle": sm, "shifted": shifted,
                                    "ratio_elsewhere_stored_as_money": bool(ratio_elsewhere and stored_as_money),
                                    "readings": readings}
        route = md.get("_pyd_route") or {}
        if route.get("source") == "rag_provisions" and route.get("model_value") is not None \
                and route.get("value") != route.get("model_value"):
            m3.setdefault(stem, {"stem": stem, "in_working_sample": stem in ws, "models": {}})["models"][m] = {
                "adopted": adopted, "rag_value": route.get("value"), "model_value": route.get("model_value")}
        if "loss ratio triangle computed" in notes:
            m4.setdefault(stem, {"stem": stem, "in_working_sample": stem in ws, "models": {}})["models"][m] = {
                "adopted": adopted}

for name, found, needed in (("M1", m1, "syndicate_1225_2022"), ("M2", m2, "syndicate_623_2014"),
                            ("M3", m3, "syndicate_1206_2014"), ("M4", m4, "syndicate_623_2022")):
    if needed not in found:
        raise SystemExit("%s does not find %s, the record that defines it: the scan is wrong" % (name, needed))

io.open(str(SCR / "mechanism-variants-scan.json"), "w", encoding="utf-8", newline="").write(json.dumps(
    {"read": "extraction HEAD via git cat-file", "records": n_records,
     "M1": sorted(m1.values(), key=lambda x: x["stem"]), "M2": sorted(m2.values(), key=lambda x: x["stem"]),
     "M3": sorted(m3.values(), key=lambda x: x["stem"]), "M4": sorted(m4.values(), key=lambda x: x["stem"])},
    indent=1, ensure_ascii=False) + "\n")
print("records read: %d" % n_records)
for name, found in (("M1", m1), ("M2", m2), ("M3", m3), ("M4", m4)):
    inws = [e for e in found.values() if e["in_working_sample"]]
    print("%s: %d records, %d in the working sample" % (name, len(found), len(inws)))
    for e in sorted(inws, key=lambda x: x["stem"]):
        print("   ", e["stem"], json.dumps(e.get("models") or e.get("hits"), ensure_ascii=False)[:600])
print("written mechanism-variants-scan.json")
