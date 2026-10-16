"""Selection weighting and two missing-outcome sensitivities.

``missingness_check.py`` first separates structural absence of an outcome,
scientific exclusions, eligible but unavailable outcomes, observed outcomes with
missing composition, and the complete model records. This script then:

1. fits ``P(model-sample membership)`` over the supported disclosure-defined
   target and evaluates explicitly capped, mean-normalised inverse-propensity
   weights at several caps; and
2. appends pseudo-outcomes only for the eligible records whose outcome is genuinely
   unavailable; and
3. separately assumes that all eligibility-unresolved records (those with no deterministic
   reading: the extraction's parsers found no prior-year figure and its models were not run)
   were economically eligible and appends them too. Neither construction is a bound or
   a correction for non-ignorable selection.

Since the author's decision of 14 October 2026 the selection-weighted fits also report the stresses:
under each fit of item 1 (the unweighted refit, a control, and each capped weighting), Vignette 1's
VaR99 and VaR99.5 and Vignette 2's paired change at 99.5% from that fit's own posterior, under the
headline size-only operator (gamma = 0), on the model sample as the vignette donor pool, through the
headline estimator's own function with its seed and B (refit_vignettes.py), beside the headline's
figures and the relative changes. The pool is unweighted there: the weights enter through the fit's
posterior. A centre-only leg weights the pool's scenarios by the same weights as well, which is the
reading under which the weighted model sample stands for the target population. The figures are
written only for fits with no divergence and every R-hat at most 1.01.

Writes ``check_missingness_sensitivity_results.json``.
Usage: python src/check_missingness_sensitivity.py
"""
import io
import json
from pathlib import Path

import arviz as az
import numpy as np
import pymc as pm
import pytensor
from scipy import stats

pytensor.config.mode = "NUMBA"

import assumed_business
import refit_vignettes as RV
import transfer_operator
from adopted_model import SAMPLE_CORES, scale_block
from missingness_check import add_size_proxies, classify_filings, unresolved_filings_from_sources


SD = Path(__file__).resolve().parent.parent
OUT = SD / "results" / "check_missingness_sensitivity_results.json"
REF, HLO, HCE, SEED = 500.0, 0.01, 1.0, 42
C_GRID = [1.0, 1.5, 2.0, 3.0, 5.0]
WEIGHT_CAPS = [0.10, 0.15, 0.20]
PRIMARY_WEIGHT_CAP = 0.15
UNRESOLVED_C_GRID = [1.0, 5.0]


def load_sample():
    with io.open(SD / "model" / "exposure_results.json", encoding="utf-8") as fh:
        data = json.load(fh)
    records = [
        row for row in data["observations"]
        if row.get("s_raw_a") is not None
        and row.get("opening_reserves_gbp_m")
        and row.get("hhi") is not None
        and row.get("pyd_basis") == "gross"
        and row.get("data_quality_tag") not in (
            "NET_BASIS", "UNKNOWN_BASIS", "TAKEON_NOT_DEVELOPMENT",
            "PROVISION_MOVEMENT_NOT_DEVELOPMENT", "GROSS_TRIANGLE_DOES_NOT_RECONCILE",
        )
    ]
    S = np.array([row["s_raw_a"] for row in records], float)
    R = np.array([row["opening_reserves_gbp_m"] for row in records], float)
    H = np.clip(np.array([row["hhi"] for row in records], float), HLO, HCE)
    year = np.array([row["year"] for row in records], int)
    key = np.array([f"syndicate_{row['syndicate']}_{row['year']}.json" for row in records])
    syndicate = np.array([row["syndicate"] for row in records], int)
    return S, R, H, year, key, syndicate


def ritc_flag(key):
    occurrences = assumed_business.keys()
    return np.array([
        Path(name).stem.removeprefix("syndicate_") in occurrences for name in key
    ])


#: gamma is 0 in the likelihood (the headline's since option B, 10 October 2026): not a fitted parameter here
VARIABLES = ["k", "sd_undiv", "sd_div", "nu_clean", "nu_ritc", "tau_s"]


