# Mature-cohort primary outcome: design and per-record measurement

Read-only stage, 22 October 2026, written from 18:50 Brisbane (08:49 UTC by the clock). Inputs: analysis
`D:/tmp/r62/pub4` at e9e6645 (run from a copy in `D:/tmp/r62/oc/design/ana`), extraction
`D:/dev/lloyds_reserve_stress_testing` at 713c77b3 (read only; its record files are byte-for-byte the analysis copies
once parsed: 1,065 of 1,065 equal), manuscript `D:/tmp/r62/fin8/M` at c9074a1. No repository was changed, nothing
was committed, no API was called (`LLOYDS_EXTRACTION_OFFLINE=1`). The AI declaration is out of scope and was not
touched.

Files in this folder:

| File | What it is |
|---|---|
| `per_record.csv` | one row per record: the 672 working-sample records, the 25 entrants, the 12 records whose figure changes but stay out, and every other record carrying a sign-override or veto (717 rows) |
| `measure.py` -> `stage1.json` | the current loader's outcome per record, the adopted block's route, its veto notes, and the RAG triangle's figure recomputed by the extraction's own estimator |
| `tri_compute.py` | `compute_pyd_from_triangle` and its helpers, copied by source (ast) from `test_gemini.py` at 713c77b3 without importing it (its import loads `.env` and the API clients) |
| `sim.py` -> `stage2.json` | the loader (`load_and_classify`, unchanged) run with the rule applied to the blocks it reads |
| `scan_restored.py` -> `scan_restored.json` | the fourteenth amendment's reconciliation census (`scan_triangle_tables.scan_record`, unchanged) on every restored triangle |
| `final.py` | assembles the CSV, the shape check (`scan_grid_shape.shape_tests`), the flags and the reading tiers |
| `prior_readings.py` -> `prior_readings.json` | every earlier error-rate reading of the records whose figure changes |

Validation of the copied estimator: on the 669 committed blocks whose route is `rag_triangle` with its triangle keys it
reproduces the route's value in 667. The two it does not, 1967/2014 and 2999/2022, are refused by the stage-2 reader
and are listed in `pdf_extraction/audit/redecision_pending.json` already; neither is a restored record.

## 1. Where the precedence decisions are made

Both rules are applied in the **extraction**, in `process_one_report` and `extract_pyd_from_relevant_pages`
(`test_gemini.py`). The adopted block's `_pyd_route` is already decided when the analysis loads it; the loader never
re-decides precedence.

