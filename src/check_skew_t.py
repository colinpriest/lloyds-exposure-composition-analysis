"""Skewed-shock sensitivity: the adopted model with a Jones-Faddy skew-t shock, through the headline's estimator (D3-3).

The adopted model's shock is a Student-t with location 0 (calibrate_dispersion_ritc.py). The clean residuals lean
adverse: most of the clean residuals beyond +/-3 are adverse, against about half expected under the fitted t (P-16; the
counts and the fitted degrees of freedom are in the headline record and the regeneration moves them, so they are not
quoted here). The headline VaR does not come from the t directly: it comes from the empirical-pool operator, donors'
standardised residuals rescaled by posterior draws of k, gamma, the floor and the tail indices, and those residuals
already carry the lean. The t enters through the scale law and the RITC quantile map, so only a refit through the
same estimator says whether a skewed shock moves the stress.

The refit replaces the likelihood's Student-t by pm.SkewStudentT (Jones and Faddy 2003) with
    a = (nu/2) exp(delta),   b = (nu/2) exp(-delta),
for each regime's nu (nu_clean, nu_ritc) and ONE shared delta ~ Normal(0, 0.5), location 0 as in the adopted model.
At delta = 0, a = b = nu/2 and the density is the Student-t with nu degrees of freedom exactly, so delta = 0 is the
adopted model. delta > 0 leans the shock adverse. The shock's implied median and mean, which are no longer 0, are
reported at the posterior mean.

The VaR goes through the headline's estimator (vignette_uncertainty.py's primary replicates): the same donor pool,
the same Bayesian-bootstrap weights and posterior indices (its seed and replicate count), the size-only operator
(transfer_operator.HEADLINE), and the RITC quantile map in the skewed family, z_clean =
F^-1_{JF(a_clean, b_clean)}(F_{JF(a_ritc, b_ritc)}(z)), which is vignette_uncertainty.deritc_resid at delta = 0.

A delta = 0 control refits the same code with delta fixed at zero, on two seeds: each must reproduce the headline
within adopted_model.check_against_headline, and the spread of its VaR between the seeds is the noise floor. The
result records a flag, for Colin's decision (D3-3): the posterior median adverse VaR99.5 at either vignette moves by
more than 5% against the control, and by more than the control's seed-to-seed spread. The flag is read only if both
controls reproduce the headline (flag_valid): otherwise it is None, because a control that does not reproduce the
headline is no noise floor (the review of 4 October 2026, finding 2). The record also carries Vignette 2's change, old
to new, and the probability it rises: the paper's Vignette 2 conclusion is that sign, and the VaR99.5 levels do not say
it.

Writes check_skew_t_results.json.
Usage:  python src/check_skew_t.py
"""
import io
import json
import math
import sys
from pathlib import Path

import numpy as np
from scipy import special
import pytensor

pytensor.config.mode = "NUMBA"
import pymc as pm  # noqa: E402
import arviz as az  # noqa: E402

import adopted_model  # noqa: E402
from adopted_model import scale_block, SAMPLE_CORES  # noqa: E402
import transfer_operator  # noqa: E402
import vignette_uncertainty as VU  # noqa: E402

SD = Path(__file__).resolve().parent.parent
OUT = SD / "results" / "check_skew_t_results.json"
#: the adopted sampling configuration (fx_sensitivity.py, calibrate_dispersion_ritc.py): 4 x 1500 draws, the same
#: number as the published draws, so the estimator's posterior indices address the same positions
DRAWS, TUNE, CHAINS, TARGET_ACCEPT = 1500, 1500, 4, 0.98
FIT_SEED = 42
CONTROL_SEEDS = (42, 20261004)
DELTA_PRIOR_SD = 0.5
MOVE_LINE = 0.05
MAX_RHAT = 1.05
VIGNETTES = ("V1_adj_v995", "V2_new_v995")


