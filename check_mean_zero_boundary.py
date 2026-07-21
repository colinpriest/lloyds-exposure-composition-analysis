"""Check 6 (referee): mean-zero boundary for persistent adverse development.

Bounds how much fixing mu=0 could understate stress where development is persistently
adverse.
  (a) within-syndicate AR(1) coefficient of S (syndicates with >=4 obs): pooled estimate.
  (b) share of syndicates whose posterior-mean development is credibly positive (adverse),
      via a syndicate random-intercept on S.
  (c) for the most-persistent decile, the implied one-year mean contribution as a fraction
      of sigma (the model's dispersion scale).

Writes check_mean_zero_boundary_results.json.
Usage:  python check_mean_zero_boundary.py
"""
import io, json, sys
from pathlib import Path
import numpy as np

SD = Path(__file__).resolve().parent
OUT = SD / "results" / "check_mean_zero_boundary_results.json"
CALIB = SD / "model" / "dispersion_calibration_ritc.json"
HLO, HCE = 0.01, 1.0


def load():
    d = json.load(io.open(SD / "model" / "exposure_results.json", encoding="utf-8"))
    recs = [o for o in d["observations"]
            if o.get("s_raw_a") is not None and o.get("opening_reserves_gbp_m")
            and o.get("hhi") is not None]
    S = np.array([o["s_raw_a"] for o in recs], float)
    R = np.array([o["opening_reserves_gbp_m"] for o in recs], float)
    H = np.clip(np.array([o["hhi"] for o in recs], float), HLO, HCE)
    syn = np.array([o["syndicate"] for o in recs])
    yr = np.array([o["year"] for o in recs])
    return S, R, H, syn, yr


def ar1_within(S, syn, yr, min_obs=4):
    """Pooled within-syndicate AR(1): regress S_t on S_{t-1} within each syndicate
    (consecutive years), de-meaned per syndicate. Returns pooled slope + per-synd."""
    xs, ys, per = [], [], {}
    for s in set(syn):
        m = syn == s
        if m.sum() < min_obs:
            continue
        yy, ss = yr[m], S[m]
        o = np.argsort(yy); yy, ss = yy[o], ss[o]
        mu = ss.mean()
        pairs = [(ss[i] - mu, ss[i + 1] - mu) for i in range(len(ss) - 1)
                 if yy[i + 1] == yy[i] + 1]
        if len(pairs) >= 2:
            x = np.array([p[0] for p in pairs]); y = np.array([p[1] for p in pairs])
            xs.append(x); ys.append(y)
            if (x ** 2).sum() > 0:
                per[int(s)] = float((x * y).sum() / (x ** 2).sum())
    X = np.concatenate(xs); Y = np.concatenate(ys)
    pooled = float((X * Y).sum() / (X ** 2).sum())
    # block bootstrap over syndicates for a CI
    rng = np.random.default_rng(42)
    keys = list(per.keys())
    boots = []
    xs_map = dict(zip([k for k in per], xs)) if False else None
    return pooled, per, len(keys)


def credibly_positive_share(S, syn, min_obs=3, n_draw=4000):
    """Bayesian normal random-intercept on S: share of syndicates whose intercept
    (mu_s) 95% interval is entirely > 0. Conjugate normal-normal per syndicate with a
    pooled hyper-prior estimated by moments (empirical Bayes)."""
    groups = [s for s in set(syn) if (syn == s).sum() >= min_obs]
    means = np.array([S[syn == s].mean() for s in groups])
    ns = np.array([(syn == s).sum() for s in groups])
    within_var = np.array([S[syn == s].var(ddof=1) for s in groups])
    sigma2 = np.nanmean(within_var)
    grand = means.mean()
    tau2 = max(0.0, means.var(ddof=1) - sigma2 / np.mean(ns))
    # posterior per syndicate: precision-weighted
    post_var = 1.0 / (1.0 / tau2 + ns / sigma2) if tau2 > 0 else sigma2 / ns
    post_mean = post_var * (grand / tau2 + ns * means / sigma2) if tau2 > 0 else means
    lo = post_mean - 1.96 * np.sqrt(post_var)
    hi = post_mean + 1.96 * np.sqrt(post_var)
    cred_pos = int((lo > 0).sum())
    cred_neg = int((hi < 0).sum())
    return {"n_syndicates": len(groups), "credibly_positive": cred_pos,
            "credibly_negative": cred_neg,
            "share_credibly_positive": float(cred_pos / len(groups)),
            "share_credibly_negative": float(cred_neg / len(groups)),
            "tau2_between": float(tau2), "sigma2_within": float(sigma2),
            "grand_mean_S": float(grand)}


def main():
    S, R, H, syn, yr = load()
    c = json.load(io.open(CALIB, encoding="utf-8"))

    pooled_ar1, per_ar1, n_ar1 = ar1_within(S, syn, yr, min_obs=4)
    cred = credibly_positive_share(S, syn, min_obs=3)

    # (c) most-persistent decile: syndicates ranked by AR(1); their mean S vs sigma scale
    items = sorted(per_ar1.items(), key=lambda kv: -kv[1])
    n_dec = max(1, len(items) // 10)
    top = [s for s, _ in items[:n_dec]]
    m = np.isin(syn, top)
    Hc = np.clip(H, HLO, HCE)
    log_reff = np.log(np.maximum(R, 1e-9) / c["reference_size"]) - c["gamma"] * np.log(Hc)
    sigma = np.sqrt(c["sd_undiv"] ** 2 + c["sd_div"] ** 2
                    * np.exp(2.0 * (c["k"] - 1.0) * log_reff))
    mean_S_top = float(S[m].mean())
    sigma_top = float(sigma[m].mean())
    implied_frac = mean_S_top / sigma_top if sigma_top else np.nan

    out = {
        "a_ar1": {"pooled_within_syndicate_ar1": pooled_ar1,
                  "n_syndicates_ge4obs": n_ar1,
                  "per_syndicate_ar1_median": float(np.median(list(per_ar1.values()))),
                  "per_syndicate_ar1_iqr": [float(np.percentile(list(per_ar1.values()), 25)),
                                            float(np.percentile(list(per_ar1.values()), 75))]},
        "b_credibly_positive": cred,
        "c_most_persistent_decile": {
            "n_syndicates": n_dec, "syndicates": [int(s) for s in top],
            "mean_S": mean_S_top, "mean_sigma": sigma_top,
            "implied_one_year_mean_as_fraction_of_sigma": float(implied_frac)},
        "sigma_source": "dispersion_calibration_ritc.json posterior means",
    }
    OUT.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"Wrote {OUT}")
    print(f"(a) pooled within-syndicate AR(1) = {pooled_ar1:+.3f}  "
          f"(median per-synd {out['a_ar1']['per_syndicate_ar1_median']:+.3f}, {n_ar1} syndicates >=4 obs)")
    print(f"(b) credibly-positive syndicates: {cred['credibly_positive']}/{cred['n_syndicates']} "
          f"({100*cred['share_credibly_positive']:.1f}%); credibly-negative "
          f"{cred['credibly_negative']} ({100*cred['share_credibly_negative']:.1f}%)")
    print(f"(c) most-persistent decile ({n_dec} synd): mean S={mean_S_top:+.4f}, "
          f"mean sigma={sigma_top:.4f}, mean/sigma = {implied_frac:+.3f}")


if __name__ == "__main__":
    sys.exit(main())
