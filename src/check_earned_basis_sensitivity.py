"""Earned-basis sensitivity (the adjudication of 22 October 2026, Q4; the author's choice (i): option A, with a
sensitivity on option B's named records).

A table on an earned basis develops each underwriting year's claims on the premium earned so far, so the youngest
mature year's step (u = t-2) can mix earning with re-estimation while that year is still earning. The adjudication
kept every earned-basis table in the primary (option A) and asked for a sensitivity that leaves out the records whose
filings THEMSELVES say the t-2 cohort was still earning in year t. They are named in
results/extraction_error_rate/mature-cohort/adjudication.md (Q4, option B, and Q7), 21 records:

  1699/2024 and 2015/2021   found by reading (Q7: a reader's objection was earning, which no rule excludes);
  1225/2016 to 1225/2022    the filing prints an unearned portion still on the t-2 cohort at year end (7);
  2121/2015 to 2121/2024    the filing states earning continues up to 24 months beyond the underwriting year (10);
  5820/2015 and 5820/2017   the filing states long earning patterns (2).

780/2016, an earned-basis table found by reading, is not among them: the adjudication names it for the earned basis and
its older-years bucket, not for a t-2 cohort still earning. Every named record must be in the primary working sample,
or nothing is written.

The script refits the adopted model and transfers the vignettes without the 21 (sample_scope.refit_without), and
reports k, the floor, both tail indices and the year-shock scale, and Vignette 1's VaR99 and VaR99.5 and Vignette 2's
VaR99 and VaR99.5 before and after and their change, beside the primary's.

It also counts the earned-basis tables in the primary, from the adjudication's population classification
(results/extraction_error_rate/mature-cohort/measures/pop_classified.json, classify_pop.py on measure_pop.py's text of
each used table's page and the page before, offline): a lower bound, since a scanned or reflowed page can hide the
wording, so the records found only by reading are added.

Writes check_earned_basis_sensitivity_results.json.
Usage:  python src/check_earned_basis_sensitivity.py
"""
import io
import json
import sys
import time

import sample_scope as SS
from adopted_model import SD

OUT = SD / "results" / "check_earned_basis_sensitivity_results.json"
#: option B's named records (adjudication.md, Q4 and Q7), each with the filing's own words as the adjudication gives them
NAMED = {
    **{"1699_2024": "found by reading (Q7): the youngest mature step is earning, the filing says the 2022 ultimate fell",
       "2015_2021": "found by reading (Q7): as 1699/2024"},
    **{"1225_%d" % y: "the filing prints an unearned portion still on the t-2 cohort at year end" for y in range(2016, 2023)},
    **{"2121_%d" % y: "the filing states earning continues up to 24 months beyond the underwriting year"
       for y in range(2015, 2025)},
    **{"5820_%d" % y: "the filing states long earning patterns" for y in (2015, 2017)},
}
#: the earned-basis records found only by reading (adjudication.md, Q4: "1699/2024, 2015/2021 and 780/2016 were found
#: only by reading")
FOUND_BY_READING = ("1699_2024", "2015_2021", "780_2016")
#: classify_pop.py's earned classes
EARNED_CLASSES = ("earned-basis table", "first diagonal earned", "ultimate basis, unearned portion deducted",
                  "no earned wording found")


