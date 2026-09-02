"""The concentration-location relationship, fitted inside the ADOPTED model.

Table 6 of the manuscript once reported this relationship under a "95% HDI" heading
with a slope standard error and a p-value beneath it. The interval printed there,
[-0.081, +0.052], was exactly -0.014 +/- 1.96*0.034: a Wald interval left over from
the superseded least-squares method, which no script here produced.

The first replacement was also wrong. It retyped its likelihood from
calibrate_dispersion.py -- the older SINGLE-REGIME fit, one common nu, no RITC scale
term -- while claiming to be the adopted model, and returned gamma = 0.310 against
the adopted model's 0.243 without anyone noticing the gap. The scale and tail now
come from adopted_model.scale_block(), which is the two-regime specification, and
every fit here is checked against the published posterior before its location
coefficient is believed.

Five fits, differing only in the location:

  ctrl  mu = 0                                    (must reproduce the headline)
  A     mu = m0 + m1 (H - Hbar)
  B     A + m2 (logR - logRbar)
  C     A + alpha_i,  alpha_i ~ Normal(0, tau_alpha^2)
  D     mu = m0 + m_w (H - Hbar_i) + m_b (Hbar_i - Hbar) + alpha_i

C and D exist because A pools repeated observations of the same syndicate as though
they were independent, while the paper itself finds a persistent syndicate intercept
of tau_alpha = 0.041 -- comparable with the whole diversifiable scale. A concentration
slope estimated without it can be reporting culture rather than portfolio mix. D
separates the two channels: m_w is what happens when a syndicate's OWN concentration
moves, m_b is whether persistently more concentrated syndicates sit at a different
level. Only m_w is a portfolio effect.

Run: python src/check_mean_concentration_bayes.py
"""
import io
import json

import numpy as np
import pytensor

pytensor.config.mode = "NUMBA"
import arviz as az
import pymc as pm

from adopted_model import (SD, REFERENCE_SIZE, load_sample, scale_block,
                           check_against_headline, report)

OUT = SD / "results" / "check_mean_concentration_bayes_results.json"
SEED = 42


def hdi95(x):
    a = np.asarray(x, float).ravel()
    if a.min() == a.max():
        return [float(a[0]), float(a[0])]
    return [float(v) for v in az.hdi(a, hdi_prob=0.95)]


def summarise(draws):
    d = np.asarray(draws, float).ravel()
    return {"mean": float(d.mean()), "hdi": hdi95(d),
            "P_lt_0": float((d < 0).mean())}


