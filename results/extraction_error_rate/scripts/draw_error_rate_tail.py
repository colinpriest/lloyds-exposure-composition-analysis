r"""Compute the error-rate study's tail stratum after the refit (protocol amendment, point 3).

The tail is the 20 largest transferred severities: every donor in the pool transferred to
Vignette 1's target, exactly as src/donor_review.py ranks its top adverse transferred donors --
the de-RITC transfer under the headline calibration's posterior means -- sorted from the most
adverse. It is purposive, so it is never pooled with the primary sample.

It depends on the refit, so it refuses to run without --after-refit, records the hashes of the
calibration and the donor pool it used, and never overwrites its output. A stem that is also in
the primary sample is adjudicated once and counted in both strata, which are reported separately.

    python draw_error_rate_tail.py --after-refit
"""
import hashlib
import io
import json
import sys
from pathlib import Path

import numpy as np

AN = Path(r"D:/dev/IME-Lloyds-exposure-composition")
OUT = Path(__file__).resolve().parent
TAIL = OUT / "error-rate-tail.json"
N_TAIL = 20
sys.path.insert(0, str(AN / "src"))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

if "--after-refit" not in sys.argv:
    raise SystemExit("the tail depends on the refitted operator; run with --after-refit once the manifest has run")
if TAIL.exists():
    raise SystemExit("%s already exists; not recomputed" % TAIL.name)

import donor_review as dr  # noqa: E402
from dispersion_mle import sigma, deritc_z  # noqa: E402
from vignette_uncertainty import load_pool, load_ritc  # noqa: E402

cal_path = AN / "model" / "dispersion_calibration_ritc.json"
pool_path = AN / "distortion_tool.html"
cal = json.load(io.open(str(cal_path), encoding="utf-8"))
mp = {k: cal[k] for k in ("k", "gamma", "sd_undiv", "sd_div", "nu_clean", "nu_ritc")}
S, R, H, synd, year = load_pool()
ritc = load_ritc(synd, year)
V1 = dr.V1
sig_i = sigma(R, H, mp["k"], mp["gamma"], mp["sd_undiv"], mp["sd_div"])
sig_q = sigma(V1[0], V1[1], mp["k"], mp["gamma"], mp["sd_undiv"], mp["sd_div"])
z = deritc_z(S / sig_i, ritc.astype(float), mp["nu_clean"], mp["nu_ritc"])
s_adj = z * sig_q
order = np.argsort(-s_adj)[:N_TAIL]
stems = ["syndicate_%s_%s" % (synd[i], year[i]) for i in order]

primary = json.load(io.open(str(OUT / "error-rate-sample.json"), encoding="utf-8"))["primary"]["stems"]
# the fourth amendment's sample is the one the current extraction is measured on; a tail stem it holds keeps
# that reading when nothing its verdict was read against has changed (fourth amendment, point 3)
primary_after = json.load(io.open(str(OUT / "error-rate-sample-after.json"), encoding="utf-8"))["primary"]["stems"]
results = json.load(io.open(str(AN / "model" / "exposure_results.json"), encoding="utf-8"))
payload = {
    "protocol": "error-rate-protocol.md, amendment point 3: computed after the refit, before any tail record is adjudicated",
    "definition": ("the 20 largest Vignette-1 transferred severities of the donor pool, de-RITC transfer "
                   "under the headline calibration's posterior means, as src/donor_review.py ranks them"),
    "vignette_1_target": list(V1),
    "calibration": {"file": "model/dispersion_calibration_ritc.json",
                    "sha256": hashlib.sha256(cal_path.read_bytes()).hexdigest(),
                    "parameters": mp},
    "donor_pool": {"file": "distortion_tool.html", "n": int(len(S)),
                   "sha256": hashlib.sha256(pool_path.read_bytes()).hexdigest()},
    "exposure_results_run_id": results.get("analysis_run_id"),
    "tail": {"n": len(stems), "stems": stems,
             "transferred_severity": [float(s_adj[i]) for i in order],
             "assumed_business_regime": [bool(ritc[i]) for i in order]},
    "overlap_with_primary": sorted(set(stems) & set(primary)),
    "overlap_with_primary_after": sorted(set(stems) & set(primary_after)),
}
io.open(str(TAIL), "w", encoding="utf-8", newline="").write(json.dumps(payload, indent=1) + "\n")
print("donor pool %d; tail %d; overlap with the first primary sample %d, with the second %d"
      % (len(S), len(stems), len(payload["overlap_with_primary"]), len(payload["overlap_with_primary_after"])))
print("tail: %s" % stems)
