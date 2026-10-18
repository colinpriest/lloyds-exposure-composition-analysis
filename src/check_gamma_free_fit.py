"""Sensitivity: the gamma-free fit beside the gamma = 0 headline.

Since the author's decision of 10 October 2026 (option B) the headline is the adopted two-regime model with the
concentration exponent gamma FIXED AT 0 in the likelihood (calibrate_dispersion_ritc.py), and the headline
size-only operator is that fit's own posterior: a refit, not a zeroing. The same model with gamma fitted,
gamma ~ HalfNormal(1) (calibrate_dispersion_ritc_gamma_free.py), is the gamma-free fit: the concentration
overlay's only source. Before option B the gamma-free fit was the headline and the size-only operator zeroed
gamma in its retained draws; this check (until then the script check_gamma0_refit, which fitted the gamma = 0 model as
its sensitivity) now inverts that comparison. It fits nothing: it reads both calibrations and their draws, and
records

  (1) the gamma-free fit's parameters (gamma with its 95% HDI and P(gamma > 0.05), and k, sigma_undiv, sigma_div,
      nu_clean, nu_RITC, lambda, beta_RITC, tau_s) beside the headline's, each mean's relative change, and the
      gamma-free fit's gaps from the headline in the units of adopted_model.check_against_headline, RECORDED and
      not enforced: the gamma-free fit is a departure by declaration (it fits a concentration term the headline
      fixes at 0, and sigma_div moves with the concentration factor its scale carries);
  (2) Vignette 1's VaR99 and VaR99.5 and Vignette 2's paired change at 99.5% under three constructions, through
      the transfer, targets, cluster resampler, seed and B of check_gamma0_vignette.py (its own function, called
      here): the headline (the gamma = 0 fit, size-only); the RETIRED construction (the gamma-free fit with gamma
      zeroed in its draws, transfer_operator.params(retired_zeroing=True): the bridge to the figures the paper
      printed before option B); and the overlay (the gamma-free fit, its fitted gamma). The headline and the
      overlay must equal check_gamma0_vignette.py's record exactly, or the comparison is not like for like and
      nothing is written. The retired construction's relative change from the headline is listed where it is 2%
      or more;
  (3) the 100m/2,000m scale ratio of the headline's size-only scale law and of the retired construction's, and,
      in a block of its own, the concentration overlay's ratio at H = 0.4 under the gamma-free fit's posterior-mean
      scale law (its fitted gamma), the paper's labelled sensitivity;
  (4) the overlay's concentration effect at a fixed 500m, sigma at H = 0.9 over sigma at H = 0.1, under the gamma-free
      fit's posterior-mean scale law, with the two scales (under the size-only headline sigma does not depend on H).

Each block carries the operator it was computed under (transfer_operator.stamp), and the file as a whole the headline
size-only operator's, which its headline figures are: the overlay's figures sit in blocks stamped "overlay" (the
manuscript's gate CD binds each registry entry to the stamp of the block it reads).

Writes check_gamma_free_fit_results.json.
Usage:  python src/check_gamma_free_fit.py [B]
"""
import io
import json
import sys
import time

import numpy as np

from adopted_model import SD, HEADLINE_JSON, GAMMA_FREE_JSON, check_against_headline
import transfer_operator
from check_gamma0_vignette import operator_vignettes
from vignette_uncertainty import load_pool, load_ritc, load_targets, sigma_theta

OUT = SD / "results" / "check_gamma_free_fit_results.json"
GAMMA0 = SD / "results" / "check_gamma0_vignette_results.json"
B = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else 4000
VIG_SEED = 20240704          # check_gamma0_vignette.py's
PARAMS = ("k", "sd_undiv", "sd_div", "nu_clean", "nu_ritc", "lambda_ritc", "beta_ritc", "tau_s")
#: the npz's parameters (tau_s is not persisted in the draws; the guard reads its posterior mean from the JSON)
DRAW_PARAMS = ("k", "gamma", "sd_undiv", "sd_div", "nu_clean", "nu_ritc", "lambda_ritc", "beta_ritc")
QUANTITIES = ("V1_v99", "V1_v995", "V2_d995")
#: the quantities a move of RELATIVE_FLAG or more is reported on
HEADLINE_QUANTITIES = ("k", "sd_undiv", "V1_v995", "V2_d995")
RELATIVE_FLAG = 0.02
SIZE_RATIO_RS = (100.0, 2000.0)
H_RATIO = 0.4
#: the overlay's concentration effect: the scale at a fixed size, at the two concentrations
CONC_R = 500.0
CONC_HS = (0.1, 0.9)
RETIRED = ("retired size-only construction: the gamma-free fit with gamma set to zero in every retained posterior draw "
           "(and in the posterior mean); k, sigma_undiv, sigma_div, nu_clean and nu_RITC keep the gamma-free fit's "
           "values; not a refit. The paper's headline before option B (10 October 2026); recorded as the bridge to "
           "the figures printed then")