- **Provisions sign-disagreement override** (`extract_pyd_from_relevant_pages`, l.3442-3481). When the table backend's
  triangle figure and the provisions note's gross prior-year line differ in sign, and the note is an affirmed movement
  row bound to the report year (R138's `movement_semantics`), the RAG step returns the provisions figure with method
  `provisions`. The route is written as `rag_provisions` (`_rag_figure_source`), with no triangle keys. The triangle's
  own figure exists only in the local `pyd_details` string and the console log: **it is not written to the record**.
  The grid itself is kept (`_rag_triangle` in both model blocks, with `type`, `units`, `source_page`, `entity`).
- **Model-agreement veto** (`_rag_veto` -> `_pyd_override_gate`, l.5460-5516, called at l.5866). A deterministic
  figure is not applied when both models agree on the other sign, or when it is above 50% of opening reserves while both
  models are under 10%. The models' figures stand (route `model_reading`), and the note `[RAG PYD NOT APPLIED:
  deterministic figure +x.xxxm ...]` records the vetoed figure in both blocks' `data_quality_notes`. The same gate
  then runs on the models' own triangles in `verify_triangles` (`[CODE PYD NOT APPLIED: ...]`). The grid is kept.
- Loss-ratio fallback (`_apply_loss_ratio_fallback`, l.5375): fills a blank or overrides a contradicting model value;
  writes no route, only `[MANAGED LEVEL ...]` or `[RAG DIRECTION OVERRIDE ...]` notes.
- `PYD_EXCLUDED_RECENT_UW_YEARS = 2` (table_extraction.py l.1369) is enforced in every triangle route
  (`_diagonal_cells`, the loss-ratio reader l.1654, the first-year test l.3381).

**Can the analysis select the mature-cohort figure from what the files already hold? Yes, for every displaced
triangle.** What the files keep:

| Needed | Kept? | Where |
|---|---|---|
| the displaced triangle's grid | yes, all 61 working-sample and 37 other records | `models/*/_rag_triangle` (`underwriting_years`, `development_rows`, `type`, `units`, `units_evidence`, `source_page`, `entity`, `current_estimate_row`, `aggregated_cohort`) |
| its underwriting-year columns | yes | `underwriting_years`; every restored grid holds at least one column up to t-2 |
| its computed figure, sign override | **no** (only in the run log) | recomputed from the stored grid; the recomputation equals the readers' own recomputation from the printed page in all 26 records an earlier reading recomputed |
| its computed figure, veto | yes | the veto note; equals the recomputation in all 32 working-sample veto records with a triangle |
| its reconciliation status | **no** for displaced triangles (the 13 October census covered the 573 triangle-sourced records only) | measured here by running the census's own script on the restored grids: `scan_restored.json` |
| its shape status | no | measured here with the fifteenth amendment's `shape_tests` |

**Recommendation: implement in the analysis loader, through an evidenced register, not by re-extraction.**

- It changes exactly the records the rule moves (61 figures in the working sample, 25 entrants) and nothing else. An
  extraction change plus offline replay rewrites the 1,065 records; history shows replays move records nobody predicted
  (`redecision_pending.json`), and 1988/2024 and 3456/2024, both restored records, were last settled by paid page-vision
  calls on 29 September; 6117/2018, another restored record, was unservable offline in round 55
  (`offline_unservable.json`). The loader route needs **no replay, so no record can be refused into an uncached call:
  the predicted count is zero by construction.**
- The data already carry the decision's evidence (grid, page, type, vetoed figure). What they do not carry (the sign
  override's figure, reconciliation, transaction effects) has to come from a page reading anyway.
- It keeps the 672 construction reproducible from the same records with a flag.

Design: a new register `data/mature_cohort_figures.json`, one entry per record whose gross triangle figure a sign-only
rule displaced, holding `figure_m` (report currency), `displaced_by` (`sign_override` | `veto`), `displaced_figure_m`,
`triangle_page`, the reconciliation (`co_g`, the table total or latest diagonal, class), and the two readings, pages and
quote (the R213 evidence contract, `_evidence_gaps`). A loader step `apply_mature_cohort_figure(cm, entry, blocks=...)`,
modelled on `apply_confirmed_figure`, runs before the basis and cohort decisions and before the FX conversion and writes
route `{"source": "mature_cohort_triangle", "figure_kind": "triangle", "basis": "gross", ...}`; `pyd_basis` and
`pyd_cohort_scope` read it like the confirmed-figure route (gross; `mature-enforced`). The register is generated by a
script that recomputes each figure with the extraction's estimator read from `LLOYDS_EXTRACTION_REPO` at the pinned
commit (as `tri_compute.py` does: parse, do not import), so the analysis does not fork the estimator. Records whose
readings find an evidence-based reason not to restore get an entry with no figure and the reason (as the
`gross_triangle_does_not_reconcile` entries do).

A test must hold the register to the corpus, not to itself: it scans every record for a gross `_rag_triangle` displaced
by a `rag_provisions` route or a `[RAG|CODE] PYD NOT APPLIED` note (the population `measure.kind` finds) and requires
each to be in the register, with a figure or a stated reason.

## 2. The rule

**Valid mature-cohort figure.** A record's figure is a valid mature-cohort figure when all of these hold:

1. it is computed from a printed, absolute-amount claims development triangle of the syndicate (entity bound;
   `units` monetary; not a loss-ratio grid), by the deterministic estimator, as the latest less the previous diagonal
   over the underwriting years u <= t-2 the table develops (`_diagonal_cells`), with at least one such column;
2. the estimator accepts the grid: structure score >= 0.5, every mature current estimate on the report-year diagonal,
   no negative cumulative cell, no step below `MIN_STEP_RATIO`, no year-like contamination, max underwriting year in
   range;
3. the table is gross (its `type`, and its total reconciles to the filing's gross claims outstanding or its latest
   diagonal to the filing's gross latest-estimate total, the census's 2% rule);
4. no transaction in the step: no RITC, loss portfolio transfer or other take-on in either diagonal that the opening
   reserves do not carry (the take-on registers settle this; an "X and prior" column whose last two diagonals are not
   like-for-like, as 2007/2015's, is the same failure);
5. or a figure two readings confirmed from such a triangle (`pyd_confirmed_figures.json`, `figure_kind` "triangle").

**When a triangle figure may be overridden, and on what evidence.** Only on evidence about the triangle itself:

| Evidence | Test | Stays as |
|---|---|---|
| arithmetic | the triangle does not recompute from the printed page (a misread cell, misaligned grid, wrong scale) | repair to the printed table's figure (`pyd_confirmed_figures.json`), or exclude |
| gross/net basis | the used table is the net one | repair to the gross table's figure, or exclude as net |
| table validity | fails reconciliation (census class C after reading), shape fail confirmed on the page, a results note read as a triangle | exclude: `gross_triangle_does_not_reconcile`, or repair |
| transaction effects | an RITC or transfer in the step's diagonals | take-on base adjustment, or exclude as a take-on |
| cohort coverage | no column up to t-2 (`no_mature_cohort`), or the aggregated column's last step is not a report-year movement | exclude (no mature cohort) or undeterminable |

**Existing override reasons mapped:**

| Reason in the code | Class | Under the rule |
|---|---|---|
| provisions sign-disagreement override (`extract_pyd_from_relevant_pages` l.3471-3481) | sign only | goes |
| R138 movement-semantics test on the provisions figure (l.3457-3465) | evidence (about the provisions row) | stays, but no longer decides a triangle |
| veto (a): both models agree on the other sign (`_pyd_override_gate` l.5500) | sign only | goes |
| veto (b): figure > 50% of opening while both models < 10% (l.5511-5515) | value only | goes as an override; becomes a reading trigger (1861/2020 is the one record it decided) |
| `CODE PYD NOT APPLIED` (same gate on the models' own triangles, `verify_triangles`) | sign or value only | goes for the decision; the models' own triangles are not promoted (they leave out "X and prior" columns by instruction) |
| hand-confirmed figure applied over the veto (`_rag_veto`, R213) | evidence | stays (becomes unnecessary) |
| RAG sanity: release below -100% of opening (l.5845) | evidence (arithmetic impossibility) | stays |
| RAG sanity: strengthening above +200% of opening (l.5851) | value only | keep as a reading trigger; it decided no restored record |
| non-zero figure on zero opening (l.5855) | evidence | stays |
| structure score < 0.5, `_diagonal_cells` refusals, `MIN_STEP_RATIO`, negative cells, year-like values, UW-year range | evidence (table validity, arithmetic) | stays |
| percentage/loss-ratio detection | evidence (not an absolute-amount table) | stays |
| entity binding, foreign/closed-year tables skipped | evidence (cohort/entity coverage) | stays |
| `no_mature_cohort` (extraction l.5645, loader M01) | evidence (cohort coverage) | stays |
| `gross_triangle_does_not_reconcile` (loader) | evidence (table validity) | stays |
| take-on registers, assumed-business regime | evidence (transaction) | stays |
| net triangle treated as authoritative, then excluded on basis in the loader | evidence (basis) | stays |
| loss-ratio fallback over a contradicting narrative | sign only, managed level | the 3 leave the primary (section 3) |

## 3. The whole population, per record

All counts are on the committed records, rule applied in the loader (`sim.py`), nothing else changed.

| | Records |
|---|---|
| working sample now (the 672 construction) | 672 |
| of which a triangle figure now (cohort-enforced) | 571 |
| sign-override records whose triangle comes back | **29 of 29** |
| veto records whose triangle comes back | **32 of 34** |
| veto records with no triangle to restore (the vetoed figure was the provisions note's: 2008/2016 +298.5, 2008/2018 +437.1, magnitude gate) | 2 |
| loss-ratio figures (2623/2019, 3623/2017, 623/2022) | 3 |
| stated or model-read movements with no triangle figure | 35 |
| **records that enter the working sample** (a gross triangle displaced by the veto; the models' figure was net or unstated, so the record was excluded on basis) | **25**: 16 from NET_BASIS, 8 from UNKNOWN_BASIS, 1 from INCOMPLETE (6107/2023) |
| records whose figure changes but which stay outside (no usable weights: 3002/2017, 3002/2019, 3002/2020, 3002/2024, 6104/2016, 6117/2018, 6117/2024, 779/2015; INCOMPLETE: 779/2016, 6134/2024; run-off: 1206/2019, 1209/2016) | 12 |
| working sample under the rule | 697 |
| **primary sample (cohort-enforced, gross)** | **657** = 571 + 29 + 32 + 25, from 118 syndicates |
| leave the primary, kept in the 672 sensitivity | 40 = 35 + 3 loss-ratio + 2 veto without a triangle |
| records leaving the working sample | 0 |

Every restored figure has the other sign from the figure it replaces (61 of 61, by the rules' construction). Among the
61, adverse figures go from 16 to 45; the mean severity of the 61 moves from -0.0078 to +0.0368; 23 of the 25 entrants
are adverse (mean +0.0653). The primary's mean severity is +0.0307 against +0.0228 for the 672. Two restored records
reach the ten largest severities of the primary: 1861/2020 (+0.782, an entrant, rank 3) and 1945/2020 (+0.605, rank 9).

Not restored, by an evidence rule that stays: 2007/2015 and 2014/2017 (a code triangle already stands; 2007/2015's
RAG figure +148.8 rests on a "2010 & prior" column whose last step two readings found not like-for-like); 1991/2018,
2010/2018, 3010/2018, 3010/2019, 3010/2022, 3500/2018, 6112/2016 (a confirmed-figure register entry decides);
1947/2019, 2014/2015, 6125/2017 (no column up to t-2); 1183/2019 (net table); 2001/2014, 3010/2017, 4444/2021,
4472/2014 (no gross RAG triangle, or the vetoed figure is not one).

Cross-checks against the loader's census rules (all run inside the unchanged `load_and_classify`): no restored record
trips `no_mature_cohort`, the opening-reserve floor, the run-off rules, the take-on register or the provision-movement
rule; every entrant has reconciled weights and an HHI; no sign correction fires (the direction follows the figure). The
basis of every restored figure is decided by its triangle route (gross); three entrants carry a basis-register entry
written about the replaced figure (1686/2021 and 1880/2020 "unknown", 3000/2021 "net"), which the triangle route
supersedes in `pyd_basis`, so the reading must confirm the gross table. Reconciliation (census rule, deterministic
run): A 80, B 1 (1084/2020), C 3 (2015/2021, 2987/2023, 3000/2024), D 2 (1225/2016, 780/2016) of the 86 in the
primary; shape check: 84 pass, 2 fail S4 (3902/2024, 4020/2024: every tested column one row short, the grid reads one
row up). Five carry the assumed-business regime (1084/2022, 1686/2021, 1861/2020, 3000/2016, 4000/2022).

Earlier readings support the rule where they looked: 1221/2024, 2010/2020 and 3000/2024 were each read as the
provisions or prior-year line holding the t-1 underwriting year's own step (2010/2020: the 2019 year's +87.1m sits in
the stated line; the triangle over u <= 2018 gives -14.9m), which is the reviewer's mechanism.

The 3 loss-ratio records: computed over u <= t-2, but from a managed- or group-level grid (ratio times managed
ultimates), not the syndicate's absolute-amount table. Recommended out of the primary (section 6, Q3).

## 4. Records to read before any refit

All 86 records whose figure changes inside the new working sample (`per_record.csv`, `change` = "figure restored to
the triangle's" or "enters the working sample"), with the filing path, the triangle page, the triangle figure, the
figure it replaces, the census class, the shape class and `what_to_check`. Tiers:

- **Tier 1 (20), read first, two readings each:** 780/2016 (D: the stored grid is not found on the page), 1084/2020
  (B: the table reconciles to net), 1084/2022 (the take-on census's first reader found the 1 January 2022 RITC of
  Syndicate 2088 carried in both printed tables; its second reader called the RITC a take-on outside the note), 1225/2016 (D), 1686/2021 (RITC; basis register "unknown"), 1699/2024 (S +0.372), 1861/2020 (S
  +0.782, the magnitude veto, RITC), 1880/2020 (basis register), 1945/2020 (S +0.605), 2001/2022 (+969.6 against
  -256.3, S +0.318), 2015/2021 (C), 2987/2023 (C), 3000/2016 (RITC), 3000/2021 (basis register "net"), 3000/2024 (C),
  3902/2024 and 4020/2024 (shape S4), 4000/2022 (RITC and an inward transfer), 6130/2018 (S -0.290), 6134/2023
  (S +0.317).
- **Tier 2 (43):** the other entrants (census rules on each), and restored records no earlier reading recomputed.
- **Tier 3 (23):** restored, census class A, shape pass, and an earlier reading already recomputed the same triangle
  figure from the printed page (one reading for transaction and cohort coverage).

What every reading records: the printed gross table (page, units, columns), the u <= t-2 latest-less-previous
recomputation, any "X and prior" column and whether its last two diagonals are like-for-like, the table's total against
the filing's gross claims outstanding, any RITC or transfer in the step, and the stated prior-year line less the
triangle figure (how much of it is year t-1 or a transaction).

Reading resources on the PC (no paid API): the filings, `D:/dev/lloyds_reserve_stress_testing/syndicate_reports/pdfs/`
(1,065) and `pdf_extraction/html_converted/` (95 HTML filings as PDFs); the OCR page cache
`pdf_extraction/ocr_page_cache/` (204 filings); `results/extraction_error_rate/scripts/filing_pages.py` (text layer, or
Tesseract at 240 dpi for a scanned page; writes nothing); page images rendered on demand (the census's render helper,
or `fitz`); the census method and brief in `results/extraction_error_rate/triangle-table-scan/eye-reading-brief.md` and
`protocol/error-rate-protocol-table-scan.md` (deterministic scan, then readers place totals by eye, then the class is
recomputed by the rule); the reading packs and verdict files of the earlier draws for the 33 records already read
(`prior_readings.json`). Readers are Claude agents.

## 5. Knock-on effects

Every analysis step reads the sample from `model/exposure_results.json` (`adopted_model.load_sample`: `s_raw_a`, opening
reserves and HHI present), so the change moves every step in `reproduce.py`'s `STEPS` after `build_working_sample.py`:
all six calibrations (headline fit, RITC regime, gamma-free, systemic, hetscale, size-loaded) and their posterior draws;
every check under "checks" (pooling CV and extended CV with their folds, clustered SE, Bayes model comparison, k
support and half-k, prior masses, random effect, large-book slope and flattening, mean-zero boundary, missingness,
margin, skew-t, serial and temporal correlation, systemic share and PPC, donor review, FX, outbound transfer, proxy
stress, maturity denominator, long-tail share, RITC robustness, shape invariance); the tails (vignette uncertainty,
operator backtest, donor influence, error-rate propagation, vignette 1 diagnostics, GPD and Bayesian GPD,
`check_cohort_scope.py`); and the outputs (`run_analysis.py`'s exposure results, distortion tool, paper pack tables and
figures, `make_paper_figures.py`, `build_current_results.py`, `generate_data_audit.py`). `build_maturity_share.py`
must cover the 25 entrants. `declared_outputs()` lists every file these write. Error-rate propagation needs its frame
restated (the unread records change: 86 records get new figures, 25 are new). The extraction error-rate study's
figure-source rule (`draw_error_rate_fourth.figure_source`) needs the new route name. Manuscript: Equation (1)'s
footnote and Section 3.2 (571/101), Section 3 data counts (672, 118 syndicates, 11 years), every posterior and vignette
figure, Table `tab:reconcile` (App 2.3), App 2.1 (the precedence paragraph: both sign-only rules leave the primary),
App 2.2 (the 101 split, the 672 and 299 frames, the census counts), the supplement's S5 (cohort scope) and S20, and
the claim-registry computations `stated_movement_routes` and gates that read 672.

**The 672 construction can be kept as a sensitivity through a flag.** `ANALYSIS_CONFIG["outcome"]` (or an argument to
`load_and_classify`) with values `"mature_cohort"` (primary: apply the new register; tag the 40 non-triangle records
`NO_MATURE_COHORT_FIGURE` with no severity) and `"precedence_672"` (skip both, reproducing today's records exactly).
The sensitivity script replaces `check_cohort_scope.py`'s role in reverse: it calls the loader in memory with
`"precedence_672"` and refits and transfers on the 672, beside the primary, by the same functions (`refit_vignettes`),
so no second `exposure_results.json` is needed.

## 6. Risks and open questions

1. **Restored triangles can be wrong where the old rules were right.** R193 restored the veto because, where checked,
   the models were right (3010/2022's exempted triangle). Since then two readings confirmed 3010/2022's triangle figure
   (-10.926) under the clarified rule, so that precedent now points the other way, but the rule only says a sign is
   not evidence. Recommendation: read all 86 before the refit (tier 1 twice), and register a figure only from the
   readings.
2. **Transaction effects in mature cohorts.** RITC or transfers restate a triangle (1084/2022's 2088 RITC; 1861/2020 is
   +357.2m at S +0.78 against the models' +7.9m). Recommendation: read every assumed-business record for a take-on in
   the step; adjust the opening reserves (take-on base) or exclude as a take-on, by the existing registers.
3. **The 3 loss-ratio records.** Recommendation: out of the primary (managed level; a ratio grid times managed
   ultimates); in the 672 sensitivity. Alternative: keep them, at the cost of a second outcome definition inside the
   primary.
4. **The 25 entrants enlarge the sample** (657 primary, not 571 + 61 = 632). They follow from the rule (their gross
   mature figure was displaced on sign). Recommendation: include them after the census reading; report the primary
   with and without them in the supplement.
5. **The 40 non-triangle records.** The models' own triangles give a figure for some (1919/2019: +92.6 against
   +64.2). Recommendation: do not promote model-transcribed grids (they leave out aggregated columns by instruction);
   the 40 stay in the sensitivity only.
6. **The direction of the change is systematic** (45 of 61 adverse after, 16 before; two new top-ten donors), so the
   VaR will move materially. The 571-only fit already moved Vignette 1's VaR99.5 by +11% read by rank. Recommendation:
   do not predict the number; read, then run the recorded pass on the PC.
7. **The register keeps the estimator in one place** only if the generator parses the extraction source at the pinned
   commit. Recommendation: a cross-repository test that the register's figures equal that recomputation, and the
   corpus-driven completeness test of section 1.
8. **2007/2015** stays in the primary on its code-triangle figure (-2.0, the models' triangles without the "2010 &
   prior" column), which two readings found undeterminable. Recommendation: decide with the readings whether it is a
   valid mature-cohort figure (coverage rule) or leaves the primary.
