# Reading brief: restored mature-cohort triangle figures (BAJ paper, Lloyd's syndicate filings)

Out of scope, always: the paper's AI declaration and anything about AI use. Do not touch it.

## Why these records

The paper's outcome (its Equation 1) is the prior-year movement on MATURE underwriting years only:
M = sum over underwriting years u <= t-2 of (the latest estimate at report year t) less (the estimate at t-1), gross of
reinsurance, in the report's currency. The extraction pipeline sometimes replaced a mature-cohort triangle figure with
a broader figure (the provisions note's "movement arising from prior years", or the models' reading) only because the
two had opposite signs. Both can be correct: a stated all-prior-years line also includes year t-1's own development.
The author has decided that a valid mature-cohort triangle figure is never replaced for its sign alone. Each record
below gets its triangle figure back (or enters the working sample for the first time). Before any refit, a reader must
check each one on the filing's own pages.

## Your material

- Your batch: `D:/tmp/r62/oc/readings/<your reader id>/batch.json`, a list of records. For each: `key` (syndicate_year),
  the figure it carries now (`current_figure_report_ccy`, `current_route`), the restored triangle figure
  (`triangle_figure_report_ccy`, millions of the report currency), the triangle's page (`triangle_page`), its
  underwriting years, the deterministic census class and numbers (`reconciliation_class_deterministic`, `CO_g`, `CO_n`,
  `table_latest_diagonal`, `shape_check`), `flags`, `vetoed_figures`, `provisions_gross_prior_year`, the filing
  (`filing_pdf`), suggested pages (`pages_to_read`) and `what_to_check`.
- The stored grid the triangle figure was computed from: `D:/dev/lloyds_reserve_stress_testing/pdf_extraction/<stem>.json`
  where stem is `syndicate_<key>`, under `models.<model>._rag_triangle` (`development_rows`: rows are development ages,
  columns underwriting years; `units`; `source_page`), or `_claims_triangle` for a code triangle. Read only.
- The page text tool (text layer, or Tesseract OCR for a scanned page; writes nothing):
  `C:/Python312/python.exe D:/tmp/r62/pub4/results/extraction_error_rate/scripts/filing_pages.py <stem> <pages...>`
  or `... <stem> --find "<regex>"` to find pages. If it cannot find the filing, read the PDF at `filing_pdf` with
  PyMuPDF (`import fitz`) yourself.
- Page images: `C:/Python312/python.exe D:/tmp/r62/scan/eye/render.py <stem> <pages...> [--dpi 130] [--clip x0 y0 x1 y1]`,
  then Read the PNG it prints. Use an image whenever the text layer or OCR is garbled, the page is scanned, or the
  table layout is ambiguous. Say what you read (text layer, OCR, page image).

## For each record, check on the filing

1. **Recompute** the mature-cohort gross movement from the PRINTED gross development table: for every underwriting year
   u <= t-2, the latest estimate (at report year t) less the previous one (at t-1); sum them; report in millions of the
   report currency. Note any "X and prior" column and whether its last two diagonal entries are like for like (same
   years covered). Say whether your figure equals `triangle_figure_report_ccy` (within 0.5m or 1%).
2. **Basis**: is the table gross of reinsurance? Quote its heading.
3. **Table validity**: does the table's latest diagonal (or its printed reserve total) reconcile to the filing's gross
   claims outstanding / gross total of latest estimates (within 2%)? Does any column repeat the previous report's
   triangle shifted by a column? Is any column one row short of the diagonal?
4. **Transactions**: is there a reinsurance to close (RITC) received, a portfolio transfer or a take-on in year t that
   moves the prior-year figures (look in the notes for RITC / transfer / acquisition wording)? Quote it.
5. **Cohort coverage**: the stated prior-year line (the provisions note's "movement arising from prior years" or
   similar), if printed: its value, and the stated line less your triangle figure (how much is year t-1 or other scope).
6. **Verdict** (one of):
   - `confirmed`: the printed gross table gives this mature-cohort figure (within tolerance), the table is valid;
   - `differs`: the printed gross table gives a different mature-cohort figure (give it, with the cells);
   - `table_invalid`: the table cannot be the measure (net, faulty, does not reconcile, shifted), with evidence;
   - `transaction`: the figure is moved by an RITC/transfer/take-on in year t (with the wording);
   - `undeterminable`: you cannot decide from the pages (say why).

## Rules

- Read only. Never edit anything under `D:/dev/` or `D:/tmp/r62/pub4/`. Write only in your own folder
  `D:/tmp/r62/oc/readings/<your reader id>/` (renders may go under `renders/` there; pass `--out` if the render script
  supports it, else copy). Do not read any other reader's folder: the readings must be independent.
- No paid API, no network. Do not kill processes. Never `cd` in Bash; use absolute paths. Write scripts with the Write
  tool, never with heredocs. Write files as UTF-8 with LF endings.
- Never invent a number: every figure comes with its page and the verbatim cells or label that give it.
- After EVERY record, rewrite your whole JSON output file `readings.json` (a dict key -> entry) and append one line to
  `log.txt`, so your work survives if you are stopped. You may be stopped after about 8 turns; work record by record,
  and when resumed continue from the first record not in `readings.json`.

## Output entry

```json
{
 "1861_2020": {
  "read_by": "text layer and page image",
  "pages": [41, 42],
  "table": {"page": 41, "heading": "Gross claims development (£000)", "basis": "gross"},
  "recomputed_mature_figure_m": 357.2,
  "matches_restored": true,
  "cells": "2017 col: 1,204,511 -> 1,330,105 ... (u <= 2018)",
  "x_and_prior": "'2010 & prior' last two diagonals 707,993 / 711,896, like for like",
  "reconciliation": "latest diagonal less paid 512.4 vs gross claims outstanding 509.8 (p55): within 2%",
  "shift_or_short_column": "none",
  "transaction": "none found" ,
  "stated_prior_year_line": {"value_m": 7.9, "page": 23, "quote": "...", "stated_less_triangle_m": -349.3},
  "verdict": "confirmed",
  "note": "..."
 }
}
```

Finish with a short summary in your final message: per record, the verdict and the recomputed figure.