# ---------------------------------------------------------------- the Jones-Faddy skew-t, unit scale
def jf_ab(nu, delta):
    """The Jones-Faddy shape pair for tail index nu and skewness index delta: (nu/2) e^delta, (nu/2) e^-delta."""
    return 0.5 * nu * math.exp(delta), 0.5 * nu * math.exp(-delta)


def jf_cdf(t, a, b):
    """F(t) = I_x(a, b) with x = (1 + t / sqrt(a + b + t^2)) / 2: the variable is a transformed Beta(a, b)."""
    t = np.asarray(t, float)
    return special.betainc(a, b, 0.5 * (1.0 + t / np.sqrt(a + b + t * t)))


def jf_ppf(u, a, b):
    x = special.betaincinv(a, b, np.asarray(u, float))
    return np.sqrt(a + b) * (2.0 * x - 1.0) / (2.0 * np.sqrt(x * (1.0 - x)))


def jf_mean(a, b):
    """The mean, which exists when a and b exceed 1/2 (Jones and Faddy 2003)."""
    if a <= 0.5 or b <= 0.5:
        return None
    return float((a - b) * math.sqrt(a + b) * math.exp(math.lgamma(a - 0.5) + math.lgamma(b - 0.5)
                                                       - math.lgamma(a) - math.lgamma(b)) / 2.0)


def implied_shock(nu, delta):
    """The unit-scale shock's median and mean under (nu, delta); both are 0 at delta = 0."""
    a, b = jf_ab(nu, delta)
    return {"a": a, "b": b, "median": float(jf_ppf(0.5, a, b)), "mean": jf_mean(a, b)}


# ---------------------------------------------------------------- the model
def build_model(S, R, H, yr, ritc, fix_delta=None):
    """The adopted block with the skew-t likelihood; `fix_delta` = 0 is the adopted model through this code."""
    with pm.Model() as m:
        b = scale_block(R=R, H=H, yr=yr, ritc=ritc)
        delta = pm.Normal("delta", 0.0, DELTA_PRIOR_SD) if fix_delta is None else float(fix_delta)
        half = 0.5 * b["nu_obs"]
        pm.SkewStudentT("S_obs", a=half * pm.math.exp(delta), b=half * pm.math.exp(-delta), mu=0.0,
                        sigma=b["sigma"], observed=S)
    return m


def fit(fix_delta=None, seed=FIT_SEED):
    """One fit on the working sample: its draws, diagnostics and the headline guard."""
    S, R, H, yr, _syn, ritc = adopted_model.load_sample()
    with build_model(S, R, H, yr, ritc, fix_delta):
        idata = pm.sample(DRAWS, tune=TUNE, chains=CHAINS, cores=SAMPLE_CORES, target_accept=TARGET_ACCEPT,
                          random_seed=seed, progressbar=False)
    post = idata.posterior
    keep = list(adopted_model.SHARED) + ["delta"]
    draws = {p: np.asarray(post[p]).ravel() for p in keep if p in post}
    rhat = float(az.rhat(idata).to_array().max())
    if rhat > MAX_RHAT:
        raise SystemExit("skew-t fit (delta %s, seed %d) did not converge: max R-hat %.3f" % (fix_delta, seed, rhat))
    ok, rows = adopted_model.check_against_headline(draws)
    return {"draws": draws, "max_rhat": rhat, "divergences": int(idata.sample_stats["diverging"].sum()),
            "reproduces_headline": bool(ok), "guard_rows": rows}


# ---------------------------------------------------------------- the estimator
def deritc_skew(z, th, ritc):
    """vignette_uncertainty.deritc_resid in the skewed family: RITC donors' residuals rank-mapped from the RITC law
    to the clean one, both JF(a, b) at the draw's delta. At delta = 0 it is deritc_resid, zero fixed point included."""
    if ritc is None or not np.any(ritc):
        return z
    delta = float(th.get("delta", 0.0))
    a_r, b_r = jf_ab(float(th["nu_ritc"]), delta)
    a_c, b_c = jf_ab(float(th["nu_clean"]), delta)
    z = np.array(z, float, copy=True)
    zr = z[ritc]
    u = np.clip(jf_cdf(zr, a_r, b_r), 1e-12, 1.0 - 1e-12)
    mapped = jf_ppf(u, a_c, b_c)
    if delta == 0.0:
        mapped = np.where(zr == 0.0, 0.0, mapped)
    z[ritc] = mapped
    return z