def summarise(idata, variables=VARIABLES):
    """Each parameter's posterior mean and 95% HDI, stored unrounded, and the fit's diagnostics.

    ArviZ's summary rounds by default. It kept 3 decimals here, so the high-volatility stress fit's nu_clean mean
    was stored as 3.655 and printed "3.65" at 2 dp, a tie that no committed output could settle (round 62's
    verification, N-V-A-2). The documents format what is stored, so what is stored is the unrounded value."""
    summary = az.summary(idata, var_names=variables, hdi_prob=0.95, round_to="none")
    out = {
        name: {
            "mean": float(summary.loc[name, "mean"]),
            "hdi_2.5": float(summary.loc[name, "hdi_2.5%"]),
            "hdi_97.5": float(summary.loc[name, "hdi_97.5%"]),
        }
        for name in variables
    }
    out["_diag"] = {
        "max_rhat": float(summary["r_hat"].max()),
        "divergences": int(idata.sample_stats["diverging"].sum()),
    }
    return out


def fit(S, R, H, yidx, n_y, ritc, tag, weights=None, keep=None, keep_as=None):
    """Adopted model, with an optional observation-weighted likelihood. With `keep` (a dict), the fit's operator
    draws and convergence are stored in it under `keep_as`, for the stresses under the weights."""
    logR, logH = np.log(R / REF), np.log(H)
    with pm.Model():
        block = scale_block(
            ritc=ritc, logR=logR, logH=logH, yidx=yidx, n_y=n_y
        )
        nu_obs, sigma = block["nu_obs"], block["sigma"]
        if weights is None:
            pm.StudentT("S_obs", nu=nu_obs, mu=0.0, sigma=sigma, observed=S)
        else:
            dist = pm.StudentT.dist(nu=nu_obs, mu=0.0, sigma=sigma)
            pm.Potential("S_obs_w", (pm.logp(dist, S) * weights).sum())
        idata = pm.sample(
            1500, tune=1500, chains=4, cores=SAMPLE_CORES,
            target_accept=0.98, random_seed=SEED, progressbar=False,
        )
    out = summarise(idata)
    print(
        f"    {tag:34s} k={out['k']['mean']:.3f} "
        f"[{out['k']['hdi_2.5']:.3f},{out['k']['hdi_97.5']:.3f}] "
        f"floor={out['sd_undiv']['mean']:.4f} "
        f"nu={out['nu_clean']['mean']:.2f} div={out['_diag']['divergences']}"
    )
    if keep is not None:
        keep[keep_as] = {"draws": RV.operator_draws(idata), "convergence": RV.convergence(idata)}
    return out


#: the fits whose stresses are reported: the unweighted refit (a control: the headline's model, data and seed) and
#: each capped weighting
WEIGHTED_STRESS_FITS = ("unweighted",) + tuple(f"ipw_cap_{cap:.2f}" for cap in WEIGHT_CAPS)


def stress_under_weights(kept, keys, S, R, weight_sets):
    """Vignette 1's VaR99 and VaR99.5 and Vignette 2's change under each fit in WEIGHTED_STRESS_FITS, from its own
    posterior, on the model sample as the donor pool, beside the headline's (refit_vignettes.py). `keys` are the model
    sample's syndicate-years in load_sample's order, which `S`, `R` and every weight vector follow."""
    for tag in WEIGHTED_STRESS_FITS:
        if not RV.converged(kept[tag]["convergence"]):
            raise SystemExit("the %s fit has not converged (%s): no stresses are written"
                             % (tag, kept[tag]["convergence"]))
    recorded = RV.headline_record()
    head, _head_draws, cfg = RV.headline_block(recorded)
    pool, ritc, pkeys = RV.pool_for(keys)
    RV.check_pool_is_the_fit_sample(pool, pkeys, keys, S, R)
    position = {k: i for i, k in enumerate(keys)}
    to_pool = np.array([position[k] for k in pkeys])
    out = {
        "question": "what do the vignette stresses become under the selection-weighted fits?",
        "seed": recorded["seed"], "B": recorded["B"], "estimator": RV.ESTIMATOR,
        "pool": {"n_donors": int(len(pkeys)),
                 "definition": ("the model sample (load_sample) as the vignette donor pool (the shipped tool's donors, "
                                "in its order, checked equal to the fitted records); unweighted, so each weighting "
                                "acts through its fit's posterior only")},
        "pool_weighted_note": ("centre_pool_weighted: the same centre with each donor's scenario mass set to its "
                               "weight (the weighted inverse-CDF VaR), so the pool too stands for the target "
                               "population; centre only, no interval"),
        "headline": {"source": "results/check_gamma0_vignette_results.json, the headline operator's block "
                               "(its centre recomputed here and found equal)", **head},
        "by_fit": {},
    }
    for tag in WEIGHTED_STRESS_FITS:
        draws = kept[tag]["draws"]
        block = RV.vignettes(draws, pool, ritc, cfg, recorded)
        cap = None if tag == "unweighted" else float(tag.rsplit("_", 1)[1])
        entry = {"fit": tag, "probability_floor": cap, "convergence": kept[tag]["convergence"], **block,
                 "relative_to_headline": RV.relative(block["centre"], head["centre"])}
        if cap is not None:
            weights = weight_sets[cap][to_pool]
            weighted = RV.centre_only(draws, pool, ritc, cfg, weights=weights)
            entry["centre_pool_weighted"] = weighted
            entry["centre_pool_weighted_relative_to_headline"] = RV.relative(weighted, head["centre"])
        out["by_fit"][tag] = entry
        print(f"    stresses under {tag:16s} V1 VaR99.5 {block['centre']['V1_v995']:.4f} "
              f"({100 * entry['relative_to_headline']['V1_v995']:+.2f}%)  V2 change {block['centre']['V2_d995']:.4f} "
              f"({100 * entry['relative_to_headline']['V2_d995']:+.2f}%)  [{transfer_operator.HEADLINE}]")
    return out


