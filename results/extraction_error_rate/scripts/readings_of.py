r"""Every reading a record has had, in any sample or census, and whether it is in the working sample (read-only).

    python readings_of.py syndicate_457_2017 syndicate_1884_2019 ...
    python readings_of.py --prefix syndicate_457_ syndicate_1884_
"""
import glob
import io
import json
import sys
from pathlib import Path

SCR = Path(__file__).resolve().parent
sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def load(p):
    return json.load(io.open(str(p), encoding="utf-8"))


third = load(SCR / "error-rate-sample-third.json")
ws = set(load(SCR / "error-rate-population-698.json")["stems"]) - set(third["left"]["stems"]) | set(third["E_entrants"]["stems"])

readings = {}
for p in sorted(glob.glob(str(SCR / "error-rate-verdicts*.json")) + glob.glob(str(SCR / "error-rate-verification*.json"))):
    name = Path(p).name
    if "-batch-" in name:
        continue
    rows = load(p)
    if not isinstance(rows, list):
        continue
    kind = "second" if "verification" in name else "first"
    for r in rows:
        if isinstance(r, dict) and "stem" in r:
            v = r.get("verdict")
            c = r.get("clarified_verdict")
            readings.setdefault(r["stem"], []).append("%s %s %s%s" % (name.replace("error-rate-", "").replace(".json", ""),
                                                                    kind, v, "" if c in (None, v) else "/clarified " + c))

args = sys.argv[1:]
if args and args[0] == "--prefix":
    stems = sorted(s for s in ws if any(s.startswith(p) for p in args[1:]))
else:
    stems = args
for s in stems:
    print("%-22s WS %-5s %s" % (s, s in ws, "; ".join(readings.get(s, ["never read"]))))
