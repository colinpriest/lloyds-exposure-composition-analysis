r"""Build data/restated_base_excluded.json: the records whose development table restates its history (round 5 of the
filing readings, decision rules of 23 October 2026).

A screen of the primary sample's 649 records at 35a259c (results/extraction_error_rate/mature-cohort/round5/screen/
rebase_screen.py) set each year t table's end-(t-1) cells against the year t-1 report's latest cells and flagged the
records whose history moved by more than an exchange rate explains. The 82 records it asked to read were read twice,
independently (arms P1-P8 and Q1-Q8, brief round5/briefs/brief_r5.md), 2689/2023 by V1 and V2 (brief_2689.md; W1 and
W2 recomputed its figure), and the two records whose readings disagreed on the facts by two tie-break readers (Z5, Z6,
brief_r6.md). The readings are archived verbatim under round5/readings/. The decision rules (round5/rules.md, a decision
of the Claude analysis session written before the adjudication) were applied record by record; the adjudication is in
round5/adjudication.md, and OUTCOMES below records the rule and outcome of each of the 83 records.

The register holds three buckets, each entry with its readings (copied from the archive, with the year t filing's pages),
its pages and quote, the facts the rule rests on and the decision:

  * "excluded": rule 1. The year t table's history differs from the year t-1 report beyond the exchange rate with no
    explanation in either filing, the table fails the year's accounts by more than 10% beyond what its basis explains
    while the year t-1 control ties, and the year t-1 printed base gives no figure that reconciles either. The loader
    (run_analysis.py) removes the record from the primary at the unusable-severity step with the tag
    RESTATED_BASE_TABLE; under outcome 'precedence_672' the register is not read.
  * "history_restated": rule 6. The table ties to the year's accounts (or its basis explains the gap), but an
    underwriting year u <= t-2 moved beyond the exchange rate without explanation by more than 1% of R, or the readings
    disagree on the validity label but not on the facts, or (clause take_on_base_bounded, rule 5b) the filing prints no
    transferred gross amount for a take-on in year t but bounds it at or below 10% of R, or (clause
    take_on_table_unreconciled) an explained take-on that is already in R has a table that does not reconcile with the
    filing's own roll-forward. The record stays; the least-certain sensitivity (src/check_low_confidence_sensitivity.py)
    reads this bucket and leaves the records out.
  * "takeon_unmeasurable": rule 5b. The year's take-on (an RITC, LPT or merger effective in year t whose acquired history
    the table shows 'as if always') is not in R, the filing prints no transferred gross amount, and the readings show the
    acquired share of the base could exceed 10% of R: the movement is development on a combined book whose base cannot
    be measured. The loader removes the record from the primary at the unusable-severity step with the tag
    TAKEON_BASE_UNMEASURABLE (data/takeon_not_development.json, which describes the step of the mature-cohort figure and
    applies to a block carrying a displaced figure, does not fit: the figure here is the extraction's own and the base,
    not the step, is what is missing); under outcome 'precedence_672' the register is not read.

The other rules are applied through the registers that already carry them: rule 2 (the author's rule B) through
data/fx_untranslated_excluded.json (3000/2022), rules 3 and 4 through data/mature_cohort_figures.json (2232/2020,
318/2024, 1274/2016, 1609/2024), and rule 5 through data/opening_reserves_takeon_base.json (every candidate whose take-on
the readings print is already there).

Usage:
  python src/build_restated_base_excluded.py            # check the register against a rebuild; exit 1 on a difference
  python src/build_restated_base_excluded.py --write    # rebuild and write it
"""
import io
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
REGISTER = HERE / "data" / "restated_base_excluded.json"
ROUND5 = HERE / "results" / "extraction_error_rate" / "mature-cohort" / "round5"
READINGS = ROUND5 / "readings"
#: the readers of round 5 (arms P and Q), the 2689/2023 readers (V1, V2 read the table's validity; W1, W2 recomputed its
#: figure) and the round-6 tie-break readers
READERS = (tuple("%s%d" % (a, i) for a in "PQ" for i in range(1, 9)) + ("V1", "V2", "W1", "W2", "Z5", "Z6")
           + ("U1", "U2"))
#: readers whose readings recompute a figure only (kept with the entry as supporting readings, not as its readings)
SUPPORTING = ("W1", "W2")
#: the round-7 readers (brief_r7.md): they read the transferred gross amount of the two take-ons whose amount the round-5
#: readings did not print (1110/2022, 1458/2024); their readings carry no validity verdict and are kept with the entry
#: as its take-on readings (rule 5b)
AMOUNT_READERS = ("U1", "U2")
#: rule 5b's threshold: the acquired share of the base, in per cent of the opening gross claims outstanding R
TAKEON_THRESHOLD_PCT = 10.0
VALID = ("valid", "screen_misread", "units_slip")
INVALID = ("restated_base", "undeterminable")
SESSION = "decision of the Claude analysis session, 23 October 2026"

