r"""Candidates for Syndicate 382's mechanism: a movement (incremental) table stored as a cumulative triangle (read-only).

In 382/2015 and 382/2016 the printed development tables are incremental: each row after the first holds the year's
movement, and the column's estimates are the first row plus the movements. The stored grid keeps those rows, and the
pipeline differences consecutive rows as if they were cumulative estimates. A cumulative triangle's later cells stay
close to the column's first estimate; a movement table's later cells are small beside it and often negative.

For every stored triangle of every working-sample record (every model, both kinds), over the cells after the first row:
  neg   the share of cells below zero
  small the share of cells whose size is under a quarter of their column's first cell
A triangle is a candidate when neg >= 0.2 or small >= 0.5. A candidate is not an error: a table of changes can be
printed for other reasons, and a triangle routed nowhere does not touch the adopted figure. The route source is shown.
The scan refuses to report unless it flags 382/2015 and 382/2016, the records that define it.

    python scan_incremental_triangles.py
"""
import glob
import io
import json
import sys
from pathlib import Path

SCR = Path(__file__).resolve().parent
EXT = Path(r"D:/dev/lloyds_reserve_stress_testing")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
DEFINERS = ("syndicate_382_2015", "syndicate_382_2016")


def working_sample():
    d = json.load(io.open(str(SCR / "error-rate-sample-third.json"), encoding="utf-8"))
    pop = json.load(io.open(str(SCR / "error-rate-population-698.json"), encoding="utf-8"))["stems"]
    return set(pop) - set(d["left"]["stems"]) | set(d["E_entrants"]["stems"])


def shape(tri):
    rows = tri.get("development_rows") or []
    if len(rows) < 3 or not rows[0]:
        return None
    later, neg, small = 0, 0, 0
    for j, first in enumerate(rows[0]):
        if not isinstance(first, (int, float)) or first == 0:
            continue
        for row in rows[1:]:
            if j >= len(row) or not isinstance(row[j], (int, float)):
                continue
            later += 1
            neg += row[j] < 0
            small += abs(row[j]) < 0.25 * abs(first)
    if later < 6:
        return None
    return {"cells": later, "neg": round(neg / later, 2), "small": round(small / later, 2)}


ws = working_sample()
hits = {}
for p in sorted(glob.glob(str(EXT / "pdf_extraction" / "syndicate_*_*.json"))):
    stem = Path(p).stem
    parts = stem.split("_")
    if len(parts) != 3 or not parts[2].isdigit() or stem not in ws:
        continue
    rec = json.load(io.open(p, encoding="utf-8"))
    for model, md in sorted((rec.get("models") or {}).items()):
        route = (md.get("_pyd_route") or {}).get("source")
        for kind in ("_rag_triangle", "_claims_triangle"):
            s = shape(md.get(kind) or {})
            if s and (s["neg"] >= 0.2 or s["small"] >= 0.5):
                hits.setdefault(stem, []).append(dict(s, model=model, kind=kind, route=route,
                                                      adopted=md.get("prior_year_development_gbp_m"),
                                                      page=(md.get(kind) or {}).get("source_page")))

missing = [d for d in DEFINERS if d not in hits]
if missing:
    raise SystemExit("the scan does not flag %s, the records that define it: it is wrong" % missing)
print("candidates: %d working-sample records (of %d)" % (len(hits), len(ws)))
for stem in sorted(hits):
    routed = [h for h in hits[stem] if h["route"] == "rag_triangle"]
    print("  %-22s %s" % (stem, "ROUTED" if routed else ""))
    for h in hits[stem]:
        print("      %-28s %-17s route %-20s neg %.2f small %.2f cells %3d adopted %s page %s"
              % (h["model"], h["kind"], h["route"], h["neg"], h["small"], h["cells"], h["adopted"], h["page"]))
