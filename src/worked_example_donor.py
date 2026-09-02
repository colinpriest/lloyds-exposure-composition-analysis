"""Worked example: single-donor transfer for Vignette 1 (paper Section 5.1).

Selects two REAL donors from the donor pool per the spec (Donor A: large adverse
movement from a small syndicate; Donor B: moderate adverse movement from a target-size but
more-concentrated syndicate), and runs the transfer arithmetic with a point estimate
(posterior mean) and a 95% interval (propagating posterior draws of theta). Uses the same
shape-aware operator as the aggregate pipeline: the donor severity is de-RITC'd (Student-t
quantile transform from nu_ritc to nu_clean) when the donor is an RITC year, then rescaled by
sigma(target)/sigma(donor). Computation at full precision; display rounded to 3 sig figs.

Run: python src/worked_example_donor.py
"""
import json, re
from pathlib import Path
import numpy as np
from scipy import stats as _sps

SCRIPT_DIR = Path(__file__).resolve().parent.parent
TARGET = (500.0, 0.17)          # Vignette 1: R_q, H_q


def load_pool():
    html = (SCRIPT_DIR / "distortion_tool.html").read_text(encoding="utf-8")
    donors = json.loads(re.search(r"const EMBEDDED_DATA = (\{.*?\});\s*\n", html, re.S).group(1))["donors"]
    return donors


def load_params():
    """Prefer the RITC tail-regime calibration (adds nu_clean/nu_ritc); fall back to the plain fit."""
    ritc_cal = SCRIPT_DIR / "model" / "dispersion_calibration_ritc.json"
    ritc_npz = SCRIPT_DIR / "model" / "dispersion_posterior_draws_ritc.npz"
    use_ritc = ritc_cal.exists() and ritc_npz.exists()
    cal = json.loads((ritc_cal if use_ritc else SCRIPT_DIR / "model" / "dispersion_calibration.json").read_text())
    z = np.load(ritc_npz if use_ritc else SCRIPT_DIR / "model" / "dispersion_posterior_draws.npz")
    base = ["k", "gamma", "sd_undiv", "sd_div"]
    nu = ["nu_clean", "nu_ritc"] if ("nu_clean" in z.files) else []
    mean = {p: float(cal[p]) for p in base + nu}
    mean["ref"] = float(cal["reference_size"]); mean["hlo"] = float(cal["hhi_floor"]); mean["hce"] = float(cal["hhi_ceil"])
    draws = {p: z[p] for p in base + nu}
    return mean, draws


def deritc(z, ritc, nu_ritc, nu_clean):
    """Map an RITC donor's standardised residual from the RITC tail to the clean tail."""
    if not ritc or nu_ritc is None or nu_clean is None:
        return z
    u = np.clip(_sps.t.cdf(z, df=nu_ritc), 1e-12, 1.0 - 1e-12)
    return _sps.t.ppf(u, df=nu_clean)


def sigma(R, H, k, g, su, sd, ref, hlo, hce):
    Hc = np.clip(H, hlo, hce)
    reff = (np.maximum(R, 1e-9) / ref) * (1.0 / Hc) ** g
    return np.sqrt(su * su + sd * sd * reff ** (2.0 * (k - 1.0)))


def reff_over_ref(R, H, g, ref, hlo, hce):
    return (R / ref) * (1.0 / np.clip(H, hlo, hce)) ** g


def select_donors(donors):
    S = np.array([d["s_raw_a"] for d in donors], float)
    R = np.array([d["opening_reserves_gbp_m"] for d in donors], float)
    H = np.array([d["hhi"] for d in donors], float)
    pos = S > 0
    posS = S[pos]
    qhi = np.percentile(posS, 90)   # "high but not maximal" movement quantile
    qmax = np.percentile(posS, 98)  # avoid the very extreme tail
    qmed = np.percentile(posS, 55)  # "moderate" movement

    # Donor A: small syndicate (~1/10 of target, centred near £50m), large-but-not-maximal
    # adverse movement.
    a_mask = pos & (R >= 40) & (R <= 75) & (S >= qhi) & (S <= qmax)
    if not a_mask.any():
        a_mask = pos & (R >= 25) & (R <= 90) & (S >= np.percentile(posS, 85)) & (S <= qmax)
    a_idx = np.where(a_mask)[0]
    # among candidates pick the one whose movement is closest to the 90th pct (illustrative,
    # not maximal) and whose size is closest to a tenth of the target (£50m)
    A = a_idx[np.argmin(np.abs(S[a_idx] - qhi) / qhi + 0.5 * np.abs(R[a_idx] - 50.0) / 50.0)]

    # Donor B: target-size (R ~ 500), clearly more concentrated than target, moderate adverse.
    b_mask = pos & (R >= 380) & (R <= 660) & (H >= 0.30) & (S >= np.percentile(posS, 40)) & (S <= np.percentile(posS, 75))
    if not b_mask.any():
        b_mask = pos & (np.abs(np.log(R / 500.0)) <= 0.35) & (H >= 0.28)
    b_idx = np.where(b_mask)[0]
    # prefer R closest to 500 and moderate movement
    score = np.abs(np.log(R[b_idx] / 500.0)) + 0.5 * np.abs(S[b_idx] - qmed) / qmed
    B = b_idx[np.argmin(score)]
    return int(A), int(B)


