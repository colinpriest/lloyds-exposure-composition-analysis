# Round-5 adjudication: tables whose history moved between reports

Decision of the Claude analysis session, 23 October 2026, applying the decision rules of `rules.md` record by record (rules 1 to 7 were written before the adjudication; rule 5b, rule 6's take-on clause and rule 1's exact control clause were added after particular readings or review 8, and `rules.md` names them) to the 83 records of the round: the 82 records the rebase screen (`screen/rebase_screen.py` over the primary's 649 records at 35a259c) asked to read, each read by one P-arm and one Q-arm reader (`readings/P1..P8`, `Q1..Q8`, brief `briefs/brief_r5.md`), and 2689/2023 (V1, V2; W1, W2 recomputed its figure; `briefs/brief_2689.md`). The two records whose readings disagreed on the facts (1609/2024, 4444/2017) were decided on the tie-break readings Z5 and Z6 (`briefs/brief_r6.md`). Every number below is a reader's, with the page the reader gives, or the session's arithmetic on cells the readers quote.

Round 7 (23 October 2026, same session): the two take-ons whose transferred amount the round-5 readings did not print (1110/2022, 1458/2024) were read again for the amount (readings U1 and U2, `briefs/brief_r7.md`), and rule 5b was added to `rules.md` before they were applied: a take-on the filing does not print leaves the primary as an unmeasurable take-on when the readings show the acquired share of the base could exceed 10% of R, and stays on the least-certain list when the filing bounds it at or below 10%. 3500/2023, whose take-on is in R but whose table does not reconcile with note 7, joined the least-certain list under rule 6's added clause. The outcomes below are those after round 7 and review 8.

Review 8 (23 October 2026, same session; the decisions below are those of the Claude analysis session after the review's findings): 4242/2022 moves from rule 1 to rule 3 (the 2021 report's printed base reconciles with the accounts once the merged '2016 & Prior' column is set aside; both readers give -80.015m USD); rule 1's control clause is made exact and re-applied to every record; 3500/2022 joins the least-certain list; 1274/2016's corrected figure becomes a derived one (+22.694m USD, the 2012 column's own exchange factor), kept apart from the readers' figures, and the record joins the list; 2001/2016 was checked against rule 6's 1% of R and stays. Rules 1 to 7 were written before the adjudication; rule 5b, rule 6's take-on clause (take_on_table_unreconciled) and rule 1's exact control clause were added after particular readings or the review (`rules.md` names them).

## How the rules were read

- Validity classes. A 'label' disagreement (rule 6) is one between the classes valid, screen_misread, units_slip and restated_base, undeterminable (the classes `compare_r5.py` uses for 'VERDICTS DIFFER'). A record whose two readings agree on the cells and the tests but not on the class is a label disagreement; one whose readings give different cells, figures or test results is a fact disagreement and went to a third reading (1609/2024, 4444/2017).
- Rule 6's first clause reads the screen's flag (a year u <= t-2 moved more than 5% beyond the common exchange factor and by more than max(1% of R, 1m)) together with the readings: the move is 'without explanation' when neither reading finds a cause in either filing (a stated retranslation explains a uniform move, not a year-specific one; a misprint in the year t-1 report, a basis change the filing states, an RITC, or a screen misread explains it).
- Rule 1's control (made exact on 23 October 2026, after review 8, and re-applied to every record). The year t-1 control ties within 5%; or within 10% when the same basis gap explains both years (an '& prior' column outside the cells, an ultimate basis against earned accounts) and the year t miss is at least three times the control's. Two of the four rule-1 records need the 10% clause: 780/2016 (control +9.5% from the '2010 & prior' years outside the cells; year t paid identity +79.8%, 8.4 times) and 4747/2024 (control -7.2%, outstanding tying exactly; year t -81.9%, 11.4 times; neither reader names its basis gap, which the session reads as the table's own underwriting-year basis, the place the clause leans on judgement). Under the exact clause 2232/2017, 2488/2016, 382/2021, 1967/2017 and 1729/2023 do not meet rule 1 and stay on the least-certain list, each entry saying why. Re-applying the clause to every record changed no outcome: 780/2016 and 4747/2024 meet it only through its 10% branch, and 4242/2022's move from rule 1 to rule 3 did not come from the clause (its control, -1.1%, ties under either reading) but from review 8's separate decision to set aside the merged '2016 & Prior' column.
- Rule 1 does not reach a year t-1 column: 2015/2022's table restates only its UY2021 column (outside M) and stands.

## Outcomes

| outcome | rule | records | keys |
|---|---|---|---|
| excluded | 1, 2 | 5 | 780_2016, 2689_2023, 3000_2022, 4747_2024, 6134_2022 |
| corrected | 3, 4 | 4 | 318_2024, 1609_2024, 2232_2020, 4242_2022 |
| corrected_least_certain | 4 and 6 | 1 | 1274_2016 |
| take_on_base | 5 | 7 | 1686_2021, 1856_2024, 1884_2021, 2488_2019, 4000_2022, 4444_2018, 4444_2023 |
| take_on_base_and_least_certain | 5 and 6 | 3 | 3000_2016, 3500_2022, 3500_2023 |
| take_on_unmeasurable | 5b | 1 | 1110_2022 |
| take_on_bounded_least_certain | 5b and 6 | 1 | 1458_2024 |
| least_certain | 6 | 24 | 382_2021, 382_2022, 382_2023, 780_2017, 1176_2019, 1686_2022, 1729_2023, 1910_2018, 1947_2022, 1967_2017, 1967_2018, 2001_2016, 2001_2017, 2232_2017, 2232_2019, 2468_2019, 2468_2020, 2488_2016, 4020_2018, 4141_2022, 4242_2017, 4444_2017, 5000_2023, 6118_2018 |
| stands | 7 | 37 | 382_2017, 382_2020, 435_2016, 510_2015, 1084_2016, 1218_2016, 1274_2022, 1274_2024, 1301_2016, 1416_2024, 1492_2019, 1856_2021, 1880_2015, 1897_2019, 1910_2016, 1945_2016, 1945_2018, 1947_2020, 1955_2023, 1967_2022, 2007_2016, 2015_2022, 2121_2018, 2357_2024, 2623_2023, 2786_2024, 2791_2022, 2988_2020, 3000_2018, 3624_2018, 4444_2022, 4472_2022, 4472_2024, 5000_2018, 5151_2020, 5678_2016, 6107_2023 |

Primary at 35a259c: 649 records. Leaving: the four of rule 1, 3000/2022 (rule 2) and 1110/2022 (rule 5b, after the round-7 readings): 643. Five figures corrected (318/2024, 1274/2016, 1609/2024, 2232/2020, 4242/2022). The 29 records listed under history_restated (the 25 of rule 6, 1458/2024 under rule 5b, 3500/2023 and 3500/2022 under rules 5 and 6, and 1274/2016 under rules 4 and 6) stay and join the least-certain sensitivity.

## Label disagreements settled by the rules

- 382_2021: P1 screen_misread, Q8 valid. Same facts; the rule decides: least_certain (rule 6).
- 382_2022: P4 valid, Q5 restated_base. Same facts; the rule decides: least_certain (rule 6).
- 780_2017: P5 restated_base, Q6 valid. Same facts; the rule decides: least_certain (rule 6).
- 1301_2016: P4 valid, Q5 screen_misread. Same facts; the rule decides: stands (rule 7).
- 1609_2024: P3 valid, Q2 screen_misread, Z5 valid, Z6 screen_misread. Fact disagreement (literal against transposed reading): the tie-break readers Z5 and Z6 both read the body as transposed (+13.935m USD), so rule 4.
- 1686_2022: P6 valid, Q7 restated_base. Same facts; the rule decides: least_certain (rule 6).
- 2121_2018: P6 screen_misread, Q7 valid. Same facts; the rule decides: stands (rule 7).
- 2232_2017: P3 valid, Q4 restated_base. Same facts; the rule decides: least_certain (rule 6).
- 2488_2016: P6 valid, Q5 restated_base. Same facts; the rule decides: least_certain (rule 6).
- 2786_2024: P7 screen_misread, Q6 units_slip. Same facts; the rule decides: stands (rule 7).
- 3000_2016: P4 valid, Q5 restated_base. Same facts; the rule decides: take_on_base_and_least_certain (rule 5 and 6).
- 3500_2022: P6 restated_base, Q7 undeterminable. Same facts; the rule decides: take_on_base_and_least_certain (rule 5 and 6).
- 4444_2017: P1 valid, Q8 restated_base, Z5 restated_base, Z6 restated_base. Fact disagreement on whether the year's flows tie: Z5 and Z6 confirm Q8's facts (restated_base, moderate confidence); rule 1 is not met on a same-table basis (incurred +6.3%, paid +30.8% only as a cross-report proxy), so rule 6.
- 6118_2018: P3 valid, Q4 restated_base. Same facts; the rule decides: least_certain (rule 6).

## 1274/2016: the corrected figure (rule 4)

Both readings quote the same cells of the 2016 table (p41, USD'000): the 2012 column runs 102,670 / 158,484 / 174,440 / 141,355 / 185,418, so its end-2015 cell (141,355) sits between 174,440 and 185,418 and implies a reserve of 12,005 against 47,564 in the 2015 report, whose own 2012 cell is 178,987 (p41). P3 reads it as a misprint 'not correctable from the filing'; Q4 reads it as a misprint and gives the replacement without the exchange factor (+19.871m). Before review 8 the exchange factor was the 2008 column's end-2015 cell over the 2015 report's, 209,137 / 213,518 = 0.979482 (the screen's common factor; the other years run 0.968-0.989). Review 8 changed it: the replaced cell belongs to the 2012 column, so the column's own factor is used, from its paid cells at end-2015, which both readers quote and which the misprint does not touch: 129,350 (2016 table) against 131,423 (2015 report), f = 0.98423.

- corrected 2012 end-2015 cell: 178,987 x 0.98423 = 176,163.7
- 2012 term: 185,418 - 176,163.7 = +9,254.3
- other six years (2008 -681, 2009 +564, 2010 +2,491, 2011 +3,607, 2013 -3,166, 2014 +10,625): +13,440
- M = 13,440 + 9,254.3 = +22,694.3, i.e. +22.6943m USD (GBP 18.395m at the loader's rate), against +57.503m as printed and +23.5435m before review 8 (the 2008 column's factor)
- check: the table's implied incurred with the corrected cell is 260,042 - 44,063 + 9,254.3 = 225,233.3 against 230,541 in the accounts (-2.3%; the paid test ties at -1.9% either way)
- range: the other columns' end-2015 ratios (0.96766 to 0.98919) as the factor give +21.806m to +25.659m (review 8: +21.8m to +25.6m); no factor (the 2015 cell as printed) gives Q4's +19.871m

The readings support the correction's inputs and the diagnosis (both call the cell a misprint and quote every cell used); neither gives the figure. It is the session's derivation from cells both readers quote, stored apart from the readers' own figures (derived_figure_m; each reading keeps its figure_m, +57.503m as printed), allowed only while both readers quote every cell used and the derivation is recorded. The build recomputes it from each reader's own quoted cells (`build_mature_cohort_figures.misprint_figure`). Because it rests on a choice of factor, 1274/2016 also joins the least-certain list (rule 6, clause derived_correction).

## Rule 1: excluded

### 780_2016 (rule 1: excluded)

- P6 restated_base, M 24.9, paid +79.8 (294.7 vs 163.9) on the own-diagonal identity; the cross-table figure 121.1 is below accounts only because 2010-and-prior is excluded, incurred 5.6
- Q5 restated_base, M 24.9, paid None, incurred 5.6
- Rule 1. History differs, unexplained: every early cell of the 2016 table (p30) is 8-72% below the 2015 print (p28; first-year cells 40-65% lower) and the '2010 & prior' balance to pay rises from 89.5 to 203.2 while the 2011-2015 rows shrink; the only wording is the reconversion of non-dollar claims at 31 December 2016 rates (p29) and a restatement of reinsurance commissions (note 3(j)); no restatement, RITC or change of basis of the table (P6, Q5). Year t fails the accounts: the reserve identity on the table's own end-2015 diagonal implies 294.7m of 2016 gross paid against 163.9m in the accounts (+79.8%, P6, p12); the printed reserves and payments of 2011-2014 give a 2016 movement of -94.5m against +24.9m from the table's cells (Q5). The incurred test (+5.6%) does not discriminate: the '2010 & prior' years carry no cells (both readings). Control ties: control miss +9.5% (over the 5% bar): the 2015 table's implied incurred 110.268m against 100.7m in the 2015 accounts (both readings). Basis reason: the '2010 & prior' years carry no cells in either table, so both years run above the accounts by about the development a favourable '2010 & prior' would remove (Q5); the 2015 table is the base the 2015 balance sheet was struck on (outstanding 348.483 ties). Year t miss: +79.8% (paid, the reserve identity on the table's own end-2015 diagonal, 294.7m against 163.9m, P6, p12), 8.4 times the control's. Rule 1's exact control clause (made exact on 23 October 2026 after review 8): 9.5% is within 10%, the same basis gap explains both years (its incurred miss in year t is +5.6%, the same gap), and 79.8% is at least three times 9.5% (28.5%); met. The year t-1 base does not reconcile: on the 2015 print's cells the 2011-2014 movement is -94.4m against the filing's all-prior-years gross line of -15.6m (p26) and the table's +24.9m: neither base reconciles (P6, Q5). Outcome: excluded (data/restated_base_excluded.json, tag RESTATED_BASE_TABLE).

### 2689_2023 (rule 1: excluded)

- V1 restated_base, M None, paid None, incurred None
- V2 restated_base, M None, paid None, incurred None
- W1 confirmed, M None, paid None, incurred None
- W2 confirmed, M 42.378, paid None, incurred None
- Rule 1. History differs, unexplained: the 2023 table (p46) restates the 2020 and 2021 history: end-2022 cells 123,040 and 97,435 against 81,688 and 77,230 printed in 2022 (p46), earlier diagonals too, under the same heading and basis; neither filing states a restatement, and 2023 has no RITC, transfer or take-on (V1, V2). Year t fails the accounts: implied 2023 gross paid 133.1m against 36.1m (p20); implied incurred 93.9m on the table's own base (155.6m on the 2022 base) against 58.2m (p34) (V1, V2). Control ties: the 2022 table's own movement, +55.9m, against 2022 gross incurred of 56.3m (0.7%, V1); outstanding ties in both years (108,937; 131,452). Rule 1's exact control clause (23 October 2026): within 5%; met. The year t-1 base does not reconcile: on the 2022 printed diagonal the mature movement is about +103.9m, above the year's total gross incurred of 58.2m (V1, V2). Outcome: excluded (data/restated_base_excluded.json, tag RESTATED_BASE_TABLE).

### 4747_2024 (rule 1: excluded)

- P2 restated_base, M -11.116, paid -60.7, incurred -81.9
- Q3 restated_base, M -11.116, paid -60.7, incurred -81.9
- Rule 1. History differs, unexplained: the 2024 table (p48) raises the end-2023 cells of 2022 and 2023 to 24,572 and 34,726 against 17,343 and 7,482 printed in 2023 (p39), lowers the 2020-2021 history by about 6%, and its paid row falls (2020: 4,843 to 213); the only restatement note (p31) concerns the management fee (P2, Q3). Year t fails the accounts: implied incurred 11.2m against 61.9m (-81.9%, note 6 p35); paid 8.7m against 22.1m (-60.7%, p17) (P2, Q3). Control ties: control miss -7.2% (over the 5% bar): the 2023 table's implied incurred 27.9m against 30.1m (both readings), while its outstanding, 38,860, ties exactly to the 2023 balance sheet and the 2024 opening (p35). Basis reason (the session's reading; neither reader names one): the table is cumulative incurred by underwriting year on its own basis, 'not obviously earned or ultimate' (P2: the 2024 first-year cell is 9,151 against 163,404 of gross premiums written), set against the accounts' calendar-year gross incurred, and that difference of basis is the same in 2023 and 2024. Year t miss: -81.9% (incurred, note 6 p35; paid -60.7%, p17), 11.4 times the control's. Rule 1's exact control clause (made exact on 23 October 2026 after review 8): 7.2% is within 10%, and 81.9% is at least three times 7.2% (21.6%); met. The year t-1 base does not reconcile: against the 2023 printed cells the 2024 latest diagonal gives 96,582 - 51,304 = 45.3m against 61.9m (-27%, from the cells both readings quote) and M -4.3m (P2); the 2024 table's end-2023 diagonal less the 2023 paid implies a 72.9m end-2023 reserve against 38.9m (P2): no figure reconciles. Outcome: excluded (data/restated_base_excluded.json, tag RESTATED_BASE_TABLE).

### 6134_2022 (rule 1: excluded)

- P4 restated_base, M 11.563, paid -100, incurred 14.9
- Q5 restated_base, M 11.563, paid None, incurred 14.9
- Rule 1. History differs, unexplained: the 2022 table (p45) drops the 2018 column the 2021 report printed (p44: estimate 25,190, outstanding 22,458) and folds the 2018 year of account into the 2020 column at end-2022 only ('The 2020 amounts above include the 2018 year of account', p45), while its end-2021 cell for 2020 (108,774 = 100,104 x 1.087) does not carry it; the footnote states the fold, not why the history was left unrebuilt; the 2019 24-month cell departs from the retranslation by 2.95m (P4, Q5). Year t fails the accounts: implied incurred 73.7m against 64.1m (+14.9%, p19, p33); the payments row (2,869 in all) does not move with the 22.1m of gross claims paid (P4, Q5). Control ties: the 2021 table: 82.7m against 82.0m (+0.9%, P4, Q5). Rule 1's exact control clause (23 October 2026): within 5%; met. The year t-1 base does not reconcile: the 2021 report's cells give no 2022 movement for the 2018 year folded into the 2020 column, whose movement is in no printed column (Q5); P4's like-for-like -15.8m is an inference, not a printed cell. Outcome: excluded (data/restated_base_excluded.json, tag RESTATED_BASE_TABLE).

## Rule 2: excluded under the author's rule B

### 3000_2022 (rule 2: excluded)

- P2 restated_base, M 112.626, paid -13.3, incurred 11.0
- Q1 restated_base, M 112.626, paid -13.3, incurred 11.0
- Both readings: the 2022 table's end-2021 incurred and cumulative paid are both lifted by the same amount in every column (2013: +20,536 on each; P2 and Q1), so the paid history is retranslated (about 8%) and the end-2021 reserves are not, and (end-2022 less end-2021) mixes exchange bases; the gross roll-forward prints 'Movement due to foreign exchange 91,879' on an opening 1,146,474 (note 17, p42; balance sheet p25): 8.01% of R. Neither filing explains the history. Rule 2 decides before rule 1. Outcome: excluded (data/fx_untranslated_excluded.json).

## Rules 3 and 4: corrected

### 318_2024 (rule 4: corrected)

- P5 screen_misread, M -27.99, paid 2.3, incurred 4.4
- Q4 screen_misread, M -27.99, paid None, incurred 4.4
- Rule 4. Cause: the 2024 gross table's body is printed transposed against its labels (p69): each printed row is one underwriting year, as the 2023 report's columns show at a uniform 1.0097-1.0137 retranslation. Derivation: u <= 2022 read by rows (one underwriting year per row), latest less end-2023 cell: both readers give -27.990m; the table read by its printed column labels gives -67.098m. Outcome: corrected from -67.098 to -27.99 (report currency, GBP), data/mature_cohort_figures.json, displaced.by printed_table_error.

### 1274_2016 (rule 4 and 6: corrected_least_certain)

- P3 valid, M 57.503, paid -1.9, incurred 12.8
- Q4 valid, M 57.503, paid -1.9, incurred 12.8
- Rule 4. Cause: a misprinted cell: the 2016 table's 2012 column prints 141,355 at three years later between 174,440 and 185,418 (p41), a reserve of 12,005 against 47,564 in the 2015 report, whose own cell is 178,987; both readers read it as a misprint, which the filing does not correct. Derivation: DERIVED by the decision of the Claude analysis session, 23 October 2026 (after review 8); not a figure either reader gives. The 2015 report's 2012 cell (178,987) replaces the misprinted 141,355 at the 2012 column's own exchange factor: its paid cells at end-2015, 129,350 in the 2016 table against 131,423 in the 2015 report (the 2012 column's paid history is a retranslation of cells the misprint does not touch), f = 129,350 / 131,423 = 0.98423. Corrected cell 178,987 x f = 176,163.7; the 2012 term is 185,418 - 176,163.7 = +9,254.3; M = +13,440 (the other six years) + 9,254.3 = +22,694.3, i.e. +22.6943m USD. Every cell used is quoted by both readers (P3, Q4) and the build recomputes the figure from each reader's own quoted cells. Each reader's own figure is kept as given: +57.503m as printed (both), P3 calling the cell not correctable from the filing, Q4 giving +19.871m with the 2015 report's cell unretranslated. Other defensible factors (the ratio of any other column's end-2015 cell to the 2015 report's, 0.96766 to 0.98919) give +21.806m to +25.659m (review 8: +21.8m to +25.6m); the 2008 column's factor 0.97948 gives +23.5435m, the figure this register carried before review 8. Outcome: corrected from 57.503 to 22.6943 (report currency, USD), data/mature_cohort_figures.json, displaced.by printed_table_error.