RULE = (
    "Round 5 of the filing readings (decision rules of 23 October 2026, a decision of the Claude analysis session, "
    "results/extraction_error_rate/mature-cohort/round5/rules.md). 'excluded' (rule 1): a record leaves the PRIMARY "
    "sample (outcome 'mature_cohort') when its year t development table's history (an underwriting year u <= t-2, or "
    "the table as a whole) differs from the year t-1 report beyond the exchange rate with no explanation in either "
    "filing; AND the year t table fails the year's accounts (implied gross incurred, or paid where computable, off by "
    "more than 10% beyond what its basis explains) while the year t-1 control ties within 5%; AND the year t-1 report's "
    "printed base does not give a figure that reconciles either. The loader (run_analysis.py) removes an 'excluded' "
    "entry's record at the unusable-severity step with the tag RESTATED_BASE_TABLE and counts it "
    "(restated_base_excluded); under outcome 'precedence_672' the register is not read and nothing changes. "
    "'history_restated' (rule 6): the table ties to the year's accounts (or its basis explains the gap), but an "
    "underwriting year u <= t-2 moved beyond the exchange rate without explanation by more than 1% of R "
    "(unexplained_history_move), or the two readings disagree on the validity label (valid, screen_misread, units_slip "
    "against restated_base, undeterminable) but not on the facts (label_disagreement), or (rule 5b) the filing prints no "
    "transferred gross amount for a take-on in year t but bounds it at or below 10% of R (take_on_base_bounded), or "
    "an explained take-on already in R has a table that does not reconcile with the filing's own roll-forward "
    "(take_on_table_unreconciled); the record stays in the primary "
    "and src/check_low_confidence_sensitivity.py leaves it out of its least-certain refit. 'takeon_unmeasurable' (rule 5b, "
    "decision of the Claude analysis session, 23 October 2026): a record leaves the PRIMARY sample when an RITC, LPT or "
    "merger effective in year t, whose acquired history the table shows as if always, is not in the opening gross claims "
    "outstanding R, the filing does not print the transferred gross reserves, and the readings show the acquired share "
    "of the base could exceed 10% of R (an unmeasurable take-on, as 1861/2020 and 1084/2022 are); the loader removes the "
    "entry's record at the unusable-severity step with the tag TAKEON_BASE_UNMEASURABLE and counts it "
    "(takeon_base_unmeasurable_excluded); under outcome 'precedence_672' nothing changes. A take-on the filing bounds "
    "at or below 10% of R stays and is listed under history_restated. Every entry rests on two "
    "independent readings of the filing (and the tie-break readings where the first two disagreed on the facts), with "
    "the pages and quotes. Built by src/build_restated_base_excluded.py from the archived readings.")

POPULATION = {
    "screen": ("results/extraction_error_rate/mature-cohort/round5/screen/rebase_screen.json (rebase_screen.py, "
               "report rebase_report.md), over the primary sample's 649 records at 35a259c"),
    "records": 649,
    "screen_verdicts": {"clean": 423, "no_gross_grid_prev": 92, "rebase": 41, "units_case": 40,
                        "rebase_oldest_column_only": 13, "no_common_single_year": 12, "no_prev_record": 8,
                        "rebase_year_t1_only": 7, "alignment_uncertain": 6, "no_identity_evidence": 4,
                        "cell_scale_slip": 2, "no_gross_grid_year_t": 1},
    "read": ("the 82 records of the screen's reading groups A, A2, A3, B, C and D (rebase_screen.json reading_needed, "
             "alignment_uncertain, no_identity_evidence), each read once in arm P and once in arm Q (round5/batches/), "
             "and 2689/2023 (the reference case) read by V1 and V2 and recomputed by W1 and W2: 83 records"),
    "tie_break": "1609/2024 and 4444/2017, whose first two readings disagreed on the facts, read by Z5 and Z6 (brief_r6.md)",
    "take_on_amount": ("1110/2022 and 1458/2024, whose take-on the round-5 readings did not give an amount for, read by U1 "
                       "and U2 (brief_r7.md); neither filing prints the transferred gross amount (rule 5b)"),
    "not_read": ("the 2 cell-scale slips (2001/2018, 2121/2019) and the records the screen could not compare (no year "
                 "t-1 gross grid, record or common single year) or found clean"),
}

