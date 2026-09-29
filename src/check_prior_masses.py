"""The prior probability of every event the paper quotes as a posterior probability, beside the posterior.

The review of 29 September 2026 (M-4) found posterior probabilities read as evidence that are mostly
prior: P(gamma > 0.05) = 0.97 against a prior mass of 0.96, P(nu_RITC < nu_clean) = 0.46 against 0.50,
P(nu_RITC < 2) = 0.03 against 0.036. A posterior probability says what the data did only beside what
the prior already said. So each quoted event is written here with both, with their difference and with
the Bayes factor for the event (posterior odds over prior odds), and flagged as data-informed when the
two differ by at least INFORMED (0.05) OR the odds moved by at least ODDS_FACTOR (3) either way. The
distance alone misreads a rare event: P(nu_clean < 2) falls from a prior 0.018 to 0 of 6,000 draws,
which the data plainly decided, at a distance of only 0.018. (3 is Jeffreys' conventional line for
"substantial"; it is a reading convention, not a test.)

The priors are READ from adopted_model.scale_block, not retyped: a PyMC model is built with the block and
each prior's family and parameters are taken from the graph. Each event's prior mass is then the exact
closed form for that family (scipy) or a one-dimensional quadrature where the event involves a derived
quantity (nu_RITC = nu_clean exp(-lambda_RITC); sigma_undiv = exp(log_tot) sqrt(f)), and a Monte Carlo
draw from the same model's prior checks each value. A family the closed forms do not cover stops the
script: a changed prior needs its closed form checked, not assumed.

The posterior masses are counted over model/dispersion_posterior_draws_ritc.npz, the 6,000 draws of the
adopted fit, and those the calibration also records (posterior_prob) must agree with it.

One source. The calibration (calibrate_dispersion_ritc.py) records the same prior masses as `prior_prob`
beside its `posterior_prob`, under the calibration's key names (CALIBRATION_KEYS), by calling
calibration_prior_prob() here on its own model; this script checks the recorded values against its own.

Writes check_prior_masses_results.json.
Run: python src/check_prior_masses.py
"""
import io
import json
from pathlib import Path

import numpy as np
from scipy import integrate, stats
import pytensor
pytensor.config.mode = "NUMBA"
import pymc as pm

import adopted_model

SD = Path(__file__).resolve().parent.parent
OUT = SD / "results" / "check_prior_masses_results.json"
DRAWS = SD / "model" / "dispersion_posterior_draws_ritc.npz"
CALIBRATION = SD / "model" / "dispersion_calibration_ritc.json"
#: a posterior probability within this of its prior mass, and whose odds moved by less than ODDS_FACTOR,
#: is reported as not informed by the data
INFORMED = 0.05
ODDS_FACTOR = 3.0
MC_DRAWS, MC_SEED = 20000, 20260929

#: (key, how the paper writes it, key in the calibration's posterior_prob and prior_prob, or None)
EVENTS = (
    ("gamma_gt_0.05", "P(gamma > 0.05)", "gamma_gt_0.05"),
    ("nu_ritc_lt_nu_clean", "P(nu_RITC < nu_clean)", "nu_ritc_lt_nu_clean"),
    ("nu_ritc_lt_2", "P(nu_RITC < 2)", "nu_ritc_lt_2"),
    ("nu_clean_lt_2", "P(nu_clean < 2)", "nu_clean_lt_2"),
    ("sd_undiv_gt_0.005", "P(sigma_undiv > 0.005)", "sd_undiv_gt_0.005"),
    ("beta_ritc_abs_gt_0.1", "P(|beta_RITC| > 0.1)", "beta_ritc_gt_0.1_abs"),
    ("k_gt_0.5", "P(k > 1/2)", None),
    ("k_lt_1", "P(k < 1)", None),
)
#: this module's event keys -> the calibration's, for the events the calibration records a prior mass for (the
#: manuscript's registry reads model/dispersion_calibration_ritc.json's prior_prob under these names)
CALIBRATION_KEYS = {key: cal for key, _label, cal in EVENTS if cal is not None}


def prior_model():
    """The adopted model built from scale_block on the working sample: its priors are the fit's."""
    S, R, H, yr, syn, ritc = adopted_model.load_sample()
    with pm.Model() as m:
        adopted_model.scale_block(R=R, H=H, yr=yr, ritc=ritc)
    return m


def prior_of(m, name):
    """(family, parameters) of a free variable's prior, read from the graph."""
    rv = m[name]
    op = rv.owner.op
    params = op.dist_params(rv.owner) if hasattr(op, "dist_params") else rv.owner.inputs[2:]
    return type(op).__name__, [float(np.asarray(p.eval())) for p in params]


def _require(fam, got, want, name):
    if got != want:
        raise SystemExit("the prior on %s is now %s, not %s: its closed form below must be re-derived"
                         % (name, got, want))
    return fam