def relative(new, old):
    return new / old - 1.0


def fit_params(cal):
    """{param: mean, sd, HDI} of one calibration: the means at full precision where the calibration stores them at
    its top level (its params block rounds), every other entry from the params block."""
    h = cal["params"]
    names = PARAMS + (("gamma",) if "gamma" in h else ())
    return {p: {"mean": float(cal[p]) if p in cal else float(h[p]["mean"]), "sd": float(h[p]["sd"]),
                "hdi_2.5": float(h[p]["hdi_2.5"]), "hdi_97.5": float(h[p]["hdi_97.5"])} for p in names}


def size_ratio(means, cfg):
    """sigma(100m) / sigma(2,000m) under a posterior-mean scale law whose gamma is already as the construction sets
    it (0 for both size-only constructions)."""
    s = [float(sigma_theta(r, H_RATIO, means["k"], means["gamma"], means["sd_undiv"], means["sd_div"], *cfg))
         for r in SIZE_RATIO_RS]
    return s[0] / s[1]


def overlay_size_ratio(cal, cfg):
    """sigma(100m) / sigma(2,000m) at H_RATIO under the gamma-free fit's posterior-mean scale law, its fitted gamma in
    force (the calibration's top-level means, at full precision)."""
    s = [float(sigma_theta(r, H_RATIO, cal["k"], cal["gamma"], cal["sd_undiv"], cal["sd_div"], *cfg))
         for r in SIZE_RATIO_RS]
    return s[0] / s[1]


def concentration_effect(cal, cfg):
    """The overlay's scale at CONC_R and each of CONC_HS, and their ratio (high over low), under the gamma-free fit's
    posterior-mean scale law (the calibration's top-level means, at full precision)."""
    lo, hi = (float(sigma_theta(CONC_R, h, cal["k"], cal["gamma"], cal["sd_undiv"], cal["sd_div"], *cfg))
              for h in CONC_HS)
    if not hi / lo > 1.0:
        raise SystemExit("the overlay's concentration effect %.4f does not raise the scale" % (hi / lo))
    return lo, hi