# ------------------------------------------------------------------------------------------------ the adjudication
#: rule 1 (decision of the Claude analysis session, 23 October 2026): the facts each condition rests on, from both readings
EXCLUDED = {
    "780_2016": {
        "history_differs_unexplained": (
            "every early cell of the 2016 table (p30) is 8-72% below the 2015 print (p28; first-year cells 40-65% lower) "
            "and the '2010 & prior' balance to pay rises from 89.5 to 203.2 while the 2011-2015 rows shrink; the only "
            "wording is the reconversion of non-dollar claims at 31 December 2016 rates (p29) and a restatement of "
            "reinsurance commissions (note 3(j)); no restatement, RITC or change of basis of the table (P6, Q5)"),
        "year_t_fails_accounts": (
            "the reserve identity on the table's own end-2015 diagonal implies 294.7m of 2016 gross paid against 163.9m "
            "in the accounts (+79.8%, P6, p12); the printed reserves and payments of 2011-2014 give a 2016 movement of "
            "-94.5m against +24.9m from the table's cells (Q5). The incurred test (+5.6%) does not discriminate: the "
            "'2010 & prior' years carry no cells (both readings)"),
        "control_ties": (
            "the 2015 table's implied incurred is +9.5% against the 2015 accounts (both readings), the same gap the "
            "'2010 & prior' years outside the cells explain in both years (Q5); the 2015 table is the base the 2015 "
            "balance sheet was struck on (outstanding 348.483 ties). Read by the session as tying once its basis is "
            "allowed for, as the rule allows the year t test; the raw gap exceeds 5%"),
        "previous_base_reconciles": (
            "on the 2015 print's cells the 2011-2014 movement is -94.4m against the filing's all-prior-years gross line "
            "of -15.6m (p26) and the table's +24.9m: neither base reconciles (P6, Q5)"),
    },
    "2689_2023": {
        "history_differs_unexplained": (
            "the 2023 table (p46) restates the 2020 and 2021 history: end-2022 cells 123,040 and 97,435 against 81,688 "
            "and 77,230 printed in 2022 (p46), earlier diagonals too, under the same heading and basis; neither filing "
            "states a restatement, and 2023 has no RITC, transfer or take-on (V1, V2)"),
        "year_t_fails_accounts": (
            "implied 2023 gross paid 133.1m against 36.1m (p20); implied incurred 93.9m on the table's own base "
            "(155.6m on the 2022 base) against 58.2m (p34) (V1, V2)"),
        "control_ties": (
            "the 2022 table's own movement, +55.9m, against 2022 gross incurred of 56.3m (0.7%, V1); outstanding ties "
            "in both years (108,937; 131,452)"),
        "previous_base_reconciles": (
            "on the 2022 printed diagonal the mature movement is about +103.9m, above the year's total gross incurred of "
            "58.2m (V1, V2)"),
    },
    "4242_2022": {
        "history_differs_unexplained": (
            "the 2022 table (p44) lowers the end-2021 cells of 2019 and 2020 (204,999 and 277,405 against 207,954 and "
            "310,094 printed in 2021, p46), -35.9m on the 2017-2021 diagonal of a dollar table that is not "
            "retranslated, and merges the older columns into '2016 & Prior', whose cumulative paid falls 17.7m; the "
            "loss-funds reclassification (p38) gives no amount and neither filing explains the change (P4, Q3)"),
        "year_t_fails_accounts": (
            "implied incurred 115.1m against 78.3m (+47%, p18, p32); cross-table paid -19.6% (P4, Q3)"),
        "control_ties": "the 2021 table: 227.1m against 229.5m (-1.1%, P4, Q3)",
        "previous_base_reconciles": (
            "the readings do not agree that it does: on the 2021 printed cells, excluding the merged column, 79.3m "
            "(+1.2%, Q3); with the merged column as printed, 54.3m (-30.6%, P4). The merged column's 2022 movement "
            "cannot be measured (its paid falls), so the 2021 base reconciles only if the older years did not move, "
            "which neither filing shows; rule 3 needs both readings to give the reconciling figure"),
    },
    "4747_2024": {
        "history_differs_unexplained": (
            "the 2024 table (p48) raises the end-2023 cells of 2022 and 2023 to 24,572 and 34,726 against 17,343 and "
            "7,482 printed in 2023 (p39), lowers the 2020-2021 history by about 6%, and its paid row falls (2020: "
            "4,843 to 213); the only restatement note (p31) concerns the management fee (P2, Q3)"),
        "year_t_fails_accounts": (
            "implied incurred 11.2m against 61.9m (-81.9%, note 6 p35); paid 8.7m against 22.1m (-60.7%, p17) (P2, Q3)"),
        "control_ties": (
            "the 2023 table's implied incurred is 27.9m against 30.1m (-7.2%, both readings) and its outstanding, "
            "38,860, ties exactly to the 2023 balance sheet and the 2024 opening (p35). Read by the session as tying: "
            "the 5% bar is missed by 2.2 points on incurred while outstanding ties, against a year t miss of 82%; the "
            "raw incurred gap exceeds 5%"),
        "previous_base_reconciles": (
            "against the 2023 printed cells the 2024 latest diagonal gives 96,582 - 51,304 = 45.3m against 61.9m (-27%, "
            "from the cells both readings quote) and M -4.3m (P2); the 2024 table's end-2023 diagonal less the 2023 "
            "paid implies a 72.9m end-2023 reserve against 38.9m (P2): no figure reconciles"),
    },
    "6134_2022": {
        "history_differs_unexplained": (
            "the 2022 table (p45) drops the 2018 column the 2021 report printed (p44: estimate 25,190, outstanding "
            "22,458) and folds the 2018 year of account into the 2020 column at end-2022 only ('The 2020 amounts above "
            "include the 2018 year of account', p45), while its end-2021 cell for 2020 (108,774 = 100,104 x 1.087) "
            "does not carry it; the footnote states the fold, not why the history was left unrebuilt; the 2019 "
            "24-month cell departs from the retranslation by 2.95m (P4, Q5)"),
        "year_t_fails_accounts": (
            "implied incurred 73.7m against 64.1m (+14.9%, p19, p33); the payments row (2,869 in all) does not move "
            "with the 22.1m of gross claims paid (P4, Q5)"),
        "control_ties": "the 2021 table: 82.7m against 82.0m (+0.9%, P4, Q5)",
        "previous_base_reconciles": (
            "the 2021 report's cells give no 2022 movement for the 2018 year folded into the 2020 column, whose movement "
            "is in no printed column (Q5); P4's like-for-like -15.8m is an inference, not a printed cell"),
    },
}

