# Cohort-depth input gaps: audit of the 62 records left out

Scope: pre-submission-fixes.md section 1.4. Read only: analysis `D:/tmp/r62/oc/A` (branch oc, head 9c227e7a),
extraction `D:/tmp/r62/finalv/E` (713c77b3), filings from `D:/tmp/r62/finalv/Efull/syndicate_reports/pdfs`
(E holds no PDFs). LLOYDS_EXTRACTION_OFFLINE=1, no API, no network. Out of scope: the AI declaration.
Decisions recorded here are decisions of the Claude analysis session (sub-agent), not the owner's.

Scripts (this folder): `diag19.py` (the 19, every stored grid at t-2 and t-3, the registers),
`diag43.py` (the 43, and every kept record whose u <= t-3 figure has no non-zero step), `show19.py`.

## Turn 1 (2026-10-26 12:01 Brisbane): the record

`results/check_cohort_depth_sensitivity_results.json`: n_primary 643, kept 581, left out 62:
`figure_not_reproduced_from_a_stored_grid` 19, `no_figure_at_t_minus_3` 43, the other two reasons 0.

### Why all 19 fail: the primary figure is a register figure, not a stored grid's

Every one of the 19 takes its primary figure from a register whose figure no stored grid computes:
`data/mature_cohort_figures.json` CORRECTIONS (5: 318/2024, 1274/2016, 1609/2024, 2232/2020, 4242/2022) or
`data/pyd_confirmed_figures.json` (14). `check_cohort_depth_sensitivity.reproduce` tries only the stored
grids (`_rag_triangle`, `_claims_triangle` of every block), so a register-corrected figure can never
reproduce. The fault class per record:

| record | register | stored grid's fault |
|---|---|---|
| 1274/2016 | CORRECTIONS (derived misprint) | misprinted 2012 cell 141,355 (p41) |
| 1274/2022 | confirmed | RAG grid is the net table (p37); gpt-5-mini claims grid is the gross p36 table shifted one column, 2013 dropped |
| 1609/2023 | confirmed | table printed transposed |
| 1609/2024 | CORRECTIONS | table labels transposed (p51) |
| 1991/2018 | confirmed | estimator refuses the grid (an "After six years" row of non-staircase cells) |
| 2232/2020 | CORRECTIONS (previous-report base) | 2020 table restates the end-2019 diagonal |
| 318/2024 | CORRECTIONS | table printed transposed (p69) |
| 3334/2018 | confirmed | no stored grid (image-only p47) |
| 3500/2018 | confirmed | estimator refuses the grid (dash rows dropped) |
| 382/2015-2020 (6) | confirmed | incremental (movement) table; estimator refuses negative cells |
| 4242/2022 | CORRECTIONS (previous-report base) | 2022 table lowers 2019 and 2020 end-2021 cells |
| 4444/2022 | confirmed | grid misaligned one column (labels +1), true 2013 dropped |
| 4472/2022, 4472/2023 | confirmed | RAG grid is the net table of p53 |

None is a units or "& prior" column fault. No stored grid of these 19 carries the register's figure.

### The 43: none is an empty sum turned zero

All 43 stored grids hold exactly three underwriting years, t-2, t-1 and t, so u <= t-3 is empty and the
estimator returns "no usable UW years in triangle"; the depth script leaves each out (no zero is written).
27 of the 43 are syndicates whose inception (data/syndicate_inception_years.json) is t-2 or later: absent by
construction (1991/2015 among them, inception 2013 = t-2). 16 have an inception at or before t-3, so the
filing may print older cohorts the grid does not hold: 1200/2023, 1301/2023, 1416/2024, 1861/2019,
1910/2023, 1955/2021, 2007/2018, 2015/2020, 2468/2018, 2689/2022, 2880/2024, 3902/2019, 4000/2021,
6103/2015, 6103/2023, 6123/2019. To be read (turn 2).

Kept records whose u <= t-3 figure is zero: 1796/2024 (one step, 14.0 - 14.0: an observed zero) and
5678/2016 (two all-zero columns, 2012 and 2013, "PYD=0": to be checked against the filing, turn 2).

