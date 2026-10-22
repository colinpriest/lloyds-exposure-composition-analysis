# aggcol report (append-only log)
- Worktree of 37d8308 at D:/tmp/r62/oc/aggcol/wt (git worktree add --detach).
- Plan: (1) scan script scan_load.py: run loader (mature_cohort + precedence_672) with fx-wrapper capturing adopted block; (2) scan all grids for aggregated labels; (3) classify col construction; (4) estimator with/without column.
- scan_load.py -> loaded.json: loader at 37d8308. Primary sample (pyd_pct set, opening>0, lob_severity_computed, gross, not TAKEON) = 649 under mature_cohort (653 less 4 rule-B fx exclusions); precedence_672 gives 672 (matches). 902 parsed records both.
- Findings so far: (a) all stored grids' underwriting_years are ints; the only stored label of an aggregated column is _rag_triangle.aggregated_cohort (58 blocks, 29 records; agg_flagged.json). _claims_triangle never carries it. (b) free-text scan (colnotes.txt, string_hits.json): many records' notes say the filing's triangle had an aggregate column that the extraction dropped from the stored grid (e.g. 1274_2021, 2987_2024 have _claims_triangle.notes naming '2011 & prior'/'2014 & prior' columns excluded from underwriting_years) -> second category "column not in stored grid".
- Method for construction test: A_t(a) vs A_{t-1}(a) + sum of next-UW-year columns of t-1 report at same age (1% tolerance); fixed anchor => A_t(a)=A_{t-1}(a).
- analyze.py (v1) run: estimator reproduces the adopted figure with the column for every rag_triangle record (all 29 flagged are GBP-... see aggcol_raw.json). Neighbour reports often store their first column unflagged -> v2 tests a flagged-or-first column and 3 hypotheses (equal / dev-age additive / calendar-shifted) when anchors differ.
- v2 results: 218 series (fixed anchor 2010, 2016-2020) = calendar (cells equal 0.0%); 1945 2023->2024 and 2791 2023->2024 = dev-age strict (max 0.2%/0.8%); 1945_2022->2023 dev-age approx (3.3% uniform offset; calendar fails 29%); 1955 moving anchor but calendar-shifted fits better than dev-age (needs rounding tolerance); 4020/2007/1200 fixed anchors but cells restated between reports 4-28% (1200 USD retranslation); many 2015 records lack comparable t-1 grid.
- v3 plan: rounding tolerance (decimals in grid), fixed-anchor flagged neighbour => calendar coverage, also t-2/t+2 fallback.
- Study evidence (results/extraction_error_rate/**, readings of the filing pages; mined by mine_study.py -> study_mined.txt): 218_2017/2018/2020 quote the aggregated column's rows as 'Seven/Eight/Ten years or more later' (a calendar series of a fixed block, 2018 report's 'Seven years later' = 2017 report's 'Seven years or more later' = 4,113,577). 2007_2015: two readers found the '2010 & Prior' column's last diagonal 'not like-for-like' (2015 paid diagonal 507.8m vs 343.9m paid in the technical account). 2791: reports restate each prior year at current exchange rates (p81), so cells shift ~5% between reports. 1945 2022-23: translated at year-end rates.
- Decision: add uniform-scale-adjusted additive test (FX restatement), keep strict 1% test + rounding tolerance.
- analyze2.py written (3 hypotheses + rounding tolerance + common-factor test; neighbours t-1,t+1,t-2,t+2) -> aggcol_raw2.json. Preliminary: estimator reproduces adopted figure for every flagged record whose route is a triangle (with column), 2007_2015 adopted = without (code_triangle), 1945_2023/24 adopted = without (register). Strong construction: 218_2016-20 calendar (cells equal 0.0%, quotes 'n years or more later'); 1945_2022-24 dev-age. 2791 weak discrimination (block dominates; 5% FX restatement); many 2015 records have no comparable t-1 grid => undeterminable.
- TODO: discrimination measure; Part B (notes say column excluded from stored grid); first-column-magnitude heuristic; final tables.
- Part B (partb.py -> partb.json): 695 records in primary-or-672 scanned; 53 non-flagged triangle-route records whose extraction notes say the filing's table has an aggregated older-years column left out of the stored grid (about 47 strong); estimator reproduces their adopted figure from the stored grid (column excluded). Construction cannot be tested (column not stored): label-anchor pattern across years used as presumption only.
- Built aggcol.json (finalize.py): Part A 29 records (24 in primary, 24 in 672; 5 in neither: 4020_2017 unreconciled, 510_2014 net, 557_2014/6104_2015/6118_2015 no LOB weights); Part B 49 candidates (47 primary); Section C 12 heuristic candidates (first column age-0 > 2.5x neighbours; probably individual large years). mutation_check.py passed (note: common-factor test is lax on small added columns; strict test used where available).
- Primary verdicts (Part A, 24): consistent 8 (218x5, 4020_2016 [calendar after restatement factor], 1945_2023, 1945_2024), inconsistent 1 (1945_2022, dev-age, includes; rule -13.831 vs -13.84), undeterminable 15.

# FINAL (see tables.md for Part A, Part B and Section C tables; aggcol.json is the full record)
- Scan: primary sample 649 records (all route through a triangle: rag_triangle 538, mature_cohort_triangle 82, confirmed_figure 23, code_triangle 6); 672 construction 672. All 1065 files' models scanned: every underwriting_years label is an int; aggregated columns recorded only as _rag_triangle.aggregated_cohort (58 blocks, 29 records); free-text scan of all string fields; notes sentences scanned for 695 primary-or-672 records.
- Verdicts primary Part A (24): consistent 8, inconsistent 1 (1945_2022), undeterminable 15. Part B: 47 primary records whose figure leaves out a column the filing prints: all undeterminable (column not stored).

## Part A: aggregated column recorded in the stored grid (29 records)

Figures in GBP m (every record is GBP after the loader; the stored grids of 1200 are labelled USD but the loader reports GBP). 'with'/'without' are the extraction's estimator on the adopted block's stored grid.

| key | prim | 672 | adopted (route) | label t | label t-1 | construction (evidence) | adopted has col | with | without | with-without (share of adopted) | verdict | rule figure (change) | pages t / t-1 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 33_2015 | yes | yes | -118.31 (rag_triangle) | 2010 and prior GBP 000 | report stores no comparable grid | undeterminable | yes | -118.31 | -86.114 | -32.196 (-27.2%) | undeterminable | - | 36 / None |
| 218_2016 | yes | yes | 88.896 (rag_triangle) | 2010 and prior GBP 000 | none stored in the t-1/t+1 grid (its first grid year 2011 compared, assumed) | calendar [t+1] | yes | 88.896 | 56.55 | 32.346 (+36.4%) | consistent | 88.896 (+0.000) | 30 / 30 |
| 218_2017 | yes | yes | -41.916 (rag_triangle) | and prior GBP 000 | 2010 and prior GBP 000 (anchor 2010) | calendar [t-1] | yes | -41.916 | -29.643 | -12.273 (-29.3%) | consistent | -41.916 (+0.000) | 32 / 30 |
| 218_2018 | yes | yes | -116.005 (rag_triangle) | and prior GBP 000 | and prior GBP 000 (anchor 2010) | calendar [t-1] | yes | -116.005 | -90.66 | -25.345 (-21.9%) | consistent | -116.005 (+0.000) | 32 / 32 |
| 218_2019 | yes | yes | -29 (rag_triangle) | 2010 & prior GBP m | and prior GBP 000 (anchor 2010) | calendar [t-1] | yes | -29 | -42.4 | 13.4 (+46.2%) | consistent | -29 (+0.000) | 36 / 32 |
| 218_2020 | yes | yes | -24.5 (rag_triangle) | 2010 & prior GBP m | 2010 & prior GBP m (anchor 2010) | calendar [t-1] | yes | -24.5 | -19.9 | -4.6 (-18.8%) | consistent | -24.5 (+0.000) | 37 / 36 |
| 510_2014 | no | no | -48.4 (confirmed_figure) | 2008 & prior GBP m 3,896.5 | report not in the corpus | undeterminable | yes | -48.4 | -31.4 | -17 (-35.1%) | undeterminable | - | 44 / None |
| 557_2014 | no | no | -1.5 (rag_triangle) | 2008 & prior GBP m 146.7 | report not in the corpus | undeterminable | yes | -1.5 | -1.4 | -0.1 (-6.7%) | undeterminable | - | 68 / None |
| 1200_2015 | yes | yes | 0.5 (rag_triangle) | Before 2011 Em | report stores no comparable grid | undeterminable | yes | 0.5 | 8.4 | -7.9 (-1580.0%) | undeterminable | - | 40 / None |
| 1200_2017 | yes | yes | 44.9 (rag_triangle) | 2011 and prior Em 209.2 | none stored in the t-1/t+1 grid (its first grid year 2010 compared, assumed) | undeterminable | yes | 44.9 | 40.5 | 4.4 (+9.8%) | undeterminable | - | 43 / 40 |
| 1945_2022 | yes | yes | -13.84 (rag_triangle) | 2012&Prior GBP 000 20,567 | none stored in the t-1/t+1 grid (its first grid year 2011 compared, assumed) | dev-age [t-1] | yes | -13.84 | -13.831 | -0.009 (-0.1%) | inconsistent | -13.831 (+0.009) | 51 / 49 |
| 1945_2023 | yes | yes | -4.997 (mature_cohort_triangle) | 2013&Prior GBP 000 | 2012&Prior GBP 000 20,567 (anchor 2012) | dev-age [t-1] | no | -5.034 | -4.997 | -0.037 (-0.7%) | consistent | -4.997 (+0.000) | 52 / 51 |
| 1945_2024 | yes | yes | 5.264 (mature_cohort_triangle) | 2014 & Prior GBP 000 | 2013&Prior GBP 000 (anchor 2013) | dev-age [t-1] | no | 4.839 | 5.264 | -0.425 (-8.1%) | consistent | 5.264 (+0.000) | 54 / 52 |
| 1955_2015 | yes | yes | 11.444 (rag_triangle) | 2011 & Prior GBP 000 438,186 | report stores no comparable grid | undeterminable | yes | 11.444 | 11.763 | -0.319 (-2.8%) | undeterminable | - | 48 / None |
| 1955_2018 | yes | yes | 16.7 (rag_triangle) | 2012 & Prior GBP m | report not in the corpus | undeterminable | yes | 16.7 | 18.5 | -1.8 (-10.8%) | undeterminable | - | 48 / None |
| 1955_2019 | yes | yes | 44.2 (rag_triangle) | 2013 & Prior GBP m 834.7 | 2012 & Prior GBP m (anchor 2012) | undeterminable [t+1] | yes | 44.2 | 65.8 | -21.6 (-48.9%) | undeterminable | - | 47 / 48 |
| 1955_2020 | yes | yes | 15.9 (rag_triangle) | 2014 & Prior GBP m | 2013 & Prior GBP m 834.7 (anchor 2013) | undeterminable [t-1] | yes | 15.9 | 10.7 | 5.2 (+32.7%) | undeterminable | - | 51 / 47 |
| 2007_2015 | yes | yes | -2 (code_triangle) | 2010 & Prior Em | report stores no comparable grid | undeterminable | no | 148.8 | -2 | 150.8 (+7540.0%) | undeterminable | - | 37 / None |
| 2007_2016 | yes | yes | 54.8 (rag_triangle) | 2010&P GBP m 1,440.4 | 2010 & Prior Em (anchor 2010) | undeterminable | yes | 54.8 | 61.3 | -6.5 (-11.9%) | undeterminable | - | 35 / 37 |
| 2007_2017 | yes | yes | -44.5 (rag_triangle) | 2010&P Em | 2010&P GBP m 1,440.4 (anchor 2010) | undeterminable | yes | -44.5 | -22 | -22.5 (-50.6%) | undeterminable | - | 33 / 35 |
| 2791_2022 | yes | yes | -17.497 (rag_triangle) | 2012 and prior 000,3 | none stored in the t-1/t+1 grid (its first grid year 2011 compared, assumed) | undeterminable [t+1] | yes | -17.497 | -8.245 | -9.252 (-52.9%) | undeterminable | - | 82 / 81 |
| 2791_2023 | yes | yes | -35.529 (rag_triangle) | 2013 and prior 000,3 | 2012 and prior 000,3 (anchor 2012) | undeterminable [t-1] | yes | -35.529 | -28.21 | -7.319 (-20.6%) | undeterminable | - | 83 / 82 |
| 2791_2024 | yes | yes | -36.191 (rag_triangle) | 2014 and prior E'000 | 2013 and prior 000,3 (anchor 2013) | undeterminable [t-1] | yes | -36.191 | -27.986 | -8.205 (-22.7%) | undeterminable | - | 49 / 83 |
| 3624_2015 | yes | yes | 5.025 (rag_triangle) | 2010 and prior GBP 000 | report stores no comparable grid | undeterminable | yes | 5.025 | -0.912 | 5.937 (+118.2%) | undeterminable | - | 36 / None |
| 4020_2016 | yes | yes | 25.303 (rag_triangle) | 2010 and prior GBP '000 614,673 | report stores no comparable grid | calendar [t+1] | yes | 25.303 | 18.492 | 6.811 (+26.9%) | consistent | 25.303 (+0.000) | 42 / None |
| 4020_2017 | no | no | 21.188 (confirmed_figure) | prior GBP '000 | 2010 and prior GBP '000 614,673 (anchor 2010) | calendar [t-1] | yes | 21.188 | 17.285 | 3.903 (+18.4%) | consistent | 21.188 (+0.000) | 41 / 42 |
| 4020_2018 | yes | yes | 43.863 (rag_triangle) | 2010 & prior GBP '000 604,240 | prior GBP '000 (anchor 2010) | undeterminable [t-1] | yes | 43.863 | 54.639 | -10.776 (-24.6%) | undeterminable | - | 39 / 41 |
| 6104_2015 | no | no | -3.686 (rag_triangle) | 2010 and prior GBP 000 | report stores no comparable grid | undeterminable | yes | -3.686 | -3.092 | -0.594 (-16.1%) | undeterminable | - | 65 / None |
| 6118_2015 | no | no | 3.61 (rag_triangle) | 2011 & Prior GBP 000 50,716 | report stores no comparable grid | undeterminable | yes | 3.61 | 2.287 | 1.323 (+36.6%) | undeterminable | - | 37 / None |

### Part A construction evidence, one line per record

- 33_2015: t-1: report stores no grid; t+1: neither fits (development-age: median 92.9%, max 94.3%; calendar: median 92.8%, max 94.4%); t-2: report not in the corpus; t+2: neither fits (development-age: median 93.3%, max 94.7%; calendar: median 93.2%, max 94.7%). Pages t=36, t-1=None. 
- 218_2016: same anchor, cells equal within 1% over 7 ages. Pages t=30, t-1=30. 
- 218_2017: same anchor, cells equal within 1% over 7 ages. Pages t=32, t-1=30. Study: Study (first-sample verdicts): p32 prints the column's rows as 'Six years later 4,125,850' and 'Seven years or more later 4,113,577'; the 2018 report (p32) prints 'Seven years later 4,113,577' and 'Eight years or more later 4,088,232': one fixed block (2010 and prior) developed by calendar year.
- 218_2018: same anchor, cells equal within 1% over 7 ages. Pages t=32, t-1=32. Study: Study (fourth-sample verdicts): p32 'Seven years later 4,113,577, Eight years or more later 4,088,232' (same series as the 2017 report's).
- 218_2019: same anchor, cells equal within 1% over 8 ages. Pages t=36, t-1=32. 
- 218_2020: same anchor, cells equal within 1% over 10 ages. Pages t=37, t-1=36. Study: Study (first-sample verdicts): p37 '2010 & prior' column 'Nine years later 4,101.7', 'Ten years or more later 4,097.1'.
- 510_2014: t-1: report not in the corpus; t+1: neither fits (development-age: median 88.9%, max 93.8%; calendar: median 88.6%, max 93.8%); t-2: report not in the corpus; t+2: neither fits (development-age: median 87.4%, max 92.9%; calendar: median 87.0%, max 92.9%). Pages t=44, t-1=None. 
- 557_2014: t-1: report not in the corpus; t+1: report stores no grid; t-2: report not in the corpus; t+2: report stores no grid. Pages t=68, t-1=None. 
- 1200_2015: t-1: report stores no grid; t+1: same anchor assumed but cells do not match; t-2: report not in the corpus; t+2: neither fits (development-age: median 6.2%, max 59.5%; calendar: median 7.9%, max 26.3%). Pages t=40, t-1=None. 
- 1200_2017: t-1: neither fits (development-age: median 5.6%, max 53.5%; calendar: median 4.4%, max 17.7%); t+1: neither fits (development-age: median 76.1%, max 76.4%; calendar: median 76.1%, max 76.8%); t-2: neither fits (development-age: median 6.2%, max 59.5%; calendar: median 7.9%, max 26.3%); t+2: age: currency differs (GBP vs USD); calendar: currency differs (GBP vs USD). Pages t=43, t-1=40. 
- 1945_2022: as development-age sum after one common factor 1.061 over 10 ages (max 0.91%); calendar fails (max 12.4%). Pages t=51, t-1=49. 
- 1945_2023: as development-age sum after one common factor 0.967 over 10 ages (max 0.45%); calendar fails (max 29.3%). Pages t=52, t-1=51. Study: Register entry and readings F1, F2: the column is built by development age; its last step (-37k) is not the report year's movement.
- 1945_2024: older block + the added cohort at the same development age, within 1% over 10 ages (worst 0.15%). Pages t=54, t-1=52. Study: Register entry and readings F1, F2: the column is the 2023 report's '2013&Prior' plus UY2014 added by development age.
- 1955_2015: t-1: report stores no grid; t+1: report not in the corpus; t-2: report not in the corpus; t+2: report not in the corpus. Pages t=48, t-1=None. 
- 1955_2018: t-1: report not in the corpus; t+1: neither fits (development-age: median 3.6%, max 16.5%; calendar: median 3.2%, max 3.4%); t-2: report not in the corpus; t+2: neither fits (development-age: median 2.8%, max 12.1%; calendar: median 4.2%, max 4.3%). Pages t=48, t-1=None. 
- 1955_2019: the two constructions predict cells within 2.1% of each other (the older block dominates), so the cells cannot tell them apart (development-age closer in 2 of 5 ages, calendar closer in 3). Pages t=47, t-1=48. Lean: leans calendar (cells closer to the calendar-year sum in most ages) but cannot be told apart at 1%. 
- 1955_2020: the two constructions predict cells within 2.1% of each other (the older block dominates), so the cells cannot tell them apart (development-age closer in 2 of 5 ages, calendar closer in 3). Pages t=51, t-1=47. Lean: leans calendar (cells closer to the calendar-year sum in most ages) but cannot be told apart at 1%. 
- 2007_2015: t-1: report stores no grid; t+1: same anchor label in both reports but the cells differ by a median 25.6% (worst 27.9% at age 1), so the stored columns are not the same block; t-2: report not in the corpus; t+2: same anchor assumed but cells do not match. Pages t=37, t-1=None. Study: Study (census verdicts, two readers): the column's last diagonal 'is not like-for-like' (the 2015 paid diagonal moves 507.8m, 261.0m of it in '2010 & Prior', against 343.9m paid in the technical account, p23); both readers call the RAG +148.8m undeterminable and the code triangle's -2.0m (without the column) stands.
- 2007_2016: t-1: same anchor label in both reports but the cells differ by a median 25.6% (worst 27.9% at age 1), so the stored columns are not the same block; t+1: same anchor assumed but cells do not match; t-2: report stores no grid; t+2: neither fits (development-age: median 91.0%, max 91.0%; calendar: median 93.9%, max 93.9%). Pages t=35, t-1=37. 
- 2007_2017: t-1: same anchor assumed but cells do not match; t+1: age: currency differs (GBP vs USD); calendar: currency differs (GBP vs USD); t-2: same anchor assumed but cells do not match; t+2: age: currency differs (GBP vs USD); calendar: currency differs (GBP vs USD). Pages t=33, t-1=35. 
- 2791_2022: the two constructions predict cells within 1.1% of each other (the older block dominates), so the cells cannot tell them apart (development-age closer in 0 of 10 ages, calendar closer in 10). Pages t=82, t-1=81. Lean: no lean (the older block dominates; neighbours disagree). Study: Study (eighth-census): p81 'Each prior year is restated at the current exchange rates', so cells move between reports.
- 2791_2023: the two constructions predict cells within 1.1% of each other (the older block dominates), so the cells cannot tell them apart (development-age closer in 0 of 10 ages, calendar closer in 10). Pages t=83, t-1=82. Lean: no lean (the older block dominates; neighbours disagree). Study: Study (eighth-census): p82 restates each prior year at current exchange rates.
- 2791_2024: the two constructions predict cells within 1.2% of each other (the older block dominates), so the cells cannot tell them apart (development-age closer in 10 of 10 ages, calendar closer in 0). Pages t=49, t-1=83. Lean: no lean (the older block dominates; neighbours disagree). Study: Study (eighth-census): the p49 rows run '12 months ... 120 months' for '2014 and prior'; the gross figures are restated at current rates.
- 3624_2015: t-1: report stores no grid; t+1: neither fits (development-age: median 45.2%, max 54.1%; calendar: median 45.9%, max 65.7%); t-2: report not in the corpus; t+2: neither fits (development-age: median 48.0%, max 57.2%; calendar: median 48.7%, max 68.1%). Pages t=36, t-1=None. Study: Study (census verdicts): p36 prints the '2010 and prior' column with 'Four years later 148,309' and 'Five years later 154,246'; the latest diagonal ties to the balance sheet's 393,088 (so its last cell is a latest estimate); the study did not say how the column is built.
- 4020_2016: same anchor, cells equal after one common factor 0.946 (restatement) over 7 ages. Pages t=42, t-1=None. 
- 4020_2017: same anchor, cells equal after one common factor 0.946 (restatement) over 7 ages. Pages t=41, t-1=42. Study: Study (fourth-sample census): the printed table is unreliable (its latest diagonal sums to 2,006,546 against the printed total 1,935,876; rows repeat the 2016 filing's triangle one column over).
- 4020_2018: same anchor in both reports (coverage unchanged) but cells differ: median 3.8%, worst 4.2% at age 0. Pages t=39, t-1=41. Lean: leans calendar (same coverage in both reports; cells restated). 
- 6104_2015: t-1: report stores no grid; t+1: neither fits (development-age: median 66.4%, max 68.1%; calendar: median 66.1%, max 69.7%); t-2: report not in the corpus; t+2: neither fits (development-age: median 68.2%, max 70.0%; calendar: median 67.8%, max 71.7%). Pages t=65, t-1=None. 
- 6118_2015: t-1: report stores no grid; t+1: neither fits (development-age: median 16.9%, max 16.9%; calendar: median 10.7%, max 10.7%); t-2: report not in the corpus; t+2: neither fits (development-age: median 15.8%, max 15.8%; calendar: median 11.2%, max 11.2%). Pages t=37, t-1=None. 

## Part B: filing's aggregated column named in the extraction notes, absent from the stored grid (49 candidates, 47 in the primary)

| key | prim | 672 | route | adopted | anchors t-1 / t / t+1 (notes or grid) | presumption from the anchor pattern (not a finding) | pages (grid / claims) |
|---|---|---|---|---|---|---|---|
| 1084_2015 | yes | yes | mature_cohort_triangle | 18.5 | - / [2010] / - | not testable: the neighbouring report names no anchor | 35 / 14 |
| 1084_2020 | yes | yes | mature_cohort_triangle | 5.7 | - / [2010] / - | not testable: the neighbouring report names no anchor | 29 / 16 |
| 1110_2017 | yes | yes | rag_triangle | -1.845 | - / - / - | not testable: the neighbouring report names no anchor | 25 / 8 |
| 1176_2020 | yes | yes | rag_triangle | -7.549 | - / [2010] / [2011] | coverage grows by 1 between t and t+1 (anchor 2010 -> 2011): presumption development age | 32 / 13 |
| 1176_2021 | yes | yes | rag_triangle | -7.647 | [2010] / [2011] / - | coverage grows by 1 between the reports (anchor 2010 -> 2011): presumption development age, so leaving it out would be consistent | 33 / 14 |
| 1200_2020 | yes | yes | rag_triangle | 54.4 | - / [2013] / - | not testable: the neighbouring report names no anchor | 43 / 18 |
| 1218_2017 | yes | yes | rag_triangle | -3.14 | - / [2010] / [2010] | fixed coverage across t and t+1 (anchor 2010 -> 2010): presumption calendar | 38 / 18 |
| 1218_2018 | yes | yes | rag_triangle | -22.744 | [2010] / [2010] / - | fixed coverage in both reports (anchor 2010 -> 2010): presumption calendar, so leaving the column out would be inconsistent | 38 / 18 |
| 1225_2021 | yes | yes | rag_triangle | 8.1 | - / [2016] / [2017] | coverage grows by 1 between t and t+1 (anchor 2016 -> 2017): presumption development age | 30 / 14 |
| 1225_2022 | yes | yes | rag_triangle | 18.6 | [2016] / [2017] / - | coverage grows by 1 between the reports (anchor 2016 -> 2017): presumption development age, so leaving it out would be consistent | 33 / 16 |
| 1274_2021 | yes | yes | rag_triangle | 72.645 | - / [2011] / - | not testable: the neighbouring report names no anchor | 36 / 13 |
| 1274_2023 | yes | yes | confirmed_figure | 87.073 | - / [2013] / - | not testable: the neighbouring report names no anchor | 36 / 12 |
| 1414_2015 | yes | yes | rag_triangle | -13.749 | - / [2010] / - | not testable: the neighbouring report names no anchor | 29 / 14 |
| 1458_2021 | yes | yes | rag_triangle | 57.601 | - / - / - | not testable: the neighbouring report names no anchor | 45 / 17 |
| 1884_2022 | yes | yes | rag_triangle | 9.1 | - / [2012] / - | not testable: the neighbouring report names no anchor | 32 / 14 |
| 2003_2016 | yes | yes | mature_cohort_triangle | 49.256 | - / [2011] / - | not testable: the neighbouring report names no anchor | 43 / 21 |
| 2003_2020 | yes | yes | rag_triangle | 369 | - / [2011] / - | not testable: the neighbouring report names no anchor | 46 / 23 |
| 2088_2017 | yes | no | mature_cohort_triangle | 3.259 | - / [2012] / [2013] | coverage grows by 1 between t and t+1 (anchor 2012 -> 2013): presumption development age | None / 14 |
| 2088_2018 | yes | yes | rag_triangle | 10.856 | [2012] / [2013] / - | coverage grows by 1 between the reports (anchor 2012 -> 2013): presumption development age, so leaving it out would be consistent | 35 / 16 |
| 2121_2015 | yes | yes | rag_triangle | 1.619 | - / [2010] / - | not testable: the neighbouring report names no anchor | 56 / 19 |
| 2121_2021 | yes | no | mature_cohort_triangle | 15.7 | - / [2011] / [2012] | coverage grows by 1 between t and t+1 (anchor 2011 -> 2012): presumption development age | 57 / 54 |
| 2121_2022 | yes | yes | rag_triangle | 36.2 | [2011] / [2012] / - | coverage grows by 1 between the reports (anchor 2011 -> 2012): presumption development age, so leaving it out would be consistent | 59 / 18 |
| 2468_2016 | no | yes | rag_triangle | 158.048 | - / [2010] / - | not testable: the neighbouring report names no anchor | 38 / 17 |
| 2468_2018 | yes | yes | rag_triangle | 18.37 | - / - / - | not testable: the neighbouring report names no anchor | 41 / 18 |
| 2525_2018 | yes | yes | rag_triangle | -10.773 | - / [2011] / - | not testable: the neighbouring report names no anchor | 44 / 18 |
| 2791_2015 | yes | yes | confirmed_figure | -2.131 | - / - / [2010] | not testable: the neighbouring report names no anchor | 69 / 31 |
| 2987_2023 | yes | no | mature_cohort_triangle | 234.1 | - / [2013] / [2014] | coverage grows by 1 between t and t+1 (anchor 2013 -> 2014): presumption development age | 47 / 21 |
| 2987_2024 | yes | yes | rag_triangle | 170.224 | [2013] / [2014] / - | coverage grows by 1 between the reports (anchor 2013 -> 2014): presumption development age, so leaving it out would be consistent | 54 / 26 |
| 2999_2021 | yes | yes | rag_triangle | 166.2 | - / [2011] / - | not testable: the neighbouring report names no anchor | 46 / 21 |
| 3000_2015 | yes | yes | rag_triangle | -12.617 | - / - / - | not testable: the neighbouring report names no anchor | 36 / 14 |
| 386_2020 | yes | yes | rag_triangle | 43.9 | - / [2010] / [2011] | coverage grows by 1 between t and t+1 (anchor 2010 -> 2011): presumption development age | 43 / 22 |
| 386_2021 | yes | yes | rag_triangle | -1.7 | [2010] / [2011] / - | coverage grows by 1 between the reports (anchor 2010 -> 2011): presumption development age, so leaving it out would be consistent | 44 / 22 |
| 4242_2021 | yes | yes | rag_triangle | 9.493 | - / [2015] / - | not testable: the neighbouring report names no anchor | 46 / 14 |
| 4242_2023 | yes | yes | rag_triangle | -7.19 | - / [2017] / - | not testable: the neighbouring report names no anchor | 45 / 18 |
| 435_2015 | yes | yes | rag_triangle | -9.756 | - / [2010] / [2010] | fixed coverage across t and t+1 (anchor 2010 -> 2010): presumption calendar | 34 / 12 |
| 435_2016 | yes | yes | rag_triangle | -44.233 | [2010] / [2010] / [2010] | fixed coverage in both reports (anchor 2010 -> 2010): presumption calendar, so leaving the column out would be inconsistent | 35 / 12 |
| 435_2017 | yes | yes | rag_triangle | -30.689 | [2010] / [2010] / [2010] | fixed coverage in both reports (anchor 2010 -> 2010): presumption calendar, so leaving the column out would be inconsistent | 37 / 12 |
| 435_2018 | yes | yes | rag_triangle | -4.551 | [2010] / [2010] / - | fixed coverage in both reports (anchor 2010 -> 2010): presumption calendar, so leaving the column out would be inconsistent | 36 / 13 |
| 435_2021 | yes | yes | rag_triangle | -96.222 | - / [2011] / [2012] | coverage grows by 1 between t and t+1 (anchor 2011 -> 2012): presumption development age | 41 / 11 |
| 435_2022 | yes | yes | rag_triangle | -43.811 | [2011] / [2012] / [2013] | coverage grows by 1 between the reports (anchor 2011 -> 2012): presumption development age, so leaving it out would be consistent | 40 / 12 |
| 435_2023 | yes | yes | rag_triangle | -34.385 | [2012] / [2013] / - | coverage grows by 1 between the reports (anchor 2012 -> 2013): presumption development age, so leaving it out would be consistent | 42 / 14 |
| 4444_2015 | yes | yes | rag_triangle | -13.896 | - / [2010] / - | not testable: the neighbouring report names no anchor | 24 / 13 |
| 4472_2015 | yes | yes | rag_triangle | -24.3 | - / [2010] / [2010] | fixed coverage across t and t+1 (anchor 2010 -> 2010): presumption calendar | 40 / 17 |
| 4472_2016 | yes | yes | rag_triangle | 26.1 | [2010] / [2010] / - | fixed coverage in both reports (anchor 2010 -> 2010): presumption calendar, so leaving the column out would be inconsistent | 41 / 17 |
| 4472_2018 | yes | yes | rag_triangle | 87.9 | - / [2010] / - | not testable: the neighbouring report names no anchor | 42 / 16 |
| 510_2017 | yes | yes | rag_triangle | -10.2 | - / [2010] / - | not testable: the neighbouring report names no anchor | 48 / 20 |
| 5678_2015 | no | yes | confirmed_figure | -8.135 | - / [2010] / [2011] | coverage grows by 1 between t and t+1 (anchor 2010 -> 2011): presumption development age | None / 15 |
| 5678_2016 | yes | yes | rag_triangle | 0.861 | [2010] / [2011] / - | coverage grows by 1 between the reports (anchor 2010 -> 2011): presumption development age, so leaving it out would be consistent | 41 / 16 |
| 958_2015 | yes | yes | rag_triangle | -4.935 | - / [2010] / - | not testable: the neighbouring report names no anchor | 23 / 12 |

## Section C: heuristic candidates (first stored column's age-0 cell more than 2.5 times its neighbours'; probably individual large years)

| key | prim | route | adopted | first column year | ratio | with first col | without | page |
|---|---|---|---|---|---|---|---|---|
| 1880_2015 | yes | rag_triangle | -5.8 | 2011 | 8.51 | -5.8 | - | 31 |
| 1880_2016 | yes | rag_triangle | -16.4 | 2011 | 8.76 | -16.4 | -9.8 | 32 |
| 1880_2017 | yes | rag_triangle | 2 | 2011 | 8.59 | 2 | - | 33 |
| 1880_2018 | yes | mature_cohort_triangle | 7.6 | 2011 | 8.74 | 7.6 | 9.3 | 33 |
| 1880_2019 | yes | rag_triangle | 20.9 | 2011 | 8.65 | 20.9 | 20.6 | 34 |
| 1880_2020 | yes | mature_cohort_triangle | 0.4 | 2011 | 8.57 | 0.4 | 0.6 | 32 |
| 1880_2021 | yes | rag_triangle | -24.8 | 2012 | 3.03 | -24.8 | -24.5 | 34 |
| 4472_2019 | yes | rag_triangle | 226.2 | 2011 | 13.53 | 226.2 | 223.3 | 41 |
| 780_2015 | yes | rag_triangle | -20.251 | 2011 | 2.77 | -20.251 | -17.644 | 28 |
| 780_2016 | yes | mature_cohort_triangle | 24.9 | 2011 | 3.54 | 24.9 | - | 30 |
| 780_2017 | yes | rag_triangle | -1.6 | 2011 | 2.67 | -1.6 | - | 31 |
| 780_2018 | yes | rag_triangle | -21.3 | 2011 | 2.67 | -21.3 | -14.4 | 31 |
