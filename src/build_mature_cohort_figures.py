"""Build data/mature_cohort_figures.json: the mature-cohort figures of the primary outcome (the owner's decision,
22 October 2026, option c).

The paper's outcome (Equation 1) is the gross prior-year movement over the underwriting years u <= t-2. The extraction
applies two precedence rules that replaced a printed gross triangle's mature-cohort figure with a broader one only
because the two had opposite signs: the provisions sign-disagreement override (route rag_provisions) and the
model-agreement veto (a "[RAG PYD NOT APPLIED: ...]" note, the models' reading kept). The owner decided that a valid
mature-cohort triangle figure is never replaced merely because a broader movement has the other sign. The register
holds one entry per record of the corpus whose gross RAG triangle such a rule displaced (DISPLACED, the corpus rule
the completeness test reads): the triangle's figure where readings of the filing confirm it as a valid mature-cohort
figure, or no figure and the reason. run_analysis.py (apply_mature_cohort_figure) adopts the figures under the
primary outcome; the 672-record construction (outcome "precedence_672") ignores the register.

Each figure is recomputed here from the record's stored grid (models.<model>._rag_triangle) by the extraction's own
estimator, test_gemini.compute_pyd_from_triangle and its helpers, read from the extraction checkout
(LLOYDS_EXTRACTION_REPO) at the commit this analysis pins (record_tests.extraction_pin), parsed and never imported
(its import loads .env and the API clients), so the analysis does not carry a copy of the estimator. The rest of each
entry is assembled from committed evidence:

  - results/extraction_error_rate/mature-cohort/readings/<reader>.json, the readings of 22 October 2026 (A1-A4, B1),
    and the second readings of the records that round read once (C1, C2), so that every figure entry rests on two
    independent agent readings of the filing;
  - results/extraction_error_rate/mature-cohort/decisions.csv, the adjudication's decision per record
    (adjudication.md beside it);
  - results/extraction_error_rate/mature-cohort/design_per_record.csv, the design study's deterministic
    reconciliation census and route;
  - the extraction error-rate study's earlier readings that recomputed the same printed triangle
    (results/extraction_error_rate/);
  - NO_FIGURE below, the records the register keeps without a figure, with the reason;
  - results/extraction_error_rate/mature-cohort/round5/readings/<reader>.json, the round-5 readings of 23 October 2026
    (arms P and Q, and the round-6 tie-break readers Z5 and Z6), for CORRECTIONS below: the records whose printed
    table's own figure rules 3 and 4 of the round-5 decision rules (round5/rules.md) correct.

Usage:
  python src/build_mature_cohort_figures.py            # check the register against a rebuild; exit 1 on a difference
  python src/build_mature_cohort_figures.py --write    # rebuild and write the register
"""
import ast
import copy
import csv
import glob
import io
import json
import os
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE / "src"))

REGISTER = HERE / "data" / "mature_cohort_figures.json"
EVIDENCE = HERE / "results" / "extraction_error_rate" / "mature-cohort"
READERS = ("A1", "A2", "A3", "A4", "B1", "C1", "C2")
READING_ROUND = "mature-cohort readings of 22 October 2026"
#: the second readings of the 43 figure entries the first round read once (each read by C1 or C2, who opened no other
#: reader's folder); they replace the extraction's table read as the entry's second reading
SECOND_ROUND = "mature-cohort second readings of 22 October 2026 (the records the first round read once)"
ROUNDS = {"C1": SECOND_ROUND, "C2": SECOND_ROUND}
#: the kinds of reading that are an agent's reading of the filing; the extraction's table read is not one
AGENT_READING_KINDS = ("reading", "error_rate_study")
STUDY = HERE / "results" / "extraction_error_rate"
RECORDS = HERE / "pdf_extraction"

#: Appendix 2.1 leaves an aggregated development-age column ("2014 & Prior": older underwriting years added by
#: development age) out of the mature-cohort figure, because its last two diagonal cells are not like for like by
#: calendar year. The author's decision of 22 October 2026 applies it to two records of syndicate 1945, whose oldest
#: column is such a column (the label and anchor year of the column are the stored grid's aggregated_cohort). Two
#: independent readings (F1, F2) recompute each figure from the printed table without the column, and the
#: extraction's estimator on the stored grid without the column gives the same figure. The readings are archived with
#: the exchange-rate readings of the same brief (fx-translation/readings/F1.json, F2.json).
#: 1945_2022 (decision of the Claude analysis session, 23 October 2026) is the third such record: the round-2 reading of
#: the older-years columns (X4, Y5) and the two tie-break readings (Z1, Z2) all find its "2012&Prior" column built by
#: development age (the 2021 report's UY2011 column plus UY2012, added age by age), so its last step is not the report
#: year's movement; the adopted figure was -13.840 with the column and is -13.831 without it.
AGGREGATED_COLUMN = {"1945_2022": {"label": "2012&Prior", "anchor": 2012},
                     "1945_2023": {"label": "2013&Prior", "anchor": 2013},
                     "1945_2024": {"label": "2014 & Prior", "anchor": 2014}}
#: the entries of AGGREGATED_COLUMN that no precedence rule displaced: the adopted figure is the code or RAG
#: triangle's own, with the column in it (the corpus rule, population(), does not see them)
COLUMN_ONLY = ("1945_2022", "1945_2023")
COLUMN_READERS = ("F1", "F2")
COLUMN_READINGS = HERE / "results" / "extraction_error_rate" / "mature-cohort" / "fx-translation" / "readings"
COLUMN_ROUND = "aggregated-column readings of 22 October 2026 (F1, F2)"
#: the records whose column readings are the round-2 readers' (results/extraction_error_rate/mature-cohort/round2/
#: readings/): two independent arms (X, Y) and two tie-break readers (Z1, Z2), each with the figure with and without
#: the column. Every other AGGREGATED_COLUMN record rests on F1 and F2.
COLUMN_READERS_R2 = {"1945_2022": ("X4", "Y5", "Z1", "Z2")}
ROUND2 = HERE / "results" / "extraction_error_rate" / "mature-cohort" / "round2"
COLUMN_ROUND_R2 = "aggregated-column readings of 23 October 2026 (X and Y arms, tie-break readers Z1 and Z2)"
COLUMN_RULE = (
    "Appendix 2.1 leaves an aggregated development-age column out of the mature-cohort figure, because its last two "
    "diagonal cells are not like for like by calendar year: it adds the older underwriting years age by age, so its "
    "'ten years later' cell holds the older years at age 10 and its 'nine years later' cell the older years at age 9. "
    "The author's decision of 22 October 2026 applies the rule to this record: the figure is the sum over the "
    "underwriting years up to t-2 of the latest estimate less the previous one, without that column")
COLUMN_RULE_R2 = (
    "Appendix 2.1 counts an older-years column as one of the mature years only if its last step (its latest cell less "
    "the cell before it) is a like-for-like movement of the same underwriting years during year t. A column built by "
    "development age adds the older underwriting years age by age, so its 'ten years later' cell holds the older years "
    "at age 10 and its 'nine years later' cell the older years at age 9, and its last step is not the report year's "
    "movement. Four independent readings (X4, Y5, Z1, Z2, 23 October 2026) find this record's column built that way, "
    "and the decision of the Claude analysis session, 23 October 2026, applies the rule: the figure is the sum over "
    "the underwriting years up to t-2 of the latest estimate less the previous one, without that column")

EXTRACTION_ENV = "LLOYDS_EXTRACTION_REPO"
EXTRACTION_DEFAULT = os.path.join("D:" + os.sep, "dev", "lloyds_reserve_stress_testing")
#: the definitions of test_gemini.py the estimator needs, read by name from its syntax tree
ESTIMATOR_NAMES = ("_as_number", "MIN_STEP_RATIO", "_same_figure", "_thousandfold", "_printed_current_estimates",
                   "_diagonal_cells", "_null_zeros_beyond_the_staircase", "_staircase_limit",
                   "_validate_triangle_structure", "_single_cohort_staircase", "MIN_TRIANGLE_STRUCTURE_SCORE",
                   "compute_pyd_from_triangle")
#: the two constants compute_pyd_from_triangle reads from table_extraction.py, checked against that file at the pin
TABLE_CONSTANTS = {"MAX_UW_YEAR_LAG": 5, "PYD_EXCLUDED_RECENT_UW_YEARS": 2}

#: the corpus rule: a block displaced a gross triangle when its stored RAG triangle is gross and its figure is the
#: provisions note's after the sign-disagreement override, or a veto note records a deterministic figure not applied
VETO_NOTE = re.compile(r"\[(?:RAG|CODE) PYD NOT APPLIED")
RAG_VETO = re.compile(r"\[RAG PYD NOT APPLIED: deterministic figure ([+-]?\d+(?:\.\d+)?)m "
                      r"(has the opposite sign|is \d+% of opening)")
FIGURE_TOL = 0.0015

