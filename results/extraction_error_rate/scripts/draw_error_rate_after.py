r"""Draw the error-rate study's new primary sample after R209 and R210 (protocol, fourth amendment, point 2).

R209 and R210 changed the working sample after the first result was scored: nine records left and one
entered (2121/2017). The third amendment's rule for an entering record re-runs the study from step 1.
So this draws a new primary sample by the first draw's method (draw_error_rate_primary.py): the
observations adopted_model.load_sample retains, as stems sorted lexicographically, n = 60,
numpy default_rng(42). It writes error-rate-sample-after.json, and leaves error-rate-sample.json, the
first sample, as it is.

It refuses to run if the fourth amendment is not yet in the protocol, if the working sample is not the
rebuild the amendment names, or if the new sample file exists. It reads no verdict: the overlap with
the first sample is listed by stem only.

    python draw_error_rate_after.py
"""
import hashlib
import io
import json
import sys
from pathlib import Path

import numpy as np

AN = Path(r"D:/dev/IME-Lloyds-exposure-composition")
OUT = Path(__file__).resolve().parent
FIRST = OUT / "error-rate-sample.json"
SAMPLE = OUT / "error-rate-sample-after.json"
PROTOCOL = OUT / "error-rate-protocol.md"
RUN_ID = "59da1151-3c18-5781-b5e0-bd47eb2cd2d3"
N_WORKING = 698
sys.path.insert(0, str(AN / "src"))
import adopted_model  # noqa: E402

N_PRIMARY = 60
SEED = 42

if SAMPLE.exists():
    raise SystemExit("%s already exists; the protocol says a sample is not redrawn" % SAMPLE.name)
if "## Fourth amendment" not in io.open(str(PROTOCOL), encoding="utf-8").read():
    raise SystemExit("the fourth amendment is not in the protocol yet; not drawing")
results = AN / "model" / "exposure_results.json"
digest = hashlib.sha256(results.read_bytes()).hexdigest()
run_id = json.load(io.open(str(results), encoding="utf-8")).get("analysis_run_id")
if run_id != RUN_ID:
    raise SystemExit("exposure_results.json is run %s, not the rebuild the amendment names (%s); not drawing"
                     % (run_id, RUN_ID))
S, R, H, yr, syn, ritc = adopted_model.load_sample()
stems = sorted("syndicate_%s_%s" % (s, y) for s, y in zip(syn, yr))
if len(set(stems)) != len(stems):
    raise SystemExit("the working sample holds a syndicate-year twice; not drawing")
n = len(stems)
if n != N_WORKING:
    raise SystemExit("the working sample holds %d records, not the %d the amendment names; not drawing" % (n, N_WORKING))
rng = np.random.default_rng(SEED)
idx = rng.choice(n, size=N_PRIMARY, replace=False)
primary = [stems[int(i)] for i in sorted(idx)]
first = json.load(io.open(str(FIRST), encoding="utf-8"))["primary"]["stems"]
both = sorted(set(primary) & set(first))

payload = {
    "protocol": "error-rate-protocol.md, fourth amendment (13 September 2026), written before this draw",
    "drawn": "2026-09-13",
    "seed": SEED,
    "first_sample": "%s is kept: the rate before R209 and R210 is computed from it" % FIRST.name,
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
        "note": "the rate after R209 and R210 is computed from this sample and this sample only",
    },
    "also_in_the_first_sample": both,
    "tail": {
        "kind": "purposive: the 20 largest transferred severities",
        "status": "computed after the refit, before any tail record is adjudicated (amendment, point 3)",
    },
}
io.open(str(SAMPLE), "w", encoding="utf-8", newline="").write(json.dumps(payload, indent=1) + "\n")
print("population: %d stems from exposure_results.json run %s (sha256 %s...)" % (n, run_id, digest[:12]))
print("primary sample: %d stems, seed %d; also in the first sample: %d" % (len(primary), SEED, len(both)))
print("written to %s -- not redrawn" % SAMPLE.name)
