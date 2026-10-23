# Decision rules for the round-5 readings (decision of the Claude analysis session, 23 October 2026)

Rules 1 to 7 were written before the adjudication. Four rules were added or made exact after particular readings or the
eighth review: rule 5b (23 October 2026, after the round-7 readings U1 and U2 of the two take-ons whose transferred
amount the round-5 readings did not print); rule 6's take-on clause, take_on_table_unreconciled (23 October, after the
readings of 3500/2023; applied to 3500/2022 after review 8); rule 1's exact control clause (23 October, after review 8);
and rule 4b (24 October 2026, after the round-8 readings Z7 and Z8, `../round8/`). Review 8 also added rule 6's
derived-correction clause (derived_correction, 1274/2016).

Written before the adjudication, applied the same way to every record (82 read in round 5, plus 2689/2023 read by V1, V2
and W1, W2). Every decision rests on facts both readings report; where the two readings give conflicting facts (not
labels), a third reading decides.

1. **Invalid table: leaves the primary.** The year t table's history (an underwriting year u <= t-2, or the table as a
   whole) differs from the year t-1 report beyond the exchange rate, with no explanation in either filing; AND the year t
   table fails the year's accounts (implied gross incurred, or paid where computable, off by more than 10% beyond what
   its basis explains) while the year t-1 control ties; AND the year t-1 report's printed base does not give a figure
   that reconciles either. The year t-1 control ties when it is within 5%, or within 10% when the same basis gap explains
   both years (an '& prior' column outside the cells, an ultimate basis against earned accounts) and the year t miss is at
   least three times the control's. Expected: 2689/2023, 6134/2022 (both tie within 5%). (4242/2022 was expected here
   before review 8 and is decided under rule 3: its year t-1 base reconciles once the merged '2016 & Prior' column, which
   both readers call unreadable as a cohort, is set aside. 780/2016 and 4747/2024 were expected here until the round-8
   readings, and are decided under rules 6 and 4b.)

   The control clause was made exact on 23 October 2026, after review 8, and re-applied to every record. It decided no
   record. 4242/2022 moved from rule 1 to rule 3 on review 8's decision to set aside the merged '2016 & Prior' column
   (its control, -1.1%, ties under the old and the exact clause alike). 780/2016 and 4747/2024, which stayed under rule 1
   on the session's reading that their controls met the 10% branch, both fail it on the round-8 readings Z7 and Z8
   (`../round8/`, brief_r8.md), which agree on every fact: 4747/2024's control misses by -7.2% with no shared basis gap
   (a shortfall, which an ultimate or underwriting basis cannot give); 780/2016's misses by +9.4% and its year t
   incurred by +5.6%, 0.6 times the control's, so the 10% branch fails whatever the basis (P6's +80% paid identity is
   not like for like: the 2016 table re-cuts its history). 2232/2017, 2488/2016, 382/2021, 1967/2017 and 1729/2023 do not
   meet rule 1 either (their entries in the register say why).
2. **Exchange rule B: leaves the primary.** The table mixes exchange bases (history not retranslated while the year end
   is) and the year's exchange effect on gross reserves is at least 5% of R (the author's rule B). Expected: 3000/2022.
3. **Corrected to the previous report's base.** As in 1, but the year t-1 report's printed cells, used as the base,
   give a movement that reconciles with the year's accounts (within 5%), and both readings give the same corrected
   figure: the register carries that figure. Expected: 2232/2020 (+19.3m against +55.2m); and, after review 8, 4242/2022
   (-80.015m USD against -44.371m: both readings give the same movement on the 2021 report's printed cells, which
   reconcile with the 2022 accounts, 79.3m against 78.3m, once the merged '2016 & Prior' column is set aside; M uses
   no cell of that column on either base).