#: the records the register keeps without a figure, each with its reason (decisions of the Claude analysis session,
#: 22 October 2026, under the rules the analysis already applies; design.md section 3 and adjudication.md)
NO_FIGURE = {
    # a figure two readings confirmed stands in data/pyd_confirmed_figures.json, which decides the record
    **{k: ("confirmed_figure_register",
           "data/pyd_confirmed_figures.json holds this record's figure, confirmed by two readings of the filing; that "
           "register decides it, under either outcome")
       for k in ("1991_2018", "2010_2018", "3010_2018", "3010_2019", "3010_2022", "3500_2018", "6112_2016")},
    # the stored triangle holds no underwriting year up to t-2
    **{k: ("no_mature_cohort",
           "the stored gross triangle holds no underwriting year up to t-2, so it has no mature-cohort figure "
           "(the estimator computes none)")
       for k in ("1947_2019", "2014_2015", "6125_2017")},
    # a deterministic triangle figure is the adopted block's route already: nothing displaced it there
    "2007_2015": ("triangle_figure_stands",
                  "the adopted block's figure is the code triangle's (-2.0m, the models' triangles without the '2010 & "
                  "prior' column); the RAG figure +148.8m rests on that column, whose last two diagonals two readings "
                  "of the error-rate study found not like for like (design.md section 3)"),
    "2014_2017": ("triangle_figure_stands",
                  "the adopted block's figure is the code triangle's (+4.024m); the vetoed RAG figure (-1.2m) is not "
                  "the stored gross triangle's"),
    # outside the working sample under either outcome for a reason that is not the figure; not read
    **{k: ("outside_working_sample_not_read",
           "outside the working sample under either outcome for a reason that is not its figure (%s), so the "
           "triangle was not read and its figure is not adopted" % why)
       for k, why in (("1206_2019", "in run-off"), ("1209_2016", "in run-off"),
                      ("3002_2017", "no usable line-of-business weights"),
                      ("3002_2019", "no usable line-of-business weights"),
                      ("3002_2020", "no usable line-of-business weights"),
                      ("3002_2024", "no usable line-of-business weights"),
                      ("6104_2016", "no usable line-of-business weights"),
                      ("6117_2018", "no usable line-of-business weights"),
                      ("6117_2024", "no usable line-of-business weights"),
                      ("779_2015", "no usable line-of-business weights"),
                      ("779_2016", "no premium mix: incomplete"), ("6134_2024", "no premium mix: incomplete"))},
    # the readings' own finding, under Appendix 2.1's rule for an aggregated column (adjudication.md, Q2)
    "6134_2023": ("aggregated_column_not_like_for_like",
                  "the 2021 column, the only one up to t-2, absorbs the 2019 and 2020 years of account at its latest "
                  "cell only (reinsured to close into Syndicate 2121 and reassumed under the 2021 quota share, p43): "
                  "its last step is not the report year's movement, so Appendix 2.1 leaves the column out and no "
                  "mature column remains; both readings also read the step as a take-on dominating it"),
}

#: the figure entries that leave the primary through data/takeon_not_development.json (their entries there carry
#: figure_route "mature_cohort_triangle"): the take-on, or the outward transfer, dominates the triangle's step
TAKEON_EXCLUDED = ("1084_2022", "1861_2020", "2001_2022")

#: flags the second readings raised that the existing rules decide, each with its rule (decisions of the Claude
#: analysis session, 22 October 2026); no figure changes
NOTES = {
    "5151_2016": (
        {"flag": "readers disagree: A4 confirmed (+18.850, 'the earlier diagonals are restated in this table, so the two "
                 "diagonals used are on the same (restated) basis'); C2 table_invalid: the cells are never retranslated "
                 "between reports (the cells before the 2015 diagonal are identical in the 2015 and 2016 reports, and "
                 "the 2017 report repeats the 2016 diagonal exactly), the functional currency is US dollars from 1 "
                 "January 2016 (p25; p20 'The Syndicate changed its functional currency to US dollars with effect from "
                 "1st January 2016'), the gross claims outstanding roll-forward prints 'Foreign exchange 35,556' on an "
                 "opening 244,293 (p33, 14.6%), and C2 estimates the translation in the step at roughly +20m to +26m, "
                 "which is not a printed figure. Both readers recompute +18.850 and reconcile the table exactly to "
                 "gross claims outstanding 304,206 (p44, p33)",
         "reader": "A4, C2",
         "rule": "no existing rule covers a triangle held at historical rates or a change of functional currency. The "
                 "validity rule (design.md section 2, points 1-4) tests the table's computation, its gross basis and "
                 "reconciliation, a transaction in the step and an aggregated column's coverage, not its exchange "
                 "basis; the paper converts R and M at the reporting-date rate and treats S as invariant to the "
                 "reporting currency, which holds for that conversion, not for translation inside the filing's own "
                 "table; and the one precedent, 3500/2018 in the error-rate study's tail stratum, took a printed gross "
                 "line that included exchange because the filing printed no figure without it. An estimate of the "
                 "translation is not a printed figure, so no rule puts one in the figure's place",
         "decision": "the figure stands under the existing rules: primary, +18.850. Whether a historical-rate triangle "
                     "or a year-t change of functional currency leaves the primary is a scope question for the author, "
                     "for every affected record. fx-translation/fx_translation.json measures the primary sample's 653 "
                     "from the stored grids: 506 tables re-presented between reports, 37 not retranslated (their "
                     "earlier diagonals equal the year t-1 report's), 110 not comparable; of the 37, 18 in a year "
                     "sterling moved 5% or more against the dollar, and of those the gross claims-outstanding "
                     "roll-forward prints an exchange movement of 5% or more of R for 3 (2468/2016, 5151/2016, "
                     "5151/2017); 13 records change functional currency in year t (a lower bound), 5151/2016 the "
                     "only one measured as not retranslated"},
        {"flag": "the 2016 report amends the 2015 diagonal ('Certain amounts in the prior period triangles have been "
                 "amended to correctly reflect the claims incurred by pure year of account', p44) on a basis it does "
                 "not state (C2): 2011 96,952 -> 117,599, 2012 67,682 -> 80,021, 2013 78,897 -> 91,276, 2014 97,599 -> "
                 "106,295, 2015 42,095 -> 43,849, every earlier cell unchanged",
         "reader": "C2 (A4 reads the same amendment as a restatement on both diagonals)",
         "rule": "the figure is the latest less the previous diagonal of the year-t report's own table (design.md "
                 "section 2, point 1; Appendix 2.1), and a prior diagonal the year-t report itself amends is that "
                 "table's previous diagonal, as a triangle restated in the year-t report is under the take-on base "
                 "rule (error-rate protocol, ninth amendment). The amendment is not a transaction (both readers find "
                 "none in 2016), the table reconciles exactly, and the stored grids show the amended cells continuing "
                 "each column's own history where the 2015 report's did not (2011: 114,839 at end-2014, 117,599 "
                 "amended end-2015, 121,341 end-2016; the 2015 report printed 96,952 after 114,839)",
         "decision": "not a table-validity failure: the figure stands"},
    ),
    "2689_2022": (
        {"flag": "a remnant after an outward RITC at the start of year t: 'Immediately following 31 December 2021, the "
                 "2019 and prior underwriting years were externally Reinsured-to-Close (RITC) to an external party, "
                 "Syndicate 1254' (p12); 'External RITC (101,597)' in the gross claims outstanding movement (p35); the "
                 "table develops the 2020 year alone up to t-2",
         "reader": "C1 (A3 reads the same transfer and finds it does not move the 2020 column)",
         "rule": "the figure is the development of the years the table develops (Appendix 2.1), and the transfer is "
                 "of years the table does not print, so it is not in the step (design.md section 2, point 4); "
                 "no_mature_cohort applies only to a table with no column up to t-2. R stays the unadjusted gross "
                 "claims outstanding at 1 January, which includes the 101.597m transferred out (the author's decision "
                 "of 29 September 2026, data/outbound_transfer_retained_base.json); the retained-base sensitivity "
                 "(src/check_outbound_transfer_sensitivity.py) replaces R by the balance retained for that register's "
                 "confirmed records, and 2689/2022 has been among them since the readings of 22 October "
                 "2026 (F1, F2)",
         "decision": "primary, figure unchanged (-3.651); in the outbound-transfer sensitivity register since 22 "
                     "October 2026"},
    ),
    "1492_2022": (
        {"flag": "an outward loss portfolio transfer (31 August 2022, to Syndicate 2008, of the 2020 year of account) and "
                 "a split RITC of the 2018 and prior liabilities effective 31 December 2022 (p62); the gross table "
                 "still carries the 2015-2018 liabilities at 31 December 2022 (PRA approval of the split RITC came "
                 "on 25 January 2023)",
         "reader": "C2",
         "rule": "an outward loss portfolio transfer is ceded reinsurance: it moves the net table and leaves the gross "
                 "table and gross R unchanged (data/outbound_transfer_retained_base.json, 1200/2022); an outward "
                 "transfer takes a figure out of the primary only where it dominates the gross step "
                 "(data/takeon_not_development.json: 1856/2020, 2001/2022), and here it does not move the gross "
                 "table; a transfer at the balance-sheet date does not move year t (error-rate protocol, ninth "
                 "amendment). Whether the 2018 year's +12.2m was set in pricing the deal cannot be told from the "
                 "pages, and no rule turns on it",
         "decision": "primary, figure unchanged (+3.669); the split RITC is an outward transfer at the start of "
                     "1492/2023, in the outbound-transfer sensitivity register since 22 October 2026"},
    ),
    "4444_2024": (
        {"flag": "a take-on in year t-1, not t: 'On 1 January 2023 the 2021 year of account of the Syndicate accepted "
                 "the RITC of the 2020 year of account of Syndicate 1861' (p99), carried on both 2024 diagonals (the "
                 "2023 report, p26: 'The 2019 and 2020 years of account development includes the business assumed "
                 "from Syndicate 1861'); presentation changed to US dollars in 2024, and the previous diagonal is the "
                 "2023 table's end-2023 cells retranslated at about 1.257 (C1, and the stored grids)",
         "reader": "C1",
         "rule": "the validity rule asks for no transaction in the step that the opening reserves do not carry "
                 "(design.md section 2, point 4); the 1 January 2024 reserves carry Syndicate 1861's business, which "
                 "entered in 2023, the year whose take-on base data/opening_reserves_takeon_base.json registers "
                 "(4444/2023). The take-on base and take-on rules concern the report year's transfers only",
         "decision": "primary, figure unchanged (+115.290)"},
    ),
    "1945_2024": (
        {"flag": "the '2014 & Prior' column is the 2023 report's '2013&Prior' and '2014' columns added by development "
                 "age (C2, from the 2023 report p52; F2 the same), so its last step holds the 2013&Prior block's 2023 "
                 "movement (-37k at 2023 rates) in place of its 2024 movement, and the column contributes -425k of "
                 "the +4.839m that includes it",
         "reader": "C2, F2",
         "rule": COLUMN_RULE,
         "decision": "the column is left out: the figure is +5.264 (F1 and F2 recompute it from the printed table, "
                     "and the estimator on the stored grid without the column gives it); +4.839 includes the column "
                     "and rests on A4 and C2, kept under superseded_readings"},
    ),
    "1945_2022": (
        {"flag": "the '2012&Prior' column of the 2022 table is the 2021 report's UY2011 column and UY2012 column added by "
                 "development age and restated at 2022 rates (X4, Y5, Z1, Z2; at the same age the 2022 cell is 1.0606 "
                 "times the sum on ages 4 to 10, a uniform factor, while the calendar-date pairing drifts from 0.876 to "
                 "1.087), so its last step (29,583 less 29,592, -9 in thousands) holds UY2011's age 9 to 10 step of "
                 "2021 in place of the column's 2022 movement",
         "reader": "X4, Y5, Z1, Z2",
         "rule": COLUMN_RULE_R2,
         "decision": "the column is left out: the figure is -13.831 (X4, Y5, Z1 and Z2 recompute it from the printed "
                     "table, and the estimator on the stored grid without the column gives it); the triangle's own "
                     "figure with the column, -13.840, is the 672 construction's and the adopted figure before this "
                     "decision; the column moves the figure by 0.009m"},
    ),
    "1945_2023": (
        {"flag": "the '2013&Prior' column of the 2023 table is built by development age from the older underwriting "
                 "years (C2 read the same construction), so its last step (-37k, ten years later 62,948 less nine "
                 "years later 62,985) is not the report year's movement",
         "reader": "F1, F2",
         "rule": COLUMN_RULE,
         "decision": "the column is left out: the figure is -4.997 (F1 and F2 recompute it from the printed table, "
                     "and the estimator on the stored grid without the column gives it); the triangle's own figure "
                     "with the column, -5.034, is the 672 construction's and the adopted figure before this decision"},
    ),
}

