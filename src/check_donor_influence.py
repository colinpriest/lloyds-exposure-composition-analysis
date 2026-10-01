"""The headline with and without Vignette 1's most adverse donor (the author's decision of 1 October 2026).

The measurement behind the in-sample run-off decision found that the headline's upper tail rests on one record:
1991/2020, a syndicate placed into run-off on 6 November 2020 after writing business for most of the year (a
part-year run-off year, so the rule keeps it), and the most adverse donor in Vignette 1's pool. The author asked
for that influence to be reported. This script finds the pool's most adverse donor under the headline (size-only)
operator at the published posterior mean, refits the adopted model without it at the adopted sampling
configuration (fx_sensitivity.fit_adopted_config, calibrate_dispersion_ritc.py's call), and recomputes the
vignettes with the published estimator (vignette_uncertainty.operator_results: the centre, the full pool at the
posterior mean, and the posterior mean with its 2.5-97.5% interval, a Bayesian bootstrap by syndicate with one
posterior draw per replicate) on the pool without it.

The headline side is refitted the same way on the full sample and must reproduce the published calibration and
vignettes exactly, so the two sides differ only by the donor. Two separately fitted posteriors are compared at
their summaries; no interval for the difference is estimated. Each side also carries the fitted concentration
overlay's centres, the labelled sensitivity every operator output carries beside the headline.

Writes results/check_donor_influence_results.json.
Run: python src/check_donor_influence.py
"""
import io
import json
from pathlib import Path

import numpy as np

from adopted_model import load_sample
from fx_sensitivity import CHAINS, DRAWS, SEED, TARGET_ACCEPT, TUNE, fit_adopted_config
import run_analysis
import transfer_operator
import vignette_uncertainty as VU

SD = Path(__file__).resolve().parent.parent
CALIBRATION = SD / "model" / "dispersion_calibration_ritc.json"
VIGNETTES = SD / "results" / "vignette_uncertainty_results.json"
OUT = SD / "results" / "check_donor_influence_results.json"
PARAMS = ("k", "gamma", "sd_undiv", "sd_div", "nu_clean", "nu_ritc")
#: the refit of the full sample must reproduce the published calibration's posterior means, and the recomputed
#: vignettes the published ones, to this (the same code, seeds and data give the same numbers)
REPRODUCE_TOL = 1e-9


def transferred_pool(draws=None):
    """(keys, S, transferred): Vignette 1's pool (the tool's donors) moved to the V1 target by the headline operator
    at the posterior mean of `draws` (the published draws by default)."""
    S, R, H, synd, year = VU.load_pool()
    published, ref, hlo, hce = VU.load_draws()
    draws = published if draws is None else draws
    th = {p: float(np.asarray(v).mean())
          for p, v in transfer_operator.params(draws, transfer_operator.HEADLINE).items()}
    v1, _v2o, _v2n = VU.load_targets()
    a = VU.transfer(S, R, H, v1, th, (ref, hlo, hce), VU.load_ritc(synd, year))
    return ["%s_%s" % (s, y) for s, y in zip(synd, year)], S, np.asarray(a)


def most_adverse(keys, transferred):
    """(key, index) of the pool's most adverse donor; a tie is refused, since the question has no single answer."""
    order = np.argsort(-np.asarray(transferred), kind="stable")
    if len(order) > 1 and transferred[order[0]] == transferred[order[1]]:
        raise SystemExit("two donors tie for the most adverse: %s, %s" % (keys[order[0]], keys[order[1]]))
    return keys[int(order[0])], int(order[0])


def vignettes(keep, draws):
    """The published estimator on the donors `keep` marks, with `draws`: V1 VaR99.5 and the V2 change at 99.5%."""
    S, R, H, synd, year = VU.load_pool()
    _published, ref, hlo, hce = VU.load_draws()
    vdraws = {p: np.asarray(draws[p]) for p in PARAMS}
    block, _prim, centres = VU.operator_results(
        transfer_operator.HEADLINE, S[keep], R[keep], H[keep], synd[keep], year[keep], vdraws,
        VU.load_ritc(synd[keep], year[keep]), (ref, hlo, hce), VU.load_targets(), robustness=False)
    v1 = block["vignette1"]["adjusted"]["var995"]
    v2 = block["vignette2"]["change_old_to_new"]["abs_995"]
    return {"V1_VaR995": {"centre": float(centres["V1_adj"]["v995"]), "posterior_mean": float(v1["mean"]),
                          "hdi_2.5": float(v1["lo"]), "hdi_97.5": float(v1["hi"])},
            "V2_change995": {"centre": float(centres["V2_d995"]), "posterior_mean": float(v2["mean"]),
                             "hdi_2.5": float(v2["lo"]), "hdi_97.5": float(v2["hi"])}}


