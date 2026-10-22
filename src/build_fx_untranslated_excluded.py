r"""Build data/fx_untranslated_excluded.json: the records the primary sample leaves for the exchange-rate rule.

The author's decision of 22 October 2026 (rule B). A record leaves the PRIMARY sample when

  (a) its development table is not retranslated between the year t-1 and year t reports across a sterling/dollar move
      of 5% or more (the cells for years before t-1 are the same in the year-t report as in the year t-1 report, so
      the step from the t-1 diagonal to the t diagonal carries the translation of the foreign-currency part of the
      book), AND
  (b) the filing's own gross claims-outstanding roll-forward prints an exchange line of at least 5% of the opening
      gross claims outstanding R.

The population screened is the 13 candidates of results/extraction_error_rate/mature-cohort/fx-translation/
fx_translation.json (written by fx-translation/measure_fx_translation.py: the primary sample's 653 records, 37 with a table not retranslated, 18
of those in a year sterling moved 5% or more against the dollar, and of those 3 with a placed exchange line of 5% or
more and 10 with no placed line), each read twice, independently, from the filing (readers F1 and F2). Both readers
agree on every record. The register holds the four records both conditions hold for ("excluded") and the nine that
were read and kept ("read_and_kept"), each with both readings' pages, quotes, figures and percentage.

Round 2 (23 October 2026) adds 97 records to "read_and_kept", each read twice, independently, by an X-arm and a Y-arm
reader (archived under round2/readings/): no record is excluded, and four (457/2015, 1301/2015, 4711/2017, 6105/2015)
are kept as 'undeterminable_kept' (decision of the Claude analysis session).

The readings are archived verbatim in results/extraction_error_rate/mature-cohort/fx-translation/readings/F1.json
and F2.json (their parts 2 and 3, the aggregated column of 1945 and the outward transfers of 2689/2022 and
1492/2023, are used by build_mature_cohort_figures.py and by data/outbound_transfer_retained_base.json).

Usage:
  python src/build_fx_untranslated_excluded.py            # check the register against a rebuild; exit 1 on a difference
  python src/build_fx_untranslated_excluded.py --write    # rebuild and write the register
"""
import io
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
REGISTER = HERE / "data" / "fx_untranslated_excluded.json"
READINGS = HERE / "results" / "extraction_error_rate" / "mature-cohort" / "fx-translation" / "readings"
READERS = ("F1", "F2")
THRESHOLD_PCT = 5.0

#: the records read and the author's verdict on each (the rule applied to both readers' figures)
EXCLUDED = ("1897_2016", "2468_2016", "5151_2016", "5151_2017")
KEPT = ("218_2017", "1301_2023", "1686_2018", "1971_2023", "2468_2017", "4242_2016", "4242_2017", "4242_2018",
        "5151_2018")

#: the five records the script placed an exchange line for, under 5% (fx-translation/measure_fx_translation.py; a pattern placement,
#: not a reading, and not read twice)
SCREENED_UNDER_5 = {"1686_2023": 2.03, "2019_2023": 0.03, "2689_2022": 0.26, "4242_2022": 0.14, "4242_2023": 0.30}

RULE = (
    "The author's decision of 22 October 2026 (rule B). A record leaves the PRIMARY sample (outcome 'mature_cohort') "
    "when (a) its development table is not retranslated between the year t-1 and year t reports across a "
    "sterling/dollar move of 5% or more, so that the step from the t-1 diagonal to the t diagonal carries the "
    "translation of the foreign-currency part of the book, AND (b) the filing's own gross claims-outstanding "
    "roll-forward prints an exchange line of at least 5% of the opening gross claims outstanding R (absolute value). "
    "A record for which either condition fails stays. The loader (run_analysis.py) removes an 'excluded' entry's "
    "record from the primary at the unusable-severity step with the tag FX_UNTRANSLATED_TABLE and counts it "
    "(fx_untranslated_excluded); under outcome 'precedence_672' the register is not read and nothing changes. An entry "
    "is applied only with two independent readings of the filing (F1, F2) that give the same opening gross claims "
    "outstanding and the same exchange line, a table not retranslated, a line of at least 5% of R, and the pages and "
    "quotes. 'read_and_kept' entries record the candidates both readers found to fail a condition; the loader "
    "validates them and applies nothing for them. A kept entry states its reason: no_fx_line_printed, "
    "fx_line_under_5pct, table_retranslated (a line of 5% or more of R, and the table retranslated), or "
    "undeterminable_kept (a line of 5% or more of R and no year t-1 table to test condition (a): rule B excludes a "
    "record only when both conditions are shown, so it stays). Built by src/build_fx_untranslated_excluded.py from the archived "
    "readings.")