#: rule 6 (decision of the Claude analysis session, 23 October 2026): the clauses and the facts, from the readings
HISTORY_RESTATED = {
    "382_2021": (["unexplained_history_move"],
                 "UY2014's end-2020 cell in the 2021 table (187,147) is 10.3m above the 2020 report's printed estimate "
                 "and out of line with its own column (169,537 -> 187,147 -> 170,900), unexplained in the filing (P1, "
                 "Q8): 2.1% of R (498.1m). The rest moves by the stated retranslation; the table ties to the balance "
                 "sheet and its incurred gap (-8.7%) is the 2020 control's (-6.9%), the pre-2011 years outside the "
                 "table. M as printed (+20.409m) stands"),
    "382_2022": (["unexplained_history_move", "label_disagreement"],
                 "the 2018 column's end-2021 cell moved against the common 1.09 retranslation (ratio 0.959; 34.2m, 6.9% "
                 "of R 498.1m), unexplained (p44 states only the all-years retranslation at 2022 closing rates; P4, "
                 "Q5). The table ties: implied incurred 236.1m against 231.25m (+2.1%, p16) and outstanding 631,136 to "
                 "the balance sheet. P4 valid, Q5 restated_base on the same cells"),
    "382_2023": (["unexplained_history_move"],
                 "the end-2022 cells of 2016, 2019 and 2020 sit 2.8%, 2.8% and 7.1% above the 2022 report's latest in a "
                 "year sterling strengthened, against 0.95-0.99 for the other years (10.9m, 8.8m and 13.1m beyond the "
                 "common factor; 1.4-2.1% of R 631.1m), and the early rows were rebuilt beyond the stated "
                 "retranslation (P8: 2016 first year 88,722 against 72,750); p44 states only the closing-rate "
                 "retranslation (P8, Q1; Q1 attributes the moves to it). Incurred -8.1% with UY <= 2012 outside the "
                 "table (control +2.1%); outstanding ties"),
    "780_2017": (["unexplained_history_move", "label_disagreement"],
                 "the 2017 table's end-2016 estimates are 165.6m (24.6%) above the 2016 report's, mirrored by a "
                 "-170.4m fall in the '2010 & prior' balance to pay, with only the generic reconversion sentence (p30) "
                 "(P5, Q6); 2011, 2012 and 2015 move 59.2m, 17.8m and 16.1m beyond the common factor (5-19% of R "
                 "313.8m). Implied incurred 279.0m against 257.3m (+8.4%, control +5.6%) and cross-report paid +5.8%: "
                 "within rule 1's 10%, so rule 1 does not apply. P5 restated_base, Q6 valid"),
    "1176_2019": (["unexplained_history_move"],
                  "the 2011 column's end-2018 cell is 17,001 against 14,924 in the 2018 report, 2.1m (5.2% of R "
                  "39.7m), unexplained (P2, Q1). Paid ties (2,904 against 2,915) and reserves tie"),
    "1686_2022": (["unexplained_history_move", "label_disagreement"],
                  "the 2016-2018 history is cut by 175.0m in both incurred and paid (reserve-neutral) with 2019-2021 "
                  "untouched, unexplained (p32 states only balance-sheet-rate translation; P6, Q7): 8.1% of R "
                  "(2,167.2m). Implied incurred is 9.5% below the accounts, the gap equal to the stated FX line (72,783, "
                  "note 4 p24) to within 5k (both readings): the basis explains it; control +0.3%. Not a year t "
                  "take-on: the RITC of Syndicates 2007 and 6129 is of 1 January 2021 and in R, the 1 December 2022 LPR "
                  "is ceded. P6 valid, Q7 restated_base"),
    "1729_2023": (["unexplained_history_move"],
                  "UY2021's end-2022 estimate is 58.3m USD above the 2022 report's at the common presentation factor "
                  "(17.1% of R), unexplained in the filing (P7, Q6; Q6 judges the 2022 print faulty, which the filing "
                  "does not say). The 2023 table ties (incurred -0.4%)"),
    "1910_2018": (["unexplained_history_move"],
                  "the 2016 column was lowered (end-2017 73.0 against 76.5, ratio 0.954) while the other years rose "
                  "2.5-5.6% by the stated retranslation, unexplained (Q7: 'not explained anywhere'; P8): 6.8m, 2.1% of "
                  "R (322.1m). The table ties to the provision; incurred +5.3% on an ultimate basis (control -3.8%)"),
    "1947_2022": (["unexplained_history_move"],
                  "the 2018 column (oldest) is about 14% above the year's retranslation ratio at every age (about 4.3m, "
                  "3.7% of R 116.5m), unexplained (P2, Q3). Incurred ties (-0.5%, control +0.8%)"),
    "1967_2017": (["unexplained_history_move"],
                  "the whole 2011-2016 history, estimates and payments alike, is 6-16% above the 2016 report with no "
                  "retranslation or restatement statement (P5, Q6); 2015 moves 5.7m beyond the common factor (3.5% of R "
                  "165.2m). The table ties (+4.0% incurred, reserves exact)"),
    "1458_2024": (["take_on_base_bounded"],
                  "rule 5b (U1, U2). An external RITC 'in the year' of reserves relating only to the 2020 and 2021 "
                  "underwriting years (p47); counterparty, date and amount are not printed, and note 4's gross roll-forward "
                  "(p31) has no transfer row (2,050,580 + 733,886 - 79,491 - 544,404 - 10,867 = 2,149,704, USD 000). The "
                  "only ADC is outward, bought in 2020 (p49), so not a take-on. R is the opening USD 2,050.580m (p31), "
                  "which is the analysis's opening (GBP 1,637.71m) and includes no acquired reserves. The filing bounds "
                  "the take-on: the 2024 table's 2020 and 2021 columns exceed the 2023 filing's at every age while the "
                  "control columns move about -1%, and the acquired cumulative incurred at the latest comparable ages is "
                  "105.138m + 58.940m = USD 164.078m (U1, U2); the reserves taken on are that incurred less the acquired "
                  "paid to date, so they cannot exceed it: at most 8.0% of R (U2 puts it at about 2 to 3% on a "
                  "low-confidence indicative range). The table carries the acquired years as if always, so the movement "
                  "within the table (-33.258m USD = -26.56m GBP, u <= 2022, equal to the analysis figure) excludes the "
                  "take-on and only the divisor is short; the acquired years' own pre-acquisition development (-22.091m "
                  "of it) is in the figure. Bounded at or below 10% of R: the record stays and joins the least-certain "
                  "list"),
    "1967_2018": (["unexplained_history_move"],
                  "the 2011 column (oldest) is 26% higher between reports while the others are 3-9% lower "
                  "(retranslation), unexplained (P6, Q7): 28.9m, 11.8% of R (246.1m). Incurred ties (-4.5%, control "
                  "+4.0%)"),
    "2001_2016": (["unexplained_history_move"],
                  "UY2013 and UY2014 fall at end-2015 against an exchange uplift (P6: unexplained, about 2% of the "
                  "year's gross incurred; Q7: the 2013-2015 columns look mis-allocated, the 2017 report re-allocates "
                  "them); the stated basis is year-end conversion (p35). Incurred ties (+3.1%, control +4.8%)"),
    "2001_2017": (["unexplained_history_move"],
                  "the end-2016 history is re-allocated across 2013 (+11.9%), 2014 (+9.7%) and 2015 (-21.1%) beyond the "
                  "stated year-end conversion (p33), with no explanation (P8, Q7). Incurred ties (-4.4%, control "
                  "+3.1%)"),
    "2232_2017": (["label_disagreement"],
                  "the mature years' end-2016 cells equal the 2016 report's latest exactly while their earlier cells "
                  "were retranslated about -7% (P3, Q4); Q4 reads a mixed currency base, P3 a valid table. The flows "
                  "miss (incurred -10.5%, cross-report paid -20.1%) and the control does not tie within 5% (P3 incurred "
                  "+7.4%; Q4 paid +62.1%, confounded), so rule 1 does not apply; no exchange line is reported, so rule 2 "
                  "cannot be tested. P3 valid, Q4 restated_base"),
    "2232_2019": (["unexplained_history_move"],
                  "the 2013 column (oldest) is 6.3% higher between reports with no wording, in tables translated at each "
                  "year's own end rate, so no retranslation moves history (Q6; P5): 4.5m, 1.2% of R (373.2m). The table "
                  "ties (paid -0.8%, incurred -3.3%)"),
    "2468_2019": (["unexplained_history_move"],
                  "the end-2018 estimates and paid of UY2016 and UY2017 are re-allocated (about +17m each, +15.7% and "
                  "+4.6% on the diagonal), unexplained (P5, Q4); 2016 moves 10.4m beyond the common factor (3.1% of R "
                  "337.0m). The table ties (paid -3.0%, incurred -3.0%)"),
    "2468_2020": (["unexplained_history_move"],
                  "UY2016 (oldest, closed) history is 16.5-18.6m lower in estimate and paid alike, unexplained (P1, Q2): "
                  "4.2% of R (389.0m). The table ties (paid -4.3%, incurred -3.8%)"),
    "2488_2016": (["unexplained_history_move", "label_disagreement"],
                  "the 2011 column's end-2015 estimate is 28.9-29.3m above the 2015 report at the stated 1.165 "
                  "retranslation, unexplained (P6, Q5): 3.2% of R (916.3m). The paid bridge ties (-3.3%, -2.9%); "
                  "incurred +59.5% against a +38.3% control, the 2010-and-prior years outside the table. P6 valid, Q5 "
                  "restated_base"),
    "3000_2016": (["label_disagreement"],
                  "P4 valid, Q5 restated_base on the same facts: the 2016 table carries Syndicate 1400's history (RITC "
                  "accepted 1 January 2016, 248.822m gross, p37), stated on p38 and retranslated; rule 5 applies and R "
                  "already carries the take-on (data/opening_reserves_takeon_base.json). Paid -33.4% against a -30.1% "
                  "control, the 'All prior years' column printing no paid: the basis explains it"),
    "3500_2023": (["take_on_table_unreconciled"],
                  "RITCs of seven syndicates and an LPT effective 1 January 2023 (p5, p30-31; note 7 'Reinsurance of new "
                  "liabilities 3,225,818'), the history carried as if always (2 to 3.6 times the 2022 report's). The "
                  "take-on is explained and is in R (5,803.136m USD = 2,962.436 + 2,840.7, "
                  "data/opening_reserves_takeon_base.json), so rule 5 changes nothing. But the table does not reconcile "
                  "with the filing's own roll-forward: its movement on the old years is -52.1m against -184.8m of change "
                  "in estimates in note 7 (P7; Q8: neither 136.6m nor -62.3m ties). Rule 1 does not reach it (the history "
                  "change is explained) and no rule covers an explained take-on table that fails the tie; it stays and "
                  "joins the least-certain list"),
    "4020_2018": (["unexplained_history_move"],
                  "the history is re-spread across underwriting years without explanation (2012 -20.3m, 2013 +36.0m, "
                  "2014 -23.1m between reports, P5; Q6: re-allocations inside a near-constant total), each above 1% of R "
                  "(497.3m). The table ties (+4.0%, control +7.2% on the underwriting-year basis)"),
    "4141_2022": (["unexplained_history_move"],
                  "a 24.7m cross-year move between UY2018 and UY2019 on the end-2021 diagonal, sum-preserving and "
                  "unexplained (P8, Q1): 9.9% of R (248.5m) each. The table ties (-2.9%, control +0.3%)"),
    "4242_2017": (["unexplained_history_move"],
                  "the 2011 column's history is lowered by about 1.4m between reports, unexplained (P8, Q1): 4.3-4.5% "
                  "of R (30.7m). The table ties (-2.0%, control -0.6%)"),
    "4444_2017": (["unexplained_history_move", "label_disagreement"],
                  "the end-2016 cells of 2011, 2012 and 2013 sit 4.7%, 4.7% and 3.9% above the 2016 report (16.1m, "
                  "16.7m, 14.2m; 1.2-1.4% of R 1,200.6m each; +40.7m on the 2011-2016 diagonal) in a year sterling "
                  "strengthened against the dollar, unexplained (Q8, Z5, Z6; p25 states only year-end rates). Rule 1 "
                  "does not apply: on the table's own base implied incurred is +6.3% (control -1.1%), within its 10%, "
                  "and the paid +30.8% is a cross-report proxy because the 2017 table prints no end-2016 payments (Z6). "
                  "P1 valid; Q8 restated_base; the tie-break readers Z5 and Z6 confirm the facts (restated_base, "
                  "moderate confidence). M as printed (+118.224m) stands"),
    "5000_2023": (["unexplained_history_move"],
                  "the 2014 column (oldest) from two years later onward sits about 9.7-9.8m above the translated 2022 "
                  "values, unexplained (P4, Q3): 1.2% of R. The table ties (incurred +3.0%)"),
    "6118_2018": (["unexplained_history_move", "label_disagreement"],
                  "the 2014 column's end-2017 cell is 21,267 against 101,239 in the 2017 report (about 80m, 44% of R "
                  "183.4m), unexplained in either filing (P3 gives the context of the 2014 year's closure into "
                  "Syndicate 1955; Q4: unexplained). Incurred -2.0% raw (P3), +9.5% earned-equivalent (Q4): within "
                  "rule 1's 10%. P3 valid, Q4 restated_base"),
}