### 1609_2024 (rule 4: corrected)

- P3 valid, M -0.185, paid -0.6, incurred -1.2
- Q2 screen_misread, M 13.935, paid -0.6, incurred None
- Z5 valid, M 13.935, paid None, incurred None
- Z6 screen_misread, M 13.935, paid None, incurred None
- Rule 4. Cause: the 2024 gross table's row and column labels are swapped against its body (p51): each printed row is one underwriting year, as the 2023 report's columns show cell for cell at 0.984-0.991; the tie-break readers Z5 and Z6 settle the disagreement of P3 (literal reading) and Q2. Derivation: u <= 2022 read by rows: 2021 57,359 - 43,731 = +13,628; 2022 107,543 - 107,236 = +307; +13.935m USD (Z5, Z6, Q2); read by the printed labels, -0.185m (P3, superseded). Outcome: corrected from -0.185 to 13.935 (report currency, USD), data/mature_cohort_figures.json, displaced.by printed_table_error.

### 2232_2020 (rule 3: corrected)

- P7 restated_base, M 55.227, paid None, incurred 31.1
- Q8 restated_base, M 55.227, paid -1.7, incurred 31.1
- Rule 3. Cause: the 2020 table's end-2019 diagonal is restated 44.7m below the 2019 report's printed cells with no stated reason, and the table taken on its own implies gross incurred 31% above the accounts (190.0m against 144.9m), the 2019 control tying; the 2019 report's printed cells as the base reproduce the 2020 accounts within 0.3% (incurred) and 1.7% (paid). Derivation: u <= 2018, the 2020 table's latest cells less the 2019 report's printed latest cells: 2013 -926; 2014 +453; 2015 +6,174; 2016 -6,209; 2017 +3,950; 2018 +15,889; +19.331m (both readers); the 2020 table's own end-2019 cells give +55.227m. Outcome: corrected from 55.227 to 19.331 (report currency, GBP), data/mature_cohort_figures.json, displaced.by previous_report_base.

