# Eye reading brief: the triangle-table census (BAJ paper, Lloyd's syndicate filings)

Out of scope, always: the AI declaration of the paper and anything about AI use. Do not touch it.

## What the census is

Each record below is a Lloyd's syndicate report (syndicate S, report year t) whose adopted prior-year development
figure was computed by the extraction pipeline from a claims development triangle printed in the filing (the "used
table"). The pipeline sometimes used the filing's NET development table instead of the GROSS one. The census checks
each record by reconciling the used table's own totals with the filing's gross and net claims outstanding at
31 December t:

- CO_g, CO_n: the filing's gross and net claims outstanding at 31 December t (millions of the report currency);
- the used table's totals: the reserve / outstanding / balance-to-pay / liability / provision total the table prints
  (including a prior-years line or column when the table prints one), or the table's latest diagonal less its latest
  cumulative paid when both are printed for the same underwriting years;
- I_g, I_n: a total of latest estimates (incurred) the filing prints for gross and net, compared with the used table's
  latest diagonal D.

The rule (already committed, do not change it): a total reconciles when within 2% and nearer than the other basis.
A = reconciles to gross; B = to net only; C = placed but reconciles to neither, or D fails the filing's own I_g;
D = cannot be checked. Gross and net within 4% of each other are indistinguishable (A).

A deterministic script already ran. The records given to you are the ones it put in C or D (or, for some, where its
placement may be wrong). Your job: read each record's pages and (1) say whether the used table is the filing's gross
table, its net table, a faulty table, or unclear, with evidence; (2) where the script failed to place a total that the
filing does print, place it; where it placed a wrong figure, correct it. You do NOT decide the class: the class is
computed afterwards by the same rule from what you place.

## Your material

- `D:/tmp/r62/scan/eye/batch-*.txt`: per record, the script's numbers (adopted figure, grid recomputation, D = the
  stored grid's latest diagonal in millions, paid, R = D less paid, CO_g / CO_n and the lines they were read from,
  the located page) and the text lines of the located page(s) and the next page (lines with amounts or with
  gross/net/total/paid words). A `####` header starts each record.
- The page tool (text layer, or Tesseract OCR for a scanned page):
  `python D:/tmp/r62/scan/A/results/extraction_error_rate/scripts/filing_pages.py <stem> <pages...>` or
  `... <stem> --find "<regex>"` to find pages. Page numbers are the PDF's own, from 1. It writes nothing.
- The page images: `python D:/tmp/r62/scan/eye/render.py <stem> <pages...> [--dpi 130] [--clip x0 y0 x1 y1]`, then
  Read the PNG it prints. Use images whenever the text layer or the OCR is garbled, the page is scanned, or the
  layout is ambiguous. Say in your entry what you read (text layer, OCR, or image).
- The record itself (the stored grid the figure was computed from): `D:/tmp/r62/scan/A/pdf_extraction/<stem>.json`,
  under `models.<model>._rag_triangle` (`development_rows`: rows are development ages, columns underwriting years;
  `units`; `source_page`). The canonical model is the alphabetically first key in `models` when
  `validation.passed` is true. For a `code_triangle` route the grid is `_claims_triangle`.

## Rules

- Read only. Never edit anything under `D:/dev/` or `D:/tmp/r62/scan/A/`. Write only your own two output files in
  `D:/tmp/r62/scan/eye/` (named in your task) and renders in `D:/tmp/r62/scan/eye/renders/`.
- No paid API, no network. Do not kill processes. Never `cd` in Bash; use absolute paths. Write scripts with the Write
  tool, never with heredocs. Write files as UTF-8 with LF endings (Python: `io.open(path, "w", encoding="utf-8",
  newline="\n")`).
- Never invent a number: every figure you place comes with its page and the verbatim cells or label that give it.
- Do not place a figure to force a class. Place what the filing prints for the used table, nothing else.
- Units: give placed values in MILLIONS of the report's currency (a table in £'000 printing 498,500 is 498.5).
- After EVERY record, rewrite your JSON output file (the whole dict so far) and append one line per record to your
  log file, so your work survives if you are stopped. You may be stopped after about 8 turns; work record by record.

## Output: a JSON dict, stem -> entry

```json
{
 "syndicate_1218_2017": {
  "read_by": "text layer" | "OCR" | "page image" | "text layer and page image",
  "pages": [38, 15],
  "used_table": {"page": 38, "basis_by_eye": "gross" | "net" | "faulty" | "unclear",
                 "evidence": "heading 'Gross of reinsurance'; its cells match the stored grid; its total 'Total gross provision included in the balance sheet 498,500' equals the balance sheet's gross claims outstanding"},
  "placements": {
    "cands": [{"value": 498.5, "page": 38, "line": "Total gross provision included in the balance sheet 498,500"}],
    "d_less_paid": null
  },
  "gross_table": {"page": 38, "where": "the first table on the page"},
  "note": "Estimated balance to pay 351,348 excludes the 2010 & prior row (147,152); the table's own total is 498,500."
 }
}
```

Keys of `placements` (all optional; omit `placements` entirely if you place nothing):
- `cands`: the used table's own totals you read (each with value in millions, page, verbatim line). When given, they
  REPLACE the script's candidates entirely, so list every total the used table prints that you want compared
  (usually just its full reserve total).
- `d_less_paid`: a number, or `null` to remove the script's figure when it covers fewer years than the table's
  printed total (e.g. it omits the prior-years row the table prints) or is otherwise not the table's reserve.
- `co_g`, `co_n`: only to correct the script's figure when it is wrong (give page and quote in `note`).
- `i_g`, `i_n`: a filing's total of gross / net latest estimates, when printed.
- `located`: `true` with the page in `used_table`, when the script could not locate the table but you can; `false`
  if you cannot find it either (say why in `note`).
- `both_bases_lines`: `[]` to remove gross/net lines the script wrongly bound under the table.

`gross_table`: where the filing's gross development table is, when the used table is NOT it (or "none printed").
`note`: anything that matters: a scope difference (prior years, claims handling provision, unearned portion, pure
year), a faulty or inconsistent table (its latest diagonal does not reconcile to its own totals; columns repeat the
previous year's report), an OCR digit you corrected and how you know.

Finish with a short summary in your final message: per record, basis_by_eye and what you placed.
