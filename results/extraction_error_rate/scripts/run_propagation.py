r"""Run error_rate_propagation.py on refit 3 with every input read from the study's files, none typed: the rate's errors
and adjudicable records from the third result's sampled records (A), the read records from error-rate-read-stems.json,
the errors confirmed before repair, the take-on base census's result, and refit 1's results as the refit before the
repairs. Refuses if an input is missing or the output exists.

    python run_propagation.py
"""
import io
import json
import subprocess
import sys
from pathlib import Path

SCR = Path(__file__).resolve().parent
OUT = SCR / "error-rate-propagation.json"
BEFORE = SCR / "refit1-db8eba4-outputs" / "results" / "vignette_uncertainty_results.json"
INPUTS = [SCR / "error-rate-result-third.json", SCR / "error-rate-read-stems.json", SCR / "error-rate-confirmed-errors.json",
          SCR / "error-rate-census-ninth-result.json", BEFORE]

missing = [p.name for p in INPUTS if not p.exists()]
if missing:
    raise SystemExit("missing inputs: %s" % missing)
if OUT.exists():
    raise SystemExit("%s exists: the propagation is not run twice" % OUT.name)
a = json.load(io.open(str(SCR / "error-rate-result-third.json"), encoding="utf-8"))["A_sampled"]
argv = [sys.executable, str(SCR / "error_rate_propagation.py"), "--rate-errors", str(a["errors"]),
        "--rate-adjudicable", str(a["adjudicable_n"]), "--read-samples", str(SCR / "error-rate-read-stems.json"),
        "--confirmed-errors", str(SCR / "error-rate-confirmed-errors.json"),
        "--takeon-base-result", str(SCR / "error-rate-census-ninth-result.json"),
        "--before-results", str(BEFORE), "--out", str(OUT)]
print("running: %s" % " ".join(argv[1:]))
sys.exit(subprocess.run(argv).returncode)
