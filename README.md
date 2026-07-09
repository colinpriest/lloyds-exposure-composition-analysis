# Lloyd's Exposure Composition & Reserve-Development Dispersion

Analyses the exposure composition and prior-year reserve development (PYD) of Lloyd's
syndicates, using structured data extracted from syndicate annual reports (PDFs → JSON). The
core deliverable is a **robust Bayesian pooling dispersion model** and a **scenario-transfer
operator** that rescales historical reserve movements onto a user-specified target portfolio
(size, concentration, RITC status).

## Overview

- **`run_analysis.py`** — reads syndicate JSON extractions from `pdf_extraction/`, classifies
  data quality, computes line-of-business (LoB) weights, severity distributions and HHI, runs
  the analyses, and emits `exposure_results.json` plus the `paper_pack/` tables and figures and
  the `vignettes/` bundles.
- **`calibrate_dispersion_ritc.py`** — fits the dispersion model offline (Bayesian NUTS) and
  writes `dispersion_calibration_ritc.json` + `dispersion_posterior_draws_ritc.npz`, consumed by
  the pipeline and the vignette VaR scripts. (`calibrate_dispersion.py` fits the no-RITC-regime
  variant used only as a comparison baseline.)
- **`distortion_tool.html`** — self-contained portfolio basis-transfer tool (generated). The user
  enters a target LoB mix, reserve size and RITC status; the tool applies the dispersion transfer
  operator to the donor pool and shows raw vs target-basis distributions, summary statistics, a
  Shapley decomposition and per-syndicate-year worked examples. All data and dependencies are
  embedded — open in any browser, no server required.
- **`pdf_extraction/exposure_analysis.html`** — static dashboard that loads
  `exposure_results.json` and renders tables/charts (no computation of its own).

## The model (summary)

For syndicate *i* in reporting year *t*, severity `S = PYD / opening_reserves`:

```
S_it ~ Student-t(nu_it, 0, sigma_it)
sigma_it = sqrt( sigma_undiv^2 + sigma_div^2 * [ (R/R_ref)(1/H)^gamma ]^{2(k-1)} ) * exp(s_t)
nu_it    = nu_clean                      (clean years)
         = nu_clean * exp(-lambda_RITC)  (RITC years — heavier tail)
```

with `mu = 0` fixed, pooling exponent `k ∈ [0.5, 1]`, concentration via the effective line count
`n_eff = 1/H`, a positive undiversifiable floor `sigma_undiv`, a reporting-year shared shock, and
a Student-t tail split into a **clean** and an **RITC** regime (external reinsurance-to-close
fattens the tail only; see `scaling_analysis_writeup.md` §2.7).

Headline fit (n=790, 11 reporting years, single-currency GBP data — see
[docs/fx-conversion.md](docs/fx-conversion.md)): `k ≈ 0.61`, `gamma ≈ 0.24`,
`sigma_undiv ≈ 0.021`, `nu_clean ≈ 2.43`, `nu_ritc ≈ 1.55`, `P(nu_ritc < nu_clean) = 0.99`.

## The transfer operator

The operator **is** the fitted model applied. It is **shape-aware**: a donor severity at
`(R_s, H_s)` transfers to a target `(R_t, H_t)` by

```
S_adj = sigma(R_t,H_t) * F_inv[ nu_t ]( F[ nu_s ]( S_src / sigma(R_s,H_s) ) )
```

where `F` is the Student-t CDF. When `nu_s = nu_t` this collapses to the pure rescale
`S_src · sigma(R_t,H_t)/sigma(R_s,H_s)`; when the donor is an RITC year and the target is clean,
it **de-RITCs** the donor — thinning its heavy tail to the clean-composition tail. This is an
upstream distributional adjustment, not a tail model or capital-setting method.

## Statistical analyses

