r"""After refit 3: is the refit's working sample the loader's own prediction on the committed tree, registers applied?

The refit wrote model/exposure_results.json. This reruns load_and_classify, assign_event_groups, build_subsets and
compute_eligibility on the same tree (read-only; the disposition ledger's CSV goes to this scratchpad) and requires:
  * the observations adopted_model.load_sample keeps are exactly the records eligible for capital;
  * each one's opening reserves, prior-year development, percentage and raw severity equal the loader's record
    (relative 1e-6);
  * the refit's register counters (confirmed figures, confirmed openings, take-ons excluded, take-ons added to the
    opening reserves) equal the loader's, and the take-on base counter equals the committed register's entries;
  * every take-on base entry's record is in the working sample.
Any difference is printed and the script exits 1. Run against refit 2's outputs it must fail (the registers changed).

    python check_refit3_population.py
"""
import io
import json
import sys
from pathlib import Path

AN = Path(r"D:/dev/IME-Lloyds-exposure-composition")
SCR = Path(__file__).resolve().parent
sys.path.insert(0, str(AN / "src"))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import run_analysis as ra  # noqa: E402
import adopted_model  # noqa: E402

ra.log = lambda *a, **k: None
REL = 1e-6
COUNTERS = ("confirmed_figures_applied", "confirmed_openings_applied", "takeon_excluded", "takeon_base_applied")


def close(a, b):
    if a is None or b is None:
        return a is None and b is None
    return abs(a - b) <= REL * max(1.0, abs(a), abs(b))


records, counters, clog, files = ra.load_and_classify()
ra.assign_event_groups(records, min_events=3)
_meta, subsets = ra.build_subsets(records)
ra.compute_eligibility(records, subsets)
ra.build_disposition_ledger(clog, records, str(SCR / "check-refit3-ledger.csv"))
predicted = {"%s_%s" % (r["syndicate"], r["year"]): r for r in records if r.get("eligible_for_capital")}

res = json.load(io.open(str(AN / "model" / "exposure_results.json"), encoding="utf-8"))
obs = {"%s_%s" % (o["syndicate"], o["year"]): o for o in res["observations"]}
S, R, H, yr, syn, ritc = adopted_model.load_sample()
kept = {"%s_%s" % (s, y) for s, y in zip(syn, yr)}
problems = []
if kept != set(predicted):
    problems.append("working sample: the refit keeps %d, the loader predicts %d; only in the refit %s; only predicted %s"
                    % (len(kept), len(predicted), sorted(kept - set(predicted)), sorted(set(predicted) - kept)))
for k in sorted(kept & set(predicted)):
    o, r = obs[k], predicted[k]
    for field in ("opening_reserves_gbp_m", "pyd_gbp_m", "pyd_pct", "s_raw_a"):
        if not close(o.get(field), r.get(field)):
            problems.append("%s %s: refit %s, loader %s" % (k, field, o.get(field), r.get(field)))
meta = res.get("meta") or {}
for c in COUNTERS:
    if meta.get(c) != counters.get(c):
        problems.append("counter %s: refit %s, loader %s" % (c, meta.get(c), counters.get(c)))
register = json.load(io.open(str(AN / "data" / "opening_reserves_takeon_base.json"), encoding="utf-8"))
entries = sorted(k for k in register if not k.startswith("_"))
if counters.get("takeon_base_applied") != len(entries):
    problems.append("the loader applied %s take-on base entries; the register holds %d" % (counters.get("takeon_base_applied"), len(entries)))
for k in entries:
    if k not in kept:
        problems.append("take-on base %s is not in the refit's working sample" % k)

print("refit run %s; working sample %d; loader %d; counters %s"
      % (res.get("analysis_run_id"), len(kept), len(predicted), {c: counters.get(c) for c in COUNTERS}))
for p in problems[:60]:
    print("  DIFFERENCE " + p)
if len(problems) > 60:
    print("  ... and %d more" % (len(problems) - 60))
print("differences: %d" % len(problems))
sys.exit(1 if problems else 0)
