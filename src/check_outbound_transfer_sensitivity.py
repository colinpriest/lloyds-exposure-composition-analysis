"""Outbound-transfer sensitivity: the adopted model refitted with R as the balance the syndicate kept.

The headline keeps R, the severity denominator, as the unadjusted opening gross claims outstanding at 1 January
(the author's decision of 29 September 2026). A syndicate that reinsures closed years to close into another
syndicate at the start of its year keeps only part of that balance, and the development it then reports is on what
it kept, so S = PYD/R understates its severity by the share transferred out. This script measures what the choice
costs. For every record data/outbound_transfer_retained_base.json confirms -- the filing prints the amount
transferred out, with its page -- it replaces R by R minus that amount, in the report's own currency, so S = PYD/R
becomes PYD/(R - transferred) while the development PYD itself is unchanged; it refits the adopted model at the
adopted sampling configuration (fx_sensitivity.fit_adopted_config, calibrate_dispersion_ritc.py's call) on the
sample with those records adjusted; and it compares k, the floor, gamma, the tail indices and the size-only headline
vignettes (Vignette 1 VaR99.5, Vignette 2 change) with the adopted fit, the published calibration.

The register's transfers that are named with their counterparty but whose amount is not read are listed and not
adjusted. A confirmed record that is not in the working sample is listed and not applied, with the loader's own
disposition of it from results/disposition_ledger.csv. Four of the fourteen confirmed records are outside it, all as
run-off years, which the loader excludes before the corpus and the missingness partition counts as scientific
exclusions: 780/2020, 1861/2021 and 5820/2019 under the whole-year run-off rule (the author's decision of 1 October
2026), and 2468/2022 with no gross premium written. Those include the three largest shares transferred out (95%,
72% and 66% of the opening), so the rule removed the largest transfers before this sensitivity could adjust them;
the ten applied are 1200/2023 and 1861/2019 (43% and 47%) and, from the PC page readings of 5 October 2026,
1955/2021, 4000/2021, 2015/2020, 1910/2023, 2007/2018, 1301/2023, 1084/2018 and 2468/2018 (64%, 66%, 57%, 27%, 52%,
36%, 10% and 69%).
The amounts live in the register only; the sensitivity refuses an entry whose
opening balance is not the record's R within 2%, whose currency is not the record's, or whose transfer is not
smaller than its opening.

Writes results/check_outbound_transfer_sensitivity_results.json.
Run: python src/check_outbound_transfer_sensitivity.py
"""
import io
import json
from pathlib import Path

import numpy as np

from adopted_model import load_sample
from fx_sensitivity import CHAINS, DRAWS, SEED, TARGET_ACCEPT, TUNE, fit_adopted_config, fx_map
from proxy_stress_bayes import outputs
import transfer_operator

SD = Path(__file__).resolve().parent.parent
REGISTER = SD / "data" / "outbound_transfer_retained_base.json"
CALIBRATION = SD / "model" / "dispersion_calibration_ritc.json"
OUT = SD / "results" / "check_outbound_transfer_sensitivity_results.json"
LEDGER = SD / "results" / "disposition_ledger.csv"
#: a register's opening balance must be the record's R, in the report's currency, within this share
TOLERANCE = 0.02
PARAMS = ("k", "gamma", "sd_undiv", "sd_div", "nu_clean", "nu_ritc")


def load_register(path=REGISTER):
    return json.load(io.open(str(path), encoding="utf-8"))


#: the loader's pre-corpus dispositions, in words, for a confirmed record the sensitivity cannot apply
DISPOSITION_WORDS = {
    "IN RUNOFF": ("in run-off: the filing states run-off for the whole year, outside the RITC regime, or gross "
                  "written premium 0, or below 0 where the filing states run-off; the loader excludes such a year "
                  "before the corpus and the missingness partition counts it as a scientific exclusion"),
    "NO_RESERVES": "no positive opening reserve base, which the loader excludes before the corpus",
}


def loader_dispositions(path=LEDGER):
    """{register key: the loader's disposition} from results/disposition_ledger.csv."""
    import csv
    with io.open(str(path), encoding="utf-8") as fh:
        return {row["file"][len("syndicate_"):-len(".json")]: row["disposition"] for row in csv.DictReader(fh)}


