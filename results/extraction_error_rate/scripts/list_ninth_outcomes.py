"""List the ninth census's records by outcome: each reading's finding and amount, and the reason.

    python list_ninth_outcomes.py
"""
import io
import json
from pathlib import Path

SCR = Path(__file__).resolve().parent
res = json.load(io.open(str(SCR / "error-rate-census-ninth-result.json"), encoding="utf-8"))
print("records %d; outcomes %s" % (res["records"], res["outcomes"]))


def ans(a):
    if not a:
        return "-"
    return "%s/%s" % ({True: "T", False: "F", None: "null"}[a["finding"]], a["takeon_amount_m"])


for outcome in ("adjusted", "not adjusted"):
    print("== %s" % outcome)
    for r in res["table"]:
        if r["outcome"] == outcome:
            print("  %-22s first %-16s second %-16s sev %s -> %s | %s"
                  % (r["stem"], ans(r["first"]), ans(r["second"]), r["severity_pct"], r["severity_pct_adjusted"],
                     r["reason"]))