#: Rules 3 and 4 of the round-5 decision rules (decision of the Claude analysis session, 23 October 2026;
#: results/extraction_error_rate/mature-cohort/round5/rules.md and adjudication.md): the records whose printed table's
#: own figure (the adopted block's, a deterministic triangle's route) is replaced by the corrected figure the readings
#: give. No precedence rule displaced it; displaced.by names the correction (run_analysis.MATURE_COHORT_CORRECTIONS).
#: Each reader's figure is read from the archived reading: `field` names the reader's own figure, or `terms` a verbatim
#: snippet whose signed terms (one per underwriting year) the build sums, or `misprint` the snippets of the cells from
#: which the build recomputes the figure (1274/2016). `superseded` keeps a reading whose figure the tie-break overruled.
ROUND5_READINGS = HERE / "results" / "extraction_error_rate" / "mature-cohort" / "round5" / "readings"
ROUND5_ROUND = "round-5 readings of 23 October 2026 (tables whose history moved between reports)"
ROUND6_ROUND = "round-6 tie-break readings of 23 October 2026"
CORRECTIONS = {
    "318_2024": {
        "by": "printed_table_error", "rule": "rule 4 of the round-5 decision rules (known-cause correction)",
        "cause": ("the 2024 gross table's body is printed transposed against its labels (p69): each printed row is one "
                  "underwriting year, as the 2023 report's columns show at a uniform 1.0097-1.0137 retranslation"),
        "derivation": ("u <= 2022 read by rows (one underwriting year per row), latest less end-2023 cell: both readers "
                       "give -27.990m; the table read by its printed column labels gives -67.098m"),
        "readers": {"P5": {"field": "m_recomputed_m", "cells": "m_detail"},
                    "Q4": {"field": "m_recomputed_m", "cells": "m_detail"}},
    },
    "1609_2024": {
        "by": "printed_table_error", "rule": "rule 4 of the round-5 decision rules (known-cause correction)",
        "cause": ("the 2024 gross table's row and column labels are swapped against its body (p51): each printed row is "
                  "one underwriting year, as the 2023 report's columns show cell for cell at 0.984-0.991; the tie-break "
                  "readers Z5 and Z6 settle the disagreement of P3 (literal reading) and Q2"),
        "derivation": ("u <= 2022 read by rows: 2021 57,359 - 43,731 = +13,628; 2022 107,543 - 107,236 = +307; +13.935m "
                       "USD (Z5, Z6, Q2); read by the printed labels, -0.185m (P3, superseded)"),
        "readers": {"Z5": {"field": "M_m_usd", "cells": "cells", "round": ROUND6_ROUND},
                    "Z6": {"field": "recomputed_mature_figure_m", "cells": "m_cells_correct_orientation",
                           "round": ROUND6_ROUND},
                    "Q2": {"field": "m_recomputed_m", "cells": "m_recomputed_detail"}},
        "superseded": {"P3": {"field": "m_recomputed_m", "cells": "m_calc"}},
    },
    "2232_2020": {
        "by": "previous_report_base", "rule": "rule 3 of the round-5 decision rules (corrected to the previous report's base)",
        "cause": ("the 2020 table's end-2019 diagonal is restated 44.7m below the 2019 report's printed cells with no "
                  "stated reason, and the table taken on its own implies gross incurred 31% above the accounts (190.0m "
                  "against 144.9m), the 2019 control tying; the 2019 report's printed cells as the base reproduce the "
                  "2020 accounts within 0.3% (incurred) and 1.7% (paid)"),
        "derivation": ("u <= 2018, the 2020 table's latest cells less the 2019 report's printed latest cells: 2013 -926; "
                       "2014 +453; 2015 +6,174; 2016 -6,209; 2017 +3,950; 2018 +15,889; +19.331m (both readers); the "
                       "2020 table's own end-2019 cells give +55.227m"),
        "readers": {"P7": {"terms": ("2013 -926; 2014 +453; 2015 +6,174; 2016 -6,209; 2017 +3,950; 2018 +15,889; sum "
                                     "19,331"), "cells": "m_working"},
                    "Q8": {"terms": "-926+453+6,174-6,209+3,950+15,889 = +19,331", "cells": "m_derivation"}},
    },
    "1274_2016": {
        "by": "printed_table_error", "rule": "rule 4 of the round-5 decision rules (known-cause correction)",
        "derived": True,
        "cause": ("a misprinted cell: the 2016 table's 2012 column prints 141,355 at three years later between 174,440 "
                  "and 185,418 (p41), a reserve of 12,005 against 47,564 in the 2015 report, whose own cell is 178,987; "
                  "both readers read it as a misprint, which the filing does not correct"),
        "derivation": ("DERIVED by the decision of the Claude analysis session, 23 October 2026 (after review 8); not a "
                       "figure either reader gives. The 2015 report's 2012 cell (178,987) replaces the misprinted 141,355 "
                       "at the 2012 column's own exchange factor: its paid cells at end-2015, 129,350 in the 2016 table "
                       "against 131,423 in the 2015 report (the 2012 column's paid history is a retranslation of cells "
                       "the misprint does not touch), f = 129,350 / 131,423 = 0.98423. Corrected cell 178,987 x f = "
                       "176,163.7; the 2012 term is 185,418 - 176,163.7 = +9,254.3; M = +13,440 (the other six years) + "
                       "9,254.3 = +22,694.3, i.e. +22.6943m USD. Every cell used is quoted by both readers (P3, Q4) and "
                       "the build recomputes the figure from each reader's own quoted cells. Each reader's own figure is "
                       "kept as given: +57.503m as printed (both), P3 calling the cell not correctable from the filing, "
                       "Q4 giving +19.871m with the 2015 report's cell unretranslated. Other defensible factors (the "
                       "ratio of any other column's end-2015 cell to the 2015 report's, 0.96766 to 0.98919) give "
                       "+21.806m to +25.659m (review 8: +21.8m to +25.6m); the 2008 column's factor 0.97948 gives "
                       "+23.5435m, the figure this register carried before review 8"),
        "cells_used": {
            "other_years_latest_and_end_2015": {
                2008: ("208,456", "209,137"), 2009: ("165,974", "165,410"), 2010: ("208,906", "206,415"),
                2011: ("178,142", "174,535"), 2013: ("180,767", "183,933"), 2014: ("203,214", "192,589")},
            "misprinted_year_latest": "185,418", "previous_report_cell": "178,987",
            "paid_end_2015_2016_table": "129,350", "paid_end_2015_2015_report": "131,423"},
        "other_factor_cells": {2008: ("209,137", "213,518"), 2009: ("165,410", "167,218"), 2010: ("206,415", "212,521"),
                               2011: ("174,535", "180,368"), 2013: ("183,933", "188,149"), 2014: ("192,589", "196,949"),
                               2015: ("101,954", "103,804")},
        "readers": {
            "P3": {"misprint": {
                "terms": ("2008 208,456-209,137=-681; 2009 165,974-165,410=+564; 2010 208,906-206,415=+2,491; 2011 "
                          "178,142-174,535=+3,607; 2012 185,418-141,355=+44,063; 2013 180,767-183,933=-3,166; 2014 "
                          "203,214-192,589=+10,625"),
                "latest": "185,418 is right",
                "paid_t": ("2012 139,244-129,350=9,894", "129,350"),
                "paid_prev": ("2012 131,423-105,931=25,492", "131,423"),
                "prev_cells": "latest cells 213,518 (2008, seven years later); 167,218; 212,521; 180,368; 178,987"},
                "cells": "m_recomputed_cells"},
            "Q4": {"misprint": {
                "terms": "2008 -681; 2009 +564; 2010 +2,491; 2011 +3,607; 2012 +44,063; 2013 -3,166; 2014 +10,625",
                "latest": "141,355 (3y), 185,418 (4y)",
                "paid_t": ("(141,355-129,350 paid)", "129,350"),
                "paid_prev": ("(178,987-131,423)", "131,423"),
                "prev_cells": "latest cells (2008..2015): 213,518; 167,218; 212,521; 180,368; 178,987",
                "sensitivity": "M = +19,871 (USD k)"},
                "cells": "m_detail"},
        },
    },
    "4242_2022": {
        "by": "previous_report_base", "rule": "rule 3 of the round-5 decision rules (corrected to the previous report's base)",
        "cause": ("the 2022 table (p44) lowers the end-2021 cells of 2019 and 2020 (204,999 and 277,405 against 207,954 "
                  "and 310,094 printed in 2021, p46), -35.9m on the 2017-2021 diagonal of a dollar table that is not "
                  "retranslated, with no explanation in either filing (the loss-funds reclassification, p38, gives no "
                  "amount); the table taken on its own implies gross incurred 115.1m against 78.3m in the accounts "
                  "(+47%), the 2021 control tying (-1.1%). The 2021 report's printed cells as the base reproduce the "
                  "year's accounts once the merged '2016 & Prior' column, which both readers call unreadable as a cohort "
                  "(P4: its cumulative paid falls 17.7m, 'no payment can do'; Q3: not like for like, not measurable), is "
                  "set aside: 79.255m on the 2017-2022 columns against 78.306m (+1.2%, Q3), and 78.9m against 78.3m "
                  "(+0.8%, review 8). M (u <= 2020) does not use the merged column on either base. Decision of the "
                  "Claude analysis session, 23 October 2026, after review 8: rule 3, not rule 1 (the year t-1 base "
                  "reconciles)"),
        "derivation": ("u <= 2020, the 2022 table's latest cells less the 2021 report's printed latest cells: 2017 "
                       "331,324-349,613 = -18,289; 2018 233,193-249,006 = -15,813; 2019 187,713-207,954 = -20,241; "
                       "2020 284,422-310,094 = -25,672; -80,015 (USD 000), i.e. -80.015m USD (both readers); the 2022 "
                       "table's own end-2021 cells give -44.371m"),
        "readers": {"P4": {"stated": "On the 2021 report's end-2021 cells the same four columns give -80.015m",
                           "cells": "m_recomputed_note"},
                    "Q3": {"terms": "-18,289 -15,813 -20,241 -25,672 = -80,015", "cells": "m_working"}},
    },
}
#: the misprinted underwriting year of 1274/2016 and the first underwriting year of its table (the previous report's
#: cells are listed from it)
MISPRINT_YEAR, FIRST_YEAR = 2012, 2008

