r"""Draw the error-rate study's primary sample from the rebuilt working sample (protocol step 3, as amended).

`error-rate-protocol.md` was fixed on 11 September 2026 and amended on 13 September before any
draw. This does step 3 for the primary sample and nothing else. The first draw script,
`draw_error_rate_sample.py`, was never run: it rebuilt eligibility from the extraction records
without the loader's gross-basis rule, so its population was not the working sample the
protocol names. This one reads the population from the working sample itself.

  population  the observations of model/exposure_results.json that adopted_model.load_sample
              retains, as stems, sorted; the file's run identifier and SHA-256 are recorded
  primary     n = 60, simple random without replacement, numpy default_rng(42)
  tail        not drawn here: computed after the refit (amendment, point 3)

It refuses to run if the sample file exists: the protocol says the sample is not redrawn.
"""
import hashlib
import io
import json
import sys
from pathlib import Path

import numpy as np

AN = Path(r"D:/dev/IME-Lloyds-exposure-composition")
OUT = Path(__file__).resolve().parent
SAMPLE = OUT / "error-rate-sample.json"
sys.path.insert(0, str(AN / "src"))
import adopted_model  # noqa: E402

N_PRIMARY = 60
SEED = 42

if SAMPLE.exists():
    raise SystemExit("%s already exists; the protocol says it is not redrawn" % SAMPLE.name)

results = AN / "model" / "exposure_results.json"
digest = hashlib.sha256(results.read_bytes()).hexdigest()
run_id = json.load(io.open(str(results), encoding="utf-8")).get("analysis_run_id")
if not run_id:
    raise SystemExit("exposure_results.json carries no analysis_run_id; not drawing")
S, R, H, yr, syn, ritc = adopted_model.load_sample()
stems = sorted("syndicate_%s_%s" % (s, y) for s, y in zip(syn, yr))
if len(set(stems)) != len(stems):
    raise SystemExit("the working sample holds a syndicate-year twice; not drawing")
n = len(stems)
rng = np.random.default_rng(SEED)
idx = rng.choice(n, size=N_PRIMARY, replace=False)
primary = [stems[int(i)] for i in sorted(idx)]

payload = {
    "protocol": "error-rate-protocol.md, fixed 11 September 2026 and amended 13 September 2026 before this draw",
    "drawn": "2026-09-13",
    "seed": SEED,
    "population": {
        "description": ("the working sample: the observations of model/exposure_results.json that "
                        "adopted_model.load_sample retains, as syndicate-year stems sorted "
                        "lexicographically before the draw"),
        "n": n,
        "exposure_results_run_id": run_id,
        "exposure_results_sha256": digest,
    },
    "primary": {
        "kind": "simple random sample without replacement",
        "n": len(primary),
        "stems": primary,
        "note": "the rate is computed from this sample and this sample only",
    },
    "tail": {
        "kind": "purposive: the 20 largest transferred severities",
        "status": "computed after the refit, before any tail record is adjudicated (amendment, point 3)",
    },
}
io.open(str(SAMPLE), "w", encoding="utf-8", newline="").write(json.dumps(payload, indent=1) + "\n")
print("population: %d stems from exposure_results.json run %s (sha256 %s...)" % (n, run_id, digest[:12]))
print("primary sample: %d stems, seed %d" % (len(primary), SEED))
print("written to %s -- not redrawn" % SAMPLE.name)