def _logistic_propensity(target, years):
    log_size = np.log([row["size_proxy"] for row in target])
    year = np.array([row["year"] for row in target], int)
    response = np.array([row["category"] == "working_sample" for row in target], float)
    design = np.column_stack(
        [np.ones(len(target)), log_size]
        + [(year == value).astype(float) for value in years[1:]]
    )
    beta = np.zeros(design.shape[1])
    for _ in range(60):
        probability = 1.0 / (1.0 + np.exp(-design @ beta))
        variance = probability * (1 - probability) + 1e-9
        beta += np.linalg.pinv((design * variance[:, None]).T @ design) @ (
            design.T @ (response - probability)
        )
    return beta


def propensity_weights(phat, cap=None):
    """Return mean-one inverse-propensity weights and overlap diagnostics."""
    phat = np.asarray(phat, float)
    denominator = phat if cap is None else np.maximum(phat, cap)
    raw = 1.0 / denominator
    weights = raw / raw.mean()
    diagnostics = {
        "cap": cap,
        "normalisation": "divide by the model-sample mean so weights average one",
        "n_below_cap": 0 if cap is None else int(np.sum(phat < cap)),
        "weight_min": float(weights.min()),
        "weight_max": float(weights.max()),
        "weight_mean": float(weights.mean()),
        "weight_sum": float(weights.sum()),
        "kish_effective_sample_size": float(weights.sum() ** 2 / np.sum(weights ** 2)),
    }
    return weights, diagnostics


def _pseudo_inputs(records, dispositions, R, H):
    """Size, HHI and year inputs for pseudo-outcomes, with explicit imputation."""
    observed_hhi = {}
    for row in dispositions:
        obs = row["observation"]
        if obs and obs.get("hhi") is not None:
            observed_hhi.setdefault(row["syndicate"], []).append(float(obs["hhi"]))
    syndicate_hhi = {s: float(np.median(values)) for s, values in observed_hhi.items()}
    overall_hhi = float(np.median(H))
    overall_size = float(np.median(R))
    sizes = np.array([
        row["size_proxy"] if row["size_proxy"] is not None else overall_size
        for row in records
    ], float)
    hhi = np.array([
        (float(row["observation"]["hhi"])
         if row["observation"] and row["observation"].get("hhi") is not None
         else syndicate_hhi.get(row["syndicate"], overall_hhi))
        for row in records
    ], float)
    years = np.array([row["year"] for row in records], int)
    return sizes, hhi, years, {
        "size": (
            "filing or same-syndicate proxy where available; otherwise working-sample median"
        ),
        "n_size_imputed_working_sample_median": int(sum(
            row["size_proxy"] is None for row in records
        )),
        "hhi": (
            "record HHI where available, otherwise same-syndicate median, otherwise "
            "working-sample median"
        ),
    }


