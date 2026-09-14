"""The third result's A errors and each one's error kind, from the second reading, else the first (read-only).

    python basis_net_in_a.py
"""
import io
import json
from pathlib import Path

SCR = Path(__file__).resolve().parent


def rows(name):
    d = json.load(io.open(str(SCR / name), encoding="utf-8"))
    return {r["stem"]: r for r in (d if isinstance(d, list) else d.values()) if isinstance(r, dict) and "stem" in r}


res = json.load(io.open(str(SCR / "error-rate-result-third.json"), encoding="utf-8"))
first, second = rows("error-rate-verdicts-third.json"), rows("error-rate-verification-third.json")
errs = sorted(s for s, v in res["final_verdicts"]["A"].items() if v == "error")
for s in errs:
    print("%-22s second %-40s first %s" % (s, (second.get(s) or {}).get("error_kind"), (first.get(s) or {}).get("error_kind")))
print("basis-net among A's errors: %d" % sum(1 for s in errs if ((second.get(s) or first.get(s) or {}).get("error_kind") or "").startswith("basis-net")))