SESSION_23_OCT = "decision of the Claude analysis session, 23 October 2026 (after review 8)"
OWNER = ("owner's decision, 22 October 2026 (option c): the primary outcome is the mature-cohort movement of "
         "Equation (1), and a valid mature-cohort triangle figure is never replaced merely because a broader movement "
         "has the other sign")


# --------------------------------------------------------------------------------------------- the estimator
def extraction_root():
    return os.environ.get(EXTRACTION_ENV) or EXTRACTION_DEFAULT


def extraction_blob(path, root=None, pin=None):
    """`path` at the pinned commit of the extraction checkout, as text (LF)."""
    import record_tests
    root = root or extraction_root()
    pin = pin or record_tests.extraction_pin()
    r = subprocess.run(["git", "-C", root, "cat-file", "blob", "%s:%s" % (pin, path)], capture_output=True)
    if r.returncode != 0:
        raise SystemExit("the extraction checkout %s does not hold %s at the pinned commit %s (%s): set %s"
                         % (root, path, pin, r.stderr.decode("utf-8", "replace").strip(), EXTRACTION_ENV))
    return r.stdout.decode("utf-8").replace("\r\n", "\n")


def estimator(root=None, pin=None, source=None, table_source=None):
    """compute_pyd_from_triangle and its helpers, exec'd from the pinned test_gemini.py's syntax tree (the named
    definitions only), with table_extraction.py's two constants checked against that file at the pin."""
    source = source if source is not None else extraction_blob("test_gemini.py", root, pin)
    table_source = table_source if table_source is not None else extraction_blob("table_extraction.py", root, pin)
    for name, value in TABLE_CONSTANTS.items():
        if "\n%s = %r\n" % (name, value) not in table_source:
            raise SystemExit("table_extraction.py at the pin does not set %s = %r" % (name, value))
    keep, found = [], set()
    for node in ast.parse(source).body:
        if isinstance(node, ast.FunctionDef) and node.name in ESTIMATOR_NAMES:
            keep.append(node)
            found.add(node.name)
        elif isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id in ESTIMATOR_NAMES
                                                  for t in node.targets):
            keep.append(node)
            found.update(t.id for t in node.targets if isinstance(t, ast.Name))
    missing = set(ESTIMATOR_NAMES) - found
    if missing:
        raise SystemExit("test_gemini.py at the pin lacks %s" % sorted(missing))
    ns = dict(TABLE_CONSTANTS)
    exec(compile(ast.Module(body=keep, type_ignores=[]), "test_gemini.py@pin", "exec"), ns)
    return ns["compute_pyd_from_triangle"]


def compute(fn, tri, year):
    import copy
    return fn(copy.deepcopy(tri), int(year))


# --------------------------------------------------------------------------------------------- the corpus rule
def displaced_by(block):
    """The precedence rules that displaced the block's gross RAG triangle ("sign_override", "veto"), or ()."""
    tri = block.get("_rag_triangle")
    if not (isinstance(tri, dict) and tri.get("underwriting_years") and tri.get("type") == "gross"):
        return ()
    why = []
    if str((block.get("_pyd_route") or {}).get("source") or "").startswith("rag_provisions"):
        why.append("sign_override")
    if VETO_NOTE.search(block.get("data_quality_notes") or ""):
        why.append("veto")
    return tuple(why)


def population(records_dir=RECORDS):
    """{key: {model: rules}} for every record of the corpus with a block whose gross triangle a rule displaced."""
    out = {}
    for path in sorted(glob.glob(str(Path(records_dir) / "syndicate_*.json"))):
        key = os.path.basename(path)[len("syndicate_"):-len(".json")]
        with io.open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        for mk, block in sorted((data.get("models") or {}).items()):
            if isinstance(block, dict) and displaced_by(block):
                out.setdefault(key, {})[mk] = list(displaced_by(block))
    return out


def canonical_key(data):
    """The adopted model, by load_and_classify's model resolution."""
    models = data.get("models") or {}
    keys = sorted(models)
    if not keys:
        return None
    if (data.get("validation") or {}).get("passed") is True:
        return keys[0]
    cands = [(k, models[k].get("prior_year_movement_confidence", 0) or 0) for k in keys
             if isinstance(models[k], dict) and models[k].get("prior_year_development_pct") is not None]
    if not cands:
        return None
    return cands[0][0] if len(cands) == 1 else max(cands, key=lambda c: c[1])[0]


# --------------------------------------------------------------------------------------------- evidence
def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _pages(v):
    if isinstance(v, str):
        try:
            v = json.loads(v)
        except ValueError:
            return []
    return [int(p) for p in (v or []) if isinstance(p, (int, float)) and not isinstance(p, bool) and int(p) >= 1]


def load_readings():
    out = {}
    for rid in READERS:
        with io.open(EVIDENCE / "readings" / ("%s.json" % rid), encoding="utf-8") as fh:
            for key, r in json.load(fh).items():
                out.setdefault(key, []).append((rid, r))
    return out


def round_reading(rid, r):
    stated = r.get("stated_prior_year_line") or {}
    return {"kind": "reading", "reader": rid, "round": ROUNDS.get(rid, READING_ROUND),
            "source": "results/extraction_error_rate/mature-cohort/readings/%s.json" % rid,
            "pages": _pages(r.get("pages")), "read_by": r.get("read_by"),
            "table": r.get("table"), "verdict": r.get("verdict"),
            "figure_m": _num(r.get("recomputed_mature_figure_m")), "cells": r.get("cells"),
            "x_and_prior": r.get("x_and_prior"), "reconciliation": r.get("reconciliation"),
            "transaction": r.get("transaction"),
            "stated_prior_year_line": {k: stated.get(k) for k in ("value_m", "page", "quote", "stated_less_triangle_m")
                                       if k in stated} or None}


def _walk_study(obj, path, keys, out):
    if isinstance(obj, dict):
        stem = obj.get("stem")
        if isinstance(stem, str) and stem.startswith("syndicate_") and "triangle_recomputation_m" in obj:
            key = stem[len("syndicate_"):]
            if key in keys:
                out.setdefault(key, []).append((path, obj))
        for v in obj.values():
            _walk_study(v, path, keys, out)
    elif isinstance(obj, list):
        for v in obj:
            _walk_study(v, path, keys, out)


def study_readings(keys):
    """The error-rate study's earlier readings that recomputed a record's printed triangle (merged files only: a
    batch file repeats its merged file's entry)."""
    out = {}
    for path in sorted(glob.glob(str(STUDY / "**" / "*.json"), recursive=True)):
        base = os.path.basename(path)
        if re.search(r"-batch-\d+\.json$", base) or not any(w in base for w in ("verdict", "verification", "reading")):
            continue
        try:
            with io.open(path, encoding="utf-8") as fh:
                obj = json.load(fh)
        except ValueError:
            continue
        _walk_study(obj, Path(path).relative_to(HERE).as_posix(), set(keys), out)
    return out


def study_reading(path, row):
    who = row.get("second_reader") or row.get("first_reader")
    return {"kind": "error_rate_study", "reader": "error-rate study, %s%s" % (path, (" (%s)" % who) if who else ""),
            "source": path, "pages": _pages(row.get("triangle_pages")),
            "verdict": "printed triangle recomputed; the study's verdict on the then adopted figure: %s"
                       % row.get("verdict"),
            "figure_m": _num(row.get("triangle_recomputation_m")), "cells": row.get("triangle_arithmetic")}


def table_read(model, tri, figure, details, printed_page):
    page = tri.get("source_page")
    pages = [page] if isinstance(page, int) and page >= 1 else ([printed_page] if printed_page else [])
    lines = [ln.strip() for ln in str(details).splitlines() if ln.strip()]
    return {"kind": "extraction_table_read",
            "reader": "the extraction's table read: the stored grid models.%s._rag_triangle, recomputed by "
                      "compute_pyd_from_triangle at the pinned commit" % model,
            "source": "pdf_extraction/ (the record file)",
            "pages": pages,
            "verdict": "the grid the table backend transcribed from the printed page%s" % (
                "" if isinstance(page, int) else " (the grid records no page; the readers place the table on p%s)"
                % printed_page),
            "figure_m": figure, "cells": "; ".join(lines)}