def _stress_fit(records, dispositions, S, R, H, year, ritc, calibration,
                c_grid, label, interpretation):
    """Fit the adopted model after adding deterministic pseudo-outcome quantiles."""
    k0, g0 = calibration["k"], calibration["gamma"]
    su0, sd0, nu0 = (
        calibration["sd_undiv"], calibration["sd_div"], calibration["nu_clean"]
    )
    R_missing, H_missing, year_missing, imputation = _pseudo_inputs(
        records, dispositions, R, H
    )
    q = (np.arange(len(records)) + 0.5) / len(records)
    effective_size = (R_missing / REF) * (1.0 / H_missing) ** g0
    sigma_missing = np.sqrt(
        su0 ** 2 + sd0 ** 2 * effective_size ** (2.0 * (k0 - 1.0))
    )
    base_t = stats.t.ppf(q, df=nu0)
    stress = {
        "n_pseudo": len(records),
        "records": [row["file"] for row in records],
        "size_m": {
            "min": float(R_missing.min()),
            "max": float(R_missing.max()),
            "median": float(np.median(R_missing)),
        },
        "imputation": imputation,
        "placement": "equally spaced Student-t quantiles scaled by c*sigma(R,H)",
        "interpretation": interpretation,
        "by_c": {},
    }
    for c in c_grid:
        S_aug = np.concatenate([S, c * sigma_missing * base_t])
        R_aug = np.concatenate([R, R_missing])
        H_aug = np.concatenate([H, H_missing])
        year_aug = np.concatenate([year, year_missing])
        ritc_aug = np.concatenate([ritc, np.zeros(len(records))])
        years_aug = np.sort(np.unique(year_aug))
        yidx_aug = np.searchsorted(years_aug, year_aug)
        stress["by_c"][str(c)] = fit(
            S_aug, R_aug, H_aug, yidx_aug, len(years_aug), ritc_aug,
            f"{label} x{c:g}",
        )
    return stress


def check_populations(S, dispositions, unresolved):
    """The populations this sensitivity is written for, each against a second count of the same filings. The model
    sample the adopted model loads (load_sample) must be the partition's working sample, and the unresolved filings
    must be the records the extraction left unread with the stubs the filing-page audit left unresolved. These were
    typed (695 model records, 805 supported target, 12 unavailable, 45 unresolved) and had to be retyped at every
    data change; the author's decisions D1 and D2 of 30 September 2026 move the target and the unresolved filings
    (FIX3 A4)."""
    working = sum(row["category"] == "working_sample" for row in dispositions)
    if len(S) != working:
        raise AssertionError(f"the adopted model loads {len(S)} records and the partition's working sample holds "
                             f"{working}")
    expected = unresolved_filings_from_sources()
    found = {row["file"] for row in unresolved}
    if found != expected:
        raise AssertionError("the partition's unresolved filings are not the records left unread and the audit's "
                             "unresolved stubs: %d extra %s, %d missing %s"
                             % (len(found - expected), sorted(found - expected)[:5], len(expected - found),
                                sorted(expected - found)[:5]))