#: rule 5b (decision of the Claude analysis session, 23 October 2026): the take-on, its share of R and what the readings
#: give for it. 'indicated' (the share could exceed 10% of R: the record leaves the primary) or 'upper_bound' (the filing
#: bounds it at or below 10% of R: the record stays and is listed). No filing prints the transferred gross amount.
TAKEON_AMOUNT = {
    "1110_2022": {
        "currency": "GBP", "opening_R_m": 221.885, "amount_m": 221.879, "amount_kind": "indicated",
        "basis": ("not printed in either reading: U2 derives the gross claims incurred in 2022 on years before the 2022 "
                  "underwriting year, 353.805m (note 3, p27) less 131.926m (the 2022 year's end-of-year estimate, p37) = "
                  "221.879m, which is the take-on plus calendar-year development on the opening book (the two cannot be "
                  "separated; the take-on is about 221.9m less that development); U1 prints only proxies (gross written "
                  "premium 333.442m, p15; gross claims incurred 353.805m, p27; closing reserves 489.603m against an "
                  "opening of 221.885m)"),
    },
    "1458_2024": {
        "currency": "USD", "opening_R_m": 2050.58, "amount_m": 164.078, "amount_kind": "upper_bound",
        "basis": ("an upper bound, not a printed figure: the acquired cumulative incurred at the latest comparable ages, "
                  "the 2020 column's 36-month cell (708,716 against 603,578 in the 2023 filing, +105.138m) and the 2021 "
                  "column's 24-month cell (778,088 against 719,148, +58.940m), p47 and the 2023 filing p45 (U1, U2); the "
                  "reserves taken on are that incurred less what the acquired books had already paid"),
    },
}

