# Data provenance

This analysis consumes structured data produced by a separate extraction project,
**lloyds-reserve-stress-testing** (<https://github.com/colinpriest/lloyds-reserve-stress-testing>).
That project retrieves Lloyd's syndicate annual reports, runs a dual-LLM extraction over
them, and audits coverage; this project takes its outputs as inputs and does the dispersion /
scenario-transfer modelling. This file records exactly what was imported and when.

## 1. Source project and artefacts

| Artefact | Path (in this repo) | In extraction repo's git? | Role here |
|---|---|---|---|
| Extracted structured data | `pdf_extraction/syndicate_{N}_{YYYY}.json` | yes | primary input to `run_analysis.py` |
| RITC flags | `pdf_extraction/ritc_scan.json` | yes | with the transfer register, the assumed-business tail regime (`src/assumed_business.py`) + de-RITC operator |
| Transfer register | `pdf_extraction/audit/portfolio_transfer_adjudication.json` | yes | confirmed inward transfers, placed in the same regime as RITC (PLAN R195) |
| Run-off register | `pdf_extraction/audit/runoff_register.json` | yes | for each record with a development figure and a gross written premium at or below zero, whether its filing states the syndicate is in run-off that year (page, file hash, quote); a negative-premium year is a run-off year only when it does (the author's decision D1, 30 September 2026) |
| Corpus-wide run-off register | `pdf_extraction/audit/runoff_corpus_register.json` | yes | what each filing says about the syndicate's own run-off, year by year (page, file hash, quote); a year whose filing states run-off for the whole year, outside the assumed-business regime, is a run-off year, with or without a development figure (the author's decision of 1 October 2026) |
| Extraction audit | `pdf_extraction/audit/` | yes | per-filing extraction QA |
| Coverage audit | `syndicate_reports/coverage/coverage_status.{xlsx,json}`, `coverage_report.md` | yes | market-coverage denominators |
| Lloyd's lists workbook | `syndicate_reports/Lloyds_Syndicates_2014_2024.xlsx` | yes | the syndicates on Lloyd's lists by year, 2014-2024 (`src/market_active.py` holds the official active lists to it) |
| Download ledger | `syndicate_reports/download_status.json` | yes | which filings were retrieved |
| Portfolio-transfer scan | `pdf_extraction/portfolio_transfer_scan.json` | yes | not read here: kept equal to the extraction's copy so that the two repositories hold one version of it |
| Raw PDFs | extraction repository, `syndicate_reports/pdfs/` (PDF or HTML) | **no** (1,065 files, not committed) | source documents, not redistributed |

The raw PDFs are deliberately not committed (volume + redistribution); everything downstream
is re-runnable from the committed JSON, and what has been demonstrated is the recorded
clean full-manifest run (`reproduce.py --verify` prints its coverage; see the README). The
extraction itself is reconstructible from the public filings but not re-runnable from
this repository alone.

## 2. What changed in this import

The current import is the extraction's commit `57b4b14d8e066bd7b71a3c33d7bdb8e3a2ea06cb` (4 October 2026): every
artefact the table above names holds that commit's content, byte for byte. It replaces `2ee4007e` (1 October 2026)
because stage 2 of the fix cycle for the review of 2 October 2026 changed the extraction: the triangle reader's
report-year diagonal check (M-1), signed class premiums, the calendar-year mix column, the "&P" cohort label and the
widened run-off statement forms, with 151 record files, both run-off registers, the scans, the audit files and the
coverage files re-committed. The extraction's two new files, `stage2_triangle_census.json` and `download_addendum.json`,
are not imported: nothing here reads them.

The earlier snapshot of this analysis was built on a smaller, older extraction (622 filings)
with a pronounced recent-year retrieval gap. This import replaces it with the current
extraction:

- **1,065** syndicate-year extraction files (was 622).
<!-- ritc-counts:start -->
- **`ritc_scan.json`** added — a deterministic RITC scan (sentence classifier, not a
  language model), keyed `{syndicate}_{year}` with `ritc_occurred` and `confidence`.
  It scans all **1065** collected filings and flags **47** (47 strong).
- **Confirmed inward transfers join the same regime** (PLAN R195): the hand-adjudicated
  register `pdf_extraction/audit/portfolio_transfer_adjudication.json` and the take-ons
  two readings confirmed (`data/opening_reserves_takeon_base.json`, R221) confirm **31**
  syndicate-years that take on another syndicate's liabilities by transfer; **18** of them
  also accept RITC and **13** enter the regime by transfer alone, so it holds **60**.
  Those syndicate-years fall in three different populations, and the counts are not
  interchangeable: **55** are in the **902-record corpus**, and **34** are in the
  **working sample** (`n_ritc` in `results/check_ritc_scale_term_results.json`).
<!-- ritc-counts:end -->

- Coverage audit and download ledger added, giving official active-syndicate denominators.

After the pipeline's eligibility filters (`run_analysis.py`):

```
1065 files -> 902 corpus -> 649 modelling sample
  the loader's stages are disjoint and subtract to the corpus
  (generated by src/build_current_results.py from the disposition flow in
   model/exposure_results.json, asserted at build time):
    1065 - 20 excluded - 107 skipped - 4 no usable development reading - 28 in run-off - 4 no reserves above the floor = 902
  from the corpus to the working sample, also disjoint:
    902 - 98 net or unstated basis (82 net, 16 unstated; `data/pyd_basis_register.json`,
     `src/pyd_basis_rule.py`) - 8 take-on, not development
     (`data/takeon_not_development.json`) - 73 unusable severity - 0 missing opening reserves
     - 74 without premium weights = 649
  117 of the 1065 filings carry no usable dual-model extraction. That is a diagnostic
  of extraction quality and OVERLAPS the stages above; it is not a further subtraction,
  and treating it as one is what made an earlier version of this flow fail to add up.
Corpus:          902 syndicate-years / 133 syndicates; 39 appear in all 11 years (2014-2024)
Modelling sample: 649 syndicate-years / 118 syndicates
```

What two readings of a filing establish about a record's figure is registered in `data/pyd_confirmed_figures.json`,
and the loader (`src/run_analysis.py`, `apply_confirmed_figure`) acts on each entry before the basis decision: a
confirmed figure replaces the adopted one; a basis the readings established (net or unknown) excludes the record at
the basis step, as 1880/2014 and 1218/2015 are on the net basis (the settled net-basis rule); and an entry may name a
rule. The one rule, `gross_triangle_does_not_reconcile` (the author's decision of 13 October 2026): a record whose
printed gross development triangle does not reconcile to the filing's own totals carries no severity and leaves the
working sample, unless a precedence rule (the provisions sign-disagreement override, or the model-agreement veto) puts
another figure in the triangle's place. The record keeps its figure on the gross basis, carries no severity, and
leaves at the unusable-severity step tagged `GROSS_TRIANGLE_DOES_NOT_RECONCILE` (a scientific exclusion in the
inferential ledger). The entry carries the failed reconciliation, and the loader refuses one whose latest diagonal is
within 2% of the filing's gross total, and one for a record whose adopted route is not a triangle's (a precedence rule
put another figure there). 4020/2017 is the one record: its latest diagonal, 2,006.546m, against the same note's gross
total of latest estimates, 1,935.876m (the net table ties), and its older columns the 2016 report's triangle one
column over. Its adopted figure is the triangle's (+21.188m); its stated gross movement (+8.718m, which covers all
prior years, year t-1 included) and the models' reading share the triangle's sign, so neither the override nor the
veto applies. The triangle-table census of 13 October
2026 (`results/extraction_error_rate/triangle-table-scan/`) found no other working-sample record whose table fails a
total the filing prints for it. Take-ons that are not development are registered apart
(`data/takeon_not_development.json`).

The primary outcome (the owner's decision of 22 October 2026, option c) is the mature-cohort movement of Equation (1):
the gross prior-year movement over underwriting years u <= t-2, a valid mature-cohort triangle figure never replaced
merely because a broader movement has the other sign (`ANALYSIS_CONFIG["outcome"] = "mature_cohort"`). The extraction's
two sign-only precedence rules (the provisions sign-disagreement override and the model-agreement veto) displaced a
printed gross triangle's figure in 110 records of the corpus; `data/mature_cohort_figures.json` holds each, with the
triangle's figure recomputed from the stored grid by the extraction's own estimator at the pinned commit and its
readings (`results/extraction_error_rate/mature-cohort/`), or no figure and the reason, and `src/build_mature_cohort_figures.py` rebuilds it.
The loader (`apply_mature_cohort_figure`) adopts the figures, refusing an entry unless every model block of the record
shows the displaced gross triangle; a reliable gross record whose figure is not mature-enforced (a stated or model-read
movement, a loss-ratio reading) carries no severity and leaves at the unusable-severity step tagged
`NO_MATURE_COHORT_FIGURE`. Take-on bases and take-ons that describe the step of a mature-cohort figure carry
`figure_route: "mature_cohort_triangle"` in their registers and apply under the primary only. The 672-record
construction before the decision is reproduced exactly by `load_and_classify("precedence_672")`, the sensitivity
`src/check_cohort_scope.py` reports beside the primary.

Two further rules apply under the primary only (the author's decisions of 22 October 2026, each on two independent
readings of the filings, F1 and F2, archived under `results/extraction_error_rate/mature-cohort/fx-translation/readings/`).
Exchange rates (rule B): a record leaves when its development table is not retranslated between the year t-1 and year t
reports across a sterling/dollar move of 5% or more and the filing's own gross claims-outstanding roll-forward prints an
exchange line of at least 5% of the opening gross claims outstanding. `data/fx_untranslated_excluded.json`
(`src/build_fx_untranslated_excluded.py`) holds the four records both conditions hold for (1897/2016, 2468/2016,
5151/2016, 5151/2017; they leave at the unusable-severity step tagged `FX_UNTRANSLATED_TABLE`) and the nine candidates
read and kept. Aggregated columns (Appendix 2.1): the figure leaves out a development-age column that adds older years
(`2014 & Prior`, `2013&Prior`), which moves 1945/2024 to +5.264 and 1945/2023 to -4.997 in
`data/mature_cohort_figures.json`. The outward-transfer sensitivity register
(`data/outbound_transfer_retained_base.json`) gained 2689/2022 and 1492/2023 from the same readings.

<!-- coverage:start -->
Coverage is **68 % of active syndicate-years overall** (649 of 953; it was ~47 % on the
old dataset), and it is **uneven, not flat**: the annual rate runs from **62 % in 2016 (61 of
99)** to **80 % in 2024**, with every other year between 62 % and 80 %. The 2020–2024 retrieval
gap in the old dataset is closed (90–95 PDFs retrieved per year in 2020–2024 vs 92–98 active syndicates),
<!-- coverage:end -->

so the residual shortfall combines scope, disclosure availability and extraction/output states.
The 117 filings with no usable dual-model output cannot all be labelled OCR failures: the
record-level inferential ledger keeps economic eligibility, disclosure availability and extraction
status separate. The missingness section below reports the size selection that is present and
does not claim the absences are unrelated to syndicate characteristics. Full year-by-year and against-official-list tables are in
`docs/appendix-data-audit.md` in the analysis repository (§B.5), regenerated on this dataset.

<!-- round-55-correction:start -->
### The round-55 data correction (10 September 2026)

Two extraction rules were corrected and the records they touch were re-extracted offline from the committed response and table caches: the percentage-against-monetary decision, which now rests on a table's own unit evidence before any magnitude heuristic; and the transposed-grid parser, which now captures one basis block of a page printing a gross and a net triangle under one header and labels it by that block's own heading. The route by which each record's development figure was adopted is recorded on the record (`_pyd_route`) instead of being inferred from a sentence in its notes.

**Every record that moved is listed, with its figure and route on both sides, in `docs/extraction-changelog.md` in the extraction repository** (<https://github.com/colinpriest/lloyds-reserve-stress-testing>), generated by `scripts/extraction_changelog.py` by diffing the committed records against the previous pin. Reports whose page caches cannot serve an offline replay are listed in `pdf_extraction/audit/offline_unservable.json`; their committed records stand unchanged.

The counts at `9c2895f`, before the correction, and now. The change is not the correction's alone: it also carries every rule and extraction import since (the run-off rules, rule M01, the basis and take-on registers among them).

| | at `9c2895f` | now | change |
|---|---:|---:|---:|
| Corpus | 919 | 902 | -17 |
| Net or unstated basis | 157 | 98 | -59 |
| Unusable severity | 9 | 73 | +64 |
| Missing premium weights | 75 | 74 | -1 |
| **Working sample** | **678** | **649** | **-29** |
<!-- round-55-correction:end -->

## 2b. Reporting currency (converted to GBP at reporting-date spot)

The dataset is **single-currency GBP**. Each filing's presentation currency is determined from
the source PDF with provenance (statement page, nearest section heading, verbatim quote) by
`currency_scan.py`, and USD-presented filings are converted to GBP inside `run_analysis.py` at
the **reporting-date spot rate** — the last Fed **H.10** business-day rate on or before
31 December of the reporting year (`fetch_h10_rates.py` → `fx_rates_h10.json`, from
<https://www.federalreserve.gov/releases/h10/hist/dat00_uk.htm>): GBP = USD / (USD per GBP).
Full methodology, the eleven year-end rates and dates used, and the provenance hierarchy are in
[fx-conversion.md](fx-conversion.md).

Corpus currencies (1,065 filings): **747 GBP / 284 USD / 34 undetermined**. None of them is in the
902-observation dataset: they are no-model files that never enter the analysis. **No currency other
than GBP or USD was found** in a filing the scan or a model read (1100/2024, published only as HTML,
read by neither and outside the analysis, states the euro).
The 902-observation dataset is **660 GBP / 242 USD (27%) / 0 undetermined**. The scan
found zero disagreement with the dual-LLM `currency` field when it ran; taken one model at a time,
the fields differ from it for 12 corpus records, one of them in substance (780/2015, where the
filing settles USD). Every observation carries
`report_currency`, `fx_applied`, `fx_rate_usd_per_gbp`, and `fx_rate_date`.

The conversion matters for **one** variable only. The primary severity
$S=\text{PYD}/\text{reserves}$ and the HHI are **within-filing ratios**, so they are
**currency-neutral** and unaffected by conversion. Only the **size** variable $R$ (and premium
levels) change scale. `fx_sensitivity.py` quantifies the effect by refitting the headline model --- at the adopted
implementation and sampling configuration (4 chains x 1500 post-warmup draws), so the converted
baseline reproduces the published calibration --- on nominal (as-reported) sizes reconstructed
at the same year-end rates; results are reported in
`fx_sensitivity_results.json` (the pooling exponent moves by 0.002 and the clean tail by 0.03;
the Vignette-1 VaR$_{99.5}$ moves 0.2% -- 0.330 converted against 0.331 nominal, both committed
in that file with each fit's own 95% HDIs and sampling diagnostics. These are point
sensitivities of two separately fitted posteriors: no posterior interval for the
between-treatment difference is estimated; the tail-regime point ordering recurs under
each fit's own posterior and is resolved under neither (that file carries each fit's
$P(\nu_{\mathrm{RITC}}<\nu_{\mathrm{clean}})$), while the floor and $k$ rows are conditional summaries
within the adopted specification -- the floor-versus-no-floor and pooling-endpoint
model comparisons were not repeated).

## 2c. Sample selection: inferential disposition first

The 1065 filings are classified before any selection diagnostic: 107 have no eligible
outcome structurally, 20 have economic eligibility unresolved because the extraction has no
deterministic reading of them (its parsers found no prior-year figure and its models were not
run: nothing is established about those filings), 256 are scientific exclusions, 9 have an eligible but
unavailable outcome, 24 have an observed eligible outcome but no usable composition,
and 649 enter the model. The supported disclosure-defined target is therefore 682
records. If all 20 unresolved filings were economically eligible, the broader potential
target would be 702; the primary selection analysis does not claim to describe it.

The selection response is membership in the 649-record model sample. Within the
682-record supported disclosure-defined target, included records have median size £418.9m against £29.5m
for records not included (filing reserves, or a same-syndicate median where unavailable).
This shows selection by size within that supported target; missing-at-random cannot be
established, and selection from the broader economically eligible population is not
identified. The former
opening-reserve-availability and failure-prone regressions are withdrawn because their
response mixed structural stubs, scientific exclusions and target-population records.
The complete counts and diagnostics are generated in `docs/current-results.md` from
`missingness_check_results.json`.

Three sensitivities are reported instead of resting on it: bounded IPW with three
probability floors, a stress for the 9 known eligible unavailable outcomes, and a
separate broader-potential-target stress that assumes all 20 unresolved cases eligible.

<!-- missingness:start -->
- **Bounded selection weighting (IPW).** Response propensity
  $\operatorname{logit}P(\text{model-sample membership})\sim\log R+\text{year}$ measures selection
  gradient (coefficient on $\log R$ $+0.92$). Refitting with each observation weighted
  by $[1/\max(\hat p,0.15)]/\operatorname{mean}[1/\max(\hat p,0.15)]$ — moves the pooling exponent to
  $k=0.628$ $[0.534,0.719]$ against $0.599$ $[0.509,0.697]$. 1 of 649 model
  records lie below the 0.15 floor; $\hat p_{\min}=0.1266$, the mean-one weights span
  0.95--6.31 and have descriptive Kish ESS 606. Uncapped diagnostics span 0.95--7.47
  with ESS 594; uncapped weights are not fitted. Caps 0.10, 0.15 and 0.20 are refitted.
  The likelihood is $\sum_i w_i\log p(S_i\mid\theta)$; weights are fixed, so intervals
  are conditional and omit propensity-model uncertainty. At the primary cap, the floor is 0.028
  against 0.030; $\nu_{\text{clean}}=3.77$ against 4.02.
- **High-volatility eligible-outcome stress.** Appending only the 9 records whose outcome is
  eligible but unavailable moves the conditional bracketed estimate from $k=0.594$
  at $c=1$ to $0.564$ at $c=5$, between $0.564$ and $0.594$ across the grid. Because the
  construction makes those unavailable outcomes more volatile, it cannot test the
  adverse-to-sub-linearity direction.
  $\nu_{\text{clean}}$ moves 4.08 to 3.44 at $c=5$; this is not a bound.
- **Eligibility-unresolved stress.** Assuming all 20 filings with no deterministic reading were economically
  eligible expands the potential target from 682 to 702 and appends them with the 9 known
  unavailable outcomes. This 29-record stress moves $k=0.570$ at $c=1$ to $0.540$ at $c=5$.
  It is not a bound, not an estimate that those filings were eligible, and does not repair poor overlap.
<!-- missingness:end -->

(`missingness_check.py`, `missingness_check_results.json`,
`check_missingness_sensitivity.py`.)

## 3. Extraction method (as documented by the source project)

Each report is extracted independently by **two** LLMs — **Gemini 2.5 Flash** and **GPT-5
Mini** — and reconciled; `pdf_extraction/audit/` records per-filing agreement/QA. The RITC scan
is a targeted pass over the related-parties / RITC sections producing the `ritc_scan.json`
flags (evidence snippet, section, page, and a strong/weak confidence). A second deterministic
scan (`scripts/portfolio_transfer_scanner.py`) looks for loss portfolio transfers, novations and
commutations; each of its flags, and each transfer found by hand that it missed, is adjudicated
against the filing in `pdf_extraction/audit/portfolio_transfer_adjudication.json`. See the
extraction repo for prompts and the reconciliation logic.

## 4. How downstream code consumes it

- `run_analysis.py` — loads `pdf_extraction/*.json`, classifies lines, builds the corpus and
  the `n=649` modelling sample (gross-basis development only; each observation carries
  `pyd_basis` and `pyd_basis_source`), and writes `exposure_results.json` plus the paper
  tables.
- `calibrate_dispersion_ritc.py` — reads `exposure_results.json` and the assumed-business regime
  (`src/assumed_business.py`: the `ritc_scan.json` flags and the transfer register's confirmed
  inward transfers); fits the dispersion model with that tail regime and the concentration exponent fixed at 0
  in the likelihood (the headline); writes `dispersion_calibration_ritc.json` and
  `dispersion_posterior_draws_ritc.npz`.
- `calibrate_dispersion_ritc_gamma_free.py` — the same fit with the concentration exponent fitted (the
  concentration overlay's source); writes `dispersion_calibration_ritc_gamma_free.json` and
  `dispersion_posterior_draws_ritc_gamma_free.npz`.
- `vignette_uncertainty.py`, `gpd_var_uncertainty.py`, `bayesian_gpd.py` — read the donor pool
  and the assumed-business flags and apply the shape-aware (de-RITC) transfer operator for the vignette VaRs.
- `generate_data_audit.py` — mines the raw extraction to produce
  `docs/appendix-data-audit.md` in the analysis repository.

## 5. Reproducing from a fresh clone

1. Clone the extraction repo and copy its `pdf_extraction/` and `syndicate_reports/` outputs
   into this repo (the JSON only; the source PDFs stay in the extraction
   repository under `syndicate_reports/pdfs/` and are needed only to re-run
   `python src/currency_scan.py --pdf-dir <that folder> --allow-llm-fallback --replace-canonical`;
   the two flags are needed because the 2024 filings published only as HTML have no PDF).
2. `python reproduce.py` runs the whole manifest in its order (`python reproduce.py --list` prints it): the
   loader on the new records (`build_working_sample.py`), the calibrations, the checks and the tail
   analyses, then `run_analysis.py` again, so that the transfer tool, the paper pack and the vignette
   bundles embed the new calibration, and last the figures and the generated documents
   (`build_current_results.py`, then `generate_data_audit.py`). Running the scripts by hand in another
   order leaves outputs built on the previous calibration beside the new one.
