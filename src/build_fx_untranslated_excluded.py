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

Round 5 (23 October 2026, the readings of the tables whose history moved between reports, archived under
round5/readings/) adds 3000/2022 to "excluded" under rule 2 of the round-5 decision rules (round5/rules.md), which is the
author's rule B: both readers (P2, Q1) find the 2022 table's history retranslated while its end-2021 reserves are not
(incurred and cumulative paid lifted by the same amount in every column, so the end-(t-1) diagonal mixes exchange
bases), and the gross claims-outstanding roll-forward's exchange line, 91,879, is 8.0% of the opening 1,146,474 (note 17,
p42). The readers' own verdict is restated_base; "exclude" is rule B applied to their facts (decision of the Claude
analysis session). Each figure and page is a verbatim snippet of the archived reading (ROUND5_SNIPPETS), checked here.

What the cells gate proves (moved_cell_pairs, which accepts a table as retranslated for the 10 records of reason
table_retranslated) and what it does not is written in GATE and into data/fx_untranslated_excluded_evidence.json as
_moved_cells_gate (not into the register, a hashed input of the run identifier that the loader reads): it proves that
each figure is quoted verbatim from the reader's own cells, tied to a year-marked row and a labelled or cross-anchored
age, and moved beyond rounding; it does not prove that free-text notes can be parsed into a table. The alignment of the
unlabelled lists rests on the two independent readers and was checked by hand, for all 20 readings, by reviews 4 and 5
(23 October 2026). The evidence file also holds, for the 10 records, how each reading's sides were tied to its cells
(moved_cells), keyed like the register. The loader does not read it.

The readings are archived verbatim in results/extraction_error_rate/mature-cohort/fx-translation/readings/F1.json
and F2.json (their parts 2 and 3, the aggregated column of 1945 and the outward transfers of 2689/2022 and
1492/2023, are used by build_mature_cohort_figures.py and by data/outbound_transfer_retained_base.json).

Usage:
  python src/build_fx_untranslated_excluded.py            # check the register and the evidence file against a rebuild;
                                                          # exit 1 on a difference
  python src/build_fx_untranslated_excluded.py --write    # rebuild and write both
"""
import io
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
REGISTER = HERE / "data" / "fx_untranslated_excluded.json"
#: the cells gate's record and the provenance of the cells, keyed like the register; not read by the loader and not hashed
EVIDENCE = HERE / "data" / "fx_untranslated_excluded_evidence.json"
#: the keys the register never holds (they are the evidence file's)
EVIDENCE_ONLY_KEYS = ("_moved_cells_gate", "moved_cells")
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
    "is applied only with two independent readings of the filing (F1, F2; P2, Q1 for the round-5 record) that give "
    "the same opening gross claims "
    "outstanding and the same exchange line, a table not retranslated, a line of at least 5% of R, and the pages and "
    "quotes. 'read_and_kept' entries record the candidates both readers found to fail a condition; the loader "
    "validates them and applies nothing for them. A kept entry states its reason: no_fx_line_printed, "
    "fx_line_under_5pct, table_retranslated (a line of 5% or more of R, and the table retranslated), or "
    "undeterminable_kept (a line of 5% or more of R and no year t-1 table to test condition (a): rule B excludes a "
    "record only when both conditions are shown, so it stays). Built by src/build_fx_untranslated_excluded.py from the "
    "archived readings.")

#: the sentence about the cells gate that belongs after RULE. It is NOT in the register: the register is a hashed input of
#: the run identifier (run_analysis.py, source_files_for_hash) and keeps the bytes it had before the gate was recorded.
#: It is written into the evidence file, with GATE and the provenance of the cells.
RULE_ADDITION = ("A table is accepted as retranslated only through the cells gate described in _moved_cells_gate (what it "
                 "proves and what it does not).")

#: what the gate that accepts a table as retranslated (moved_cell_pairs) proves and does not prove; written into the
#: evidence file (data/fx_untranslated_excluded_evidence.json) as _moved_cells_gate, not into the register
GATE = {
    "proves": (
        "For each of the 10 records whose reason is table_retranslated, for each of its two readers (20 readings), every "
        "figure the finding rests on is quoted verbatim from the reader's own cells text of the year t report or of the "
        "year t-1 report (an exact substring of that report's cells, not of the other's); it is tied to a row marked with "
        "one underwriting year (the snippet starts at the year marker, names no other year and holds no 'prior', "
        "'earlier' or 'total' row), to a development age (a label just before the figure or, for a list of unlabelled "
        "values, a first age anchored by the reader's own words under that year's marker, in one row of the pair's series "
        "with no row break to a part that is not an age label, no other year number and no prior/earlier/total, or by the "
        "other arm's reading of the same filing, page, underwriting year, series and figure) and to a series (paid or net "
        "named in the snippet or the words before it back to the row's start; none named for the gross estimate); no "
        "figure is a percentage, an age label or part of a longer number, and no snippet is read from inside a "
        "parenthesis; at least three different cells (with '', 'estimate' and 'gross' one series, and no two pairs on one "
        "cell) or the reader's own reason for fewer are compared, all of underwriting years before t-1; and at least one "
        "pair differs by more than one unit in the last printed place, so that rounding alone cannot account for the "
        "move."),
    "does_not_prove": (
        "That free-text notes can be parsed into a table. The readers' cells are notes, not a parsed table: a list of "
        "unlabelled values is put into the columns of the filing's table by the readers' own labels, and the alignment "
        "rests on the two independent readers (the X-arm and the Y-arm) and on the hand check recorded here. The gate does "
        "not prove that either reader read a printed cell correctly (the filings' page images are not re-read by it), nor "
        "which of two alignments of the shifted 2016 rows of 1301/2016 X8 is the filing's (the entry records that as the "
        "analysis session's choice). Two limits found by review 6 (23 October 2026) remain, because refusing them would "
        "need a parse of the readers' notes that the notes do not support: (1) attack 9 D, a quote that anchors a "
        "list is tied to its year only through the last year marker before it in the reader's text, and the words between "
        "the marker and the quote are held to be one row of the pair's series; a row of another kind that no row break, "
        "year number, prior/earlier/total or paid/net word sets off from that marker (an unmarked row or another report's "
        "row joined to it by a comma) is not told apart; (2) attack A2, a figure that the reader quotes from another "
        "report inside the year t cells is refused when it stands inside a parenthesis, but not when the reader writes it "
        "with no parenthesis and no break before it."),
    "checked_by_hand": {
        "readings": 20,
        "reviews": ["review 4 of 23 October 2026", "review 5 of 23 October 2026"],
        "what": ("each of the 20 readings (10 records, two readers each) was compared by hand with the reader's cells: "
                 "that the figure, underwriting year, age and series of every pair are the cell's own"),
    },
}

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


#: Round 5 (23 October 2026): the records rule 2 of the round-5 decision rules excludes, each with two readings. Every
#: field is a verbatim snippet of the archived reading (round5/readings/<reader>.json), from which the build takes the
#: figure, and the page the snippet names (or the reader's own pages field names for that note).
ROUND5 = HERE / "results" / "extraction_error_rate" / "mature-cohort" / "round5"
ROUND5_SNIPPETS = {
    "3000_2022": {
        "P2": {
            "opening": (25, "balance sheet 'Claims outstanding 17 | 1,310,517 | 1,146,474' (p25)", "1,146,474"),
            "fx_line": (42, "Note 17 (p42): 'Movement in provision 72,164' and 'Movement due to foreign exchange "
                            "91,879'", "91,879"),
            "not_retranslated": "the paid history was re-stated up by about 8% (2013 paid ratio 1.0800), the reserve "
                                "part was not retranslated",
            "mixed_cells": "in the 2022 table the end-2021 incurred cells and the end-2021 cumulative paid cells are both "
                           "higher than the 2021 print by the SAME amount, column by column (2013: incurred 333,693 vs "
                           "313,157 = +20,536; paid (277,147) vs (256,611) = +20,536; 2014: 270,950 vs 251,173 = +19,777 "
                           "and (230,948) vs (211,170) = +19,778; 2020: 324,795 vs 318,487 = +6,308 and (72,406) vs "
                           "(66,099) = +6,307; 2021: 120,673 vs 120,156 = +517 and (7,806) vs (7,289) = +517)",
        },
        "Q1": {
            "opening": (42, "note 17 'Movement due to foreign exchange 91,879' on opening gross provisions of 1,146,474 "
                            "(8.0%)", "1,146,474"),
            "fx_line": (42, "note 17 'Movement due to foreign exchange 91,879' on opening gross provisions of 1,146,474 "
                            "(8.0%)", "91,879"),
            "not_retranslated": "So paid history was lifted (about +7% to +10% by UY) but the end-2021 outstanding was "
                                "left at the 2021 amounts, whereas the end-2022 diagonal is at 2022 rates",
            "mixed_cells": "in every column the 2022 table's end-2021 incurred and cumulative paid are both higher than "
                           "the 2021 report's by the SAME amount, so the implied provision (incurred less paid) at "
                           "end-2021 is unchanged",
        },
    },
}
ROUND5_RULE = ("rule 2 of the round-5 decision rules (decision of the Claude analysis session, 23 October 2026), which "
               "is the author's rule B (22 October 2026)")


def load_round5():
    """{key: [(reader, entry)]} of ROUND5_SNIPPETS's records, from the archived round-5 readings."""
    out = {}
    for key, readers in ROUND5_SNIPPETS.items():
        for rid in readers:
            with io.open(ROUND5 / "readings" / ("%s.json" % rid), encoding="utf-8") as fh:
                out.setdefault(key, []).append((rid, json.load(fh)[key]))
    return out


