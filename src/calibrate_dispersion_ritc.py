"""Calibrate the dispersion model with an RITC tail-shape regime.

Extends calibrate_dispersion.py: RITC (reinsurance-to-close of another syndicate's
account) markedly FATTENS the tail of the standardised residual (see ritc_tail_shape.py:
Student-t nu roughly halves for RITC years). The scale is modelled as unchanged, which is a
structural simplification and NOT an established fact: beta_ritc below is centred at -0.146
with P(|beta|>0.1)=0.67, so the term is omitted because omitting it costs about 3% of the
vignette stresses, not because it is zero (see check_ritc_scale_term.py).  So we let the
Student-t degrees of freedom depend on RITC status while keeping sigma(R,HHI) shared:

    S_it ~ StudentT( nu_it , 0 , sigma_it )
    nu_clean ~ Gamma(2, 0.1)
    nu_it = nu_clean                       (clean)
          = nu_clean * exp(-lambda_ritc)   (RITC)      lambda_ritc ~ Normal(0, 0.7)
    log sigma_it = ... + beta_ritc * 1[RITC]           beta_ritc ~ Normal(0, 0.5)   <- falsification

lambda_ritc > 0  => RITC tail is heavier (nu_ritc < nu_clean); we report
P(nu_ritc < nu_clean) = P(lambda_ritc > 0).  beta_ritc is the scale term the operator
omits.  Model-agnostic spread tests fail to separate RITC from clean years, but that is a
failure to detect: beta_ritc is centred at -0.146 with P(|beta| > 0.1) = 0.67, so it is
omitted as a simplification, NOT because it is zero (see check_ritc_scale_term.py).

Everything else (k, gamma, undiversifiable floor, year shock, mu=0) is identical to
calibrate_dispersion.py, so k/gamma/floor are directly comparable.

The model itself is built by adopted_model.scale_block(), which is the single
definition of the adopted specification; this script no longer carries its own copy.

Writes dispersion_calibration_ritc.json and dispersion_posterior_draws_ritc.npz.

Usage:  python calibrate_dispersion_ritc.py
"""
import io, json, sys
from pathlib import Path
import numpy as np
import pytensor
pytensor.config.mode = "NUMBA"
import pymc as pm
import arviz as az

from adopted_model import scale_block

SCRIPT_DIR = Path(__file__).resolve().parent.parent
RESULTS = SCRIPT_DIR / "model" / "exposure_results.json"
RITC = SCRIPT_DIR / "pdf_extraction" / "ritc_scan.json"
OUT = SCRIPT_DIR / "model" / "dispersion_calibration_ritc.json"
DRAWS = SCRIPT_DIR / "model" / "dispersion_posterior_draws_ritc.npz"
REFERENCE_SIZE = 500.0
HHI_FLOOR, HHI_CEIL = 0.01, 1.0
SEED = 42


def load_sample():
    d = json.load(io.open(RESULTS, encoding="utf-8"))
    recs = [o for o in d["observations"]
            if o.get("s_raw_a") is not None and o.get("opening_reserves_gbp_m")
            and o.get("hhi") is not None]
    S = np.array([o["s_raw_a"] for o in recs], float)
    R = np.array([o["opening_reserves_gbp_m"] for o in recs], float)
    HHI = np.clip(np.array([o["hhi"] for o in recs], float), HHI_FLOOR, HHI_CEIL)
    yr = np.array([o["year"] for o in recs])
    key = np.array([f"{o['syndicate']}_{o['year']}" for o in recs])
    return S, R, HHI, yr, key


def ritc_flag(key):
    r = json.load(io.open(RITC, encoding="utf-8"))
    occ = {k for k, v in r.items() if v.get("ritc_occurred")}
    return np.array([k in occ for k in key])


