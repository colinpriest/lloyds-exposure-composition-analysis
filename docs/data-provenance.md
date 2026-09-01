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
Corpus:          907 syndicate-years / 133 syndicates; 34 appear in all 11 years (2014-2024)
Modelling sample: 790 syndicate-years / 123 syndicates
```

Coverage is now **~76 % of active syndicate-years overall** (was ~47 %), broadly flat across
2014–2024; the 2020–2024 retrieval gap in the old dataset is closed (~90–95 PDFs retrieved per
year vs ~91–99 active syndicates). The residual shortfall is dominated by failed extraction of
a minority of (older, scanned) reports — worst in 2014 — not by systematic omission of
particular syndicates. Full year-by-year and against-official-list tables are in
`docs/appendix-data-audit.md` in the analysis repository (§B.5), regenerated on this dataset.

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
levels) change scale. `fx_sensitivity.py` quantifies the effect by refitting the headline model --- at the adopted
implementation and sampling configuration (4 chains x 1500 post-warmup draws), so the converted
baseline reproduces the published calibration --- on nominal (as-reported) sizes reconstructed
at the same year-end rates; results are reported in
`fx_sensitivity_results.json` (the pooling exponent moves by 0.004 and the clean tail by 0.03;
the Vignette-1 VaR$_{99.5}$ moves 8.6% -- 0.393 converted against 0.426 nominal, both committed
in that file with each fit's own 95% HDIs and sampling diagnostics. These are point
sensitivities of two separately fitted posteriors: no posterior interval for the
between-treatment difference is estimated, and the qualitative conclusions are checked
under each fit's own posterior, also stored there).

## 2c. Missingness: size-biased, and not shown to be ignorable

Extraction failures are size-biased. Syndicates with at least one failed year are
materially smaller than never-fail syndicates, failed filings' syndicates are smaller
than successful ones, and failures cluster in older, scanned vintages (2014: 29%; 2018:
18%; others 7–12%). So the sample under-represents small, older-scanned and short-lived
syndicates by count. **The counts and test statistics are reported in
`docs/current-results.md` in the analysis repository (§ Missingness), read directly from
`missingness_check_results.json`** — they are deliberately not restated here, because
the copies in this paragraph had drifted from the committed values.

Two counts are easy to conflate and are not the same thing: the wholly empty extractions
in the collection flow above, and the filings that lack the prior-reserves field
`missingness_check.py` needs in order to score an observation. The diagnostic uses the
latter.

That is bias on the size **covariate**, and the model is conditional on size, so what
would matter is failure relating to the **outcome given size**. Regressing $|S|$ on
$\log R$ and a failure-prone indicator over the $n=790$ sample, **no such association is
detected**. That is the whole of what this supports, and it is not a no-bias finding:

- a failure to reject is not a demonstration that the effect is absent;
- the regression is estimated only over syndicates observed at least once, so it is
  silent by construction about the **37 orphan filings from 22 syndicates never observed
  at all**, for which no outcome exists;
- **missing-at-random therefore cannot be established from these data**, and this
  document no longer claims it.

There is also a small **location** shift (failure-prone books run off slightly more
adversely). The volatility model fixes $\mu=0$ and estimates no location parameter, so it
**cannot separate** a persistent location shift from dispersion — the shift can be
absorbed into the fitted scale, not excluded from it. The manuscript's random-intercept
sensitivity shows exactly this direction of effect (the floor moves from about 2.1% to
1.6% when partially pooled syndicate intercepts are added). This is distinct from the
operator, which acts on raw severities and carries each donor's realised level across;
$\mu=0$ is a *fitting restriction*, not an operator property.

Two sensitivities are reported instead of resting on it.

- **Selection weighting (IPW).** Response propensity
  $\operatorname{logit}P(\text{success})\sim\log R+\text{year}$ confirms the size
  gradient (coefficient on $\log R$ $+0.47$). Refitting with each observation weighted
  by $1/\hat p$ — up-weighting small syndicates by up to $2.3\times$ — leaves the fit
  essentially unchanged: $k=0.614$ $[0.538,0.682]$ against $0.606$ $[0.525,0.676]$,
  $\gamma=0.243$ unchanged, floor $0.019$ against $0.021$, $\nu_{\text{clean}}=2.44$
  against $2.43$.
- **High-volatility orphan stress.** Appending 37 pseudo-records at the size distribution
  of failure-prone syndicates moves the conditional bracketed estimate from $k=0.587$
  at $c=1$ to $0.570$ at $c=5$. Because the construction makes the predominantly
  small missing books *more* volatile, it cannot test the adverse-to-sub-linearity
  direction. Two parameters move
  materially: the concentration exponent $0.244\to0.174$ and the **clean-regime tail
  $\nu_{\text{clean}}$ from $2.44$ to $1.91$** at $c=5$. The tail is therefore *not*
  unaffected, and neither the tail nor the vignette VaRs should be described as such.

(`missingness_check.py`, `missingness_check_results.json`,
`check_missingness_sensitivity.py`.)

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
  `docs/appendix-data-audit.md` in the analysis repository.

## 5. Reproducing from a fresh clone

1. Clone the extraction repo and copy its `pdf_extraction/` and `syndicate_reports/` outputs
   into this repo (the JSON only; PDFs optional).
2. `python run_analysis.py` → `exposure_results.json` + tables.
3. `python calibrate_dispersion_ritc.py` → calibration + posterior draws.
4. `python vignette_uncertainty.py && python gpd_var_uncertainty.py && python bayesian_gpd.py`
   → vignette VaRs with the shape-aware operator.
5. `python generate_data_audit.py` → refreshed data-audit appendix.