#: rule 5b, a take-on that leaves the primary (decision of the Claude analysis session, 23 October 2026): the facts
TAKEON_UNMEASURABLE = {
    "1110_2022": (
        "rule 5b (U1, U2; P7, Q6 for the table). The Syndicate 5678 RITC (all open years of account, the 2018 and 2019 "
        "underwriting years named; agreement of 9 February 2022, p5, p33) and an INWARD adverse development cover for "
        "certain years of Syndicates 33 and 3624 (the Hiscox ADC, p5): 1110 is the reinsurer, so both add gross reserves; "
        "the Gibson Re 80% whole account quota share is outward and moves the reinsurers' share, not the gross reserves. "
        "The filing prints no transferred gross amount: note 3's gross roll-forward (p27) has no transfer row (221,885 + "
        "claims incurred 353,805 - paid 99,706 + foreign exchange 13,619 = 489,603, GBP 000), so the take-on sits inside "
        "claims incurred, and gross written premium rose from 1.366m to 333.442m, mainly on the two deals (p6, p15). R is "
        "the opening 221.885m alone (p27, p18): the analysis's opening equals it exactly and includes no acquired "
        "reserves. U2 derives a take-on of about 221.9m less the unknown development on the opening book, about 100% of R "
        "and about twice the base; closing reserves are 2.2 times the opening. The development table carries the acquired "
        "2018 and 2019 years with their full history as if always (p37) and restates the older columns against the 2021 "
        "filing (U2), so the movement the table gives (+9.082m) is development on a combined book of about twice R. The "
        "acquired share of the base could exceed 10% of R by a wide margin and cannot be measured from the filing: the "
        "record leaves the primary"),
}

#: every record of the round with its rule and outcome (the adjudication: round5/adjudication.md)
_STANDS = "7", "stands"
OUTCOMES = {
    **{k: ("1", "excluded", "data/restated_base_excluded.json (excluded)") for k in EXCLUDED},
    **{k: ("6", "least_certain", "data/restated_base_excluded.json (history_restated)") for k in HISTORY_RESTATED},
    "3000_2022": ("2", "excluded", "data/fx_untranslated_excluded.json (excluded)"),
    "2232_2020": ("3", "corrected", "data/mature_cohort_figures.json (previous_report_base)"),
    "318_2024": ("4", "corrected", "data/mature_cohort_figures.json (printed_table_error)"),
    "1274_2016": ("4", "corrected", "data/mature_cohort_figures.json (printed_table_error)"),
    "1609_2024": ("4", "corrected", "data/mature_cohort_figures.json (printed_table_error)"),
    **{k: ("5", "take_on_base", "data/opening_reserves_takeon_base.json (already in R)")
       for k in ("1686_2021", "1856_2024", "1884_2021", "2488_2019", "3500_2022", "4000_2022", "4444_2018",
                 "4444_2023")},
    # rule 5b (after the round-7 readings U1, U2): neither filing prints the transferred gross amount
    "1110_2022": ("5b", "take_on_unmeasurable", "data/restated_base_excluded.json (takeon_unmeasurable)"),
    "1458_2024": ("5b and 6", "take_on_bounded_least_certain",
                  "data/restated_base_excluded.json (history_restated, take_on_base_bounded)"),
    **{k: _STANDS + ("none",) for k in (
        "382_2017", "382_2020", "435_2016", "510_2015", "1084_2016", "1218_2016", "1274_2022", "1274_2024",
        "1301_2016", "1416_2024", "1492_2019", "1856_2021", "1880_2015", "1897_2019", "1910_2016", "1945_2016",
        "1945_2018", "1947_2020", "1955_2023", "1967_2022", "2007_2016", "2015_2022", "2121_2018", "2357_2024",
        "2623_2023", "2786_2024", "2791_2022", "2988_2020", "3000_2018", "3624_2018", "4444_2022", "4472_2022",
        "4472_2024", "5000_2018", "5151_2020", "5678_2016", "6107_2023")},
}
#: a record two rules decide (rule 5 applied already, and rule 6 lists it: 3000/2016 for its label disagreement, 3500/2023
#: because its explained take-on's table does not reconcile with note 7)
OUTCOMES["3000_2016"] = ("5 and 6", "take_on_base_and_least_certain",
                         "data/opening_reserves_takeon_base.json (already in R) and data/restated_base_excluded.json "
                         "(history_restated)")