def transfer_skew(S, R, H, tgt, th, cfg, ritc=None):
    """vignette_uncertainty.transfer with the skewed RITC map: sigma(target) * map(S / sigma(source))."""
    Rq, Hq = tgt
    sq = VU.sigma_theta(Rq, Hq, th["k"], th["gamma"], th["sd_undiv"], th["sd_div"], *cfg)
    si = VU.sigma_theta(R, H, th["k"], th["gamma"], th["sd_undiv"], th["sd_div"], *cfg)
    return deritc_skew(S / si, th, ritc) * sq


def vignette_vars(draws_fitted, B=None, seed=None, mode=transfer_operator.HEADLINE):
    """The headline estimator's primary replicates (vignette_uncertainty.operator_results, scheme 'bayes', under
    `mode`, the size-only operator by default) for the two adverse VaR99.5s: the same pool, the same generator
    sequence (Bayesian-bootstrap weights, then one posterior index per replicate), the same quantile."""
    S, R, H, synd, year = VU.load_pool()
    ritc = VU.load_ritc(synd, year)
    _d, ref, hlo, hce = VU.load_draws()
    cfg = (ref, hlo, hce)
    v1, v2_old, v2_new = VU.load_targets()
    draws = transfer_operator.params(draws_fitted, mode)
    ndraw = len(draws["k"])
    rng = np.random.default_rng(VU.SEED if seed is None else seed)
    draw = VU.build_resampler(synd, year, "bayes")
    out = {v: [] for v in VIGNETTES + ("V2_old_v995", "V2_change_v995")}
    for _ in range(VU.B if B is None else B):
        idx, w = draw(rng)
        th = VU.posterior_draw(draws, rng, ndraw)
        s, rr = S[idx], ritc[idx]
        out["V1_adj_v995"].append(VU.var_q(transfer_skew(s, R[idx], H[idx], v1, th, cfg, rr), 0.995, w))
        old = VU.var_q(transfer_skew(s, R[idx], H[idx], v2_old, th, cfg, rr), 0.995, w)
        new = VU.var_q(transfer_skew(s, R[idx], H[idx], v2_new, th, cfg, rr), 0.995, w)
        out["V2_new_v995"].append(new)
        out["V2_old_v995"].append(old)
        out["V2_change_v995"].append(new - old)
    summary = {v: {"median": float(np.median(a)), "mean": float(np.mean(a)),
                   "interval_95": [float(np.percentile(a, 2.5)), float(np.percentile(a, 97.5))]}
               for v, a in ((v, np.asarray(x, float)) for v, x in out.items())}
    # the share of replicates in which Vignette 2's VaR99.5 rises, old to new: vignette_uncertainty's
    # P_sign_by_estimator.V2_rise_bayesian_bootstrap at delta = 0
    summary["V2_change_v995"]["P_rise"] = float(np.mean(np.asarray(out["V2_change_v995"], float) > 0))
    return summary


# ---------------------------------------------------------------- the record
def param_summary(draws):
    out = {}
    for p, a in draws.items():
        a = np.asarray(a, float)
        out[p] = {"mean": float(a.mean()), "sd": float(a.std()),
                  "interval_95": [float(np.percentile(a, 2.5)), float(np.percentile(a, 97.5))]}
    return out