POPULATION = {
    "screen": ("results/extraction_error_rate/mature-cohort/fx-translation/fx_translation.json (measure_fx_translation"
               ".py), over the primary sample's 653 records at bed49ee"),
    "records": 653,
    "table_not_retranslated": 37,
    "of_those_in_a_year_sterling_moved_5pct_or_more": 18,
    "of_those_with_a_placed_exchange_line_of_5pct_or_more": ["2468_2016", "5151_2016", "5151_2017"],
    "of_those_with_a_placed_line_under_5pct_not_read_twice": SCREENED_UNDER_5,
    "of_those_with_no_placed_line_candidates_read_twice": ["218_2017", "1301_2023", "1686_2018", "1897_2016",
                                                           "1971_2023", "2468_2017", "4242_2016", "4242_2017",
                                                           "4242_2018", "5151_2018"],
    "candidates_read_twice": 13,
    "candidates_read_twice_are": sorted(EXCLUDED + KEPT, key=lambda k: tuple(int(p) for p in k.split("_"))),
    "readers": "F1 and F2, each reading the filings independently (the readings archived under readings/)",
    "note": ("The five records with a placed line under 5% are the script's pattern placement of the roll-forward's "
             "first exchange amount as a share of R, shown here as the script printed it; they were not read twice. "
             "A pattern placement is not a reading, but its figure is under half the threshold in each case."),
}

#: the decisions that are the Claude analysis session's own, on top of the author's rule
SESSION_NOTE = {
    "1897_2016": (
        "decision of the Claude analysis session, 22 October 2026: the line is labelled 'Effect of FX and other "
        "movements', not an exchange line alone, and it is treated as exchange, because retranslating R at the "
        "filing's printed year-end rates (USD 1.47 to 1.24, p22) gives about 14.3m of the 13.8m line (both readers "
        "make the same calculation: 77.314 x (1.47/1.24 - 1))"),
    "5151_2016": (
        "the functional currency changed to US dollars on 1 January 2016 (p20, p25) and the 2016 report amends the "
        "t-1 diagonal (p44); both readers record this beside the verdict, and both point the same way as the "
        "exclusion"),
}


#: Round 2 (23 October 2026): the 97 records the first round did not read, each read twice, independently, by an X-arm
#: and a Y-arm reader (round2/readings/X1..X8.json, Y1..Y8.json): the primary sample's records with no grid comparison in
#: a year when GBP/USD moved 5% or more, and the five whose pattern-matched line was under 5%. All are kept.
ROUND2 = HERE / "results" / "extraction_error_rate" / "mature-cohort" / "round2"
ROUND2_READERS = tuple("%s%d" % (arm, i) for arm in "XY" for i in range(1, 9))
ROUND2_TASK = "exchange_line"
ROUND2_RECORDS = 97
#: the records condition (b) holds for (a gross exchange line of 5% or more of R) and condition (a) cannot be tested,
#: because there is no year t-1 development table to compare (decision of the Claude analysis session, 23 October
#: 2026): rule B excludes a record only when both conditions are shown, so they stay. They are DERIVED from the readers'
#: verdicts and checks (kept_reason): a reader who says 'undeterminable', or a reader whose retranslation check did not
#: compare cells of the year t-1 and year t reports. The four so derived are 457/2015, 1301/2015 (one reader 'keep' on the
#: table's stated closing-rate basis), 4711/2017 and 6105/2015. UNDETERMINABLE_NOTE is the session's prose for each; a
#: derived record without a note stops the build.
UNDETERMINABLE_NOTE = {
    "457_2015": ("the 2014 report prints no claims development table, so condition (a) cannot be tested on cells; the "
                 "2015 table states 'Balances have been translated at exchange rates prevailing at 31 December 2015 in "
                 "all cases' and the 2016 report prints the 2011 column retranslated (X6, Y7), which points to "
                 "retranslation but is not a comparison of cells of the year t-1 and year t reports"),
    "1301_2015": ("no year t-1 report table exists; the table states 'Balances have been translated at exchange rates "
                  "prevailing at 31 December 2015 in all cases' (p40) and the 2016 report prints different 2011 cells "
                  "(Y7); the line is 5.008% of R, 7.7 thousand pounds over the threshold (X7)"),
    "4711_2017": ("the 2016 report is not in the corpus; the 2017 table states translation at the 31 December 2017 "
                  "rate, as the 2015 and 2018 reports state theirs (X5, Y5), which points to retranslation but is not a "
                  "comparison of cells"),
    "6105_2015": ("the 2014 report prints no claims development table and the 2015 table states no exchange basis (the "
                  "policy note gives closing rates, p19); the line is 5.11% of R (X6, Y6)"),
}