OUTCOMES["3500_2023"] = OUTCOMES["3000_2016"]
ROUND_RECORDS = 83


# ------------------------------------------------------------------------------------------------ the readings
def order_key(k):
    return tuple(int(p) for p in k.split("_"))


def load_readings():
    """{key: [(reader, entry)]} from the archived readings of round 5 and round 6 (keys may carry a '|<task>' suffix)."""
    out = {}
    for rid in READERS:
        with io.open(READINGS / ("%s.json" % rid), encoding="utf-8") as fh:
            for k, e in json.load(fh).items():
                out.setdefault(k.split("|")[0], []).append((rid, e))
    return out


_YEAR = re.compile(r"(?<!\d)(19|20)\d{2}(?!\d)")
_PAGE = re.compile(r"\bp\.?\s?(\d+)")
_EARLIER = ("prev", "minus", "control", "older", "plus", "printed")


def _ints(v):
    if isinstance(v, bool):
        return []
    if isinstance(v, int):
        return [v] if v >= 1 else []
    if isinstance(v, list):
        return [p for x in v for p in _ints(x)]
    if isinstance(v, str):
        return [int(p) for p in _PAGE.findall(v)]
    return []


def split_pages(key, pages):
    """(year t filing's pages, {other name: pages}) from a reader's `pages`, which the readers write as a list (the year
    t filing's) or as a dict keyed by filing, by role ('t', 't_table', 'accounts_t', 'prev', 't_minus_1', ...) or by
    report year. A name that marks an earlier or later report, or a printed page number, is not the year t filing's; a
    string value that names another year than t is the other report's."""
    year = key.split("_")[1]
    if isinstance(pages, list):
        return sorted(set(_ints(pages))), {}
    own, other = set(), {}
    for name, val in (pages or {}).items():
        low = name.lower()
        years = set(m.group(0) for m in _YEAR.finditer(low))
        if any(w in low for w in _EARLIER) or (years and year not in years):
            if "printed" not in low and _ints(val):
                other[name] = sorted(set(_ints(val)))
            continue
        vals = val if isinstance(val, list) else [val]
        for v in vals:
            vy = set(m.group(0) for m in _YEAR.finditer(v)) if isinstance(v, str) else set()
            if vy and year not in vy:
                other.setdefault(name, []).extend(_ints(v))
            else:
                own.update(_ints(v))
    return sorted(own), {k: sorted(set(v)) for k, v in other.items() if v}


def reading(rid, key, e):
    """One reading as the register keeps it: the archived entry verbatim, with the reader, its source and the year t
    filing's pages (the reader's own pages kept as pages_as_read)."""
    own, other = split_pages(key, e.get("pages"))
    out = {"reader": rid, "source": "results/extraction_error_rate/mature-cohort/round5/readings/%s.json" % rid,
           "pages": own, "pages_of_other_reports": other, "pages_as_read": e.get("pages")}
    out.update({k: v for k, v in e.items() if k not in ("key", "pages")})
    return out


def _quote_of(r):
    for f in ("explanation", "explanation_search", "note"):
        v = r.get(f)
        if v:
            return v if isinstance(v, str) else json.dumps(v, ensure_ascii=False)
    return ""


def take_on_block(key, reads, bucket):
    """The rule-5b take-on of an entry: the amount and its share of R (TAKEON_AMOUNT), and the round-7 readings of the
    transferred gross amount (U1, U2, kept verbatim), none of which prints a figure."""
    amount = TAKEON_AMOUNT[key]
    us = [(rid, e) for rid, e in reads if rid in AMOUNT_READERS]
    if sorted(rid for rid, _ in us) != sorted(AMOUNT_READERS):
        raise SystemExit("%s: rule 5b needs the readings of both %s (%s)" % (key, "/".join(AMOUNT_READERS),
                                                                             [rid for rid, _ in us]))
    t = dict(amount)
    t["pct_of_R"] = round(100.0 * amount["amount_m"] / amount["opening_R_m"], 1)
    t["amount_printed"] = False
    t["threshold_pct_of_R"] = TAKEON_THRESHOLD_PCT
    t["readings"] = [reading(rid, key, x) for rid, x in sorted(us)]
    for r in t["readings"]:
        if not r["pages"]:
            raise SystemExit("%s: reader %s's pages %r give no page of the year t filing" % (key, r["reader"],
                                                                                          r["pages_as_read"]))
        if (r.get("gross_transferred_in") or {}).get("value_m") is not None:
            raise SystemExit("%s: reader %s prints a transferred gross amount; rule 5b concerns an unprinted one"
                             % (key, r["reader"]))
    if bucket == "takeon_unmeasurable" and t["pct_of_R"] <= TAKEON_THRESHOLD_PCT:
        raise SystemExit("%s: a take-on of %.1f%% of R is not above the %g%% of rule 5b" % (key, t["pct_of_R"],
                                                                                           TAKEON_THRESHOLD_PCT))
    if bucket != "takeon_unmeasurable" and t["pct_of_R"] > TAKEON_THRESHOLD_PCT:
        raise SystemExit("%s: a take-on bounded at %.1f%% of R is above the %g%% of rule 5b" % (key, t["pct_of_R"],
                                                                                              TAKEON_THRESHOLD_PCT))
    return t


