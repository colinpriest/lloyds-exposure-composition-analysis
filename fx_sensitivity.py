"""FX sensitivity: converted-GBP baseline vs as-reported (nominal) currency.

Since the FX conversion (docs/fx-conversion.md), exposure_results.json is a
single-currency GBP dataset: USD-presented reports are converted at the
reporting-date H.10 spot rate inside run_analysis.py. This script quantifies what
the conversion changes: it refits the headline two-regime Bayesian model on
(a) the converted baseline as in the bundle, and (b) the nominal (as-reported)
sizes reconstructed by multiplying USD observations back by the same year-end
rates, and compares k / gamma / floor / nu_clean and the vignette VaRs.

Severity S=PYD/reserves and HHI are within-filing ratios (currency-neutral), so
only the SIZE variable R differs between the two fits.

Run: python fx_sensitivity.py
"""
import io, json
from pathlib import Path
import numpy as np

from proxy_stress_bayes import fit_bayes, outputs, load as load_base

SD = Path(__file__).resolve().parent


def fx_map():
    """(is_usd, rate) per observation key from the converted bundle."""
    d = json.load(io.open(SD / "model" / "exposure_results.json", encoding="utf-8"))
    m = {}
    for o in d["observations"]:
        k = f"{o['syndicate']}_{o['year']}"
        m[k] = (bool(o.get("fx_applied")), o.get("fx_rate_usd_per_gbp"))
    return m


def main():
    S, R, H, yr, W, ritc, v2o, v2n = load_base()   # R is converted GBP (baseline)
    d = json.load(io.open(SD / "model" / "exposure_results.json", encoding="utf-8"))
    recs = [o for o in d["observations"]
            if o.get("s_raw_a") is not None and o.get("opening_reserves_gbp_m")
            and o.get("hhi") is not None and o.get("weights")]
    keys = [f"{o['syndicate']}_{o['year']}" for o in recs]
    fx = fx_map()
    is_usd = np.array([fx.get(k, (False, None))[0] for k in keys])
    rate = np.array([fx.get(k, (False, None))[1] or 1.0 for k in keys])
    R_nominal = np.where(is_usd, R * rate, R)   # undo conversion (as-reported USD)
    rates_used = d["fx_conversion"]["year_end_rates_used"]
    print(f"n={len(S)}  USD={int(is_usd.sum())} ({100*is_usd.mean():.0f}%)  "
          f"mean USD reserve shrink x{np.mean(1/rate[is_usd]):.2f}")

    out = {}
    for label, Rx in [("FX-converted to GBP (baseline)", R),
                      ("nominal (as-reported)", R_nominal)]:
        m = fit_bayes(S, Rx, H, yr, ritc)
        o = outputs(S, Rx, H, ritc, m, v2o, v2n)
        out[label] = {**m, "V1_VaR99": o[0], "V1_VaR995": o[1], "V2_change995": o[2]}
        print(f"  {label:<32} k={m['k']:.3f} gamma={m['gamma']:.3f} "
              f"floor={m['sd_undiv']:.4f} nu_clean={m['nu_clean']:.2f}  "
              f"V1_99.5={o[1]:.3f}  V2={o[2]:+.3f}")
    (SD / "results" / "fx_sensitivity_results.json").write_text(
        json.dumps({"n_usd": int(is_usd.sum()),
                    "rates": {y: r["usd_per_gbp"] for y, r in rates_used.items()},
                    "rate_source": "Fed H.10 year-end spot (fx_rates_h10.json)",
                    "fits": out}, indent=2), encoding="utf-8")
    print("Wrote fx_sensitivity_results.json")


if __name__ == "__main__":
    main()
