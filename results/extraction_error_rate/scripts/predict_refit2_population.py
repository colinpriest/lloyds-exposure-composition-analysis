r"""Predict refit 2's working sample from the loader alone, before the manifest run (read-only).

Imports the analysis repository's run_analysis.py with its log silenced and runs load_and_classify,
assign_event_groups, build_subsets, compute_eligibility and build_disposition_ledger (its CSV goes to this
scratchpad), as main() does. Prints the flow, the register counters, the working sample's size, the records that
leave or enter it against refit 1's population (error-rate-population-698.json), and the adopted figure, basis,
cohort scope and eligibility of every record the round-56 repairs and readings touch.

    python predict_refit2_population.py
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
TOUCHED = ["3624_2015", "1225_2022", "2010_2019", "4444_2022", "2008_2019", "2008_2021", "623_2014", "623_2022",
           "1206_2014", "2007_2015"]


def population():
    d = json.load(io.open(str(SCR / "error-rate-population-698.json"), encoding="utf-8"))
    if isinstance(d, dict):
        for key in ("stems", "population", "working_sample", "records", "rows"):
            if key in d:
                d = d[key]
                break
    stems = set(d) if isinstance(d, dict) else {r if isinstance(r, str) else r["stem"] for r in d}
    if len(stems) != 698:
        raise SystemExit("the population file gives %d stems, not 698" % len(stems))
    return stems


records, counters, clog, files = ra.load_and_classify()
ra.assign_event_groups(records, min_events=3)
_meta, subsets = ra.build_subsets(records)
ra.compute_eligibility(records, subsets)
flow = ra.build_disposition_ledger(clog, records, str(SCR / "predict-refit2-ledger.csv"))
ws = {"syndicate_%s_%s" % (r["syndicate"], r["year"]) for r in records if r.get("eligible_for_capital")}
before = population()
print("files %d; corpus %d; working sample %d (eligible for capital %d; equal: %s)"
      % (counters["total_files"], flow["corpus"], flow["working_sample"], len(ws),
         flow.get("working_sample_equals_eligible_for_capital")))
print("to_working_sample: %s" % json.dumps(flow["to_working_sample"]))
print("confirmed figures applied %d; take-ons excluded %d" % (counters["confirmed_figures_applied"],
                                                              counters["takeon_excluded"]))
print("left the working sample: %s" % sorted(before - ws))
print("entered the working sample: %s" % sorted(ws - before))
by = {"%s_%s" % (r["syndicate"], r["year"]): r for r in records}
for k in TOUCHED:
    r = by.get(k)
    if r is None:
        print("  %-10s not a parsed record" % k)
        continue
    print("  %-10s pyd_gbp_m %-10s pct %-8s basis %s (%s) cohort %s tag %s eligible %s"
          % (k, r.get("pyd_gbp_m"), None if r.get("pyd_pct") is None else round(r["pyd_pct"], 3), r.get("pyd_basis"),
             r.get("pyd_basis_source"), r.get("pyd_cohort_scope"), r.get("data_quality_tag"),
             r.get("eligible_for_capital")))