def load_reader(rid):
    with io.open(READINGS / ("%s.json" % rid), encoding="utf-8") as fh:
        return json.load(fh)


def load_round2():
    """{key: [X reading, Y reading]} from the archived round-2 files: every '<key>|exchange_line' entry, the X arm's
    first."""
    out = {}
    for rid in ROUND2_READERS:
        with io.open(ROUND2 / "readings" / ("%s.json" % rid), encoding="utf-8") as fh:
            data = json.load(fh)
        for name, e in data.items():
            if name.endswith("|" + ROUND2_TASK):
                out.setdefault(e["key"], []).append((rid, e))
    return out


def _ints(vals):
    return [p for p in vals if isinstance(p, int) and not isinstance(p, bool)]


def round2_pages(key, pages):
    """(the year t filing's pages, the other filings' pages by name, the free-text items) from a round-2 reader's
    `pages`: a list for the record's own filing (with the odd note as a string), or a dict keyed by filing."""
    if isinstance(pages, dict):
        own, other = [], {}
        for name, vals in pages.items():
            vals = vals if isinstance(vals, list) else [vals]
            if name.endswith(key):
                own += _ints(vals)
            elif _ints(vals):
                other[name] = _ints(vals)
        return own, other, []
    return _ints(pages), {}, [p for p in pages if isinstance(p, str)]


def _cell(c, own_pages, what):
    """{value_m, page, quote} of an R or fx_line cell of a round-2 reading; 'none printed' stays as no value."""
    if isinstance(c, dict):
        page = c.get("page")
        if not isinstance(page, int) or isinstance(page, bool):
            raise SystemExit("%s: page %r is not a page number" % (what, page))
        return {"value_m": c["value_m"], "page": page, "quote": c["quote"]}
    return {"value_m": None, "page": None, "quote": str(c)}


def reading_r2(rid, key, e):
    """One round-2 reader's reading of an exchange-line record, in the form the F1 and F2 readings take."""
    own, other, notes = round2_pages(key, e["pages"])
    if not own:
        raise SystemExit("%s: reader %s names no page of the year t filing" % (key, rid))
    r_open = _cell(e["R"], own, "%s %s R" % (key, rid))
    line = _cell(e["fx_line"], own, "%s %s fx_line" % (key, rid))
    if line["value_m"] is None:
        line["quote"] = "%s; pages searched: %s" % (line["quote"], ", ".join(str(p) for p in e["pages_searched"]))
    pct = e.get("fx_line_pct_of_R")
    out = {
        "reader": rid,
        "pages": own,
        "pages_of_the_earlier_report": other,
        "read_by": e["read_by"],
        "report_currency": e["report_currency"],
        "opening_gross_claims_outstanding": r_open,
        "fx_line_gross": line,
        "fx_line_pct_of_opening": pct if isinstance(pct, (int, float)) else None,
        "pages_searched": e["pages_searched"],
        "table_retranslated_check": e.get("retranslation"),
        "verdict": e["verdict"],
        "note": e["note"],
    }
    if notes:
        out["pages_notes"] = notes
    return out


#: a sentence of a reader's check that says cells moved or the table was retranslated ...
MOVED = re.compile(r"\b(?:moved|retranslated)\b", re.I)
#: ... unless it says they did not (a negation immediately before the word: 'not retranslated', 'no cells moved')
NOT_MOVED = re.compile(r"\b(?:not|no|never|without|none)\b(?:\W+\w+)?\W+(?:moved|retranslated)\b", re.I)
SENTENCE = re.compile(r"(?<=[.;:])\s+|\n")