- **N0** — descriptive statistics and data-quality classification
- **N1** — LoB weight distributions and concentration (HHI)
- **N2** — severity distributions and tail analysis
- **N3** — panel regression of PYD on LoB weights (RE-GLS with James–Stein shrinkage)
- **N4** — bootstrap and leave-one-out robustness checks
- **Dispersion model** — the robust Bayesian pooling model above (size, concentration, floor,
  heavy tails, RITC tail regime), calibrated by `calibrate_dispersion_ritc.py`

## Project structure

```
├── run_analysis.py                 # Main analysis pipeline
├── calibrate_dispersion_ritc.py    # Dispersion model calibration (RITC tail regime)
├── calibrate_dispersion.py         # No-regime baseline calibration
├── vignette_uncertainty.py         # Vignette VaR intervals (shape-aware operator)
├── gpd_var_uncertainty.py          # Frequentist EVT (POT) VaR cross-check
├── bayesian_gpd.py                 # Bayesian EVT (POT) VaR cross-check
├── ritc_robustness.py              # RITC ALL/EXCL-strong/EXCL-all refit comparison
├── ritc_shape_invariance.py        # RITC scale/shape/tail invariance diagnostics
├── ritc_tail_shape.py              # RITC tail-index comparison (clean vs RITC)
├── exposure_results.json           # Output results bundle (generated)
├── dispersion_calibration_ritc.json          # Calibrated parameters (generated)
├── dispersion_posterior_draws_ritc.npz       # Posterior draws (generated)
├── distortion_tool.html            # Portfolio basis-transfer tool (generated, self-contained)
├── _distortion_tool_template.html  # HTML template for the tool (source)
├── pdf_extraction/                 # Input syndicate JSONs + ritc_scan.json + dashboard
├── vignettes/                      # Generated vignette bundles
├── paper_pack/                     # Generated figures and LaTeX tables
├── specifications/                 # Analysis and vignette specifications
├── docs/                           # Methodology notes, data provenance, data audit
└── requirements.txt                # Python dependencies
```

## Setup

Requires Python 3.9+.

```bash
pip install -r requirements.txt
```

## Usage

```bash
python calibrate_dispersion_ritc.py   # (re-)fit the dispersion model when the data change
python run_analysis.py                # run the full pipeline
```

`run_analysis.py` reads all `pdf_extraction/syndicate_*_*.json` files and writes:

- `exposure_results.json` — structured results for the dashboard
- `paper_pack/` — figures (PNG) and tables (LaTeX)
- `vignettes/` — worked-example bundles for two hypothetical syndicate vignettes
- `distortion_tool.html` — self-contained portfolio basis-transfer tool

Vignette VaR intervals and EVT cross-checks:

```bash
python vignette_uncertainty.py && python gpd_var_uncertainty.py && python bayesian_gpd.py
python appendix_c_tail_comparison.py
```

### Data provenance

The structured inputs are produced by a separate extraction project,
[lloyds-reserve-stress-testing](https://github.com/colinpriest/lloyds-reserve-stress-testing).
See [docs/data-provenance.md](docs/data-provenance.md) for what is imported and
[docs/appendix-data-audit.md](docs/appendix-data-audit.md) for the coverage audit
(~76% of active syndicate-years, 2014–2024).

All monetary amounts are **GBP millions**: USD-presented reports (26% of observations) are
converted at the reporting-date Fed H.10 spot rate, with per-report currency provenance from
the source PDFs — see [docs/fx-conversion.md](docs/fx-conversion.md), `currency_scan.py`
(→ `pdf_extraction/currency_scan.json`) and `fetch_h10_rates.py` (→ `fx_rates_h10.json`).

### Dashboard

Open `pdf_extraction/exposure_analysis.html` in a browser and load `exposure_results.json`.

### Portfolio basis-transfer tool

Open `distortion_tool.html` directly in a browser. All data (789 donors) and Chart.js are
embedded — no server, no additional files, no internet connection required. It shows KDE density
plots of raw vs target-basis PYD distributions, the adverse-tail survivor function, a statistics
table with raw-to-adjusted deltas, a Shapley waterfall of VaR99.5, and click-through worked
examples.