def transfer_detail(d, mp, draws):
    Ri = d["opening_reserves_gbp_m"]; Hi = d["hhi"]; Si = d["s_raw_a"]
    ritc = int(d.get("ritc", 0))
    Rq, Hq = TARGET
    cfg = (mp["ref"], mp["hlo"], mp["hce"])
    nrc, ncl = mp.get("nu_ritc"), mp.get("nu_clean")
    # point (posterior mean): de-RITC the donor residual, then rescale to target
    sig_q = sigma(Rq, Hq, mp["k"], mp["gamma"], mp["sd_undiv"], mp["sd_div"], *cfg)
    sig_i = sigma(Ri, Hi, mp["k"], mp["gamma"], mp["sd_undiv"], mp["sd_div"], *cfg)
    lam = sig_q / sig_i
    zi = deritc(Si / sig_i, ritc, nrc, ncl)     # de-RITC'd standardised residual
    Sq = zi * sig_q
    # channel diagnostics (marginal; do NOT multiply to lam exactly because of the floor)
    lam_size = sigma(Rq, Hi, mp["k"], mp["gamma"], mp["sd_undiv"], mp["sd_div"], *cfg) / sig_i  # size only (H at donor)
    lam_conc = sigma(Ri, Hq, mp["k"], mp["gamma"], mp["sd_undiv"], mp["sd_div"], *cfg) / sig_i  # concentration only
    # interval via posterior draws
    sq = sigma(Rq, Hq, draws["k"], draws["gamma"], draws["sd_undiv"], draws["sd_div"], *cfg)
    si = sigma(Ri, Hi, draws["k"], draws["gamma"], draws["sd_undiv"], draws["sd_div"], *cfg)
    lam_d = sq / si
    if ritc and "nu_ritc" in draws:
        u = np.clip(_sps.t.cdf(Si / si, df=draws["nu_ritc"]), 1e-12, 1.0 - 1e-12)
        zi_d = _sps.t.ppf(u, df=draws["nu_clean"])
    else:
        zi_d = Si / si
    sq_d = zi_d * sq
    return {
        "syndicate": d["syndicate"], "year": d["year"], "ritc": ritc,
        "R_i": Ri, "H_i": Hi, "S_i": Si,
        "reff_i_over_ref": reff_over_ref(Ri, Hi, mp["gamma"], mp["ref"], mp["hlo"], mp["hce"]),
        "reff_q_over_ref": reff_over_ref(Rq, Hq, mp["gamma"], mp["ref"], mp["hlo"], mp["hce"]),
        "sigma_i": sig_i, "sigma_q": sig_q,
        "lambda": lam, "lambda_lo": float(np.percentile(lam_d, 2.5)), "lambda_hi": float(np.percentile(lam_d, 97.5)),
        "S_q": Sq, "S_q_lo": float(np.percentile(sq_d, 2.5)), "S_q_hi": float(np.percentile(sq_d, 97.5)),
        "lambda_size_only": lam_size, "lambda_conc_only": lam_conc,
    }


def main():
    donors = load_pool()
    mp, draws = load_params()
    A, B = select_donors(donors)
    dA = transfer_detail(donors[A], mp, draws)
    dB = transfer_detail(donors[B], mp, draws)

    print(f"Parameters (full precision; Table 1 rounds these): k={mp['k']:.4f} gamma={mp['gamma']:.4f} "
          f"sd_undiv={mp['sd_undiv']:.4f} sd_div={mp['sd_div']:.4f} | target sigma(500,0.17)={dA['sigma_q']:.4f}")
    hdr = ["Step", "Donor A (size-mismatch)", "Donor B (mix-mismatch)"]
    def row(label, fa, fb): print(f"  {label:<34} {fa:<26} {fb}")
    print("\n=== WORKED EXAMPLE (real donors) ===")
    row("Donor (synd, year)", f"{dA['syndicate']}, {dA['year']}", f"{dB['syndicate']}, {dB['year']}")
    row("(R_i, H_i)", f"£{dA['R_i']:.0f}m, {dA['H_i']:.3f}", f"£{dB['R_i']:.0f}m, {dB['H_i']:.3f}")
    row("Observed S_i", f"{dA['S_i']:+.3f}", f"{dB['S_i']:+.3f}")
    row("R_eff_i / R_ref", f"{dA['reff_i_over_ref']:.3f}", f"{dB['reff_i_over_ref']:.3f}")
    row("sigma(R_i,H_i)", f"{dA['sigma_i']:.4f}", f"{dB['sigma_i']:.4f}")
    row("sigma(R_q,H_q)", f"{dA['sigma_q']:.4f}", f"{dB['sigma_q']:.4f}")
    row("lambda  [95% CrI]", f"{dA['lambda']:.3f} [{dA['lambda_lo']:.3f},{dA['lambda_hi']:.3f}]",
        f"{dB['lambda']:.3f} [{dB['lambda_lo']:.3f},{dB['lambda_hi']:.3f}]")
    row("Transferred S_q  [95% CrI]", f"{dA['S_q']:.3f} [{dA['S_q_lo']:.3f},{dA['S_q_hi']:.3f}]",
        f"{dB['S_q']:.3f} [{dB['S_q_lo']:.3f},{dB['S_q_hi']:.3f}]")
    row("channel diag: size-only lambda", f"{dA['lambda_size_only']:.3f}", f"{dB['lambda_size_only']:.3f}")
    row("channel diag: conc-only lambda", f"{dA['lambda_conc_only']:.3f}", f"{dB['lambda_conc_only']:.3f}")

    (SCRIPT_DIR / "results" / "worked_example_donors.json").write_text(json.dumps(
        {"target": {"R_q": TARGET[0], "H_q": TARGET[1]}, "params": mp, "donorA": dA, "donorB": dB}, indent=2))
    print("\nWrote worked_example_donors.json")


if __name__ == "__main__":
    main()