def main():
    S, R, H, year, key, syndicate = load_sample()
    ritc = ritc_flag(key).astype(float)
    model_years = np.sort(np.unique(year))
    yidx = np.searchsorted(model_years, year)

    dispositions = add_size_proxies(classify_filings())
    target = [row for row in dispositions if row["category"] in {
        "eligible_outcome_unavailable",
        "eligible_observed_composition_unavailable",
        "working_sample",
    }]
    unavailable = [
        row for row in target if row["category"] == "eligible_outcome_unavailable"
    ]
    unresolved = [
        row for row in dispositions if row["category"] == "eligibility_unresolved"
    ]
    check_populations(S, dispositions, unresolved)
    target_years = np.sort(np.unique([row["year"] for row in target]))
    beta = _logistic_propensity(target, target_years)
    model_design = np.column_stack(
        [np.ones(len(S)), np.log(R)]
        + [(year == value).astype(float) for value in target_years[1:]]
    )
    phat = 1.0 / (1.0 + np.exp(-model_design @ beta))
    weight_sets = {}
    weight_diagnostics = {}
    for cap in WEIGHT_CAPS:
        weight_sets[cap], weight_diagnostics[str(cap)] = propensity_weights(phat, cap)
    _, uncapped_diagnostic = propensity_weights(phat)
    weights = weight_sets[PRIMARY_WEIGHT_CAP]
    print(
        f"target={len(target)} model-sample={len(S)} unavailable outcomes={len(unavailable)}; "
        f"coef(log R)={beta[1]:+.3f}; p range [{phat.min():.3f},{phat.max():.3f}]; "
        f"weight range [{weights.min():.2f},{weights.max():.2f}]"
    )

    result = {
        "n_model_sample": len(S),
        "n_supported_target_population": len(target),
        "n_target_population": len(target),
        "n_eligibility_unresolved": len(unresolved),
        "n_broader_potential_target_if_all_unresolved_eligible": len(target) + len(unresolved),
        "n_eligible_outcome_unavailable": len(unavailable),
        "seed": SEED,
        "selection_response": f"membership in the {len(S)}-record model sample",
        "propensity_model": {
            "formula": "logit P(model-sample membership) ~ log R + reporting year",
            "coef_logR": float(beta[1]),
            "p_hat_min": float(phat.min()),
            "p_hat_max": float(phat.max()),
            "primary_probability_floor": PRIMARY_WEIGHT_CAP,
            "primary_weight_rule": (
                "w_i = [1/max(p_hat_i, 0.15)] / mean_j[1/max(p_hat_j, 0.15)]"
            ),
            "cap_rationale": (
                "A pragmatic bounded-weight sensitivity, not an identified correction: 0.15 "
                "limits domination under poor overlap and is bracketed by 0.10 and 0.20 fits."
            ),
            "weighted_likelihood": (
                "sum_i w_i log StudentT(S_i | theta); propensity estimates and weights are "
                "held fixed, so posterior intervals are conditional and omit propensity-model "
                "uncertainty"
            ),
            "primary_diagnostics": weight_diagnostics[str(PRIMARY_WEIGHT_CAP)],
            "uncapped_diagnostic_not_fitted": uncapped_diagnostic,
            "cap_diagnostics": weight_diagnostics,
        },
        "fits": {},
    }
    kept = {}
    result["fits"]["unweighted"] = fit(
        S, R, H, yidx, len(model_years), ritc, "unweighted headline", keep=kept, keep_as="unweighted"
    )
    for cap in WEIGHT_CAPS:
        cap_key = f"ipw_cap_{cap:.2f}"
        result["fits"][cap_key] = fit(
            S, R, H, yidx, len(model_years), ritc,
            f"bounded IPW cap {cap:.2f}", weights=weight_sets[cap], keep=kept, keep_as=cap_key,
        )
    result["fits"]["ipw_model_sample"] = result["fits"]["ipw_cap_0.15"]
    model_keys = [f"{s}_{y}" for s, y in zip(syndicate, year)]
    result["stress_under_selection_weights"] = stress_under_weights(kept, model_keys, S, R, weight_sets)

    calibration = json.load(io.open(
        SD / "model" / "dispersion_calibration_ritc.json", encoding="utf-8"
    ))
    result["eligible_outcome_stress"] = _stress_fit(
        unavailable, dispositions, S, R, H, year, ritc, calibration, C_GRID,
        "eligible unavailable",
        "one-direction sensitivity within the supported target; not a bound",
    )
    broader_missing = unavailable + unresolved
    result["eligibility_unresolved_stress"] = _stress_fit(
        broader_missing, dispositions, S, R, H, year, ritc, calibration,
        UNRESOLVED_C_GRID, "known unavailable plus unresolved",
        f"assumes all {len(unresolved)} records with no deterministic reading were economically eligible, "
        f"appends them with the {len(unavailable)} known unavailable outcomes, and expands "
        f"the potential target to {len(target) + len(unresolved)}; "
        "not a bound or an estimate of their eligibility",
    )
    result["eligibility_unresolved_stress"]["n_known_eligible_unavailable"] = len(unavailable)
    result["eligibility_unresolved_stress"]["n_eligibility_unresolved"] = len(unresolved)
    io.open(OUT, "w", encoding="utf-8", newline="").write(json.dumps(result, indent=2) + "\n")
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    main()
