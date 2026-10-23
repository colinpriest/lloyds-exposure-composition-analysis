# Decision rules for the round-5 readings (decision of the Claude analysis session, 23 October 2026)

Rules 1 to 7 were written before the adjudication. Three rules were added or made exact after particular readings or the
eighth review, each on 23 October 2026: rule 5b (after the round-7 readings U1 and U2 of the two take-ons whose transferred
amount the round-5 readings did not print); rule 6's take-on clause, take_on_table_unreconciled (after the readings of
3500/2023; applied to 3500/2022 after review 8); and rule 1's exact control clause (after review 8). Review 8 also added
rule 6's derived-correction clause (derived_correction, 1274/2016).

Written before the adjudication, applied the same way to every record (82 read in round 5, plus 2689/2023 read by V1, V2
and W1, W2). Every decision rests on facts both readings report; where the two readings give conflicting facts (not
labels), a third reading decides.

1. **Invalid table: leaves the primary.** The year t table's history (an underwriting year u <= t-2, or the table as a
   whole) differs from the year t-1 report beyond the exchange rate, with no explanation in either filing; AND the year t
   table fails the year's accounts (implied gross incurred, or paid where computable, off by more than 10% beyond what
   its basis explains) while the year t-1 control ties; AND the year t-1 report's printed base does not give a figure
   that reconciles either. The year t-1 control ties when it is within 5%, or within 10% when the same basis gap explains
   both years (an '& prior' column outside the cells, an ultimate basis against earned accounts) and the year t miss is at
   least three times the control's. Expected: 2689/2023, 4747/2024, 6134/2022, 780/2016. (4242/2022 was expected here
   before review 8 and is decided under rule 3: its year t-1 base reconciles once the merged '2016 & Prior' column, which
   both readers call unreadable as a cohort, is set aside.)

   The control clause was made exact on 23 October 2026, after review 8, and re-applied to every record. Under it 780/2016
   (control +9.5% from the '2010 & prior' years outside the cells, the same gap in both years; year t paid identity +80%,
   8.4 times the control's) and 4747/2024 (control -7.2%, outstanding tying exactly; year t -81.9%, 11.4 times) are met;
   2232/2017, 2488/2016, 382/2021, 1967/2017 and 1729/2023 are not, and stay on the least-certain list (their entries
   in the register say why). Re-applying the clause to every record changed no outcome. 780/2016 and 4747/2024 meet it
   only through its 10% branch (2689/2023 and 6134/2022 tie within 5%). 4242/2022's move from rule 1 to rule 3 did not
   come from the clause: its control (-1.1%) ties under the old and the exact clause alike, and it moved on review 8's
   separate decision to set aside the merged '2016 & Prior' column.
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
   2001/2016 was checked against the 1% of R after review 8: its UY2013 and UY2014 cells fall 24.9m and 16.7m (1.56% and
   1.04% of R, 1,601.0m) against an exchange uplift, 2.60% together, and every measure is over 1%, so it stays listed.
7. **Stands.** Every other record: valid, screen misread, or a units slip that does not reach the analysis figure.
