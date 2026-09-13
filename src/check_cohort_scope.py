"""Check (referee, 7 September 2026, M02): the numerator's cohort coverage.

The manuscript defines every numerator as the sum of ultimate-estimate changes over
underwriting years u <= t-2. That restriction is enforced by construction only where
the figure came from a triangle route, which reads the development diagonal with the
two most recent underwriting years excluded. Where the figure is the movement the
filing discloses for "prior years" -- the provisions fallback and a retained narrative
value -- the filing does not partition by cohort, so the record may include u = t-1.
The review's example is 780/2016, whose -US$15.6m is the disclosed gross prior-year
provisions movement with no cohort decomposition.

This is a statement about evidence, not a measured bias: nothing here establishes that
the disclosed-scope records contain a t-1 contribution. The check refits the adopted
model on the observations whose cohort coverage IS enforced and reports how the
parameters move, so the manuscript can declare the source-dependent estimands and show
what the consistently constructed subset gives.

Writes check_cohort_scope_results.json.
Usage:  python src/check_cohort_scope.py
"""
import io
import json
from pathlib import Path

import numpy as np
import pytensor
pytensor.config.mode = "NUMBA"
import pymc as pm
import arviz as az

from adopted_model import scale_block, headline, SAMPLE_CORES
import assumed_business

SD = Path(__file__).resolve().parent.parent
OUT = SD / "results" / "check_cohort_scope_results.json"
RITC = SD / "pdf_extraction" / "ritc_scan.json"
REF, HLO, HCE, SEED = 500.0, 0.01, 1.0, 42
VARS = ["k", "gamma", "sd_undiv", "sd_div", "nu_clean", "nu_ritc", "tau_s"]


def load():
    d = json.load(io.open(SD / "model" / "exposure_results.json", encoding="utf-8"))
    recs = [o for o in d["observations"]
            if o.get("s_raw_a") is not None and o.get("opening_reserves_gbp_m")
            and o.get("hhi") is not None and o.get("pyd_basis") == "gross"]
    return recs


def arrays(recs):
    S = np.array([o["s_raw_a"] for o in recs], float)
    R = np.array([o["opening_reserves_gbp_m"] for o in recs], float)
    H = np.clip(np.array([o["hhi"] for o in recs], float), HLO, HCE)
    yr = np.array([o["year"] for o in recs])
    key = np.array(["%s_%s" % (o["syndicate"], o["year"]) for o in recs])
    return S, R, H, yr, key


def ritc_flag(key):
    occ = assumed_business.keys()
    return np.array([k in occ for k in key], float)


def fit(S, R, H, yr, ritc):
    years = np.sort(np.unique(yr))
    yidx = np.searchsorted(years, yr)
    logR, logH = np.log(R / REF), np.log(H)
    with pm.Model():
        b = scale_block(ritc=ritc, logR=logR, logH=logH, yidx=yidx, n_y=len(years))
        pm.StudentT("S_obs", nu=b["nu_obs"], mu=0.0, sigma=b["sigma"], observed=S)
        idata = pm.sample(1500, tune=1500, chains=4, cores=SAMPLE_CORES, target_accept=0.98,
                          random_seed=SEED, progressbar=False)
    s = az.summary(idata, var_names=VARS, hdi_prob=0.95)
    return {v: {"mean": float(s.loc[v, "mean"]), "sd": float(s.loc[v, "sd"]),
                "hdi_2.5%": float(s.loc[v, "hdi_2.5%"]),
                "hdi_97.5%": float(s.loc[v, "hdi_97.5%"])} for v in VARS}


def main():
    recs = load()
    enforced = [o for o in recs if o.get("pyd_cohort_scope") == "mature-enforced"]
    disclosed = [o for o in recs if o.get("pyd_cohort_scope") != "mature-enforced"]

    out = {
        "purpose": ("the cohort coverage of the admitted numerators, and the adopted model "
                    "refitted on the observations whose u <= t-2 restriction is enforced by "
                    "construction"),
        "estimand_note": ("a triangle route computes the sum of ultimate-estimate changes over "
                          "u <= t-2 directly; a disclosed prior-year movement is whatever the "
                          "filing reports for prior years and is not partitioned by cohort, so "
                          "the restriction is not established for those records"),
        "count_note": ("n_mature_enforced is a lower bound: the extraction annotates a "
                       "triangle override only where the triangle value differed from the "
                       "model's, so a triangle figure the model had already matched carries "
                       "no annotation and is counted as disclosed"),
        "n_gross_sample": len(recs),
        "n_mature_enforced": len(enforced),
        "n_disclosed_prior_year": len(disclosed),
        "share_enforced": round(len(enforced) / len(recs), 6) if recs else None,
        "n_syndicates_enforced": len({o["syndicate"] for o in enforced}),
    }

    S, R, H, yr, key = arrays(enforced)
    out["enforced_subset_fit"] = fit(S, R, H, yr, ritc_flag(key))
    out["headline"] = headline()
    out["shifts_vs_headline"] = {
        v: round(out["enforced_subset_fit"][v]["mean"] - float(out["headline"][v]["mean"]), 6)
        for v in VARS if v in out["headline"]
    }
    out["reading"] = ("the subset is smaller, so wider intervals are expected; the check is "
                      "whether the enforced-cohort subset moves the parameters beyond that")

    OUT.write_text(json.dumps(out, indent=1) + "\n", encoding="utf-8", newline="")
    print("wrote", OUT.name)
    print("  gross sample %d; cohort enforced %d; disclosed %d"
          % (out["n_gross_sample"], out["n_mature_enforced"], out["n_disclosed_prior_year"]))
    for v in VARS:
        if v in out["shifts_vs_headline"]:
            print("  %-10s enforced %.4f   headline %.4f   shift %+.4f"
                  % (v, out["enforced_subset_fit"][v]["mean"],
                     float(out["headline"][v]["mean"]), out["shifts_vs_headline"][v]))


if __name__ == "__main__":
    main()
