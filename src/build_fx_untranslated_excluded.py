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


#: The cells that show a development table retranslated (condition (a) fails), one entry per (record, reader) of the ten
#: records whose reason is table_retranslated: the two reports' page numbers ("pages": the year t report's, the year t-1
#: report's) and the pairs of cells compared. The build does not decide from a reader's prose (a negation such as "isn't
#: retranslated" or "nothing moved" cannot be told from a statement that cells moved by a pattern): `moved_cell_pairs`
#: accepts a table as retranslated only when the reader's check, in its own `cells_t` and `cells_t_minus_1`, holds the
#: cells below. A reading with no entry here, or whose cells do not bear its entry out, stops the build naming the record.
#:
#: A pair is (uy, age, series, a, side_t, b, side_t1): the underwriting year, the development age (0 = the end of the
#: underwriting year, 1 = one year later, ...), the series ("estimate", "paid", "gross", "net" or ""), the figure in the
#: year t report and its side, the figure in the year t-1 report and its side. A side is the reader's verbatim snippet
#: (an exact substring of that report's cells) that starts at the underwriting year and ends at the figure, for example
#: "UY2011 one year later 57.8"; when the reader lists unlabelled values by position the side is a dict
#: {"snippet", "run_start", "first_age", "quote"}: the snippet is the labelled run up to the figure, "run_start" is the
#: part of it before the list of values, "first_age" the age of the list's first value (0 = end of the underwriting year)
#: and "quote" the reader's own words (verbatim, one string or a tuple of them) that label a figure of the list at the
#: age its place implies or, where the reader labelled another row only, some figure with that first age. An entry with
#: fewer than three pairs carries "fewer_because", the reader's own words (verbatim) for it (1492/2017 X5 and Y5 and
#: 6119/2016 Y1: only one underwriting year precedes the year t-1 in the table). An entry whose row alignment is the
#: session's choice (1301/2016 X8) carries "alignment" (the session's note) and "alignment_quotes" (the reader's words,
#: verbatim). The snippets are taken from the archived readings (round2/readings/), never typed from memory.
MOVED_CELLS = {
    ("1301_2016", "X8"): {"pages": (40, 40), "pairs": (
        ("2011", 1, "",
         "57.8", "UY2011 one year later 57.8",
         "61.5", "UY2011 at end of underwriting year 65.8, one year later 61.5"),
        ("2012", 3, "",
         "54.7", "UY2012 one year later 55.1, two years later 56.1, three years later 54.7",
         "49.0", {"snippet": "UY2012 57.7, 50.2, 50.2, 49.0",
          "run_start": "UY2012 ", "first_age": 0,
          "quote": "age 3 is 54.7 vs 49.0"}),
        ("2013", 2, "",
         "85.3", "UY2013 one year later 88.8, two years later 85.3",
         "76.9", {"snippet": "UY2013 82.5, 81.3, 76.9",
          "run_start": "UY2013 ", "first_age": 0,
          "quote": "age 2 is 85.3 vs 76.9"}),
        ("2014", 1, "",
         "91.6", "UY2014 one year later 91.6",
         "81.9", {"snippet": "UY2014 87.3, 81.9",
          "run_start": "UY2014 ", "first_age": 0,
          "quote": "age 1 is 91.6 vs 81.9"}),
    ),
     "alignment": "decision of the Claude analysis session, 23 October 2026: the pairs take the cell at the age each report labels (UY2011 one year later 57.8 against one year later 61.5, and so on); the reader did not settle which alignment of the rows is the filing's (the 2016 rows look shifted by one development age against the 2015 rows), so the alignment is the session's choice, and the reader shows the cells differ under either alignment",
     "alignment_quotes": ("I did not find which alignment is right; either way no cell for UY2011 to UY2014 is unchanged.", "on that alignment the cells still differ by about 5 to 12%")},
    ("1301_2016", "Y8"): {"pages": (40, 40), "pairs": (
        ("2011", 4, "",
         "60.6", "2011 UY 'four years later' 60.6",
         "56.0", "2011 UY 'four years later' 56.0"),
        ("2012", 3, "",
         "54.7", "2012 UY 'three years later' 54.7",
         "49.0", "2012 UY 'three years later' 49.0"),
        ("2013", 2, "",
         "85.3", "2013 UY 'two years later' 85.3",
         "76.9", "2013 UY 'two years later' 76.9"),
        ("2014", 1, "",
         "91.6", "2014 UY 'one year later' 91.6",
         "81.9", "2014 UY 'one year later' 81.9"),
    )},
    ("1301_2017", "X1"): {"pages": (46, 40), "pairs": (
        ("2011", 1, "",
         "55.7", "UY2011 at end of UY 29.5, one year later 55.7",
         "57.8", {"snippet": "UY2011 30.4, 57.8",
          "run_start": "UY2011 ", "first_age": 0,
          "quote": "one year later 57.8 -> 55.7"}),
        ("2012", 2, "",
         "53.1", {"snippet": "UY2012 25.9, 52.0, 53.1",
          "run_start": "UY2012 ", "first_age": 0,
          "quote": "two years 56.1 -> 53.1"},
         "56.1", {"snippet": "UY2012 27.5, 55.1, 56.1",
          "run_start": "UY2012 ", "first_age": 0,
          "quote": "two years 56.1 -> 53.1"}),
        ("2013", 2, "",
         "80.8", {"snippet": "UY2013 49.9, 83.6, 80.8",
          "run_start": "UY2013 ", "first_age": 0,
          "quote": "two years 85.3 -> 80.8"},
         "85.3", {"snippet": "UY2013 53.6, 88.8, 85.3",
          "run_start": "UY2013 ", "first_age": 0,
          "quote": "two years 85.3 -> 80.8"}),
        ("2014", 1, "",
         "86.7", {"snippet": "UY2014 49.4, 86.7",
          "run_start": "UY2014 ", "first_age": 0,
          "quote": "one year 91.6 -> 86.7"},
         "91.6", {"snippet": "UY2014 52.2, 91.6",
          "run_start": "UY2014 ", "first_age": 0,
          "quote": "one year 91.6 -> 86.7"}),
    )},
    ("1301_2017", "Y1"): {"pages": (46, 40), "pairs": (
        ("2011", 0, "",
         "29.5", "UY2011: end of UY 29.5",
         "30.4", {"snippet": "UY2011: 30.4",
          "run_start": "UY2011: ", "first_age": 0,
          "quote": "end of UY 30.4 -> 29.5"}),
        ("2011", 1, "",
         "55.7", "UY2011: end of UY 29.5, one year later 55.7",
         "57.8", {"snippet": "UY2011: 30.4 / 57.8",
          "run_start": "UY2011: ", "first_age": 0,
          "quote": "end of UY 30.4 -> 29.5"}),
        ("2013", 0, "",
         "49.9", {"snippet": "UY2013: 49.9",
          "run_start": "UY2013: ", "first_age": 0,
          "quote": "end of UY 29.5"},
         "53.6", {"snippet": "UY2013: 53.6",
          "run_start": "UY2013: ", "first_age": 0,
          "quote": "end of UY 29.5"}),
        ("2014", 1, "",
         "86.7", {"snippet": "UY2014: 49.4 / 86.7",
          "run_start": "UY2014: ", "first_age": 0,
          "quote": "end of UY 29.5"},
         "91.6", {"snippet": "UY2014: 52.2 / 91.6",
          "run_start": "UY2014: ", "first_age": 0,
          "quote": "end of UY 29.5"}),
    )},
    ("1492_2017", "X5"): {"pages": (61, 57), "pairs": (
        ("2015", 0, "",
         "138", "YOA 2015 (the only underwriting year before t-1 = 2016): At end of underwriting year 138",
         "132", "YOA 2015: At end of underwriting year 132"),
        ("2015", 1, "",
         "3,857", "YOA 2015 (the only underwriting year before t-1 = 2016): At end of underwriting year 138; After one year 3,857",
         "4,202", "YOA 2015: At end of underwriting year 132; 12 months later 4,202"),
    ),
     "fewer_because": "Only two cells exist for the single underwriting year before t-1, so the three-cell minimum cannot be met"},
    ("1492_2017", "Y5"): {"pages": (61, 57), "pairs": (
        ("2015", 0, "",
         "138", "UY2015: 'At end of underwriting year' 138",
         "132", "UY2015 (2015 YOA): 'At end of underwriting year' 132"),
        ("2015", 1, "",
         "3,857", "UY2015: 'At end of underwriting year' 138; 'After one year' 3,857",
         "4,202", "UY2015 (2015 YOA): 'At end of underwriting year' 132; '12 months later' 4,202"),
    ),
     "fewer_because": "The table is short: only UY2015 is older than t-1 (2016), so only UY2015's cells are strictly 'before t-1'"},
    ("1884_2017", "X4"): {"pages": (34, 41), "pairs": (
        ("2015", 0, "estimate",
         "7,795", "UY2015 column, \xa3000: end of underwriting year (7,795)",
         "8,331", "UY2015 column, \xa3000: end of underwriting year (8,331)"),
        ("2015", 1, "estimate",
         "31,525", "UY2015 column, \xa3000: end of underwriting year (7,795); 12 months later (31,525)",
         "33,578", "UY2015 column, \xa3000: end of underwriting year (8,331); 12 months later (33,578)"),
        ("2015", 0, "paid",
         "841", "UY2015 column, \xa3000: end of underwriting year (7,795); 12 months later (31,525); cumulative claims paid at end of underwriting year (841)",
         "911", "UY2015 column, \xa3000: end of underwriting year (8,331); 12 months later (33,578); cumulative claims paid at end of underwriting year (911)"),
        ("2015", 1, "paid",
         "11,522", "UY2015 column, \xa3000: end of underwriting year (7,795); 12 months later (31,525); cumulative claims paid at end of underwriting year (841); 12 months later (11,522)",
         "12,206", "UY2015 column, \xa3000: end of underwriting year (8,331); 12 months later (33,578); cumulative claims paid at end of underwriting year (911); 12 months later (12,206)"),
    )},
    ("1884_2017", "Y4"): {"pages": (34, 41), "pairs": (
        ("2015", 0, "estimate",
         "7,795", "UY2015 (the only underwriting year before t-1 in the table): estimate At end of underwriting year (7,795)",
         "8,331", "UY2015: estimate At end of underwriting year (8,331)"),
        ("2015", 1, "estimate",
         "31,525", "UY2015 (the only underwriting year before t-1 in the table): estimate At end of underwriting year (7,795); 12 months later (31,525)",
         "33,578", "UY2015: estimate At end of underwriting year (8,331); 12 months later (33,578)"),
        ("2015", 0, "paid",
         "841", "UY2015 (the only underwriting year before t-1 in the table): estimate At end of underwriting year (7,795); 12 months later (31,525); cumulative paid At end of underwriting year (841)",
         "911", "UY2015: estimate At end of underwriting year (8,331); 12 months later (33,578); cumulative paid At end of underwriting year (911)"),
        ("2015", 1, "paid",
         "11,522", "UY2015 (the only underwriting year before t-1 in the table): estimate At end of underwriting year (7,795); 12 months later (31,525); cumulative paid At end of underwriting year (841); 12 months later (11,522)",
         "12,206", "UY2015: estimate At end of underwriting year (8,331); 12 months later (33,578); cumulative paid At end of underwriting year (911); 12 months later (12,206)"),
    )},
    ("3902_2023", "X3"): {"pages": (31, 31), "pairs": (
        ("2021", 1, "",
         "31,227", "UY2021 1 year 31,227",
         "32,735", "UY2021 1 year 32,735"),
        ("2021", 2, "",
         "81,243", "UY2021 1 year 31,227, 2 years 81,243",
         "85,562", "UY2021 1 year 32,735, 2 years 85,562"),
        ("2020", 1, "",
         "36,868", "UY2020 1 year 36,868",
         "38,238", "UY2020 1 year 38,238"),
        ("2019", 1, "",
         "23,147", "UY2019 1 year 23,147",
         "24,200", "UY2019 1 year 24,200"),
    )},
    ("3902_2023", "Y3"): {"pages": (31, 31), "pairs": (
        ("2017", 1, "",
         "35,618", {"snippet": "2017: 35,618",
          "run_start": "2017: ", "first_age": 1,
          "quote": "age 1 37,474 -> 35,618"},
         "37,474", {"snippet": "2017: 37,474",
          "run_start": "2017: ", "first_age": 1,
          "quote": "age 1 37,474 -> 35,618"}),
        ("2017", 2, "",
         "57,768", {"snippet": "2017: 35,618 / 57,768",
          "run_start": "2017: ", "first_age": 1,
          "quote": "age 1 37,474 -> 35,618"},
         "60,500", {"snippet": "2017: 37,474 / 60,500",
          "run_start": "2017: ", "first_age": 1,
          "quote": "age 1 37,474 -> 35,618"}),
        ("2018", 1, "",
         "29,252", {"snippet": "2018: 29,252",
          "run_start": "2018: ", "first_age": 1,
          "quote": "age 1 30,712 -> 29,252"},
         "30,712", {"snippet": "2018: 30,712",
          "run_start": "2018: ", "first_age": 1,
          "quote": "age 1 30,712 -> 29,252"}),
        ("2019", 1, "",
         "23,147", {"snippet": "2019: 23,147",
          "run_start": "2019: ", "first_age": 1,
          "quote": "age 1 24,200 -> 23,147"},
         "24,200", {"snippet": "2019: 24,200",
          "run_start": "2019: ", "first_age": 1,
          "quote": "age 1 24,200 -> 23,147"}),
        ("2020", 1, "",
         "36,868", {"snippet": "2020: 36,868",
          "run_start": "2020: ", "first_age": 1,
          "quote": "age 1 38,238 -> 36,868"},
         "38,238", {"snippet": "2020: 38,238",
          "run_start": "2020: ", "first_age": 1,
          "quote": "age 1 38,238 -> 36,868"}),
    )},
    ("4020_2016", "X5"): {"pages": (42, 44), "pairs": (
        ("2013", 1, "",
         "111,919", "UY2013: 1 year 111,919",
         "96,728", "UY2013: 1 year 96,728"),
        ("2013", 2, "",
         "216,866", "UY2013: 1 year 111,919; 2 years 216,866",
         "186,101", "UY2013: 1 year 96,728; 2 years 186,101"),
        ("2012", 1, "",
         "116,352", "UY2012: 1 year 116,352",
         "100,745", "UY2012: 1 year 100,745"),
        ("2012", 3, "",
         "184,586", "UY2012: 1 year 116,352; 2 years 178,273; 3 years 184,586",
         "158,531", "UY2012: 1 year 100,745; 2 years 153,397; 3 years 158,531"),
        ("2011", 1, "",
         "102,660", "UY2011: 1 year 102,660",
         "88,920", "UY2011: 1 year 88,920"),
    )},
    ("4020_2016", "Y5"): {"pages": (42, 44), "pairs": (
        ("2013", 1, "",
         "111,919", "UY2013 col 1 year 111,919",
         "96,728", "UY2013 col 1 year 96,728"),
        ("2013", 3, "",
         "227,010", "UY2013 col 1 year 111,919; 2 years 216,866; 3 years 227,010",
         "194,261", "UY2013 col 1 year 96,728; 2 years 186,101; 3 years 194,261"),
        ("2012", 4, "",
         "183,681", "UY2012 col 1 year 116,352; 2 years 178,273; 3 years 184,586; 4 years 183,681",
         "157,611", "UY2012 col 1 year 100,745; 2 years 153,397; 3 years 158,531; 4 years 157,611"),
        ("2011", 2, "",
         "182,455", "UY2011 col 1 year 102,660; 2 years 182,455",
         "158,760", "UY2011 col 1 year 88,920; 2 years 158,760"),
    )},
    ("5678_2016", "X1"): {"pages": (41, 41), "pairs": (
        ("2014", 0, "estimate",
         "962", "UY2014: estimate at end of UY 962",
         "859", "UY2014: estimate at end of UY 859"),
        ("2014", 1, "estimate",
         "2,362", "UY2014: estimate at end of UY 962; 12 months later 2,362",
         "2,051", "UY2014: estimate at end of UY 859; 12 months later 2,051"),
        ("2014", 0, "paid",
         "19", "UY2014: estimate at end of UY 962; 12 months later 2,362; cumulative paid at end of UY 19",
         "16", "UY2014: estimate at end of UY 859; 12 months later 2,051; cumulative paid at end of UY 16"),
        ("2014", 1, "paid",
         "515", "UY2014: estimate at end of UY 962; 12 months later 2,362; cumulative paid at end of UY 19; at 12 months 515",
         "441", "UY2014: estimate at end of UY 859; 12 months later 2,051; cumulative paid at end of UY 16; at 12 months 441"),
    )},
    ("5678_2016", "Y1"): {"pages": (41, 41), "pairs": (
        ("2014", 0, "estimate",
         "962", "UY2014: end of UY 962",
         "859", "UY2014: end of UY 859"),
        ("2014", 1, "estimate",
         "2,362", "UY2014: end of UY 962, 12 months later 2,362",
         "2,051", "UY2014: end of UY 859, 12 months later 2,051"),
        ("2014", 0, "paid",
         "19", {"snippet": "paid UY2014 19",
          "run_start": "paid UY2014 ", "first_age": 0,
          "quote": "end of UY 962"},
         "16", {"snippet": "paid UY2014 16",
          "run_start": "paid UY2014 ", "first_age": 0,
          "quote": "end of UY 962"}),
        ("2014", 1, "paid",
         "515", {"snippet": "paid UY2014 19 / 515",
          "run_start": "paid UY2014 ", "first_age": 0,
          "quote": "12 months 441 -> 515"},
         "441", {"snippet": "paid UY2014 16 / 441",
          "run_start": "paid UY2014 ", "first_age": 0,
          "quote": "12 months 441 -> 515"}),
    )},
    ("5820_2016", "X3"): {"pages": (42, 25), "pairs": (
        ("2011", 0, "",
         "44.7", "UY2011: end of UY 44.7",
         "38.7", {"snippet": "UY2011: 38.7",
          "run_start": "UY2011: ", "first_age": 0,
          "quote": "end of UY 44.7"}),
        ("2011", 1, "",
         "77.6", "UY2011: end of UY 44.7, one year later 77.6",
         "66.9", {"snippet": "UY2011: 38.7, 66.9",
          "run_start": "UY2011: ", "first_age": 0,
          "quote": "end of UY 44.7"}),
        ("2012", 0, "",
         "27.4", {"snippet": "UY2012: 27.4",
          "run_start": "UY2012: ", "first_age": 0,
          "quote": "end of UY 44.7"},
         "24.0", {"snippet": "UY2012: 24.0",
          "run_start": "UY2012: ", "first_age": 0,
          "quote": "end of UY 44.7"}),
        ("2013", 0, "",
         "18.4", {"snippet": "UY2013: 18.4",
          "run_start": "UY2013: ", "first_age": 0,
          "quote": "end of UY 44.7"},
         "16.4", {"snippet": "UY2013: 16.4",
          "run_start": "UY2013: ", "first_age": 0,
          "quote": "end of UY 44.7"}),
        ("2014", 0, "",
         "15.9", {"snippet": "UY2014: 15.9",
          "run_start": "UY2014: ", "first_age": 0,
          "quote": "end of UY 44.7"},
         "13.8", {"snippet": "UY2014: 13.8",
          "run_start": "UY2014: ", "first_age": 0,
          "quote": "end of UY 44.7"}),
    )},
    ("5820_2016", "Y3"): {"pages": (42, 25), "pairs": (
        ("2011", 0, "",
         "44.7", {"snippet": "2011: 44.7",
          "run_start": "2011: ", "first_age": 0,
          "quote": "age 0: 38.7 -> 44.7"},
         "38.7", {"snippet": "2011: 38.7",
          "run_start": "2011: ", "first_age": 0,
          "quote": "age 0: 38.7 -> 44.7"}),
        ("2011", 1, "",
         "77.6", {"snippet": "2011: 44.7 / 77.6",
          "run_start": "2011: ", "first_age": 0,
          "quote": "age 0: 38.7 -> 44.7"},
         "66.9", {"snippet": "2011: 38.7 / 66.9",
          "run_start": "2011: ", "first_age": 0,
          "quote": "age 0: 38.7 -> 44.7"}),
        ("2012", 0, "",
         "27.4", {"snippet": "2012: 27.4",
          "run_start": "2012: ", "first_age": 0,
          "quote": "age 0: 24.0 -> 27.4"},
         "24.0", {"snippet": "2012: 24.0",
          "run_start": "2012: ", "first_age": 0,
          "quote": "age 0: 24.0 -> 27.4"}),
        ("2013", 0, "",
         "18.4", {"snippet": "2013: 18.4",
          "run_start": "2013: ", "first_age": 0,
          "quote": "age 0: 16.4 -> 18.4"},
         "16.4", {"snippet": "2013: 16.4",
          "run_start": "2013: ", "first_age": 0,
          "quote": "age 0: 16.4 -> 18.4"}),
        ("2014", 0, "",
         "15.9", {"snippet": "2014: 15.9",
          "run_start": "2014: ", "first_age": 0,
          "quote": "age 0: 13.8 -> 15.9"},
         "13.8", {"snippet": "2014: 13.8",
          "run_start": "2014: ", "first_age": 0,
          "quote": "age 0: 13.8 -> 15.9"}),
    )},
    ("5820_2017", "X4"): {"pages": (41, 42), "pairs": (
        ("2011", 0, "",
         "42.0", "UY2011: end of underwriting year 42.0",
         "44.7", "UY2011: end 44.7"),
        ("2011", 5, "",
         "62.6", "UY2011: end of underwriting year 42.0; one year later 72.1; two years later 61.8; three 59.3; four 60.9; five 62.6",
         "66.4", "UY2011: end 44.7; one year later 77.6; two years later 65.8; three 63.0; four 64.5; five 66.4"),
        ("2012", 1, "",
         "43.1", "UY2012: end 25.7; one year 43.1",
         "45.2", "UY2012: end 27.4; one year 45.2"),
        ("2013", 0, "",
         "17.4", "UY2013 end 17.4",
         "18.4", "UY2013 end 18.4"),
        ("2014", 0, "",
         "14.9", "UY2014 end 14.9",
         "15.9", "UY2014 end 15.9"),
        ("2015", 1, "",
         "43.7", "UY2015 end 13.5; one year later 43.7",
         "45.7", "UY2015 end 14.3; one year later 45.7"),
    )},
    ("5820_2017", "Y4"): {"pages": (41, 42), "pairs": (
        ("2011", 0, "",
         "42.0", "UY2011 At end 42.0",
         "44.7", {"snippet": "UY2011 44.7",
          "run_start": "UY2011 ", "first_age": 0,
          "quote": "end 42.0 vs 44.7"}),
        ("2011", 5, "",
         "62.6", "UY2011 At end 42.0 / one year later 72.1 / two years 61.8 / three 59.3 / four 60.9 / five 62.6",
         "66.4", {"snippet": "UY2011 44.7 / 77.6 / 65.8 / 63.0 / 64.5 / 66.4",
          "run_start": "UY2011 ", "first_age": 0,
          "quote": "end 42.0 vs 44.7"}),
        ("2012", 0, "",
         "25.7", {"snippet": "UY2012 25.7",
          "run_start": "UY2012 ", "first_age": 0,
          "quote": "end 42.0"},
         "27.4", {"snippet": "UY2012 27.4",
          "run_start": "UY2012 ", "first_age": 0,
          "quote": "end 42.0"}),
        ("2012", 1, "",
         "43.1", {"snippet": "UY2012 25.7 / 43.1",
          "run_start": "UY2012 ", "first_age": 0,
          "quote": "one year later 43.1 vs 45.2"},
         "45.2", {"snippet": "UY2012 27.4 / 45.2",
          "run_start": "UY2012 ", "first_age": 0,
          "quote": "one year later 43.1 vs 45.2"}),
        ("2013", 0, "",
         "17.4", {"snippet": "UY2013 17.4",
          "run_start": "UY2013 ", "first_age": 0,
          "quote": "end 17.4 vs 18.4"},
         "18.4", {"snippet": "UY2013 18.4",
          "run_start": "UY2013 ", "first_age": 0,
          "quote": "end 17.4 vs 18.4"}),
        ("2014", 0, "",
         "14.9", {"snippet": "UY2014 14.9",
          "run_start": "UY2014 ", "first_age": 0,
          "quote": "end 14.9 vs 15.9"},
         "15.9", {"snippet": "UY2014 15.9",
          "run_start": "UY2014 ", "first_age": 0,
          "quote": "end 14.9 vs 15.9"}),
    )},
    ("6119_2016", "X1"): {"pages": (31, 31), "pairs": (
        ("2014", 1, "gross",
         "5,290", "UY2014: 12 months 5,290",
         "4,423", "UY2014: After 12 months 4,423"),
        ("2014", 2, "gross",
         "10,455", "UY2014: 12 months 5,290; 24 months 10,455",
         "8,715", "UY2014: After 12 months 4,423; After 24 months 8,715"),
        ("2014", 1, "net",
         "4,703", "UY2014: 12 months 5,290; 24 months 10,455; Net: 12 months 4,703",
         "3,936", {"snippet": "UY2014: After 12 months 4,423; After 24 months 8,715; Net: 3,936",
          "run_start": "UY2014: After 12 months 4,423; After 24 months 8,715; Net: ", "first_age": 1,
          "quote": ("12 months 4,703", "3,936 -> 4,703")}),
        ("2014", 2, "net",
         "9,233", "UY2014: 12 months 5,290; 24 months 10,455; Net: 12 months 4,703; 24 months 9,233",
         "7,699", {"snippet": "UY2014: After 12 months 4,423; After 24 months 8,715; Net: 3,936; 7,699",
          "run_start": "UY2014: After 12 months 4,423; After 24 months 8,715; Net: ", "first_age": 1,
          "quote": ("12 months 4,703", "3,936 -> 4,703")}),
    )},
    ("6119_2016", "Y1"): {"pages": (31, 31), "pairs": (
        ("2014", 1, "gross",
         "5,290", "UY2014: 12 months 5,290",
         "4,423", "UY2014: After 12 months 4,423"),
        ("2014", 2, "gross",
         "10,455", "UY2014: 12 months 5,290; 24 months 10,455",
         "8,715", "UY2014: After 12 months 4,423; After 24 months 8,715"),
    ),
     "fewer_because": "Only one underwriting year (2014) precedes t-1 in this small syndicate, so there are two like-for-like cells for it plus the UY2015 cell."},
}
MIN_PAIRS = 3
MONTH = r"(?:January|February|March|April|May|June|July|August|September|October|November|December)"
_FIG = r"(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?"
_FIGURE = r"(?<![\d.,])(%s)(?!\d|[.,]\d)" % _FIG
FIGURE = re.compile(_FIGURE)
#: the words a reader's cell label uses for a development age (0 = the end of the underwriting year)
AGE_WORDS = (
    (0, ("end of underwriting year", "end of UY", "end")),
    (1, ("one year later", "one year", "1 year", "12 months later", "12 months")),
    (2, ("two years later", "two years", "2 years", "24 months later", "24 months")),
    (3, ("three years later", "three years", "three", "3 years", "36 months later", "36 months")),
    (4, ("four years later", "four years", "four", "4 years", "48 months later", "48 months")),
    (5, ("five years later", "five years", "five", "5 years", "60 months later", "60 months")),
)
_AGE_OF = {w.lower(): a for a, ws in AGE_WORDS for w in ws}
_LABEL = r"(?<![\w])(age\s\d+|%s)" % "|".join(
    re.escape(w) for w in sorted(_AGE_OF, key=len, reverse=True))