### 4242_2022 (rule 3: corrected)

- P4 restated_base, M -44.371, paid -19.6, incurred 47.0
- Q3 restated_base, M -44.371, paid -19.6, incurred 47.0
- Rule 3. Cause: the 2022 table (p44) lowers the end-2021 cells of 2019 and 2020 (204,999 and 277,405 against 207,954 and 310,094 printed in 2021, p46), -35.9m on the 2017-2021 diagonal of a dollar table that is not retranslated, with no explanation in either filing (the loss-funds reclassification, p38, gives no amount); the table taken on its own implies gross incurred 115.1m against 78.3m in the accounts (+47%), the 2021 control tying (-1.1%). The 2021 report's printed cells as the base reproduce the year's accounts once the merged '2016 & Prior' column, which both readers call unreadable as a cohort (P4: its cumulative paid falls 17.7m, 'no payment can do'; Q3: not like for like, not measurable), is set aside: 79.255m on the 2017-2022 columns against 78.306m (+1.2%, Q3), and 78.9m against 78.3m (+0.8%, review 8). M (u <= 2020) does not use the merged column on either base. Decision of the Claude analysis session, 23 October 2026, after review 8: rule 3, not rule 1 (the year t-1 base reconciles). Derivation: u <= 2020, the 2022 table's latest cells less the 2021 report's printed latest cells: 2017 331,324-349,613 = -18,289; 2018 233,193-249,006 = -15,813; 2019 187,713-207,954 = -20,241; 2020 284,422-310,094 = -25,672; -80,015 (USD 000), i.e. -80.015m USD (both readers); the 2022 table's own end-2021 cells give -44.371m. Outcome: corrected from -44.371 to -80.015 (report currency, USD), data/mature_cohort_figures.json, displaced.by previous_report_base.

## Rule 5: take-on bases

### 1110_2022 (rule 5b: take_on_unmeasurable)

