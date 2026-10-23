# Decision rules for the round-5 readings (decision of the Claude analysis session, 23 October 2026)

Written before the adjudication, applied the same way to every record (82 read in round 5, plus 2689/2023 read by V1, V2
and W1, W2). Every decision rests on facts both readings report; where the two readings give conflicting facts (not
labels), a third reading decides.

1. **Invalid table: leaves the primary.** The year t table's history (an underwriting year u <= t-2, or the table as a
   whole) differs from the year t-1 report beyond the exchange rate, with no explanation in either filing; AND the year t
   table fails the year's accounts (implied gross incurred, or paid where computable, off by more than 10% beyond what
   its basis explains) while the year t-1 control ties within 5%; AND the year t-1 report's printed base does not give a
   figure that reconciles either. Expected: 2689/2023, 4747/2024, 4242/2022, 6134/2022, 780/2016.
2. **Exchange rule B: leaves the primary.** The table mixes exchange bases (history not retranslated while the year end
   is) and the year's exchange effect on gross reserves is at least 5% of R (the author's rule B). Expected: 3000/2022.
3. **Corrected to the previous report's base.** As in 1, but the year t-1 report's printed cells, used as the base,
   give a movement that reconciles with the year's accounts (within 5%), and both readings give the same corrected
   figure: the register carries that figure. Expected: 2232/2020 (+19.3m against +55.2m).
4. **Known-cause correction.** The printed or stored table is wrong for a stated, checkable reason (transposed body,
   misprinted cell proved by the same report's own arithmetic or the previous report, wrong grid): the register carries
   the corrected figure that both readings give. Expected: 318/2024 (-27.99m), 1274/2016 (misprinted 2012 cell; compute
   the corrected figure from both readings' cells and the 2015 report, at the year's exchange factor, and show it).
5. **Take-on base.** An RITC, LPT or merger effective in year t whose acquired history the table shows "as if always":
   the movement is development on the combined book, so R must include the acquired gross reserves. If the analysis's
   R already includes them (check `opening_reserves_gbp_m` against the filing's opening gross reserves plus the
   transfer, e.g. 2488/2019), nothing changes; otherwise add the record to `data/opening_reserves_takeon_base.json`
   with the transferred gross amount and its page from the readings. Candidates: 1686/2021, 1686/2022?, 1856/2024,
   1884/2021, 3000/2016, 4000/2022, 4444/2018, 4444/2023, 1110/2022, 1458/2024, 3500/2022, 3500/2023, 2488/2019,
   1897/2019 (an internal RITC between the syndicate's own years is not a take-on: Lloyd's internal RITC rule).
6. **Least certain: stays, listed.** The table ties to the year's accounts (or its basis explains the gap), but an
   underwriting year u <= t-2 moved beyond the exchange rate without explanation by more than 1% of R; or the two
   readings disagree on a label but not on the facts. These stay in the primary and join the least-certain sensitivity,
   derived by this rule from the register (never typed).
7. **Stands.** Every other record: valid, screen misread, or a units slip that does not reach the analysis figure.