_AGE_AFTER = re.compile(r"(?:\s*(?:months?|years?|yrs?)\b)")
_YEAR_MARK = re.compile(r"(?<![\w])(?:UY|YOA)\s?(\d{4})(?!\d)|(?<![\w.,])(\d{4})\s*:|(?<![\w])(\d{4})\s(?:UY|YOA)\b")
_LABELLED = re.compile(_LABEL + r"['\")]*[\s:]*(?:is\s+)?" + _FIGURE + r"(?:\s*(?:->|vs\.?)\s*" + _FIGURE + r")?",
                       re.IGNORECASE)
_ARROW = re.compile(_FIGURE + r"\s*(?:->|vs\.?)\s*" + _FIGURE)
_RUN = re.compile(r"^\s*(%s)(?:\s*[/;,]\s*(%s))*\s*$" % (_FIG, _FIG))


def _plain(figure):
    """A printed figure without its thousands separators ('3,857' -> '3857'; '42.0' stays '42.0')."""
    return figure.replace(",", "")


def _unit(figure):
    """One unit in the last printed place of a figure: the most that rounding alone can move it by."""
    f = _plain(figure)
    return 10.0 ** -(len(f.split(".")[1]) if "." in f else 0)


def _age_of_label(label):
    label = label.strip().lower()
    m = re.fullmatch(r"age\s(\d+)", label)
    return int(m.group(1)) if m else _AGE_OF.get(label)


