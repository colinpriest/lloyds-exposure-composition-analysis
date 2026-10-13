# Extraction error rate: a census of the table each triangle-sourced figure was computed from

Fourteenth amendment. Written 13 October 2026, from 15:46 (Brisbane, UTC+10, read from `date`), after draw four was
scored and before the check below is run on any record. It is committed before the script that runs it, so the rule
cannot be chosen to suit what the check finds. The first protocol (`error-rate-protocol.md`) and draw four's
(`error-rate-protocol-fourth.md`) still govern everything this file does not change. This is a check, not a repair: it
changes no record, no register and no figure.

## Why this exists

Draw four (100 records of the 400 unread, `fourth-sample/error-rate-result-fourth.json`) found two errors, and both
are the same failure: the triangle step recomputed the prior-year development from the filing's NET claims
development table instead of the GROSS one.

- 1274/2023: the net table is on p36, headed "Net Claims", but its first row is labelled "Estimate of Incurred gross
  claims"; the gross table is on p35. Adopted +58.692 USD m; gross +87.073.
- 4472/2022: p53 prints both tables. The one used totals 2,346.0 in its estimated balance to pay, which is the net
  claims outstanding (note 13, p41); the other totals 3,851.9, the gross claims outstanding. Adopted -1.5; gross
  +122.3.

The readers told the tables apart by reconciling a table's own reserve total (or its latest diagonal) to the filing's
GROSS and NET claims outstanding at the report date. The same reconciliation exposes a faulty printed triangle:
4020/2017's printed gross triangle has a latest diagonal of 2,006,546 against the filing's own gross total claims of
1,935,876 (p42), because its older columns repeat the previous year's report shifted by one column.

On 13 October 2026 the author decided to run this check on every triangle-sourced record of the working sample, and
then to repair what it finds by draw four's rule (a figure is repaired only when two independent readings agree on the
gross figure). This file fixes the check. The repair is a later step and is not part of it.

## Population

**P: every record of the working sample whose adopted figure is triangle-sourced.** The working sample is the 674
stems `adopted_model.load_sample` retains from `model/exposure_results.json` at analysis commit de0e840 (the frame of
draw four). A figure's source is decided as draw four decides it (`draw_error_rate_fourth.figure_source`, which is
`score_error_rate.figure_source` with the `code_triangle` extension), on the canonical model with the loader's
registers applied (`draw_error_rate_fourth.Loader.brief`). Counted before this file was written:

| Route of the adopted figure | Records |
|---|---|
| `rag_triangle` carrying its triangle | 548 |
| `confirmed_figure` with `figure_kind` "triangle" (two readings confirmed it from a printed triangle) | 19 |
| `code_triangle` (the deterministic triangle's code override) | 6 |
| **P** | **573** |

The other 101 records of the working sample carry a stated figure and are outside this check.

Every record of P is checked, including records an earlier sample, census or draw four has already read and judged
correct. They are reported in the same classes, and each record's reading status is reported beside its class: in
draw four (its sample or its census stratum); read earlier (the records draw four's frame file lists as read, R); or
unread (the rest of draw four's frame F). A record already judged correct that lands in class B or C is reported as
such and is not reclassified by its earlier verdict.

## The used table

The used table is the printed table the adopted figure was computed from:

- `rag_triangle`: the canonical model's stored `_rag_triangle` grid (its page is the route's `triangle_source_page`);
- `code_triangle`: the canonical model's stored `_claims_triangle` grid;
- `confirmed_figure` (triangle): the table on the register's pages (`data/pyd_confirmed_figures.json`); the stored grid
  only locates it there.

For each record the script recomputes the adopted figure from the stored grid (latest diagonal less the one before,
over underwriting years up to t-2, in the grid's units, to millions) and records whether it reproduces the adopted
figure within the protocol's tolerance, max(0.5, 0.05 x |adopted|). A grid that does not reproduce it is still checked
(the table is what is being tested) and is listed.

The table is **located** in the filing by its cells: the page (or two consecutive pages) of the filing's text whose
numbers hold the most of the grid's distinct non-zero cells, and at least half of them and at least three. The text is
the PDF's text layer, or, for a page without one, the extraction's OCR page cache
(`pdf_extraction/ocr_page_cache/<stem>.json`). A report filed as HTML is read from its PDF conversion, as draw four's
page tool reads it. A table not located is class D.

## The totals compared

All in millions of the report's currency.

1. **The filing's gross and net claims outstanding at the report date**, CO_g and CO_n (31 December of the report
   year t). They are placed from the filing's claims outstanding note (the closing line of a gross / reinsurers' share
   / net movement, where gross less reinsurers' share is net) or its balance sheet (claims outstanding among the
   technical provisions, and the reinsurers' share of claims outstanding among the assets, net being their
   difference). A placement is anchored where relevant by the record's own adopted opening reserves, which are the
   gross claims outstanding at 31 December t-1: the line the closing figure is read from (or its movement table's
   opening line) must carry the adopted opening reserves within 2% in its earlier column or line. The next report's
   record, where one exists, gives a second anchor for CO_g (its opening reserves are this report's closing gross
   claims outstanding).
2. **The used table's own totals**: the amounts printed in the used table's block after its development rows, up to
   the next table's heading (its reserve, outstanding, balance to pay, liability, provision or total lines: each
   line's last amount, and the sum of its amounts), and its latest diagonal, D, the sum of the stored grid's latest
   cells.
3. **The filing's own total of latest estimates**, I_g and I_n, where the filing prints one for its gross and its net
   development (for example 4020/2017 p42, "Total claims 1,935,876 1,596,671"). The used table's latest diagonal D is
   compared with them.

## Tolerance

A total x **reconciles** to a figure y when |x - y| <= 0.02 |y| (the protocol's opening-reserves tolerance) and x is
nearer y than the other basis's figure. Gross and net are **indistinguishable** when CO_g and CO_n differ by 4% of CO_g
or less (twice the tolerance): a table that reconciles then cannot be told gross from net by this check.

## The classes

- **A, pass**: a used-table total reconciles to the gross figure (CO_g, or D to I_g) and none reconciles to the net
  figure only. A record whose gross and net are indistinguishable, and whose table reconciles to them, is A and listed
  as such.
- **B, net-table candidate**: a used-table total reconciles to the net figure (CO_n, or D to I_n) and none reconciles to
  the gross figure.
- **C, faulty or unreconciled**: the used table's totals and the filing's figures are both placed and no total
  reconciles to either; or the filing prints its own total of gross latest estimates (I_g) and the gross table's latest
  diagonal does not reconcile to it (as 4020/2017).
- **D, cannot be checked**, with the reason: the table is not located (an image page with no OCR text, or text the
  cells cannot be matched in); the table prints no total and the filing prints no total of latest estimates; the
  filing's claims outstanding cannot be placed; or the table reconciles to neither placed figure while CO_n cannot be
  placed (it could then be net or faulty); or a total reconciles to gross and another to net within one block.

## How the check is run

1. A deterministic script, `scripts/scan_triangle_tables.py`, offline (`LLOYDS_EXTRACTION_OFFLINE=1`, no paid API, no
   network), reads the analysis copies of the records, the filings, the OCR page cache and the next reports' records,
   and writes `triangle-table-scan/triangle-table-scan.json`: per record the used table's grid, its recomputation, the
   pages it was located on, the totals placed and where, each comparison, the class and the reason.
2. Where the script cannot place a total (an image page, an ambiguous layout, a total printed as text), Claude may read
   the page (its text, or its image) and place the total by eye. Each such placement is recorded in
   `triangle-table-scan/eye-placements.json` with the record, the total, its page and the cells or text that give it,
   and the class is then computed by the same rule from the placed totals. Every record so placed is marked as placed
   by eye in the output.
3. Its tests (`scripts/checks_scan_triangle_tables.py`) include the positive controls, which must land as stated:
   1274/2023 and 4472/2022 in class B, and 4020/2017 in class C. A rule change that moves a control out of its class
   fails the tests. Each test is broken on purpose to see it fail.
4. The script, its tests and its output are committed with `MANIFEST.json` rebuilt. Nothing is repaired, and no
   register changes.

## What the check cannot say

- A table that reconciles to gross can still be read in the wrong cells or the wrong years; that is outside this check.
- The 2% tolerance can miss a gross table whose total excludes, for example, the claims handling provision or a
  discount, which lands in C or D, not in A. Every B and C record is listed for reading, so a miss of that kind costs a
  reading, not a wrong repair.
- A record in B or C is a candidate. It is not an error until two readings settle the gross figure.

No other part of the protocol changes.

## Implementation note 1, 13 October 2026 (written 16:31, Brisbane), after the script's deterministic runs and before any eye placement

1. `scripts/scan_triangle_tables.py` was written after the rule was committed (7feecbb) and run nine times on the
   population while its text parsing was corrected. The rule (the population, the totals compared, the 2% tolerance,
   the 4% indistinguishability line and the classes) did not change. The corrections were to how the script reads a
   page: a label wrapped over two or three lines (above or below its amounts); two tables stacked close together; a
   gross / reinsurers' share / net line under a table (bound to neither basis, as the rule says for a line printing
   both); a grid whose stated units are wrong (its scale is the one at which it reproduces the adopted figure); a paid
   row or an underwriting year's row is never a total; and the claims outstanding placed from the right lines of the
   balance sheet. The first run put 16 records in B; 11 of them were such parsing faults (a gross / reinsurers' share
   / net line read as a net total, or the sum of a row that is not a total), which is why every B, C and D record is
   read before it is reported.
2. One of "the used table's own totals" is computed rather than printed: the table's latest diagonal less its latest
   cumulative paid, which is the reserve the table itself states, where the table prints a paid row (or a paid amount
   at the end of each underwriting year's row) covering exactly the grid's underwriting years. A paid row covering
   other years (a prior-years column the grid does not store) is not used. It is compared with CO_g and CO_n and with
   the gross and net columns of a gross / reinsurers' share / net line under the table. The readers of draw four
   used the same reconciliation ("latest diagonal minus paid").
3. The checks (`scripts/checks_scan_triangle_tables.py`, 26, all passing, none skipped) hold the three controls on the
   real filings (1274/2023 and 4472/2022 in B, 4020/2017 in C) and the rule on synthetic totals.
   `scripts/mutate_scan_triangle_tables.py` breaks the script 14 ways in a copy of the clone; every break turns the
   checks red.
4. The deterministic result before any eye placement is kept as `triangle-table-scan/triangle-table-scan-deterministic.json`.
   Every record in B, C or D is then read (its text, or its page image) and any total placed by eye is recorded in
   `triangle-table-scan/eye-placements.json`, with a reading of whether the used table is the gross or the net one.

No other part of this protocol changes.
