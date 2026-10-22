# Reading brief, round 3 (tie-break): is an older-years column like for like? (BAJ paper)

Out of scope, always: the paper's AI declaration and anything about AI use. Do not touch it.

Tools and discipline exactly as `D:/tmp/r62/oc/readings/brief.md` (read it first): page text tool `filing_pages.py`, page
images via `render.py` (copy PNGs you use into your own `renders/`), read only, no paid API, no network, no `cd`, Write
tool for scripts, UTF-8 with LF, never invent a number, every figure with page and verbatim cells. Write ONLY in
your own folder (named in your prompt). Do not open any other reader's folder (A*, B*, C*, F*, T*, X*, Y*, Z*). After EVERY record
rewrite `readings.json` (keyed `<key>`) and append to `log.txt`; you may be stopped after about 8 turns, and when resumed
continue from the first record not in `readings.json`. Filings:
`D:/dev/lloyds_reserve_stress_testing/syndicate_reports/pdfs/syndicate_<syndicate>_<year>.pdf` (or the HTML in
`.../pdf_extraction/html_converted/`).

## The question

The paper's outcome is M = sum over underwriting years u <= t-2 of (estimate at report year t) less (estimate at t-1),
from the printed gross claims development table of the year t report. Its rule for an older-years column such as
"2013 and prior": the column counts as one of the mature years only if its LAST STEP (its latest cell less the cell
before it, in the year t table) is a like-for-like movement of the same set of underwriting years during year t.

Two constructions occur when the label's anchor moves forward a year between reports (e.g. "2012 and prior" in the
year t-1 report, "2013 and prior" in the year t report):
- **restated by calendar year (like for like, KEEP):** the year t report recomputes the whole column history for the new
  coverage, so each cell is the total of all years <= anchor_t at one calendar date. Test: the year t column's
  SECOND-TO-LAST cell (the position for end of year t-1) equals the year t-1 report's older-years column's LATEST cell
  plus the year t-1 report's latest cell for the underwriting year that joined the block (here UY2013), allowing one
  uniform exchange-restatement factor across the column; and more generally each year t column cell equals the t-1
  report's (older column + joining year) at the SAME CALENDAR DATE.
- **built by development age (not like for like, LEAVE OUT):** each year t column cell at development age a equals the
  t-1 report's older column at age a plus the joining year at age a (same AGE, different calendar dates), so the last
  step mixes years.

When the older block dominates, both fits can be within 1%: then compare the fits cell by cell, say which residual
pattern is uniform (a constant ratio or constant difference across the column) and which drifts, and look for the
filing's own words on how the table is built (footnotes, "years or more later" row labels, "as if always", RITC
restatements). Also say how the table lays out its rows (development age down, or calendar year down) and where the
column's latest and second-to-latest cells sit.

## Records

| key | adopted figure | figure with / without the column (scripts) | pages to start (year t / year t-1) |
|---|---|---|---|
| 2791_2022 | -17.497 (incl.) | -17.497 / -8.245 | p82 / 2021 report p81 (2023 report as t+1) |
| 2791_2023 | -35.529 (incl.) | -35.529 / -28.210 | p83 / 2022 report p82 |
| 2791_2024 | -36.191 (incl.) | -36.191 / -27.986 | p49 / 2023 report p83 |
| 1955_2018 | 16.7 (incl.) | 16.7 / 18.5 | p48 / no 2017 filing: use the 2019 report (p47) as t+1 |
| 1955_2020 | 15.9 (incl.) | 15.9 / 10.7 | p51 / 2019 report p47 |
| 1200_2015 | 0.5 (incl.) | 0.5 / 8.4 | p40 / no 2014 table: use the 2016 report (p40-43) |
| 1200_2017 | 44.9 (incl.) | 44.9 / 40.5 | p43 / 2016 report p40 |
| 1945_2022 | -13.84 (incl.) | -13.840 / -13.831 | p51 / 2021 report p49 |
| 1945_2023 | -4.997 (excl.) | -5.034 / -4.997 | p52 / 2022 report p51 |
| 1945_2024 | 5.264 (excl.) | 4.839 / 5.264 | p54 / 2023 report p52 |
| 4242_2021 | 9.493 (excl.) | find both | find the gross development table / 2020 report |
| 4242_2023 | -7.19 (excl.) | find both | find the gross development table / 2022 report |
| 2007_2015 | -2.0 (excl.) | 148.8 / -2.0 | p37 / no 2014 table: use the 2016 report (p35) as t+1 |

"incl." / "excl." says whether the adopted figure includes the older-years column now.

(The figures above are from scripts on the stored extraction; recompute both from the printed table yourself.)

## Output entry per record

`key`, `read_by`, `pages`, `layout` (rows are ages or calendar years; where the last two column cells sit),
`column_cells_t`, `column_cells_t_minus_1` (or t+1), `joining_year_cells`, `calendar_fit` (per cell residuals and the
factor), `age_fit` (per cell residuals), `filing_words` (quotes), `construction` (`calendar_restated` / `development_age`
/ `undeterminable`), `figure_including_m`, `figure_excluding_m`, `rule_figure_m`, `confidence` (high / medium / low),
`note`. Final message: one line per record.