def vignette_moves(skew_vars, control_vars, valid=True):
    """Each vignette's move against the delta = 0 control, and whether it is beyond the line and the spread.
    With `valid` False (a control did not reproduce the headline) no flag is given: it is None, never False."""
    moves, flagged = {}, False
    for v in VIGNETTES:
        ctrl = [c[v]["median"] for c in control_vars]
        base = float(np.mean(ctrl))
        spread = float(max(ctrl) - min(ctrl))
        move = skew_vars[v]["median"] - base
        rel = move / abs(base) if base else None
        beyond = bool(rel is not None and abs(rel) > MOVE_LINE and abs(move) > spread) if valid else None
        flagged = flagged or bool(beyond)
        moves[v] = {"skew_median": skew_vars[v]["median"], "control_medians": ctrl, "control_mean_of_medians": base,
                    "control_seed_spread": spread, "move": move, "relative_move": rel,
                    "beyond_5pct_and_the_control_spread": beyond}
    return moves, (flagged if valid else None)


def v2_sign(skew_vars, control_vars):
    """Vignette 2's change in VaR99.5, old to new, and the probability it rises, under the skewed fit and under each
    delta = 0 control (the paper's Vignette 2 conclusion is the sign of this change)."""
    def one(v):
        ch = v["V2_change_v995"]
        return {"old_median": v["V2_old_v995"]["median"], "new_median": v["V2_new_v995"]["median"],
                "change_median": ch["median"], "change_interval_95": ch["interval_95"], "P_rise": ch["P_rise"]}
    skew = one(skew_vars)
    ctrl = [one(c) for c in control_vars]
    base = float(np.mean([c["P_rise"] for c in ctrl]))
    return {"skew": skew, "controls": ctrl, "control_mean_P_rise": base,
            "move_in_P_rise": skew["P_rise"] - base,
            "note": ("P_rise is the share of the headline estimator's replicates in which Vignette 2's VaR99.5 is "
                     "higher under the new target than the old; the paper's Vignette 2 conclusion is this sign. It "
                     "is reported, not flagged: the D3-3 flag rule is on the VaR99.5 levels")}