def earned_population(keys, classified):
    """The earned-basis classes of the primary's records (classify_pop.py), with the records found by reading added to
    the earned-basis tables where the script did not find the wording."""
    rows = {k: classified.get(k) for k in keys}
    missing = sorted((k for k, r in rows.items() if r is None), key=SS.order_key)
    counts = {c: 0 for c in EARNED_CLASSES}
    late = 0
    for k, r in rows.items():
        if r is None:
            continue
        counts[r["earned"]] = counts.get(r["earned"], 0) + 1
        late += bool(r.get("late_earning_wording"))
    by_reading = [k for k in FOUND_BY_READING if k in rows and rows[k] is not None
                  and rows[k]["earned"] != "earned-basis table"]
    return {
        "method": ("classify_pop.py's classes (results/extraction_error_rate/mature-cohort/measures/), from "
                   "measure_pop.py's text of each used table's page and the page before (the census's offline text "
                   "loader): an earned-basis table is one whose wording says so ('estimates of earned ultimate', "
                   "'claims on premium earned', 'pure year earned', ...). A lower bound: a scanned or reflowed page can "
                   "hide the wording, and %d records were found only by reading" % len(FOUND_BY_READING)),
        "n_primary": len(keys), "n_classified": len(keys) - len(missing), "not_classified": missing,
        "by_class": counts,
        "earned_basis_tables_by_wording": counts["earned-basis table"],
        "found_only_by_reading": by_reading,
        "earned_basis_tables_lower_bound": counts["earned-basis table"] + len(by_reading),
        "first_diagonal_only_earned": counts["first diagonal earned"],
        "ultimate_basis_unearned_deducted": counts["ultimate basis, unearned portion deducted"],
        "late_earning_wording": late,
        "earned_basis_tables": sorted([k for k, r in rows.items() if r and r["earned"] == "earned-basis table"]
                                      + by_reading, key=SS.order_key),
    }


def compute():
    t0 = time.time()
    keys = [SS.key_of(o) for o in SS.primary()]
    classified = SS.load_json(SS.POP_CLASSIFIED)
    population = earned_population(keys, classified)
    block = SS.refit_without(
        list(NAMED), "earned_basis_option_b",
        "without the %d records whose filings say the t-2 cohort was still earning in year t (adjudication.md, Q4 "
        "option B and Q7)" % len(NAMED))
    for row in block["left_out"]:
        row["why"] = NAMED[row["record"]]
    return {
        "question": ("what do the fit and the vignette stresses become without the records whose filings say the "
                     "youngest mature cohort was still earning?"),
        "source": "results/extraction_error_rate/mature-cohort/adjudication.md, Q4 (option B) and Q7",
        "named_records": len(NAMED),
        "not_named_note": ("780/2016 is an earned-basis table found by reading, but the adjudication names it for its "
                           "basis and its older-years bucket, not for a t-2 cohort still earning; it stays"),
        "earned_basis_population": population,
        **block,
        "runtime_seconds": time.time() - t0,
    }


def main():
    out = compute()
    with io.open(OUT, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(out, indent=1) + "\n")
    print("Wrote %s" % OUT)
    p = out["earned_basis_population"]
    print("  earned-basis tables in the primary: %d by wording + %d by reading = %d (lower bound) of %d; first diagonal "
          "only %d; ultimate less unearned %d; late-earning wording %d"
          % (p["earned_basis_tables_by_wording"], len(p["found_only_by_reading"]), p["earned_basis_tables_lower_bound"],
             p["n_primary"], p["first_diagonal_only_earned"], p["ultimate_basis_unearned_deducted"],
             p["late_earning_wording"]))
    report(out)
    return 0


def report(out):
    print("  %d left out, %d fitted (%d syndicates)" % (out["n_left_out"], out["n_fit"], out["n_syndicates_fit"]))
    for v in SS.VARS:
        if v in out["primary_fit"]:
            print("  %-9s %.4f [%.4f, %.4f]  primary %.4f  shift %+.4f (%+.2f primary sd)"
                  % (v, out["fit"][v]["mean"], out["fit"][v]["hdi_2.5%"], out["fit"][v]["hdi_97.5%"],
                     out["primary_fit"][v]["mean"], out["shift_vs_primary"][v], out["shift_vs_primary_in_primary_sd"][v]))
    vg = out["vignettes"]
    for q in ("V1_v99", "V1_v995", "V2_old_v99", "V2_old_v995", "V2_new_v99", "V2_new_v995", "V2_d995"):
        iv = vg["intervals"].get(q)
        print("  %-12s %.4f  primary %.4f  (%+.2f%%)%s"
              % (q, vg["centre"][q], vg["primary_centre"][q], 100 * vg["relative_to_primary"][q],
                 "" if iv is None else "  resampling interval [%.4f, %.4f]" % (iv["lo"], iv["hi"])))


if __name__ == "__main__":
    sys.exit(main())
