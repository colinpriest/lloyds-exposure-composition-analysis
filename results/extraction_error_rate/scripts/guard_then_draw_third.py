r"""Check that refit 2's loader output is the repaired run, then take the third draw (it is drawn once).

The draw (draw_error_rate_third.py) reads model/exposure_results.json. Before it runs, this checks that the file
parses, that its run is not refit 1's (the population file's run), that the loader applied the two confirmed figures
and excluded the one take-on, that its disposition flow's working sample is 697 as the loader predicted, and that
adopted_model.load_sample() retains the same 697. Any failed check stops before the draw.

    python guard_then_draw_third.py
"""
import io
import json
import subprocess
import sys
from pathlib import Path

SCR = Path(__file__).resolve().parent
AN = Path(r"D:/dev/IME-Lloyds-exposure-composition")
sys.path.insert(0, str(AN / "src"))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

pop = json.load(io.open(str(SCR / "error-rate-population-698.json"), encoding="utf-8"))
cur = json.load(io.open(str(AN / "model" / "exposure_results.json"), encoding="utf-8"))
meta = cur.get("meta") or {}
flow = cur.get("disposition_flow") or meta.get("disposition_flow") or {}
import adopted_model  # noqa: E402

S, R, H, yr, syn, ritc = adopted_model.load_sample()
checks = [
    ("the run is not refit 1's (%s)" % pop["exposure_results_run_id"],
     cur.get("analysis_run_id") not in (None, pop["exposure_results_run_id"])),
    ("confirmed figures applied = 2", meta.get("confirmed_figures_applied") == 2),
    ("take-ons excluded = 1", meta.get("takeon_excluded") == 1),
    ("disposition flow working sample = 697", flow.get("working_sample") == 697),
    ("take-on step = 1", (flow.get("to_working_sample") or {}).get("takeon_not_development") == 1),
    ("adopted_model.load_sample retains 697", len(syn) == 697),
]
for name, ok in checks:
    print("%-60s %s" % (name, "ok" if ok else "FAILED"))
print("run id %s; flow keys %s" % (cur.get("analysis_run_id"), sorted(flow)[:8]))
if not all(ok for _, ok in checks):
    raise SystemExit("a check failed: the third sample is not drawn")
r = subprocess.run([sys.executable, str(SCR / "draw_error_rate_third.py")], capture_output=True, text=True, cwd=str(SCR))
print(r.stdout.strip())
if r.returncode:
    print(r.stderr.strip()[-2000:])
    raise SystemExit("the draw exited %d" % r.returncode)