def _r5_figure(text, rid, key, what, snippet, figure, page, own_pages):
    if snippet not in text:
        raise SystemExit("%s: reader %s's %s snippet is not in the archived reading" % (key, rid, what))
    if figure not in snippet:
        raise SystemExit("%s: reader %s's %s figure %s is not in its snippet" % (key, rid, what, figure))
    if ("p%d" % page) not in snippet and ("p.%d" % page) not in json.dumps(own_pages):
        raise SystemExit("%s: reader %s's %s page %d is named neither in its snippet nor in its pages" % (key, rid,
                                                                                                         what, page))
    return {"value_m": round(float(figure.replace(",", "")) / 1000.0, 3), "page": page, "quote": snippet}


def reading_r5(rid, key, e):
    """One round-5 reading of a rule-2 record, in the register's reading form (the fields the loader checks), built from
    the verbatim snippets of ROUND5_SNIPPETS."""
    text = json.dumps(e, ensure_ascii=False)
    snip = ROUND5_SNIPPETS[key][rid]
    for what in ("not_retranslated", "mixed_cells"):
        if snip[what] not in text:
            raise SystemExit("%s: reader %s's %s snippet is not in the archived reading" % (key, rid, what))
    pages = e["pages"]
    own = sorted({p for name, v in pages.items() if not name.startswith("prev") and "prev" not in name
                  for p in ([v] if isinstance(v, int) else v if isinstance(v, list)
                            else [int(x) for x in re.findall(r"p\.?(\d+)", v)])})
    opening = _r5_figure(text, rid, key, "opening", snip["opening"][1], snip["opening"][2], snip["opening"][0], pages)
    line = _r5_figure(text, rid, key, "exchange line", snip["fx_line"][1], snip["fx_line"][2], snip["fx_line"][0],
                      pages)
    return {
        "reader": rid,
        "source": "results/extraction_error_rate/mature-cohort/round5/readings/%s.json" % rid,
        "pages": own,
        "pages_as_read": pages,
        "read_by": e["read_by"],
        "opening_gross_claims_outstanding": opening,
        "fx_line_gross": line,
        "fx_line_pct_of_opening": pct_of(line["value_m"], opening["value_m"]),
        "table_retranslated": False,
        "table_exchange_basis": snip["not_retranslated"],
        "cells_compared": snip["mixed_cells"],
        "reader_verdict": e["verdict"],
        "verdict": "exclude",
        "verdict_by": ("%s, applied to this reading's facts: the reader's own round-5 verdict is %s" % (ROUND5_RULE,
                                                                                                    e["verdict"])),
        "note": e["note"],
    }