def retained_base(S, R, keys, fx, register, dispositions=None):
    """(S_after, R_after, rows): R replaced by R minus the amount transferred out, in the report's currency, for
    every confirmed record in the sample; S_after = S * R / R_after, so the development S * R is unchanged.

    `fx` maps a key to (is_usd, usd_per_gbp) as the loader converted it (fx_sensitivity.fx_map). A confirmed record
    outside the sample is listed with the loader's disposition of it (`dispositions`, from the ledger)."""
    S_after, R_after = np.array(S, float).copy(), np.array(R, float).copy()
    at = {k: i for i, k in enumerate(keys)}
    rows = {}
    for key, e in sorted(register["confirmed"].items()):
        entry = {"currency": e["currency"], "page": e["page"], "counterparty": e.get("counterparty"),
                 "opening_m": e["opening_m"], "transferred_out_m": e["transferred_out_m"],
                 "measure": e.get("measure")}
        if key not in at:
            disposition = (dispositions or {}).get(key)
            rows[key] = dict(entry, in_working_sample=False, applied=False, loader_disposition=disposition,
                             note="listed and not applied: the record is not in the working sample (%s)"
                                  % DISPOSITION_WORDS.get(disposition, "the loader's disposition: %s" % disposition))
            continue
        i = at[key]
        is_usd, rate = fx.get(key, (False, None))
        if (e["currency"] == "USD") != bool(is_usd):
            raise SystemExit("%s: the register says %s, the record is %s" % (key, e["currency"],
                                                                             "USD" if is_usd else "GBP"))
        rate = float(rate) if is_usd else 1.0
        r_report = float(R[i]) * rate
        if abs(r_report - e["opening_m"]) > TOLERANCE * e["opening_m"]:
            raise SystemExit("%s: the register's opening %.3f is not the record's R %.3f (%s) within %.0f%%"
                             % (key, e["opening_m"], r_report, e["currency"], 100 * TOLERANCE))
        if not 0.0 < e["transferred_out_m"] < r_report:
            raise SystemExit("%s: the amount transferred out (%.3f) must be positive and below the opening %.3f"
                             % (key, e["transferred_out_m"], r_report))
        R_after[i] = (r_report - e["transferred_out_m"]) / rate
        S_after[i] = float(S[i]) * float(R[i]) / R_after[i]
        rows[key] = dict(entry, in_working_sample=True, applied=True,
                         R_before_gbp_m=float(R[i]), R_after_gbp_m=float(R_after[i]),
                         share_transferred=e["transferred_out_m"] / r_report,
                         S_before=float(S[i]), S_after=float(S_after[i]),
                         development_gbp_m=float(S[i]) * float(R[i]))
    return S_after, R_after, rows


def vignettes(S, R, H, ritc, means, v2o, v2n):
    """The headline size-only vignettes at the fitted means, and the overlay's beside them."""
    o = outputs(S, R, H, ritc, means, v2o, v2n)
    oo = outputs(S, R, H, ritc, means, v2o, v2n, transfer_operator.SENSITIVITY)
    return {**transfer_operator.stamp(transfer_operator.HEADLINE),
            "V1_VaR99": o[0], "V1_VaR995": o[1], "V2_change995": o[2],
            "overlay_sensitivity": {**transfer_operator.stamp(transfer_operator.SENSITIVITY),
                                    "V1_VaR99": oo[0], "V1_VaR995": oo[1], "V2_change995": oo[2]}}


def compare(adopted, retained, name):
    a, b = adopted[name], retained[name]
    return {"adopted": a, "retained_base": b, "change": b - a, "pct_change": 100.0 * (b / a - 1.0)}