4. **Known-cause correction.** The printed or stored table is wrong for a stated, checkable reason (transposed body,
   misprinted cell proved by the same report's own arithmetic or the previous report, wrong grid): the register carries
   the corrected figure that both readings give. Expected: 318/2024 (-27.99m), 1274/2016 (misprinted 2012 cell). The
   1274/2016 figure is not one either reader gives: it is the session's derivation from cells both readers quote, the
   previous report's 2012 cell at the 2012 column's own exchange factor (its paid cells at end-2015, 129,350 in the 2016
   table over 131,423 in the 2015 report, 0.98423), +22.694m USD. The register keeps each reader's own figures as they
   gave them, stores the derivation apart (derived_figure_m), allows it only while both readers quote every cell used,
   gives the range other defensible factors yield (+21.8m to +25.7m), and the record joins the least-certain list (rule 6,
   clause derived_correction).
4b. **A table its own cells prove inconsistent: leaves the primary** (added 24 October 2026, after the round-8 readings).
   Where rule 1's control does not tie, a record still leaves the primary when (i) both readings report that the year t
   table prints, for an underwriting year u <= t-2, cumulative paid lower than the year t-1 report printed for the same
   year, by more than the exchange rate explains and with no explanation in either filing; and (ii) the year t table
   fails the year's accounts by more than 10% (rule 1's test); and (iii) no base gives a figure that reconciles (rule 3
   fails). A cumulative paid figure cannot fall, so the table is not one consistent cumulative table, and no figure from
   it measures the year's movement. Applied to the readings of every record of rounds 5 to 8 (`../round8/
   scan_rule_4b.py` lists every passage that reports a paid figure falling; `../round8/rule_4b_scan.json` records each
   record's answer to (i) to (iii) with its readings). It decides two records:
   - 4747/2024 (rule 1 until round 8): UY2020 cumulative paid 213 in the 2024 table (p48) against 4,843 in the 2023
     report (p39), and UY2021 4,164 against 5,883 (P2, Q3, Z7, Z8); year t miss -81.9%; no base reconciles (-27% on the
     2023 printed base).
   - 2232/2017 (rule 6, least certain, until the scan found it): UY2012 cumulative gross paid 19,393 in the 2017 table
     (p40) against 22,799 in the 2016 report (p40), x0.851, beyond the x0.918-0.939 retranslation Q4 measures on the same
     columns' earlier cells (P3 names the fall; Q4 quotes the cells); (ii) is narrow: implied incurred -10.5% in both
     readings (264.9m against 296.0m), on an ultimate basis that would put the table above the earned accounts, not
     below; the previous report's base gives the same cells, so no base reconciles.
   780/2016 meets (i) on Q5, Z7 and Z8 (UY2011 218.9 to 208.9) but fails (ii) (+5.6%), so it stays under rule 6. 2468/2020
   meets (i) on both readings but its table ties (incurred -3.8%, paid -4.3%), so it stays under rule 6.
5. **Take-on base.** An RITC, LPT or merger effective in year t whose acquired history the table shows "as if always":
   the movement is development on the combined book, so R must include the acquired gross reserves. If the analysis's
   R already includes them (check `opening_reserves_gbp_m` against the filing's opening gross reserves plus the
   transfer, e.g. 2488/2019), nothing changes; otherwise add the record to `data/opening_reserves_takeon_base.json`
   with the transferred gross amount and its page from the readings. Candidates: 1686/2021, 1686/2022?, 1856/2024,
   1884/2021, 3000/2016, 4000/2022, 4444/2018, 4444/2023, 1110/2022, 1458/2024, 3500/2022, 3500/2023, 2488/2019,
   1897/2019 (an internal RITC between the syndicate's own years is not a take-on: Lloyd's internal RITC rule).
5b. **A take-on whose transferred gross reserves the filing does not print** (rule 5 applies but the register cannot carry
   an amount; added 23 October 2026, after the round-7 readings U1 and U2 of 1110/2022 and 1458/2024, brief_r7.md): if
   the readings show the acquired share of the base could exceed 10% of the opening gross claims outstanding R, the
   record leaves the primary as an unmeasurable take-on (as 1861/2020 and 1084/2022 do); if the filing bounds the
   acquired share at or below 10% of R, the record stays and joins the least-certain list (rule 6's register bucket, with
   its own reason). Applied: 1110/2022 leaves (both readings: S5678 RITC and an inward Hiscox ADC, no amount printed,
   reserves 221.885m to 489.603m, indicated take-on about 221.9m, about 100% of R); 1458/2024 stays and is listed (an
   external RITC, upper bound USD 164.1m of cumulative incurred, 8.0% of R). 3500/2023 (rule 5, R already includes its
   take-on) is also listed: the table does not reconcile with note 7 (-52.1m against -184.8m on the old years) and no
   other rule covers an explained take-on table that fails the tie. 3500/2022 joined it after review 8, on the same
   all-prior-years scope (-389.8m against note 7's -293.1m; the whole table -26.4m): the readings conflict on where the
   loss portfolio transfers sit, and either way the acquired share outside R is at most 9.1% of R (the two mid-2022
   LPTs, 360.9m of 3,955.0m; 9.8% with all four), so rule 5b would list it too.
6. **Least certain: stays, listed.** The table ties to the year's accounts (or its basis explains the gap), but an
   underwriting year u <= t-2 moved beyond the exchange rate without explanation by more than 1% of R; or the two
   readings disagree on a label but not on the facts; or (added 23 October 2026) an explained take-on already in R has a
   table that does not reconcile with the filing's own roll-forward (3500/2023, and 3500/2022 after review 8); or (added
   after review 8) the record's corrected figure is the session's derivation from cells both readers quote (1274/2016).
   These stay in the primary and join the least-certain sensitivity, derived by this rule from the register (never typed).
   780/2016 joined after the round-8 readings (24 October 2026): its 2016 table re-cuts its history (end-2015 diagonal
   528.0 against 701.6 in the 2015 report, unexplained, far over 1% of R) while the year t table ties to the accounts
   (+5.6%); its figure is M as printed, +24.9m USD (both readings: +2.4, +4.4, +3.4, +14.7).
   2001/2016 was checked against the 1% of R after review 8: its UY2013 and UY2014 cells fall 24.9m and 16.7m (1.56% and
   1.04% of R, 1,601.0m) against an exchange uplift, 2.60% together, and every measure is over 1%, so it stays listed.
7. **Stands.** Every other record: valid, screen misread, or a units slip that does not reach the analysis figure.