def strip_aggregated_column(tri, key):
    """A copy of a stored grid without its aggregated development-age column (the first column, whose label and anchor
    year AGGREGATED_COLUMN names), for the extraction's estimator."""
    want = AGGREGATED_COLUMN[key]
    agg = tri.get("aggregated_cohort") or {}
    years = list(tri.get("underwriting_years") or [])
    if agg.get("anchor") != want["anchor"] or agg.get("column") != 1 or not years or years[0] != want["anchor"]:
        raise SystemExit("%s: the stored grid's aggregated cohort %r is not the first column anchored at %s"
                         % (key, agg, want["anchor"]))
    if want["label"].replace(" ", "") not in str(agg.get("label", "")).replace(" ", ""):
        raise SystemExit("%s: the stored grid's aggregated column is %r, not %r" % (key, agg.get("label"), want["label"]))
    extra = set(tri) - {"type", "currency", "units", "units_evidence", "cell_binding", "underwriting_years",
                        "development_rows", "row_labels", "aggregated_cohort", "source_page", "entity"}
    if extra:
        raise SystemExit("%s: the stored grid has fields %s this build does not strip by column" % (key, sorted(extra)))
    out = copy.deepcopy(tri)
    out["underwriting_years"] = years[1:]
    out["development_rows"] = [list(row)[1:] for row in tri["development_rows"]]
    del out["aggregated_cohort"]
    return out


def column_blocks(data):
    """{model: ["aggregated_column"]} for every block whose stored gross RAG triangle carries an aggregated cohort (the
    blocks of a COLUMN_ONLY record the corpus rule does not see)."""
    out = {}
    for mk, block in sorted((data.get("models") or {}).items()):
        tri = block.get("_rag_triangle") if isinstance(block, dict) else None
        if isinstance(tri, dict) and tri.get("type") == "gross" and tri.get("aggregated_cohort"):
            out[mk] = ["aggregated_column"]
    return out


def gross_blocks(data, by):
    """{model: [by]} for every block of a CORRECTIONS record that holds a gross RAG triangle."""
    out = {}
    for mk, block in sorted((data.get("models") or {}).items()):
        tri = block.get("_rag_triangle") if isinstance(block, dict) else None
        if isinstance(tri, dict) and tri.get("type") == "gross" and tri.get("underwriting_years"):
            out[mk] = [by]
    return out


def load_column_readings():
    out = {}
    for rid in COLUMN_READERS:
        with io.open(COLUMN_READINGS / ("%s.json" % rid), encoding="utf-8") as fh:
            out[rid] = json.load(fh)
    for rids in COLUMN_READERS_R2.values():
        for rid in rids:
            with io.open(ROUND2 / "readings" / ("%s.json" % rid), encoding="utf-8") as fh:
                out[rid] = json.load(fh)
    return out


def _r2_entry(rid, key, files):
    """A round-2 reader's entry for `key`: the X and Y arms key their readings '<key>|aggregated_column', the tie-break
    readers Z1 and Z2 '<key>'."""
    f = files[rid]
    return f["%s|aggregated_column" % key] if rid[0] in "XY" else f[key]


def _r2_pages(rid, e, key):
    """The year t report's pages from a round-2 reader's `pages`: a list (X, Y) or a dict keyed by report (Z1, Z2:
    'year_t' or '<t>_report'; Z1's values are strings such as '2022 report p51 (printed 49)')."""
    pages = e["pages"]
    if isinstance(pages, list):
        return [p for p in pages if isinstance(p, int)]
    year = key.split("_")[1]
    out = []
    for name, val in pages.items():
        if name in ("year_t", "%s_report" % year) or name.endswith(key):
            vals = val if isinstance(val, list) else [int(m) for m in re.findall(r"\bp(\d+)", str(val))][:1]
            out += [p for p in vals if isinstance(p, int)]
    return out


def column_reading_r2(rid, key, files):
    """One of the round-2 readers' readings of a 1945 record, in the register's reading form. X4 and Y5 give
    figure_including_column_m / figure_excluding_column_m and the cells in cells_used; Z1 and Z2 give figure_including_m
    / figure_excluding_m, with the cells in rule_figure_cells (Z1) or note (Z2)."""
    e = _r2_entry(rid, key, files)
    without = e.get("figure_excluding_column_m", e.get("figure_excluding_m"))
    with_col = e.get("figure_including_column_m", e.get("figure_including_m"))
    if rid[0] in "XY":
        cells = "%s; sum %s excluding the column, %s including it" % (e["cells_used"], without, with_col)
        table = {k: e["table_t"].get(k) for k in ("page", "heading", "basis")}
        x_and_prior = "%s: %s" % (e["table_t"]["column_label"], e["table_t"]["column_cells"])
        recon = e["note"]
    else:
        cells = e.get("rule_figure_cells") or e["note"]
        table = {"page": (_r2_pages(rid, e, key) or [None])[0], "heading": e["layout"], "basis": "gross"}
        x_and_prior = json.dumps(e["column_cells_t"], ensure_ascii=False)
        recon = e["note"]
    return {"kind": "reading", "reader": rid, "round": COLUMN_ROUND_R2,
            "source": "results/extraction_error_rate/mature-cohort/round2/readings/%s.json" % rid,
            "pages": _r2_pages(rid, e, key), "read_by": e.get("read_by"), "table": table,
            "verdict": "confirmed_excluding_the_aggregated_column", "figure_m": _num(without),
            "figure_with_column_m": _num(with_col), "cells": cells, "x_and_prior": x_and_prior,
            "construction": e["construction"], "reconciliation": recon, "transaction": None}


def column_reading(rid, key, e):
    """One of the two column readers' readings of a 1945 record, in the register's reading form. F1 and F2 recompute
    the mature-cohort figure from the printed gross table without the aggregated column, and give the figure with it."""
    f = e["figure"]
    without = f.get("mature_excluding_and_prior_m", f.get("excluding_aggregated_column_m"))
    with_col = f.get("mature_including_and_prior_m", f.get("including_aggregated_column_m"))
    pages = e["pages"]
    own = pages.get(key, []) if isinstance(pages, dict) else pages
    other = {k: v for k, v in pages.items() if k != key} if isinstance(pages, dict) else {}
    if "cells_used" in e:
        cells = "; ".join("%s %s" % (y, t) for y, t in e["cells_used"].items())
        cells = "u<=%d (000s) without the column: %s; sum %+.3f excluding the column, %+.3f including it" % (
            max(int(y) for y in e["cells_used"]), cells, without, with_col)
        x_and_prior = e["and_prior_column"]
    else:
        cells = e["cells"]
        x_and_prior = e["x_and_prior"]
    out = {"kind": "reading", "reader": rid, "round": COLUMN_ROUND,
           "source": "results/extraction_error_rate/mature-cohort/fx-translation/readings/%s.json" % rid,
           "pages": _pages(own), "read_by": e.get("read_by"), "table": e.get("table"),
           "verdict": "confirmed_excluding_the_aggregated_column", "figure_m": _num(without),
           "figure_with_column_m": _num(with_col), "cells": cells, "x_and_prior": x_and_prior,
           "reconciliation": e.get("reconciliation"), "transaction": e.get("transaction")}
    if other:
        out["pages_of_the_earlier_report"] = {k: _pages(v) for k, v in other.items()}
    return out


def column_entry(entry, key, tri, year, fn, figure_with, model, printed_page, column_files, earlier):
    """Complete the figure entry of an AGGREGATED_COLUMN record: the figure is the estimator's on the stored grid
    without the column, and both column readers' (F1, F2); the figure with the column is the stored grid's own, the
    earlier readings of it (A4, C2) are kept under superseded_readings."""
    col = AGGREGATED_COLUMN[key]
    figure, details = compute(fn, strip_aggregated_column(tri, key), year)
    if figure is None:
        raise SystemExit("%s: the estimator computes no figure without the aggregated column: %s" % (key, details))
    if key in COLUMN_READERS_R2:
        reads = [column_reading_r2(rid, key, column_files) for rid in COLUMN_READERS_R2[key]]
    else:
        reads = [column_reading(rid, key, column_files[rid][key]) for rid in COLUMN_READERS]
    for r in reads:
        if r["figure_m"] is None or abs(r["figure_m"] - figure) > FIGURE_TOL:
            raise SystemExit("%s: reader %s's figure %s is not the estimator's %s without the column"
                             % (key, r["reader"], r["figure_m"], figure))
        if r["figure_with_column_m"] is None or abs(r["figure_with_column_m"] - figure_with) > FIGURE_TOL:
            raise SystemExit("%s: reader %s's figure with the column %s is not the stored grid's %s"
                             % (key, r["reader"], r["figure_with_column_m"], figure_with))
    currency, gbp = fx_gbp(key, figure)
    entry.update({"figure_m": figure, "figure_gbp_m": gbp, "figure_kind": "triangle"})
    entry["recomputation"].update({"figure_with_column_m": figure_with, "figure_without_column_m": figure,
                                   "estimator_without_column": "the same estimator on the stored grid with its "
                                                               "first column removed (strip_aggregated_column)"})
    r2 = key in COLUMN_READERS_R2
    entry["aggregated_column"] = {"label": col["label"], "anchor": col["anchor"],
                                  "rule": COLUMN_RULE_R2 if r2 else COLUMN_RULE,
                                  "figure_with_column_m": figure_with, "figure_without_column_m": figure,
                                  "column_step_m": round(figure_with - figure, 3)}
    entry["readings"] = reads
    if earlier:
        entry["superseded_readings"] = earlier
    gaps = independent_reading_gaps(entry)
    if gaps:
        raise SystemExit("%s: a figure entry needs two independent agent readings of the filing: %s" % (key, "; ".join(gaps)))
    tr = table_read(model, strip_aggregated_column(tri, key), figure, details, printed_page)
    tr["verdict"] += "; the aggregated column '%s' left out (Appendix 2.1)" % col["label"]
    entry["table_read"] = tr
    entry["pages"] = sorted({p for r in reads for p in r["pages"]})
    entry["quote"] = " | ".join("reader %s, p%s: %s" % (r["reader"], (r.get("table") or {}).get("page"), r["cells"])
                                for r in reads)
    if key in NOTES:
        entry["notes"] = [dict(n) for n in NOTES[key]]
    entry["status"] = "primary"
    if r2:
        entry["decision"] = ("decision of the Claude analysis session, 23 October 2026, applying Appendix 2.1's rule "
                             "(the column's last step must be a like-for-like movement during year t) to the aggregated "
                             "column '%s' of %s, which four independent readings (%s) find built by development age: "
                             "the column is left out of the mature-cohort figure; primary; a valid mature-cohort "
                             "figure: the printed gross table's own development over u <= t-2 without that column; "
                             "under the %s" % (col["label"], key, ", ".join(COLUMN_READERS_R2[key]), OWNER))
        return entry
    entry["decision"] = ("decision of the Claude analysis session, 22 October 2026, applying the author's decision of "
                         "22 October 2026 that Appendix 2.1's rule leaves the aggregated column '%s' out of the "
                         "mature-cohort figure (%s): primary; a valid mature-cohort figure: the printed gross table's "
                         "own development over u <= t-2 without that column; under the %s"
                         % (col["label"], key, OWNER))
    return entry