def comparison_made(check):
    """True when a reader's retranslation check compared cells of the year t-1 and year t reports: `checked` is true or
    begins 'yes'. 'partly', 'no: ...', false and an absent check are not a comparison (no year t-1 table to compare)."""
    if not isinstance(check, dict):
        return False
    c = check.get("checked")
    return c is True or (isinstance(c, str) and c.strip().lower().startswith("yes"))


def _texts(x):
    if isinstance(x, str):
        yield x
    elif isinstance(x, dict):
        for v in x.values():
            for t in _texts(v):
                yield t
    elif isinstance(x, list):
        for v in x:
            for t in _texts(v):
                yield t


def shows_moved_cells(check, note=""):
    """True when a reader's check is a comparison (comparison_made) and the check, or the reader's note beside it, says
    in some sentence that the cells moved or the table was retranslated, without a negation before the word."""
    if not comparison_made(check):
        return False
    return any(MOVED.search(s) and not NOT_MOVED.search(s) for t in list(_texts(check)) + [note or ""]
               for s in SENTENCE.split(t))


def kept_reason(line_m, pct, reads):
    """The reason a round-2 record stays, from the readers' figures, verdicts and checks:

      * no_fx_line_printed: no exchange line (condition (b) fails);
      * fx_line_under_5pct: the line is under 5% of R in absolute value (condition (b) fails);
      * undeterminable_kept: a line of 5% or more of R and a reader who says 'undeterminable', or whose check did not
        compare cells of the two reports (no year t-1 table): condition (a) cannot be tested, so rule B keeps the record;
      * table_retranslated: a line of 5% or more of R and both readers' checks compared cells and show them moved
        (condition (a) fails).
    A line of 5% or more of R whose table both readers compared and did NOT find moved is a record rule B excludes, and
    stops the build."""
    if line_m is None:
        return "no_fx_line_printed"
    if abs(pct) < THRESHOLD_PCT:
        return "fx_line_under_5pct"
    checks = [r["table_retranslated_check"] for r in reads]
    if any(r["verdict"] == "undeterminable" for r in reads) or not all(comparison_made(c) for c in checks):
        return "undeterminable_kept"
    return "table_retranslated"