def _strings(obj):
    """Every string in a reader's check (its values, however nested)."""
    if isinstance(obj, str):
        return [obj]
    if isinstance(obj, dict):
        return [s for v in obj.values() for s in _strings(v)]
    if isinstance(obj, (list, tuple)):
        return [s for v in obj for s in _strings(v)]
    return []


def _verbatim(quotes, strings):
    """The quotes (a string or a tuple of them), when each is non-empty and an exact substring of a string of the check."""
    quotes = (quotes,) if isinstance(quotes, str) else quotes
    if not isinstance(quotes, tuple) or not quotes:
        return None
    if any(not isinstance(q, str) or not q.strip() or not any(q in s for s in strings) for q in quotes):
        return None
    return quotes


def year_marks(text):
    """[(position, year)] of the underwriting-year markers in a text: 'UY2011', 'YOA 2011', '2011 UY' or a row label
    '2011:'. A year after a month name or inside a date (31 December 2015) is not one."""
    out = []
    for m in _YEAR_MARK.finditer(text):
        pre = text[:m.start()]
        if re.search(MONTH + r"\s+$", pre, re.IGNORECASE) or re.search(r"\d[/.-]$", pre):
            continue
        out.append((m.start(), next(g for g in m.groups() if g)))
    return out


def trailing_age(prefix):
    """The development age of the label a text ends with ('... one year later ', "... 'After 12 months' "), or None."""
    m = re.search(_LABEL + r"$", prefix.rstrip(" \t:'\"("), re.IGNORECASE)
    return None if m is None else _age_of_label(m.group(1))