_NUM = r"[\d,]+(?:\.\d+)?"
#: a printed cell in thousands with its separators (209,137): not a year, an age or a page
_CELL = r"\d{1,3}(?:,\d{3})+"


def _n(s):
    return float(s.replace(",", ""))


def _snip(text, snippet, key, rid, what):
    if snippet not in text:
        raise SystemExit("%s: reader %s's %s snippet is not in the archived reading: %r" % (key, rid, what, snippet))
    return snippet


def _terms(snippet):
    """{year: signed term} from a snippet of per-year signed terms ('2013 -926; 2014 +453' or '2008 208,456-209,137=-681'),
    or [terms] from a bare sum ('-926+453+6,174 = +19,331', the part before '=')."""
    by_year = re.findall(r"(20\d\d) (?:%s-%s=)?([+-]%s)" % (_NUM, _NUM, _NUM), snippet)
    if by_year:
        return {int(y): _n(v) for y, v in by_year}
    return [_n(v) for v in re.findall(r"([+-]?%s)" % _NUM, snippet.split("=")[0])]


def _quoted(text, cell, key, rid, what):
    if cell not in text:
        raise SystemExit("%s: reader %s does not quote the %s cell %s" % (key, rid, what, cell))
    return cell


def _paid_cell(pair, text, key, rid, what):
    """A paid cell of the 2012 column: the reader's snippet that holds it, and the cell, which the snippet must show."""
    snippet, cell = pair
    if cell not in _snip(text, snippet, key, rid, what):
        raise SystemExit("%s: reader %s's %s snippet does not show the cell %s" % (key, rid, what, cell))
    return _n(cell)


def derived_cells(key=None):
    """The cell strings the derived figure of 1274/2016 uses (CORRECTIONS[...]['cells_used']), flattened and sorted."""
    c = (CORRECTIONS[key or "1274_2016"])["cells_used"]
    out = set()
    for pair in c["other_years_latest_and_end_2015"].values():
        out.update(pair)
    out.update(v for k, v in c.items() if isinstance(v, str))
    return sorted(out)


def misprint_figure(spec, text, key, rid):
    """1274/2016: the figure with the misprinted MISPRINT_YEAR cell replaced by the previous report's cell at the MISPRINT
    YEAR COLUMN'S OWN exchange factor (its paid cell at end-(t-1) in the year t table over the same cell in the previous
    report), from cells the reader quotes. The other years' terms are the sums of the reader's own cells (the table's
    latest cell less its end-(t-1) cell), checked against the reader's terms snippet. DERIVED, not a figure the reader
    gives: the reader's own figure is kept apart by correction_reading."""
    c = CORRECTIONS[key]
    terms = _terms(_snip(text, spec["terms"], key, rid, "terms"))
    latest = _n(re.findall(_CELL, _snip(text, spec["latest"], key, rid, "latest cell"))[-1])
    prev = [_n(x) for x in re.findall(_CELL, _snip(text, spec["prev_cells"], key, rid, "previous report's cells"))]
    prev_misprint = prev[MISPRINT_YEAR - FIRST_YEAR]
    paid_t = _paid_cell(spec["paid_t"], text, key, rid, "paid cell of the year t table")
    paid_prev = _paid_cell(spec["paid_prev"], text, key, rid, "paid cell of the previous report")
    quoted = [_quoted(text, cell, key, rid, "derivation") for cell in derived_cells(key)]
    other = sum(_n(a) - _n(b) for a, b in c["cells_used"]["other_years_latest_and_end_2015"].values())
    if other != sum(v for y, v in terms.items() if y != MISPRINT_YEAR):
        raise SystemExit("%s: reader %s's terms %s are not the cells' differences %s" % (key, rid, terms, other))
    if latest != _n(c["cells_used"]["misprinted_year_latest"]) or prev_misprint != _n(c["cells_used"]["previous_report_cell"]):
        raise SystemExit("%s: reader %s's latest or previous-report cell is not the one the derivation uses" % (key, rid))
    factor = paid_t / paid_prev
    corrected = prev_misprint * factor
    lo, hi = other_factor_range(c, text, key, rid)
    figure = round((other + latest - corrected) / 1000.0, 4)
    return figure, {
        "other_years_k": other, "latest_cell_k": latest, "factor": round(factor, 6), "paid_t_cell_k": paid_t,
        "paid_previous_cell_k": paid_prev, "previous_report_cell_k": prev_misprint, "corrected_cell_k": round(corrected, 1),
        "range_other_factors_m": [lo, hi], "cells_quoted": quoted}


def other_factor_range(c, text, key, rid):
    """The figures the other columns' end-(t-1) cell ratios (the year t table's over the previous report's) give as the
    misprinted column's factor: (lowest, highest), each cell quoted by the reader."""
    other = sum(_n(a) - _n(b) for a, b in c["cells_used"]["other_years_latest_and_end_2015"].values())
    latest, prev = _n(c["cells_used"]["misprinted_year_latest"]), _n(c["cells_used"]["previous_report_cell"])
    figs = []
    for a, b in c["other_factor_cells"].values():
        _quoted(text, a, key, rid, "other column's end-(t-1)")
        _quoted(text, b, key, rid, "other column's previous-report")
        figs.append(round((other + latest - prev * _n(a) / _n(b)) / 1000.0, 3))
    return min(figs), max(figs)


def correction_reading(key, rid, spec, round_name):
    """One reading of a CORRECTIONS record in the register's reading form, with the figure the spec reads or derives."""
    import build_restated_base_excluded as RB
    with io.open(ROUND5_READINGS / ("%s.json" % rid), encoding="utf-8") as fh:
        e = json.load(fh)[key]
    text = json.dumps(e, ensure_ascii=False)
    out = {"kind": "reading", "reader": rid, "round": round_name,
           "source": "results/extraction_error_rate/mature-cohort/round5/readings/%s.json" % rid,
           "pages": RB.split_pages(key, e.get("pages"))[0], "read_by": e.get("read_by"),
           "verdict": e.get("verdict"), "reader_figure_m": None}
    own = e.get("m_recomputed_m")
    out["reader_figure_m"] = own if isinstance(own, (int, float)) else e.get(spec.get("field") or "m_recomputed_m")
    if "field" in spec:
        out["figure_m"] = _num(e[spec["field"]])
        out["figure_from"] = "the reader's own figure (%s)" % spec["field"]
    elif "stated" in spec:
        m = re.findall(r"([+-]\d+(?:\.\d+)?)m", _snip(text, spec["stated"], key, rid, "stated figure"))
        if len(m) != 1:
            raise SystemExit("%s: reader %s's stated snippet holds %d signed figures, not one" % (key, rid, len(m)))
        out["figure_m"] = float(m[0])
        out["figure_from"] = "the figure the reader states: %s" % spec["stated"]
    elif "terms" in spec:
        t = _terms(_snip(text, spec["terms"], key, rid, "terms"))
        out["figure_m"] = round(sum(t.values() if isinstance(t, dict) else t) / 1000.0, 4)
        out["figure_from"] = "the sum of the reader's own terms: %s" % spec["terms"]
    else:
        # a DERIVED correction (1274/2016): figure_m stays the reader's own figure as given (the printed table's, which the
        # reader flags as carrying a misprint); the derived figure is kept apart under derived_figure_m, with the cells
        # the reader quotes
        ms = spec["misprint"]
        out["figure_m"] = out["reader_figure_m"]
        out["derived_figure_m"], parts = misprint_figure(ms, text, key, rid)
        out["cells_quoted"] = parts.pop("cells_quoted")
        out["derived_parts"] = parts
        out["figure_from"] = ("the reader's own figure (m_recomputed_m), as printed with the misprinted cell; the "
                              "corrected figure is DERIVED by the build from the reader's quoted cells, not given by the "
                              "reader (derived_figure_m): %s" % json.dumps(parts))
        if "sensitivity" in ms:
            s = re.findall(r"([+-]\d[\d,]*) \(USD k\)", _snip(text, ms["sensitivity"], key, rid, "sensitivity"))
            out["reader_sensitivity_m"] = _n(s[0]) / 1000.0
            out["reader_sensitivity_note"] = ("the reader's own sensitivity with the previous report's 2012 cell "
                                              "unretranslated: %s" % ms["sensitivity"])
    cells = e.get(spec["cells"]) or e.get("cells_check")
    out["cells"] = cells if isinstance(cells, str) else json.dumps(cells, ensure_ascii=False)
    out["table"] = {"page": (out["pages"] or [None])[0], "basis": e.get("basis") or "gross"}
    out["note"] = e.get("note")
    return out


