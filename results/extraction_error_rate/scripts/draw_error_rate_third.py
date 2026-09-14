r"""The third random sample (error-rate-protocol.md, fifth amendment, point 3), drawn after the repairs from the
rebuilt working sample and written before any of its records is read.

A is the rebuilt working sample's records that the second sample's population also holds
(error-rate-population-698.json); E is its other records, the entrants, which are read in full. 110 records are
drawn from A without the second sample's 60, by the earlier draws' method: the stems adopted_model.load_sample
retains, sorted lexicographically, numpy.random.default_rng(20260914), choice without replacement. Refuses while
exposure_results.json is still the run before the repairs, and refuses to overwrite.

    python draw_error_rate_third.py
"""
import datetime
import io
import json
import sys
from pathlib import Path

import numpy as np

AN = Path(r"D:/dev/IME-Lloyds-exposure-composition")
SCR = Path(__file__).resolve().parent
sys.path.insert(0, str(AN / "src"))
import adopted_model  # noqa: E402

SEED = 20260914
N = 110
OUT = SCR / "error-rate-sample-third.json"
if OUT.exists():
    raise SystemExit("%s exists; the third sample is drawn once" % OUT.name)
pop = json.load(io.open(str(SCR / "error-rate-population-698.json"), encoding="utf-8"))
after = json.load(io.open(str(SCR / "error-rate-sample-after.json"), encoding="utf-8"))
cur = json.load(io.open(str(AN / "model" / "exposure_results.json"), encoding="utf-8"))
if cur.get("analysis_run_id") == pop["exposure_results_run_id"]:
    raise SystemExit("exposure_results.json is still run %s, before the repairs: rebuild the working sample first"
                     % pop["exposure_results_run_id"])
S, R, H, yr, syn, ritc = adopted_model.load_sample()
rebuilt = sorted("syndicate_%s_%s" % (s, y) for s, y in zip(syn, yr))
pop_stems = set(pop["stems"])
second = set(after["primary"]["stems"])
A = [s for s in rebuilt if s in pop_stems]
E = [s for s in rebuilt if s not in pop_stems]
left = sorted(pop_stems - set(rebuilt))
frame = [s for s in A if s not in second]
idx = np.random.default_rng(SEED).choice(len(frame), size=N, replace=False)
third = [frame[int(i)] for i in sorted(idx)]
io.open(str(OUT), "w", encoding="utf-8", newline="").write(json.dumps({
    "protocol": "error-rate-protocol.md, fifth amendment (13 September 2026), point 3, written before this draw",
    "drawn": datetime.datetime.now().isoformat(timespec="seconds"),
    "seed": SEED,
    "exposure_results_run_id": cur.get("analysis_run_id"),
    "rebuilt_working_sample_n": len(rebuilt),
    "A": {"description": "rebuilt working-sample records the second sample's population also holds", "n": len(A)},
    "E_entrants": {"description": "rebuilt working-sample records the second sample's population did not hold; "
                                  "each is read (a census stratum)", "stems": E},
    "left": {"description": "second-sample population records no longer in the working sample", "stems": left},
    "second_sample_still_in_A": sorted(second & set(A)),
    "frame": {"description": "A without the second sample's 60, sorted lexicographically", "n": len(frame)},
    "third": {"kind": "simple random sample of the frame", "n": N, "stems": third},
}, indent=1) + "\n")
print("rebuilt %d; A %d; entrants %d %s; left %d %s; frame %d; drawn %d -> %s"
      % (len(rebuilt), len(A), len(E), E, len(left), left, len(frame), N, OUT.name))