def overlay_centres(keep, draws):
    """The fitted concentration overlay, the labelled sensitivity beside every headline figure: V1 VaR99.5 and the
    V2 change at 99.5% on the donors `keep` marks, the full pool at the posterior mean (vignette_uncertainty's
    centres under the overlay operator)."""
    S, R, H, synd, year = VU.load_pool()
    _published, ref, hlo, hce = VU.load_draws()
    th = {p: float(np.asarray(v).mean()) for p, v in
          transfer_operator.params({p: np.asarray(draws[p]) for p in PARAMS}, transfer_operator.SENSITIVITY).items()}
    v1, v2o, v2n = VU.load_targets()
    ritc, cfg = VU.load_ritc(synd[keep], year[keep]), (ref, hlo, hce)
    a1, ao, an = (VU.transfer(S[keep], R[keep], H[keep], t, th, cfg, ritc) for t in (v1, v2o, v2n))
    return {**transfer_operator.stamp(transfer_operator.SENSITIVITY),
            "V1_VaR995_centre": float(VU.var_q(a1, 0.995)),
            "V2_change995_centre": float(VU.var_q(an, 0.995) - VU.var_q(ao, 0.995))}


def published_overlay():
    """The vignette record's overlay centres: V1 VaR99.5 and the V2 change at 99.5%."""
    c = json.load(io.open(str(VIGNETTES), encoding="utf-8"))["overlay_sensitivity"]["centres_full_pool_posterior_mean"]
    return {"V1_VaR995_centre": float(c["V1_adj"]["v995"]), "V2_change995_centre": float(c["V2_d995"])}


def summary(S, R, H, yr, ritc, fit):
    """One refit's summary, and its draws."""
    means, params, diag, draws, cond = fit(S, R, H, yr, ritc)
    return {"n": int(len(S)), "n_ritc": int(np.asarray(ritc).sum()),
            "params": {p: params[p] for p in PARAMS if p in params}, "means": {p: float(means[p]) for p in PARAMS},
            "P_nu_ritc_lt_nu_clean": cond.get("P_nu_ritc_lt_nu_clean"), "diagnostics": diag}, draws


def published():
    """The published headline: the calibration's means and the vignette record's size-only figures."""
    cal = json.load(io.open(str(CALIBRATION), encoding="utf-8"))
    vu = json.load(io.open(str(VIGNETTES), encoding="utf-8"))
    v1, v2 = vu["vignette1"]["adjusted"]["var995"], vu["vignette2"]["change_old_to_new"]["abs_995"]
    centres = vu["centres_full_pool_posterior_mean"]
    return ({p: float(cal[p]) for p in PARAMS},
            {"V1_VaR995": {"centre": float(centres["V1_adj"]["v995"]), "posterior_mean": float(v1["mean"]),
                           "hdi_2.5": float(v1["lo"]), "hdi_97.5": float(v1["hi"])},
             "V2_change995": {"centre": float(centres["V2_d995"]), "posterior_mean": float(v2["mean"]),
                              "hdi_2.5": float(v2["lo"]), "hdi_97.5": float(v2["hi"])}})


def donor_reading(key):
    """The corpus-wide run-off register's reading of the donor's filing, if it has one."""
    entry = run_analysis.load_runoff_corpus_register().get(key)
    if entry is None:
        return None
    return {k: entry.get(k) for k in ("category", "runoff_from", "source_page", "source_page_printed")}


