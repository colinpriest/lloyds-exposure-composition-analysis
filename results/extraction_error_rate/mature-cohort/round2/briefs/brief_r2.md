# Reading brief, round 2: older-years columns and exchange lines (BAJ paper, Lloyd's syndicate filings)

Out of scope, always: the paper's AI declaration and anything about AI use. Do not touch it.

Tools, rules and output discipline are exactly those of `D:/tmp/r62/oc/readings/brief.md` (read it first): the page
text tool `filing_pages.py` (text layer or OCR), page images via `render.py` (copy the PNGs you use into your own
`renders/`), read only, no paid API, no network, no `cd`, Write tool for scripts, UTF-8 with LF, never invent a number,
every figure with its page and verbatim cells or label. Write ONLY in your own folder
`D:/tmp/r62/oc/readings/<your reader id>/`. Do not open any other reader's folder: readings must be independent.
After EVERY record rewrite your whole `readings.json` (a dict keyed `<key>|<task>`) and append one line to `log.txt`; you
may be stopped after about 8 turns, and when resumed you continue from the first record not in `readings.json`.

Your batch is `batch.json` in your folder. Each record has a `task`: `aggregated_column` or `exchange_line`. Fields named
`script_*`, `*_hint` and `grid_*` come from scripts on the stored extraction, NOT from readings: use them to find pages,
never as evidence. Filings: `D:/dev/lloyds_reserve_stress_testing/syndicate_reports/pdfs/syndicate_<key>.pdf` or the HTML
in `D:/dev/lloyds_reserve_stress_testing/pdf_extraction/html_converted/`. The year t-1 filing is `<syndicate>_<t-1>`.

## Task `aggregated_column`

The paper's outcome (Equation 1) is the gross prior-year movement on mature underwriting years: M = sum over u <= t-2 of
(estimate at report year t) less (estimate at t-1), from the printed GROSS claims development table. Its rule for an
older-years column such as "2010 & prior" (Appendix 2.1): the column is one of the mature years when the table develops it
BY CALENDAR YEAR (it covers the same underwriting years in the year t and year t-1 reports, so its last two diagonal
cells are like for like); a column printed BY DEVELOPMENT AGE (its coverage grows by one underwriting year each report,
built age by age, e.g. the 2024 report's "2014 & Prior" = the 2023 report's "2013 & Prior" plus UY2014 at each age) is
LEFT OUT, because its last step is not the report year's movement; a column with no development of its own (a single
figure) is not part of the triangle.

For each record:
1. Find the gross claims development table in the year t filing (start at `pages_hint`). Quote its heading, the older-
   years column's label, and its cells (page).
2. Find the same table in the year t-1 filing (and year t+1 if t-1 is missing). Quote the older-years column's label and
   cells there.
3. Decide the construction: `calendar_year` (same coverage both reports; e.g. label fixed "2010 & prior" in both, or rows
   printed as "n years or more later"), `development_age` (coverage moves by one year; show at two ages that the year t
   cell ~ the t-1 column plus the next underwriting year at the same age), `no_own_development`, or `undeterminable`
   (say exactly why). Note any exchange restatement of prior cells.
4. Recompute from the PRINTED year t table: M including the column and M excluding it (millions of the report currency;
   list the cells you used for every underwriting year). The rule's figure is "including" for `calendar_year` and
   "excluding" for `development_age` / `no_own_development`.
5. Verdict: `consistent` if `adopted_figure_m` equals the rule's figure within 0.5m or 1% (the adopted figure includes
   the column when `adopted_figure_includes_column` is true), `inconsistent` (give the rule's figure), or
   `undeterminable`. Also say whether the table is gross and reconciles to the gross claims outstanding (within 2%).

Entry fields: `task`, `key`, `read_by`, `pages`, `table_t` {page, heading, basis, column_label, column_cells},
`table_t_minus_1` {filing, page, column_label, column_cells}, `construction`, `construction_evidence`,
`figure_including_column_m`, `figure_excluding_column_m`, `cells_used`, `rule_figure_m`, `verdict`, `note`.

## Task `exchange_line`

The author's rule B: a record leaves the primary sample when (a) its development table is NOT retranslated between the
year t-1 and year t reports across a GBP/USD move of 5% or more (`gbp_usd_move_in_year_t` gives the move), AND (b) the
filing's own GROSS claims-outstanding roll-forward (the reconciliation of gross claims outstanding / gross provision for
claims from 1 January to 31 December) prints an exchange line of at least 5% of the opening gross claims outstanding R.

For each record:
1. Find the gross claims-outstanding roll-forward. Quote the opening gross claims outstanding R (page, verbatim) and the
   exchange / foreign currency translation line on the GROSS column (page, verbatim, value in millions). Beware lines
   that are not the gross claims roll-forward (members' balances, profit distribution, agents' fees, net or reinsurers'
   columns, the technical account): `script_fx_line_hint` is a pattern match and is often the wrong line. If no
   roll-forward or no exchange line is printed, say "none printed" and list the pages you searched.
2. Compute the line as a percentage of R. If it is under 5% in absolute value (or none printed), condition (b) fails:
   verdict `keep`, and you may stop there.
3. Only if it is 5% or more: compare at least three cells for underwriting years before t-1 in the year t and year t-1
   development tables (pages, quotes); say whether they are identical (not retranslated) or moved (retranslated), and
   whether the table states its exchange basis. Verdict `exclude` if both (a) and (b) hold, else `keep`;
   `undeterminable` if (a) cannot be checked (say why: e.g. no year t-1 filing in the corpus).

Entry fields: `task`, `key`, `read_by`, `pages`, `report_currency`, `R` {value_m, page, quote}, `fx_line` {value_m, page,
quote} or "none printed", `pages_searched`, `fx_line_pct_of_R`, `retranslation` {checked, cells_t, cells_t_minus_1,
stated_basis} (only when needed), `verdict`, `note`.

## Finish

Final message: one line per record: key, task, verdict, and the figure or percentage.