- P7 restated_base, M 9.082, paid None, incurred -60.1
- Q6 restated_base, M 9.082, paid None, incurred -60.1
- U1 (round 7, the transferred gross amount): not printed; opening R 221.885, closing 489.603
- U2 (round 7, the transferred gross amount): not printed; opening R 221.885, closing 489.603
- RITC of Syndicate 5678's 2018 and 2019 years of account and the Hiscox ADC in 2022 (p5, p33), the history carried as if always (2017 column x5.98, 2019 x2.09); R is the opening 221.885m alone. The accounts book the RITC and ADC through premium and claims incurred (353.8m) with no transfer line, and neither round-5 reading prints the transferred gross amount (P7's 'about 270m' is the change in the balance sheet, an inference). Round 7 (brief_r7.md, readings U1, U2; 23 October 2026) read the filing for the amount: it is not printed (the gross roll-forward, p27, has no transfer row), the Hiscox ADC is INWARD (the Gibson Re quota share is outward and moves the reinsurers' share only), reserves rise from 221.885m to 489.603m and gross written premium from 1.366m to 333.442m; U2 derives a take-on of about 221.9m less the unknown development on the opening book, about 100% of R. Rule 5b: the acquired share could exceed 10% of R by a wide margin, so the record leaves the primary as an unmeasurable take-on (data/restated_base_excluded.json, bucket takeon_unmeasurable, tag TAKEON_BASE_UNMEASURABLE; the existing data/takeon_not_development.json does not fit: its entries describe the step of a displaced mature-cohort figure and apply under a figure_route this record's own triangle figure does not have).

### 1458_2024 (rule 5b and 6: take_on_bounded_least_certain)

- P1 units_slip, M -33.258, paid None, incurred -5.3
- Q8 units_slip, M -33.258, paid 20.1, incurred -5.3
- U1 (round 7, the transferred gross amount): not printed; opening R 2050.58, closing 2149.704
- U2 (round 7, the transferred gross amount): not printed; opening R 2050.58, closing 2149.704
- a stated external RITC 'in the year' of the 2020 and 2021 underwriting years shown in the history (p47); note 4's roll-forward (p31) has no RITC line and neither round-5 reading gives the amount (P1: +164m of restated incurred history, not reserves). Round 7 (U1, U2; 23 October 2026): the amount is not printed; the only ADC is outward and dated 2020; R (USD 2,050.580m, GBP 1,637.71m) is the filing's opening and holds no acquired reserves. The filing bounds the take-on: the acquired cumulative incurred at the latest comparable ages is USD 164.078m (+105.138m on the 2020 column, +58.940m on the 2021 column), and the reserves taken on cannot exceed it: at most 8.0% of R. The table carries the acquired years as if always, so the movement within it (-33.258m USD = -26.56m GBP, u <= 2022, equal to the analysis figure) excludes the take-on. Rule 5b: bounded at or below 10% of R, so the record stays and joins the least-certain list (data/restated_base_excluded.json, history_restated, clause take_on_base_bounded).

### 1686_2021 (rule 5: take_on_base)

- P1 valid, M 105.521, paid None, incurred 0.26
- Q2 valid, M 105.521, paid None, incurred None
- RITC of Syndicates 2007 and 6129 into the 2019 year of account, effective 1 January 2021, shown as if always in the 2016-2018 columns (p6, p9; p25 'Effect of RITC 903,214'); the table ties (incurred +0.26%, control +3.7%). The analysis's R is 2,076.819m USD = 1,173.605 + 903.214 (take-on base register): R already includes the transfer, nothing changes.

### 1856_2024 (rule 5: take_on_base)

- P2 valid, M 140.888, paid 71.9, incurred -3.8
- Q1 valid, M 140.888, paid None, incurred -3.8
- RITC of Syndicate 3268 effective 1 January 2024, its data in the pre-2022 periods (p63; note 13 p101 'RITC from Syndicate 3268 96,610'); the table ties (incurred -3.8%). R is 696.978m = 600.368 + 96.61: already includes it.

### 1884_2021 (rule 5: take_on_base)

- P3 valid, M -20.1, paid None, incurred None
- Q2 valid, M -20.0, paid None, incurred None
- RITC of the 2018 years of account of Syndicates 1861 and 1955 effective 1 January 2021, as if always (p4, p33); the closing reserve ties. R is 913.496m = 73.709 + 839.787: already includes it.

### 2488_2019 (rule 5: take_on_base)

- P7 valid, M -2.959, paid None, incurred None
- Q8 valid, M -2.959, paid None, incurred -3.8
- RITC of Syndicate 1882 effective 1 January 2019, its data in the earlier periods (p49, p7; 143.8m gross); incurred -3.8%. R is 1,100.269m = 956.51 + 143.759: already includes it.

### 3000_2016 (rule 5 and 6: take_on_base_and_least_certain)

- P4 valid, M 27.325, paid -33.4, incurred None
- Q5 restated_base, M 27.325, paid -33.4, incurred None
- RITC of Syndicate 1400's 2013 year of account accepted 1 January 2016, the table restated as if always and revalued (p38; p37 'RITC accepted from Syndicate 1400 248,822'). R is 986.744m = 737.922 + 248.822: already includes it. P4 valid, Q5 restated_base on the same facts: rule 6's label clause also lists it.

### 3500_2022 (rule 5 and 6: take_on_base_and_least_certain)

- P6 restated_base, M -291.8, paid n/a (same-table not printed); cross-table +4.0 but not like-for-like; identity-based +26.5, incurred table -26.4m vs -293.1m: does not tie (gap 266.7m); mature columns only (2013-2019) -291.8m vs -293.1m: 0.4% apart
- Q7 undeterminable, M -291.756, paid None, incurred None
- RITCs of Syndicates 1897, 2468, 1980/2014/2001 effective 1 January 2022 and LPTs in 2022 (p4; note 7 p30 'Reinsurance of new liabilities 1,728,476'), the history re-bucketed with them. R is 3,955.045m USD = 2,615.345 + 1,339.7 (the 1 January RITCs; the amount is the ninth census's decision). The mature columns move -291.8m against note 7's change in estimates incl. FX of -293.1m (0.4%, P6). P6 restated_base, Q7 undeterminable: the same validity class. Rule 5 changes nothing. After review 8 (decision of the Claude analysis session, 23 October 2026) it joins 3500/2023 on the least-certain list under the rule-6 clause take_on_table_unreconciled, on the same all-prior-years scope: the table's movement on every column that existed at end-2021 (2013-2019 and 2021) is -291.756m - 98.057m = -389.8m against note 7's -293.1m, and the whole table is -26.4m, a gap of 266.7m (P6, Q7); only the 2013-2019 columns alone tie (0.4%). The readings conflict on the loss portfolio transfers: P6 reads the mid-2022 LPTs of Syndicates 1200 and 1686 (293.8m and 67.1m) as entering the history as if always, the ninth census (data/opening_reserves_takeon_base.json) places all four LPTs (388.7m) in the 2022 column, outside M and R. Either way the acquired share outside R is at most 9.1% of R (360.9m of 3,955.0m; 9.8% with all four), so rule 5b would list it too (data/restated_base_excluded.json, history_restated).

### 3500_2023 (rule 5 and 6: take_on_base_and_least_certain)

- P7 restated_base, M -47.666, paid None, incurred None
- Q8 restated_base, M -47.666, paid 759, incurred n/a: neither 136.6m nor -62.3m ties
- RITCs of seven syndicates and an LPT effective 1 January 2023 (p5, p30-31; note 7 'Reinsurance of new liabilities 3,225,818'), the history 2-3.6 times the 2022 report's. R is 5,803.136m USD = 2,962.436 + 2,840.7 (the register's amount leaves out the 201.9m LPT already in the opening and the 183.2m LPT). Rule 5 changes nothing. The table's movement does not tie to note 7's change in estimates (-52.1m for u <= 2022 against -184.8m, P7; Q8: neither ties); rule 1 does not reach it (the history change is explained) and no rule covered an explained take-on table that fails the tie. Round 7 (23 October 2026): it stays in the primary and joins the least-certain list, under the rule-6 clause take_on_table_unreconciled (data/restated_base_excluded.json, history_restated).

### 4000_2022 (rule 5: take_on_base)

- P5 valid, M 29.53, paid None, incurred 3.2
- Q6 valid, M 29.53, paid None, incurred 3.2
- RITC of Syndicate 3334 effective 1 January 2022, the 2019 column as if always (p5); the table ties (incurred +3.2%, control +1.1%). R is 555.661m = 374.414 + 181.247: already includes it.

