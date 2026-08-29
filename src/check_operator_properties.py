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

Any future claim about what the operator does to location should be checked here
first. Run: python check_operator_properties.py
"""
import io
import json

import numpy as np

from adopted_model import SD, REFERENCE_SIZE, load_sample
from dispersion_mle import deritc_z, sigma

OUT = SD / "results" / "check_operator_properties_results.json"
TARGET = (500.0, 0.17)      # Vignette 1 target: 500m of reserves, HHI 0.17
TOL = 1e-10


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
    S, R, H, yr, syn, ritc = load_sample()
    mp = headline_params()
    res = {"n": int(len(S)), "n_ritc": int(ritc.sum()), "target": list(TARGET),
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

    # 3. RITC donors are not a pure rescaling
    if ritc.sum():
        dev = float(np.max(np.abs(base[~clean] - ratio[~clean] * S[~clean])))
        res["properties"]["ritc_donor_is_not_pure_rescaling"] = {
            "max_abs_deviation_from_scale_ratio": dev,
            "holds": bool(dev > 1e-6), "n_checked": int((~clean).sum())}

    # 4. de-meaning removes the level, as the appendix says it does
    alpha = np.zeros_like(S)
    for s in np.unique(syn):
        m = syn == s
        alpha[m] = S[m].mean()
    demeaned, _, _ = transfer(S - alpha, R, H, ritc, mp, TARGET)
    err4 = float(np.max(np.abs((base[clean] - demeaned[clean])
                               - ratio[clean] * alpha[clean])))
    res["properties"]["demeaning_removes_the_level"] = {
        "max_abs_error": err4, "holds": bool(err4 < TOL),
        "note": "subtracting alpha_i before standardising removes lambda*alpha_i"}

    # what the transferred library's centre actually is, with and without de-meaning
    res["transferred_library_centre"] = {
        "as_implemented_mean": float(base.mean()),
        "as_implemented_median": float(np.median(base)),
        "demeaned_mean": float(demeaned.mean()),
        "demeaned_median": float(np.median(demeaned))}

    OUT.write_text(json.dumps(res, indent=2), encoding="utf-8")
    print("operator properties, at the published posterior means:")
    for name, p in res["properties"].items():
        print("  %-38s %s" % (name, "holds" if p["holds"] else "*** FAILS"))
    c = res["transferred_library_centre"]
    print("\ntransferred library centre: mean %+.4f, median %+.4f "
          "(de-meaned: %+.4f / %+.4f)"
          % (c["as_implemented_mean"], c["as_implemented_median"],
             c["demeaned_mean"], c["demeaned_median"]))
    print("written to", OUT)
    if not all(p["holds"] for p in res["properties"].values()):
        raise SystemExit("*** an operator property does not hold")


if __name__ == "__main__":
    main()
