r"""R208's loader rebuild against its prediction: what left or entered the working sample, and what changed on what stayed.

The prediction comes from PLAN R208 and route-correction-probe.json:
- the working sample loses exactly 1947/2019, whose basis becomes net, and gains nothing;
- no adopted severity, opening reserve or HHI changes on any record that stays;
- the cohort scope of exactly 1206/2014, 1221/2016, 1221/2023, 2008/2019, 2010/2015, 2010/2017,
  3010/2016 and 780/2014 moves from enforced to disclosed;
- the basis evidence of the probe's records moves from a triangle to the prompt default, with the
  basis unchanged;
- no record of the error-rate sample leaves the working sample.

    python compare_working_sample.py
"""
import io
import json
import sys
from collections import Counter
from pathlib import Path

AN = Path(r"D:/dev/IME-Lloyds-exposure-composition")
SCR = Path(__file__).resolve().parent
BEFORE = SCR / "r208-exposure-results-before.json"
AFTER = AN / "model" / "exposure_results.json"
PROBE = SCR / "route-correction-probe.json"
SAMPLE = SCR / "error-rate-sample.json"
ENFORCED = "mature-enforced"
PREDICTED_COHORT = {"1206_2014", "1221_2016", "1221_2023", "2008_2019", "2010_2015", "2010_2017", "3010_2016", "780_2014"}
FIGURES = ("s_raw_a", "opening_reserves_gbp_m", "hhi")


def load(p):
    return json.load(io.open(str(p), encoding="utf-8"))


def keyed(d):
    return {"%s_%s" % (o["syndicate"], o["year"]): o for o in d["observations"]}


def population(obs):
    """adopted_model.load_sample's filter."""
    return {k: o for k, o in obs.items()
            if o.get("s_raw_a") is not None and o.get("opening_reserves_gbp_m") and o.get("hhi") is not None}


b, a = load(BEFORE), load(AFTER)
allb, alla = keyed(b), keyed(a)
pb, pa = population(allb), population(alla)
problems = []
print("run %s -> %s" % (b.get("analysis_run_id"), a.get("analysis_run_id")))
print("observations %d -> %d; working sample %d -> %d" % (len(allb), len(alla), len(pb), len(pa)))
left, entered = sorted(set(pb) - set(pa)), sorted(set(pa) - set(pb))
print("left the working sample: %s" % left)
print("entered the working sample: %s" % entered)
if left != ["1947_2019"]:
    problems.append("left %s, predicted ['1947_2019']" % left)
if entered:
    problems.append("entered %s, predicted none" % entered)
for k in left:
    print("  %s: basis %s/%s -> %s/%s" % (k, allb[k].get("pyd_basis"), allb[k].get("pyd_basis_source"),
                                          alla.get(k, {}).get("pyd_basis"), alla.get(k, {}).get("pyd_basis_source")))

stay = sorted(set(pb) & set(pa))
moved = [(k, f, pb[k].get(f), pa[k].get(f)) for k in stay for f in FIGURES if pb[k].get(f) != pa[k].get(f)]
print("severity, opening or HHI changed on a record that stayed: %d %s" % (len(moved), moved[:10]))
if moved:
    problems.append("figures changed on %d record(s)" % len(moved))

cohort = sorted(k for k in stay if pb[k].get("pyd_cohort_scope") != pa[k].get("pyd_cohort_scope"))
print("cohort scope changed: %d %s" % (len(cohort), cohort))
if set(cohort) != PREDICTED_COHORT:
    problems.append("cohort changes differ from the prediction by %s" % sorted(set(cohort) ^ PREDICTED_COHORT))
wrong = [k for k in cohort if not (pb[k].get("pyd_cohort_scope") == ENFORCED and pa[k].get("pyd_cohort_scope") != ENFORCED)]
if wrong:
    problems.append("cohort changes other than enforced -> disclosed: %s" % wrong)
print("cohort-enforced in the working sample: %d -> %d" % (
    sum(1 for o in pb.values() if o.get("pyd_cohort_scope") == ENFORCED),
    sum(1 for o in pa.values() if o.get("pyd_cohort_scope") == ENFORCED)))

common = sorted(set(allb) & set(alla))
basis = sorted(k for k in common if allb[k].get("pyd_basis") != alla[k].get("pyd_basis"))
print("basis changed on any observation: %s" % [(k, allb[k].get("pyd_basis"), alla[k].get("pyd_basis")) for k in basis])
if basis != ["1947_2019"]:
    problems.append("basis changes %s, predicted ['1947_2019']" % basis)
evidence = sorted(k for k in common if allb[k].get("pyd_basis") == alla[k].get("pyd_basis")
                  and allb[k].get("pyd_basis_source") != alla[k].get("pyd_basis_source"))
print("basis evidence changed with the basis unchanged: %d; %s" % (
    len(evidence), dict(Counter((allb[k].get("pyd_basis_source"), alla[k].get("pyd_basis_source")) for k in evidence))))
probe = {r["stem"].replace("syndicate_", ""): r for r in load(PROBE)}
predicted = {k for k, r in probe.items() if r["basis_before"][0] == r["basis_after"][0]
             and r["basis_before"][1] != r["basis_after"][1] and k in allb and k in alla}
if set(evidence) != predicted:
    problems.append("basis-evidence changes differ from the probe by %s" % sorted(set(evidence) ^ predicted))

sampled = {s.replace("syndicate_", "") for s in load(SAMPLE)["primary"]["stems"]}
out = sorted(sampled - set(pa))
print("error-rate sample records outside the rebuilt working sample: %s" % out)
if out:
    problems.append("sampled records left the working sample: %s" % out)
print("\n" + ("AS PREDICTED" if not problems else "NOT AS PREDICTED:\n  " + "\n  ".join(problems)))
sys.exit(1 if problems else 0)