def assemble(skew, skew_vars, controls, control_vars, overlay=None):
    """The results record from the fits and their VaRs (separated from the fitting so its form can be tested).
    `skew_vars` and `control_vars` are the headline (size-only) operator's; `overlay`, when given, is the pair
    (skew_vars, control_vars) under the concentration overlay, recorded as the labelled sensitivity. The flag is
    the headline's, and it is None, with flag_valid False, when either control fails to reproduce the headline."""
    d = np.asarray(skew["draws"]["delta"], float)
    nu_c, nu_r = float(np.mean(skew["draws"]["nu_clean"])), float(np.mean(skew["draws"]["nu_ritc"]))
    controls_ok = all(c["reproduces_headline"] for c in controls)
    moves, flagged = vignette_moves(skew_vars, control_vars, controls_ok)
    out = {
        **transfer_operator.stamp(transfer_operator.HEADLINE),
        "purpose": ("the adopted model refitted with a Jones-Faddy skew-t shock, a = (nu/2)e^delta and b = "
                    "(nu/2)e^-delta with one shared delta, and the headline VaR through the same estimator, against a "
                    "delta = 0 control on two seeds (decision D3-3, 4 October 2026)"),
        "likelihood": "pm.SkewStudentT(a=(nu_obs/2)exp(delta), b=(nu_obs/2)exp(-delta), mu=0, sigma=sigma) on "
                      "adopted_model.scale_block; delta ~ Normal(0, %g)" % DELTA_PRIOR_SD,
        "estimator": ("vignette_uncertainty.py's primary replicates (Bayesian bootstrap over syndicates, one "
                      "posterior index per replicate; seed %d, %d replicates), size-only operator, RITC quantile "
                      "map in the skewed family" % (VU.SEED, VU.B)),
        "sampling": {"draws": DRAWS, "tune": TUNE, "chains": CHAINS, "target_accept": TARGET_ACCEPT,
                     "fit_seed": FIT_SEED, "control_seeds": list(CONTROL_SEEDS)},
        "skew_fit": {"params": param_summary(skew["draws"]), "max_rhat": skew["max_rhat"],
                     "divergences": skew["divergences"], "P_delta_gt_0": float(np.mean(d > 0)),
                     "headline_guard": skew["guard_rows"],
                     "implied_shock_at_posterior_mean": {
                         "delta": float(d.mean()),
                         "clean": implied_shock(nu_c, float(d.mean())),
                         "ritc": implied_shock(nu_r, float(d.mean()))},
                     "vignettes": skew_vars},
        "delta_zero_control": [{"seed": seed, "max_rhat": c["max_rhat"], "divergences": c["divergences"],
                                "reproduces_headline": c["reproduces_headline"], "headline_guard": c["guard_rows"],
                                "vignettes": cv}
                               for seed, c, cv in zip(CONTROL_SEEDS, controls, control_vars)],
        "controls_reproduce_the_headline": controls_ok,
        "vignette_moves": moves,
        "vignette2_sign": v2_sign(skew_vars, control_vars),
        "flag_valid": controls_ok,
        "flag_for_decision": flagged,
        "flag_rule": ("set when the posterior median adverse VaR99.5 at either vignette moves by more than %g%% "
                      "against the delta = 0 control and by more than the control's seed-to-seed spread, under the "
                      "headline size-only operator; if set, the numbers go to Colin as decision C of D3-3 (adopt the "
                      "skewed shock). It is None, and flag_valid is False, when a control does not reproduce the "
                      "headline: that control is no noise floor" % (100 * MOVE_LINE)),
        "flag_caveat": ("the two delta = 0 controls share the replicate seed and the posterior positions, so their "
                        "spread is tiny and in practice the 5% line decides the "
                        "flag; a move just beyond the line is weak evidence and the PC reads the moves, not the flag "
                        "alone"),
    }
    if overlay is not None:
        ov_skew, ov_controls = overlay
        ov_moves, ov_flag = vignette_moves(ov_skew, ov_controls, controls_ok)
        out["overlay_sensitivity"] = {**transfer_operator.stamp(transfer_operator.SENSITIVITY),
                                      "skew_vignettes": ov_skew, "control_vignettes": ov_controls,
                                      "vignette_moves": ov_moves, "beyond_the_line_under_the_overlay": ov_flag,
                                      "vignette2_sign": v2_sign(ov_skew, ov_controls)}
    return out


def run():
    skew = fit(None, FIT_SEED)
    controls = [fit(0.0, seed) for seed in CONTROL_SEEDS]
    for c in controls:
        c["draws"]["delta"] = np.zeros_like(c["draws"]["k"])
    ov = transfer_operator.SENSITIVITY
    return assemble(skew, vignette_vars(skew["draws"]), controls, [vignette_vars(c["draws"]) for c in controls],
                    overlay=(vignette_vars(skew["draws"], mode=ov), [vignette_vars(c["draws"], mode=ov)
                                                                      for c in controls]))


def main():
    out = run()
    with io.open(OUT, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(out, indent=1) + "\n")
    sk = out["skew_fit"]["params"]["delta"]
    print("delta %.3f [%.3f, %.3f]; flag for decision: %s (valid: %s)"
          % (sk["mean"], *sk["interval_95"], out["flag_for_decision"], out["flag_valid"]))
    for v, m in out["vignette_moves"].items():
        print("  %s: skew %.4f vs control %.4f (spread %.4f): %+.1f%%"
              % (v, m["skew_median"], m["control_mean_of_medians"], m["control_seed_spread"],
                 100 * (m["relative_move"] or 0)))
    s2 = out["vignette2_sign"]
    print("  V2 change (new - old) %.4f, P(rise) %.3f under the skew fit; control mean P(rise) %.3f"
          % (s2["skew"]["change_median"], s2["skew"]["P_rise"], s2["control_mean_P_rise"]))
    print("Wrote %s" % OUT)
    return 0


if __name__ == "__main__":
    sys.exit(main())
