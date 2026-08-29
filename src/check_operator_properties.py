"""What the transfer operator actually does to a donor's location, as a test not a claim.

The manuscript acquired the sentence "the operator transfers spread and deliberately
not location". That is false, and the paper's own Section 3 derives why: Equation (7)
rescales the RAW severity, so a donor carrying a persistent level alpha_i contributes
lambda*alpha_i to the transferred value. The false sentence was written into a results
section without being checked against the equation three sections earlier, and no
check could catch it because the operator's behaviour existed only as prose.

This turns the four properties the manuscript relies on into assertions that run:

  1. For a clean donor the operator is exactly the scale ratio, sigma_q / sigma_i.
  2. Location is TRANSFERRED AND SCALED, not removed: adding a constant a to a clean
     donor's severity moves the transferred value by exactly (sigma_q/sigma_i) * a.
  3. For an RITC donor the quantile transform is not the identity, so the operator is
     not a pure rescaling there.
  4. De-meaning is the remedy: subtracting alpha_i before standardising removes the
     donor's level from the transferred value, to numerical tolerance.

It then answers the question the manuscript had been answering badly. "The centre is
small relative to the 99.5% stress" compares a mean with a quantile and settles
nothing about the tail. So the stresses are recomputed with donor location removed,
under BOTH estimators -- the raw within-syndicate mean and the partially pooled
intercept the manuscript recommends -- and the differences reported directly.

Any future claim about what the operator does to location should be checked here
first. Run: python check_operator_properties.py
"""
import io
import json
import re

import numpy as np

from adopted_model import SD, REFERENCE_SIZE, RITC_SCAN
from dispersion_mle import deritc_z, sigma

OUT = SD / "results" / "check_operator_properties_results.json"
RANEF = SD / "results" / "check_syndicate_random_effect_results.json"
TARGET = (500.0, 0.17)      # Vignette 1 target: 500m of reserves, HHI 0.17
TOL = 1e-10


def load_vignette_pool():
    """The 789 capital-eligible donors the vignettes transfer, not the 790-row fit.

    The sensitivity below is about the stresses the paper reports, and those are
    computed on the donor pool in distortion_tool.html -- the same pool
    vignette_uncertainty.py loads. The calibration sample carries one extra
    syndicate-year (syndicate 2015, reporting year 2014) that is excluded from the
    donor pool by the capital-eligibility guard, so using it moved the de-meaned
    V1 figures by a thousandth. Load the pool that the numbers belong to.
    """
    html = (SD / "distortion_tool.html").read_text(encoding="utf-8")
    m = re.search(r"const EMBEDDED_DATA = (\{.*?\});\s*\n", html, re.S)
    donors = json.loads(m.group(1))["donors"]
    S = np.array([d["s_raw_a"] for d in donors], float)
    R = np.array([d["opening_reserves_gbp_m"] for d in donors], float)
    H = np.array([d["hhi"] for d in donors], float)
    syn = np.array([d["syndicate"] for d in donors])
    key = np.array(["%s_%s" % (d["syndicate"], d["year"]) for d in donors])
    occ = {k for k, v in json.load(io.open(RITC_SCAN, encoding="utf-8")).items()
           if v.get("ritc_occurred")}
    ritc = np.array([k in occ for k in key]).astype(float)
    return S, R, H, syn, ritc


def headline_params():
    d = json.load(io.open(SD / "model" / "dispersion_calibration_ritc.json",
                          encoding="utf-8"))
    return {k: d[k] for k in ("k", "gamma", "sd_undiv", "sd_div",
                              "nu_clean", "nu_ritc")}


def transfer(S, R, H, ritc, mp, tgt):
    """Equation (7), exactly as dispersion_mle.transfer_var applies it."""
    sig_i = sigma(R, H, mp["k"], mp["gamma"], mp["sd_undiv"], mp["sd_div"])
    sig_q = sigma(np.array([tgt[0]]), np.array([tgt[1]]),
                  mp["k"], mp["gamma"], mp["sd_undiv"], mp["sd_div"])[0]
    z = deritc_z(S / sig_i, ritc, mp["nu_clean"], mp["nu_ritc"])
    return z * sig_q, sig_i, sig_q


