r"""After the refit: is the refit's working sample the population the error-rate study's second sample was drawn from?

The second sample (error-rate-sample-after.json) was drawn from analysis run 59da1151, whose exposure_results.json
the refit has since overwritten; no copy was kept. So the check is behavioural: the refit's working sample is
redrawn exactly as draw_error_rate_after.py drew it (the stems adopted_model.load_sample retains, sorted
lexicographically, n = 60, numpy default_rng(42)), and the 60 stems must be the committed draw's. A population
that differs in any stem, or in size, almost surely redraws differently. compare_r209_r210.py, rerun against the
refit's file, then checks the severities, opening reserves and HHI.

Read-only.

    python check_refit_population.py
"""
import io
import json
import sys
from pathlib import Path

import numpy as np

AN = Path(r"D:/dev/IME-Lloyds-exposure-composition")
SCR = Path(__file__).resolve().parent
sys.path.insert(0, str(AN / "src"))
import adopted_model  # noqa: E402

sample = json.load(io.open(str(SCR / "error-rate-sample-after.json"), encoding="utf-8"))
res = json.load(io.open(str(AN / "model" / "exposure_results.json"), encoding="utf-8"))
S, R, H, yr, syn, ritc = adopted_model.load_sample()
stems = sorted("syndicate_%s_%s" % (s, y) for s, y in zip(syn, yr))
n = len(stems)
rng = np.random.default_rng(sample["seed"])
redrawn = [stems[int(i)] for i in sorted(rng.choice(n, size=sample["primary"]["n"], replace=False))]
same_n = n == sample["population"]["n"]
same_draw = redrawn == sample["primary"]["stems"]
print("refit exposure_results run %s; the draw's population run %s"
      % (res.get("analysis_run_id"), sample["population"]["exposure_results_run_id"]))
print("working sample: %d records (the draw's population: %d) -> %s" % (n, sample["population"]["n"], "same" if same_n else "DIFFERENT"))
print("redrawn 60 stems equal the committed draw: %s" % same_draw)
if not same_draw:
    print("  only in the redraw: %s" % sorted(set(redrawn) - set(sample["primary"]["stems"])))
    print("  only in the draw:   %s" % sorted(set(sample["primary"]["stems"]) - set(redrawn)))
sys.exit(0 if (same_n and same_draw) else 1)
