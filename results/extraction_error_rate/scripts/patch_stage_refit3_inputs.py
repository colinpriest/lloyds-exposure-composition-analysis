r"""stage_extraction_error_rate.py: refit 3's checks and the propagation's inputs.

  * checks/: the loader's predictions for A4c and A4d, the refit 3 population check's dry run on refit 2's outputs,
    and its run on refit 3 (check-refit3.txt);
  * propagation/: the read records the propagation counts (error-rate-read-stems.json);
  * scripts/: check_refit3_population.py, build_read_stems.py, run_propagation.py, first_draw_errors_now.py,
    basis_net_in_a.py, inspect_results.py and this patch.

Each replacement must match exactly once, or nothing is written.

    python patch_stage_refit3_inputs.py
"""
import io
from pathlib import Path

SCR = Path(__file__).resolve().parent
TARGET = SCR / "stage_extraction_error_rate.py"
REPLACEMENTS = [
    ('FILES["checks"] += ["predict-refit3-a4b.txt", "mutate-takeon-base.txt"]',
     'FILES["checks"] += ["predict-refit3-a4b.txt", "mutate-takeon-base.txt"]\n'
     '# refit 3: the loader\'s predictions after A4c and A4d, and the population check (its dry run on refit 2 must fail)\n'
     'FILES["checks"] += ["predict-refit3-a4c.txt", "predict-refit3-a4d.txt", "check-refit3-dryrun-on-refit2.txt",\n'
     '                    "check-refit3.txt"]\n'
     'FILES["propagation"] += ["error-rate-read-stems.json"]\n'
     'FILES["scripts"] += ["check_refit3_population.py", "build_read_stems.py", "run_propagation.py",\n'
     '                     "first_draw_errors_now.py", "basis_net_in_a.py", "inspect_results.py",\n'
     '                     "patch_stage_refit3_inputs.py"]'),
]

raw = io.open(str(TARGET), encoding="utf-8", newline="").read()
crlf = "\r\n" in raw
text = raw.replace("\r\n", "\n")
if "check-refit3.txt" in text:
    raise SystemExit("the staging script already stages refit 3's checks")
for old, new in REPLACEMENTS:
    n = text.count(old)
    if n != 1:
        raise SystemExit("expected once, found %d: %r" % (n, old[:90]))
    text = text.replace(old, new)
compile(text, TARGET.name, "exec")
io.open(str(TARGET), "w", encoding="utf-8", newline="").write(text.replace("\n", "\r\n") if crlf else text)
print("patched %d site(s) in %s" % (len(REPLACEMENTS), TARGET.name))
