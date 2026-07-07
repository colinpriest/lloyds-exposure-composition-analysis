"""Uncertainty intervals for the vignette VaRs (bootstrap + posterior).

Implements the spec "uncertainty intervals for the vignette VaRs": replaces the
point-estimate VaRs in the two worked vignettes with 95% intervals that propagate BOTH
donor-sampling uncertainty (cluster bootstrap) AND parameter uncertainty (posterior draws
of the operator parameters), plus intervals on the headline VaR *change*.

Sources (all build artifacts of the main pipeline):
  - donor pool (market capital-analysis donors)          <- distortion_tool.html
  - posterior draws of (k, gamma, sd_undiv, sd_div, nu_clean, nu_ritc) <- dispersion_posterior_draws_ritc.npz
  - target profiles (V1; V2 old/new)                     <- vignettes/*/target_*.json

Outputs: vignette_uncertainty_results.json  (+ a printed summary and LaTeX-ready cells).

Reproducibility: seed, B, quantile definition (numpy type-7 'linear'), and clustering are
all recorded in the output. Run:  python vignette_uncertainty.py [B] [seed]
"""
import json, re, sys
from pathlib import Path
import numpy as np

try:
    from scipy import stats as _sps
except Exception:
    _sps = None

SCRIPT_DIR = Path(__file__).resolve().parent
SEED = int(sys.argv[2]) if len(sys.argv) > 2 else 20240704
B = int(sys.argv[1]) if len(sys.argv) > 1 else 4000
ALPHAS = (0.99, 0.995)
QUANTILE_METHOD = "linear"   # numpy type-7; matches the paper's empirical VaR point estimates


# ----------------------------------------------------------------------------- loading
def load_pool():
    html = (SCRIPT_DIR / "distortion_tool.html").read_text(encoding="utf-8")
    m = re.search(r"const EMBEDDED_DATA = (\{.*?\});\s*\n", html, re.S)
    donors = json.loads(m.group(1))["donors"]
    S = np.array([d["s_raw_a"] for d in donors], float)
    R = np.array([d["opening_reserves_gbp_m"] for d in donors], float)
    H = np.array([d["hhi"] for d in donors], float)
    synd = np.array([d["syndicate"] for d in donors])
    year = np.array([d["year"] for d in donors])
    return S, R, H, synd, year


def load_draws():
    """Posterior draws of the operator parameters.

    Prefers the RITC-regime draws (adds nu_clean, nu_ritc for the shape-aware operator);
    falls back to the plain draws (pure rescale, no de-RITC) if the RITC file is absent.
    """
    ritc_path = SCRIPT_DIR / "dispersion_posterior_draws_ritc.npz"
    path = ritc_path if ritc_path.exists() else (SCRIPT_DIR / "dispersion_posterior_draws.npz")
    z = np.load(path)
    keys = ["k", "gamma", "sd_undiv", "sd_div"]
    if "nu_clean" in z.files:
        keys += ["nu_clean", "nu_ritc"]
    return {k: z[k] for k in keys}, \
           float(z["reference_size"][0]), float(z["hhi_floor"][0]), float(z["hhi_ceil"][0])


def load_ritc(synd, year):
    """Per-donor RITC flag aligned to the pool, from pdf_extraction/ritc_scan.json."""
    path = SCRIPT_DIR / "pdf_extraction" / "ritc_scan.json"
    if not path.exists():
        return np.zeros(len(synd), bool)
    r = json.loads(path.read_text(encoding="utf-8"))
    occ = {k for k, v in r.items() if v.get("ritc_occurred")}
    return np.array([f"{s}_{y}" in occ for s, y in zip(synd, year)], bool)


def load_targets():
    t1 = json.loads((SCRIPT_DIR / "vignettes/vignette-1/target_profile.json").read_text())
    t2 = json.loads((SCRIPT_DIR / "vignettes/vignette-2/target_transition.json").read_text())
    v1 = (float(t1["reserve_size"]), float(t1["hhi"]))
    v2_old = (float(t2["old_reserve_size"]), float(t2["old_hhi"]))
    v2_new = (float(t2["new_reserve_size"]), float(t2["new_hhi"]))
    return v1, v2_old, v2_new


# ----------------------------------------------------------------------------- operator
def sigma_theta(R, H, k, g, su, sd, ref, hlo, hhi_ceil):
    Hc = np.clip(H, hlo, hhi_ceil)
    reff = (np.maximum(R, 1e-9) / ref) * (1.0 / Hc) ** g
    return np.sqrt(su * su + sd * sd * reff ** (2.0 * (k - 1.0)))