def prior_masses(m):
    """{event key: prior probability}, exact or by quadrature, from the priors in the graph."""
    fam, (g_loc, g_scale) = prior_of(m, "gamma")
    _require(fam, fam, "HalfNormalRV", "gamma")
    fam, (l_mu, l_sd) = prior_of(m, "lambda_ritc")
    _require(fam, fam, "NormalRV", "lambda_ritc")
    fam, (nu_shape, nu_scale) = prior_of(m, "nu_clean")
    _require(fam, fam, "GammaRV", "nu_clean")        # pytensor's GammaRV takes (shape, SCALE)
    fam, (t_mu, t_sd) = prior_of(m, "log_tot")
    _require(fam, fam, "NormalRV", "log_tot")
    fam, (f_a, f_b) = prior_of(m, "f")
    _require(fam, fam, "BetaRV", "f")
    fam, (b_mu, b_sd) = prior_of(m, "beta_ritc")
    _require(fam, fam, "NormalRV", "beta_ritc")
    fam, (th_mu, th_sd) = prior_of(m, "theta")
    _require(fam, fam, "NormalRV", "theta")

    nu = stats.gamma(a=nu_shape, scale=nu_scale)
    lam = stats.norm(l_mu, l_sd)
    out = {}
    # gamma ~ HalfNormal(loc, scale): P(gamma > c) = 2 (1 - Phi((c - loc)/scale))
    out["gamma_gt_0.05"] = float(2.0 * stats.norm.sf((0.05 - g_loc) / g_scale))
    # nu_RITC = nu_clean exp(-lambda) < nu_clean  <=>  lambda > 0
    out["nu_ritc_lt_nu_clean"] = float(lam.sf(0.0))
    # P(nu_clean exp(-lambda) < 2) = E_lambda[ F_nu(2 exp(lambda)) ]
    out["nu_ritc_lt_2"] = float(integrate.quad(lambda x: nu.cdf(2.0 * np.exp(x)) * lam.pdf(x),
                                               l_mu - 12 * l_sd, l_mu + 12 * l_sd, limit=200)[0])
    out["nu_clean_lt_2"] = float(nu.cdf(2.0))
    # sigma_undiv = exp(log_tot) sqrt(f) > c  <=>  log_tot > log c - log(f)/2
    beta_f = stats.beta(f_a, f_b)
    out["sd_undiv_gt_0.005"] = float(integrate.quad(
        lambda f: beta_f.pdf(f) * stats.norm.sf((np.log(0.005) - 0.5 * np.log(f) - t_mu) / t_sd),
        0.0, 1.0, limit=200)[0])
    b = stats.norm(b_mu, b_sd)
    out["beta_ritc_abs_gt_0.1"] = float(b.sf(0.1) + b.cdf(-0.1))
    # k = 1/2 + sigmoid(theta)/2 lies in (1/2, 1) for every theta: both endpoint masses are one by construction
    out["k_gt_0.5"] = 1.0
    out["k_lt_1"] = 1.0
    return out


def calibration_prior_prob(m):
    """prior_prob as model/dispersion_calibration_ritc.json records it: prior_masses() on the model `m`, under
    the calibration's key names. The calibration calls this on its own model, so there is one computation."""
    masses = prior_masses(m)
    return {cal: masses[key] for key, cal in CALIBRATION_KEYS.items()}


def monte_carlo_masses(m, draws=MC_DRAWS, seed=MC_SEED):
    """The same events counted over draws from the model's own prior: the cross-check of the closed forms."""
    names = ("gamma", "nu_clean", "nu_ritc", "sd_undiv", "beta_ritc", "k")
    vals = pm.draw([m[n] for n in names], draws=draws, random_seed=seed)
    d = {n: np.asarray(v).ravel() for n, v in zip(names, vals)}
    return {"gamma_gt_0.05": float((d["gamma"] > 0.05).mean()),
            "nu_ritc_lt_nu_clean": float((d["nu_ritc"] < d["nu_clean"]).mean()),
            "nu_ritc_lt_2": float((d["nu_ritc"] < 2.0).mean()),
            "nu_clean_lt_2": float((d["nu_clean"] < 2.0).mean()),
            "sd_undiv_gt_0.005": float((d["sd_undiv"] > 0.005).mean()),
            "beta_ritc_abs_gt_0.1": float((np.abs(d["beta_ritc"]) > 0.1).mean()),
            "k_gt_0.5": float((d["k"] > 0.5).mean()),
            "k_lt_1": float((d["k"] < 1.0).mean())}


