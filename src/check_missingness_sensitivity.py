"""Selection weighting and an eligible-outcome sensitivity.

``missingness_check.py`` first separates structural absence of an outcome,
scientific exclusions, eligible but unavailable outcomes, observed outcomes with
missing composition, and the 685 complete model records. This script then:

1. fits ``P(model-sample membership)`` over that defined target population and
   weights the 685 observed model records by inverse response propensity; and
2. appends pseudo-outcomes only for the eligible records whose outcome is genuinely
   unavailable. Structural stubs and scientific exclusions receive no synthetic
   outcome. The stress changes the target population intentionally and is not a
   bound or a correction for non-ignorable selection.

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
from adopted_model import SAMPLE_CORES, scale_block
from missingness_check import add_size_proxies, classify_filings


SD = Path(__file__).resolve().parent.parent
OUT = SD / "results" / "check_missingness_sensitivity_results.json"
REF, HLO, HCE, SEED = 500.0, 0.01, 1.0, 42
C_GRID = [1.0, 1.5, 2.0, 3.0, 5.0]


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
            "PROVISION_MOVEMENT_NOT_DEVELOPMENT",
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


def fit(S, R, H, yidx, n_y, ritc, tag, weights=None):
    """Adopted model, with an optional observation-weighted likelihood."""
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
    variables = ["k", "gamma", "sd_undiv", "sd_div", "nu_clean", "nu_ritc", "tau_s"]
    summary = az.summary(idata, var_names=variables, hdi_prob=0.95)
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
    print(
        f"    {tag:34s} k={out['k']['mean']:.3f} "
        f"[{out['k']['hdi_2.5']:.3f},{out['k']['hdi_97.5']:.3f}] "
        f"gamma={out['gamma']['mean']:.3f} floor={out['sd_undiv']['mean']:.4f} "
        f"nu={out['nu_clean']['mean']:.2f} div={out['_diag']['divergences']}"
    )
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


def main():
    S, R, H, year, key, syndicate = load_sample()
    if len(S) != 685:
        raise AssertionError(f"expected 685 model records, found {len(S)}")
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
    if len(target) != 794 or len(unavailable) != 12:
        raise AssertionError(
            f"expected target=794 and unavailable outcomes=12; found {len(target)}, {len(unavailable)}"
        )
    target_years = np.sort(np.unique([row["year"] for row in target]))
    beta = _logistic_propensity(target, target_years)
    model_design = np.column_stack(
        [np.ones(len(S)), np.log(R)]
        + [(year == value).astype(float) for value in target_years[1:]]
    )
    phat = 1.0 / (1.0 + np.exp(-model_design @ beta))
    weights = 1.0 / np.clip(phat, 0.15, 1.0)
    weights /= weights.mean()
    print(
        f"target={len(target)} model-sample={len(S)} unavailable outcomes={len(unavailable)}; "
        f"coef(log R)={beta[1]:+.3f}; p range [{phat.min():.3f},{phat.max():.3f}]; "
        f"weight range [{weights.min():.2f},{weights.max():.2f}]"
    )

    result = {
        "n_model_sample": len(S),
        "n_target_population": len(target),
        "n_eligible_outcome_unavailable": len(unavailable),
        "seed": SEED,
        "selection_response": "membership in the 685-record model sample",
        "propensity_model": {
            "formula": "logit P(model-sample membership) ~ log R + reporting year",
            "coef_logR": float(beta[1]),
            "p_hat_min": float(phat.min()),
            "p_hat_max": float(phat.max()),
            "weight_min": float(weights.min()),
            "weight_max": float(weights.max()),
        },
        "fits": {},
    }
    result["fits"]["unweighted"] = fit(
        S, R, H, yidx, len(model_years), ritc, "unweighted headline"
    )
    result["fits"]["ipw_model_sample"] = fit(
        S, R, H, yidx, len(model_years), ritc,
        "IPW model-sample membership", weights=weights,
    )

    calibration = json.load(io.open(
        SD / "model" / "dispersion_calibration_ritc.json", encoding="utf-8"
    ))
    k0, g0 = calibration["k"], calibration["gamma"]
    su0, sd0, nu0 = (
        calibration["sd_undiv"], calibration["sd_div"], calibration["nu_clean"]
    )
    observed_hhi = {}
    for row in dispositions:
        obs = row["observation"]
        if obs and obs.get("hhi") is not None:
            observed_hhi.setdefault(row["syndicate"], []).append(float(obs["hhi"]))
    syndicate_hhi = {s: float(np.median(values)) for s, values in observed_hhi.items()}
    overall_hhi = float(np.median(H))
    R_missing = np.array([row["size_proxy"] for row in unavailable], float)
    H_missing = np.array([
        (float(row["observation"]["hhi"])
         if row["observation"] and row["observation"].get("hhi") is not None
         else syndicate_hhi.get(row["syndicate"], overall_hhi))
        for row in unavailable
    ], float)
    year_missing = np.array([row["year"] for row in unavailable], int)
    q = (np.arange(len(unavailable)) + 0.5) / len(unavailable)
    effective_size = (R_missing / REF) * (1.0 / H_missing) ** g0
    sigma_missing = np.sqrt(
        su0 ** 2 + sd0 ** 2 * effective_size ** (2.0 * (k0 - 1.0))
    )
    base_t = stats.t.ppf(q, df=nu0)

    stress = {
        "n_pseudo": len(unavailable),
        "records": [row["file"] for row in unavailable],
        "size_m": {
            "min": float(R_missing.min()),
            "max": float(R_missing.max()),
            "median": float(np.median(R_missing)),
        },
        "hhi_imputation": (
            "record HHI where available, otherwise same-syndicate median, otherwise "
            "working-sample median"
        ),
        "placement": "equally spaced Student-t quantiles scaled by c*sigma(R,H)",
        "interpretation": (
            "one-direction sensitivity for eligible unavailable outcomes; structural and "
            "scientific exclusions are not appended; not a bound"
        ),
        "by_c": {},
    }
    for c in C_GRID:
        S_aug = np.concatenate([S, c * sigma_missing * base_t])
        R_aug = np.concatenate([R, R_missing])
        H_aug = np.concatenate([H, H_missing])
        year_aug = np.concatenate([year, year_missing])
        ritc_aug = np.concatenate([ritc, np.zeros(len(unavailable))])
        years_aug = np.sort(np.unique(year_aug))
        yidx_aug = np.searchsorted(years_aug, year_aug)
        stress["by_c"][str(c)] = fit(
            S_aug, R_aug, H_aug, yidx_aug, len(years_aug), ritc_aug,
            f"eligible unavailable x{c:g}",
        )
    result["eligible_outcome_stress"] = stress
    OUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    main()