def var_q(arr, alpha):
    return float(np.percentile(arr, 100.0 * alpha, method=QUANTILE_METHOD))


def deritc_resid(z, th, ritc):
    """Map RITC donors' standardised residual from the RITC tail law to the clean one.

    z = S/sigma(src) is a standard Student-t(nu) draw under the model.  For RITC donors we
    rank-match through the two t-laws (PIT):  z_clean = F^-1_{nu_clean}( F_{nu_ritc}(z) ),
    which THINS the heavy RITC tail to the clean-composition tail.  Median-0-preserving.
    Clean donors (and the no-nu fallback) are returned unchanged, so this reduces exactly to
    the pure rescale when nu_src = nu_tgt.
    """
    nuc, nur = th.get("nu_clean"), th.get("nu_ritc")
    if _sps is None or nuc is None or nur is None or ritc is None or not np.any(ritc):
        return z
    z = np.array(z, float, copy=True)
    u = np.clip(_sps.t.cdf(z[ritc], df=float(nur)), 1e-12, 1.0 - 1e-12)
    z[ritc] = _sps.t.ppf(u, df=float(nuc))
    return z


def transfer(S, R, H, tgt, th, cfg, ritc=None):
    """Transfer donor severities to target (Rq,Hq) under one parameter draw th.

    Shape-aware Option-A operator:  S_adj = sigma(tgt) * deRITC( S/sigma(src) ).  The de-RITC
    step (quantile transform) only fires for RITC-flagged donors when nu_clean/nu_ritc are in
    th; otherwise this is the pure rescale S*sigma(tgt)/sigma(src).
    """
    Rq, Hq = tgt
    sq = sigma_theta(Rq, Hq, th["k"], th["gamma"], th["sd_undiv"], th["sd_div"], *cfg)
    si = sigma_theta(R, H, th["k"], th["gamma"], th["sd_undiv"], th["sd_div"], *cfg)
    z = deritc_resid(S / si, th, ritc)
    return z * sq


# ------------------------------------------------------------------- resampling schemes
def build_resampler(synd, year, scheme):
    n = len(synd)
    if scheme == "cluster":
        groups = {}
        for i, s in enumerate(synd):
            groups.setdefault(s, []).append(i)
        keys = list(groups.keys()); idx_lists = [np.array(groups[k]) for k in keys]
        def draw(rng):
            pick = rng.integers(0, len(keys), len(keys))
            return np.concatenate([idx_lists[p] for p in pick])
    elif scheme == "year":
        groups = {}
        for i, y in enumerate(year):
            groups.setdefault(int(y), []).append(i)
        keys = list(groups.keys()); idx_lists = [np.array(groups[k]) for k in keys]
        def draw(rng):
            pick = rng.integers(0, len(keys), len(keys))
            return np.concatenate([idx_lists[p] for p in pick])
    elif scheme == "iid":
        def draw(rng):
            return rng.integers(0, n, n)
    else:
        raise ValueError(scheme)
    return draw


# --------------------------------------------------------------- one replicate's stats
def ci(vals):
    a = np.asarray(vals, float)
    return {"mean": float(np.mean(a)), "sd": float(np.std(a, ddof=1)),
            "lo": float(np.percentile(a, 2.5)), "hi": float(np.percentile(a, 97.5))}


def shapley_v1(S, R, H, idx, tgt, th, cfg, ritc=None):
    """Size vs concentration Shapley of the raw->adjusted VaR99.5 change.

    Decomposition runs on the de-RITC'd standardised residual z0 so the size/conc split
    isolates the composition channels (de-RITC is a separate operator step).
    """
    Rq, Hq = tgt
    s = S[idx]; Ri = R[idx]; Hi = H[idx]
    ridx = ritc[idx] if ritc is not None else None
    def sig(Rx, Hx): return sigma_theta(Rx, Hx, th["k"], th["gamma"], th["sd_undiv"], th["sd_div"], *cfg)
    base = sig(Ri, Hi)
    z0 = deritc_resid(s / base, th, ridx)
    raw = z0 * base
    size = z0 * sig(Rq, Hi)
    conc = z0 * sig(Ri, Hq)
    full = z0 * sig(Rq, Hq)
    vr, vs, vc, vf = (var_q(raw, 0.995), var_q(size, 0.995), var_q(conc, 0.995), var_q(full, 0.995))
    se = 0.5 * ((vs - vr) + (vf - vc))
    ce = 0.5 * ((vc - vr) + (vf - vs))
    return se, ce