def entry_r5(key, reads):
    """The 'excluded' entry of a round-5 rule-2 record: both readings give the same R and exchange line, a table whose
    history is retranslated while its end-(t-1) reserves are not, and a line of at least 5% of R."""
    r1 = reads[0]
    for r in reads:
        if (r["opening_gross_claims_outstanding"]["value_m"] != r1["opening_gross_claims_outstanding"]["value_m"]
                or r["fx_line_gross"]["value_m"] != r1["fx_line_gross"]["value_m"]):
            raise SystemExit("%s: the round-5 readers disagree on R or the exchange line" % key)
    open_m, line_m = r1["opening_gross_claims_outstanding"]["value_m"], r1["fx_line_gross"]["value_m"]
    pct = pct_of(line_m, open_m)
    if abs(pct) < THRESHOLD_PCT:
        raise SystemExit("%s: a line of %s%% of R is under the threshold" % (key, pct))
    quote = " | ".join("reader %s, p%s: %s" % (r["reader"], r["opening_gross_claims_outstanding"]["page"],
                                                r["opening_gross_claims_outstanding"]["quote"]) for r in reads)
    quote += " || " + " | ".join("reader %s, p%s: %s" % (r["reader"], r["fx_line_gross"]["page"],
                                                          r["fx_line_gross"]["quote"]) for r in reads)
    return {
        "report_currency": "GBP",
        "opening_gross_claims_outstanding_m": open_m,
        "fx_line_gross_m": line_m,
        "fx_line_pct_of_opening": pct,
        "pages": sorted({p for r in reads for p in r["pages"]}),
        "quote": quote,
        "readings": reads,
        "table_retranslated": False,
        "decision": ("%s, applied to two independent readings of the filing (round 5: %s): the development table's "
                     "history is retranslated while its end-(t-1) reserves are not, so the step from the t-1 diagonal "
                     "to the t diagonal carries the translation of the reserves, and the gross claims-outstanding "
                     "roll-forward prints an exchange line of %.1f%% of the opening gross claims outstanding (absolute "
                     "value at least 5%%), so the record leaves the primary sample; the 672 sensitivity keeps it"
                     % (ROUND5_RULE, ", ".join(r["reader"] for r in reads), pct)),
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
#: underwriting year, 1 = one year later, ...; a table whose first column is '12 months' or '1 year', as 6119/2016 and
#: 3902/2023 print, has no age 0 and its first column is age 1), the series ("estimate", "paid", "gross", "net" or "";
#: "" is read as estimate or gross: its snippets name neither paid nor net), the figure in the year t report and its
#: side, the figure in the year t-1 report and its side. A side is the reader's verbatim snippet (an exact substring of
#: that report's cells) that starts at the underwriting year's marker (after an optional series word) and ends at the
#: figure, for example "UY2011 one year later 57.8"; when the reader lists unlabelled values by position the side is a
#: dict {"snippet", "run_start", "first_age", "anchor", "quote"}: the snippet is the run up to the figure, "run_start" is
#: the part of it before the list of values (it ends with the year marker or a series word), "first_age" the age of the
#: list's first value, and "anchor" what fixes that first age: "place_label" (the default; "quote" is the reader's own
#: words, verbatim, one string or a tuple of them, that label a figure of the list at the age its place implies, under
#: this underwriting year's marker, in one row of the pair's series) or "other_arm" (the other arm's reading of the same
#: filing, page, underwriting year, series and figure gives the figure at this age: 1301/2017 Y1, 5678/2016 Y1, 5820/2016
#: X3, 5820/2017 Y4). Nothing else anchors a list: a label of another row, of another underwriting year or series, or after
#: a row break, anchors nothing. ("row_label", a labelled later value of the same row, was removed in review 6: no entry
#: used it.) "first_age" is 0 or more. A series is '', 'estimate', 'gross' (one gross estimate: two pairs on one
#: underwriting year, age and gross cell are refused), 'paid' or 'net'. An entry with fewer than three different cells carries
#: "fewer_because", the reader's own words (verbatim) for it (1492/2017 X5 and Y5 and 6119/2016 Y1: only one
#: underwriting year precedes the year t-1 in the table). An entry whose row alignment is the
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
          "anchor": "other_arm"},
         "53.6", {"snippet": "UY2013: 53.6",
          "run_start": "UY2013: ", "first_age": 0,
          "anchor": "other_arm"}),
        ("2014", 1, "",
         "86.7", {"snippet": "UY2014: 49.4 / 86.7",
          "run_start": "UY2014: ", "first_age": 0,
          "anchor": "other_arm"},
         "91.6", {"snippet": "UY2014: 52.2 / 91.6",
          "run_start": "UY2014: ", "first_age": 0,
          "anchor": "other_arm"}),
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
          "anchor": "other_arm"},
         "16", {"snippet": "paid UY2014 16",
          "run_start": "paid UY2014 ", "first_age": 0,
          "anchor": "other_arm"}),
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
          "anchor": "other_arm"}),
        ("2011", 1, "",
         "77.6", "UY2011: end of UY 44.7, one year later 77.6",
         "66.9", {"snippet": "UY2011: 38.7, 66.9",
          "run_start": "UY2011: ", "first_age": 0,
          "anchor": "other_arm"}),
        ("2012", 0, "",
         "27.4", {"snippet": "UY2012: 27.4",
          "run_start": "UY2012: ", "first_age": 0,
          "anchor": "other_arm"},
         "24.0", {"snippet": "UY2012: 24.0",
          "run_start": "UY2012: ", "first_age": 0,
          "anchor": "other_arm"}),
        ("2013", 0, "",
         "18.4", {"snippet": "UY2013: 18.4",
          "run_start": "UY2013: ", "first_age": 0,
          "anchor": "other_arm"},
         "16.4", {"snippet": "UY2013: 16.4",
          "run_start": "UY2013: ", "first_age": 0,
          "anchor": "other_arm"}),
        ("2014", 0, "",
         "15.9", {"snippet": "UY2014: 15.9",
          "run_start": "UY2014: ", "first_age": 0,
          "anchor": "other_arm"},
         "13.8", {"snippet": "UY2014: 13.8",
          "run_start": "UY2014: ", "first_age": 0,
          "anchor": "other_arm"}),
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
          "anchor": "other_arm"},
         "27.4", {"snippet": "UY2012 27.4",
          "run_start": "UY2012 ", "first_age": 0,
          "anchor": "other_arm"}),
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
#: a whole figure: not part of a longer number, and not a percentage ('12%')
_FIGURE = r"(?<![\d.,])(%s)(?!\d|[.,]\d|\s?%%)" % _FIG
FIGURE = re.compile(_FIGURE)
#: the words a reader's cell label uses for a development age (0 = the end of the underwriting year). A table whose
#: first column is '12 months' or '1 year' (6119/2016, 3902/2023) has no age 0: its first column is age 1.
AGE_WORDS = (
    (0, ("end of underwriting year", "end of UY", "end")),
    (1, ("one year later", "one year", "1 year", "12 months later", "12 months")),
    (2, ("two years later", "two years", "2 years", "24 months later", "24 months")),
    (3, ("three years later", "three years", "three", "3 years", "36 months later", "36 months")),
    (4, ("four years later", "four years", "four", "4 years", "48 months later", "48 months")),
    (5, ("five years later", "five years", "five", "5 years", "60 months later", "60 months")),
)
_AGE_OF = {w.lower(): a for a, ws in AGE_WORDS for w in ws}
#: the labels that are a bare word ('end 42.0', 'three 59.3'). They are an age label only where the cell list continues
#: the reader's own sequence of labels: after a separator or the row's year marker ('UY2011: end 44.7; ... ; three 63.0'),
#: not inside a phrase ('of the five 62.6')
BARE_LABELS = ("end", "three", "four", "five")
_SERIES_WORD = r"(?:paid|net|gross|estimate)"
_LEAD_WORD = r"(?:at|after|cumulative|claims|paid|net|gross|estimate)"
_LABEL = r"(?<![\w])(age\s\d+|%s)" % "|".join(
    re.escape(w) for w in sorted(_AGE_OF, key=len, reverse=True))