def entry_r2(key, reads, move):
    """The read_and_kept entry of a round-2 record: both readers agree on R, the exchange line and the percentage, and
    the record stays (nothing in round 2 is excluded)."""
    r1, r2 = reads
    open_m = r1["opening_gross_claims_outstanding"]["value_m"]
    line_m = r1["fx_line_gross"]["value_m"]
    for r in reads:
        if abs(r["opening_gross_claims_outstanding"]["value_m"] - open_m) > 0.0015:
            raise SystemExit("%s: the readers disagree on R" % key)
        v = r["fx_line_gross"]["value_m"]
        if (v is None) != (line_m is None):
            raise SystemExit("%s: the readers disagree on the exchange line" % key)
        if v is not None and abs(v - line_m) > 0.0015:
            if abs(abs(v) - abs(line_m)) > 0.0015:
                raise SystemExit("%s: the readers disagree on the exchange line" % key)
            # the two readers read the printed line with opposite signs (a roll-forward that prints liabilities as
            # negative); the magnitude is the same and the 5% test uses the absolute value, so the entry takes the first
            # reader's sign and the second reading keeps the value it read beside it
            r["fx_line_gross"] = dict(r["fx_line_gross"], value_m=line_m, printed_value_m=v,
                                      sign_note="read with the opposite sign by this reader; the entry takes the "
                                                "first reader's sign (the test is on the absolute value)")
        if line_m is not None and r["fx_line_pct_of_opening"] is not None and abs(
                r["fx_line_pct_of_opening"] - 100.0 * line_m / open_m) > 0.02:
            raise SystemExit("%s: reader %s's percentage %s is not the line over R" % (
                key, r["reader"], r["fx_line_pct_of_opening"]))
        if r["verdict"] == "exclude":
            raise SystemExit("%s: a reader says exclude; round 2 excludes nothing" % key)
    pct = pct_of(line_m, open_m)
    verdicts = sorted({r["verdict"] for r in reads})
    reason = kept_reason(line_m, pct, reads)
    if reason == "undeterminable_kept":
        if not set(verdicts) <= {"keep", "undeterminable"}:
            raise SystemExit("%s: verdicts %s" % (key, verdicts))
        if key not in UNDETERMINABLE_NOTE:
            raise SystemExit("%s: condition (a) cannot be tested from the readers' verdicts and checks, and the session "
                             "has no note for it (UNDETERMINABLE_NOTE)" % key)
    elif verdicts != ["keep"]:
        raise SystemExit("%s: reason %s with verdicts %s" % (key, reason, verdicts))
    if reason == "table_retranslated" and not all(shows_moved_cells(r["table_retranslated_check"], r["note"])
                                                  for r in reads):
        raise SystemExit("%s: a line of %s%% of R and a verdict 'keep', but %s: condition (a) is not shown to fail, so "
                         "rule B would exclude the record" % (
                             key, pct, "reader %s's retranslation check does not show moved cells" % ", ".join(
                                 r["reader"] for r in reads if not shows_moved_cells(r["table_retranslated_check"], r["note"]))))
    pages = sorted({p for r in reads for p in r["pages"]})
    quote = " | ".join("reader %s, p%s: %s" % (r["reader"], r["opening_gross_claims_outstanding"]["page"],
                                                r["opening_gross_claims_outstanding"]["quote"]) for r in reads)
    quote += " || " + " | ".join(
        "reader %s, p%s: %s" % (r["reader"], r["fx_line_gross"]["page"], r["fx_line_gross"]["quote"]) for r in reads)
    e = {
        "report_currency": r1["report_currency"],
        "opening_gross_claims_outstanding_m": open_m,
        "fx_line_gross_m": line_m,
        "fx_line_pct_of_opening": pct,
        "gbp_usd_move_in_year_t": move,
        "pages": pages,
        "quote": quote,
        "readings": [r1, r2],
        "round": "round 2 of 23 October 2026 (X and Y arms)",
        "reason": reason,
    }
    base = "read twice (X and Y arms, round 2 of 23 October 2026) and kept in the primary sample under the author's rule B (decision of 22 October 2026): "
    if reason == "no_fx_line_printed":
        e["decision"] = base + "the gross claims-outstanding roll-forward prints no exchange line, so condition (b) fails"
    elif reason == "fx_line_under_5pct":
        e["decision"] = base + ("the gross exchange line is %.2f%% of the opening gross claims outstanding (absolute "
                                "value under 5%%), so condition (b) fails" % pct)
    elif reason == "table_retranslated":
        e["table_retranslated"] = True
        e["decision"] = base + ("the gross exchange line is %.2f%% of the opening gross claims outstanding (absolute "
                                "value at least 5%%), so condition (b) holds, but both readers find the development "
                                "table retranslated between the year t-1 and year t reports across a GBP/USD move of "
                                "%.1f%%, so condition (a) fails" % (pct, 100.0 * move))
    else:
        e["table_retranslated"] = None
        e["decision"] = (
            "decision of the Claude analysis session, 23 October 2026, because rule B excludes a record only when both "
            "conditions are shown: the gross exchange line is %.2f%% of the opening gross claims outstanding "
            "(absolute value at least 5%%), so condition (b) holds, and condition (a) cannot be tested, because no "
            "year t-1 development table is available to compare; the record stays in the primary sample" % pct)
        e["session_decision"] = UNDETERMINABLE_NOTE[key]
    return e


def _pick(e, *names):
    for n in names:
        if n in e:
            return e[n]
    return None


def year_pages(key, pages):
    """The year-t filing's pages (ints), and the other filing's, from a reader's `pages` (a dict keyed by filing, or a
    list for the record's own filing)."""
    if isinstance(pages, dict):
        own = [p for p in pages.get(key, []) if isinstance(p, int)]
        other = {k: [p for p in v if isinstance(p, int)] for k, v in pages.items() if k != key}
        return own, {k: v for k, v in other.items() if v}
    return [p for p in pages if isinstance(p, int)], {}


