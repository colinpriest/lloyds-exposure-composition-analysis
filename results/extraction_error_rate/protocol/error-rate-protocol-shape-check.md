# Extraction error rate: a shape check of every stored triangle grid

Fifteenth amendment. Written 13 October 2026, from 21:09 (Brisbane, UTC+10, read from the clock), after the
triangle-table census (the fourteenth amendment, `error-rate-protocol-table-scan.md`) and before the check below is
run on any record. It is committed before the script that runs it, so the rule cannot be chosen to suit what the check
finds. Before this file was written only the stored grids' field names, label types and row lengths were surveyed
(which fields a grid carries, whether its labels are integers); no shape test was computed on any record. The earlier
protocols still govern everything this file does not change. This is a check, not a repair: it changes no record, no
register and no figure.

## Why this exists

The census of the fourteenth amendment asks whether the used table is the gross or the net one. It cannot see a grid
whose cells are the right table's but sit under the wrong underwriting years. 4444/2022 is such a grid: the extraction's
stored grid for its image-only gross table sits one underwriting year early. Its "2013" column is the filing's 2014,
its "2020" the filing's 2021, its 2022 column is empty, and the filing's 2013 is dropped. Recomputed over the labels up
to t-2, the raw figure +435.491m includes 2021's first-year development (+399.219m). The first sample found it, and two
readings registered the printed triangle's +34.9m (`data/pyd_confirmed_figures.json`). A label shift leaves the latest
diagonal unchanged, so the census's reconciliation passes such a grid (4444/2022 is in its class A).

The extraction's reader (`test_gemini._diagonal_cells` at extraction 713c77b) reads a grid whose columns' last cells
sit one row above the report-year diagonal "one row up throughout", as a table that starts one year later. That reading
gives 4444/2022's raw figure. The grid's shape is what tells such a reading apart from a correctly labelled one, and
only the filing's page can say which a flagged grid is.

## Population