_AGE_AFTER = re.compile(r"(?:\s*(?:months?|years?|yrs?)\b)")
_YEAR_MARK = re.compile(r"(?<![\w])(?:UY|YOA)\s?(\d{4})(?!\d)|(?<![\w.,])(\d{4})\s*:|(?<![\w])(\d{4})\s(?:UY|YOA)\b")
_YEAR_LIKE = re.compile(r"(?<![\w.,])((?:19|20)\d{2})(?!\d|[.,]\d)")
_ROW_WORDS = re.compile(r"(?<![\w])(?:prior|earlier|total)(?![\w])", re.IGNORECASE)
_GLOSS = re.compile(r"\s*\(([^()]*)\)")
_LABELLED = re.compile(_LABEL + r"['\")]*[\s:]*(?:is\s+)?" + _FIGURE + r"(?:\s*(?:->|vs\.?)\s*" + _FIGURE + r")?",
                       re.IGNORECASE)
_ARROW = re.compile(_FIGURE + r"\s*(?:->|vs\.?)\s*" + _FIGURE)
_RUN = re.compile(r"^\s*(%s)(?:\s*[/;,]\s*(%s))*\s*$" % (_FIG, _FIG))
#: how a positional side's first age is anchored (see _side_check). A third anchor of review 5, a labelled value of the same
#: row in the same report's cells ("row_label"), was removed in review 6: no entry used it.
ANCHORS = ("place_label", "other_arm")
#: the series a pair may name, and the one cell each stands for when cells are counted: '', 'estimate' and 'gross' are the
#: one gross estimate; 'paid' and 'net' are others
SERIES = {"": "gross", "estimate": "gross", "gross": "gross", "paid": "paid", "net": "net"}


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


def _marks(text):
    """[(start, end, year_start, year_end, year)] of the underwriting-year markers in a text (see year_marks)."""
    out = []
    for m in _YEAR_MARK.finditer(text):
        pre = text[:m.start()]
        if re.search(MONTH + r"\s+$", pre, re.IGNORECASE) or re.search(r"\d[/.-]$", pre):
            continue
        g = next(i for i in (1, 2, 3) if m.group(i))
        out.append((m.start(), m.end(), m.start(g), m.end(g), m.group(g)))
    return out


def year_marks(text):
    """[(position, year)] of the underwriting-year markers in a text: 'UY2011', 'YOA 2011', '2011 UY' or a row label
    '2011:'. A year after a month name or inside a date (31 December 2015) is not one."""
    return [(s, y) for s, _e, _ys, _ye, y in _marks(text)]


def _bare_ok(pre):
    """True when a bare label ('end', 'three', ...) that follows `pre` continues a row's sequence of labels: `pre` is
    empty, ends with a separator or with the row's year marker (leading words such as 'At', 'cumulative paid' aside)."""
    pre = pre.rstrip(" \t'\"(")
    while True:
        m = re.search(r"(?<![\w])%s[\s:'\"(]*$" % _LEAD_WORD, pre, re.IGNORECASE)
        if m is None:
            break
        pre = pre[:m.start()].rstrip(" \t'\"(")
    return (not pre or pre[-1] in ";,/:"
            or re.search(r"(?:UY|YOA)\s?\d{4}$|(?<![\w])\d{4}\s(?:UY|YOA)$", pre) is not None)