def shapley_v2(S, R, H, idx, old, new, th, cfg, ritc=None):
    """Size-change vs concentration-change Shapley of old->new VaR99.5 change."""
    (Ro, Ho), (Rn, Hn) = old, new
    s = S[idx]; Ri = R[idx]; Hi = H[idx]
    ridx = ritc[idx] if ritc is not None else None
    def sig(Rx, Hx): return sigma_theta(Rx, Hx, th["k"], th["gamma"], th["sd_undiv"], th["sd_div"], *cfg)
    base = sig(Ri, Hi)
    z0 = deritc_resid(s / base, th, ridx)
    oo = z0 * sig(Ro, Ho); on = z0 * sig(Ro, Hn)
    no = z0 * sig(Rn, Ho); nn = z0 * sig(Rn, Hn)
    voo, von, vno, vnn = (var_q(oo, 0.995), var_q(on, 0.995), var_q(no, 0.995), var_q(nn, 0.995))
    se = 0.5 * ((vno - voo) + (vnn - von))
    ce = 0.5 * ((von - voo) + (vnn - vno))
    return se, ce


# ------------------------------------------------------------------------------- driver
def run():
    S, R, H, synd, year = load_pool()
    draws, ref, hlo, hce = load_draws()
    ritc = load_ritc(synd, year)
    cfg = (ref, hlo, hce)
    v1, v2_old, v2_new = load_targets()
    n = len(S); ndraw = len(draws["k"])
    rng = np.random.default_rng(SEED)
    thbar = {p: float(draws[p].mean()) for p in draws}  # posterior mean

    def point(tgt=None, arr=None):
        """Centre = full pool at posterior mean."""
        if arr is None:
            arr = S if tgt is None else transfer(S, R, H, tgt, thbar, cfg)
        return arr

    schemes = {"cluster": build_resampler(synd, year, "cluster"),
               "year": build_resampler(synd, year, "year"),
               "iid": build_resampler(synd, year, "iid")}

    def combined(scheme, param_uncertainty=True, do_shapley=False):
        draw = schemes[scheme]
        acc = {"V1_raw_sd": [], "V1_raw_v99": [], "V1_raw_v995": [],
               "V1_adj_sd": [], "V1_adj_v99": [], "V1_adj_v995": [],
               "V1_d99": [], "V1_d995": [], "V1_d995_pct": [],
               "V2_old_v99": [], "V2_old_v995": [], "V2_new_v99": [], "V2_new_v995": [],
               "V2_d99": [], "V2_d995": [], "V2_d995_pct": [],
               "V1_shap_size": [], "V1_shap_conc": [], "V2_shap_size": [], "V2_shap_conc": []}
        for _ in range(B):
            idx = draw(rng)
            th = {p: draws[p][rng.integers(0, ndraw)] for p in draws} if param_uncertainty else thbar
            s = S[idx]; rr = ritc[idx]
            a1 = transfer(s, R[idx], H[idx], v1, th, cfg, rr)
            acc["V1_raw_sd"].append(np.std(s, ddof=1)); acc["V1_adj_sd"].append(np.std(a1, ddof=1))
            rr99, rr995 = var_q(s, 0.99), var_q(s, 0.995)
            aa99, aa995 = var_q(a1, 0.99), var_q(a1, 0.995)
            acc["V1_raw_v99"].append(rr99); acc["V1_raw_v995"].append(rr995)
            acc["V1_adj_v99"].append(aa99); acc["V1_adj_v995"].append(aa995)
            acc["V1_d99"].append(aa99 - rr99); acc["V1_d995"].append(aa995 - rr995)
            acc["V1_d995_pct"].append(100 * (aa995 - rr995) / abs(rr995) if rr995 else np.nan)
            ao = transfer(s, R[idx], H[idx], v2_old, th, cfg, rr)
            an = transfer(s, R[idx], H[idx], v2_new, th, cfg, rr)
            o99, o995, n99, n995 = var_q(ao, 0.99), var_q(ao, 0.995), var_q(an, 0.99), var_q(an, 0.995)
            acc["V2_old_v99"].append(o99); acc["V2_old_v995"].append(o995)
            acc["V2_new_v99"].append(n99); acc["V2_new_v995"].append(n995)
            acc["V2_d99"].append(n99 - o99); acc["V2_d995"].append(n995 - o995)
            acc["V2_d995_pct"].append(100 * (n995 - o995) / abs(o995) if o995 else np.nan)
            if do_shapley:
                se, ce = shapley_v1(S, R, H, idx, v1, th, cfg, ritc); acc["V1_shap_size"].append(se); acc["V1_shap_conc"].append(ce)
                se, ce = shapley_v2(S, R, H, idx, v2_old, v2_new, th, cfg, ritc); acc["V2_shap_size"].append(se); acc["V2_shap_conc"].append(ce)
        return acc

    prim = combined("cluster", param_uncertainty=True, do_shapley=True)

    # centres (full pool at posterior mean)
    a1c = transfer(S, R, H, v1, thbar, cfg, ritc)
    aoc = transfer(S, R, H, v2_old, thbar, cfg, ritc); anc = transfer(S, R, H, v2_new, thbar, cfg, ritc)
    centres = {
        "V1_raw": {"sd": float(np.std(S, ddof=1)), "v99": var_q(S, 0.99), "v995": var_q(S, 0.995)},
        "V1_adj": {"sd": float(np.std(a1c, ddof=1)), "v99": var_q(a1c, 0.99), "v995": var_q(a1c, 0.995)},
        "V2_old": {"v99": var_q(aoc, 0.99), "v995": var_q(aoc, 0.995)},
        "V2_new": {"v99": var_q(anc, 0.99), "v995": var_q(anc, 0.995)},
        "V1_d995": var_q(a1c, 0.995) - var_q(S, 0.995),
        "V2_d995": var_q(anc, 0.995) - var_q(aoc, 0.995),
    }

    def tailsupport(tgt):
        a = transfer(S, R, H, tgt, thbar, cfg, ritc)
        q99, q995 = var_q(a, 0.99), var_q(a, 0.995)
        return {"n": n, "n_adverse": int((a > 0).sum()),
                "n_at_or_beyond_99": int((a >= q99).sum()), "n_at_or_beyond_995": int((a >= q995).sum())}

    # robustness: alternative clusterings (combined scheme) and uncertainty decomposition
    yearb = combined("year", param_uncertainty=True, do_shapley=False)
    iidb = combined("iid", param_uncertainty=True, do_shapley=False)
    samp_only = combined("cluster", param_uncertainty=False, do_shapley=False)  # bootstrap only
    # parameter-only: full pool, vary theta
    par_only = {"V1_adj_v995": [], "V2_d995": []}
    for _ in range(B):
        th = {p: draws[p][rng.integers(0, ndraw)] for p in draws}
        a1 = transfer(S, R, H, v1, th, cfg, ritc)
        par_only["V1_adj_v995"].append(var_q(a1, 0.995))
        par_only["V2_d995"].append(var_q(transfer(S, R, H, v2_new, th, cfg, ritc), 0.995) - var_q(transfer(S, R, H, v2_old, th, cfg, ritc), 0.995))

    def width(d): return ci(d)["hi"] - ci(d)["lo"]
    decomp = {
        "V1_adj_v995": {"combined": width(prim["V1_adj_v995"]), "sampling_only": width(samp_only["V1_adj_v995"]),
                        "parameter_only": width(par_only["V1_adj_v995"])},
        "V2_d995": {"combined": width(prim["V2_d995"]), "sampling_only": width(samp_only["V2_d995"]),
                    "parameter_only": width(par_only["V2_d995"])},
    }

    # EVT (GPD/POT) robustness for VaR99.5 (appendix) — full pool, posterior mean
    def evt_var995(arr, uq=90.0):
        # Standard peaks-over-threshold return level on the FULL (signed) sample, N/Nu form —
        # matches gpd_var_uncertainty.py and bayesian_gpd.py. (A previous positive-only
        # conditioning inflated this to ~0.79/0.77; that variant is superseded.)
        if _sps is None:
            return None
        u = float(np.percentile(arr, uq))
        exc = arr[arr > u] - u
        N, Nu = len(arr), len(exc)
        if Nu < 10:
            return None
        try:
            xi, _, sc = _sps.genpareto.fit(exc, floc=0.0)
        except Exception:
            return None
        if sc <= 0 or not np.isfinite(xi):
            return None
        a = (N / Nu) * (1.0 - 0.995)
        return float(u - sc * np.log(a) if abs(xi) < 1e-6 else u + (sc / xi) * (a ** (-xi) - 1.0))
    evt = {"method": "standard full-sample POT point (90th-pctile threshold); "
                     "95% intervals in gpd_var_uncertainty.py (frequentist) and bayesian_gpd.py (Bayesian)",
           "V1_adj_v995_gpd": evt_var995(a1c), "V1_adj_v995_empirical": centres["V1_adj"]["v995"],
           "V2_new_v995_gpd": evt_var995(anc), "V2_new_v995_empirical": centres["V2_new"]["v995"]}

    d995 = np.array(prim["V1_d995"]); v2d = np.array(prim["V2_d995"])
    out = {
        "meta": {"seed": SEED, "B": B, "n_donors": n, "n_syndicates": int(len(set(synd))),
                 "n_posterior_draws": ndraw, "quantile_method": "numpy type-7 (linear)",
                 "primary_clustering": "by syndicate", "alphas": list(ALPHAS),
                 "donor_set": "market capital-analysis pool (same for V1 and V2)",
                 "n_ritc_donors": int(ritc.sum()),
                 "operator": ("shape-aware Option-A: S_adj = sigma(tgt)*deRITC(S/sigma(src)); "
                              "RITC donors' tail thinned from nu_ritc to nu_clean via PIT")
                 if ("nu_clean" in draws) else "pure rescale (no RITC regime draws found)",
                 "nu_clean_mean": float(draws["nu_clean"].mean()) if "nu_clean" in draws else None,
                 "nu_ritc_mean": float(draws["nu_ritc"].mean()) if "nu_ritc" in draws else None},
        "centres_full_pool_posterior_mean": centres,
        "vignette1": {
            "raw": {"sd": ci(prim["V1_raw_sd"]), "var99": ci(prim["V1_raw_v99"]), "var995": ci(prim["V1_raw_v995"])},
            "adjusted": {"sd": ci(prim["V1_adj_sd"]), "var99": ci(prim["V1_adj_v99"]), "var995": ci(prim["V1_adj_v995"])},
            "change_raw_to_adjusted": {
                "abs_99": ci(prim["V1_d99"]), "abs_995": ci(prim["V1_d995"]), "pct_995": ci([x for x in prim["V1_d995_pct"] if np.isfinite(x)]),
                "P_fall_995": float((d995 < 0).mean())},
            "shapley_995": {"size": ci(prim["V1_shap_size"]), "concentration": ci(prim["V1_shap_conc"])},
            "tail_support": tailsupport(v1),
        },
        "vignette2": {
            "adjusted_old": {"var99": ci(prim["V2_old_v99"]), "var995": ci(prim["V2_old_v995"])},
            "adjusted_new": {"var99": ci(prim["V2_new_v99"]), "var995": ci(prim["V2_new_v995"])},
            "change_old_to_new": {
                "abs_99": ci(prim["V2_d99"]), "abs_995": ci(prim["V2_d995"]), "pct_995": ci([x for x in prim["V2_d995_pct"] if np.isfinite(x)]),
                "P_rise_995": float((v2d > 0).mean())},
            "shapley_995": {"size_change": ci(prim["V2_shap_size"]), "concentration_change": ci(prim["V2_shap_conc"])},
            "tail_support_old": tailsupport(v2_old), "tail_support_new": tailsupport(v2_new),
        },
        "robustness": {
            "V1_adj_var995_CI_by_clustering": {"cluster_syndicate": ci(prim["V1_adj_v995"]),
                                               "year_block": ci(yearb["V1_adj_v995"]), "iid_row": ci(iidb["V1_adj_v995"])},
            "V2_change995_CI_by_clustering": {"cluster_syndicate": ci(prim["V2_d995"]),
                                              "year_block": ci(yearb["V2_d995"]), "iid_row": ci(iidb["V2_d995"])},
            "ci_width_decomposition": decomp,
            "evt_gpd_var995": evt,
        },
    }
    (SCRIPT_DIR / "vignette_uncertainty_results.json").write_text(json.dumps(out, indent=2))
    print(json.dumps(out, indent=2))

    # sanity: centres inside CIs
    def inside(c, d): return d["lo"] <= c <= d["hi"]
    checks = [
        inside(centres["V1_adj"]["v995"], out["vignette1"]["adjusted"]["var995"]),
        inside(centres["V1_raw"]["v995"], out["vignette1"]["raw"]["var995"]),
        inside(centres["V2_new"]["v995"], out["vignette2"]["adjusted_new"]["var995"]),
        inside(centres["V1_d995"], out["vignette1"]["change_raw_to_adjusted"]["abs_995"]),
        inside(centres["V2_d995"], out["vignette2"]["change_old_to_new"]["abs_995"]),
    ]
    print(f"\nACCEPTANCE — centres inside their 95% CIs: {sum(checks)}/{len(checks)} "
          f"{'PASS' if all(checks) else 'FAIL'}")


if __name__ == "__main__":
    run()