## Turn 2 (2026-10-26 12:13 Brisbane): the filings, the 19 classified, the empty sums

Note: another session committed three test-only commits to `D:/tmp/r62/oc/A` at 12:04 (head now fe348d46).
None touches the depth script, its record, `data/pyd_confirmed_figures.json`, `data/mature_cohort_figures.json`
or `build_mature_cohort_figures.py` (git diff 9c227e7a..HEAD on those paths is empty). This audit wrote nothing there.

Filing pages read (text layer with PyMuPDF; image pages rendered and read; HTML filings through
`Efull/pdf_extraction/html_converted`; 3500/2018 through E's OCR page cache). Page numbers are 1-based PDF pages.
`terms19.py` holds every term below and checks that the terms over u <= t-2 give the register figure and, after the
loader's FX, the primary GBP figure to the depth script's own tolerance: all 19 reproduce.

### The 19, classified

Figures in millions of the report's currency; GBP after the loader's rate. "t-3" is the sum over u <= t-3.

| record | cur | primary (u<=t-2) | t-3 figure | t-3 GBP | S t-2 | S t-3 | class |
|---|---|---:|---:|---:|---:|---:|---|
| 1274/2016 | USD | 22.6943 | 12.0693 | 9.7830 | 0.0475 | 0.0253 | recoverable; rests on the register's DERIVED 2012 cell |
| 1274/2022 | USD | 8.960 | 27.851 | 23.0612 | 0.0083 | 0.0259 | recoverable |
| 1609/2023 | USD | 8.834 | none | - | 0.0994 | - | not recoverable: no cohort u <= 2020 exists |
| 1609/2024 | USD | 13.935 | 13.628 | 10.8841 | 0.0688 | 0.0673 | recoverable |
| 1991/2018 | GBP | 42.675 | 4.085 | 4.085 | 0.3975 | 0.0380 | recoverable |
| 2232/2020 | GBP | 19.331 | 3.442 | 3.442 | 0.0488 | 0.0087 | recoverable (two-report base, rule 3) |
| 318/2024 | GBP | -27.990 | -18.177 | -18.177 | -0.1289 | -0.0837 | recoverable |
| 3334/2018 | GBP | 5.109 | -0.014 | -0.014 | 0.0648 | -0.0002 | recoverable, thin (one cohort) |
| 3500/2018 | GBP | -0.408 | -0.408 | -0.408 | -0.0095 | -0.0095 | recoverable, thin (one cohort; t-3 = t-2) |
| 382/2015 | GBP | 2.626 | 3.649 | 3.649 | 0.0112 | 0.0155 | recoverable |
| 382/2016 | GBP | -14.328 | -21.278 | -21.278 | -0.0574 | -0.0852 | recoverable |
| 382/2017 | GBP | 7.401 | 9.677 | 9.677 | 0.0216 | 0.0282 | recoverable |
| 382/2018 | GBP | 24.988 | 20.300 | 20.300 | 0.0587 | 0.0477 | recoverable |
| 382/2019 | GBP | 12.549 | -9.557 | -9.557 | 0.0254 | -0.0194 | recoverable |
| 382/2020 | GBP | 29.620 | 18.953 | 18.953 | 0.0614 | 0.0393 | recoverable |
| 4242/2022 | USD | -80.015 | -54.343 | -44.9971 | -0.1926 | -0.1308 | recoverable (two-report base, rule 3) |
| 4444/2022 | GBP | 34.900 | 9.387 | 9.387 | 0.0176 | 0.0047 | recoverable |
| 4472/2022 | GBP | 122.3 | 97.6 | 97.6 | 0.0372 | 0.0297 | recoverable |
| 4472/2023 | GBP | 311.2 | 73.2 | 73.2 | 0.0808 | 0.0190 | recoverable |

No primary figure is in doubt on this reading: every one is the sum of printed cells two earlier readings
quoted, and each u = t-2 cell dropped for t-3 was found on the page. 1274/2016 is the one whose t-3 figure
leans harder on a judgement: its corrected cell (2012 cohort) is u = t-4, so the derivation is 9.254 of the
12.069 (77%); the register's other defensible factors (0.96766 to 0.98919) give 11.18 to 15.03m USD at t-3.

### Evidence per record (page, cells)

- **1274/2016** p41 (printed 39), gross, USD 000. 2012 column "Three years later 141,355", "Four years later
  185,418" (the misprint). Other u <= 2013 terms: 2008 208,456-209,137 = -681; 2009 165,974-165,410 = +564;
  2010 208,906-206,415 = +2,491; 2011 178,142-174,535 = +3,607; 2013 180,767-183,933 = -3,166. 2012 term on the
  register's corrected cell 178,987 x 129,350/131,423 = 176,163.7: +9,254.3. t-3 = +12,069.3. Why no grid
  reproduces: every stored grid carries the misprinted 141,355 (gives 57.503).
- **1274/2022** p36 (printed "Page 34 of 43"), "Gross Claims / Estimate of incurred gross claims", USD 000: 2013
  180,742 -> 179,555; 2014 231,152 -> 228,328; 2015 234,187 -> 238,958; 2016 504,727 -> 494,736; 2017 484,033 ->
  485,745; 2018 416,498 -> 446,405; 2019 372,154 -> 377,617 (t-3 = +27,851); 2020 279,086 -> 260,195 (-18,891).
  Why: the RAG grid of both blocks is the p37 NET table (41.013); gpt-5-mini's `_claims_triangle` holds the gross
  cells one column off (its "2013" is 2014), dropping 2013 (122.749). "2012 & prior" prints one cell (946,246).
- **1609/2023** p41 (printed 38): "Underwriting year 2021|2022|2023 ... At end of first underwriting year
  16,028|57,866|66,700; One Year Later 32,794|108,475; Two Years Later 44,451". Printed transposed (register):
  UW2021 = 16,028, 57,866, 66,700, so t-2 = 66,700-57,866 = +8,834. Only 2021-2023 exist (inception 2021,
  `data/syndicate_inception_years.json`): u <= 2020 is empty. NOT recoverable; it belongs with the
  no-deeper-cohort records, and must never be 0.
- **1609/2024** HTML filing, converted p51 (printed 48): "At end of first underwriting year
  15,865|32,368|43,731|57,359; One year later 57,296|107,236|107,543; Two years later 66,053|118,174; Three years
  later 54,930". Rows are underwriting years (CORRECTIONS; Z5, Z6, Q2). t-3 = UW2021 57,359-43,731 = +13,628.
  Stored grids read the printed labels (-0.185; t-3 -11.123).
- **1991/2018** p30 (printed 29), "Gross claims development as at 31 December 2018", GBP 000: 2013 "After five
  years" 25,912 -> "After six years" 28,621 (+2,709); 2014 42,715 -> 44,725 (+2,010); 2015 60,761 -> 60,127
  (-634); 2016 39,226 -> 77,816 (+38,590). t-3 = +4,085 (3.80% of R, the figure small-book-tail-understatement.md
  gives). The "After six years" line also prints 16,410|17,235|8,583|16, not staircase cells (gross reserves
  reconcile without them: 28,621-19,689 = 8,932), and the estimator refuses both stored grids for it. This is the
  1991/2018 case Codex cites: the stored grid is unavailable, the economic information is printed.
- **2232/2020** 2020 p49 latest cells 2013 56,258; 2014 85,063; 2015 158,133; 2016 145,208; 2017 232,763; 2018
  181,451. 2019 report p47 (image, E OCR cache) latest cells 57,184; 84,610; 151,959; 151,417; 228,813; 165,562.
  Terms -926, +453, +6,174, -6,209, +3,950 (t-3 = +3,442), +15,889. Stored grids difference the 2020 table's own
  restated end-2019 diagonal (55.227).
- **318/2024** HTML filing, converted p69 (printed 66), GBP 000, rows are underwriting years (CORRECTIONS; P5, Q4):
  end-2023 -> end-2024: 2015 76,533 -> 76,033; 2016 149,610 -> 148,503; 2017 267,819 -> 265,595; 2018 145,148 ->
  142,194; 2019 107,483 -> 105,208; 2020 140,095 -> 136,462; 2021 111,992 -> 106,508 (t-3 = -18,177); 2022
  137,010 -> 127,197 (-9,813). Stored grids read the printed labels (-67.098).
- **3334/2018** p47 (image, read here): "Gross insurance contract outstanding claims provision as at 31 December
  2018": 2015 "1,152 | 2,332 | 2,038 | 2,024"; 2016 "16,552 | 44,893 | 50,016". t-3 = 2015 only: 2,024-2,038 =
  -14 (the 2017 report p47 prints 2015 at 2,036, giving -12). The 2011-2014 run-off years left by external RITC
  effective 31 December 2017 and are not in the table (nor in R, 78.79 = 116,772-37,982). No stored grid exists.
- **3500/2018** p24 (image; E OCR cache): columns "2009 2018 Total" only; 2009 eight years later 1,185, nine
  years later 777 (current estimate 777). No cohort 2010-2017 exists, so u <= 2015 = {2009} and t-3 = t-2 =
  -408. Stored grids are refused (the two dash rows dropped).
- **382/2015-2020** incremental (movement) tables, "Claims development table gross of reinsurance", GBP 000. The
  u = t-2 cell dropped for t-3, each on the page's "Two years later" row: 2015 p46 2013 "(1,023)"; 2016 p46 2014
  "6,950"; 2017 p47 2015 "(2,276)"; 2018 p46 2016 "4,688"; 2019 p46 2017 "22,106"; 2020 p47 2018 "10,667". The
  estimator refuses every stored grid ("the column holds negative values ... not cumulative estimates").
- **4242/2022** 2022 p44: 2017 "Five Years Later 331,324", 2018 "Four Years Later 233,193", 2019 "Three Years
  Later 187,713", 2020 "Two Years Later 284,422"; 2021 report p46 latest: 2017 349,613; 2018 249,006; 2019
  207,954; 2020 310,094. t-3 = -18,289-15,813-20,241 = -54,343. The "2016 & Prior" column (u <= t-3) is the merged
  column the readers found unreadable as a cohort; it is out at t-2 and stays out at t-3.
- **4444/2022** p27 (image, read here), "Gross of reinsurance", GBP 000: 2013 "Eight years later 486,013",
  "Nine years later 484,641"; 2014 568,628 -> 567,990; 2015 734,058 -> 741,648; 2016 861,281 -> 868,960; 2017
  1,089,417 -> 1,099,025; 2018 899,889 -> 916,705; 2019 683,114 -> 652,818 (t-3 = +9,387); 2020 587,818 ->
  613,331 (+25,513). The stored grid is one column off (its "2013" is 2014) and drops 2013 (435.491).
  "2012 & prior" prints one cell (3,597,051): no step.
- **4472/2022, 4472/2023** p53, the first (gross) of two tables, GBP m. 2022: 2013 765.5 -> 763.5; 2014 919.5 ->
  893.2; 2015 941.6 -> 947.1; 2016 1,097.0 -> 1,100.3; 2017 1,533.2 -> 1,547.9; 2018 1,385.1 -> 1,448.5; 2019
  918.0 -> 957.0 (t-3 = +97.6); 2020 705.9 -> 730.6. 2023: 2014 854.3 -> 862.4; 2015 902.4 -> 891.8; 2016 1,046.1
  -> 1,071.9; 2017 1,466.8 -> 1,501.2; 2018 1,372.6 -> 1,391.4; 2019 908.9 -> 890.3; 2020 696.3 -> 711.6 (t-3 =
  +73.2); 2021 946.9 -> 1,184.9. Both stored grids are the second (net) table. "2012/2013 and prior" print no
  development cells.

### The 43 and the empty sums

- All 43 stored grids hold only u = t-2, t-1, t. The depth script leaves each out with "no usable UW years in
  triangle"; none gets a zero. 27 are syndicates whose first underwriting year is t-2 or later (1991/2015 among
  them: inception 2013). The other 16 have an earlier inception; I read all 16 filings' tables (text layer for
  12, rendered images for 1301/2023 p70, 2007/2018 p29, 6123/2019 p35, HTML for 2880/2024): every one prints only
  the three open years. Two say why: 6123/2019 p35 "The SPA's closed year of accounts do not feature in the above
  tables as they have reinsured to close into the Host"; 6103/2023 p58, older years are reinsured to close into
  Syndicate 2791. Older cohorts are absent from these filings, not lost by the extraction: keep all 43 ineligible.