### 4444_2018 (rule 5: take_on_base)

- P5 valid, M 88.583, paid None, incurred 6.1
- Q4 valid, M 88.583, paid 94.0, incurred 6.1
- RITC of Syndicate 958's 2015 year of account effective 1 January 2018, as if always; the balance to pay ties (1,949,555); incurred +6.1% on an ultimate basis. R is 1,824.548m = 1,547.219 + 277.329: already includes it.

### 4444_2023 (rule 5: take_on_base)

- P3 screen_misread, M 48.207, paid None, incurred -2.6
- Q2 screen_misread, M 48.207, paid None, incurred None
- screen misread (end-2021 cells read as end-2022); 2019 and 2020 rebased x1.7 and x1.5 by the stated RITC of Syndicate 1861's 2020 year of account from 1 January 2023 (gross provision +313,953). R is 2,681.837m = 2,367.884 + 313.953: already includes it.

## Rule 6: least certain, stays

### 382_2021 (rule 6: least_certain)

- P1 screen_misread, M 20.409, paid None, incurred -8.7
- Q8 valid, M 20.409, paid None, incurred -8.7
- Rule 6 (unexplained_history_move): UY2014's end-2020 cell in the 2021 table (187,147) is 10.3m above the 2020 report's printed estimate and out of line with its own column (169,537 -> 187,147 -> 170,900), unexplained in the filing (P1, Q8): 2.1% of R (498.1m). The rest moves by the stated retranslation; the table ties to the balance sheet and its incurred gap (-8.7%) is the 2020 control's (-6.9%), the pre-2011 years outside the table. M as printed (+20.409m) stands. Rule 1 under the exact control clause (23 October 2026, review 8): not met. The control miss is -6.9% (over 5%, within 10%, the same pre-2011 years outside the table in both years), but the year t miss, -8.7%, is 1.3 times the control's, not three times, and is itself under 10%. The record stays least certain. Outcome: stays in the primary, listed under history_restated.

### 382_2022 (rule 6: least_certain)

- P4 valid, M 34.169, paid None, incurred 2.1
- Q5 restated_base, M 34.169, paid None, incurred 2.1
- Rule 6 (unexplained_history_move, label_disagreement): the 2018 column's end-2021 cell moved against the common 1.09 retranslation (ratio 0.959; 34.2m, 6.9% of R 498.1m), unexplained (p44 states only the all-years retranslation at 2022 closing rates; P4, Q5). The table ties: implied incurred 236.1m against 231.25m (+2.1%, p16) and outstanding 631,136 to the balance sheet. P4 valid, Q5 restated_base on the same cells. Outcome: stays in the primary, listed under history_restated.

### 382_2023 (rule 6: least_certain)

- P8 valid, M -7.893, paid None, incurred -8.1
- Q1 valid, M -7.893, paid -15.7, incurred -8.1
- Rule 6 (unexplained_history_move): the end-2022 cells of 2016, 2019 and 2020 sit 2.8%, 2.8% and 7.1% above the 2022 report's latest in a year sterling strengthened, against 0.95-0.99 for the other years (10.9m, 8.8m and 13.1m beyond the common factor; 1.4-2.1% of R 631.1m), and the early rows were rebuilt beyond the stated retranslation (P8: 2016 first year 88,722 against 72,750); p44 states only the closing-rate retranslation (P8, Q1; Q1 attributes the moves to it). Incurred -8.1% with UY <= 2012 outside the table (control +2.1%); outstanding ties. Rule 1 does not apply: incurred is within its 10%, and the paid -15.7% (Q1) is a cross-report proxy because the 2023 table prints no end-2022 payments (P8, Q1). Outcome: stays in the primary, listed under history_restated.

### 780_2017 (rule 6: least_certain)

- P5 restated_base, M -1.6, paid 5.8, incurred 8.4
- Q6 valid, M -1.6, paid 5.8, incurred 8.4
- Rule 6 (unexplained_history_move, label_disagreement): the 2017 table's end-2016 estimates are 165.6m (24.6%) above the 2016 report's, mirrored by a -170.4m fall in the '2010 & prior' balance to pay, with only the generic reconversion sentence (p30) (P5, Q6); 2011, 2012 and 2015 move 59.2m, 17.8m and 16.1m beyond the common factor (5-19% of R 313.8m). Implied incurred 279.0m against 257.3m (+8.4%, control +5.6%) and cross-report paid +5.8%: within rule 1's 10%, so rule 1 does not apply. P5 restated_base, Q6 valid. Outcome: stays in the primary, listed under history_restated.

### 1176_2019 (rule 6: least_certain)

- P2 valid, M -8.44, paid -0.4, incurred None
- Q1 valid, M -8.44, paid -0.4, incurred None
- Rule 6 (unexplained_history_move): the 2011 column's end-2018 cell is 17,001 against 14,924 in the 2018 report, 2.1m (5.2% of R 39.7m), unexplained (P2, Q1). Paid ties (2,904 against 2,915) and reserves tie. Outcome: stays in the primary, listed under history_restated.

### 1686_2022 (rule 6: least_certain)

- P6 valid, M -21.4, paid -0.0005 on the bridge (746,797 vs 746,801); cross-table -23.4% (571,795), which is the unexplained history cut, incurred -9.5
- Q7 restated_base, M -21.386, paid None, incurred -9.5
- Rule 6 (unexplained_history_move, label_disagreement): the 2016-2018 history is cut by 175.0m in both incurred and paid (reserve-neutral) with 2019-2021 untouched, unexplained (p32 states only balance-sheet-rate translation; P6, Q7): 8.1% of R (2,167.2m). Implied incurred is 9.5% below the accounts, the gap equal to the stated FX line (72,783, note 4 p24) to within 5k (both readings): the basis explains it; control +0.3%. Not a year t take-on: the RITC of Syndicates 2007 and 6129 is of 1 January 2021 and in R, the 1 December 2022 LPR is ceded. P6 valid, Q7 restated_base. Outcome: stays in the primary, listed under history_restated.

### 1729_2023 (rule 6: least_certain)

- P7 valid, M 16.766, paid None, incurred -0.4
- Q6 valid, M 16.766, paid 34.1, incurred -0.4
- Rule 6 (unexplained_history_move): UY2021's end-2022 estimate is 58.3m USD above the 2022 report's at the common presentation factor (17.1% of R), unexplained in the filing (P7, Q6; Q6 judges the 2022 print faulty, which the filing does not say). The 2023 table ties (incurred -0.4%). Rule 1 under the exact control clause (23 October 2026, review 8): not met. The year t incurred ties (-0.4%); the cross-table paid (+35%, P7; +34.1%, Q6) comes, P7 shows, entirely from the restated UY2021 column, and the control does not tie under either bound (-27.3%, Q6; about -29%, P7). The record stays least certain. Outcome: stays in the primary, listed under history_restated.

### 1910_2018 (rule 6: least_certain)

- P8 valid, M 1.9, paid 12.4, incurred 5.3
- Q7 valid, M 2.01, paid None, incurred 5.3
- Rule 6 (unexplained_history_move): the 2016 column was lowered (end-2017 73.0 against 76.5, ratio 0.954) while the other years rose 2.5-5.6% by the stated retranslation, unexplained (Q7: 'not explained anywhere'; P8): 6.8m, 2.1% of R (322.1m). The table ties to the provision; incurred +5.3% on an ultimate basis (control -3.8%). Rule 1 does not apply: the paid +12.4% (P8; +6.3% with the 2017 paid retranslated) is a cross-report proxy because the 2018 table prints no end-2017 payments (P8; Q7: not computable). Outcome: stays in the primary, listed under history_restated.

### 1947_2022 (rule 6: least_certain)

- P2 valid, M -14.449, paid 20.8, incurred -0.5
- Q3 valid, M -14.449, paid 20.8, incurred -0.5
- Rule 6 (unexplained_history_move): the 2018 column (oldest) is about 14% above the year's retranslation ratio at every age (about 4.3m, 3.7% of R 116.5m), unexplained (P2, Q3). Incurred ties (-0.5%, control +0.8%). Rule 1 does not apply: the paid +20.8% (P2, Q3) is a cross-report proxy because the 2022 table prints no end-2021 payments (Q3). Outcome: stays in the primary, listed under history_restated.

### 1967_2017 (rule 6: least_certain)