def fit(S, R, H, yr, ritc, sidx, n_s, spec, tag):
    """The adopted model with `spec` deciding the location only."""
    logR = np.log(R / REFERENCE_SIZE)
    Hc = H - H.mean()
    logRc = logR - logR.mean()
    # each syndicate's own mean concentration, and its deviation from it
    Hbar_i = np.array([H[sidx == j].mean() for j in range(n_s)])
    H_within = H - Hbar_i[sidx]
    H_between = Hbar_i[sidx] - H.mean()

    with pm.Model():
        b = scale_block(R, H, yr, ritc)
        wanted = ["k", "gamma", "sd_undiv", "nu_clean", "nu_ritc", "beta_ritc"]

        if spec == "ctrl":
            mu = 0.0
        else:
            m0 = pm.Normal("m0", 0.0, 0.1)
            mu = m0
            if spec in ("A", "B", "C"):
                m1 = pm.Normal("m1", 0.0, 0.5)
                mu = mu + m1 * Hc
            if spec == "B":
                m2 = pm.Normal("m2", 0.0, 0.5)
                mu = mu + m2 * logRc
            if spec == "D":
                mw = pm.Normal("m_within", 0.0, 0.5)
                mb = pm.Normal("m_between", 0.0, 0.5)
                mu = mu + mw * H_within + mb * H_between
            if spec in ("C", "D"):
                tau_a = pm.HalfNormal("tau_alpha", 0.05)
                z_a = pm.Normal("z_alpha", 0.0, 1.0, shape=n_s)
                mu = mu + (tau_a * z_a)[sidx]

        pm.StudentT("S_obs", nu=b["nu_obs"], mu=mu, sigma=b["sigma"], observed=S)
        idata = pm.sample(1500, tune=1500, chains=4, cores=1, target_accept=0.98,
                          random_seed=SEED, progressbar=False)

    post = idata.posterior
    shared = {p: post[p].values.ravel() for p in wanted}
    ok, rows = check_against_headline(shared)
    names = [n for n in ("m0", "m1", "m2", "m_within", "m_between", "tau_alpha")
             if n in post]
    s = az.summary(idata, var_names=wanted + names, hdi_prob=0.95)

    out = {"spec": spec, "label": tag,
           # only the mu=0 control is REQUIRED to reproduce the published fit; the
           # location variants are expected to move the scale parameters, and that
           # movement is a reported finding rather than a defect
           "must_match_headline": spec == "ctrl",
           "adopted_model_consistent": bool(ok),
           "shared_vs_headline": rows,
           "shared": {p: {"mean": float(v.mean()), "hdi": hdi95(v)}
                      for p, v in shared.items()},
           "max_rhat": float(s["r_hat"].max()),
           "min_ess_bulk": float(s["ess_bulk"].min()),
           "divergences": int(idata.sample_stats["diverging"].sum())}
    for n in names:
        out[n] = summarise(post[n].values)
    print("\n[%s] %s" % (spec, tag))
    report(rows, ok)
    for n in names:
        o = out[n]
        print("    %-11s %+.4f  95%% HDI [%+.4f, %+.4f]  P(<0)=%.2f"
              % (n, o["mean"], o["hdi"][0], o["hdi"][1], o["P_lt_0"]))
    print("    Rhat %.3f  divergences %d" % (out["max_rhat"], out["divergences"]))
    return out, post


def main():
    S, R, H, yr, syn, ritc = load_sample()
    sids = np.sort(np.unique(syn))
    sidx = np.searchsorted(sids, syn)
    n_s = len(sids)
    print("n=%d  syndicates=%d  RITC=%d  Hbar=%.4f"
          % (len(S), n_s, int(ritc.sum()), H.mean()))

    specs = [("ctrl", "mu = 0: must reproduce the published adopted fit"),
             ("A", "pooled concentration slope"),
             ("B", "pooled slope with a log R control"),
             ("C", "pooled slope with a syndicate random intercept"),
             ("D", "within/between concentration, syndicate random intercept")]
    fits, posts = {}, {}
    for spec, tag in specs:
        fits[spec], posts[spec] = fit(S, R, H, yr, ritc, sidx, n_s, spec, tag)

    res = {"n": int(len(S)), "n_syndicates": int(n_s), "seed": SEED,
           "H_mean": float(H.mean()),
           "spec": ("adopted two-regime model (adopted_model.scale_block) with the "
                    "location freed; nu_clean, lambda_ritc, per-observation nu and "
                    "beta_ritc all present"),
           "history": ("replaces a Wald interval from the superseded least-squares "
                       "method, and a first replacement that was fitted on the older "
                       "single-regime likelihood"),
           "fits": fits}

    # the shift the manuscript quotes, taken from whichever slope is the portfolio one
    for spec, key in (("A", "m1"), ("C", "m1"), ("D", "m_within")):
        d = np.asarray(posts[spec][key].values, float).ravel() * (0.9 - 0.1)
        res.setdefault("shift_H_0.1_to_0.9", {})[spec] = summarise(d)

    OUT.write_text(json.dumps(res, indent=2), encoding="utf-8")
    print("\nwritten to", OUT)
    bad = [s for s, f in fits.items()
           if f["must_match_headline"] and not f["adopted_model_consistent"]]
    if bad:
        print("*** control fit(s) failed to reproduce the published model: %s"
              % ", ".join(bad))
    moved = [s for s, f in fits.items()
             if not f["must_match_headline"] and not f["adopted_model_consistent"]]
    if moved:
        print("variants whose shared parameters moved (expected, and reported): %s"
              % ", ".join(moved))


if __name__ == "__main__":
    main()
