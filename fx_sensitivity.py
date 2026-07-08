"""Currency sensitivity: does leaving reserves in nominal (as-reported) currency matter?

The extraction stores opening reserves in the syndicate's REPORTING currency (GBP or USD;
~24% of the sample is USD) under a field misleadingly named opening_reserves_gbp_m; no FX
conversion is applied. Severity S=PYD/reserves and HHI are within-filing ratios (currency-
neutral), so only the SIZE variable R is affected. We refit the headline two-regime Bayesian
model with USD reserves converted to GBP at annual average rates, and compare k / gamma / floor
/ nu_clean and the vignette VaRs against the nominal fit.

Run: python fx_sensitivity.py
"""
import io, json, glob
from pathlib import Path
import numpy as np

from proxy_stress_bayes import fit_bayes, outputs, load as load_base

SD = Path(__file__).resolve().parent

# GBP/USD annual average (USD per 1 GBP); USD reserves -> GBP = R_usd / rate
GBPUSD = {2014: 1.647, 2015: 1.528, 2016: 1.355, 2017: 1.288, 2018: 1.335, 2019: 1.277,
          2020: 1.284, 2021: 1.376, 2022: 1.237, 2023: 1.244, 2024: 1.278}


def currency_map():
    m = {}
    for f in glob.glob(str(SD / "pdf_extraction" / "syndicate_*_*.json")):
        try:
            d = json.load(io.open(f, encoding="utf-8"))
            md = d.get("models", {})
            c = None
            for mk in ("gemini-2.5-flash", "gpt-5-mini"):
                if mk in md and md[mk].get("currency"):
                    c = md[mk]["currency"]; break
            key = f.split("syndicate_")[1].replace(".json", "")
            m[key] = c
        except Exception:
            pass
    return m


def main():
    S, R, H, yr, W, ritc, v2o, v2n = load_base()
    d = json.load(io.open(SD / "exposure_results.json", encoding="utf-8"))
    recs = [o for o in d["observations"]
            if o.get("s_raw_a") is not None and o.get("opening_reserves_gbp_m")
            and o.get("hhi") is not None and o.get("weights")]
    keys = [f"{o['syndicate']}_{o['year']}" for o in recs]
    cur = currency_map()
    is_usd = np.array([cur.get(k) == "USD" for k in keys])
    rate = np.array([GBPUSD.get(int(k.split("_")[1]), 1.30) for k in keys])
    R_conv = np.where(is_usd, R / rate, R)   # convert USD reserves to GBP
    print(f"n={len(S)}  USD={int(is_usd.sum())} ({100*is_usd.mean():.0f}%)  "
          f"mean USD reserve shrink x{np.mean(1/rate[is_usd]):.2f}")

    out = {}
    for label, Rx in [("nominal (as-reported)", R), ("FX-converted to GBP", R_conv)]:
        m = fit_bayes(S, Rx, H, yr, ritc); o = outputs(S, Rx, H, ritc, m, v2o, v2n)
        out[label] = {**m, "V1_VaR99": o[0], "V1_VaR995": o[1], "V2_change995": o[2]}
        print(f"  {label:<22} k={m['k']:.3f} gamma={m['gamma']:.3f} floor={m['sd_undiv']:.4f} "
              f"nu_clean={m['nu_clean']:.2f}  V1_99.5={o[1]:.3f}  V2={o[2]:+.3f}")
    (SD / "fx_sensitivity_results.json").write_text(
        json.dumps({"n_usd": int(is_usd.sum()), "rates": GBPUSD, "fits": out}, indent=2), encoding="utf-8")
    print("Wrote fx_sensitivity_results.json")


if __name__ == "__main__":
    main()