def main(fit=fit_adopted_config):
    S, R, H, yr, syn, ritc = load_sample()        # the adopted working sample
    keys = ["%s_%s" % (s, y) for s, y in zip(syn, yr)]
    pool_keys, pool_S, transferred = transferred_pool()
    if sorted(pool_keys) != sorted(keys):
        raise SystemExit("the tool's donor pool is not the working sample")
    donor, i = most_adverse(pool_keys, transferred)
    order = np.argsort(-transferred, kind="stable")

    pub_means, pub_vignettes = published()
    with_fit, with_draws = summary(S, R, H, yr, ritc, fit)
    off = {p: abs(with_fit["means"][p] - pub_means[p]) for p in PARAMS}
    if max(off.values()) > REPRODUCE_TOL:
        raise SystemExit("the refit of the full sample does not reproduce the published calibration: %s" % off)
    all_donors = np.ones(len(pool_keys), bool)
    with_vignettes = vignettes(all_donors, with_draws)
    apart = {"%s %s" % (name, stat): abs(with_vignettes[name][stat] - pub_vignettes[name][stat])
             for name in pub_vignettes for stat in pub_vignettes[name]}
    if max(apart.values()) > REPRODUCE_TOL:
        raise SystemExit("the vignettes recomputed on the full pool are not the published ones: %s" % apart)
    with_overlay = overlay_centres(all_donors, with_draws)
    apart = {k: abs(with_overlay[k] - v) for k, v in published_overlay().items()}
    if max(apart.values()) > REPRODUCE_TOL:
        raise SystemExit("the overlay centres recomputed on the full pool are not the published ones: %s" % apart)

    keep = np.array([k != donor for k in keys])
    without_fit, without_draws = summary(S[keep], R[keep], H[keep], yr[keep], ritc[keep], fit)
    pool_keep = np.array([k != donor for k in pool_keys])
    without_vignettes = vignettes(pool_keep, without_draws)

    fits = {"with": {**with_fit, **with_vignettes, "overlay_sensitivity": with_overlay},
            "without": {**without_fit, **without_vignettes,
                        "overlay_sensitivity": overlay_centres(pool_keep, without_draws)}}
    change = {}
    for name in ("V1_VaR995", "V2_change995"):
        for stat in ("centre", "posterior_mean", "hdi_2.5", "hdi_97.5"):
            a, b = fits["with"][name][stat], fits["without"][name][stat]
            change["%s_%s" % (name, stat)] = {"with": a, "without": b, "change": b - a,
                                              "pct_change": 100.0 * (b / a - 1.0)}
    for p in PARAMS:
        a, b = fits["with"]["means"][p], fits["without"]["means"][p]
        change[p] = {"with": a, "without": b, "change": b - a, "pct_change": 100.0 * (b / a - 1.0)}
    out = {
        "question": "how much of the headline rests on Vignette 1's most adverse donor?",
        **transfer_operator.stamp(transfer_operator.HEADLINE),
        "donor": {"key": donor, "rank": 1, "n_pool": len(pool_keys), "S": float(pool_S[i]),
                  "transferred_at_posterior_mean": float(transferred[i]),
                  "next_most_adverse": {"key": pool_keys[int(order[1])],
                                        "transferred_at_posterior_mean": float(transferred[int(order[1])])},
                  "regime": "RITC" if ritc[keys.index(donor)] > 0.5 else "clean",
                  "runoff_reading": donor_reading(donor)},
        "sampling": {"draws": DRAWS, "tune": TUNE, "chains": CHAINS, "target_accept": TARGET_ACCEPT, "seed": SEED,
                     "same_as": "calibrate_dispersion_ritc.py"},
        "vignette_estimator": {"B": VU.B, "seed": VU.SEED, "same_as": "vignette_uncertainty.py (primary)"},
        "fits": fits,
        "changes": dict(change, note=("two separately fitted posteriors compared at their summaries; no interval "
                                      "for the difference is estimated")),
    }
    io.open(str(OUT), "w", encoding="utf-8", newline="\n").write(json.dumps(out, indent=1) + "\n")
    print("most adverse donor %s (transferred %+.4f; next %s %+.4f)" % (
        donor, transferred[i], out["donor"]["next_most_adverse"]["key"],
        out["donor"]["next_most_adverse"]["transferred_at_posterior_mean"]))
    for side in ("with", "without"):
        f = fits[side]
        print("  %-7s n=%d k=%.4f gamma=%.4f floor=%.4f nu_clean=%.3f nu_ritc=%.3f  V1 %.4f / %.4f [%.4f, %.4f]"
              "  V2 %.5f / %.5f" % (side, f["n"], f["means"]["k"], f["means"]["gamma"], f["means"]["sd_undiv"],
                                    f["means"]["nu_clean"], f["means"]["nu_ritc"], f["V1_VaR995"]["centre"],
                                    f["V1_VaR995"]["posterior_mean"], f["V1_VaR995"]["hdi_2.5"],
                                    f["V1_VaR995"]["hdi_97.5"], f["V2_change995"]["centre"],
                                    f["V2_change995"]["posterior_mean"]))
    print("Wrote %s" % OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
