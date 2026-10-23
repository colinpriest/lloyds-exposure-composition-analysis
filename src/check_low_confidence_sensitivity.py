"""Least-certain-records sensitivity (rounds 2 and 5 of the filing readings, 23 October 2026).

Round 2 read the 64 older-years ("& prior") columns and the 97 exchange lines of the primary sample twice, and settled
nearly all of them. Ten records could not be settled, and the primary keeps them under rules that stand without a
finding for them:

  * six older-years columns whose construction (calendar year or development age) could not be settled:
    data/aggregated_column_review.json marks them confidence "low_confidence" (3624/2015, 1955/2018, 1200/2015, 2007/2015,
    33/2015, 1200/2017 when the register was built); each keeps the figure it has;
  * four exchange lines of 5% or more of the opening gross claims outstanding with no year t-1 development table to test
    condition (a) of the author's rule B: data/fx_untranslated_excluded.json marks them reason "undeterminable_kept"
    (457/2015, 1301/2015, 4711/2017, 6105/2015); rule B excludes a record only when both conditions are shown, so they
    stay.

Round 5 of the filing readings (decision rules of 23 October 2026, a decision of the Claude analysis session) adds the
records whose development table restated its history and that stay in the primary under rule 6: the table ties to the
year's accounts, but an underwriting year u <= t-2 moved beyond the exchange rate without explanation by more than 1% of
R, or the two readings disagree on the validity label but not on the facts. data/restated_base_excluded.json lists them
under "history_restated" (25 records when the register was built). The least-certain set is the ten and these.

The list is read from the three registers, never typed here: a record whose confidence, reason or bucket changes there
changes the sensitivity. Every record must be in the primary working sample (sample_scope.refit_without refuses a key
outside it), or nothing is written.

The script refits the adopted model and transfers the vignettes without them (sample_scope.refit_without), and reports
n, k, the floor, both tail indices and the year-shock scale, and Vignette 1's VaR99 and VaR99.5 and Vignette 2's VaR99
and VaR99.5 before and after and their change, beside the primary's.

The least-certain records are not the whole of what the readings left uncertain, so a WIDENED set is refitted beside them
(review of 23 October 2026). It adds, again by rule from the registers and never typed:

  * every read-and-kept exchange line within 0.5 percentage points of the 5% threshold of the opening gross claims
    outstanding, on either side (data/fx_untranslated_excluded.json, fx_line_pct_of_opening, absolute value): the lines
    just under 5% are kept on a test that one more reading of the filing could move, and those just over on a table that
    is retranslated;
  * every older-years column whose construction is undeterminable or whose confidence is medium or low_confidence
    (data/aggregated_column_review.json): 1955/2015, whose two candidate figures differ by 0.319m, and any other the
    register marks so.

The record holds the least-certain result (the top-level keys) and the widened one (widened), and sets the fit, the
vignette stresses and their change on the primary side by side (least_certain_and_widened_side_by_side).

Writes check_low_confidence_sensitivity_results.json.
Usage:  python src/check_low_confidence_sensitivity.py
"""
import hashlib
import io
import json
import sys
import time

import sample_scope as SS
from adopted_model import SD

OUT = SD / "results" / "check_low_confidence_sensitivity_results.json"
COLUMN_REGISTER = SD / "data" / "aggregated_column_review.json"
FX_REGISTER = SD / "data" / "fx_untranslated_excluded.json"
RESTATED_REGISTER = SD / "data" / "restated_base_excluded.json"
RESTATED_BUCKET = "history_restated"
COLUMN_CONFIDENCE = "low_confidence"
EXCHANGE_REASON = "undeterminable_kept"
#: the widened set: exchange lines within FX_BAND_PP percentage points of FX_THRESHOLD_PCT (absolute value of the line over
#: the opening gross claims outstanding; the register states the percentage to two decimals), and older-years columns whose
#: construction is undeterminable or whose confidence is one of WIDE_COLUMN_CONFIDENCE
FX_THRESHOLD_PCT = 5.0
FX_BAND_PP = 0.5
WIDE_COLUMN_CONFIDENCE = ("low_confidence", "medium")
WIDE_COLUMN_CONSTRUCTION = "undeterminable"


def column_records(register):
    """{key: why} for the entries of the older-years review marked low confidence, from the register's entries (keys
    that are not underscore-led metadata)."""
    out = {}
    for key, e in register.items():
        if key.startswith("_"):
            continue
        if e.get("confidence") == COLUMN_CONFIDENCE:
            out[key] = ("older-years column, construction could not be settled (%s): %s"
                        % (e.get("construction"), e.get("decision")))
    return out


def exchange_records(register):
    """{key: why} for the read-and-kept exchange lines whose condition (a) could not be tested."""
    out = {}
    for key, e in (register.get("read_and_kept") or {}).items():
        if e.get("reason") == EXCHANGE_REASON:
            out[key] = ("exchange line %.2f%% of the opening gross claims outstanding with no year t-1 table to test "
                        "condition (a): %s" % (e["fx_line_pct_of_opening"], e.get("session_decision")))
    return out