def main(fit=fit_adopted_config):
    S, R, H, yr, syn, ritc = load_sample()        # the adopted working sample
    keys = ["%s_%s" % (s, y) for s, y in zip(syn, yr)]
    register = load_register()
    S_after, R_after, rows = retained_base(S, R, keys, fx_map(), register, loader_dispositions())
    moved = [k for k, r in rows.items() if r["applied"]]
    t2 = json.load(io.open(str(SD / "vignettes" / "vignette-2" / "target_transition.json"), encoding="utf-8"))
    v2o = (float(t2["old_reserve_size"]), float(t2["old_hhi"]))
    v2n = (float(t2["new_reserve_size"]), float(t2["new_hhi"]))

    cal = json.load(io.open(str(CALIBRATION), encoding="utf-8"))
    adopted = {p: float(cal[p]) for p in PARAMS}
    adopted_fit = {**adopted, "source": "model/dispersion_calibration_ritc.json (the published calibration)",
                   "params": {p: cal["params"][p] for p in PARAMS if p in cal["params"]},
                   **vignettes(S, R, H, ritc, adopted, v2o, v2n)}
    means, params, diag, _draws, cond = fit(S_after, R_after, H, yr, ritc)
    retained_fit = {**means, "params": params, "diagnostics": diag, "conditional_fit_summaries": cond,
                    **vignettes(S_after, R_after, H, ritc, means, v2o, v2n)}

    at = {k: i for i, k in enumerate(keys)}
    named = {k: dict(v, in_working_sample=k in at, adjusted=False,
                     **({"S": float(S[at[k]]), "R_gbp_m": float(R[at[k]])} if k in at else {}))
             for k, v in register["named_not_adjusted"].items() if not k.startswith("_")}
    out = {
        "question": ("what does keeping R as the unadjusted opening cost, for the records whose filings print an "
                     "outbound reinsurance to close or transfer at the start of the year?"),
        "rule": ("the headline keeps R as the unadjusted opening gross claims outstanding at 1 January (author, 29 "
                 "September 2026); this is a sensitivity, R replaced by R minus the amount transferred out"),
        "register": "data/outbound_transfer_retained_base.json",
        **transfer_operator.stamp(transfer_operator.HEADLINE),
        "n": int(len(S)), "n_adjusted": len(moved), "adjusted": moved,
        "records": rows,
        "named_not_adjusted": named,
        "sampling": {"draws": DRAWS, "tune": TUNE, "chains": CHAINS, "target_accept": TARGET_ACCEPT, "seed": SEED,
                     "same_as": "calibrate_dispersion_ritc.py"},
        "fits": {"adopted": adopted_fit, "retained_base": retained_fit},
        "point_sensitivities": {
            "note": ("two separately fitted posteriors compared at their means; no interval for the difference is "
                     "estimated"),
            "k": compare(adopted_fit, retained_fit, "k"),
            "floor": compare(adopted_fit, retained_fit, "sd_undiv"),
            "gamma": compare(adopted_fit, retained_fit, "gamma"),
            "nu_clean": compare(adopted_fit, retained_fit, "nu_clean"),
            "nu_ritc": compare(adopted_fit, retained_fit, "nu_ritc"),
            "V1_VaR995": {**transfer_operator.stamp(transfer_operator.HEADLINE),
                          **compare(adopted_fit, retained_fit, "V1_VaR995")},
            "V2_change995": {**transfer_operator.stamp(transfer_operator.HEADLINE),
                             **compare(adopted_fit, retained_fit, "V2_change995")},
        },
    }
    io.open(str(OUT), "w", encoding="utf-8", newline="\n").write(json.dumps(out, indent=1) + "\n")
    for key, r in rows.items():
        if r["applied"]:
            print("  %-10s R %8.3f -> %8.3f GBP m (%.0f%% out)   S %+.4f -> %+.4f"
                  % (key, r["R_before_gbp_m"], r["R_after_gbp_m"], 100 * r["share_transferred"],
                     r["S_before"], r["S_after"]))
        else:
            print("  %-10s %s" % (key, r["note"]))
    ps = out["point_sensitivities"]
    for name in ("k", "floor", "gamma", "nu_clean", "nu_ritc", "V1_VaR995", "V2_change995"):
        print("  %-12s adopted %+.4f  retained base %+.4f  (%+.1f%%)"
              % (name, ps[name]["adopted"], ps[name]["retained_base"], ps[name]["pct_change"]))
    print("Wrote %s" % OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
