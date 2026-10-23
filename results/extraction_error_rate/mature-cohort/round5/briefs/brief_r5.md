# Reading brief, round 5: development tables whose history moved between reports (BAJ paper)

Out of scope, always: the paper's AI declaration and anything about AI use.

Tools and discipline exactly as `D:/tmp/r62/oc/readings/brief.md` (read it first): page text tool `filing_pages.py`,
page images via `render.py` (copy PNGs into your own `renders/`), read only, no paid API, no network, NEVER `cd` in
Bash, Write tool for scripts, UTF-8 with LF, never invent a number, every figure with page and verbatim cells. Write ONLY
in your own folder. Do not open any other reader's folder. Rewrite `readings.json` (keyed by record key) after EVERY
record and append to `log.txt`; you may be stopped and resumed: continue from the first record not in `readings.json`.

## Why
The paper's outcome for a record (syndicate, report year t) is M = sum over underwriting years u <= t-2 of (estimate at
end of year t) less (estimate at end of year t-1), both read from the year t report's printed GROSS claims development
table. A screen compared each year t table's end-(t-1) cells with the year t-1 report's latest cells and flagged
records where some underwriting year moved by more than one exchange rate explains. The reference case is 2689/2023:
its 2023 table restated the 2020-2021 history (e.g. 2020 at end-2022: 123,040 against 81,688 printed in 2022), with no
explanation; outstanding still tied to the balance sheet, but the table's implied 2023 gross PAID (sum over every column
of the change in cumulative paid, plus the current year's paid) was 133.1m against 36.1m gross claims paid in the 2023
accounts, and its implied incurred 93.9m against 58.2m. Such a table cannot give the year's movement. A restatement
can also be legitimate (a stated change of basis, a correction, a retranslation, a structural change shown "as if
always"): the reading decides which.

## Your batch
`batch.json` in your folder: per record, `key`, the screen's `verdict` and tier, the flagged underwriting years with
`cells_t` (the year t table's end-(t-1) cell), `cells_prev` (the year t-1 table's latest cell), their `ratio`s and the
record's `factor` (the common exchange ratio), size against opening reserves R, and pages (`page_t`, `page_prev`).
These come from a script on the stored extraction, not from readings: check them on the page.

## For each record
1. Confirm or correct the screen's cells on BOTH filings' printed gross tables (pages, headings, units, quotes). If the
   screen misread (wrong column, wrong row, a units label wrong, an "and prior" column), say so and stop at verdict
   `screen_misread` with the correct cells.
2. Look for any explanation in either filing (restat, re-present, prior year adjust, change of basis or presentation,
   correction, RITC received or "as if always", merger, portfolio transfer, change of managing agent, reclassif). Quote.
3. The paid test, on the year t table: implied gross paid in year t = sum over every underwriting-year column of
   (cumulative paid at end t) less (cumulative paid at end t-1, as printed in the SAME year t table), plus the
   current year's cumulative paid; compare with the year t accounts' gross claims paid (technical account or note; quote
   the line). Do the same for the year t-1 table against the year t-1 accounts as a control. If the table prints no
   cumulative paid, use the incurred test instead: implied gross incurred against gross claims incurred, and say
   whether the table is on an underwriting (ultimate, unearned included) or earned basis, since an ultimate-basis table
   legitimately exceeds earned incurred.
4. Verdict:
   - `valid`: the year t table ties to the year t accounts (paid within 5%, or incurred within 5% on an earned basis),
     and any change of history is explained or immaterial; M stands.
   - `restated_base`: the table does not tie to the year's accounts in the way 2689/2023 does, and the history change is
     not explained; M is not measurable from the table. Give the true movement only if the filing prints it.
   - `screen_misread`: the cells the screen used are wrong; give the right ones and whether M is affected.
   - `units_slip`: a units label is wrong in one grid; say which and whether M's scale is affected.
   - `undeterminable`: say exactly why.
   Also give M recomputed from the printed year t table (u <= t-2) and whether it equals the analysis figure if given.

Entry fields: `key`, `read_by`, `pages`, `cells_check`, `explanation` (quotes), `paid_test` {table_implied, accounts,
page, quote, diff_pct}, `paid_test_prev` {...}, `incurred_test` (when used), `basis`, `m_recomputed_m`, `verdict`,
`note`. Final message: one line per record: key, verdict, the paid test's two numbers.