def named_records(column_register, fx_register):
    """The records to leave out, {key: why}, from the two registers; a record in both keeps both reasons."""
    cols, fx = column_records(column_register), exchange_records(fx_register)
    out = dict(cols)
    for k, why in fx.items():
        out[k] = (out[k] + " | " if k in out else "") + why
    return out, sorted(cols, key=SS.order_key), sorted(fx, key=SS.order_key)


def restated_records(register):
    """{key: why} for the records rule 6 of the round-5 decision rules lists (the register's history_restated bucket)."""
    out = {}
    for key, e in (register.get(RESTATED_BUCKET) or {}).items():
        out[key] = ("development table's history restated, kept under rule 6 (%s): %s"
                    % (", ".join(e.get("clauses") or []), e.get("facts")))
    return out


def least_certain_records(column_register, fx_register, restated_register):
    """(all, cols, fx, restated): the least-certain set {key: why} (the ten of named_records and the records of
    restated_records; a record reached by two rules keeps both reasons) and the key lists of each part."""
    ten, cols, fx = named_records(column_register, fx_register)
    rs = restated_records(restated_register)
    out = dict(ten)
    for k, why in rs.items():
        out[k] = (out[k] + " | " if k in out else "") + why
    return out, cols, fx, sorted(rs, key=SS.order_key)


def wide_column_records(register):
    """{key: why} for the older-years columns whose construction is undeterminable or whose confidence is medium or
    low_confidence, from the register's entries."""
    out = {}
    for key, e in register.items():
        if key.startswith("_"):
            continue
        if e.get("construction") == WIDE_COLUMN_CONSTRUCTION or e.get("confidence") in WIDE_COLUMN_CONFIDENCE:
            out[key] = ("older-years column, construction %s, confidence %s: %s"
                        % (e.get("construction"), e.get("confidence"), e.get("decision")))
    return out


def near_threshold_exchange_records(register):
    """{key: why} for the read-and-kept exchange lines within FX_BAND_PP percentage points of FX_THRESHOLD_PCT of the
    opening gross claims outstanding, on either side, by the absolute value of the line (to the register's two decimals)."""
    out = {}
    for key, e in (register.get("read_and_kept") or {}).items():
        pct = e.get("fx_line_pct_of_opening")
        if pct is not None and abs(abs(pct) - FX_THRESHOLD_PCT) <= FX_BAND_PP + 1e-9:
            out[key] = ("exchange line %.2f%% of the opening gross claims outstanding, within %g percentage points of "
                        "the %g%% threshold (reason %s)" % (pct, FX_BAND_PP, FX_THRESHOLD_PCT, e.get("reason")))
    return out


def widened_records(column_register, fx_register, restated_register=None):
    """(all, least, near, wide): the widened set {key: why} (the least-certain records of least_certain_records, the
    exchange lines near the threshold and the columns that are undeterminable or of medium or low confidence; a record
    reached by two rules keeps both reasons), and the key lists of the least-certain records, of the lines near the
    threshold and of the wide columns. With no restated register the least-certain records are the ten."""
    ten = least_certain_records(column_register, fx_register, restated_register or {})[0]
    near, wide = near_threshold_exchange_records(fx_register), wide_column_records(column_register)
    out = dict(ten)
    for extra in (near, wide):
        for k, why in extra.items():
            if k not in out:
                out[k] = why
            elif why not in out[k]:
                out[k] = out[k] + " | " + why

    def by(d):
        return sorted(d, key=SS.order_key)

    return out, by(ten), by(near), by(wide)


def side_by_side(least, wide):
    """The fit and the vignette stresses of the primary, of the least-certain refit and of the widened refit, with each
    refit's change on the primary."""
    return {
        "fit": {v: {"primary": least["primary_fit"][v]["mean"], "least_certain": least["fit"][v]["mean"],
                    "widened": wide["fit"][v]["mean"]} for v in SS.VARS if v in least["primary_fit"]},
        "n_fit": {"primary": least["n_primary"], "least_certain": least["n_fit"], "widened": wide["n_fit"]},
        "vignette_centres": {
            k: {"primary": least["vignettes"]["primary_centre"][k], "least_certain": least["vignettes"]["centre"][k],
                "widened": wide["vignettes"]["centre"][k],
                "least_certain_relative_to_primary": least["vignettes"]["relative_to_primary"][k],
                "widened_relative_to_primary": wide["vignettes"]["relative_to_primary"][k]}
            for k in least["vignettes"]["centre"]}}