def main():
    S, R, HHI, yr, key = load_sample()
    ritc = ritc_flag(key).astype(float)
    years = np.sort(np.unique(yr))
    yidx = np.searchsorted(years, yr)
    n_y, n = len(years), len(S)
    print(f"n={n}  RITC={int(ritc.sum())}  clean={int((1-ritc).sum())}  years={n_y}")

    with pm.Model():
        # The specification lives in adopted_model.scale_block and nowhere else.
        # This script used to carry its own copy of it, which is how a later analysis
        # came to be written against the OLDER single-regime block while calling
        # itself the adopted model. One definition, one place to change.
        b = scale_block(R, HHI, yr, ritc)
        pm.StudentT("S_obs", nu=b["nu_obs"], mu=0.0, sigma=b["sigma"], observed=S)
        idata = pm.sample(1500, tune=1500, chains=4, cores=1, target_accept=0.98,
                          random_seed=SEED, progressbar=False)

    vn = ["k", "gamma", "nu_clean", "nu_ritc", "lambda_ritc", "beta_ritc",
          "tau_s", "sd_undiv", "sd_div", "f"]
    summ = az.summary(idata, var_names=vn, hdi_prob=0.95)

    def row(p):
        r = summ.loc[p]
        return {"mean": float(r["mean"]), "sd": float(r["sd"]),
                "hdi_2.5": float(r["hdi_2.5%"]), "hdi_97.5": float(r["hdi_97.5%"])}

    post = idata.posterior
    def rav(p): return post[p].values.ravel()
    kf, gf = rav("k"), rav("gamma")
    ncl, nri, lam_f, bet = rav("nu_clean"), rav("nu_ritc"), rav("lambda_ritc"), rav("beta_ritc")
    suf, ff = rav("sd_undiv"), rav("f")

    out = {
        "model": "robust_bayesian_pooling_with_floor_and_ritc_tail_regime",
        "spec": ("S ~ StudentT(nu_it,0,sigma); nu_it = nu_clean for clean, "
                 "nu_clean*exp(-lambda_ritc) for RITC; sigma = exp(beta_ritc*1[RITC]) * "
                 "sqrt(sd_undiv^2 + sd_div^2 [(R/500)(1/H)^gamma]^{2(k-1)}) * exp(s_t)"),
        "reference_size": REFERENCE_SIZE, "hhi_floor": HHI_FLOOR, "hhi_ceil": HHI_CEIL,
        "n": int(n), "n_ritc": int(ritc.sum()), "n_years": int(n_y),
        "years": [int(y) for y in years], "seed": SEED,
        # operator point estimates (clean is the default operator tail)
        "k": float(kf.mean()), "gamma": float(gf.mean()),
        "nu_clean": float(ncl.mean()), "nu_ritc": float(nri.mean()),
        "nu": float(ncl.mean()),
        "sd_undiv": float(suf.mean()), "sd_div": float(rav("sd_div").mean()),
        "lambda_ritc": float(lam_f.mean()), "beta_ritc": float(bet.mean()),
        "params": {p: row(p) for p in vn},
        "posterior_prob": {
            "nu_ritc_lt_nu_clean": float((lam_f > 0).mean()),
            "nu_clean_lt_2": float((ncl < 2.0).mean()),
            "nu_ritc_lt_2": float((nri < 2.0).mean()),
            # beta_ritc above: the scale term is omitted as a structural
            # simplification, not shown to be zero -- current-results displays
            # it with exactly that caveat.
            "beta_ritc_gt_0.1_abs": float((np.abs(bet) > 0.1).mean()),
            # (a k_lt_1 key computed at 0.999 was removed: P(k<1) is identically
            # 1 by construction on the bracketed support, and is stated
            # structurally where displayed rather than computed at a proxy
            # threshold)
        },
        "diagnostics": {
            "max_rhat": float(summ["r_hat"].max()),
            "min_ess_bulk": float(summ["ess_bulk"].min()),
            "divergences": int(idata.sample_stats["diverging"].sum()),
        },
    }
    OUT.write_text(json.dumps(out, indent=2), encoding="utf-8")
    np.savez(DRAWS, k=kf, gamma=gf, sd_undiv=suf, sd_div=rav("sd_div"),
             nu_clean=ncl, nu_ritc=nri, lambda_ritc=lam_f, beta_ritc=bet,
             reference_size=np.array([REFERENCE_SIZE]),
             hhi_floor=np.array([HHI_FLOOR]), hhi_ceil=np.array([HHI_CEIL]))
    print(f"Wrote {OUT}\nWrote {DRAWS} ({kf.size} draws)")
    p = out["params"]
    print(f"\n  k        = {p['k']['mean']:.4f} [{p['k']['hdi_2.5']:.3f},{p['k']['hdi_97.5']:.3f}]")
    print(f"  gamma    = {p['gamma']['mean']:.4f} [{p['gamma']['hdi_2.5']:.3f},{p['gamma']['hdi_97.5']:.3f}]")
    print(f"  sd_undiv = {p['sd_undiv']['mean']:.4f} [{p['sd_undiv']['hdi_2.5']:.4f},{p['sd_undiv']['hdi_97.5']:.4f}]")
    print(f"  nu_clean = {p['nu_clean']['mean']:.3f} [{p['nu_clean']['hdi_2.5']:.3f},{p['nu_clean']['hdi_97.5']:.3f}]")
    print(f"  nu_ritc  = {p['nu_ritc']['mean']:.3f} [{p['nu_ritc']['hdi_2.5']:.3f},{p['nu_ritc']['hdi_97.5']:.3f}]")
    print(f"  lambda   = {p['lambda_ritc']['mean']:+.3f} [{p['lambda_ritc']['hdi_2.5']:+.3f},{p['lambda_ritc']['hdi_97.5']:+.3f}]"
          f"   P(nu_ritc<nu_clean)={out['posterior_prob']['nu_ritc_lt_nu_clean']:.3f}")
    print(f"  beta_ritc= {p['beta_ritc']['mean']:+.3f} [{p['beta_ritc']['hdi_2.5']:+.3f},{p['beta_ritc']['hdi_97.5']:+.3f}]"
          f"   (falsification: expect ~0)")
    print(f"  divergences={out['diagnostics']['divergences']}  maxRhat={out['diagnostics']['max_rhat']:.3f}")


if __name__ == "__main__":
    sys.exit(main())