def correction_entry(entry, key, tri, year, figure_printed, details, model, printed_page):
    """Complete the entry of a CORRECTIONS record: the corrected figure every reading gives, the correction object (with
    the printed table's own figure, which the estimator recomputes from the stored grid and which is the adopted block's)
    and the readings."""
    c = CORRECTIONS[key]
    if figure_printed is None or abs(figure_printed - entry["displaced"]["figure_m"]) > FIGURE_TOL:
        raise SystemExit("%s: the stored grid's figure %s is not the adopted figure %s the correction replaces"
                         % (key, figure_printed, entry["displaced"]["figure_m"]))
    reads = [correction_reading(key, rid, spec, spec.get("round", ROUND5_ROUND)) for rid, spec in c["readers"].items()]
    derived = bool(c.get("derived"))
    # a derived correction's figure is the build's own derivation from the cells each reader quotes (derived_figure_m);
    # any other correction's figure is the one every reader gives (figure_m)
    which = "derived_figure_m" if derived else "figure_m"
    figure = round(reads[0][which], 4)
    for r in reads:
        if r.get(which) is None or abs(r[which] - figure) > FIGURE_TOL:
            raise SystemExit("%s: reader %s's corrected figure %s is not reader %s's %s" % (
                key, r["reader"], r.get(which), reads[0]["reader"], figure))
    currency, gbp = fx_gbp(key, figure)
    entry.update({"figure_m": figure, "figure_gbp_m": gbp, "figure_kind": "triangle"})
    entry["correction"] = {"rule": c["rule"], "cause": c["cause"], "derivation": c["derivation"],
                           "figure_as_printed_m": figure_printed}
    if derived:
        lows = [r["derived_parts"]["range_other_factors_m"] for r in reads]
        if any(x != lows[0] for x in lows):
            raise SystemExit("%s: the readers' ranges of other factors differ: %s" % (key, lows))
        entry["correction"].update({
            "derived_figure_m": figure, "derived_by": SESSION_23_OCT,
            "factor": reads[0]["derived_parts"]["factor"],
            "factor_basis": ("the 2012 column's own paid cells at end-2015: 129,350 (2016 table) over 131,423 (2015 "
                             "report)"),
            "cells_used": derived_cells(key),
            "range_other_factors_m": lows[0],
            "range_other_factors_basis": ("the ratio of each other column's end-2015 cell in the 2016 table to the 2015 "
                                          "report's latest cell (2008-2011, 2013-2015: 0.96766 to 0.98919) as the "
                                          "misprinted column's factor; review 8 quotes +21.8m to +25.6m"),
            "figure_before_review_8_m": 23.5435,
            "figure_before_review_8_basis": "the 2008 column's factor 209,137 / 213,518 = 0.97948"})
    entry["readings"] = reads
    if c.get("superseded"):
        entry["superseded_readings"] = [correction_reading(key, rid, spec, ROUND5_ROUND)
                                        for rid, spec in c["superseded"].items()]
    gaps = independent_reading_gaps(entry)
    if gaps:
        raise SystemExit("%s: a figure entry needs two independent agent readings of the filing: %s" % (key, "; ".join(gaps)))
    tr = table_read(model, tri, figure_printed, details, printed_page)
    tr["verdict"] += "; the printed table's own figure, which the correction replaces"
    entry["table_read"] = tr
    entry["pages"] = sorted({p for r in reads for p in r["pages"]})
    entry["quote"] = " | ".join("reader %s, p%s: %s" % (r["reader"], r["table"]["page"], r["cells"]) for r in reads)
    entry["status"] = "primary"
    if derived:
        entry["decision"] = ("decision of the Claude analysis session, 23 October 2026 (after review 8), applying %s: "
                             "%s; the register carries the corrected figure DERIVED from the cells both readers (%s) "
                             "quote, at the misprinted column's own exchange factor (a figure neither reader gives), in "
                             "place of the printed table's own (%s); primary, and listed with the least-certain records "
                             "(data/restated_base_excluded.json, history_restated, clause derived_correction); under "
                             "the %s" % (c["rule"], c["cause"], ", ".join(r["reader"] for r in reads), figure_printed,
                                         OWNER))
        return entry
    entry["decision"] = ("decision of the Claude analysis session, 23 October 2026, applying %s: %s; the register carries "
                         "the corrected figure the readings give (%s) in place of the printed table's own (%s); "
                         "primary; under the %s" % (c["rule"], c["cause"], ", ".join(r["reader"] for r in reads),
                                                    figure_printed, OWNER))
    return entry


def independent_reading_gaps(entry):
    """Why a figure entry does not rest on two independent agent readings of the filing, or []: every reading is an
    agent's (AGENT_READING_KINDS; the extraction's table read is not a reading), at least two distinct readers, at
    least one of them a reader's own reading of 22 October 2026, and each with its pages and cells, giving the
    entry's figure. A DERIVED correction (correction.derived_figure_m: 1274/2016, whose figure no reader gives) is allowed
    only when it records its derivation, its figure is the one each reader's quoted cells give (the reading's
    derived_figure_m, kept apart from the reader's own figure_m), and both readers quote every cell the derivation uses
    (correction.cells_used, each in the reading's cells_quoted)."""
    reads = entry.get("readings") or []
    corr = entry.get("correction") if isinstance(entry.get("correction"), dict) else {}
    derived = corr.get("derived_figure_m") is not None
    gaps = ["reading %d is not an agent's reading (kind %r)" % (i, r.get("kind"))
            for i, r in enumerate(reads) if r.get("kind") not in AGENT_READING_KINDS]
    agents = [r for r in reads if r.get("kind") in AGENT_READING_KINDS]
    if len({r.get("reader") for r in agents if r.get("reader")}) < 2:
        gaps.append("two distinct readers (%s)" % sorted({str(r.get("reader")) for r in agents}))
    if not any(r.get("kind") == "reading" for r in agents):
        gaps.append("a reader's own reading (kind 'reading')")
    if derived:
        if abs(corr["derived_figure_m"] - entry["figure_m"]) > FIGURE_TOL:
            gaps.append("a derived figure %s equal to the entry's %s" % (corr["derived_figure_m"], entry["figure_m"]))
        if not str(corr.get("derivation") or "").strip():
            gaps.append("a recorded derivation")
        if not corr.get("cells_used"):
            gaps.append("the cells the derivation uses (correction.cells_used)")
    for i, r in enumerate(agents):
        if not r.get("pages") or not str(r.get("cells") or "").strip():
            gaps.append("reading %s's pages and cells" % r.get("reader"))
        if derived:
            if r.get("derived_figure_m") is None or abs(r["derived_figure_m"] - entry["figure_m"]) > FIGURE_TOL:
                gaps.append("reading %s's derived figure %s against the entry's %s" % (
                    r.get("reader"), r.get("derived_figure_m"), entry["figure_m"]))
            missing = sorted(set(corr.get("cells_used") or []) - set(r.get("cells_quoted") or []))
            if missing:
                gaps.append("reading %s quotes every cell the derivation uses (missing %s)" % (r.get("reader"), missing))
        elif r.get("figure_m") is None or abs(r["figure_m"] - entry["figure_m"]) > FIGURE_TOL:
            gaps.append("reading %s's figure %s against the entry's %s" % (r.get("reader"), r.get("figure_m"),
                                                                           entry["figure_m"]))
    return gaps


def load_csv(path):
    with io.open(path, encoding="utf-8", newline="") as fh:
        return {r["key"]: r for r in csv.DictReader(fh)}


def fx_gbp(key, figure):
    import run_analysis as ra
    currency = ra.FX_CURRENCIES.get(key, "UNDETERMINED")
    if currency != "USD" or figure is None:
        return currency, (None if figure is None else round(figure, 6))
    rate = ra.FX_RATES[int(key.rsplit("_", 1)[1])]["usd_per_gbp"]
    return currency, round(figure / rate, 6)