def reading(rid, key, e):
    """One reader's reading of a candidate, normalised across the two readers' field names."""
    own, other = year_pages(key, e["pages"])
    r_open = _pick(e, "opening_gross_claims_outstanding_R", "opening_R")
    line = _pick(e, "fx_line_gross", "fx_line")
    out = {
        "reader": rid,
        "pages": own,
        "pages_of_the_earlier_report": other,
        "read_by": e["read_by"],
        "report_currency": e["report_currency"],
        "functional_currency": e["functional_currency"],
        "opening_gross_claims_outstanding": {k: r_open[k] for k in ("value_m", "page", "quote")},
        "fx_line_gross": ({k: line.get(k) for k in ("value_m", "page", "quote")} if isinstance(line, dict)
                          else {"value_m": None, "page": None, "quote": line}),
        "fx_line_pct_of_opening": _pick(e, "fx_line_pct_of_R"),
        "table_retranslated": e["retranslated"],
        "cells_compared": _pick(e, "cell_comparison", "cells_compared"),
        "table_exchange_basis": e["table_exchange_basis"],
        "rate_move": e["rate_move"],
        "verdict": e["verdict"],
        "note": e["note"],
    }
    return out


def pct_of(line_m, opening_m):
    return None if line_m is None else round(100.0 * line_m / opening_m, 2)


def entry_for(key, reads):
    r1, r2 = reads
    open_m = r1["opening_gross_claims_outstanding"]["value_m"]
    line_m = r1["fx_line_gross"]["value_m"]
    for r in reads:
        if r["opening_gross_claims_outstanding"]["value_m"] != open_m or r["fx_line_gross"]["value_m"] != line_m:
            raise SystemExit("%s: the readers disagree on R or the exchange line" % key)
        if r["verdict"] != reads[0]["verdict"]:
            raise SystemExit("%s: the readers disagree on the verdict" % key)
    verdict = r1["verdict"]
    if (key in EXCLUDED) != (verdict == "exclude"):
        raise SystemExit("%s: the readers' verdict %r does not match the register's list" % (key, verdict))
    pct = pct_of(line_m, open_m)
    if (verdict == "exclude") != (pct is not None and abs(pct) >= THRESHOLD_PCT):
        raise SystemExit("%s: verdict %s against a line of %s%% of R" % (key, verdict, pct))
    pages = sorted({p for r in reads for p in r["pages"]})
    quote = " | ".join("reader %s, p%s: %s" % (r["reader"], r["opening_gross_claims_outstanding"]["page"],
                                                r["opening_gross_claims_outstanding"]["quote"]) for r in reads)
    quote += " || " + " | ".join(
        "reader %s, p%s: %s" % (r["reader"], r["fx_line_gross"]["page"], r["fx_line_gross"]["quote"]) for r in reads)
    e = {
        "report_currency": r1["report_currency"],
        "opening_gross_claims_outstanding_m": open_m,
        "fx_line_gross_m": line_m,
        "fx_line_pct_of_opening": pct,
        "pages": pages,
        "quote": quote,
        "readings": [r1, r2],
    }
    if verdict == "exclude":
        e["table_retranslated"] = False
        e["decision"] = (
            "the author's rule B (decision of 22 October 2026), applied to two independent readings of the filing "
            "(F1, F2): the development table is not retranslated across a sterling/dollar move of 5%% or more, and "
            "the gross claims-outstanding roll-forward prints an exchange line of %s%% of the opening gross claims "
            "outstanding (absolute value at least 5%%), so the record leaves the primary sample; the 672 "
            "sensitivity keeps it" % ("%.1f" % (100.0 * line_m / open_m)))
        if key in SESSION_NOTE:
            e["session_decision"] = SESSION_NOTE[key]
    else:
        e["reason"] = "no_fx_line_printed" if line_m is None else "fx_line_under_5pct"
        e["decision"] = (
            "read twice (F1, F2) and kept in the primary sample under the author's rule B (decision of 22 October "
            "2026): %s" % (
                "the gross claims-outstanding roll-forward prints no exchange line, so condition (b) fails"
                if line_m is None else
                "the gross exchange line is %.2f%% of the opening gross claims outstanding (absolute value under "
                "5%%), so condition (b) fails" % pct))
    return e


def round2_moves():
    """{key: GBP/USD move in year t} from the archived round-2 batches (the record's own field in the measurement)."""
    out = {}
    for rid in ROUND2_READERS:
        with io.open(ROUND2 / "batches" / ("%s.json" % rid), encoding="utf-8") as fh:
            for rec in json.load(fh):
                if rec["task"] == ROUND2_TASK:
                    out[rec["key"]] = rec["gbp_usd_move_in_year_t"]
    return out


