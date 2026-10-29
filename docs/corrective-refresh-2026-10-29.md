# Corrective metadata refresh, 29 October 2026

The underlying frozen analysis is commit `fb2f0c28b409038465f3efcd0728eebfb5b0d9f6`. This revision corrects descriptions of the source-reading frame, cohort classification, active-syndicate lists and temporal-dependence diagnostics; it does not change the associated statistical calculations.

`check_pyd_temporal_correlation.py` and `error_rate_propagation.py` were executed in an isolated checkout of that commit with the corrective source changes present. Recursive comparisons with the frozen outputs found no changed numeric values. The latter records the checkout's underlying commit and dirty status; its run was not a clean full reproduction of this revision.

`check_cohort_scope.py --refresh-notes` updated only the three explanatory text fields of the existing cohort-sensitivity result. The previous fitted results were retained, not refitted. Focused tests cover that preservation and the corrected source descriptions. The earlier full-run report continues to describe its original run, not a full rerun of this revision.
