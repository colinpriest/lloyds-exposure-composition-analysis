r"""The working sample rebuilt after R209 (replayed records) and R210 (the basis rule), against the post-R208 sample.

Predictions, each from a measurement made before this rebuild:
- R210 removes exactly the working-sample records whose basis the isolated rule comparison moved
  away from gross (r210-rule-comparison.json).
- R209 moves the severity of exactly the working-sample records whose adopted figure the replay moved
  (r209-verified.json), each by its new figure over unchanged opening reserves.
- Opening reserves and HHI do not change. Any other entry, exit or change is listed and must be
  explained.

    python compare_r209_r210.py
"""
import io
import json
import sys
from collections import Counter
from pathlib import Path

AN = Path(r"D:/dev/IME-Lloyds-exposure-composition")
SCR = Path(__file__).resolve().parent
sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def load(p):
    return json.load(io.open(str(p), encoding="utf-8"))


def keyed(d):
    return {"%s_%s" % (o["syndicate"], o["year"]): o for o in d["observations"]}


def population(obs):
    return {k: o for k, o in obs.items()
            if o.get("s_raw_a") is not None and o.get("opening_reserves_gbp_m") and o.get("hhi") is not None}


b, a = load(SCR / "r209-exposure-results-before.json"), load(AN / "model" / "exposure_results.json")
allb, alla = keyed(b), keyed(a)
pb, pa = population(allb), population(alla)
r210_out = {r["record"] for r in load(SCR / "r210-rule-comparison.json")
            if r["in_working_sample"] and r["basis_after"][0] != "gross"}
moved = {m["stem"].replace("syndicate_", ""): m for m in load(SCR / "r209-verified.json")["moved"]}
sampled = {s.replace("syndicate_", "") for s in load(SCR / "error-rate-sample.json")["primary"]["stems"]}
problems = []

print("run %s -> %s" % (b.get("analysis_run_id"), a.get("analysis_run_id")))
print("observations %d -> %d; working sample %d -> %d" % (len(allb), len(alla), len(pb), len(pa)))
left, entered = sorted(set(pb) - set(pa)), sorted(set(pa) - set(pb))
print("left: %d %s" % (len(left), left))
print("  predicted by R210: %d; left and predicted: %d; predicted and still in: %s; left, not predicted by R210: %s"
      % (len(r210_out), len(set(left) & r210_out), sorted(r210_out - set(left)), sorted(set(left) - r210_out)))
for k in sorted(set(left) - r210_out):
    o = alla.get(k, {})
    print("    %s: basis %s/%s -> %s/%s; figure moved by R209: %s" % (
        k, allb[k].get("pyd_basis"), allb[k].get("pyd_basis_source"), o.get("pyd_basis"), o.get("pyd_basis_source"),
        k in moved))
if r210_out - set(left):
    problems.append("R210 removals that did not happen: %s" % sorted(r210_out - set(left)))
print("entered: %d %s" % (len(entered), entered))
for k in entered:
    print("    %s: basis %s -> %s; figure moved by R209: %s" % (k, allb.get(k, {}).get("pyd_basis"), alla[k].get("pyd_basis"), k in moved))

stay = sorted(set(pb) & set(pa))
fixed = [(k, f) for k in stay for f in ("opening_reserves_gbp_m", "hhi") if pb[k].get(f) != pa[k].get(f)]
print("opening or HHI changed on a record that stayed: %d %s" % (len(fixed), fixed[:10]))
if fixed:
    problems.append("opening reserves or HHI changed on %d records" % len(fixed))
sev = sorted(k for k in stay if pb[k].get("s_raw_a") != pa[k].get("s_raw_a"))
print("severity changed on a record that stayed: %d" % len(sev))
unexplained = [k for k in sev if k not in moved]
if unexplained:
    problems.append("severity changed without a moved figure: %s" % unexplained)
not_seen = sorted(k for k in moved if k in stay and k not in sev)
print("  figure moved by R209 but severity unchanged: %s" % not_seen)
for k in sev:
    m = moved.get(k, {})
    print("    %-10s sample %-5s figure %s -> %s  severity %.5f -> %.5f" % (
        k, k in sampled, m.get("before"), m.get("after"), pb[k]["s_raw_a"], pa[k]["s_raw_a"]))
print("cohort scope changes on records that stayed: %s" % dict(Counter(
    "%s -> %s" % (pb[k].get("pyd_cohort_scope"), pa[k].get("pyd_cohort_scope"))
    for k in stay if pb[k].get("pyd_cohort_scope") != pa[k].get("pyd_cohort_scope"))))
print("error-rate sample: left %s; severity changed %s" % (sorted(set(left) & sampled), sorted(set(sev) & sampled)))
print("\n" + ("AS PREDICTED" if not problems else "NOT AS PREDICTED:\n  " + "\n  ".join(problems)))
sys.exit(1 if problems else 0)
