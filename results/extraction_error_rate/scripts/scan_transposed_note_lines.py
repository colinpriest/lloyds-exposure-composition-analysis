r"""Candidates for the transposed-row mechanism of 2010/2019 and 2010/2018 (read-only).

In those filings the provisions note's line labelled "Change in prior year provisions" holds the current year of
account's claims: its gross value matches the current underwriting year's first estimate in the filing's own gross
triangle (136,599 against 132,679 for 2019; 178,295 against 179,777 for 2018, the gap being exchange translation).
A figure taken from such a line is not development.

For every record in the working tree whose adopted figure is not triangle-routed, this compares the adopted figure with
the first-row cell of the report year's underwriting year in the record's deterministic triangle (else the models'
triangle), in the triangle's units, and lists those within 5%. A candidate is not an error: a real prior-year movement
can equal a first-year estimate by chance, so each needs reading. The scan refuses to report unless it flags
2010/2018, the record that defines it (2010/2019 is now triangle-routed after its repair).

    python scan_transposed_note_lines.py
"""
import glob
import io
import json
import sys
from pathlib import Path

SCR = Path(__file__).resolve().parent
EXT = Path(r"D:/dev/lloyds_reserve_stress_testing")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
SCALE = {"thousands": 0.001, "millions": 1.0}


def working_sample():
    d = json.load(io.open(str(SCR / "error-rate-sample-third.json"), encoding="utf-8"))
    pop = json.load(io.open(str(SCR / "error-rate-population-698.json"), encoding="utf-8"))["stems"]
    left = set(d["left"]["stems"])
    return set(pop) - left | set(d["E_entrants"]["stems"])


ws = working_sample()
hits = []
for p in sorted(glob.glob(str(EXT / "pdf_extraction" / "syndicate_*_*.json"))):
    stem = Path(p).stem
    parts = stem.split("_")
    if len(parts) != 3 or not parts[2].isdigit():
        continue
    year = int(parts[2])
    rec = json.load(io.open(p, encoding="utf-8"))
    for model, md in sorted((rec.get("models") or {}).items()):
        adopted = md.get("prior_year_development_gbp_m")
        if adopted is None or (md.get("_pyd_route") or {}).get("source") == "rag_triangle":
            continue
        for kind in ("_rag_triangle", "_claims_triangle"):
            tri = md.get(kind) or {}
            ys, rows = tri.get("underwriting_years") or [], tri.get("development_rows") or []
            scale = SCALE.get((tri.get("units") or "").lower())
            if year not in ys or not rows or scale is None:
                continue
            j = ys.index(year)
            first = rows[0][j] if j < len(rows[0]) else None
            if first is None or first == 0:
                continue
            first_m = first * scale
            if abs(adopted - first_m) <= 0.05 * abs(first_m):
                hits.append({"stem": stem, "in_working_sample": stem in ws, "model": model, "adopted": adopted,
                             "first_estimate_m": round(first_m, 3), "triangle": kind})
            break

by_stem = {}
for h in hits:
    by_stem.setdefault(h["stem"], h)
if "syndicate_2010_2018" not in by_stem:
    raise SystemExit("the scan does not flag 2010/2018, the record that defines it: it is wrong")
print("candidates: %d records, %d in the working sample" % (len(by_stem), sum(h["in_working_sample"] for h in by_stem.values())))
for s, h in sorted(by_stem.items()):
    print("  %-22s %-3s adopted %-10s current year's first estimate %-10s (%s, %s)"
          % (s, "WS" if h["in_working_sample"] else "", h["adopted"], h["first_estimate_m"], h["triangle"], h["model"]))
