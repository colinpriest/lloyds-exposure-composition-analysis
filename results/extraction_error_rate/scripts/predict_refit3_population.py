r"""Predict refit 3's working sample from the loader alone, before the manifest run (read-only).

Runs the analysis repository's load_and_classify, assign_event_groups, build_subsets, compute_eligibility and
build_disposition_ledger (its CSV goes to this scratchpad) on the committed registers, as main() does. Prints the flow,
the register counters, the records that leave or enter the working sample against refit 2's (the 697 records the third
sample and the eighth census were drawn from), and the figure, percentage, opening reserves, basis, tag and eligibility
of every record the eighth amendment's repairs touch (and any record named on the command line).

    python predict_refit3_population.py [syndicate_1234_2020 ...]
"""
import io
import json
import sys
from pathlib import Path

SCR = Path(__file__).resolve().parent
ANA = Path(r"D:/dev/IME-Lloyds-exposure-composition")
sys.path.insert(0, str(ANA / "src"))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import run_analysis as ra  # noqa: E402

ra.log = lambda *a, **k: None
TOUCHED = ["382_2015", "382_2016", "382_2018", "382_2019", "2010_2018", "3010_2019", "1880_2014", "623_2014",
           "1274_2018", "1980_2018", "2003_2018"] + [s.replace("syndicate_", "") for s in sys.argv[1:]]


def refit2_working_sample():
    third = json.load(io.open(str(SCR / "error-rate-sample-third.json"), encoding="utf-8"))
    pop = json.load(io.open(str(SCR / "error-rate-population-698.json"), encoding="utf-8"))["stems"]
    ws = set(pop) - set(third["left"]["stems"]) | set(third["E_entrants"]["stems"])
    if len(ws) != third["rebuilt_working_sample_n"]:
        raise SystemExit("refit 2's working sample rebuilds to %d, not %d" % (len(ws), third["rebuilt_working_sample_n"]))
    return ws


records, counters, clog, files = ra.load_and_classify()
ra.assign_event_groups(records, min_events=3)
_meta, subsets = ra.build_subsets(records)
ra.compute_eligibility(records, subsets)
flow = ra.build_disposition_ledger(clog, records, str(SCR / "predict-refit3-ledger.csv"))
ws = {"syndicate_%s_%s" % (r["syndicate"], r["year"]) for r in records if r.get("eligible_for_capital")}
before = refit2_working_sample()
print("files %d; corpus %d; working sample %d (eligible for capital %d; equal: %s)"
      % (counters["total_files"], flow["corpus"], flow["working_sample"], len(ws),
         flow.get("working_sample_equals_eligible_for_capital")))
print("to_working_sample: %s" % json.dumps(flow["to_working_sample"]))
print("confirmed figures applied %d; confirmed openings applied %d; take-ons excluded %d; net %d; unknown basis %d"
      % (counters["confirmed_figures_applied"], counters["confirmed_openings_applied"], counters["takeon_excluded"],
         counters["net_basis_excluded"], counters["unknown_basis_excluded"]))
print("left the working sample (against refit 2's 697): %s" % sorted(before - ws))
print("entered the working sample: %s" % sorted(ws - before))
by = {"%s_%s" % (r["syndicate"], r["year"]): r for r in records}
for k in TOUCHED:
    r = by.get(k)
    if r is None:
        print("  %-10s not a parsed record" % k)
        continue
    print("  %-10s pyd_gbp_m %-10s pct %-8s opening %-10s basis %s (%s) tag %s eligible %s"
          % (k, None if r.get("pyd_gbp_m") is None else round(r["pyd_gbp_m"], 3),
             None if r.get("pyd_pct") is None else round(r["pyd_pct"], 3),
             None if r.get("opening_reserves_gbp_m") is None else round(r["opening_reserves_gbp_m"], 3),
             r.get("pyd_basis"), r.get("pyd_basis_source"), r.get("data_quality_tag"), r.get("eligible_for_capital")))
