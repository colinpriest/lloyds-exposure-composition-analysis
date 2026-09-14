r"""The verification set, one line per record: first and clarified verdicts, source, figures, why it is in the set, and whether it is second-read yet.

    python show_vset.py
"""
import io
import json
from pathlib import Path

SCR = Path(__file__).resolve().parent


def load(name):
    return json.load(io.open(str(SCR / name), encoding="utf-8"))


rows = {r["stem"]: r for r in load("error-rate-verdicts.json")}
vset = load("error-rate-verification-set.json")
done = {v["stem"]: v["verdict"] for v in load("error-rate-verification.json")}
reasons = {}
for name, members in vset.items():
    if isinstance(members, list) and name != "all":
        for s in members:
            reasons.setdefault(s, []).append(name[:20])
for s in vset["all"]:
    r = rows[s]
    print("%-22s %-8s first %-14s clarified %-14s src %-8s done %-14s adopted %9s filing %9s rec %9s  %s" % (
        s, r["first_reader"], r["verdict"], r["clarified_verdict"], r["figure_source"], done.get(s, "-"),
        r.get("adopted_figure_m"), r.get("filing_figure_m"), r.get("triangle_recomputation_m"),
        ",".join(reasons.get(s, []))))
print("\nverified %d of %d" % (sum(1 for s in vset["all"] if s in done), len(vset["all"])))
