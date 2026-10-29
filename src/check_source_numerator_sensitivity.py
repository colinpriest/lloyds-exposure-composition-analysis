"""Source-assumption sensitivities for two numerator observations and vignette donors.

Refits the adopted gamma-zero model after excluding 3330/2017, excluding 1274/2016,
excluding both, or replacing the latter's derived USD numerator with two alternatives
available from the filings. The alternatives are scenarios, not validated corrections.
Uses the existing fit and vignette implementations, and independently reconstructs
the baseline vignette centres before comparing any refit. Full posterior draws go
only to the explicit output directory. Run in an isolated analysis checkout:

  python src/check_source_numerator_sensitivity.py --output-dir PATH

The JSON in that folder records the exact source/input fingerprints and convergence.
This script does not run cross-validation or generate uncertainty intervals for the
vignette point estimates. It refuses to overwrite an existing output directory.
"""
import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

os.environ.setdefault("LLOYDS_EXTRACTION_OFFLINE", "1")
os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")

ROOT = Path(__file__).resolve().parent.parent
EXCLUSIONS = {"exclude_3330_2017": ("3330_2017",),
              "exclude_1274_2016": ("1274_2016",),
              "exclude_both": ("3330_2017", "1274_2016")}
ALTERNATIVES = {"printed_2016_table": 57.503,
                "prior_cell_without_retranslation": 19.871}
SOURCE_KEY = "1274_2016"
SOURCE_BASE_USD_M = 22.6943
SAMPLER = {"chains": 4, "tune": 1500, "draws": 1500,
           "target_accept": 0.98, "seed": 42}
INPUTS = ("model/exposure_results.json", "data/mature_cohort_figures.json",
          "model/dispersion_posterior_draws_ritc.npz", "src/adopted_model.py",
          "src/check_cohort_scope.py", "src/refit_vignettes.py",
          "src/vignette_uncertainty.py", "src/transfer_operator.py",
          "results/check_gamma0_vignette_results.json")


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def row_keys(syndicates, years):
    return ["%s_%s" % (s, y) for s, y in zip(syndicates, years)]


def case_sample(S, R, H, years, syndicates, ritc, label):
    """Return an independent fit sample with exactly the intended change."""
    import numpy as np
    arrays = tuple(np.asarray(x) for x in (S, R, H, years, syndicates, ritc))
    if len({len(x) for x in arrays}) != 1:
        raise ValueError("sample arrays have different lengths")
    keys = row_keys(arrays[4], arrays[3])
    if len(set(keys)) != len(keys):
        raise ValueError("sample contains duplicate keys")
    if label in EXCLUSIONS:
        missing = set(EXCLUSIONS[label]) - set(keys)
        if missing:
            raise ValueError("exclusion keys absent: %s" % sorted(missing))
        mask = np.array([k not in EXCLUSIONS[label] for k in keys], bool)
        return tuple(x[mask].copy() for x in arrays), sorted(EXCLUSIONS[label])
    if label not in ALTERNATIVES:
        raise ValueError("unknown case %s" % label)
    if SOURCE_KEY not in keys:
        raise ValueError("alternative source key absent")
    changed = [x.copy() for x in arrays]
    i = keys.index(SOURCE_KEY)
    changed[0][i] *= ALTERNATIVES[label] / SOURCE_BASE_USD_M
    return tuple(changed), []