def main():
    t0 = time.time()
    cal_h = transfer_operator.load_calibration(transfer_operator.HEADLINE)
    cal_g = transfer_operator.load_calibration(transfer_operator.OVERLAY)
    if cal_h.get("gamma_prior") != "fixed_0" or cal_h["gamma"] != 0.0:
        raise SystemExit("%s is not the gamma = 0 headline fit" % HEADLINE_JSON.name)
    if "gamma" not in cal_g["params"]:
        raise SystemExit("%s carries no fitted gamma" % GAMMA_FREE_JSON.name)
    draws_h, ref, hlo, hce = transfer_operator.load_draws(transfer_operator.HEADLINE, keys=DRAW_PARAMS)
    draws_g, ref_g, hlo_g, hce_g = transfer_operator.load_draws(transfer_operator.OVERLAY, keys=DRAW_PARAMS)
    if (ref, hlo, hce) != (ref_g, hlo_g, hce_g):
        raise SystemExit("the two fits' reference size and H bounds differ")
    cfg = (ref, hlo, hce)
    vig_keys = transfer_operator.OPERATOR_KEYS
    vh = {p: draws_h[p] for p in vig_keys}
    vg = {p: draws_g[p] for p in vig_keys}
    # the retired construction, built here and only here (transfer_operator.RETIRED_ZEROING_DECLARED)
    vr = transfer_operator.params(vg, transfer_operator.SIZE_ONLY, retired_zeroing=True)

    pool = load_pool()
    ritc = load_ritc(pool[3], pool[4])
    targets = load_targets()
    with io.open(GAMMA0, encoding="utf-8") as _fh:
        recorded = json.load(_fh)
    blk_h = operator_vignettes(transfer_operator.HEADLINE, pool, vh, cfg, ritc, targets, b=B, seed=VIG_SEED)
    blk_o = operator_vignettes(transfer_operator.OVERLAY, pool, vg, cfg, ritc, targets, b=B, seed=VIG_SEED)
    for mode, blk in ((transfer_operator.HEADLINE, blk_h), (transfer_operator.OVERLAY, blk_o)):
        rec = recorded[mode]
        if rec["centre"] != blk["centre"] or (B == recorded["B"] and rec["intervals"] != blk["intervals"]):
            raise SystemExit("the %s vignettes differ from check_gamma0_vignette.py's record: %s against %s"
                             % (mode, blk["centre"], rec["centre"]))
    blk_r = operator_vignettes(transfer_operator.SIZE_ONLY, pool, vr, cfg, ritc, targets, b=B, seed=VIG_SEED)
    ch, cr, co = blk_h["centre"], blk_r["centre"], blk_o["centre"]
    vignettes = {
        "seed": VIG_SEED, "B": B,
        "estimator": ("check_gamma0_vignette.py's run: centre on the whole pool at the posterior means; intervals "
                      "are the 2.5 and 97.5 percentiles over a cluster bootstrap by syndicate with one posterior "
                      "draw per replicate (not a posterior interval)"),
        "headline": {**transfer_operator.stamp(transfer_operator.HEADLINE),
                     "centre": ch, "intervals": blk_h["intervals"]},
        "retired_zeroing": {"construction": RETIRED, "centre": cr, "intervals": blk_r["intervals"]},
        "overlay_sensitivity": {**transfer_operator.stamp(transfer_operator.OVERLAY),
                                "gamma_in_force_posterior_mean": blk_o["gamma_in_force_posterior_mean"],
                                "centre": co, "intervals": blk_o["intervals"]},
        "retired_pct_change_from_headline": {q: 100.0 * relative(cr[q], ch[q]) for q in ch},
        "retired_change_from_headline": {q: cr[q] - ch[q] for q in ch},
        "overlay_pct_change_from_headline": {q: 100.0 * relative(co[q], ch[q]) for q in ch},
    }

    params_h, params_g = fit_params(cal_h), fit_params(cal_g)
    relative_change = {p: relative(params_g[p]["mean"], params_h[p]["mean"]) for p in PARAMS}
    retired_relative = {q: relative(cr[q], ch[q]) for q in ch}
    # k and sigma_undiv of the retired construction are the gamma-free fit's, so its move in them is the fit's
    moved = sorted(q for q in HEADLINE_QUANTITIES
                   if abs(relative_change[q] if q in relative_change else retired_relative[q]) >= RELATIVE_FLAG)

    means_h = {p: float(np.mean(vh[p])) for p in vig_keys}
    means_r = {p: float(np.mean(vr[p])) for p in vig_keys}
    ratio_h, ratio_r = size_ratio(means_h, cfg), size_ratio(means_r, cfg)
    conc_lo, conc_hi = concentration_effect(cal_g, cfg)
    ratio_o = overlay_size_ratio(cal_g, cfg)
    if not ratio_o < ratio_h:
        raise SystemExit("the overlay's 100m/2,000m ratio %.4f is not below the size-only headline's %.4f"
                         % (ratio_o, ratio_h))

    # tau_s is not in the draws: the guard reads the gamma-free fit's posterior mean (as its params block stores it)
    guard_ok, guard_rows = check_against_headline({
        **{p: draws_g[p] for p in DRAW_PARAMS},
        "tau_s": np.array([float(cal_g["params"]["tau_s"]["mean"])])})
    sample = {k: cal_h[k] for k in ("n", "n_ritc", "n_years")}
    if sample != {k: cal_g[k] for k in ("n", "n_ritc", "n_years")}:
        raise SystemExit("the two fits are on different samples")
    out = {
        "question": ("The headline fixes gamma at 0 in the likelihood (option B). What does the gamma-free fit, the "
                     "overlay's source, say beside it, and how far is the retired zeroing construction (the "
                     "headline before option B) from the headline?"),
        # the file's headline figures are the size-only operator's; the overlay's are in blocks stamped "overlay"
        **transfer_operator.stamp(transfer_operator.HEADLINE),
        **sample, "fit_seed": cal_h["seed"],
        "headline_fit": {"source": "model/dispersion_calibration_ritc.json",
                         "spec": ("adopted_model.scale_block(gamma_prior='fixed_0'): gamma = 0, no concentration "
                                  "term in the likelihood"),
                         "params": params_h, "diagnostics": cal_h["diagnostics"],
                         "posterior_prob": {"nu_ritc_lt_nu_clean": cal_h["posterior_prob"]["nu_ritc_lt_nu_clean"]}},
        "gamma_free_fit": {"source": "model/dispersion_calibration_ritc_gamma_free.json",
                           "spec": ("adopted_model.scale_block(gamma_prior='halfnormal'): gamma ~ HalfNormal(1); "
                                    "every other term as the headline"),
                           "params": params_g, "diagnostics": cal_g["diagnostics"],
                           "posterior_prob": {k: cal_g["posterior_prob"][k]
                                              for k in ("gamma_gt_0.05", "nu_ritc_lt_nu_clean")},
                           "prior_prob": {"gamma_gt_0.05": cal_g["prior_prob"]["gamma_gt_0.05"]}},
        "relative_change_of_means": {"note": "gamma-free fit's mean / headline's - 1", **relative_change},
        "retired_relative_to_headline": {"note": "retired zeroing construction / headline - 1", **retired_relative},
        "headline_quantities_moved_by_2pct_or_more": moved,
        "relative_flag": RELATIVE_FLAG,
        "headline_guard": {"enforced": False,
                           "why_not": ("the gamma-free fit is a departure by declaration: it fits the concentration "
                                       "term the headline fixes at 0, and sigma_div moves with the concentration "
                                       "factor its scale carries; the rows are recorded so the size of each gap can "
                                       "be read"),
                           "within_tolerance": bool(guard_ok), "rows": guard_rows},
        "vignettes": vignettes,
        "size_ratio_100_2000_size_only": {
            "scale_law": ("the posterior-mean scale law at H = %g: the headline's (gamma = 0 in the likelihood) and "
                          "the retired construction's (the gamma-free fit, gamma zeroed)" % H_RATIO),
            **transfer_operator.stamp(transfer_operator.HEADLINE),
            "headline": ratio_h, "retired_zeroing": ratio_r, "retired_pct_change": 100.0 * relative(ratio_r, ratio_h)},
        "size_ratio_100_2000_overlay": {
            "H": H_RATIO,
            "scale_law": ("the gamma-free fit's posterior-mean scale law at H = %g, its fitted gamma in force: the "
                          "concentration overlay's ratio, a labelled sensitivity beside the size-only headline's "
                          "(size_ratio_100_2000_size_only)" % H_RATIO),
            **transfer_operator.stamp(transfer_operator.OVERLAY),
            "gamma_free_fit": ratio_o},
        "concentration_effect_500m": {
            "scale_law": ("the gamma-free fit's posterior-mean scale law (its fitted gamma) at R = %gm; under the "
                          "size-only headline sigma does not depend on H" % CONC_R),
            **transfer_operator.stamp(transfer_operator.OVERLAY),
            "R_m": CONC_R, "H_low": CONC_HS[0], "H_high": CONC_HS[1],
            "sigma_H_low": conc_lo, "sigma_H_high": conc_hi, "ratio": conc_hi / conc_lo},
        "runtime_seconds": time.time() - t0,
    }
    with io.open(OUT, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(out, indent=2) + "\n")
    print("Wrote %s" % OUT)
    print("  gamma-free fit: gamma %.4f [%.4f, %.4f], P(gamma > 0.05) %.3f"
          % (params_g["gamma"]["mean"], params_g["gamma"]["hdi_2.5"], params_g["gamma"]["hdi_97.5"],
             cal_g["posterior_prob"]["gamma_gt_0.05"]))
    for p in PARAMS:
        print("  %-11s headline %8.4f   gamma-free %8.4f   (%+.2f%%)"
              % (p, params_h[p]["mean"], params_g[p]["mean"], 100 * relative_change[p]))
    for q in QUANTITIES:
        print("  %-8s headline %.4f   retired %.4f (%+.2f%%)   overlay %.4f (%+.2f%%)"
              % (q, ch[q], cr[q], vignettes["retired_pct_change_from_headline"][q], co[q],
                 vignettes["overlay_pct_change_from_headline"][q]))
    print("  100m/2,000m size-only ratio: headline %.3f   retired %.3f" % (ratio_h, ratio_r))
    print("  100m/2,000m overlay ratio at H = %g: %.3f" % (H_RATIO, ratio_o))
    print("  overlay's concentration effect at %gm, H %g to %g: %.4f to %.4f (ratio %.3f)"
          % (CONC_R, CONC_HS[0], CONC_HS[1], conc_lo, conc_hi, conc_hi / conc_lo))
    print("  headline guard (recorded, not enforced): %s" % ("within tolerance" if guard_ok else "outside tolerance"))
    if moved:
        print("  MOVED BY 2%% OR MORE: %s" % ", ".join(moved))


if __name__ == "__main__":
    sys.exit(main())
