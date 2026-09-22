r"""Refit 3's Vignette 1 VaR99.5 read with the inverse CDF, the before-fit for the tenth amendment's propagation.

The tenth amendment's repairs and the change of quantile rule (frozen review of 21 September 2026, M04: every pool
VaR is now the inverse CDF of the pool, src/pool_quantile.py) land in the same refit. So that the propagation's
comparison of the fits before and after the repairs does not mix the two, the before-fit's VaR is read here with the
rule the after-fit uses. Everything is read from the analysis commit of refit 3 (the frozen review's HEAD): the
donor pool embedded in distortion_tool.html, the posterior draws, the targets, and the regime as that commit's
RITC scan and transfer register gave it. The script refuses unless the old rule (numpy type 7) on those inputs
reproduces the centre that commit's results/vignette_uncertainty_results.json records.

    python results/extraction_error_rate/scripts/propagation_before_inverse_cdf.py [--commit f65f14e]
"""
import argparse
import io
import json
import re
import subprocess
import sys
from pathlib import Path

import numpy as np

AN = Path(__file__).resolve().parents[3]
OUT = AN / "results" / "extraction_error_rate" / "propagation" / "before-refit3-inverse-cdf.json"

ap = argparse.ArgumentParser()
ap.add_argument("--commit", default="f65f14e")
args = ap.parse_args()
sys.argv = [sys.argv[0]]
sys.path.insert(0, str(AN / "src"))
import pool_quantile  # noqa: E402
import vignette_uncertainty as vu  # noqa: E402


def show(rel, binary=False):
    r = subprocess.run(["git", "-C", str(AN), "show", "%s:%s" % (args.commit, rel)], capture_output=True)
    if r.returncode:
        raise SystemExit("git show %s:%s failed" % (args.commit, rel))
    return r.stdout if binary else r.stdout.decode("utf-8")


html = show("distortion_tool.html")
donors = json.loads(re.search(r"const EMBEDDED_DATA = (\{.*?\});\s*\n", html, re.S).group(1))["donors"]
S = np.array([d["s_raw_a"] for d in donors], float)
R = np.array([d["opening_reserves_gbp_m"] for d in donors], float)
H = np.array([d["hhi"] for d in donors], float)
synd = np.array([d["syndicate"] for d in donors])
year = np.array([d["year"] for d in donors])

z = np.load(io.BytesIO(show("model/dispersion_posterior_draws_ritc.npz", binary=True)))
draws = {k: z[k] for k in ("k", "gamma", "sd_undiv", "sd_div", "nu_clean", "nu_ritc")}
cfg = (float(z["reference_size"][0]), float(z["hhi_floor"][0]), float(z["hhi_ceil"][0]))

scan = json.loads(show("pdf_extraction/ritc_scan.json"))
reg = json.loads(show("pdf_extraction/audit/portfolio_transfer_adjudication.json"))
regime = {k for k, v in scan.items() if isinstance(v, dict) and v.get("ritc_occurred")}
regime |= {r["stem"] for r in reg["records"] + reg.get("found_by_hand", [])
           if r.get("verdict") == "genuine" and r.get("direction") in ("inward", "both")}
ritc = np.array(["%s_%s" % (s, y) in regime for s, y in zip(synd, year)], bool)

t1 = json.loads(show("vignettes/vignette-1/target_profile.json"))
v1 = (float(t1["reserve_size"]), float(t1["hhi"]))
thbar = {p: float(draws[p].mean()) for p in draws}
pool = vu.transfer(S, R, H, v1, thbar, cfg, ritc)

type7 = float(np.percentile(pool, 99.5, method="linear"))
committed = json.loads(show("results/vignette_uncertainty_results.json"))
want = committed["centres_full_pool_posterior_mean"]["V1_adj"]["v995"]
if abs(type7 - want) > 1e-12:
    raise SystemExit("type 7 on the commit's inputs gives %.15f, not the committed centre %.15f" % (type7, want))
inv = pool_quantile.var_q(pool, 0.995)
out = {"_about": ("refit 3's Vignette 1 VaR99.5 at the posterior-mean parameters, read with the inverse CDF "
                  "(src/pool_quantile.py); every input from analysis commit %s, where numpy type 7 reproduces the "
                  "committed centre %.6f (results/extraction_error_rate/scripts/propagation_before_inverse_cdf.py)"
                  % (args.commit, want)),
       "commit": args.commit, "n_donors": int(len(S)), "n_ritc": int(ritc.sum()),
       "type7_v995": type7, "rule": pool_quantile.RULE,
       "centres_full_pool_posterior_mean": {"V1_adj": {"v995": inv}}}
OUT.parent.mkdir(parents=True, exist_ok=True)
io.open(str(OUT), "w", encoding="utf-8", newline="\n").write(json.dumps(out, indent=1) + "\n")
print("refit 3 (%s): type 7 %.6f = committed; inverse CDF %.6f; %d donors, %d in the regime"
      % (args.commit, type7, inv, len(S), ritc.sum()))
