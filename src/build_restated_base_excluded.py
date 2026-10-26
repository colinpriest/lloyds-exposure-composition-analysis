r"""Build data/restated_base_excluded.json: the records whose development table restates its history (round 5 of the
filing readings, decision rules of 23 October 2026).

A screen of the primary sample's 649 records at 35a259c (results/extraction_error_rate/mature-cohort/round5/screen/
rebase_screen.py) set each year t table's end-(t-1) cells against the year t-1 report's latest cells and flagged the
records whose history moved by more than an exchange rate explains. The 82 records it asked to read were read twice,
independently (arms P1-P8 and Q1-Q8, brief round5/briefs/brief_r5.md), 2689/2023 by V1 and V2 (brief_2689.md; W1 and
W2 recomputed its figure), and the two records whose readings disagreed on the facts by two tie-break readers (Z5, Z6,
brief_r6.md). The readings are archived verbatim under round5/readings/. The decision rules (round5/rules.md, a decision
of the Claude analysis session) were applied record by record; the adjudication is in round5/adjudication.md, and
OUTCOMES below records the rule and outcome of each of the 83 records.

Rules 1 to 7 were written before the adjudication. Four things were added after particular readings or a review, each
named in rules.md: rule 5b (23 October, after the round-7 readings U1 and U2 of 1110/2022 and 1458/2024); rule 6's
take-on clause, take_on_table_unreconciled (23 October, after the readings of 3500/2023, and applied to 3500/2022 after
review 8); rule 1's exact control clause (23 October, after review 8: the year t-1 control ties within 5%, or within
10% when the same basis gap explains both years and the year t miss is at least three times the control's); and rule 4b
(24 October, after the round-8 readings Z7 and Z8, round8/). On 23 October the exact control clause moved no record
(4242/2022 moved from rule 1 to rule 3 on review 8's decision to set aside its merged '2016 & Prior' column; its control
ties at -1.1% under either reading); applied to the round-8 readings it takes 780/2016 and 4747/2024 out of rule 1
(4747/2024: control -7.2%, no shared basis gap; 780/2016: control +9.4%, year t miss +5.6%, 0.6 times it on the
percentages, Z7, and 0.81 on the absolute misses, Z8). Incurred first (24 October, after the review of the fixes): rule
1's accounts test and rule 4b's (ii) use the implied gross incurred test wherever the table gives one; the paid test
decides only where the table gives none, because M is an incurred movement and a paid cell M does not use cannot make M
unmeasured. 780/2016 returns to the primary under rule 6 (+24.9m USD as printed); 4747/2024 stays out under rule 4b, a table
its own cells prove inconsistent (its cumulative paid falls between reports). Rule 4b was applied to the readings of
every record of rounds 5 to 8 (round8/rule_4b_scan.json): it also takes 2232/2017 out of the primary, which rule 6
listed until then. Review 8 also added the rule-6 clause derived_correction (1274/2016, whose corrected figure is the
session's derivation from cells both readers quote).

Rule 8, the source-history rule (26 October 2026; the recommendation of the Codex analysis, adopted on Colin's instruction
and applied by the Claude analysis session; found in Codex's tail investigation of 6131/2021, post hoc), was applied to the
census population chosen by source features (round9/population.md; 81 core and 20 host-side records, each read twice by arms
K and L, with third readings where the facts conflicted: Z9-Z13). It sets 11 records aside (the fourth bucket), moves
3000/2016, 3500/2022 and 3500/2023 off the rule-6 list, lists 1110/2020, 1254/2023, 1686/2021, 3330/2017 and 1609/2024 under
rule 6 and keeps 6118/2018 listed (round9/adjudication.md).

The register holds four buckets, each entry with its readings (copied from the archive, with the year t filing's pages),
its pages and quote, the facts the rule rests on and the decision:

  * "excluded": rule 1 or rule 4b, each entry naming its rule. Rule 1: the year t table's history differs from the
    year t-1 report beyond the exchange rate with no explanation in either filing, the table fails the year's accounts
    by more than 10% beyond what its basis explains (implied gross incurred first; paid only where the table gives no
    implied incurred) while the year t-1 control ties (within 5%, or within 10% when the
    same basis gap explains both years and the year t miss is at least three times the control's), and the year t-1
    printed base gives no figure that reconciles either. Rule 4b: the control does not tie, but both readings report
    that the year t table prints, for a year u <= t-2, cumulative paid lower than the year t-1 report printed, beyond
    the exchange rate and unexplained; the table fails the year's accounts by more than 10% (incurred first); and no
    base reconciles. A reading reports the fall when it quotes both cells for the same underwriting year. The
    loader (run_analysis.py) removes the record from the primary at the unusable-severity step with the tag
    RESTATED_BASE_TABLE; under outcome 'precedence_672' the register is not read.
  * "history_restated": rule 6. The table ties to the year's accounts (or its basis explains the gap), but an
    underwriting year u <= t-2 moved beyond the exchange rate without explanation by more than 1% of R, or the readings
    disagree on the validity label but not on the facts, or (clause take_on_base_bounded, rule 5b) the filing prints no
    transferred gross amount for a take-on in year t but bounds it at or below 10% of R, or (clause
    take_on_table_unreconciled) an explained take-on that is already in R has a table that does not reconcile with the
    filing's own roll-forward, or (clause derived_correction) the record's corrected figure is the session's derivation
    from cells both readers quote (1274/2016). The record stays; the least-certain sensitivity
    (src/check_low_confidence_sensitivity.py) reads this bucket and leaves the records out.
  * "source_history_set_aside": rule 8. A record on which specific source evidence raises a material unresolved concern
    about overlapping claims history, gross/net mixing or cohort reassignment through closure, and whose declared gross
    original-cohort outcome cannot be defensibly reconstructed or validated, whatever its size or sign. Each entry names its
    reason code (source_history_unresolved), the concerns, the facts two readings report, the census criteria that selected
    the record and the readings (K, L; Z where the first two conflicted). The loader (run_analysis.py) gives the record no
    figure and the tag SOURCE_HISTORY_SET_ASIDE and counts it (source_history_set_aside), one mask for estimation, donor pools,
    tools and scoring; under outcome 'precedence_672' the register is not read.
  * "takeon_unmeasurable": rule 5b. The year's take-on (an RITC, LPT or merger effective in year t whose acquired history
    the table shows 'as if always') is not in R, the filing prints no transferred gross amount, and the readings show the
    acquired share of the base could exceed 10% of R: the movement is development on a combined book whose base cannot
    be measured. The loader removes the record from the primary at the unusable-severity step with the tag
    TAKEON_BASE_UNMEASURABLE (data/takeon_not_development.json, which describes the step of the mature-cohort figure and
    applies to a block carrying a displaced figure, does not fit: the figure here is the extraction's own and the base,
    not the step, is what is missing); under outcome 'precedence_672' the register is not read.

The other rules are applied through the registers that already carry them: rule 2 (the author's rule B) through
data/fx_untranslated_excluded.json (3000/2022), rules 3 and 4 through data/mature_cohort_figures.json (2232/2020,
4242/2022, 318/2024, 1274/2016, 1609/2024), and rule 5 through data/opening_reserves_takeon_base.json (every candidate
whose take-on the readings print is already there).

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
#: the round-8 readers (round8/briefs/brief_r8.md, 24 October 2026): they read rule 1's year t-1 control again for
#: 780/2016 and 4747/2024; their readings carry no validity verdict and are kept with the entry as its control readings
ROUND8 = HERE / "results" / "extraction_error_rate" / "mature-cohort" / "round8"
READINGS8 = ROUND8 / "readings"
CONTROL_READERS = ("Z7", "Z8")
#: the record rule 6 lists since the round-8 readings (it was excluded under rule 1 until then)
ROUND8_RULE6 = ("780_2016",)
#: rule 4b's population scan over the readings of rounds 5 to 8: every record's answer (round8/scan_rule_4b.py)
RULE_4B_SCAN = ROUND8 / "rule_4b_scan.json"
#: rule 5b's threshold: the acquired share of the base, in per cent of the opening gross claims outstanding R
TAKEON_THRESHOLD_PCT = 10.0
VALID = ("valid", "screen_misread", "units_slip")
INVALID = ("restated_base", "undeterminable")
SESSION = "decision of the Claude analysis session, 23 October 2026"
SESSION_R8 = "decision of the Claude analysis session, 24 October 2026 (after the round-8 readings)"

#: round 9 (26 October 2026): the source-history census (rule 8 of the round-5 decision rules). The rule is the
#: recommendation of the Codex analysis, adopted on Colin's instruction of 26 October 2026 and applied by the Claude
#: analysis session. Codex found the concern in its tail investigation of 6131/2021, after the results were seen (post hoc);
#: the census applied the rule to every record its source-feature criteria select (population.md: 81 core and 20 host-side
#: records, chosen without outcome values). Two independent arms (K1-K8, L1-L8, every record read twice, brief_r9.md) and
#: third readings where the facts conflicted (Z11: 6118/2018; Z12: 3330/2017 and 3330/2018; Z13: 3500/2019 and 3000/2016;
#: round 10, brief_r10.md: Z9 and Z10 for 1609/2024).
ROUND9 = HERE / "results" / "extraction_error_rate" / "mature-cohort" / "round9"
READINGS9 = ROUND9 / "readings"
POPULATION9 = ROUND9 / "population.json"
CENSUS_READERS = (tuple("K%d" % i for i in range(1, 9)) + tuple("L%d" % i for i in range(1, 9))
                  + ("Z9", "Z10", "Z11", "Z12", "Z13"))
SESSION_R9 = "decision of the Claude analysis session, 26 October 2026 (the source-history census, round 9)"
CODEX_RULE_TEXT = (
    "set aside an observation when specific source evidence raises a material unresolved concern about overlapping claims "
    "history, gross/net mixing or cohort reassignment through closure, and the declared gross original-cohort outcome "
    "cannot be defensibly reconstructed or validated; regardless of the outcome's size or sign; an unexpired exposure, "
    "ordinary internal RITC, funds-withheld arrangement, unusual business, youth or SPA status is not sufficient by "
    "itself; a calendar/triangle inequality alone is insufficient where FX or accounting scope differs.")

RULE = (
    "Round 5 of the filing readings (decision rules of 23 October 2026, a decision of the Claude analysis session, "
    "results/extraction_error_rate/mature-cohort/round5/rules.md). 'excluded' (rule 1 or rule 4b; each entry names its "
    "rule). Rule 1: a record leaves the PRIMARY "
    "sample (outcome 'mature_cohort') when its year t development table's history (an underwriting year u <= t-2, or "
    "the table as a whole) differs from the year t-1 report beyond the exchange rate with no explanation in either "
    "filing; AND the year t table fails the year's accounts (implied gross incurred off by more than 10% beyond what "
    "its basis explains; the paid test decides only where the table gives no implied incurred) while the year t-1 control ties (within 5%; or within 10% when the "
    "same basis gap explains both years, an '& prior' column outside the cells or an ultimate basis against earned "
    "accounts, and the year t miss is at least three times the control's); AND the year t-1 report's "
    "printed base does not give a figure that reconciles either. Rule 4b (a table its own cells prove inconsistent, "
    "added 24 October 2026 after the round-8 readings): where rule 1's control does not tie, a record still leaves the "
    "PRIMARY sample when (i) both readings report that the year t table prints, for an underwriting year u <= t-2, "
    "cumulative paid lower than the year t-1 report printed for the same year, by more than the exchange rate explains "
    "and with no explanation in either filing (a reading reports the fall when it quotes both cells for the same "
    "underwriting year, whether or not it names it); (ii) the year t table fails the year's accounts by more than 10% "
    "(rule 1's test); and (iii) no base gives a figure that reconciles (rule 3 fails). Incurred first (added 24 October "
    "2026 after the review of the fixes): rule 1's accounts test and rule 4b's (ii) use the implied gross incurred test "
    "wherever the table gives one; the paid test decides only where the table gives no implied incurred, because M is an "
    "incurred movement and a paid cell M does not use cannot make M unmeasured. Rules 1 to 7 were written before the "
    "adjudication; rule 5b, rule 6's take-on clause (take_on_table_unreconciled), rule 1's exact control clause and "
    "rule 4b were added after particular readings or review 8 (rules.md names them). The exact control clause, made "
    "exact on 23 October 2026 after review 8 and re-applied to every record: on 23 October it moved no record "
    "(4242/2022 moved from rule 1 to rule 3 on review 8's decision to set aside the merged '2016 & Prior' column; its "
    "control, -1.1%, ties under either reading); applied to the round-8 readings Z7 and Z8 it takes 780/2016 and "
    "4747/2024 out of rule 1. Rule 4b, applied "
    "to the readings of every record of rounds 5 to 8 (round8/rule_4b_scan.json), decides two records: 4747/2024 and "
    "2232/2017. "
    "The loader (run_analysis.py) removes an 'excluded' "
    "entry's record at the unusable-severity step with the tag RESTATED_BASE_TABLE and counts it "
    "(restated_base_excluded); under outcome 'precedence_672' the register is not read and nothing changes. "
    "'history_restated' (rule 6): the table ties to the year's accounts (or its basis explains the gap), but an "
    "underwriting year u <= t-2 moved beyond the exchange rate without explanation by more than 1% of R "
    "(unexplained_history_move), or the two readings disagree on the validity label (valid, screen_misread, units_slip "
    "against restated_base, undeterminable) but not on the facts (label_disagreement), or (rule 5b) the filing prints no "
    "transferred gross amount for a take-on in year t but bounds it at or below 10% of R (take_on_base_bounded), or "
    "an explained take-on already in R has a table that does not reconcile with the filing's own roll-forward "
    "(take_on_table_unreconciled), or the record's corrected figure is the session's derivation from cells both readers "
    "quote, a figure neither reader gives (derived_correction); the record stays in the primary "
    "and src/check_low_confidence_sensitivity.py leaves it out of its least-certain refit. 'takeon_unmeasurable' (rule 5b, "
    "decision of the Claude analysis session, 23 October 2026): a record leaves the PRIMARY sample when an RITC, LPT or "
    "merger effective in year t, whose acquired history the table shows as if always, is not in the opening gross claims "
    "outstanding R, the filing does not print the transferred gross reserves, and the readings show the acquired share "
    "of the base could exceed 10% of R (an unmeasurable take-on, as 1861/2020 and 1084/2022 are); the loader removes the "
    "entry's record at the unusable-severity step with the tag TAKEON_BASE_UNMEASURABLE and counts it "
    "(takeon_base_unmeasurable_excluded); under outcome 'precedence_672' nothing changes. A take-on the filing bounds "
    "at or below 10% of R stays and is listed under history_restated. 'source_history_set_aside' (rule 8, the source-history "
    "rule of 26 October 2026, the recommendation of the Codex analysis adopted on Colin's instruction and applied by the Claude "
    "analysis session; found during Codex's tail investigation of 6131/2021, post hoc, and applied to the census population "
    "chosen by source features): a record leaves the PRIMARY sample when specific source evidence raises a material unresolved "
    "concern about overlapping claims history, gross/net mixing or cohort reassignment through closure and the declared gross "
    "original-cohort outcome cannot be defensibly reconstructed or validated, whatever its size or sign; the loader gives it no "
    "figure and the tag SOURCE_HISTORY_SET_ASIDE and counts it (source_history_set_aside), under outcome 'precedence_672' "
    "nothing changes. Every entry rests on two "
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
    "control_readings": ("780/2016 and 4747/2024, the two rule-1 records whose control needed the 10% branch, read again "
                         "for rule 1's year t-1 control by Z7 and Z8 (round8/briefs/brief_r8.md, 24 October 2026): "
                         "both fail the clause; 780/2016 returns under rule 6 and 4747/2024 leaves under rule 4b"),
    "rule_4b_scan": ("rule 4b applied to the readings of every record of rounds 5 to 8 (round8/rule_4b_scan.json, "
                     "round8/scan_rule_4b.py): it decides 4747/2024 and 2232/2017; every other record's answer to its "
                     "conditions is recorded there"),
    "not_read": ("the 2 cell-scale slips (2001/2018, 2121/2019) and the records the screen could not compare (no year "
                 "t-1 gross grid, record or common single year) or found clean"),
}

# ------------------------------------------------------------------------------------------------ the adjudication
#: rule 1 (decision of the Claude analysis session, 23 October 2026): the facts each condition rests on, from both readings
EXCLUDED = {
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
            "in both years (108,937; 131,452). Rule 1's exact control clause (23 October 2026): within 5%; met"),
        "previous_base_reconciles": (
            "on the 2022 printed diagonal the mature movement is about +103.9m, above the year's total gross incurred of "
            "58.2m (V1, V2)"),
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
        "control_ties": ("the 2021 table: 82.7m against 82.0m (+0.9%, P4, Q5). Rule 1's exact control clause "
                         "(23 October 2026): within 5%; met"),
        "previous_base_reconciles": (
            "the 2021 report's cells give no 2022 movement for the 2018 year folded into the 2020 column, whose movement "
            "is in no printed column (Q5); P4's like-for-like -15.8m is an inference, not a printed cell"),
    },
}

#: rule 4b (decision of the Claude analysis session, 24 October 2026, after the round-8 readings): a table its own cells
#: prove inconsistent. Where rule 1's control does not tie, the record still leaves the primary when (i) both readings
#: report that the year t table prints, for an underwriting year u <= t-2, cumulative paid lower than the year t-1
#: report printed for the same year, beyond the exchange rate and unexplained; (ii) the table fails the year's accounts
#: by more than 10% (rule 1's test); (iii) no base gives a figure that reconciles (rule 3 fails). Applied to the readings
#: of every record of rounds 5 to 8 (round8/rule_4b_scan.json); these two records meet it
#: the conditions of rule 1 and of rule 4b, each with the value an excluded entry of that rule must show (the loader,
#: run_analysis.RESTATED_EXCLUDED_RULES, holds the same)
CONDITIONS_1 = (("history_differs_unexplained", True), ("year_t_fails_accounts", True), ("control_ties", True),
                ("previous_base_reconciles", False))
CONDITIONS_4B = (("control_ties", False), ("cumulative_paid_falls_unexplained", True), ("year_t_fails_accounts", True),
                 ("previous_base_reconciles", False))
EXCLUDED_4B = {
    "2232_2017": {
        "control_ties": (
            "control miss +7.4% (P3: the 2016 table's own movement 99,984 against 2016 gross incurred 93,058; Q4's paid "
            "control, +62.1%, is confounded by a retranslation): over 5%, and the year t miss, incurred -10.5%, is 1.4 "
            "times it, not three times, with the opposite sign (the table above the accounts in 2016, below in 2017). "
            "Rule 1's exact control clause: not met; the control does not tie"),
        "cumulative_paid_falls_unexplained": (
            "the 2017 table (p40) prints UY2012 cumulative gross paid 19,393 against 22,799 in the 2016 report (p40), "
            "x0.851, and UY2013 43,200 against 47,658, x0.906 (P3: 'falling between the two reports ... with no stated "
            "reason'; Q4 quotes the same cells in its paid derivation). Q4 measures the retranslation of the same "
            "columns' earlier cells at x0.918-0.939, so UY2012's fall is beyond the exchange rate (UY2013's is at its "
            "edge). Both filings state translation 'at the rates that applied at the end of each underwriting year' "
            "(p40), which explains no move, and neither filing explains it (P3, Q4)"),
        "year_t_fails_accounts": (
            "implied incurred 264.9m against 296.0m in the accounts (-10.5%, P3 and Q4; p14, p40): over 10%, narrowly. "
            "The table is on an underwriting-year (ultimate) basis against earned accounts, which would put the table "
            "above the accounts, not below, so its basis does not explain the miss. The cross-report paid -20.1% is a "
            "proxy (the 2017 table prints no end-2016 payments) and is set aside"),
        "previous_base_reconciles": (
            "the 2017 table's end-2016 cells for u <= 2015 equal the 2016 report's latest exactly (31,666; 65,024; "
            "91,202; 118,237; P3, Q4), so the previous report's base gives the same movement (M +12.763m) and the same "
            "-10.5% miss; Q4's constant-currency M of about +34m is an estimate, not a printed figure: no base "
            "reconciles"),
        "found_by": ("the rule-4b population scan of 24 October 2026 (round8/rule_4b_scan.json); rule 6 listed it "
                     "until then (label_disagreement: P3 valid, Q4 restated_base)"),
    },
    "4747_2024": {
        "control_ties": (
            "control miss -7.2% (the 2023 table's implied incurred 27.9m against 30.1m; P2, Q3, Z7; Z8 -7.15%), over "
            "5%, and no shared basis gap (Z7, Z8): the gap is a shortfall, which an ultimate or underwriting basis "
            "cannot give, the table has no outside column, and FX on claims outstanding (570, 2023 p30) is about 27% "
            "of it (Z8). Rule 1's exact control clause: not met; the control does not tie. (Until the round-8 "
            "readings the record was excluded under rule 1, the session reading a basis gap neither reader named)"),
        "cumulative_paid_falls_unexplained": (
            "the 2024 table (p48) prints UY2020 cumulative paid 213 against 4,843 in the 2023 report (p39), and UY2021 "
            "4,164 against 5,883 (P2, Q3, Z7, Z8): 'a cumulative figure cannot fall' (Z8). The 2020-2021 estimates "
            "move by the exchange scale or less (Z8), so no exchange rate gives a fall of 96%; the only restatement "
            "note (p31) concerns the management fee (Z8)"),
        "year_t_fails_accounts": (
            "implied incurred 11.2m against 61.9m (-81.9%, note 6 p35; P2, Q3, Z7, Z8); paid 8.7m against 22.1m "
            "(-60.7%, p17; P2, Q3)"),
        "previous_base_reconciles": (
            "against the 2023 printed cells the 2024 latest diagonal gives 96,582 - 51,304 = 45.3m against 61.9m (-27%, "
            "from the cells both readings quote) and M -4.3m (P2); the 2024 table's end-2023 diagonal less the 2023 "
            "paid implies a 72.9m end-2023 reserve against 38.9m (P2): no figure reconciles"),
        "found_by": "the round-8 readings Z7 and Z8 (round8/briefs/brief_r8.md); rule 1 excluded it until then",
    },
}

#: rule 6 (decision of the Claude analysis session, 23 October 2026): the clauses and the facts, from the readings
HISTORY_RESTATED = {
    "382_2021": (["unexplained_history_move"],
                 "UY2014's end-2020 cell in the 2021 table (187,147) is 10.3m above the 2020 report's printed estimate "
                 "and out of line with its own column (169,537 -> 187,147 -> 170,900), unexplained in the filing (P1, "
                 "Q8): 2.1% of R (498.1m). The rest moves by the stated retranslation; the table ties to the balance "
                 "sheet and its incurred gap (-8.7%) is the 2020 control's (-6.9%), the pre-2011 years outside the "
                 "table. M as printed (+20.409m) stands. Rule 1 under the exact control clause (23 October 2026, "
                 "review 8): not met. The control miss is -6.9% (over 5%, within 10%, the same pre-2011 years outside "
                 "the table in both years), but the year t miss, -8.7%, is 1.3 times the control's, not three times, "
                 "and is itself under 10%. The record stays least certain"),
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
                 "table (control +2.1%); outstanding ties. Rule 1 does not apply: incurred is within its 10%, and the "
                 "paid -15.7% (Q1) is a cross-report proxy because the 2023 table prints no end-2022 payments (P8, "
                 "Q1)"),
    "780_2016": (["unexplained_history_move"],
                 "the 2016 table (p30) re-cuts its history: its end-2015 diagonal is 528.0 against 701.6 in the 2015 "
                 "report (p28), 173.6m lower cell by cell (2011 234.5 against 255.7; 2014 84.2 against 130.9; 2015 21.0 "
                 "against 75.2), its first-year cells are 40-55% of the 2015 report's, and the '2010 & prior' balance to "
                 "pay rises from 89.5 to 203.2 while total outstanding ties in both years (348.5; 313.8); the only "
                 "wording is the reconversion of non-dollar claims at year-end rates (p29) and a restatement of "
                 "reinsurance commissions (note 3(j)) (P6, Q5, Z7, Z8): far over 1% of R (348.5m). The year t table ties "
                 "to the accounts within 10%: implied incurred 146.3m against 138.6m (+5.6%, P6, Q5, Z7, Z8). It was "
                 "excluded under rule 1 until the round-8 readings, on P6's reserve identity (+79.8% paid), which is not "
                 "like for like: the 2016 table re-cuts its history, so its own end-2015 diagonal is not the base the 2015 "
                 "balance sheet was struck on (Z7, Z8). Rule 1's exact control clause: not met (Z7, Z8). The control miss "
                 "is +9.4% (the 2015 table's 110.268m against 100.753m), over 5%, and the year t miss, +5.6%, is 0.6 "
                 "times it on the percentages (Z7; 0.81 on Z8's absolute misses, 7.7m against 9.5m), so the 10% branch fails whatever the basis (shared basis "
                 "gap: undeterminable, Z7, Z8). Rule 4b: not met. Three of the four readings (Q5, Z7, Z8) report "
                 "UY2011's cumulative paid at 208.9 against 218.9 in the 2015 report (P6 quotes only 208.9), but the "
                 "table does not fail the accounts by more than 10% on incurred (condition (ii), incurred first). M as printed, +24.9m USD (2011 +2.4, 2012 +4.4, 2013 +3.4, 2014 +14.7; P6, Q5), "
                 "stands: the record returns to the primary sample (decision of the Claude analysis session, 24 October "
                 "2026, after the round-8 readings) and stays least certain"),
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
                  "does not say). The 2023 table ties (incurred -0.4%). Rule 1 under the exact control clause (23 "
                  "October 2026, review 8): not met. The year t incurred ties (-0.4%); the cross-table paid (+35%, P7; "
                  "+34.1%, Q6) comes, P7 shows, entirely from the restated UY2021 column, and the control does not tie under "
                  "either bound (-27.3%, Q6; about -29%, P7). The record stays least certain"),
    "1910_2018": (["unexplained_history_move"],
                  "the 2016 column was lowered (end-2017 73.0 against 76.5, ratio 0.954) while the other years rose "
                  "2.5-5.6% by the stated retranslation, unexplained (Q7: 'not explained anywhere'; P8): 6.8m, 2.1% of "
                  "R (322.1m). The table ties to the provision; incurred +5.3% on an ultimate basis (control -3.8%). "
                  "Rule 1 does not apply: the paid +12.4% (P8; +6.3% with the 2017 paid retranslated) is a "
                  "cross-report proxy because the 2018 table prints no end-2017 payments (P8; Q7: not computable)"),
    "1947_2022": (["unexplained_history_move"],
                  "the 2018 column (oldest) is about 14% above the year's retranslation ratio at every age (about 4.3m, "
                  "3.7% of R 116.5m), unexplained (P2, Q3). Incurred ties (-0.5%, control +0.8%). Rule 1 does not "
                  "apply: the paid +20.8% (P2, Q3) is a cross-report proxy because the 2022 table prints no end-2021 "
                  "payments (Q3)"),
    "1967_2017": (["unexplained_history_move"],
                  "the whole 2011-2016 history, estimates and payments alike, is 6-16% above the 2016 report with no "
                  "retranslation or restatement statement (P5, Q6); 2015 moves 5.7m beyond the common factor (3.5% of R "
                  "165.2m). The table ties (+4.0% incurred, reserves exact). Rule 1 under the exact control clause (23 "
                  "October 2026, review 8): not met. The year t table does not fail the accounts: incurred +4.0% and "
                  "P5's reserve-identity paid test +1.7% (the like-for-like test used for 780/2016); Q6's cross-report "
                  "paid +55.2% is the proxy that the restated history itself distorts. The control miss is -7.6% "
                  "(Q6), over 5% and within 10%. The record stays least certain"),
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
                  "UY2013 and UY2014 fall at end-2015 against an exchange uplift (P6: unexplained; Q7: the 2013-2015 "
                  "columns look mis-allocated, the 2017 report re-allocates them); the stated basis is year-end "
                  "conversion (p35). Incurred ties (+3.1%, control +4.8%). Share of R, checked after review 8 against "
                  "rule 6's 1% of R (opening gross claims outstanding 1,601.0m, note 9(a), so 16.01m): the 2016 table's "
                  "end-2015 cells are 761.5 (UY2013) and 804.7 (UY2014) against 786.4 and 821.4 in the 2015 report, "
                  "falls of 24.9m (1.56% of R) and 16.7m (1.04% of R), 41.6m together (2.60%), both cells that the "
                  "exchange uplift (ratios 1.016, 1.074, 0.968, 0.980 for UY2011-UY2014, no common factor) should have "
                  "raised, so the move beyond the exchange rate is at least the fall; P6's own measure, about 2% of the "
                  "year's gross incurred (1,089.5m), is 21.8m or 1.4% of R. Every measure is over 1% of R: rule 6 is "
                  "met and the record stays on the list (decision of the Claude analysis session, 23 October 2026)"),
    "2001_2017": (["unexplained_history_move"],
                  "the end-2016 history is re-allocated across 2013 (+11.9%), 2014 (+9.7%) and 2015 (-21.1%) beyond the "
                  "stated year-end conversion (p33), with no explanation (P8, Q7). Incurred ties (-4.4%, control "
                  "+3.1%). Rule 1 does not apply: the paid -13.1% (P8) is a cross-report proxy because the 2017 table "
                  "prints no end-2016 payments (P8; Q7: not computable)"),
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
                  "incurred +59.5% against a +38.3% control, the 2010-and-prior years outside the table. Rule 1 under the "
                  "exact control clause (23 October 2026, review 8): not met. The control miss is +38.3%, over 10%, so "
                  "the control ties under neither bound (the same 2010-and-prior gap makes the year t incurred test "
                  "uninformative, P6, Q5); the year t incurred miss, +59.5%, is 1.6 times the control's, not three "
                  "times; and the year t paid test ties (-3.3% with the factor, P6; -2.9%, Q5). The record stays least "
                  "certain. P6 valid, Q5 restated_base"),
    "1274_2016": (["derived_correction"],
                  "added after review 8 (decision of the Claude analysis session, 23 October 2026). Rule 4 corrects the "
                  "misprinted 2012 cell (141,355 for 178,987 in the 2015 report), but the corrected figure, "
                  "+22.6943m USD, is the session's derivation from cells both readers quote, not a figure either gives "
                  "(P3: not correctable from the filing, +57.503m as printed; Q4: +19.871m with the 2015 report's cell "
                  "unretranslated): the 2015 cell at the 2012 column's own paid factor, 129,350 / 131,423 = 0.98423 "
                  "(data/mature_cohort_figures.json, correction.derived_figure_m). The factor is a choice: the other "
                  "columns' end-2015 ratios (0.96766 to 0.98919) give +21.806m to +25.659m (review 8: +21.8m to "
                  "+25.6m), and the 2008 column's factor 0.97948 gives +23.5435m, the figure carried before review 8. "
                  "Both readers call the table otherwise valid (paid -1.9%, the stated retranslation); the record "
                  "stays at the derived figure and joins the least-certain list"),
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
    "1609_2024": (["orientation_outside_evidence"],
                  "the round-5 and round-6 rule-4 correction (+13.935m USD, the 2024 table read by rows as transposed) is "
                  "REVERSED (decision of the Claude analysis session, 26 October 2026): the round-10 tie-break readers Z9 "
                  "and Z10 and the cohort-depth second reading read the 2024 table as labelled (the 2022 and 2024 tables "
                  "share an orientation, the 2023 table is the mirror). Decisive: the 2021 gross ultimate loss ratio falls "
                  "from 49.6% to 36.2% (2023 p5, 2024 p6), which only the as-labelled reading shows; the implied premium "
                  "and the net combined ratio agree. M = -0.185m USD (UW2021 -11,123; UW2022 +10,938), the figure the "
                  "table prints under its labels. The earlier test compared the 2024 rows with the transposed 2023 table, "
                  "which was circular. The record stays and is listed because its orientation needed evidence outside the "
                  "table. The earlier readings (P3, Q2, Z5, Z6) are kept; Z9 and Z10 are its census readings"),
    "6118_2018": (["unexplained_history_move", "label_disagreement"],
                  "the 2014 column's end-2017 cell is 21,267 against 101,239 in the 2017 report (about 80m, 44% of R "
                  "183.4m), unexplained in either filing (P3 gives the context of the 2014 year's closure into "
                  "Syndicate 1955; Q4: unexplained). Incurred -2.0% raw (P3), +9.5% earned-equivalent (Q4): within "
                  "rule 1's 10%. The paid -72.7% (Q4) is a cross-report proxy because the 2018 table prints no "
                  "end-2017 payments, only an end-2018 total rolled from the 2017 report's (P3, Q4), and that total's "
                  "scope shrank with the 2014 column (Q4). P3 valid, Q4 restated_base"),
}

#: the rule-6 listings of 3000/2016 (clause label_disagreement) and of 3500/2022 and 3500/2023 (clause
#: take_on_table_unreconciled, review 8) before the census: all three
#: now leave the primary under rule 8 (see SOURCE_HISTORY), and this text is kept in their entries as the earlier listing
LISTED_BEFORE_SET_ASIDE = {
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
    "3500_2022": (["take_on_table_unreconciled"],
                  "added after review 8 (decision of the Claude analysis session, 23 October 2026), on the same "
                  "all-prior-years scope as 3500/2023. RITCs of Syndicates 1897, 2468 and 1980/2014/2001 effective 1 "
                  "January 2022 and loss portfolio transfers (p4; note 7 p30 'Reinsurance of new liabilities "
                  "1,728,476'), the history carried as if always (the 2018 column about double the 2021 report's, Q7). "
                  "The RITCs are in R (3,955.045m USD = 2,615.345 + 1,339.7, data/opening_reserves_takeon_base.json), so "
                  "rule 5 changes nothing. But the table does not reconcile with note 7's change in estimates "
                  "including foreign exchange of -293.1m (-293,072, p30) on that scope: the movement on every column "
                  "that existed at end-2021 (2013-2019 and 2021) is -291.756m - 98.057m = -389.8m (review 8; P6's "
                  "workings), and the whole table (those columns plus the new 2022 column, +363.424m) is -26.4m, a gap "
                  "of 266.7m (P6; Q7 -26.389m); only the 2013-2019 columns alone (-291.8m, the adopted figure) are "
                  "within 0.4% of it. LPT placement conflict: P6 reads the mid-2022 loss portfolio transfers of "
                  "Syndicates 1200 (293.8m) and 1686 (67.1m) as entering the history as if always, while the ninth "
                  "census (data/opening_reserves_takeon_base.json) places all four LPTs (also 2468's 22.6m and 2001's "
                  "5.2m: 388.7m) in the 2022 column, outside M and outside R. Either way the acquired share outside R "
                  "is at most 9.1% of R for the two mid-2022 LPTs (360.9m of 3,955.045m) and 9.8% with all four "
                  "(388.7m), at or below rule 5b's 10%, so rule 5b would list the record too. Rule 1 does not reach it "
                  "(the history change is explained). It stays and joins the least-certain list"),
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

#: rule 8, the source-history rule (decision of the Claude analysis session, 26 October 2026): the 11 records the census
#: set aside, each with the readers whose readings it rests on, the concerns the rule names that the readings find, and the
#: facts both readings (or two of three) report (round9/adjudication.md). A decision rests on facts at least two readings
#: report; 3000/2016 is set aside by K3 and the third reading Z13 (L3 found the concern resolved).
SOURCE_HISTORY = {
    "1084_2018": {
        "readers": ("K2", "L2"), "concern": ["cohort_reassignment_through_closure"],
        "facts": ("the UK Division RITC to 1274 (gross 199.7m, net nil, 1 January 2018) falls between the diagonals: the "
                  "end-2017 cells are pre-transfer and the end-2018 cells post; incurred -20.6% against the accounts "
                  "(control +0.1-0.2%); adding back 199.7m closes the gap; no cohort split is printed")},
    "1416_2024": {
        "readers": ("K4", "L4"), "concern": ["cohort_reassignment_through_closure"],
        "facts": ("the 2021 column vanishes at the opening of 2024 while its reserve stays in R; the base is retranslated; "
                  "incurred -14% against the accounts; no bridge")},
    "1884_2021": {
        "readers": ("K8", "L8"), "concern": ["overlapping_claims_history"],
        "facts": ("a pro forma 'as if always' table for three RITC'd 2018 books (1861, 1955 and another, 1 January 2021); "
                  "the accounts test fails by 23.0m; the 2022 and 2023 reports reprint the end-2021 diagonal about 25.7m "
                  "higher; no t-1 table")},
    "2008_2023": {
        "readers": ("K8", "L8"), "concern": ["overlapping_claims_history", "cohort_reassignment_through_closure"],
        "facts": ("the 1301 and 1492 RITCs and the QBE LPT (1 January 2023) are 'as if always'; the filing says its "
                  "developments include reserves newly acquired, with no split; the 2014-16 columns are restated 13-33%; "
                  "incurred -29% / +14% against the accounts; no 2022 report")},
    "3000_2016": {
        "readers": ("K3", "Z13", "L3"), "concern": ["overlapping_claims_history"],
        "facts": ("the 1400 RITC is restated into 2011-2013: the end-2015 cumulative cells are 454m (49%) above the sum of "
                  "3000's and 1400's own 2015 tables, unexplained; the end-2015 diagonal mixes rates (paid revalued, "
                  "reserves not), putting about 75m of retranslation in M; the accounts state a favourable movement "
                  "against M +27.3m adverse (K3 and Z13 set aside; L3 found the concern resolved)")},
    "3500_2021": {
        "readers": ("K3", "L3"), "concern": ["overlapping_claims_history"],
        "facts": ("about 1.4bn of 1 January 2021 RITCs are folded into the 2012-2018 rows without a note; the functional "
                  "currency changed the same day; the table's incurred is +109.1m against -25.4m (P&L) / -60.6m "
                  "(note 7); no cohort bridge")},
    "3500_2022": {
        "readers": ("K3", "L3"), "concern": ["overlapping_claims_history"],
        "facts": ("about 1.37bn of 1 January 2022 RITCs are in the mature rows; the end-2021 cells are 2.5bn above the 2021 "
                  "report; the table's -389.8m against -126.1m / -293.1m")},
    "3500_2023": {
        "readers": ("K3", "L3"), "concern": ["overlapping_claims_history", "cohort_reassignment_through_closure"],
        "facts": ("seven 1 January 2023 RITCs (3.04bn) are folded in; the 1200 LPT is reassigned out of the 2022 column "
                  "('replaces a previously recorded LPT'); the end-2022 cells are 2-3 times the 2022 report's; the "
                  "table's -52m against -185m")},
    "6111_2017": {
        "readers": ("K7", "L7"), "concern": ["cohort_reassignment_through_closure", "gross_net_mixing"],
        "facts": ("the closure settlement of the 2014 year (76,855) falls between the diagonals and is settled net "
                  "(policy p14); incurred about +20% after FX (control tied); the stated run-off 4.7m against net M about "
                  "15m; no cohort bridge")},
    "6111_2018": {
        "readers": ("K7", "L7"), "concern": ["cohort_reassignment_through_closure", "gross_net_mixing"],
        "facts": ("the same pattern for the 2015 year (83,790): incurred about +40%; the FX line is distorted; no bridge")},
    "6131_2021": {
        "readers": ("K8", "L8"), "concern": ["overlapping_claims_history", "gross_net_mixing"],
        "facts": ("the table implies gross paid 10.5m against 6.5m in the accounts (+61%) and incurred 11.1m against 6.9m; "
                  "the net excess equals the two named closing amounts; the 2018 row's gross paid equals its net paid "
                  "(4,114) after the venture's RITC; the 2019 row's paid rises more than the year's gross paid; there "
                  "are no closing accounts in the corpus to bridge; all earlier years pass")},
}

#: rule 6 listings from the census (decisions of the Claude analysis session, 26 October 2026): records the census readings
#: kept in the primary but left with a residual concern that falls short of rule 8's set-aside test. clause
#: census_residual_concern: the concern is specific but the outcome is reconstructed or validated well enough to stay;
#: derived_correction: 3330/2017's figure is the session's roll-forward, which the corrections register carries;
#: orientation_outside_evidence: 1609/2024's table orientation needed evidence outside the table (after its reversal).
#: {key: (clauses, readers, facts)}; the readers are the census readers whose readings it rests on
CENSUS_LISTED = {
    "1110_2020": (["census_residual_concern"], ("K4", "L4"),
                  "four take-ons are booked to u >= 2019, outside M; the table is 6.8% short of the balance sheet and its "
                  "incurred 7-14% short, with no bridge: an inequality without a specific history concern on M's cohorts "
                  "(L4 sets it aside, K4 finds it undeterminable; the census decision is that the readings report no "
                  "specific overlap, gross/net mixing or reassignment on M's cohorts)"),
    "1254_2023": (["census_residual_concern"], ("K6", "L6"),
                  "the end-2022 diagonal of the 2023 table sits about 23m (about 41% of R, 55.6m) above the 2022 report's "
                  "table at a like-for-like rate: the 2022 table (read by L6 from the page image, p30; K6 found none) is "
                  "2689's estimates before the RITC of its 2017-2019 years (1 January 2022), the 2023 table's are 1254's "
                  "own. The year's incurred ties to the accounts within 2.3% and the cohort bridge gives +8.7m for these "
                  "years against the table's +10.5m, so the table is bridged as the taken-on book's development; the "
                  "restated base is over 1% of R and is listed under rule 6's 1%-of-R clause"),
    "1686_2021": (["census_residual_concern"], ("K3", "L3"),
                  "the opening-2021 RITC of Syndicate 2007 and its SPA 6129 (903.2m gross, in R) is built into the "
                  "2016-2018 rows as if always; the table ties to the accounts within 0.3% and the end-2020 diagonal rolls "
                  "to opening provision plus RITC within 1.2%. The 2018 row sits 110-130m above 2007's own cells "
                  "(possible 6129 overlap; the filing says 6129 was eliminated), worth 18.1m of M: 5-6% of R on the "
                  "take-on-inclusive base (2,076.8m USD), over rule 6's 1% of R"),
    "3330_2017": (["derived_correction"], ("K4", "L4", "Z12"),
                  "the 2017 table's end-2016 cells are about 1.5m above the opening balance sheet (translation would lower "
                  "them) and its printed M (-0.990m) has the opposite sign to the accounts' incurred (+0.559m); the "
                  "whole reserve is in the two mature rows, so the roll-forward (14,059 + 559 - 2,270 - 647 = 11,701) "
                  "gives M = +0.559m GBP, a derived figure no reader prints as a cohort split (L4, Z12; K4 stands on the "
                  "printed figure); the 2016 report is not in the corpus"),
}
#: what the corrections register (data/mature_cohort_figures.json) carries for each census figure change
CENSUS_FIGURES = {
    "3330_2018": "rule 3: +1.094m GBP in place of -1.384m (the 2017 report's printed end-2017 cells as the base)",
    "3330_2017": "derived: +0.559m GBP in place of -0.990m (the roll-forward of the opening balance sheet)",
    "1609_2024": ("rule-4 correction REVERSED: -0.185m USD as printed in place of +13.935m (the table is as labelled; round "
                  "10, Z9 and Z10)"),
}

#: every record of the round with its rule and outcome (the adjudication: round5/adjudication.md)
_STANDS = "7", "stands"
OUTCOMES = {
    **{k: ("1", "excluded", "data/restated_base_excluded.json (excluded)") for k in EXCLUDED},
    # rule 4b (24 October 2026, after the round-8 readings): 4747/2024 (rule 1 until then) and 2232/2017 (rule 6 until
    # then, found by the rule-4b population scan)
    **{k: ("4b", "excluded", "data/restated_base_excluded.json (excluded, rule 4b)") for k in EXCLUDED_4B},
    **{k: ("6", "least_certain", "data/restated_base_excluded.json (history_restated)") for k in HISTORY_RESTATED},
    "3000_2022": ("2", "excluded", "data/fx_untranslated_excluded.json (excluded)"),
    "2232_2020": ("3", "corrected", "data/mature_cohort_figures.json (previous_report_base)"),
    # 4242/2022: rule 3 after review 8 (it was excluded under rule 1 before: the previous report's base reconciles once
    # the merged '2016 & Prior' column both readers call unreadable is set aside)
    "4242_2022": ("3", "corrected", "data/mature_cohort_figures.json (previous_report_base)"),
    "318_2024": ("4", "corrected", "data/mature_cohort_figures.json (printed_table_error)"),
    # 1609/2024: the rule-4 correction was reversed on 26 October 2026 (round 10: Z9, Z10); the record stays at the printed
    # figure and is listed (clause orientation_outside_evidence)
    "1609_2024": ("4 (reversed) and 6", "correction_reversed_least_certain",
                  "data/restated_base_excluded.json (history_restated, orientation_outside_evidence); the correction is "
                  "removed from data/mature_cohort_figures.json"),
    **{k: ("5", "take_on_base", "data/opening_reserves_takeon_base.json (already in R)")
       for k in ("1856_2024", "1884_2021", "2488_2019", "4000_2022", "4444_2018", "4444_2023")},
    # 1686/2021: rule 5 holds (R carries the take-on) and the source-history census lists it under rule 6 (26 October 2026,
    # clause census_residual_concern: the 2018 row sits 110-130m above 2007's own cells)
    "1686_2021": ("5 and 6", "take_on_base_and_least_certain",
                  "data/opening_reserves_takeon_base.json (already in R) and data/restated_base_excluded.json "
                  "(history_restated, census_residual_concern)"),
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
OUTCOMES["3000_2016"] = ("5 and 8", "take_on_base_and_set_aside",
                         "data/opening_reserves_takeon_base.json (already in R) and data/restated_base_excluded.json "
                         "(source_history_set_aside)")
#: 3000/2016, 3500/2022 and 3500/2023 left the least-certain list for the excluded set on 26 October 2026: the
#: source-history census set them aside under rule 8 (their round-5 readings stay in their entries); rule 5 still holds (R carries the take-on)
OUTCOMES["3500_2023"] = OUTCOMES["3000_2016"]
#: 3500/2022 joined the list after review 8 under the same clause as 3500/2023 (take_on_table_unreconciled)
OUTCOMES["3500_2022"] = OUTCOMES["3500_2023"]
#: 1884/2021 (rule 5, R carries its take-on) and 1416/2024 (round 5: stands) are set aside by the census as well
OUTCOMES["1884_2021"] = OUTCOMES["3000_2016"]
OUTCOMES["1416_2024"] = ("7 and 8", "stands_then_set_aside",
                         "data/restated_base_excluded.json (source_history_set_aside); round 5 had it stand")
#: 1274/2016 (rule 4) is corrected to a figure the session derives from cells both readers quote, so it also joins the list
#: (clause derived_correction)
OUTCOMES["1274_2016"] = ("4 and 6", "corrected_least_certain",
                         "data/mature_cohort_figures.json (printed_table_error, derived) and "
                         "data/restated_base_excluded.json (history_restated, derived_correction)")
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
    # round 8: Z8 keys its records by the filing's name ('syndicate_780_2016')
    for rid in CONTROL_READERS:
        with io.open(READINGS8 / ("%s.json" % rid), encoding="utf-8") as fh:
            for k, e in json.load(fh).items():
                out.setdefault(k.replace("syndicate_", "", 1), []).append((rid, e))
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
    rnd = "round8" if rid in CONTROL_READERS else "round5"
    out = {"reader": rid, "source": "results/extraction_error_rate/mature-cohort/%s/readings/%s.json" % (rnd, rid),
           "pages": own, "pages_of_other_reports": other, "pages_as_read": e.get("pages")}
    out.update({k: v for k, v in e.items() if k not in ("key", "pages")})
    return out


#: the fields of a reading that carry its own words, in the order the quote takes them: the round-5 and round-8 readers'
#: explanation (or search note), then the round-9 readers' reason and the text they quote from the filing
QUOTE_FIELDS = ("explanation", "explanation_search", "note", "reason", "selection_event", "cells")


def _quote_of(r):
    for f in QUOTE_FIELDS:
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
    main = [(rid, e) for rid, e in reads if rid not in SUPPORTING + AMOUNT_READERS + CONTROL_READERS]
    supp = [(rid, e) for rid, e in reads if rid in SUPPORTING]
    ctl = [(rid, e) for rid, e in reads if rid in CONTROL_READERS]
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
    if bucket == "excluded" and key in EXCLUDED_4B:
        # rule 4b rests on the facts both readings report, not on their validity labels (2232/2017: P3 valid, Q4
        # restated_base)
        e["rule"] = "4b"
        e["conditions"] = {name: {"holds": want, "facts": EXCLUDED_4B[key][name]} for name, want in CONDITIONS_4B}
        e["found_by"] = EXCLUDED_4B[key]["found_by"]
        e["decision"] = ("%s: rule 4b of the round-5 decision rules; rule 1's control does not tie, but both readings "
                         "report that the year t table prints a cumulative paid figure for a year u <= t-2 lower than "
                         "the year t-1 report printed, beyond the exchange rate and unexplained, the table fails the "
                         "year's accounts by more than 10%%, and no base gives a figure that reconciles, so the table is "
                         "not one consistent cumulative table, no figure from it measures the year's movement, and the "
                         "record leaves the primary sample; the 672 sensitivity keeps it" % SESSION_R8)
    elif bucket == "excluded":
        if any(v != "restated_base" for v in verdicts):
            raise SystemExit("%s: rule 1 needs both readings to find a restated base (%s)" % (key, verdicts))
        e["rule"] = "1"
        e["conditions"] = {name: {"holds": want, "facts": EXCLUDED[key][name]} for name, want in CONDITIONS_1}
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
        elif "derived_correction" in clauses:
            rule = "rules 4 and 6"
        e["decision"] = ("%s: %s of the round-5 decision rules (%s); the record stays in the primary sample with its "
                         "figure and joins the least-certain sensitivity (src/check_low_confidence_sensitivity.py)"
                         % (SESSION_R8 if key in ROUND8_RULE6 else SESSION, rule, ", ".join(clauses)))
    e["readings"] = rr
    if supp:
        e["supporting_readings"] = [reading(rid, key, x) for rid, x in supp]
    if ctl:
        e["control_readings"] = [reading(rid, key, x) for rid, x in sorted(ctl)]
    return e



# ------------------------------------------------------------------------------------------------ round 9 (rule 8)
def load_readings9():
    """{key: {reader: entry}} from the archived round-9 readings (K1-K8, L1-L8, Z9-Z13; a key may carry a '|<task>' suffix)."""
    out = {}
    for rid in CENSUS_READERS:
        with io.open(READINGS9 / ("%s.json" % rid), encoding="utf-8") as fh:
            for k, e in json.load(fh).items():
                out.setdefault(k.split("|")[0], {})[rid] = e
    return out


def pages9(key, e):
    """The year t filing's pages a round-9 reading cites: its `pages` list where it gives one, else the table's page and
    the pages its selection-event field cites (the readers write page numbers as 'p33' in prose; a page of another
    report would be named with its year, and the selection-event field names the closure's own pages)."""
    pages = set()
    if isinstance(e.get("pages"), list):
        pages.update(_ints(e["pages"]))
    for f in ("table", "1_table", "item1_table"):
        t = e.get(f)
        if isinstance(t, dict) and isinstance(t.get("page"), int):
            pages.add(t["page"])
        elif isinstance(t, dict) and isinstance(t.get("page"), str):
            pages.update(int(x) for x in re.findall(r"\d+", t["page"])[:1])
    for f in ("selection_event", "2_selection_event", "item2_selection_event", "2_event"):
        if f in e:
            pages.update(_ints(e[f] if isinstance(e[f], str) else json.dumps(e[f])))
    return sorted(pages)


def reading9(rid, key, e):
    """One round-9 reading as the register keeps it: the archived entry verbatim, with the reader, its source, the year t
    filing's pages it cites and a verdict. A reading that gives no verdict field keeps verdict_as_read null and takes
    the verdict its reason states (1254/2023's second reader: the concern is resolved at the level of M)."""
    out = {"reader": rid, "source": "results/extraction_error_rate/mature-cohort/round9/readings/%s.json" % rid,
           "pages": pages9(key, e), "pages_as_read": e.get("pages"), "verdict_as_read": e.get("verdict")}
    out.update({k: v for k, v in e.items() if k not in ("key", "pages", "id")})
    if out.get("verdict") is None:
        text = str(e.get("reason") or "")
        out["verdict"] = "concern_resolved" if "resolved" in text else None
    return out


def population9():
    with io.open(POPULATION9, encoding="utf-8") as fh:
        return json.load(fh)


def census_block(key, pop):
    """The census record of one set-aside entry: the criteria that selected it and the evidence behind each, from
    round9/population.json (chosen from source features before any outcome was seen)."""
    sel = {x["id"]: x for x in pop["selected"]}
    x = sel[key]
    return {"population": "results/extraction_error_rate/mature-cohort/round9/population.json (population.md)",
            "criteria": list(x["criteria"]), "evidence": x["evidence"],
            "chosen_by": "source features only (no outcome value, sign or size was used); criteria S1-S6, population.md"}


def source_history_entry(key, reads9, reads5, pop):
    """A rule-8 entry: two readings that each set the record aside (a third reading where the first two conflicted), the
    facts they report, the census record, the concerns, the pages and a quote. 3500/2022 and 3500/2023 carry their
    round-5 readings and their earlier rule-6 listing as earlier_listing."""
    spec = SOURCE_HISTORY[key]
    rr = [reading9(rid, key, reads9[key][rid]) for rid in spec["readers"]]
    for r in rr:
        if not r["pages"]:
            raise SystemExit("%s: reader %s's reading cites no page of the year t filing" % (key, r["reader"]))
    e = {"rule": "8", "reason_code": "source_history_unresolved", "concern": list(spec["concern"]),
         "facts": spec["facts"],
         "pages": sorted({p for r in rr for p in r["pages"]}),
         "quote": " || ".join("reader %s: %s" % (r["reader"], _quote_of(r)[:600]) for r in rr),
         "verdicts": {r["reader"]: r["verdict"] for r in rr},
         "census": census_block(key, pop),
         "decision": ("%s: rule 8 of the round-5 decision rules, the source-history rule (the recommendation of the Codex "
                      "analysis, adopted on Colin's instruction of 26 October 2026; applied by the Claude analysis "
                      "session): specific source evidence raises a material unresolved concern about overlapping claims "
                      "history, gross/net mixing or cohort reassignment through closure (%s), and the declared gross "
                      "original-cohort outcome cannot be defensibly reconstructed or validated, so the record leaves the "
                      "primary sample whatever the outcome's size or sign; the 672 sensitivity keeps it"
                      % (SESSION_R9, ", ".join(spec["concern"]))),
         "readings": rr}
    if key in LISTED_BEFORE_SET_ASIDE:
        clauses, facts = LISTED_BEFORE_SET_ASIDE[key]
        e["earlier_listing"] = {"rule": "6", "clauses": list(clauses), "facts": facts,
                                "decision": ("%s: the record was listed under rule 6 until the census; it now leaves the "
                                             "primary under rule 8, and rule 5 still holds (its take-on is in R)" % SESSION),
                                "round5_readings": [reading(rid, key, x) for rid, x in sorted(reads5.get(key, []))
                                                    if rid in READERS]}
    return e


def census_listed_entry(key, reads9):
    """A history_restated entry the census adds (rule 6, a clause from the census), built from its round-9 readings."""
    clauses, readers, facts = CENSUS_LISTED[key]
    rr = [reading9(rid, key, reads9[key][rid]) for rid in readers]
    for r in rr:
        if not r["pages"]:
            raise SystemExit("%s: reader %s's reading cites no page of the year t filing" % (key, r["reader"]))
    return {"clauses": list(clauses), "facts": facts, "pages": sorted({p for r in rr for p in r["pages"]}),
            "quote": " || ".join("reader %s: %s" % (r["reader"], _quote_of(r)[:600]) for r in rr),
            "verdicts": {r["reader"]: r["verdict"] for r in rr},
            "decision": ("%s: rule 6 of the round-5 decision rules (%s), found by the source-history census (rule 8): the "
                         "readings keep the record in the primary sample but leave a residual concern short of the "
                         "set-aside test; it stays in the primary sample with its figure and joins the least-certain "
                         "sensitivity (src/check_low_confidence_sensitivity.py)" % (SESSION_R9, ", ".join(clauses))),
            "readings": rr}


#: the census readers of an existing history_restated entry (their readings are kept beside the round-5 readings) and the
#: census decision for it
CENSUS_EXISTING = {
    "6118_2018": (("K1", "L1", "Z11"),
                  "census (26 October 2026): stays, listed. Z11 (third reading, K1 set aside and L1 found the concern "
                  "resolved): the 2014 column narrowed to the 2014 year alone, unexplained in the 2018 report; M is within "
                  "one table on one basis; the table ties to the accounts within 2.0-2.5%"),
    "1609_2024": (("Z9", "Z10"),
                  "census, round 10 (26 October 2026): the 2024 table is as labelled; the rule-4 correction is reversed "
                  "and the record is listed (orientation_outside_evidence)"),
}


def source_history_meta(pop, set_aside, listed):
    t = pop["totals"]
    return {
        "rule_text": CODEX_RULE_TEXT,
        "rule": "rule 8 of results/extraction_error_rate/mature-cohort/round5/rules.md, dated 26 October 2026",
        "label": ("recommendation of the Codex analysis, adopted on Colin's instruction of 26 October 2026 and applied by "
                  "the Claude analysis session"),
        "found": ("during Codex's tail investigation of 6131/2021, after the results were seen (post hoc); the census "
                  "applied the rule to the population its source-feature criteria select, chosen without outcome values"),
        "population": {"file": "results/extraction_error_rate/mature-cohort/round9/population.md (population.json)",
                       "primary_records": pop["primary"]["records"], "primary_syndicates": pop["primary"]["syndicates"],
                       "selected_core": t["selected_core"], "selected_core_syndicates": t["selected_core_syndicates"],
                       "selected_host_side": t["selected_host_side"], "read_twice": t["selected_with_host_side"],
                       "by_criterion_core": t["by_criterion_core"], "touched_out": t["touched_out"],
                       "untouched": t["neither"]},
        "readings": ("round 9 (brief_r9.md): two independent arms K1-K8 and L1-L8, every selected record read twice; "
                     "third readings Z11 (6118/2018), Z12 (3330/2017, 3330/2018), Z13 (3500/2019, 3000/2016); round 10 "
                     "(brief_r10.md) Z9 and Z10 for 1609/2024"),
        "set_aside": sorted(set_aside, key=order_key),
        "listed_by_census": sorted(listed, key=order_key),
        "figure_changes": CENSUS_FIGURES,
        "adjudication": "results/extraction_error_rate/mature-cohort/round9/adjudication.md",
    }


def build():
    reads = load_readings()
    keys = sorted(set(OUTCOMES), key=order_key)
    if len(keys) != ROUND_RECORDS:
        raise SystemExit("OUTCOMES holds %d records, not the round's %d" % (len(keys), ROUND_RECORDS))
    read = {k for k, rs in reads.items() if any(rid[0] in "PQV" for rid, _ in rs)}
    if set(keys) != read:
        raise SystemExit("the records decided %s are not the records read %s" % (sorted(set(keys) - read),
                                                                                sorted(read - set(keys))))
    if len(set(EXCLUDED) | set(EXCLUDED_4B) | set(HISTORY_RESTATED) | set(TAKEON_UNMEASURABLE)) != (
            len(EXCLUDED) + len(EXCLUDED_4B) + len(HISTORY_RESTATED) + len(TAKEON_UNMEASURABLE)):
        raise SystemExit("a record in two buckets")
    pop = dict(POPULATION)
    counts = {}
    for k in keys:
        counts[OUTCOMES[k][1]] = counts.get(OUTCOMES[k][1], 0) + 1
    pop["outcomes"] = dict(sorted(counts.items()))
    reads9 = load_readings9()
    pop9 = population9()
    new_listed = [k for k in CENSUS_LISTED if k not in HISTORY_RESTATED]
    reg = {"_rule": RULE, "_population": pop,
           "_source_history": source_history_meta(pop9, SOURCE_HISTORY, list(CENSUS_LISTED) + list(CENSUS_EXISTING)),
           "_adjudicated": {k: {"rule": OUTCOMES[k][0], "outcome": OUTCOMES[k][1], "where": OUTCOMES[k][2],
                                "readers": [rid for rid, _ in reads[k]]} for k in keys},
           "excluded": {}, "history_restated": {}, "takeon_unmeasurable": {}, "source_history_set_aside": {}}
    for bucket, src in (("excluded", {**EXCLUDED, **EXCLUDED_4B}), ("history_restated", HISTORY_RESTATED),
                        ("takeon_unmeasurable", TAKEON_UNMEASURABLE)):
        for k in sorted(src, key=order_key):
            reg[bucket][k] = entry_for(k, reads[k], bucket)
    for k, (readers, why) in CENSUS_EXISTING.items():
        e = reg["history_restated"][k]
        e["census_readings"] = [reading9(rid, k, reads9[k][rid]) for rid in readers]
        e["census_decision"] = "%s: %s" % (SESSION_R9, why)
    for k in new_listed:
        reg["history_restated"][k] = census_listed_entry(k, reads9)
    reg["history_restated"] = dict(sorted(reg["history_restated"].items(), key=lambda kv: order_key(kv[0])))
    for k in sorted(SOURCE_HISTORY, key=order_key):
        reg["source_history_set_aside"][k] = source_history_entry(k, reads9, reads, pop9)
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