def run(outdir):
    import numpy as np
    import arviz as az
    import adopted_model as am
    import refit_vignettes as rv
    from check_cohort_scope import fit
    from pool_quantile import var_q
    from vignette_uncertainty import load_targets, transfer
    import transfer_operator as op

    outdir = Path(outdir).resolve()
    outdir.mkdir(parents=True, exist_ok=False)
    state = subprocess.run(["git", "status", "--porcelain", "--untracked-files=all"],
                           cwd=ROOT, text=True, capture_output=True, check=True).stdout
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True,
                          capture_output=True, check=True).stdout.strip()
    register = json.loads((ROOT / "data/mature_cohort_figures.json").read_text(encoding="utf-8"))
    if register[SOURCE_KEY]["figure_m"] != SOURCE_BASE_USD_M:
        raise SystemExit("1274/2016's adopted numerator changed; recalculate the alternatives")
    sample = tuple(np.asarray(x) for x in am.load_sample())
    if len(sample[0]) != 632:
        raise SystemExit("unexpected headline sample size; review this analysis")
    pool, pool_ritc, pool_keys = rv.pool_for()
    sample_keys = row_keys(sample[4], sample[3])
    rv.check_pool_is_the_fit_sample(pool, pool_keys, sample_keys, sample[0], sample[1])
    published, head_draws, cfg = rv.headline_block(rv.headline_record())
    baseline = rv.centre_only(head_draws, pool, pool_ritc, cfg)
    if baseline != published["centre"]:
        raise SystemExit("headline baseline does not reproduce the published centre")
    result = {
        "question": "Effect of source-derived numerator assumptions in 3330/2017 and 1274/2016",
        "code_commit": head, "working_tree_dirty": bool(state),
        "working_tree_status": state.splitlines(),
        "producer_sha256": digest(__file__),
        "input_sha256": {rel: digest(ROOT / rel) for rel in INPUTS},
        "sampler": SAMPLER,
        "baseline_n": len(sample[0]), "baseline_centre": baseline,
        "baseline_exactly_reproduces_published_centre": True,
        "source_usd_m": SOURCE_BASE_USD_M,
        "interpretation": ("The alternative figures are source-based assumptions, not demonstrated true values. "
                           "Vignette figures are equal-donor empirical inverse-CDF points at posterior-mean "
                           "parameters, not posterior intervals. CV is not refitted here."),
        "cases": {},
    }
    for label in (*EXCLUSIONS, *ALTERNATIVES):
        changed, excluded = case_sample(*sample, label)
        S, R, H, years, synd, ritc = changed
        print("START", label, "n", len(S), flush=True)
        params, idata = fit(S, R, H, years, ritc)
        summary = az.summary(idata, hdi_prob=.95, round_to="none")
        diag = {"divergences": int(idata.sample_stats.diverging.sum()),
                "max_rhat": float(summary.r_hat.max()),
                "min_ess_bulk": float(summary.ess_bulk.min()),
                "min_ess_tail": float(summary.ess_tail.min())}
        if diag["divergences"] or diag["max_rhat"] > 1.01:
            raise SystemExit("nonconverged fit for %s: %s" % (label, diag))
        saved = outdir / (label + ".npz")
        np.savez_compressed(saved,
                            **{str(k): v.values for k, v in idata.posterior.data_vars.items()},
                            **{"sample_stats__" + str(k): v.values
                               for k, v in idata.sample_stats.data_vars.items()})
        draws = rv.operator_draws(idata)
        keep = np.array([str(k) not in excluded for k in pool_keys], bool)
        changed_pool = [v[keep].copy() for v in pool]
        changed_ritc = pool_ritc[keep]
        if label in ALTERNATIVES:
            i = row_keys(changed_pool[3], changed_pool[4]).index(SOURCE_KEY)
            changed_pool[0][i] = round(float(S[sample_keys.index(SOURCE_KEY)]), 8)
        changed_pool = tuple(changed_pool)
        changed_keys = row_keys(changed_pool[3], changed_pool[4])
        fit_keys = row_keys(synd, years)
        rv.check_pool_is_the_fit_sample(changed_pool, changed_keys, fit_keys, S, R)
        pool_only = rv.centre_only(head_draws, changed_pool, changed_ritc, cfg)
        fit_only = rv.centre_only(draws, pool, pool_ritc, cfg)
        combined = rv.centre_only(draws, changed_pool, changed_ritc, cfg)
        th = op.params(draws, op.HEADLINE)
        means = {k: float(np.mean(v)) for k, v in th.items()}
        mapped = transfer(changed_pool[0], changed_pool[1], changed_pool[2],
                          load_targets()[0], means, cfg, changed_ritc)
        thresholds = {}
        for alpha in (0.99, 0.995):
            q = var_q(mapped, alpha)
            thresholds[str(alpha)] = {
                "value": float(q),
                "donors_at_threshold": [changed_keys[i] for i in np.flatnonzero(mapped == q)],
                "rank_from_top": rv.rank_from_top(len(mapped), alpha)}
        result["cases"][label] = {
            "excluded": excluded, "alternative_figure_usd_m": ALTERNATIVES.get(label),
            "n_fit_and_donors": len(S), "fit": params, "diagnostics": diag,
            "posterior_sha256": digest(saved),
            "pool_only": pool_only, "fit_only": fit_only, "refit_and_rebuilt_pool": combined,
            "relative_to_baseline": rv.relative(combined, baseline), "V1_thresholds": thresholds,
        }
        (outdir / "results.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        print("DONE", label, "k", params["k"]["mean"], "diagnostics", diag, flush=True)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True,
                        help="New directory for fitted draws and summary; must not exist")
    args = parser.parse_args()
    run(args.output_dir)


if __name__ == "__main__":
    main()