def trailing_age(prefix):
    """The development age of the label a text ends with ('... one year later ', "... 'After 12 months' "), or None. A
    bare word ('end', 'three') is a label only where it continues the row's sequence of labels (see BARE_LABELS)."""
    stripped = prefix.rstrip(" \t:'\"(")
    m = re.search(_LABEL + r"$", stripped, re.IGNORECASE)
    if m is None:
        return None
    age = _age_of_label(m.group(1))
    if age is not None and m.group(1).lower() in BARE_LABELS and not _bare_ok(stripped[:m.start(1)]):
        return None
    return age


def _label_matches(q, pre_of):
    """[(age, figures)] of the age-labelled figures of a text (`pre_of(position)` gives the text before the label, for a
    bare label's context)."""
    out = []
    for m in _LABELLED.finditer(q):
        label = m.group(1)
        age = _age_of_label(label)
        if age is None or (label.lower() in BARE_LABELS and not _bare_ok(pre_of(m.start(1)))):
            continue
        out.append((age, [f for f in (m.group(2), m.group(3)) if f], m.start(1)))
    return out


def _arrow_ages(quotes, ages):
    for _ in range(2):
        for q in quotes:
            for m in _ARROW.finditer(q):
                x, y = m.group(1), m.group(2)
                ages.setdefault(x, set()).update(ages.get(y, ()))
                ages.setdefault(y, set()).update(ages.get(x, ()))
    return ages


def labelled_ages(quotes):
    """{figure: {ages}} the reader's quotes give: a figure that follows an age label ('one year later 57.8',
    'age 3 is 54.7 vs 49.0', both figures of a 'x -> y' or 'x vs y' take the label), and a figure beside a labelled one
    in an arrow ('(3,936 -> 4,703)')."""
    ages = {}
    for q in quotes:
        for age, figs, _pos in _label_matches(q, lambda i, q=q: q[:i]):
            for fig in figs:
                ages.setdefault(fig, set()).add(age)
    return _arrow_ages(quotes, ages)


def tied_label_ages(strings, quotes, uy, series=""):
    """labelled_ages for the labels that stand, in the reader's own text, under the underwriting year `uy`: the last year
    marker before the label, where the quote occurs in a string of the check, is `uy`, and the text from that marker to the
    label is one row of that year and series (see _one_row: no row break to a part that is not an age label, no other year
    number, no prior/earlier/total; no paid or net unless the series is paid or net). A label under another row's year
    marker ('UY2011 ... one year later 77.6' for a UY2012 list), after '2010 and prior:', 'total', 'in the 2014 report' or
    'paid' anchors nothing."""
    ages = {}
    for q in quotes:
        for s in strings:
            at = s.find(q)
            while at != -1:
                for age, figs, pos in _label_matches(q, lambda i, s=s, at=at: s[:at + i]):
                    marks = _marks(s[:at + pos])
                    if not (marks and marks[-1][4] == uy):
                        continue
                    row = s[marks[-1][0]:at + pos]
                    if _one_row(row) and _series_ok(series, row.lower()):
                        for fig in figs:
                            ages.setdefault(fig, set()).add(age)
                at = s.find(q, at + 1)
    return _arrow_ages(quotes, ages)


def _series_ok(series, low):
    """True when `low` (lower-cased cells: the snippet and the words before it in its row) agree with the series: a paid
    pair names paid, a net pair names net, and a pair of the gross estimate ('', 'estimate', 'gross') names neither."""
    if series == "paid":
        return re.search(r"\bpaid\b", low) is not None
    if series == "net":
        return re.search(r"\bnet\b", low) is not None
    return re.search(r"\b(?:paid|net)\b", low) is None


def _row_context(text, start):
    """The words of `text` before `start` in the same row: from the last row break or the last year marker."""
    pre = text[:start]
    cut = max([m.end() for m in re.finditer(r"[;.]\s+", pre)] + [mk[1] for mk in _marks(pre)] + [0])
    return pre[cut:]


def _one_row(head):
    """True when `head` reads as the labelled cells of one row of one report: it starts at its underwriting-year marker
    (after an optional series word); it holds no other year-like number (a gloss right after the marker, '(2015 YOA)' or
    '(the only underwriting year before t-1 = 2016)', aside) and no 'prior', 'earlier' or 'total'; and every part after a
    row break ('; ' or '. ') begins with an age label (after words such as 'cumulative paid at'), not with another row's
    label ('2010 and prior:', 'total gross outstanding')."""
    lead = re.match(r"(?:%s\s+)?" % _SERIES_WORD, head, re.IGNORECASE)
    marks = _marks(head)
    if not marks or marks[0][0] != lead.end():
        return False
    gloss = _GLOSS.match(head, marks[0][1])
    if gloss:
        if re.search(r"\d", _YEAR_LIKE.sub("", gloss.group(1).replace("t-1", ""))):
            return False
        head = head[:gloss.start()] + head[gloss.end():]
    own = {(ys, ye) for _s, _e, ys, ye, _y in _marks(head)}
    if any((m.start(1), m.end(1)) not in own for m in _YEAR_LIKE.finditer(head)):
        return False
    if _ROW_WORDS.search(head):
        return False
    for m in re.finditer(r"[;.]\s+", head):
        seg = re.sub(r"^(?:%s(?![\w])[\s:'\"(]*)*" % _LEAD_WORD, "", head[m.end():].lstrip(" '\"("), flags=re.IGNORECASE)
        if seg.strip() and re.match(_LABEL, seg, re.IGNORECASE) is None:
            return False
    return True