- P5 valid, M 11.417, paid 1.7, incurred 4.0
- Q6 valid, M 11.417, paid 55.2, incurred 4.0
- Rule 6 (unexplained_history_move): the whole 2011-2016 history, estimates and payments alike, is 6-16% above the 2016 report with no retranslation or restatement statement (P5, Q6); 2015 moves 5.7m beyond the common factor (3.5% of R 165.2m). The table ties (+4.0% incurred, reserves exact). Rule 1 under the exact control clause (23 October 2026, review 8): not met. The year t table does not fail the accounts: incurred +4.0% and P5's reserve-identity paid test +1.7% (the like-for-like test used for 780/2016); Q6's cross-report paid +55.2% is the proxy that the restated history itself distorts. The control miss is -7.6% (Q6), over 5% and within 10%. The record stays least certain. Outcome: stays in the primary, listed under history_restated.

### 1967_2018 (rule 6: least_certain)

- P6 valid, M 31.2, paid -2.1 on the bridge; cross-table -17.4 (restated paid history, e.g. UY2011 cumulative paid 85,816 -> 109,154), incurred -4.5
- Q7 valid, M 31.226, paid None, incurred -4.5
- Rule 6 (unexplained_history_move): the 2011 column (oldest) is 26% higher between reports while the others are 3-9% lower (retranslation), unexplained (P6, Q7): 28.9m, 11.8% of R (246.1m). Incurred ties (-4.5%, control +4.0%). Outcome: stays in the primary, listed under history_restated.

### 2001_2016 (rule 6: least_certain)

- P6 valid, M 88.1, paid n/a (cross-table 951.7 vs 831.3 = +14.5%, not a valid like-for-like test), incurred 3.1
- Q7 valid, M 88.1, paid None, incurred 3.1
- Rule 6 (unexplained_history_move): UY2013 and UY2014 fall at end-2015 against an exchange uplift (P6: unexplained; Q7: the 2013-2015 columns look mis-allocated, the 2017 report re-allocates them); the stated basis is year-end conversion (p35). Incurred ties (+3.1%, control +4.8%). Share of R, checked after review 8 against rule 6's 1% of R (opening gross claims outstanding 1,601.0m, note 9(a), so 16.01m): the 2016 table's end-2015 cells are 761.5 (UY2013) and 804.7 (UY2014) against 786.4 and 821.4 in the 2015 report, falls of 24.9m (1.56% of R) and 16.7m (1.04% of R), 41.6m together (2.60%), both cells that the exchange uplift (ratios 1.016, 1.074, 0.968, 0.980 for UY2011-UY2014, no common factor) should have raised, so the move beyond the exchange rate is at least the fall; P6's own measure, about 2% of the year's gross incurred (1,089.5m), is 21.8m or 1.4% of R. Every measure is over 1% of R: rule 6 is met and the record stays on the list (decision of the Claude analysis session, 23 October 2026). Outcome: stays in the primary, listed under history_restated.

### 2001_2017 (rule 6: least_certain)

- P8 valid, M 111.3, paid -13.1, incurred -4.4
- Q7 valid, M 111.3, paid None, incurred -4.4
- Rule 6 (unexplained_history_move): the end-2016 history is re-allocated across 2013 (+11.9%), 2014 (+9.7%) and 2015 (-21.1%) beyond the stated year-end conversion (p33), with no explanation (P8, Q7). Incurred ties (-4.4%, control +3.1%). Rule 1 does not apply: the paid -13.1% (P8) is a cross-report proxy because the 2017 table prints no end-2016 payments (P8; Q7: not computable). Outcome: stays in the primary, listed under history_restated.

### 2232_2017 (rule 6: least_certain)

- P3 valid, M 12.763, paid -20.1, incurred -10.5
- Q4 restated_base, M 12.763, paid -20.1, incurred -10.5
- Rule 6 (label_disagreement): the mature years' end-2016 cells equal the 2016 report's latest exactly while their earlier cells were retranslated about -7% (P3, Q4); Q4 reads a mixed currency base, P3 a valid table. The flows miss (incurred -10.5%, cross-report paid -20.1%) and the control does not tie within 5% (P3 incurred +7.4%; Q4 paid +62.1%, confounded), so rule 1 does not apply; no exchange line is reported, so rule 2 cannot be tested. Rule 1 under the exact control clause (23 October 2026, review 8): not met. The control miss is +7.4% (P3 incurred), within 10% with a basis that is the same in both years (an ultimate underwriting-year table against earned accounts, Q4), but the year t miss is not three times the control's (22.2%): incurred -10.5% is 1.4 times it and the cross-report paid -20.1% 2.7 times it; the control's sign (table above the accounts, as the basis predicts) is the opposite of the year t miss's (below), so the basis gap does not explain the year t miss either; Q4's paid control +62.1% is confounded (the 2015 report's cells are 19% lower than the 2016 report's for the same year). The record stays least certain. P3 valid, Q4 restated_base. Outcome: stays in the primary, listed under history_restated.

### 2232_2019 (rule 6: least_certain)

- P5 valid, M 12.79, paid -0.8, incurred -3.3
- Q6 valid, M 12.79, paid -0.8, incurred -3.3
- Rule 6 (unexplained_history_move): the 2013 column (oldest) is 6.3% higher between reports with no wording, in tables translated at each year's own end rate, so no retranslation moves history (Q6; P5): 4.5m, 1.2% of R (373.2m). The table ties (paid -0.8%, incurred -3.3%). Outcome: stays in the primary, listed under history_restated.

### 2468_2019 (rule 6: least_certain)

- P5 valid, M 45.776, paid -3.0, incurred -3.0
- Q4 valid, M 45.776, paid -3.0, incurred -3.0
- Rule 6 (unexplained_history_move): the end-2018 estimates and paid of UY2016 and UY2017 are re-allocated (about +17m each, +15.7% and +4.6% on the diagonal), unexplained (P5, Q4); 2016 moves 10.4m beyond the common factor (3.1% of R 337.0m). The table ties (paid -3.0%, incurred -3.0%). Outcome: stays in the primary, listed under history_restated.

### 2468_2020 (rule 6: least_certain)

- P1 valid, M 71.205, paid -4.3, incurred -3.8
- Q2 valid, M 71.205, paid -4.3, incurred None
- Rule 6 (unexplained_history_move): UY2016 (oldest, closed) history is 16.5-18.6m lower in estimate and paid alike, unexplained (P1, Q2): 4.2% of R (389.0m). The table ties (paid -4.3%, incurred -3.8%). Outcome: stays in the primary, listed under history_restated.

### 2488_2016 (rule 6: least_certain)

- P6 valid, M -26.8, paid -3.3 with the factor (remainder is paid on 2010-and-prior years); unadjusted +29.9, incurred 59.5
- Q5 restated_base, M -26.755, paid None, incurred 59.5
- Rule 6 (unexplained_history_move, label_disagreement): the 2011 column's end-2015 estimate is 28.9-29.3m above the 2015 report at the stated 1.165 retranslation, unexplained (P6, Q5): 3.2% of R (916.3m). The paid bridge ties (-3.3%, -2.9%); incurred +59.5% against a +38.3% control, the 2010-and-prior years outside the table. Rule 1 under the exact control clause (23 October 2026, review 8): not met. The control miss is +38.3%, over 10%, so the control ties under neither bound (the same 2010-and-prior gap makes the year t incurred test uninformative, P6, Q5); the year t incurred miss, +59.5%, is 1.6 times the control's, not three times; and the year t paid test ties (-3.3% with the factor, P6; -2.9%, Q5). The record stays least certain. P6 valid, Q5 restated_base. Outcome: stays in the primary, listed under history_restated.

### 4020_2018 (rule 6: least_certain)

- P5 valid, M 43.863, paid None, incurred 4.0
- Q6 valid, M 43.863, paid None, incurred 4.0
- Rule 6 (unexplained_history_move): the history is re-spread across underwriting years without explanation (2012 -20.3m, 2013 +36.0m, 2014 -23.1m between reports, P5; Q6: re-allocations inside a near-constant total), each above 1% of R (497.3m). The table ties (+4.0%, control +7.2% on the underwriting-year basis). Outcome: stays in the primary, listed under history_restated.

### 4141_2022 (rule 6: least_certain)

- P8 valid, M -16.697, paid 1.0, incurred -2.9
- Q1 valid, M -16.697, paid 1.0, incurred -2.9
- Rule 6 (unexplained_history_move): a 24.7m cross-year move between UY2018 and UY2019 on the end-2021 diagonal, sum-preserving and unexplained (P8, Q1): 9.9% of R (248.5m) each. The table ties (-2.9%, control +0.3%). Outcome: stays in the primary, listed under history_restated.

