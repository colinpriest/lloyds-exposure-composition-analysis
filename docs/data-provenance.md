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
| RITC flags | `pdf_extraction/ritc_scan.json` | yes | RITC tail regime + de-RITC operator |
| Extraction audit | `pdf_extraction/audit/` | yes | per-filing extraction QA |
| Coverage audit | `syndicate_reports/coverage/coverage_status.{xlsx,json}`, `coverage_report.md` | yes | market-coverage denominators |
| Download ledger | `syndicate_reports/download_status.json` | yes | which filings were retrieved |
| Raw PDFs | `syndicate_reports/*.pdf` | **no** (1,065 files, not committed) | source documents, not redistributed |

The raw PDFs are deliberately not committed (volume + redistribution); everything downstream
is reproducible from the committed JSON.

## 2. What changed in this import

The earlier snapshot of this analysis was built on a smaller, older extraction (622 filings)
with a pronounced recent-year retrieval gap. This import replaces it with the current
extraction:

- **1,065** syndicate-year extraction files (was 622).
- **`ritc_scan.json`** added — a dual-LLM RITC scan not present before, keyed
  `{syndicate}_{year}` with `ritc_occurred` and `confidence` ∈ {strong, weak}. 162 RITC-occurred
  (88 strong, 74 weak); 140 fall in the modelling sample.
- Coverage audit and download ledger added, giving official active-syndicate denominators.

After the pipeline's eligibility filters (`run_analysis.py`):

```
1065 files (134 empty extraction) -> 931 extracted -> 907 corpus -> 790 modelling sample
133 syndicates; 34 present in all 11 reporting years (2014-2024)
```

Coverage is now **~76 % of active syndicate-years overall** (was ~47 %), broadly flat across
2014–2024; the 2020–2024 retrieval gap in the old dataset is closed (~90–95 PDFs retrieved per
year vs ~91–99 active syndicates). The residual shortfall is dominated by failed extraction of
a minority of (older, scanned) reports — worst in 2014 — not by systematic omission of
particular syndicates. Full year-by-year and against-official-list tables are in
[appendix-data-audit.md](appendix-data-audit.md) (§B.5), regenerated on this dataset.

## 2b. Reporting currency (converted to GBP at reporting-date spot)

The dataset is **single-currency GBP**. Each filing's presentation currency is determined from
the source PDF with provenance (statement page, nearest section heading, verbatim quote) by
`currency_scan.py`, and USD-presented filings are converted to GBP inside `run_analysis.py` at
the **reporting-date spot rate** — the last Fed **H.10** business-day rate on or before
31 December of the reporting year (`fetch_h10_rates.py` → `fx_rates_h10.json`, from
<https://www.federalreserve.gov/releases/h10/hist/dat00_uk.htm>): GBP = USD / (USD per GBP).
Full methodology, the eleven year-end rates and dates used, and the provenance hierarchy are in
[fx-conversion.md](fx-conversion.md).

Corpus currencies (1,065 filings): **743 GBP / 280 USD / 42 undetermined** (the undetermined are
all skipped no-model files that never enter the analysis; **no currency other than GBP or USD
was found**). The 907-observation dataset is **669 GBP / 238 USD (26%)**, with zero disagreement
between the PDF scan and the dual-LLM `currency` field. Every observation carries
`report_currency`, `fx_applied`, `fx_rate_usd_per_gbp`, and `fx_rate_date`.

The conversion matters for **one** variable only. The primary severity
$S=\text{PYD}/\text{reserves}$ and the HHI are **within-filing ratios**, so they are
**currency-neutral** and unaffected by conversion. Only the **size** variable $R$ (and premium
levels) change scale. `fx_sensitivity.py` quantifies the effect by refitting the headline model
on nominal (as-reported) sizes reconstructed at the same year-end rates; results are reported in
`fx_sensitivity_results.json` (structural parameters shift <2%; the Vignette-1 VaR$_{99.5}$
moves ~7%, well inside its uncertainty band).

## 2c. Missingness: size-biased, but not in the quantity the model estimates

Extraction failures (134 of 1,065 filings; the same figure this document gives in the flow above, and the one the manuscript reports) are **not** size-neutral. Probing failure-prone
syndicates via their successful years (`missingness_check.py`): syndicates with ≥1 failed year
have median size £140m vs £370m for never-fail syndicates (Mann-Whitney $p=0.002$), and failed
filings' syndicates are smaller than successful ones (£122m vs £362m, $p<0.001$). Failures also
cluster in older/scanned vintages (2014: 29%; 2018: 18%; others 7–12%). So the sample
under-represents small (and older-scanned, and short-lived / special-purpose) syndicates by
count.

That is bias on the size **covariate**. The model is **conditional on size**, so what matters is
whether failure relates to the **outcome given size** — and it does not, for the quantity
modelled. Regressing on the $n=790$ sample: the **dispersion** $|S| \sim \log R +
\mathbf 1[\text{failure-prone}]$ shows **no** failure-prone effect (coef $-0.011$, $p=0.30$) —
conditional on size, failure-prone syndicates have the same development dispersion. There is a
small **location** shift (signed $S$: $+0.030$, $p=0.028$; failure-prone books run off slightly
more adversely), but the volatility model fixes $\mu=0$ and does not estimate location, so this
does not bias it. The vignettes transfer to a fixed target size, so the marginal
under-representation of small syndicates does not bias the transferred VaR either.

**Net:** missingness is size-biased, but it is missing-at-random with respect to the
dispersion-given-size relationship the operator is built on — so $\sigma(R,H)$, the tail and the
vignette VaRs are unaffected. (`missingness_check.py`, `missingness_check_results.json`.)

## 3. Extraction method (as documented by the source project)

Each report is extracted independently by **two** LLMs — **Gemini 2.5 Flash** and **GPT-5
Mini** — and reconciled; `pdf_extraction/audit/` records per-filing agreement/QA. The RITC scan
is a targeted pass over the related-parties / RITC sections producing the `ritc_scan.json`
flags (evidence snippet, section, page, and a strong/weak confidence). See the extraction repo
for prompts and the reconciliation logic.

## 4. How downstream code consumes it

- `run_analysis.py` — loads `pdf_extraction/*.json`, classifies lines, builds the corpus and
  the `n=790` modelling sample, and writes `exposure_results.json` plus the paper tables.
- `calibrate_dispersion_ritc.py` — reads `exposure_results.json` and `ritc_scan.json`; fits the
  dispersion model with the RITC tail regime; writes `dispersion_calibration_ritc.json` and
  `dispersion_posterior_draws_ritc.npz`.
- `vignette_uncertainty.py`, `gpd_var_uncertainty.py`, `bayesian_gpd.py` — read the donor pool
  and the RITC flags and apply the shape-aware (de-RITC) transfer operator for the vignette VaRs.
- `generate_data_audit.py` — mines the raw extraction to produce
  [appendix-data-audit.md](appendix-data-audit.md).

## 5. Reproducing from a fresh clone

1. Clone the extraction repo and copy its `pdf_extraction/` and `syndicate_reports/` outputs
   into this repo (the JSON only; PDFs optional).
2. `python run_analysis.py` → `exposure_results.json` + tables.
3. `python calibrate_dispersion_ritc.py` → calibration + posterior draws.
4. `python vignette_uncertainty.py && python gpd_var_uncertainty.py && python bayesian_gpd.py`
   → vignette VaRs with the shape-aware operator.
5. `python generate_data_audit.py` → refreshed data-audit appendix.