- `scan_empty.py` over every reproduced record at both depths: one figure is an empty sum returned as zero.
  **5678/2016 (kept, Q1, R 87.761m)**: its u <= t-3 figure 0.0 is the estimator's "all-zero column (no claims
  activity), PYD=0" for 2012 and 2013, whose columns print no cell at all (p41, printed 39: the 2012 and 2013
  columns are blank in every development row and "-" in the provision row; the syndicate began in 2014). This is
  exactly the empty sum Codex warns of, and it sits in the 581 today. It must leave the depth sample
  (no_figure_at_t_minus_3). Nine other records have empty columns beside real steps (harmless). No u <= t-2 figure
  is an empty sum. 1796/2024's t-3 zero is a printed 14 -> 14 step (observed). 1840/2022's primary 0.0 (one of
  the 43) is printed "-" to "-" in a column that printed 18 at end of year (p39): an observed nil.
- The 9 kept records whose primary is a pyd_confirmed_figures.json figure that a stored grid happens to reproduce
  (`kept_conf.py`): every grid's per-cohort cells match the register's quoted cells, so their t-3 figures are
  sound.

## Turn 3 (2026-10-26 12:20 Brisbane): the repair path

### Where the 19 figures come from, and so where the correction belongs

Chain: extraction `pdf_extraction/syndicate_*.json` (stored grids) -> copied into the analysis at the extraction pin
-> `src/run_analysis.py` load_and_classify adopts the route figure, then `data/pyd_confirmed_figures.json`
(apply_confirmed_figure: 14 of the 19) and `data/mature_cohort_figures.json` (apply_mature_cohort_figure, built by
`src/build_mature_cohort_figures.py` from its CORRECTIONS: 5 of the 19) -> `model/exposure_results.json` (each
observation carries `pyd_basis_source` "confirmed-figure:register" or "mature-cohort-figure:register") -> the depth
script, which reads the observations, the stored grids, and `data/mature_cohort_figures.json` only to name a model.