# --------------------------------------------------------------------------------------------- the register
def entry_for(key, data, pop_blocks, fn, decisions, design, readings, study, column_files=None):
    year = int(key.split("_")[1])
    ck = canonical_key(data)
    cm = data["models"][ck]
    models = sorted(pop_blocks)
    model = ck if ck in pop_blocks else models[0]
    tri = cm.get("_rag_triangle") if ck in pop_blocks else data["models"][model]["_rag_triangle"]
    figure, details = compute(fn, tri, year)
    figures = set()
    for mk in models:
        f, _d = compute(fn, data["models"][mk]["_rag_triangle"], year)
        figures.add(f)
    if len(figures) != 1:
        raise SystemExit("%s: the displaced blocks' triangles compute to different figures %s" % (key, figures))
    route = cm.get("_pyd_route") or {}
    rules = displaced_by(cm)
    by = "sign_override" if "sign_override" in rules else ("veto" if "veto" in rules else None)
    if by is None and key in COLUMN_ONLY:
        by = "aggregated_column"
    if by is None and key in CORRECTIONS:
        by = CORRECTIONS[key]["by"]
    gate = None
    if by == "veto":
        m = [g for g in RAG_VETO.finditer(cm.get("data_quality_notes") or "")
             if figure is not None and abs(float(g.group(1)) - figure) <= FIGURE_TOL]
        gate = ("sign" if m[0].group(2).startswith("has") else "magnitude") if m else None
    d = design.get(key) or {}
    dec = decisions.get(key)
    printed_page = int(dec["triangle_page"]) if dec and dec.get("triangle_page", "").isdigit() else None
    years = list(tri.get("underwriting_years") or [])
    mature = [y for y in years if isinstance(y, int) and y <= year - 2]
    currency, gbp = fx_gbp(key, figure)
    entry = {
        "figure_m": None, "figure_gbp_m": None, "report_currency": currency, "figure_kind": None, "basis": "gross",
        "displaced": {"by": by, "veto_gate": gate, "route": route.get("source"),
                      "figure_m": _num(cm.get("prior_year_development_gbp_m")), "adopted_model": ck,
                      "blocks": {mk: pop_blocks[mk] for mk in models},
                      "status_under_precedence_672": d.get("current_status") or None,
                      "route_label": d.get("current_route") or None},
        "triangle": {"printed_page": printed_page, "stored_source_page": tri.get("source_page"),
                     "model": model, "type": tri.get("type"), "units": tri.get("units"),
                     "entity": tri.get("entity"), "underwriting_years": years, "mature_years": mature},
        "recomputation": {"estimator": "test_gemini.compute_pyd_from_triangle at the pinned extraction commit "
                                       "(record_tests.extraction_pin), parsed from the extraction checkout",
                          "figure_m": figure, "figure_gbp_m": gbp,
                          "refusal": None if figure is not None else str(details)},
        "reconciliation": {"census_class_deterministic": d.get("reconciliation_class_deterministic") or None,
                           "co_g_m": _num(d.get("CO_g")), "co_n_m": _num(d.get("CO_n")),
                           "table_latest_diagonal_m": _num(d.get("table_latest_diagonal")),
                           "shape_check": d.get("shape_check") or None,
                           "source": "results/extraction_error_rate/mature-cohort/design_per_record.csv "
                                     "(the census's own script on the "
                                     "stored grid), and each reading's reconciliation below"},
    }
    rr = [round_reading(rid, r) for rid, r in readings.get(key, [])]
    if key in NO_FIGURE:
        reason, why = NO_FIGURE[key]
        entry["reason"] = reason
        entry["reason_evidence"] = why
        entry["readings"] = rr
        entry["status"] = "no_figure"
        if rr:
            entry["pages"] = sorted({p for r in rr for p in r["pages"]})
            entry["quote"] = " | ".join("reader %s: %s" % (r["reader"], r["transaction"] or r["cells"]) for r in rr)
        entry["decision"] = ("decision of the Claude analysis session, 22 October 2026: no mature-cohort figure is "
                             "adopted (%s), under the %s" % (reason, OWNER))
        return entry
    if key in AGGREGATED_COLUMN:
        if figure is None:
            raise SystemExit("%s: the estimator computes no figure on the stored grid: %s" % (key, details))
        return column_entry(entry, key, tri, year, fn, figure, model, printed_page, column_files, rr)
    if key in CORRECTIONS:
        return correction_entry(entry, key, tri, year, figure, details, model, printed_page)
    if dec is None:
        raise SystemExit("%s: a displaced record with neither a decision (decisions.csv) nor a NO_FIGURE reason" % key)
    if figure is None:
        raise SystemExit("%s: decided with a figure, but the estimator computes none: %s" % (key, details))
    study_rows = [study_reading(p, row) for p, row in study.get(key, [])
                  if _num(row.get("triangle_recomputation_m")) is not None
                  and abs(_num(row.get("triangle_recomputation_m")) - figure) <= FIGURE_TOL]
    reads = rr + study_rows
    entry.update({"figure_m": figure, "figure_gbp_m": gbp, "figure_kind": "triangle"})
    entry["readings"] = reads
    gaps = independent_reading_gaps(entry)
    if gaps:
        raise SystemExit("%s: a figure entry needs two independent agent readings of the filing: %s"
                         % (key, "; ".join(gaps)))
    # supporting evidence, not a reading: the grid the extraction's table backend transcribed, which the figure is
    # recomputed from
    entry["table_read"] = table_read(model, tri, figure, details, printed_page)
    entry["pages"] = sorted({p for r in reads for p in r["pages"]})
    entry["quote"] = " | ".join("reader %s, p%s: %s" % (r["reader"], (r.get("table") or {}).get("page"), r["cells"])
                                for r in rr)
    if key in NOTES:
        entry["notes"] = [dict(n) for n in NOTES[key]]
    if key in TAKEON_EXCLUDED:
        entry["status"] = "excluded_takeon_not_development"
        rule = ("the take-on dominates the triangle's step: data/takeon_not_development.json holds the record with "
                "figure_route mature_cohort_triangle, so the loader adopts the figure and then tags the record "
                "TAKEON_NOT_DEVELOPMENT")
    else:
        entry["status"] = "primary"
        rule = "a valid mature-cohort figure: the printed gross table's own development over u <= t-2"
    agreed = dec.get("readers_agreed") or ""
    verdicts = ["%s %s" % (r["reader"], r["verdict"]) for r in rr]
    if agreed != "yes":
        readers_note = "; readers: " + agreed
    elif len({r["verdict"] for r in rr}) > 1:
        readers_note = "; readers disagree (%s), settled under the existing rules in notes" % ", ".join(verdicts)
    else:
        readers_note = ""
    entry["decision"] = ("decision of the Claude analysis session, 22 October 2026 "
                         "(results/extraction_error_rate/mature-cohort/"
                         "decisions.csv, adjudication.md): %s; %s; under the %s%s"
                         % (dec.get("final_status"), rule, OWNER, readers_note))
    return entry


def build():
    import run_analysis as ra  # noqa: F401  (FX tables)
    fn = estimator()
    pop = population()
    decisions = load_csv(EVIDENCE / "decisions.csv")
    design = load_csv(EVIDENCE / "design_per_record.csv")
    readings = load_readings()
    study = study_readings(pop)
    missing = sorted(set(decisions) - set(pop))
    if missing:
        raise SystemExit("decided records outside the displaced population: %s" % missing)
    column_files = load_column_readings()
    if set(COLUMN_ONLY) & set(pop) or not set(COLUMN_ONLY) <= set(AGGREGATED_COLUMN):
        raise SystemExit("COLUMN_ONLY %s must be aggregated-column records no precedence rule displaced" % (COLUMN_ONLY,))
    blocks = dict(pop)
    for key in COLUMN_ONLY:
        with io.open(RECORDS / ("syndicate_%s.json" % key), encoding="utf-8") as fh:
            blocks[key] = column_blocks(json.load(fh))
    if set(CORRECTIONS) & (set(pop) | set(COLUMN_ONLY) | set(NO_FIGURE)):
        raise SystemExit("CORRECTIONS must be records no precedence rule displaced and no other list names")
    for key in CORRECTIONS:
        with io.open(RECORDS / ("syndicate_%s.json" % key), encoding="utf-8") as fh:
            blocks[key] = gross_blocks(json.load(fh), CORRECTIONS[key]["by"])
    reg = {"_purpose": PURPOSE}
    for key in sorted(blocks, key=lambda k: (int(k.split("_")[0]), int(k.split("_")[1]))):
        with io.open(RECORDS / ("syndicate_%s.json" % key), encoding="utf-8") as fh:
            data = json.load(fh)
        reg[key] = entry_for(key, data, blocks[key], fn, decisions, design, readings, study, column_files)
    return reg


PURPOSE = (
    "Mature-cohort figures of the primary outcome (the owner's decision, 22 October 2026, option c): the gross "
    "prior-year movement over underwriting years u <= t-2 of Equation (1), for every record of the corpus whose "
    "stored gross RAG triangle a sign-only precedence rule displaced (the provisions sign-disagreement override, route "
    "rag_provisions, or the model-agreement veto, a '[RAG|CODE] PYD NOT APPLIED' note). Built by "
    "src/build_mature_cohort_figures.py, which recomputes each figure from the record's stored grid by the extraction's "
    "own estimator at the pinned commit and assembles the evidence from "
    "results/extraction_error_rate/mature-cohort/ and the error-rate "
    "study. figure_m is in millions of the report's own currency (figure_gbp_m at the loader's H.10 rate, for "
    "reference). Under ANALYSIS_CONFIG['outcome'] 'mature_cohort' (the primary) run_analysis.py "
    "(apply_mature_cohort_figure) adopts figure_m before the basis and cohort decisions and before the FX conversion, "
    "writes route 'mature_cohort_triangle' (gross, mature-enforced), and refuses an entry unless every model block of "
    "the record shows the displaced gross triangle; under 'precedence_672' the register is not applied. An entry with "
    "a figure carries at least two independent agent readings of the filing, each with its reader, pages and cells: "
    "the readings of 22 October 2026 and the second readings of the records that round read once (kind 'reading'), "
    "and earlier readings of the error-rate study that recomputed the same printed triangle (kind "
    "'error_rate_study'). The extraction's own table read of the printed page (the stored grid the estimator computed "
    "from) is kept under table_read as supporting evidence; it is not a reading. notes records a flag a reader raised "
    "and the existing rule that decides it. An entry without a figure "
    "states its reason (confirmed_figure_register, no_mature_cohort, triangle_figure_stands, "
    "outside_working_sample_not_read, aggregated_column_not_like_for_like), and the loader adopts nothing for it. "
    "status 'excluded_takeon_not_development' marks a figure whose record data/takeon_not_development.json excludes "
    "(an entry there with figure_route 'mature_cohort_triangle'). An entry with an aggregated_column object (the three "
    "records of syndicate 1945: 2023 and 2024 on the author's decision of 22 October 2026, 2022 on the decision of the "
    "Claude analysis session of 23 October 2026) leaves the stored grid's aggregated "
    "development-age column out of the figure (Appendix 2.1): its figure is the estimator's on the grid without the "
    "column and its column readers' (F1 and F2 for 2023 and 2024, archived in fx-translation/readings/; X4, Y5, Z1 "
    "and Z2 for 2022, archived in round2/readings/), figure_with_column_m is the grid's "
    "own, and the earlier readings of that figure are kept under superseded_readings. Its displaced.by is a "
    "precedence rule where one displaced the triangle (1945/2024), and 'aggregated_column' where the adopted figure "
    "is the triangle's own with the column in it (1945/2022 and 1945/2023). An entry with a correction object (rules 3 "
    "and 4 of the round-5 decision rules of 23 October 2026: 318/2024, 1274/2016, 1609/2024, 2232/2020 and 4242/2022) "
    "replaces the printed table's own figure, the adopted one, with the corrected figure its readings give (archived "
    "in round5/readings/); its displaced.by is 'printed_table_error' (a body transposed against its labels, a "
    "misprinted cell) or 'previous_report_base' (the year t-1 report's printed cells as the base: 2232/2020 and "
    "4242/2022). 1274/2016's corrected figure is DERIVED (correction.derived_figure_m, decision of the Claude analysis "
    "session of 23 October 2026 after review 8), not given by either reader: each reading keeps its own figure_m and "
    "carries derived_figure_m and the cells it quotes (cells_quoted), and the entry is allowed only while both readers "
    "quote every cell in correction.cells_used and the derivation is recorded (independent_reading_gaps).")


def dumps(reg):
    return json.dumps(reg, indent=1, ensure_ascii=False) + "\n"


def main(argv):
    reg = build()
    text = dumps(reg)
    if "--write" in argv:
        with io.open(REGISTER, "w", encoding="utf-8", newline="") as fh:
            fh.write(text)
        print("wrote %s: %d entries" % (REGISTER.relative_to(HERE), len(reg) - 1))
        return 0
    with io.open(REGISTER, encoding="utf-8", newline="") as fh:
        committed = fh.read()
    if committed != text:
        print("data/mature_cohort_figures.json differs from its rebuild: run with --write and read the diff")
        return 1
    print("data/mature_cohort_figures.json equals its rebuild (%d entries)" % (len(reg) - 1))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