def entry_for(key, reads, bucket):
    main = [(rid, e) for rid, e in reads if rid not in SUPPORTING + AMOUNT_READERS]
    supp = [(rid, e) for rid, e in reads if rid in SUPPORTING]
    rr = [reading(rid, key, e) for rid, e in sorted(main, key=lambda p: (p[0][0] not in "PV", p[0]))]
    for r in rr:
        if not r["pages"]:
            raise SystemExit("%s: reader %s's pages %r give no page of the year t filing" % (key, r["reader"],
                                                                                          r["pages_as_read"]))
    verdicts = [r.get("verdict") for r in rr]
    if any(v not in VALID + INVALID for v in verdicts):
        raise SystemExit("%s: a verdict outside the round's (%s)" % (key, verdicts))
    e = {"pages": sorted({p for r in rr for p in r["pages"]}),
         "quote": " || ".join("reader %s: %s" % (r["reader"], _quote_of(r)[:600]) for r in rr),
         "verdicts": {r["reader"]: r.get("verdict") for r in rr}}
    if bucket == "excluded":
        if any(v != "restated_base" for v in verdicts):
            raise SystemExit("%s: rule 1 needs both readings to find a restated base (%s)" % (key, verdicts))
        e["conditions"] = {name: {"holds": want, "facts": EXCLUDED[key][name]}
                           for name, want in (("history_differs_unexplained", True), ("year_t_fails_accounts", True),
                                              ("control_ties", True), ("previous_base_reconciles", False))}
        e["decision"] = ("%s: rule 1 of the round-5 decision rules; the year t table restates its history without "
                         "explanation, fails the year's accounts while the year t-1 control ties, and the year t-1 "
                         "printed base gives no figure that reconciles, so the table cannot give the year's movement "
                         "and the record leaves the primary sample; the 672 sensitivity keeps it" % SESSION)
    elif bucket == "takeon_unmeasurable":
        e["facts"] = TAKEON_UNMEASURABLE[key]
        e["take_on"] = take_on_block(key, reads, bucket)
        e["decision"] = ("%s: rule 5b of the round-5 decision rules; the year's take-on is not in R, the filing prints no "
                         "transferred gross amount, and the readings show the acquired share of the base could exceed "
                         "%g%% of R (indicated %.1f%%), so the movement is development on a combined book whose base "
                         "cannot be measured and the record leaves the primary sample as an unmeasurable take-on; the "
                         "672 sensitivity keeps it"
                         % (SESSION, TAKEON_THRESHOLD_PCT, e["take_on"]["pct_of_R"]))
    else:
        clauses, facts = HISTORY_RESTATED[key]
        label = bool(set(verdicts) & set(VALID)) and bool(set(verdicts) & set(INVALID))
        if label != ("label_disagreement" in clauses):
            raise SystemExit("%s: the clause label_disagreement (%s) against the verdicts %s" % (key, clauses, verdicts))
        e["clauses"] = list(clauses)
        e["facts"] = facts
        rule = "rule 6"
        if "take_on_base_bounded" in clauses:
            e["take_on"] = take_on_block(key, reads, bucket)
            rule = "rule 5b"
        elif "take_on_table_unreconciled" in clauses:
            rule = "rules 5 and 6"
        e["decision"] = ("%s: %s of the round-5 decision rules (%s); the record stays in the primary sample with its "
                         "figure and joins the least-certain sensitivity (src/check_low_confidence_sensitivity.py)"
                         % (SESSION, rule, ", ".join(clauses)))
    e["readings"] = rr
    if supp:
        e["supporting_readings"] = [reading(rid, key, x) for rid, x in supp]
    return e


def build():
    reads = load_readings()
    keys = sorted(set(OUTCOMES), key=order_key)
    if len(keys) != ROUND_RECORDS:
        raise SystemExit("OUTCOMES holds %d records, not the round's %d" % (len(keys), ROUND_RECORDS))
    read = {k for k, rs in reads.items() if any(rid[0] in "PQV" for rid, _ in rs)}
    if set(keys) != read:
        raise SystemExit("the records decided %s are not the records read %s" % (sorted(set(keys) - read),
                                                                                sorted(read - set(keys))))
    if len(set(EXCLUDED) | set(HISTORY_RESTATED) | set(TAKEON_UNMEASURABLE)) != (
            len(EXCLUDED) + len(HISTORY_RESTATED) + len(TAKEON_UNMEASURABLE)):
        raise SystemExit("a record in two buckets")
    pop = dict(POPULATION)
    counts = {}
    for k in keys:
        counts[OUTCOMES[k][1]] = counts.get(OUTCOMES[k][1], 0) + 1
    pop["outcomes"] = dict(sorted(counts.items()))
    reg = {"_rule": RULE, "_population": pop,
           "_adjudicated": {k: {"rule": OUTCOMES[k][0], "outcome": OUTCOMES[k][1], "where": OUTCOMES[k][2],
                                "readers": [rid for rid, _ in reads[k]]} for k in keys},
           "excluded": {}, "history_restated": {}, "takeon_unmeasurable": {}}
    for bucket, src in (("excluded", EXCLUDED), ("history_restated", HISTORY_RESTATED),
                        ("takeon_unmeasurable", TAKEON_UNMEASURABLE)):
        for k in sorted(src, key=order_key):
            reg[bucket][k] = entry_for(k, reads[k], bucket)
    return reg


def dumps(reg):
    return json.dumps(reg, indent=1, ensure_ascii=False) + "\n"


def main(argv):
    text = dumps(build())
    if "--write" in argv:
        with io.open(REGISTER, "w", encoding="utf-8", newline="") as fh:
            fh.write(text)
        print("wrote data/restated_base_excluded.json")
        return 0
    committed = None
    if REGISTER.exists():
        with io.open(REGISTER, encoding="utf-8", newline="") as fh:
            committed = fh.read()
    if committed != text:
        print("data/restated_base_excluded.json differs from its rebuild: run with --write and read the diff")
        return 1
    print("data/restated_base_excluded.json equals its rebuild")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
