r"""Working-sample records whose adopted figure a loss-ratio grid may have produced (read-only).

623/2014 adopts -17.3, a sum of loss-ratio points from a grid gpt-5-mini stored as millions, through the code
override. 2623/2019 adopts -7.441 through the RAG direction override, whose note says a "loss ratio triangle computed"
it. This lists every model block of every working-sample record whose notes say a figure came from a loss-ratio
triangle, or that stores a triangle in percentage units and records a code or direction override, with the override
text, so each can be judged. A listed record is not an error until its figure's source is traced.
The scan refuses to report unless it flags 623/2014 and 2623/2019, the records that define it.

    python scan_loss_ratio_figures.py
"""
import glob
import io
import json
import re
import sys
from pathlib import Path

SCR = Path(__file__).resolve().parent
EXT = Path(r"D:/dev/lloyds_reserve_stress_testing")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
DEFINERS = ("syndicate_623_2014", "syndicate_2623_2019")
LR = re.compile(r"loss[ -]ratio triangle", re.I)
OVERRIDE = re.compile(r"\[(CODE OVERRIDE|RAG DIRECTION OVERRIDE)[^\]]*\]")


def load(p):
    return json.load(io.open(str(p), encoding="utf-8"))


third = load(SCR / "error-rate-sample-third.json")
ws = set(load(SCR / "error-rate-population-698.json")["stems"]) - set(third["left"]["stems"]) | set(third["E_entrants"]["stems"])
hits = {}
for p in sorted(glob.glob(str(EXT / "pdf_extraction" / "syndicate_*_*.json"))):
    stem = Path(p).stem
    parts = stem.split("_")
    if len(parts) != 3 or not parts[2].isdigit() or stem not in ws:
        continue
    rec = load(p)
    for model, md in sorted((rec.get("models") or {}).items()):
        text = " ".join(v for v in md.values() if isinstance(v, str))
        units = {k: (md.get(k) or {}).get("units") for k in ("_rag_triangle", "_claims_triangle") if md.get(k)}
        pct = any((u or "").lower() in ("percentage", "percent", "%", "ratio") for u in units.values())
        ov = OVERRIDE.findall(text) and [m.group(0) for m in OVERRIDE.finditer(text)]
        if LR.search(text) or (pct and ov):
            hits.setdefault(stem, []).append((model, md.get("prior_year_development_gbp_m"),
                                              (md.get("_pyd_route") or {}).get("source"), units, ov or []))
missing = [d for d in DEFINERS if d not in hits]
if missing:
    raise SystemExit("the scan does not flag %s, the records that define it: it is wrong" % missing)
print("candidates: %d working-sample records" % len(hits))
for stem in sorted(hits):
    for model, adopted, route, units, ov in hits[stem]:
        print("  %-22s %-17s adopted %-9s route %-20s units %s" % (stem, model, adopted, route, units))
        for o in ov:
            print("      %s" % o[:400])