**Q: every record of the working sample whose raw figure, or whose adopted figure, is triangle-sourced.** The working
sample is the 674 stems `adopted_model.load_sample` retains (draw four's frame). A figure's source is decided by
`draw_error_rate_fourth.figure_source` (as the fourteenth amendment decides it):

- the **adopted** figure on the brief `draw_error_rate_fourth.Loader.brief` builds, with the loader's registers applied
  (the 573 records of the fourteenth amendment's P);
- the **raw** figure on the same brief built with no register applied (the canonical model's own figure and route).

A record is in Q when either is "triangle". Records of the working sample outside Q are counted in the output with
their reason. Counted before this file was written (`survey_population.py`, a count of sources only):

| Raw route | Raw figure | Adopted figure | Records |
|---|---|---|---|
| `rag_triangle` | triangle | triangle | 551 (548 adopted on the route, 3 through the confirmed-figure register) |
| `code_triangle` | triangle | triangle | 7 (6 on the route, 1 through the register: 4444/2022) |
| `model_reading` | stated | triangle (the register's) | 15 |
| **Q** | | | **573** |

No record's raw figure is triangle-sourced while its adopted figure is stated, so Q is the fourteenth amendment's P.
For the 15 records whose raw figure is a model's reading the grid tested did not produce the raw figure; their S7 says
so, and they are all registered.

## The grid tested

The RAW stored grid: the grid the raw figure was computed from.

- raw route `rag_triangle`: the canonical model's `_rag_triangle` (else the first model's that has one, as the
  fourteenth amendment's `used_grid` does);
- raw route `code_triangle`: the `_claims_triangle` of the model the route's note names ("OVERRIDE from <model>
  triangle"), else the canonical model's;
- any other raw route (the adopted figure is triangle-sourced through a register): the grid the fourteenth amendment
  used for the record.

A grid's columns are underwriting years (`underwriting_years`); its rows are development ages, row 0 the end of the
underwriting year (`development_rows`). Trailing rows with no cell are dropped, as the reader drops them. A cell is
filled when it holds a number other than an exact zero (the reader reads a zero beyond the staircase as a dash; a zero
inside a column is not a development estimate either way). t is the report year.

## The tests

For each labelled column y <= t holding a filled cell, its diagonal row is e = t - y and its last filled row is L. A
column is **tested** when e is inside the grid (e < the number of rows). A tested column is *on* the diagonal
(L = e), *one short* (L = e - 1), *short* (L < e - 1) or *beyond* (L > e). A column's printed current estimate is the
grid's `current_estimate_row` value for it, where the grid stores one with one value per column.

Tests that set the class (a record fails when any fails):

- **S1, labels.** The labels are distinct integers, and no label later than t heads a column holding a filled cell.
- **S2, unlabelled values.** No row holds a filled cell in a position without a label.
- **S3, label gaps.** The labels run without a skipped year between the first and the last (a skipped year is a
  possible dropped year).
- **S4, a shifted staircase.** Over the tested columns, more are one short than on the diagonal (the grid reads one
  row up: labels one year early, or a lost first row), or more are beyond than on the diagonal (labels one year late).
- **S5, the 4444/2022 signature.** The grid labels year t, the year-t column holds no filled cell, and the year t-1
  column holds exactly one.
- **S6, a mature column off its diagonal.** A tested column with y <= t-2 is not on its diagonal, unless the grid's
  printed current estimate places it as the reader places it (it is beyond, and the printed estimate is the cell on
  row e; or it is one short, and a printed estimate stands in for the missing diagonal cell).
- **S7, reproduction.** The figure recomputed from the grid as the fourteenth amendment recomputes it (latest filled
  cell less the one before, over the labels up to t-2; at the scale, of 1, 1,000, 1,000,000 or 1/1,000, at which the
  grid reproduces the raw figure, else the stated units) equals the record's raw figure within the protocol's
  tolerance, max(0.5, 0.05 x |raw figure|).

A test reported beside the class and not setting it:

- **R1, the latest diagonal.** Where the census's deterministic run computed the grid's latest diagonal less the
  table's latest paid (`triangle-table-scan-deterministic.json`, `d_less_paid`) and its final run placed the filing's
  gross claims outstanding (`triangle-table-scan.json`, `co_g`), whether they agree within 2%. It does not set the
  class: a label shift leaves the latest diagonal unchanged, and an unreconciled diagonal is the census's class B or C,
  already listed for reading.

## The classes

- **pass**: every test S1 to S7 passes.
- **shape-fail**: one or more of S1 to S7 fails (a possible shift, or a grid that does not explain the figure). Each
  failing test is listed with its columns.
- **not checkable**, with the reason: no stored grid; no integer labels; fewer than two development rows; or no tested
  column.

Each shape-fail is then reported as **already registered** when its key is in `data/pyd_confirmed_figures.json` (the
adopted figure is the register's, read from the filing by two readings), and **open** otherwise (the adopted figure is
the grid's own).

## How the check is run

1. `scripts/scan_grid_shape.py`, deterministic and offline (`LLOYDS_EXTRACTION_OFFLINE=1`, no paid API, no network,
   no filing opened), reads the analysis copies of the records, the loader's registers and the census's two output
   files, and writes `grid-shape-check/grid-shape-check.json`: per record the grid tested, its raw and adopted figures
   and sources, each test's result with its columns, the class, and whether a shape-fail is registered or open.
2. Its checks (`scripts/checks_scan_grid_shape.py`) hold the positive control (4444/2022's raw grid is a shape-fail
   by S4 and S5, and already registered), known-good grids that must pass (records two readings found correct, their
   grids inspected), and the rule on synthetic grids. `scripts/mutate_scan_grid_shape.py` breaks the script on purpose,
   in a copy of the clone, and every break must turn the checks red.
3. For each open shape-fail, Claude reads the filing's page (its text layer, the OCR page cache or the page image) and
   records whether the grid is misaligned, with the printed cells and the figure the page supports. That reading is a
   first reading for the main session to send for two independent readings; it repairs nothing and registers nothing.

## What the check cannot say

- A pass says the grid's staircase is consistent with its labels. A grid whose every label and cell is shifted
  consistently with an extra or missing printed column of the same shape (for example a whole table one year late
  with year t dropped) can still pass S4; S1, S5 and S6 then carry it, and they may not.
- A shape-fail is a candidate. A table that genuinely starts one year later, or a run-off syndicate's table, can fail
  S4 or S6 with every cell in its place. It is not an error until the page is read and two readings settle the figure.

No other part of the protocol changes.