def sha256(path):
    with io.open(str(path), "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def compute():
    t0 = time.time()
    registers = SS.load_json(COLUMN_REGISTER), SS.load_json(FX_REGISTER), SS.load_json(RESTATED_REGISTER)
    named, cols, fx, restated = least_certain_records(*registers)
    if not named:
        raise SystemExit("the registers name no least-certain record: nothing to leave out")
    block = SS.refit_without(
        list(named), "low_confidence_records",
        "without the %d records the filing readings could not settle: %d older-years columns marked low_confidence in "
        "data/aggregated_column_review.json, %d exchange lines marked undeterminable_kept in "
        "data/fx_untranslated_excluded.json and %d tables whose history restated, listed under history_restated in "
        "data/restated_base_excluded.json" % (len(named), len(cols), len(fx), len(restated)))
    for row in block["left_out"]:
        row["why"] = named[row["record"]]
        row["register"] = " and ".join(r for r, ks in (("aggregated_column_review", cols),
                                                       ("fx_untranslated_excluded", fx),
                                                       ("restated_base_excluded", restated)) if row["record"] in ks)
    wide_named, w_least, w_near, w_cols = widened_records(*registers)
    wide = SS.refit_without(
        list(wide_named), "low_confidence_records_widened",
        "without the %d records of the widened set: the %d least-certain records, %d exchange lines within %g "
        "percentage points of the %g%% threshold, and %d older-years columns whose construction is undeterminable or "
        "whose confidence is medium or low_confidence" % (
            len(wide_named), len(w_least), len(w_near), FX_BAND_PP, FX_THRESHOLD_PCT, len(w_cols)))
    for row in wide["left_out"]:
        row["why"] = wide_named[row["record"]]
        row["rules"] = [r for r, ks in (("least_certain", w_least), ("exchange_line_near_threshold", w_near),
                                        ("column_undeterminable_or_medium_confidence", w_cols)) if row["record"] in ks]
    return {
        "question": ("what do the fit and the vignette stresses become without the records whose older-years column, "
                     "exchange line or development-table history the filing readings could not settle?"),
        "source": "data/aggregated_column_review.json (confidence low_confidence), data/fx_untranslated_excluded.json "
                  "(reason undeterminable_kept) and data/restated_base_excluded.json (history_restated); the readings "
                  "are archived in results/extraction_error_rate/mature-cohort/round2/ and round5/",
        "inputs_sha256": {"data/aggregated_column_review.json": sha256(COLUMN_REGISTER),
                          "data/fx_untranslated_excluded.json": sha256(FX_REGISTER),
                          "data/restated_base_excluded.json": sha256(RESTATED_REGISTER)},
        "named_records": len(named),
        "older_years_columns_low_confidence": cols,
        "exchange_lines_undeterminable": fx,
        "history_restated": restated,
        **block,
        "widened": {
            "question": ("the same, widened to the exchange lines within %g percentage points of the %g%% threshold and to "
                         "the older-years columns whose construction is undeterminable or whose confidence is medium"
                         % (FX_BAND_PP, FX_THRESHOLD_PCT)),
            "named_records": len(wide_named),
            "least_certain": w_least,
            "exchange_lines_near_threshold": w_near,
            "columns_undeterminable_or_medium_or_low_confidence": w_cols,
            "added_to_the_least_certain": sorted(set(wide_named) - set(named), key=SS.order_key),
            **wide},
        "least_certain_and_widened_side_by_side": side_by_side(block, wide),
        "runtime_seconds": time.time() - t0,
    }


def main():
    out = compute()
    with io.open(OUT, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(out, indent=1) + "\n")
    print("Wrote %s" % OUT)
    report(out)
    return 0


def report(out):
    print("  --- the least-certain records")
    print("  %d left out (%d columns, %d exchange lines, %d restated histories), %d fitted (%d syndicates) of the "
          "primary's %d" % (out["n_left_out"], len(out["older_years_columns_low_confidence"]),
                            len(out["exchange_lines_undeterminable"]), len(out["history_restated"]), out["n_fit"],
                            out["n_syndicates_fit"], out["n_primary"]))
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
    w = out["widened"]
    print("  --- widened: %d left out (%d added: %s), %d fitted" % (
        w["n_left_out"], len(w["added_to_the_least_certain"]), ", ".join(w["added_to_the_least_certain"]), w["n_fit"]))
    sb = out["least_certain_and_widened_side_by_side"]
    for v, row in sb["fit"].items():
        print("  %-9s primary %.4f   least certain %.4f   widened %.4f" % (v, row["primary"], row["least_certain"],
                                                                         row["widened"]))
    for q, row in sb["vignette_centres"].items():
        print("  %-12s primary %.4f   least certain %.4f (%+.2f%%)   widened %.4f (%+.2f%%)"
              % (q, row["primary"], row["least_certain"], 100 * row["least_certain_relative_to_primary"],
                 row["widened"], 100 * row["widened_relative_to_primary"]))


if __name__ == "__main__":
    sys.exit(main())
