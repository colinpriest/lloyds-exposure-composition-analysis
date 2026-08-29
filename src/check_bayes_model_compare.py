"""Convert the remaining frequentist model comparisons to Bayesian summaries.

Three comparisons in the manuscript were still reported as an ELPD difference with a
standard error, which is out of keeping with a Bayesian paper and, worse, treats the
several years contributed by one syndicate as independent:

  systemic    m1 (directional reporting-year shock) vs m0 (scale shock only)
  size-loaded m3 (directional MEAN loads on effective size) vs m1 (uniform mean)
  het-scale   m4 (SCALE shock loads on effective size) vs h0 (uniform scale)

All three source scripts fit with log_likelihood retained, so pointwise LOO
contributions are available. For each contrast we take the pointwise elpd_loo
difference, sum it WITHIN syndicate, then place Dirichlet(1,...,1) weights on the
syndicate totals -- the same Bayesian bootstrap already used for the pooling and
floor comparisons. That gives a posterior for the population ELPD difference and a
direct P(model A predicts better), with no normal approximation and no independence
assumption across a syndicate's years.

Writes check_bayes_model_compare_results.json.
Usage:  python check_bayes_model_compare.py
"""
import io, json
from pathlib import Path
import numpy as np
import arviz as az

import calibrate_dispersion_systemic as SYS
import calibrate_dispersion_sizeloaded as SZL
import calibrate_dispersion_hetscale as HET

SD = Path(__file__).resolve().parent.parent
OUT = SD / "results" / "check_bayes_model_compare_results.json"
BB, SEED = 20000, 42


def syndicates():
    """Syndicate id per observation, on exactly the filter load_sample() uses."""
    d = json.load(io.open(SYS.RESULTS, encoding="utf-8"))
    return np.array([o["syndicate"] for o in d["observations"]
                     if o.get("s_raw_a") is not None
                     and o.get("opening_reserves_gbp_m")
                     and o.get("hhi") is not None])


def pointwise(idata):
    return np.asarray(az.loo(idata, pointwise=True).loo_i.values, float)


def bb(e_a, e_b, syn, label):
    d = np.asarray(e_a) - np.asarray(e_b)
    ok = np.isfinite(d)
    tot = {}
    for di, sj in zip(d[ok], np.asarray(syn)[ok]):
        tot[sj] = tot.get(sj, 0.0) + di
    v = np.array(list(tot.values()), float)
    rng = np.random.default_rng(SEED)
    draws = len(v) * (rng.dirichlet(np.ones(len(v)), size=BB) @ v)
    rec = {"contrast": label,
           "delta_ELPD": float(d[ok].sum()),
           "n_obs": int(ok.sum()), "n_syndicates": int(len(v)),
           "bb_mean": float(draws.mean()),
           "bb_2.5": float(np.percentile(draws, 2.5)),
           "bb_97.5": float(np.percentile(draws, 97.5)),
           "P_first_better": float((draws > 0).mean()),
           "SE_plain_for_reference": float(np.sqrt(ok.sum()) * d[ok].std(ddof=1))}
    print("  %-38s dELPD %+8.2f   95%% [%+7.2f, %+7.2f]   P=%.3f"
          % (label, rec["delta_ELPD"], rec["bb_2.5"], rec["bb_97.5"],
             rec["P_first_better"]))
    return rec


def main():
    S, R, HHI, yr, key, W, gpw = SYS.load_sample()
    syn = syndicates()
    assert len(syn) == len(S), "syndicate vector does not match the sample"
    ritc = SYS.ritc_flag(key).astype(float)
    logR = np.log(R / SYS.REFERENCE_SIZE)
    logH = np.log(HHI)
    years = np.sort(np.unique(yr)); yidx = np.searchsorted(years, yr); n_y = len(years)
    print(f"n={len(S)}  syndicates={len(set(syn))}  years={n_y}")

    res = {"n": int(len(S)), "n_syndicates": int(len(set(syn))), "seed": SEED,
           "bootstrap_draws": BB,
           "method": ("pointwise elpd_loo differences summed within syndicate, then "
                      "Dirichlet(1,...,1) weights on the syndicate totals"),
           "contrasts": {}}

    print("\nsystemic: directional reporting-year shock")
    m0 = SYS.build_and_fit("m0", S, logR, logH, yidx, n_y, ritc)
    m1 = SYS.build_and_fit("m1", S, logR, logH, yidx, n_y, ritc)
    res["contrasts"]["systemic_m1_vs_m0"] = bb(
        pointwise(m1), pointwise(m0), syn, "m1 directional shock vs m0 scale-only")
    del m0, m1

    print("\nsize-loaded directional mean")
    z1 = SZL.build_and_fit("m1", S, logR, logH, yidx, n_y, ritc)
    z3 = SZL.build_and_fit("m3", S, logR, logH, yidx, n_y, ritc)
    res["contrasts"]["sizeloaded_m3_vs_m1"] = bb(
        pointwise(z3), pointwise(z1), syn, "m3 size-loaded mean vs m1 uniform")
    del z1, z3

    print("\nsize-loaded scale shock")
    h0 = HET.build_and_fit("h0", S, logR, logH, yidx, n_y, ritc)
    h4 = HET.build_and_fit("m4", S, logR, logH, yidx, n_y, ritc)
    res["contrasts"]["hetscale_m4_vs_h0"] = bb(
        pointwise(h4), pointwise(h0), syn, "m4 size-loaded scale vs h0 uniform")

    OUT.write_text(json.dumps(res, indent=2), encoding="utf-8")
    print(f"\nWrote {OUT}")


if __name__ == "__main__":
    main()
