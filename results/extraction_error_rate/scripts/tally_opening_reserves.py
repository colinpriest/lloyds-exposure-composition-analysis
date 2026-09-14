r"""The opening-reserve checks, which the protocol reports separately from the error rate (read-only).

error-rate-protocol.md, "What is checked": "The opening reserves are checked at the same time, against a 2%
tolerance, and reported separately. An error there matters because severity is the ratio."

For every merged reading file (error-rate-verdicts*.json, batch files left out) this counts the first readings'
opening_reserves.within_2pct (true, false, not recorded), lists every false with its figures, and lists every second
reading (error-rate-verification*.json) whose text puts the opening reserves outside the tolerance or names another
figure for them. A record is marked WS when it is in the working sample the third sample was drawn from.

    python tally_opening_reserves.py
"""
import glob
import io
import json
import re
import sys
from pathlib import Path

SCR = Path(__file__).resolve().parent
sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def load(p):
    return json.load(io.open(str(p), encoding="utf-8"))


third = load(SCR / "error-rate-sample-third.json")
ws = set(load(SCR / "error-rate-population-698.json")["stems"]) - set(third["left"]["stems"]) | set(third["E_entrants"]["stems"])

print("First readings (merged files)")
outside = {}
for p in sorted(glob.glob(str(SCR / "error-rate-verdicts*.json"))):
    if "-batch-" in Path(p).name:
        continue
    rows = load(p)
    if not isinstance(rows, list):
        continue
    t = f = n = 0
    for r in rows:
        o = r.get("opening_reserves") if isinstance(r, dict) else None
        w = o.get("within_2pct") if isinstance(o, dict) else None
        if w is True:
            t += 1
        elif w is False:
            f += 1
            outside.setdefault(r["stem"], []).append((Path(p).name, o))
        else:
            n += 1
    print("  %-44s records %3d  within 2%% %3d  outside %2d  not recorded %2d" % (Path(p).name, len(rows), t, f, n))
print("  outside the tolerance at a first reading:")
for s in sorted(outside):
    for name, o in outside[s]:
        print("    %-22s WS %-5s %-40s adopted %s filing %s page %s" % (s, s in ws, name, o.get("adopted_m"), o.get("filing_m"), o.get("page")))

print("Second readings naming a problem with the opening reserves")
pat = re.compile(r"[Oo]pening[^.]{0,160}(outside|not agree|disagree|differs|reinsurers' share|instead|rather|wrong|misread)")
for p in sorted(glob.glob(str(SCR / "error-rate-verification*.json"))):
    rows = load(p)
    if not isinstance(rows, list):
        continue
    for r in rows:
        why = r.get("why") or ""
        m = pat.search(why)
        if m:
            print("  %-22s WS %-5s %-40s ... %s ..." % (r["stem"], r["stem"] in ws, Path(p).name, why[m.start(): m.start() + 420]))
