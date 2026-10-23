# Tie-break brief, round 8: the year t-1 control for two rule-1 exclusions (BAJ paper)

Out of scope, always: the paper's AI declaration and anything about AI use.

Tools and discipline exactly as `D:/tmp/r62/oc/readings/brief.md` (read it first) and the round-5 brief
`D:/tmp/r62/oc/readings/brief_r5.md` (read it: the question, the incurred and paid tests, the verdicts). Write ONLY in
your own folder (named in your prompt). Do not open any other reader's folder, the analysis registers, or any
adjudication. Rewrite `readings.json` after each record. No paid API; no network.

## The question
Rule 1 excludes a record when its year t table fails the year's accounts while the year t-1 table (the control) ties.
The control ties when it is within 5%; or within 10% when **the same basis gap explains both years** (for example an
'& prior' column outside the printed cells, or an ultimate or underwriting basis set against earned calendar-year
accounts) and the year t miss is at least three times the control's. For each record below, from the pages alone:

1. The control: the year t-1 report's table, its implied gross incurred for year t-1 (the latest diagonal less the
   diagonal before, all printed years, with every cell, page and unit), set against year t-1's gross claims incurred in
   that report's accounts (page). Also the paid test if the table prints cumulative paid at both dates.
2. The basis of each table (earned, written, ultimate, underwriting-year cumulative incurred; any column outside the
   cells; any note on what the table includes or leaves out), quoted with its page.
3. Whether a named basis difference **explains the control's gap**: estimate its size from the pages where you can (for
   example the outside column's movement, or unearned premium's share), and say whether the same difference is present
   in the year t table. Answer `shared_basis_gap: yes | no | undeterminable`, with the reason and the figures.
4. The year t miss (implied gross incurred against the year t accounts), with cells and pages, and its ratio to the
   control's miss.

## 4747_2024 (`syndicate_4747_2024`; year t-1 report `syndicate_4747_2023`)
Look in particular at what the tables' first-year cells compare with (gross premiums written; earned), whether the
outstanding in the 2023 table ties to the 2023 balance sheet, and any note on the table's basis.

## 780_2016 (`syndicate_780_2016`; year t-1 report `syndicate_780_2015`)
Look in particular at the '& prior' years outside the printed cells (their movement in each year, from any page that
gives it), and at both the incurred and the paid tests in each year.

## Report
`readings.json`: per record, the cells and pages for items 1-4, `control_diff_pct`, `basis_each_table`,
`shared_basis_gap` with reason, `year_t_diff_pct`, `ratio`, and anything that contradicts the question's premises.
Final message: the two records' answers in a few lines each.