def labelled_ages(quotes):
    """{figure: {ages}} the reader's quotes give: a figure that follows an age label ('one year later 57.8',
    'age 3 is 54.7 vs 49.0', both figures of a 'x -> y' or 'x vs y' take the label), and a figure beside a labelled one
    in an arrow ('(3,936 -> 4,703)')."""
    ages = {}
    for q in quotes:
        for m in _LABELLED.finditer(q):
            age = _age_of_label(m.group(1))
            if age is not None:
                for fig in (m.group(2), m.group(3)):
                    if fig:
                        ages.setdefault(fig, set()).add(age)
    for _ in range(2):
        for q in quotes:
            for m in _ARROW.finditer(q):
                x, y = m.group(1), m.group(2)
                ages.setdefault(x, set()).update(ages.get(y, ()))
                ages.setdefault(y, set()).update(ages.get(x, ()))
    return ages


def _side_found(text, strings, uy, age, series, fig, side):
    """True when one side of a pair is the reader's own snippet, in this report's cells, for this underwriting year, age
    and figure (see MOVED_CELLS)."""
    spec = {"snippet": side} if isinstance(side, str) else side
    if not isinstance(spec, dict) or not isinstance(spec.get("snippet"), str) or not isinstance(text, str):
        return False
    snip = spec["snippet"]
    if not snip or not FIGURE.fullmatch(fig):
        return False
    # (a) the snippet is the reader's, in this report's cells, and its last figure is a whole figure there: not part of a
    # longer number and not an age label ('12 months')
    if not re.search(re.escape(snip) + r"(?![\d]|[.,]\d)(?!%s)" % _AGE_AFTER.pattern, text):
        return False
    # (b) it names this underwriting year, and only this one, as an underwriting year (not a year in a date)
    marks = year_marks(snip)
    if not marks or {y for _, y in marks} != {uy}:
        return False
    # (b) it ends with the figure; that the figure is a whole one (157.8 is not 57.8) follows from the label before it or
    # from the list of values it ends
    core = snip[:-1] if snip.endswith(")") else snip
    if not core.endswith(fig):
        return False
    prefix = core[:-len(fig)]
    low = snip.lower()
    if series == "paid" and "paid" not in low:
        return False
    if series == "net" and "net" not in low:
        return False
    if series in ("estimate", "gross") and re.search(r"\b(paid|net)\b", low):
        return False
    if "run_start" not in spec:
        # labelled: the label just before the figure is this pair's age
        return trailing_age(prefix) == age
    # positional: the snippet is run_start and a list of unlabelled values; the figure's place in the list is its age
    start, first_age = spec["run_start"], spec.get("first_age")
    if not isinstance(start, str) or not isinstance(first_age, int) or isinstance(first_age, bool):
        return False
    if not snip.startswith(start):
        return False
    tail = start.rstrip()
    if re.search(r"[/;,]$", tail) or re.search(r"(?<![\w])%s$" % _FIG, tail):
        return False
    run = snip[len(start):]
    if not _RUN.match(run):
        return False
    tokens = [m.group(1) for m in FIGURE.finditer(run)]
    if not tokens or tokens[-1] != fig or first_age + len(tokens) - 1 != age:
        return False
    # the first age is the reader's, not ours: the reader's own words (verbatim) label a figure of the list at the age its
    # place implies, or label some figure with the first age
    quotes = _verbatim(spec.get("quote"), strings)
    if quotes is None:
        return False
    given = labelled_ages(quotes)
    return (any(first_age + i in given.get(tok, ()) for i, tok in enumerate(tokens))
            or any(first_age in ages for ages in given.values()))