def main():
    S, R, H, syn, ritc = load_vignette_pool()
    mp = headline_params()
    res = {"n": int(len(S)), "n_ritc": int(ritc.sum()), "target": list(TARGET),
           "pool": ("the 789 capital-eligible donors from distortion_tool.html, as "
                    "used by the vignettes and vignette_uncertainty.py"),
           "evaluated_at": ("posterior-mean operator parameters and posterior-mean "
                            "syndicate intercepts; parameter uncertainty is NOT "
                            "propagated here, so these are point sensitivities"),
           "params": mp, "properties": {}}

    base, sig_i, sig_q = transfer(S, R, H, ritc, mp, TARGET)
    ratio = sig_q / sig_i
    clean = ritc == 0

    # 1. clean donors: the operator is exactly the scale ratio
    err1 = float(np.max(np.abs(base[clean] - ratio[clean] * S[clean])))
    res["properties"]["clean_donor_is_scale_ratio"] = {
        "max_abs_error": err1, "holds": bool(err1 < TOL),
        "n_checked": int(clean.sum())}

    # 2. location is transferred and scaled, NOT removed
    a = 0.05
    shifted, _, _ = transfer(S + a, R, H, ritc, mp, TARGET)
    moved = shifted[clean] - base[clean]
    expected = ratio[clean] * a
    err2 = float(np.max(np.abs(moved - expected)))
    res["properties"]["location_is_transferred_and_scaled"] = {
        "constant_added": a,
        "max_abs_error_vs_scaled_constant": err2,
        "holds": bool(err2 < TOL),
        "mean_transferred_shift": float(moved.mean()),
        "note": ("adding a to a clean donor moves the transferred value by "
                 "(sigma_q/sigma_i)*a; the operator does not remove location")}

    # 3. RITC donors are not a pure rescaling, and their location is NOT separable
    #
    # For a clean donor the quantile map is the identity and lambda*alpha_i falls out
    # of the algebra. For an RITC donor Equation (7) applies
    # F^-1_{nu_clean}(F_{nu_RITC}(.)), which is nonlinear, so the level is carried
    # through the map but cannot be written as lambda*alpha_i. The manuscript stated
    # the clean algebra without that qualification; these numbers are what it costs.
    if ritc.sum():
        dev = float(np.max(np.abs(base[~clean] - ratio[~clean] * S[~clean])))
        moved_r = shifted[~clean] - base[~clean]
        linear_r = ratio[~clean] * a
        res["properties"]["ritc_donor_is_not_pure_rescaling"] = {
            "max_abs_deviation_from_scale_ratio": dev,
            "holds": bool(dev > 1e-6), "n_checked": int((~clean).sum())}
        res["properties"]["ritc_location_is_not_separable"] = {
            "constant_added": a,
            "shift_min": float(moved_r.min()), "shift_max": float(moved_r.max()),
            "shift_median": float(np.median(moved_r)),
            "linear_prediction_median": float(np.median(linear_r)),
            "max_abs_discrepancy": float(np.max(np.abs(moved_r - linear_r))),
            "holds": bool(np.max(np.abs(moved_r - linear_r)) > 1e-6),
            "note": ("adding a to an RITC donor does NOT move the transferred value "
                     "by (sigma_q/sigma_i)*a; the rank map is nonlinear")}

    # 4. de-meaning removes the level, under BOTH estimators
    #
    # Two estimators of a syndicate's level exist and they are not interchangeable.
    # The raw within-syndicate sample mean is unshrunk, so for a syndicate with two or
    # three observations it absorbs noise as well as level and over-corrects. The
    # partially pooled posterior-mean intercept from the random-effect fit is what the
    # manuscript actually recommends. An earlier version of this script quoted the raw
    # estimator while the manuscript recommended the pooled one, without either saying
    # so -- and, as the tail figures below show, they do not give the same answer.
    raw = np.zeros_like(S)
    for sy in np.unique(syn):
        m = syn == sy
        raw[m] = S[m].mean()

    ah = json.load(io.open(RANEF, encoding="utf-8"))["shrunken_alpha"]["by_syndicate"]
    pooled = np.array([ah[str(sy)] for sy in syn], float)

    demeaned = {}
    for tag, a in (("raw_syndicate_mean", raw), ("partially_pooled", pooled)):
        d, _, _ = transfer(S - a, R, H, ritc, mp, TARGET)
        demeaned[tag] = (d, a)
    d_raw = demeaned["raw_syndicate_mean"][0]

    err4 = float(np.max(np.abs((base[clean] - d_raw[clean])
                               - ratio[clean] * raw[clean])))
    res["properties"]["demeaning_removes_the_level"] = {
        "max_abs_error": err4, "holds": bool(err4 < TOL),
        "estimator_checked": "raw_syndicate_mean",
        "note": "subtracting alpha_i before standardising removes lambda*alpha_i"}

    res["transferred_library_centre"] = {
        "estimator": "identified per row; the operator as implemented does no de-meaning",
        "as_implemented": {"mean": float(base.mean()),
                           "median": float(np.median(base))}}
    for tag, (d, _) in demeaned.items():
        res["transferred_library_centre"][tag] = {
            "mean": float(d.mean()), "median": float(np.median(d))}

    # --- what de-meaning would do to the numbers the paper actually reports -----
    #
    # The manuscript argued the tail is dispersion-driven by comparing a transferred
    # MEAN of +0.020 with a 99.5% quantile of 0.393. A mean cannot bound a quantile;
    # that comparison establishes nothing about the tail. Recompute the stresses
    # themselves under each estimator and report the difference.
    t2 = json.load(io.open(SD / "vignettes/vignette-2/target_transition.json",
                           encoding="utf-8"))
    v2o = (float(t2["old_reserve_size"]), float(t2["old_hhi"]))
    v2n = (float(t2["new_reserve_size"]), float(t2["new_hhi"]))

    def stresses(Sv):
        v1, _, _ = transfer(Sv, R, H, ritc, mp, TARGET)
        old, _, _ = transfer(Sv, R, H, ritc, mp, v2o)
        new, _, _ = transfer(Sv, R, H, ritc, mp, v2n)
        return (float(np.percentile(v1, 99.5, method="linear")),
                float(np.percentile(new, 99.5, method="linear")
                      - np.percentile(old, 99.5, method="linear")))

    base_v1, base_v2 = stresses(S)
    res["tail_sensitivity_to_donor_location"] = {
        "note": ("what the operator's stresses become if donor location is removed "
                 "before standardising; the operator itself is unchanged"),
        "as_implemented": {"V1_VaR995": base_v1, "V2_change995": base_v2}}
    for tag, (_, a) in demeaned.items():
        v1, v2 = stresses(S - a)
        res["tail_sensitivity_to_donor_location"][tag] = {
            "V1_VaR995": v1, "V2_change995": v2,
            "V1_relative_change": (v1 - base_v1) / base_v1,
            "V2_absolute_change": v2 - base_v2}

    OUT.write_text(json.dumps(res, indent=2), encoding="utf-8")
    print("operator properties, at the published posterior means:")
    for name, p in res["properties"].items():
        print("  %-38s %s" % (name, "holds" if p["holds"] else "*** FAILS"))
    c = res["transferred_library_centre"]
    print("\ntransferred library centre:")
    for tag in ("as_implemented", "raw_syndicate_mean", "partially_pooled"):
        print("  %-20s mean %+.4f  median %+.4f"
              % (tag, c[tag]["mean"], c[tag]["median"]))
    r = res["properties"].get("ritc_location_is_not_separable")
    if r:
        print("\nRITC donors, adding %.2f to the severity:" % r["constant_added"])
        print("  transferred shift ranges %.4f to %.4f, median %.4f"
              % (r["shift_min"], r["shift_max"], r["shift_median"]))
        print("  linear prediction would be %.4f; max discrepancy %.4f"
              % (r["linear_prediction_median"], r["max_abs_discrepancy"]))
    t = res["tail_sensitivity_to_donor_location"]
    print("\ntail sensitivity to donor location:")
    print("  %-20s V1 VaR99.5 %.3f   V2 change %+.3f" %
          ("as_implemented", t["as_implemented"]["V1_VaR995"],
           t["as_implemented"]["V2_change995"]))
    for tag in ("raw_syndicate_mean", "partially_pooled"):
        r = t[tag]
        print("  %-20s V1 VaR99.5 %.3f   V2 change %+.3f   (V1 %+.1f%%)"
              % (tag, r["V1_VaR995"], r["V2_change995"],
                 100.0 * r["V1_relative_change"]))
    print("written to", OUT)
    if not all(p["holds"] for p in res["properties"].values()):
        raise SystemExit("*** an operator property does not hold")


if __name__ == "__main__":
    main()