def _side_check(text, strings, uy, age, series, fig, side, assigned=None):
    """How one side of a pair is tied to the pair's underwriting year, development age and figure: 'labelled' (a label
    just before the figure gives its age), or, for a list of unlabelled values, the anchor of the list's first age:
    'place_label' (the reader's own words, verbatim, label a figure of the list at the age its place implies, under this
    underwriting year's marker and in one row of its series) or 'other_arm' (the other arm's reading of the same filing,
    page, underwriting year and series gives the figure at this age; `assigned` holds its figures). None when the side is
    not found. See MOVED_CELLS."""
    spec = {"snippet": side} if isinstance(side, str) else side
    if not isinstance(spec, dict) or not isinstance(spec.get("snippet"), str) or not isinstance(text, str):
        return None
    snip = spec["snippet"]
    if not snip or not FIGURE.fullmatch(fig):
        return None
    # (a) the snippet is the reader's, in this report's cells, and its last figure is a whole figure there: not part of a
    # longer number, not a percentage and not an age label ('12 months'). An occurrence inside a parenthesis is a quotation
    # ('(as printed in the 2014 report: UY2011 one year later 70.0)'), not a cell of this report; and the series of the pair
    # is that of the row the occurrence is in: the snippet and the words before it back to the row's start
    # ('paid UY2014 19 / 515' read as an estimate is paid)
    low = snip.lower()
    found = [m for m in re.finditer(re.escape(snip) + r"(?![\d]|[.,]\d)(?!\s?%%)(?!%s)" % _AGE_AFTER.pattern, text)
             if text.count("(", 0, m.start()) <= text.count(")", 0, m.start())
             and _series_ok(series, low + " " + _row_context(text, m.start()).lower())]
    if not found:
        return None
    # (b) it names this underwriting year, and only this one, as an underwriting year (not a year in a date)
    marks = year_marks(snip)
    if not marks or {y for _, y in marks} != {uy}:
        return None
    # (b) it ends with the figure; that the figure is a whole one (157.8 is not 57.8) follows from the label before it or
    # from the list of values it ends
    core = snip[:-1] if snip.endswith(")") else snip
    if not core.endswith(fig):
        return None
    prefix = core[:-len(fig)]
    if "run_start" not in spec:
        # labelled: the snippet is one row's cells, and the label just before the figure is this pair's age
        return "labelled" if _one_row(snip) and trailing_age(prefix) == age else None
    # positional: the snippet is run_start and a list of unlabelled values; the figure's place in the list is its age
    start, first_age = spec["run_start"], spec.get("first_age")
    if not isinstance(start, str) or not isinstance(first_age, int) or isinstance(first_age, bool) or first_age < 0:
        return None
    if not snip.startswith(start) or not _one_row(start):
        return None
    tail = start.rstrip()
    if re.search(r"[/;,]$", tail) or re.search(r"(?<![\w])%s$" % _FIG, tail):
        return None
    # the list follows its row's year marker or a series word ('paid UY2014 19', 'Net: 3,936'), not a label or a word
    bare = tail.rstrip(" :")
    if not (any(len(bare) in (e, ye) for _s, e, _ys, ye, _y in _marks(start))
            or re.search(r"(?<![\w])%s$" % _SERIES_WORD, bare, re.IGNORECASE)):
        return None
    run = snip[len(start):]
    if not _RUN.match(run):
        return None
    tokens = [m.group(1) for m in FIGURE.finditer(run)]
    if not tokens or tokens[-1] != fig or first_age + len(tokens) - 1 != age:
        return None
    # the first age is the reader's, not ours: it is anchored by one of three things the entry names ("anchor")
    anchor = spec.get("anchor", "place_label")
    if anchor == "place_label":
        quotes = _verbatim(spec.get("quote"), strings)
        if quotes is None:
            return None
        given = tied_label_ages(strings, quotes, uy, series)
        ok = any(first_age + i in given.get(tok, ()) for i, tok in enumerate(tokens))
    elif anchor == "other_arm":
        ok = assigned is not None and (uy, SERIES[series], age, fig) in assigned
    else:
        ok = False
    return anchor if ok else None


def _side_assign(spec, uy, series, age, fig):
    """{(uy, series, age, figure)} an accepted side gives: every value of a positional list at the age its place implies,
    the figure an age label directly precedes in a labelled snippet (the part after its last series word, for a paid or net
    pair; not the second figure of 'x vs y', which is the other report's), and the pair's own figure. The series is the
    pair's, normalised (SERIES)."""
    series = SERIES[series]
    out = {(uy, series, age, fig)}
    spec = {"snippet": spec} if isinstance(spec, str) else spec
    snip = spec["snippet"]
    if "run_start" in spec:
        run = snip[len(spec["run_start"]):]
        for i, m in enumerate(FIGURE.finditer(run)):
            out.add((uy, series, spec["first_age"] + i, m.group(1)))
        return out
    cut = 0
    if series in ("paid", "net"):
        cut = max([m.end() for m in re.finditer(series, snip, re.IGNORECASE)] + [0])
    seg = snip[cut:]
    for a, figs, _pos in _label_matches(seg, lambda i: snip[:cut + i]):
        out.add((uy, series, a, figs[0]))
    return out


def _assignments(key, other):
    """{'t': {...}, 't1': {...}, 'pages': (...), 'reader': id} the other arm's reading of the record gives, from the pairs
    of its own entry in MOVED_CELLS when that entry is itself found in its reader's cells without any other arm
    ({} otherwise)."""
    if not isinstance(other, dict) or other.get("key") != key or not isinstance(other.get("evidence"), dict):
        return None
    ev = other["evidence"]
    if _evaluate(other.get("check"), ev, key, None) is None:
        return None
    out = {"t": set(), "t1": set(), "pages": tuple(ev["pages"]), "reader": other.get("reader")}
    for uy, age, series, a, side_t, b, side_t1 in ev["pairs"]:
        out["t"] |= _side_assign(side_t, uy, series, age, a)
        out["t1"] |= _side_assign(side_t1, uy, series, age, b)
    return out


def comparison_made(check):
    """True when a reader's retranslation check compared cells of the year t-1 and year t reports: `checked` is true or
    begins 'yes'. 'partly', 'no: ...', false and an absent check are not a comparison (no year t-1 table to compare)."""
    if not isinstance(check, dict):
        return False
    c = check.get("checked")
    return c is True or (isinstance(c, str) and c.strip().lower().startswith("yes"))


