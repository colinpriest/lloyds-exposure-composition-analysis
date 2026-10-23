# Reading brief, round 7: transferred gross amounts of two take-ons (BAJ paper)

Out of scope, always: the paper's AI declaration and anything about AI use.

Tools and discipline exactly as `D:/tmp/r62/oc/readings/brief.md` (read it first). Write ONLY in your own folder;
never open another reader's folder; rewrite `readings.json` after each record; never `cd` in Bash; Write tool for
scripts; never invent a number.

The analysis divides a record's mature-cohort movement by its opening gross claims outstanding R. When an RITC, LPT
or merger effective in year t brings in another book and the development table shows the acquired history "as if
always", R must include the acquired gross reserves. For each record give:
1. the transaction(s): type, counterparty, effective date, quotes and pages;
2. the gross claims outstanding transferred in (the gross amount, not net or the reinsurers' share), page and verbatim
   line, in the report currency; if several items, each and their total;
3. the opening gross claims outstanding at 1 January of year t (page, line) and the closing at 31 December;
4. whether the development table includes the acquired years "as if always" (quote the wording or show it by cells);
5. whether an adverse development cover or loss portfolio reinsurance is OUTWARD (ceded, so not a take-on of gross
   reserves) or INWARD;
6. the take-on base: opening R plus the gross amount transferred in, and how it compares with the analysis's
   `opening_reserves_gbp_m` (given below; GBP).

Records:
- `1110_2022` (GBP report; analysis opening_reserves_gbp_m 221.885): Syndicate 5678 RITC and a Hiscox adverse
  development cover; earlier readers point to p5, p27, p28, p33; the closing gross claims outstanding is about 489.6m
  against an opening of about 221.9m.
- `1458_2024` (USD report; analysis opening_reserves_gbp_m from `D:/tmp/r62/oc/A/model/exposure_results.json`, look it
  up): an external RITC in 2024 restating the 2020 and 2021 underwriting years; earlier readers point to p31 and p47.

Entry fields: `key`, `read_by`, `pages`, `transactions`, `gross_transferred_in` {value_m, page, quote}, `opening_R`
{value_m, page, quote}, `closing` {...}, `as_if_always` (quote), `adc_direction`, `takeon_base_m`, `note`.