### 4242_2017 (rule 6: least_certain)

- P8 valid, M 0.816, paid -5.9, incurred -2.0
- Q1 valid, M 0.816, paid -5.9, incurred -2.0
- Rule 6 (unexplained_history_move): the 2011 column's history is lowered by about 1.4m between reports, unexplained (P8, Q1): 4.3-4.5% of R (30.7m). The table ties (-2.0%, control -0.6%). Outcome: stays in the primary, listed under history_restated.

### 4444_2017 (rule 6: least_certain)

- P1 valid, M 118.224, paid None, incurred 6.3
- Q8 restated_base, M 118.224, paid 30.8, incurred 6.3
- Z5 restated_base, M None, paid None, incurred None
- Z6 restated_base, M 118.224, paid 30.8, incurred None
- Rule 6 (unexplained_history_move, label_disagreement): the end-2016 cells of 2011, 2012 and 2013 sit 4.7%, 4.7% and 3.9% above the 2016 report (16.1m, 16.7m, 14.2m; 1.2-1.4% of R 1,200.6m each; +40.7m on the 2011-2016 diagonal) in a year sterling strengthened against the dollar, unexplained (Q8, Z5, Z6; p25 states only year-end rates). Rule 1 does not apply: on the table's own base implied incurred is +6.3% (control -1.1%), within its 10%, and the paid +30.8% is a cross-report proxy because the 2017 table prints no end-2016 payments (Z6). P1 valid; Q8 restated_base; the tie-break readers Z5 and Z6 confirm the facts (restated_base, moderate confidence). M as printed (+118.224m) stands. Outcome: stays in the primary, listed under history_restated.

### 5000_2023 (rule 6: least_certain)

- P4 valid, M 14.7, paid -7.2, incurred 3.0
- Q3 valid, M 14.7, paid -7.2, incurred 3.1
- Rule 6 (unexplained_history_move): the 2014 column (oldest) from two years later onward sits about 9.7-9.8m above the translated 2022 values, unexplained (P4, Q3): 1.2% of R. The table ties (incurred +3.0%). Outcome: stays in the primary, listed under history_restated.

### 6118_2018 (rule 6: least_certain)

- P3 valid, M 7.579, paid None, incurred -2.0
- Q4 restated_base, M 7.579, paid -72.7, incurred 9.5
- Rule 6 (unexplained_history_move, label_disagreement): the 2014 column's end-2017 cell is 21,267 against 101,239 in the 2017 report (about 80m, 44% of R 183.4m), unexplained in either filing (P3 gives the context of the 2014 year's closure into Syndicate 1955; Q4: unexplained). Incurred -2.0% raw (P3), +9.5% earned-equivalent (Q4): within rule 1's 10%. The paid -72.7% (Q4) is a cross-report proxy because the 2018 table prints no end-2017 payments, only an end-2018 total rolled from the 2017 report's (P3, Q4), and that total's scope shrank with the 2014 column (Q4). P3 valid, Q4 restated_base. Outcome: stays in the primary, listed under history_restated.

## Rule 7: stands

### 382_2017 (rule 7: stands)

- P7 screen_misread, M 7.401, paid None, incurred None
- Q6 screen_misread, M 7.401, paid 2.9, incurred 0.5
- Rule 7: screen misread: it compared balance-sheet pages and read an incremental table as levels (no identity evidence); M from the printed increments +7.401m equals the analysis figure (P7, Q6).

### 382_2020 (rule 7: stands)

- P8 screen_misread, M 29.62, paid None, incurred -6.9
- Q7 screen_misread, M 29.62, paid None, incurred -6.9
- Rule 7: screen misread (incremental table, wrong pages); the end-2019 history differs by the stated closing-rate retranslation (-1.6% to -5.7%); the re-cut of the first two rows and UY2019 are outside M; M +29.62m.

### 435_2016 (rule 7: stands)

- P1 screen_misread, M -44.233, paid None, incurred 36.1
- Q8 screen_misread, M -44.233, paid -19.0, incurred 36.1
- Rule 7: screen misaligned (end-2014 cells); aligned, the history is the 2015 report's times a uniform 1.12-1.19, the stated December-2016 retranslation (+15.2% on opening); M -44.233m.

### 510_2015 (rule 7: stands)

- P3 screen_misread, M 0.1, paid None, incurred 4.8
- Q4 screen_misread, M 0.1, paid None, incurred 4.8
- Rule 7: screen compared the 2015 gross table with the 2014 net table (no 2014 gross table); incurred +4.8%; M +0.1m.

### 1084_2016 (rule 7: stands)

- P3 valid, M 3.4, paid -9.6, incurred 8.9
- Q2 valid, M 3.4, paid None, incurred None
- Rule 7: the only flagged year is u = 2015 (t-1, outside M); mature years 1.03-1.075 (translation); M +3.4m.

### 1218_2016 (rule 7: stands)

- P1 screen_misread, M -8.941, paid None, incurred 50.6
- Q2 screen_misread, M -8.941, paid None, incurred None
- Rule 7: screen compared the 2016 gross table with the 2015 net table; net to net a uniform 1.12-1.15; M -8.941m.

### 1274_2022 (rule 7: stands)

- P8 screen_misread, M 8.96, paid 33.4, incurred 0.25
- Q1 screen_misread, M 8.96, paid 33.4, incurred 0.25
- Rule 7: screen took the year t net table; on the gross table a stated 2-3% retranslation, incurred +0.25% (control 0.2%); M +8.96m.

### 1274_2024 (rule 7: stands)

- P7 screen_misread, M 53.399, paid None, incurred -0.4
- Q8 screen_misread, M 53.399, paid -10.2, incurred -0.4
- Rule 7: screen compared with the 2023 net table (its row label misprinted 'gross'); gross history moves by a uniform 0.986 (stated retranslation); incurred -0.4%; M +53.399m.

### 1301_2016 (rule 7: stands)

- P4 valid, M -1.6, paid None, incurred 7.1
- Q5 screen_misread, M -1.6, paid None, incurred 7.1
- Rule 7: the only flagged year is u = 2015 (t-1): a change from ultimate to earned basis; mature columns move by the common exchange ratio; M -1.6m (P4 valid, Q5 screen_misread: same class).

### 1416_2024 (rule 7: stands)

- P8 units_slip, M -0.302, paid None, incurred -14.0
- Q7 units_slip, M -0.302, paid None, incurred -14.0
- Rule 7: units slip in the stored 2024 grid ('millions' by default; printed $'000); M's scale unaffected (-0.302m equals the stored figure); the 2022 column moves -1.5%.

### 1492_2019 (rule 7: stands)

- P5 units_slip, M 10.889, paid -10.3, incurred -2.5
- Q4 units_slip, M 10.889, paid -10.3, incurred -2.5
- Rule 7: units and currency slip in the stored 2018 grid; no restatement beyond the stated closing-rate rebasing; M +10.889m.

### 1856_2021 (rule 7: stands)

- P2 valid, M -16.186, paid -3.5, incurred -0.4
- Q1 valid, M -16.186, paid -3.5, incurred -0.4
- Rule 7: the 2019 and 2020 end-2020 cells fall by the 2020 report's unearned claims reserve (31.2m) as the 2021 table moved to an earned basis, stated in its footnote (Q1; P2 reports the same footnote); the table ties (incurred -0.4%, paid -3.5%); explained, M -16.186m stands.

### 1880_2015 (rule 7: stands)

- P2 screen_misread, M -5.8, paid None, incurred -1.2
- Q3 screen_misread, M -5.8, paid None, incurred -1.2
- Rule 7: screen compared the 2015 gross table with the 2014 net ultimate table (no 2014 gross table); incurred -1.2%; M -5.8m.

### 1897_2019 (rule 7: stands)

- P1 valid, M 11.964, paid -29.7, incurred -6.1
- Q2 valid, M 11.964, paid None, incurred None
- Rule 7: the history moves by the stated retranslation and by the 2016 Property class transferred to the 2017 year of account under the syndicate's own RITC (p33): an internal RITC between its own years is not a take-on (Lloyd's internal RITC rule); the table ties (incurred -6.1% on an underwriting-year basis, control 2.9%); M +11.964m. Both readings note the 2017 term may carry the transferred claims.

### 1910_2016 (rule 7: stands)

- P7 valid, M -8.28, paid None, incurred 13.1
- Q8 valid, M -8.28, paid -9.9, incurred 13.1
- Rule 7: the only flagged year is u = 2015 (t-1); the mature years move by the stated balance-sheet-rate retranslation; M -8.28m.