def _evaluate(check, evidence, key=None, other=None):
    """None when the reader's check does not bear the entry out; else {'moved': [...], 'pairs': n, 'distinct_pairs': n,
    'sides': {anchor: n}, 'other_arm': reader or None}. See moved_cell_pairs."""
    if not comparison_made(check) or not isinstance(evidence, dict) or not evidence.get("pairs"):
        return None
    t_text, t1_text = check.get("cells_t"), check.get("cells_t_minus_1")
    if not isinstance(t_text, str) or not isinstance(t1_text, str):
        return None
    page_t, page_t1 = evidence["pages"]
    if not (re.search(r"(?<![\w])p%d(?!\d)" % page_t, t_text) and re.search(r"(?<![\w])p%d(?!\d)" % page_t1, t1_text)):
        return None
    strings = _strings(check)
    pairs = evidence["pairs"]
    if any(not isinstance(p, tuple) or len(p) != 7 for p in pairs):
        return None
    t_year = int(key.rsplit("_", 1)[1]) if isinstance(key, str) else None
    if any(p[2] not in SERIES for p in pairs):
        return None
    # cells are counted by (underwriting year, age, series) with the series normalised ('', 'estimate' and 'gross' are one
    # series), and two pairs on one cell are refused: a cell is entered once
    distinct = {(p[0], p[1], SERIES[p[2]]) for p in pairs}
    if len(distinct) != len(pairs):
        return None
    if t_year is not None and any(int(p[0]) >= t_year - 1 for p in pairs):
        return None
    if len(distinct) < MIN_PAIRS:
        # fewer than three different cells: the reader's own words say why, and the report holds no more underwriting
        # years before t-1 than the entry uses
        reason = _verbatim(evidence.get("fewer_because"), strings)
        if reason is None or any(len(q.split()) < 5 or not re.search(r"\b(?:only|single|precedes?|older)\b", q, re.IGNORECASE)
                                 for q in reason):
            return None
        if t_year is not None and len({y for _, y in year_marks(t_text) if int(y) < t_year - 1}) > len({p[0] for p in pairs}):
            return None
    if "alignment_quotes" in evidence and (_verbatim(evidence["alignment_quotes"], strings) is None
                                           or not str(evidence.get("alignment", "")).strip()):
        return None
    given = _assignments(key, other) if other is not None else None
    if given is not None and given["pages"] != tuple(evidence["pages"]):
        given = None
    moved, sides = [], {}
    for pair in pairs:
        uy, age, series, a, side_t, b, side_t1 = pair
        for text, fig, side, name in ((t_text, a, side_t, "t"), (t1_text, b, side_t1, "t1")):
            how = _side_check(text, strings, uy, age, series, fig, side, None if given is None else given[name])
            if how is None:
                return None
            sides[how] = sides.get(how, 0) + 1
        if abs(float(_plain(a)) - float(_plain(b))) > max(_unit(a), _unit(b)) + 1e-9:
            moved.append((uy, age, a, b))
    used = "other_arm" in sides
    return {"moved": moved, "pairs": len(pairs), "distinct_pairs": len(distinct), "sides": dict(sorted(sides.items())),
            "other_arm": given["reader"] if used else None}


def moved_cell_pairs(check, evidence, key=None, other=None):
    """The pairs of `evidence` (a MOVED_CELLS entry) that differ by more than rounding, when the reader's check supports
    the entry; [] otherwise. `key` is the record ('1301_2017'): the year t is its year, and no pair may be of an
    underwriting year from t-1 on. `other` is the other arm's reading of the record, {"key", "reader", "check",
    "evidence"}, for a positional side anchored on "other_arm". The decision never reads the check's prose. It needs:

      * a check that compared cells (comparison_made);
      * the check's own `cells_t` and `cells_t_minus_1`, as text, each naming the entry's page (p<N>);
      * for every pair, on each side, the reader's snippet as an exact substring of that report's cells (not the other's),
        which starts at the row's year marker (after an optional series word: 'paid UY2014 19'), names the pair's
        underwriting year, and only that year, as an underwriting year (UY2011, YOA 2011, '2011:'; not a year in a date),
        holds no other year number, no 'prior', 'earlier' or 'total', and no part after a row break ('; ' or '. ') that
        does not begin with an age label, and ends with the pair's figure as a whole figure (not part of a longer
        number, not a percentage, not an age label such as '12 months') under the pair's development age: a label just
        before the figure, or, for unlabelled values listed by position, the figure's place in the list counted from the
        age of its first value, a list that follows its row's year marker or a series word ('Net: ') and whose first age
        is anchored by what the side's "anchor" names: "place_label" (the default: the reader's own words, verbatim,
        label a figure of the list at its place's age, under this underwriting year's marker and in one row of the pair's
        series) or "other_arm" (the other arm's reading of the same filing, page, underwriting year, series and figure
        gives it at this age, the figure the other arm's label directly precedes); the first age is 0 or more. No other
        figure of any underwriting year, and no label of another row, anchors a list. The series of the pair must be one
        of '', 'estimate', 'gross', 'paid', 'net'; a paid or net pair names it in the snippet or in the words before the
        snippet back to the row's start, and a '', 'estimate' or 'gross' pair names neither paid nor net there. An
        occurrence of the snippet inside a parenthesis is not a cell of the report. One pair that is not found rejects the
        entry. The two snippets of a pair name the same underwriting year and age because each is tied to the pair's;
      * at least three different (underwriting year, age, series) cells, with '', 'estimate' and 'gross' one series and two
        pairs on one cell refused, or "fewer_because" in the entry, the reader's own
        words for fewer (verbatim) where the year t cells hold no more underwriting years before t-1 than the entry uses;
      * "alignment_quotes", where the entry has them, verbatim;
      * at least one pair whose figures differ by more than one unit in the last printed place (rounding alone cannot
        move a figure by more than that).

    What is not checked: that the reader read the filing's cell correctly (the snippet is the reader's), that the reader's
    notes, which are free text, are a table whose columns are the filing's (the lists are aligned by the readers' own
    labels and the other arm's reading, and were checked by hand: see GATE), which of two alignments of a shifted
    table is the filing's (the entry says so; 1301/2016 X8), and the two limits GATE names from review 6 (a row set off
    from the year marker by no break, year number or word; a quotation of another report outside parentheses)."""
    res = _evaluate(check, evidence, key, other)
    return [] if res is None else res["moved"]