def sort_key(k):
    return tuple(int(p) for p in k.split("_"))


def build():
    data = {rid: load_reader(rid) for rid in READERS}
    pop = json.loads(json.dumps(POPULATION))
    r2 = load_round2()
    moves = round2_moves()
    if len(r2) != ROUND2_RECORDS or set(r2) != set(moves):
        raise SystemExit("round 2 holds %d records read and %d in the batches, not %d" % (len(r2), len(moves),
                                                                                         ROUND2_RECORDS))
    keys2 = sorted(r2, key=sort_key)
    pop["round2"] = round2_population(keys2)
    pop["note"] += (" The five were read twice in round 2 (X and Y arms, 23 October 2026), with the other 92 records "
                    "of that round; see round2.")
    out = {"_rule": RULE, "_population": pop, "excluded": {}, "read_and_kept": {}}
    for bucket, keys in (("excluded", EXCLUDED), ("read_and_kept", KEPT)):
        for key in sorted(keys, key=sort_key):
            reads = [reading(rid, key, data[rid][key]) for rid in READERS]
            out[bucket][key] = entry_for(key, reads)
    for key in keys2:
        if key in out["excluded"] or key in out["read_and_kept"]:
            raise SystemExit("%s was read in both rounds" % key)
        pairs = sorted(r2[key], key=lambda p: p[0])
        if [p[0][0] for p in pairs] != ["X", "Y"]:
            raise SystemExit("%s: round 2 needs one X-arm and one Y-arm reading, got %s" % (key, [p[0] for p in pairs]))
        out["read_and_kept"][key] = entry_r2(key, [reading_r2(rid, key, e) for rid, e in pairs], moves[key])
    counts = {}
    for key in keys2:
        reason = out["read_and_kept"][key]["reason"]
        counts[reason] = counts.get(reason, 0) + 1
    pop["round2"]["reasons"] = dict(sorted(counts.items()))
    undet = [k for k in keys2 if out["read_and_kept"][k]["reason"] == "undeterminable_kept"]
    if set(UNDETERMINABLE_NOTE) != set(undet):
        raise SystemExit("the session's notes %s are not the records derived undeterminable %s" % (
            sorted(UNDETERMINABLE_NOTE, key=sort_key), undet))
    # keep the key order of the committed register (undeterminable_kept sits before undeterminable_kept_why)
    ordered = {}
    for name, val in pop["round2"].items():
        ordered[name] = val
        if name == "outcome":
            ordered["undeterminable_kept"] = undet
    pop["round2"] = ordered
    return out


def round2_population(keys2):
    """The _population entry of round 2: how the records were chosen, what the readers found."""
    return {
        "records_read_twice": len(keys2),
        "chosen_as": ("the primary sample's records for which the screen (fx-translation/measure_fx_translation.py) "
                      "found no grid comparison in a year when GBP/USD moved 5% or more (cells class "
                      "'no_comparison'), and the five records whose pattern-matched exchange line was under 5% "
                      "(listed above, read here for the first time by two readers)"),
        "readers": "X1-X8 and Y1-Y8, two independent arms, each record read once in each arm (archived under "
                   "round2/readings/; the brief round2/briefs/brief_r2.md; the batches round2/batches/)",
        "outcome": ("no record is excluded: the reason of each is recorded in its entry (no_fx_line_printed, "
                    "fx_line_under_5pct, table_retranslated, undeterminable_kept)"),
        "undeterminable_kept_why": ("condition (b) holds and no year t-1 development table is available to test "
                                    "condition (a); decision of the Claude analysis session, 23 October 2026, because "
                                    "rule B excludes a record only when both conditions are shown"),
        "records_are": keys2,
    }


def dumps(reg):
    return json.dumps(reg, indent=1, ensure_ascii=False) + "\n"


def main(argv):
    text = dumps(build())
    if "--write" in argv:
        with io.open(REGISTER, "w", encoding="utf-8", newline="") as fh:
            fh.write(text)
        print("wrote %s" % REGISTER.relative_to(HERE))
        return 0
    with io.open(REGISTER, encoding="utf-8", newline="") as fh:
        committed = fh.read()
    if committed != text:
        print("data/fx_untranslated_excluded.json differs from its rebuild: run with --write and read the diff")
        return 1
    print("data/fx_untranslated_excluded.json equals its rebuild")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