def comparison_made(check):
    """True when a reader's retranslation check compared cells of the year t-1 and year t reports: `checked` is true or
    begins 'yes'. 'partly', 'no: ...', false and an absent check are not a comparison (no year t-1 table to compare)."""
    if not isinstance(check, dict):
        return False
    c = check.get("checked")
    return c is True or (isinstance(c, str) and c.strip().lower().startswith("yes"))


def moved_cell_pairs(check, evidence):
    """The pairs of `evidence` (a MOVED_CELLS entry) that differ by more than rounding, when the reader's check supports
    the entry; [] otherwise. The decision never reads the check's prose. It needs:

      * a check that compared cells (comparison_made);
      * the check's own `cells_t` and `cells_t_minus_1`, as text, each naming the entry's page (p<N>);
      * for every pair, on each side, the reader's snippet as an exact substring of that report's cells (not the other's),
        which names the pair's underwriting year, and only that year, as an underwriting year (UY2011, YOA 2011, '2011:';
        not a year in a date), and ends with the pair's figure as a whole figure (not part of a longer number, not an age
        label such as '12 months') under the pair's development age: a label just before the figure, or, for unlabelled
        values listed by position, the figure's place in the list counted from the age of its first value, with the
        reader's own words (verbatim) labelling a figure of the list at its place's age or some figure with the first
        age; the series of the pair ('paid', 'net') must
        be in the snippet and an 'estimate' or 'gross' pair must not name paid or net. One pair that is not found rejects
        the entry. The two snippets of a pair name the same underwriting year and age because each is tied to the pair's;
      * at least three pairs, or "fewer_because" in the entry, the reader's own words for fewer (verbatim);
      * "alignment_quotes", where the entry has them, verbatim;
      * at least one pair whose figures differ by more than one unit in the last printed place (rounding alone cannot
        move a figure by more than that).

    What is not checked: that the reader read the filing's cell correctly (the snippet is the reader's), that an unlabelled
    list's first value is at the age the entry says (the reader's words must label a figure of that list at its place's
    age, or some figure with that first age, which may be in another row), and which of two alignments of a shifted table
    is the filing's (the entry says so; 1301/2016 X8)."""
    if not comparison_made(check) or not isinstance(evidence, dict) or not evidence.get("pairs"):
        return []
    t_text, t1_text = check.get("cells_t"), check.get("cells_t_minus_1")
    if not isinstance(t_text, str) or not isinstance(t1_text, str):
        return []
    page_t, page_t1 = evidence["pages"]
    if not (re.search(r"(?<![\w])p%d(?!\d)" % page_t, t_text) and re.search(r"(?<![\w])p%d(?!\d)" % page_t1, t1_text)):
        return []
    strings = _strings(check)
    pairs = evidence["pairs"]
    if len(pairs) < MIN_PAIRS and _verbatim(evidence.get("fewer_because"), strings) is None:
        return []
    if "alignment_quotes" in evidence and (_verbatim(evidence["alignment_quotes"], strings) is None
                                           or not str(evidence.get("alignment", "")).strip()):
        return []
    moved = []
    for pair in pairs:
        if not isinstance(pair, tuple) or len(pair) != 7:
            return []
        uy, age, series, a, side_t, b, side_t1 = pair
        if not (_side_found(t_text, strings, uy, age, series, a, side_t)
                and _side_found(t1_text, strings, uy, age, series, b, side_t1)):
            return []
        if abs(float(_plain(a)) - float(_plain(b))) > max(_unit(a), _unit(b)) + 1e-9:
            moved.append((uy, age, a, b))
    return moved


def shows_moved_cells(check, evidence):
    """True when `moved_cell_pairs` finds at least one pair of cells that moved."""
    return bool(moved_cell_pairs(check, evidence))


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
    if reason == "table_retranslated":
        unshown = [r["reader"] for r in reads
                   if not shows_moved_cells(r["table_retranslated_check"], MOVED_CELLS.get((key, r["reader"])))]
        if unshown:
            raise SystemExit("%s: a line of %s%% of R and a verdict 'keep', but reader %s's retranslation check does not "
                             "give cells of the year t and year t-1 reports (same underwriting years and ages) that differ "
                             "by more than rounding, as MOVED_CELLS records them: condition (a) is not shown to fail, so "
                             "rule B would exclude the record" % (key, pct, ", ".join(unshown)))
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
    retranslated = {(k, r["reader"]) for k in keys2 if out["read_and_kept"][k]["reason"] == "table_retranslated"
                    for r in out["read_and_kept"][k]["readings"]}
    if retranslated != set(MOVED_CELLS):
        raise SystemExit("MOVED_CELLS holds %s, not the readings of the table_retranslated records %s" % (
            sorted(set(MOVED_CELLS) ^ retranslated), sorted(retranslated)))
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