def shows_moved_cells(check, evidence, key=None, other=None):
    """True when `moved_cell_pairs` finds at least one pair of cells that moved."""
    return bool(moved_cell_pairs(check, evidence, key, other))


def reader_moved_cells(key, reads, rid):
    """moved_cells_record of one reader of a record: `reads` are the record's two readings (round-2 form), the reader's
    MOVED_CELLS entry is found by (key, reader), and the other reading is the other arm's."""
    mine = next(r for r in reads if r["reader"] == rid)
    theirs = [r for r in reads if r["reader"] != rid]
    other = None
    if len(theirs) == 1:
        other = {"key": key, "reader": theirs[0]["reader"], "check": theirs[0]["table_retranslated_check"],
                 "evidence": MOVED_CELLS.get((key, theirs[0]["reader"]))}
    return moved_cells_record(mine["table_retranslated_check"], MOVED_CELLS.get((key, rid)), key, other)


def moved_cells_record(check, evidence, key, other):
    """The provenance of a table_retranslated reading for the register: the pages compared, the pairs found and how many
    moved, how the sides were tied to their cells (labelled, or the anchor of each unlabelled list), and the other arm
    where it anchored a list; None where the check does not bear the entry out."""
    res = _evaluate(check, evidence, key, other)
    if res is None:
        return None
    return {"pages": list(evidence["pages"]), "pairs": res["pairs"], "distinct_pairs": res["distinct_pairs"],
            "pairs_moved": len(res["moved"]), "sides": res["sides"], "other_arm_reader": res["other_arm"]}


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
    moved_cells = {}
    if reason == "table_retranslated":
        moved_cells = {r["reader"]: reader_moved_cells(key, reads, r["reader"]) for r in reads}
        unshown = [rid for rid, rec in moved_cells.items() if rec is None or not rec["pairs_moved"]]
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
        e["moved_cells"] = moved_cells
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
    """The register (data/fx_untranslated_excluded.json), the bytes the loader reads and the run identifier hashes."""
    return build_all()[0]


def build_evidence():
    """The evidence file (data/fx_untranslated_excluded_evidence.json)."""
    return build_all()[1]


def split_evidence(out):
    """(register, evidence): the provenance of the cells (moved_cells) leaves each entry of the register for the evidence
    file, keyed like the register, which also holds the gate's record and the sentence about it that follows RULE."""
    evidence = {
        "_about": ("The record of the cells gate of data/fx_untranslated_excluded.json (src/build_fx_untranslated_excluded.py): "
                   "what it proves and does not prove, and how each of the 20 table_retranslated readings was tied to its "
                   "cells. Keyed like the register. The loader does not read it and a run does not hash it: the register "
                   "itself is a hashed input and holds none of this."),
        "_rule_addition": RULE_ADDITION,
        "_moved_cells_gate": GATE,
        "read_and_kept": {},
    }
    for key, e in out["read_and_kept"].items():
        if "moved_cells" in e:
            evidence["read_and_kept"][key] = {"moved_cells": e.pop("moved_cells")}
    # round 5: the cells that show condition (a), from each reading (the register's entry carries them too)
    evidence["excluded"] = {key: {"mixed_base_cells": {r["reader"]: r["cells_compared"]
                                                       for r in out["excluded"][key]["readings"]}}
                            for key in ROUND5_SNIPPETS if key in out["excluded"]}
    return out, evidence


def register_defects(reg):
    """What would make the register's bytes differ from what the loader-facing rules produce: a key of the evidence file, or
    the sentence of RULE_ADDITION, in the register."""
    found = [k for k in EVIDENCE_ONLY_KEYS if k in reg]
    found += ["%s/%s" % (b, k) for b in ("excluded", "read_and_kept") for k, e in reg[b].items()
              for n in EVIDENCE_ONLY_KEYS if n in e]
    if RULE_ADDITION in reg.get("_rule", ""):
        found.append("_rule holds the sentence of RULE_ADDITION")
    return found


def build_all():
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
    r5 = load_round5()
    for key in sorted(r5, key=sort_key):
        if key in out["excluded"] or key in out["read_and_kept"]:
            raise SystemExit("%s was read in an earlier round" % key)
        out["excluded"][key] = entry_r5(key, [reading_r5(rid, key, e) for rid, e in r5[key]])
    pop["round5"] = {
        "records_excluded": sorted(r5, key=sort_key),
        "chosen_as": ("the records of the round-5 readings of tables whose history moved between reports "
                      "(results/extraction_error_rate/mature-cohort/round5/; the screen rebase_screen.py over the "
                      "primary sample's 649 records at 35a259c) that rule 2 of the round-5 decision rules decides: a "
                      "table whose history is retranslated while its end-(t-1) reserves are not, with an exchange line "
                      "of 5% or more of R"),
        "readers": "P2 and Q1, two independent arms (round5/readings/; the brief round5/briefs/brief_r5.md)",
        "decision": "decision of the Claude analysis session, 23 October 2026, applying the author's rule B",
    }
    out, evidence = split_evidence(out)
    defects = register_defects(out)
    if defects:
        raise SystemExit("the register would not be the loader-facing bytes: %s" % ", ".join(defects))
    return out, evidence


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
    register, evidence = build_all()
    files = ((REGISTER, dumps(register)), (EVIDENCE, dumps(evidence)))

    def shown(path):
        try:
            return path.relative_to(HERE).as_posix()
        except ValueError:
            return str(path)
    if "--write" in argv:
        for path, text in files:
            with io.open(path, "w", encoding="utf-8", newline="") as fh:
                fh.write(text)
            print("wrote %s" % shown(path))
        return 0
    status = 0
    for path, text in files:
        name = shown(path)
        committed = None
        if path.exists():
            with io.open(path, encoding="utf-8", newline="") as fh:
                committed = fh.read()
        if committed != text:
            print("%s differs from its rebuild: run with --write and read the diff" % name)
            status = 1
        else:
            print("%s equals its rebuild" % name)
    return status


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