def posterior_masses(z):
    """The same events counted over the adopted fit's posterior draws."""
    return {"gamma_gt_0.05": float((z["gamma"] > 0.05).mean()),
            "nu_ritc_lt_nu_clean": float((z["nu_ritc"] < z["nu_clean"]).mean()),
            "nu_ritc_lt_2": float((z["nu_ritc"] < 2.0).mean()),
            "nu_clean_lt_2": float((z["nu_clean"] < 2.0).mean()),
            "sd_undiv_gt_0.005": float((z["sd_undiv"] > 0.005).mean()),
            "beta_ritc_abs_gt_0.1": float((np.abs(z["beta_ritc"]) > 0.1).mean()),
            "k_gt_0.5": float((z["k"] > 0.5).mean()),
            "k_lt_1": float((z["k"] < 1.0).mean())}


def bayes_factor(prior, post):
    """Posterior odds over prior odds for an event; inf or 0 when the posterior mass is 1 or 0."""
    if prior <= 0.0 or prior >= 1.0:
        return None
    if post >= 1.0:
        return float("inf")
    if post <= 0.0:
        return 0.0
    return (post / (1.0 - post)) / (prior / (1.0 - prior))


def informed(prior, post):
    """Did the data move this event's probability: by distance or by odds (module docstring)?"""
    bf = bayes_factor(prior, post)
    moved_odds = bf is not None and (bf >= ODDS_FACTOR or bf <= 1.0 / ODDS_FACTOR)
    return bool(abs(post - prior) >= INFORMED or moved_odds)


def compute():
    m = prior_model()
    prior = prior_masses(m)
    mc = monte_carlo_masses(m)
    for key, p in prior.items():
        tol = 5.0 * np.sqrt(max(p * (1.0 - p), 1e-12) / MC_DRAWS) + 1e-3
        if abs(mc[key] - p) > tol:
            raise SystemExit("the prior mass of %s disagrees with a draw from the model's own prior: %.4f "
                             "against %.4f" % (key, p, mc[key]))
    z = np.load(DRAWS)
    post = posterior_masses(z)
    calibration = json.load(io.open(CALIBRATION, encoding="utf-8"))
    cal = calibration.get("posterior_prob", {})
    recorded_prior = calibration.get("prior_prob")
    if recorded_prior is not None:
        for key, cal_key in CALIBRATION_KEYS.items():
            if cal_key not in recorded_prior or abs(recorded_prior[cal_key] - prior[key]) > 1e-12:
                raise SystemExit("the calibration's prior_prob[%s] (%s) is not this script's closed form (%.6f)"
                                 % (cal_key, recorded_prior.get(cal_key), prior[key]))
    rows = {}
    for key, label, cal_key in EVENTS:
        if cal_key is not None and cal_key in cal and abs(cal[cal_key] - post[key]) > 1e-12:
            raise SystemExit("the calibration's %s (%.6f) is not the draws' (%.6f)" % (cal_key, cal[cal_key], post[key]))
        diff = post[key] - prior[key]
        by_construction = key in ("k_gt_0.5", "k_lt_1")
        bf = bayes_factor(prior[key], post[key])
        data_informed = informed(prior[key], post[key]) and not by_construction
        rows[key] = {"event": label, "prior": prior[key], "posterior": post[key],
                     "posterior_minus_prior": diff, "bayes_factor": bf,
                     "prior_monte_carlo": mc[key], "data_informed": data_informed,
                     "reading": ("one by construction on the bracketed support: neither mass is evidence"
                                 if by_construction else
                                 "informed by the data: the posterior moved from the prior mass"
                                 if data_informed else
                                 "mostly the prior: within %.2f of the prior mass and its odds moved by less "
                                 "than a factor of %g; not a finding about the data" % (INFORMED, ODDS_FACTOR))}
    priors = {n: dict(zip(("family", "parameters"), prior_of(m, n)))
              for n in ("theta", "gamma", "log_tot", "f", "nu_clean", "lambda_ritc", "beta_ritc")}
    return {
        "question": ("which of the posterior probabilities the paper quotes did the data inform, and which are "
                     "mostly the prior"),
        "prior_source": "adopted_model.scale_block, read from the PyMC graph (families and parameters below)",
        "priors": priors,
        "posterior_source": "model/dispersion_posterior_draws_ritc.npz (%d draws)" % len(z["k"]),
        "informed_threshold": INFORMED,
        "informed_odds_factor": ODDS_FACTOR,
        "monte_carlo_check": {"draws": MC_DRAWS, "seed": MC_SEED,
                              "tolerance": "5 binomial standard errors + 0.001"},
        "calibration_prior_prob_checked": recorded_prior is not None,
        "events": rows,
    }


def main():
    out = compute()
    OUT.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print("event                      prior   posterior  diff    reading")
    for r in out["events"].values():
        print("  %-24s %.4f  %.4f   %+.4f  %s" % (r["event"], r["prior"], r["posterior"],
                                                 r["posterior_minus_prior"], r["reading"]))
    print("Wrote %s" % OUT)


if __name__ == "__main__":
    main()
