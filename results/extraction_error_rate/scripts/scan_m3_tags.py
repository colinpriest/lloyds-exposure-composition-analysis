r"""Mechanism M3 by its note tag as well as its route field (read-only).

scan_mechanism_variants.py found provisions overrides by the _pyd_route field, which records extracted before round
55 may lack. This reads the note tag every provisions override writes ("RAG OVERRIDE: Model said PYD=x, RAG
provisions computed y") in the working tree's records (stable after the replay) and lists the working-sample records
where the computed figure differs from every model's said value beyond max(0.5, 5% of it), with whether the record
carries the route field.

    python scan_m3_tags.py
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
TAG = re.compile(r"RAG OVERRIDE: Model said PYD=(-?\d+(?:\.\d+)?), RAG provisions computed (-?\d+(?:\.\d+)?)")

d = json.load(io.open(str(SCR / "error-rate-population-698.json"), encoding="utf-8"))
if isinstance(d, dict):
    for key in ("stems", "population", "working_sample", "records", "rows"):
        if key in d:
            d = d[key]
            break
ws = set(d) if isinstance(d, dict) else {r if isinstance(r, str) else r["stem"] for r in d}
if len(ws) != 698:
    raise SystemExit("the population file gives %d stems, not 698" % len(ws))

hits = []
for p in sorted(glob.glob(str(EXT / "pdf_extraction" / "syndicate_*.json"))):
    stem = Path(p).stem
    rec = json.load(io.open(p, encoding="utf-8"))
    models = rec.get("models") or {}
    said, computed, routed = [], None, False
    for md in models.values():
        for s, c in TAG.findall(md.get("data_quality_notes") or ""):
            said.append(float(s))
            computed = float(c)
        routed = routed or (md.get("_pyd_route") or {}).get("source") == "rag_provisions"
    if computed is None:
        continue
    far = all(abs(computed - s) > max(0.5, 0.05 * abs(computed)) for s in said)
    hits.append({"stem": stem, "ws": stem in ws, "route_field": routed, "said": said, "computed": computed, "far": far})

for needed in ("syndicate_1206_2014", "syndicate_2008_2019"):
    if not any(h["stem"] == needed and h["far"] for h in hits):
        raise SystemExit("the tag scan does not flag %s, which the route scan did: it is wrong" % needed)
print("records with a provisions-override tag: %d; in the working sample %d; carrying the route field %d"
      % (len(hits), sum(h["ws"] for h in hits), sum(h["route_field"] for h in hits)))
for h in hits:
    if h["ws"] and h["far"]:
        print("  working sample, computed far from every model's value: %s said %s computed %s %s"
              % (h["stem"], h["said"], h["computed"], "(route field)" if h["route_field"] else "(NO route field)"))