The primary's figure for all 19 is a register decision; the stored grids are faithful transcriptions of a table the
registers overrule (transposed, net, one column off, incremental, restated base, misprint) or are missing. So the
correction belongs in the registers, as the per-cohort cells each register figure is the sum of. Nothing in the
extraction needs to change, and no primary figure moves.

Options (decision for Colin; see the final report):

- **A. Terms in the two existing registers (recommended).** Each triangle-kind entry of
  `data/pyd_confirmed_figures.json` gains `cohort_cells` ({u: [previous cell, latest cell]} or {u: movement} for an
  incremental table; unit; page; the year t-1 report's page for a rule-3 base), and each CORRECTIONS entry of
  `build_mature_cohort_figures.py` gains the same, written into `data/mature_cohort_figures.json` by `--write`
  (2232 and 4242 already hold the readers' terms; 318, 1609 and 1274 hold cells in the readings). A loader or
  register test asserts, for EVERY triangle entry (not only these 19), that the cells over u <= t-2 sum to
  figure_m at the table's rounding and that every cell string appears in the entry's quote or archived reading
  (gates-must-generalise). Strengths: one source per record, beside the figure and its readings; the primary's
  loader can check its own figures. Weaknesses: touches two files the primary loader reads, so the change must be
  shown not to move `model/exposure_results.json` (byte-identical) and the register test suite must be rerun.
- **B. A depth-only register** (`data/cohort_depth_terms.json`, each entry naming the register and figure it
  decomposes). Strengths: the primary's inputs are untouched. Weaknesses: a second copy of evidence the registers
  already hold, which can drift; it still moves the run id (every tracked file is in reproduce.py's inputs digest).
- **C. Correct the stored grids in the extraction** (transpose 318/1609, de-cumulate 382, regrid 4444 and 1274/2022,
  swap to the gross table for 4472, composite two reports for 2232/4242, insert the derived cell for 1274/2016,
  transcribe 3334 from the image). Not recommended: four of the corrections would be synthetic grids no filing
  prints (2232, 4242, 1274/2016, 382 as cumulative), it needs a re-extraction, a new pin and the record tests, and
  it moves 19 primaries from register provenance to grid provenance.

### What the depth script needs (`src/check_cohort_depth_sensitivity.py`)

1. In `judge`, when `reproduce` finds no stored grid: if the observation's `pyd_basis_source` names a register,
   read that entry's cohort cells; require the u <= t-2 sum, after `bm.fx_gbp`, to equal the primary figure to the
   same tolerance (else the record stays out as not reproduced); the t-3 figure is the u <= t-3 sum; if no u <= t-3
   cell exists the record is `no_figure_at_t_minus_3` (1609/2023), never 0. The row's `grid` names the source
   ("register:data/pyd_confirmed_figures.json"), so `grids_used` shows it.
2. An empty-sum guard for stored grids: a u <= t-3 figure none of whose years has a printed cell at both ages
   (the estimator's "all-zero column" for a column of None) is `no_figure_at_t_minus_3` (5678/2016). Do it in the
   depth script, not in the extraction's estimator, which the primary uses (no u <= t-2 figure is affected today).
   Printed zeros and dashes stay observations.
3. Keep both reconciliations in the record: `partition_before_repair` (today's 581/62 with reasons) and
   `repairs` (per record: the old reason, the source, the t-2 check, the t-3 figure). Keep the left-out list with a
   reason for every record (acceptance of section 1.4).
4. Docstring: the reason "a figure two readings of the filing confirmed, whose printed table the extraction did not
   store" is wrong for most of the 19 (5 are CORRECTIONS figures; 13 have a stored table in the wrong form). The
   quartile counts (37/9/11/5; 32,2,8,1; 5,7,3,4), "1991/2018 (no stored grid)" and "Syndicate 382 has six" change.
5. Tests: `test_cohort_depth_sensitivity.py` (581/62 at line 425, the reason set), `test_cohort_depth_honest_backtest.py`
   (line 556 1991's left-out records; line 595 "Syndicate 382 has six"); new tests: the register path reproduces
   each of the 18 and refuses a broken cell (mutation-check), an empty u <= t-3 set gives no figure, 5678/2016's
   case gives no figure; run both files whole.

### Projected partition after the repair (partition only; nothing refitted)

598 kept from 106 syndicates (1609 is new), 45 left out, all `no_figure_at_t_minus_3` (the 43, 1609/2023,
5678/2016). By the primary's size quartile the left-out become 34, 2, 8, 1 (now 37, 9, 11, 5). Added: 18 records
(Q1 4, Q2 7, Q3 3, Q4 4). Notable: 1991/2018 enters with S 0.0380 at t-3 against 0.3975 at t-2, so syndicate
1991's u = t-2 dominance enters the like-for-like table; 4472/2023 falls from 0.0808 to 0.0190; 382/2019 changes
sign.

### Dependent copies to propagate

Analysis: `results/check_cohort_depth_sensitivity_results.json` (the run), the script's docstring, the two test
files, `reproduce-run-report.json` (a new recorded pass: the inputs digest covers every tracked file). Manuscript
(`D:/tmp/r62/oc/M`): `paper/main.tex` section `sec:results:depth` (643/62/43/19/37/581/105 and every figure in
Table `tab:depthv` and the backtest sentences after it), `paper/arxiv.tex`, `paper/number-ledger.json`,
`paper/claim_registry.json` (claim `cohort_depth`), `paper/test_audit_gates.py`.

### Aside (outside section 1.4, for the record)

5678/2016's R (87.761m) is mostly a "Before 2012" column (81,688 outstanding, p41) that prints no development
cells, so the primary's u <= t-2 numerator (0.861m, the 2014 cohort) measures cohorts holding about 6m of R. Several
records carry such "& prior" lumps (382, 2232, 4472, 1274/2022, 4444). That is an outcome-definition question for
the primary, not a depth-check gap; it is not assessed here.