### 1945_2016 (rule 7: stands)

- P2 valid, M -10.776, paid 31.6, incurred 12.4
- Q3 valid, M -10.776, paid 31.6, incurred 12.4
- Rule 7: the history moves by the stated closing-rate retranslation (1.10-1.17), both readings; incurred ties once the ultimate basis is allowed for (control 2.1%); M -10.776m.

### 1945_2018 (rule 7: stands)

- P2 valid, M 8.067, paid 1.5, incurred 11.5
- Q3 valid, M 8.067, paid 1.5, incurred 11.5
- Rule 7: the one outlier (2013, ratio 0.755) is a defect of the 2017 report's table (both readings); M from the 2018 table's own cells; the table ties (+11.5% on an ultimate basis, paid +1.5%); M +8.067m.

### 1947_2020 (rule 7: stands)

- P1 valid, M -3.502, paid 0.1, incurred -6.3
- Q2 valid, M -3.502, paid None, incurred None
- Rule 7: the 2019 report's 2018 cell is a misprint (the outstanding printed as the estimate, paid '-'), both readings; the 2020 table ties; M -3.502m.

### 1955_2023 (rule 7: stands)

- P2 screen_misread, M 6.565, paid -7.3, incurred -1.9
- Q1 screen_misread, M 6.565, paid -7.3, incurred -1.9
- Rule 7: screen used end-2021 cells; the right cells differ by the retranslation (0.94-0.98); the table ties within 2%; M +6.565m.

### 1967_2022 (rule 7: stands)

- P4 valid, M 45.457, paid None, incurred -2.6
- Q5 valid, M 45.457, paid None, incurred -2.6
- Rule 7: the 2021 report's 2020 cell (216,548) is a misprint of 416,548 proved by its own paid and balance rows (both readings); the 2022 table ties (-2.6%); M +45.457m.

### 2007_2016 (rule 7: stands)

- P4 valid, M 54.8, paid None, incurred 6.5
- Q3 valid, M 54.8, paid 56.5, incurred 6.5
- Rule 7: a change from an ultimate table with an unearned deduction (2015) to an earned table (2016), plus the retranslation (both readings); the screen's factor was not an exchange ratio; the table ties (+6.5%); M +54.8m.

### 2015_2022 (rule 7: stands)

- P1 valid, M 3.421, paid None, incurred -28.5
- Q8 valid, M 3.421, paid +9.0 unadjusted / -11.6 FX-adjusted, incurred -28.5
- Rule 7: the mature cells move by the stated retranslation (1.08-1.09); only the year t-1 column (UY2021) is restated, +28.4m beyond FX and unexplained, which is why the whole-table incurred test misses (-28.5%); rule 1 reads the history of u <= t-2 or the table as a whole, and M's years are untouched; M +3.421m.

### 2121_2018 (rule 7: stands)

- P6 screen_misread, M 27.6, paid +4.0 with the factor; +24.9 unadjusted, incurred 7.4
- Q7 valid, M 27.589, paid None, incurred None
- Rule 7: the flagged 2017 cell (t-1) is a misread 121,848; the rest is the stated 5.4% retranslation; M +27.589m.

### 2357_2024 (rule 7: stands)

- P6 units_slip, M -64.8, paid +0.9 (identity); cross-table -9.0, incurred 0.9
- Q5 units_slip, M -64.757, paid None, incurred 0.9
- Rule 7: the stored 2024 grid's units default to 'millions' (printed $'000); the analysis figure -64.757m is in the right scale; the history moves at most -2.5%.

### 2623_2023 (rule 7: stands)

- P2 screen_misread, M -472.2, paid 2.7, incurred 0.8
- Q1 screen_misread, M -472.2, paid 2.7, incurred 0.8
- Rule 7: screen set the $m triangle against the 2022 report's percentage block; the $m rows agree within 0.5%; the table ties (paid +2.7%, incurred +0.8%); M -472.2m.

### 2786_2024 (rule 7: stands)

- P7 screen_misread, M 5.989, paid None, incurred -1.6
- Q6 units_slip, M 5.989, paid -12.0, incurred -1.6
- Rule 7: label slip in the stored 2024 grid (USD millions); both printed tables are GBP thousands; the table ties (-1.6%); the analysis figure +5.989m is in the right scale (P7 screen_misread, Q6 units_slip: same class).

### 2791_2022 (rule 7: stands)

- P3 screen_misread, M -17.497, paid None, incurred 7.5
- Q4 screen_misread, M -17.5, paid None, incurred 2.6
- Rule 7: screen misaligned the 2021 table (its greyed '2010 and prior' column); every year moves by the stated 1.10-1.12; M -17.497m (the round-2 decision on its older-years column stands).

### 2988_2020 (rule 7: stands)

- P8 units_slip, M 3.155, paid None, incurred -4.7
- Q7 units_slip, M 3.1548, paid None, incurred -4.7
- Rule 7: label slip in the stored 2019 grid; the base moved 2.1-2.6% uniformly (stated); M +3.155m.

### 3000_2018 (rule 7: stands)

- P7 valid, M 17.88, paid -8.9, incurred 14.2
- Q6 valid, M 17.88, paid -8.9, incurred 14.2
- Rule 7: the history moves by the stated year-end revaluation; the flagged 2013 move comes from a faulty 2017 print (both readings); the reallocation P7 names in 2011 and 2014 is under the screen's 1%-of-R flag, and the end-2017 reserve agrees with the 2017 report within 0.7%; M +17.88m.

### 3624_2018 (rule 7: stands)

- P3 valid, M 22.902, paid -1.0, incurred 23.6
- Q2 valid, M 22.902, paid None, incurred None
- Rule 7: a change of presentation currency to US dollars (1.32-1.34 on every mature year); only the t-1 first-year cell is a misprint; M +22.902m.

### 4444_2022 (rule 7: stands)

- P1 screen_misread, M 34.9, paid None, incurred 3.3
- Q2 screen_misread, M 34.9, paid None, incurred None
- Rule 7: the screen's year t cells were one column off; the history moves 1.07-1.10 (translation); the table ties (3.3%, control 3.2%); the figure +34.9m is the confirmed one (data/pyd_confirmed_figures.json).

### 4472_2022 (rule 7: stands)

- P6 screen_misread, M 122.3, paid -3.8, incurred 6.1
- Q5 screen_misread, M 122.3, paid None, incurred 6.1
- Rule 7: screen compared the 2022 net table with the 2021 gross; gross to gross the stated retranslation only; the analysis figure +122.3m is the gross table's (Q5 notes the stored 2022 grid holds the net block under a gross label: the adopted figure does not come from it).

### 4472_2024 (rule 7: stands)

- P4 screen_misread, M 216.776, paid 5.7, incurred 4.0
- Q3 screen_misread, M 216.776, paid 5.7, incurred 4.0
- Rule 7: screen compared the 2024 gross table with the 2023 net table; gross to gross 1.006-1.016; the table ties (4.0%, control -3.0%); M +216.776m.

### 5000_2018 (rule 7: stands)

- P4 screen_misread, M 38.47, paid 0.0, incurred 2.4
- Q3 screen_misread, M 38.47, paid 20.4, incurred 2.4
- Rule 7: a zero-filled blank read by the screen; a uniform 1.036-1.054 retranslation; the table ties (+2.4%, paid 0.05%); M +38.47m.

### 5151_2020 (rule 7: stands)

- P5 screen_misread, M 68.015, paid -1.2, incurred -1.4
- Q4 screen_misread, M 68.015, paid -1.2, incurred -1.4
- Rule 7: screen compared against a zero placeholder; the history is identical; the table ties (paid -1.2%, incurred -1.4%); M +68.015m.

### 5678_2016 (rule 7: stands)

- P6 screen_misread, M 0.861, paid -62.3 for the table alone (the 7,067 gap is the Before-2012 RITC block); not testable for that block, incurred 22.6
- Q5 screen_misread, M 0.861, paid -62.3, incurred 22.6
- Rule 7: an alignment artefact; the history moves by the FX factor 1.13-1.15; M +0.861m.

### 6107_2023 (rule 7: stands)

- P8 screen_misread, M -11.6, paid 5.2, incurred 2.3
- Q1 screen_misread, M -11.6, paid 5.2, incurred None
- Rule 7: screen compared $m with a loss-ratio percentage grid on the wrong page; the history is unchanged within 1.4%; the table ties; M -11.6m.

