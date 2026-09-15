# Lloyd's Exposure Composition & Reserve-Development Dispersion

![Project infographic](figures/project-infographic.png)

*The infographic is a hand-drawn summary of the round-49 sample (about 76% coverage,
790 records) and is kept as a historical illustration; the current sample and results
are in [docs/current-results.md](docs/current-results.md) and
[docs/appendix-data-audit.md](docs/appendix-data-audit.md).*

Analyses the exposure composition and prior-year reserve development (PYD) of Lloyd's
syndicates, using structured data extracted from syndicate annual reports (PDFs → JSON). The
core deliverable is a **robust Bayesian pooling dispersion model** and a **scenario-transfer
operator** that rescales historical reserve movements onto a user-specified target portfolio
(size, concentration and target tail regime: clean by default, RITC-affected, or a preserve-donor-regime diagnostic).

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
  enters a target LoB mix, reserve size and target tail regime --- clean (the default), RITC-affected, or a diagnostic that preserves each donor's own regime; the tool quantile-maps every donor from its own tail index onto the selected target's and applies the dispersion transfer
  operator to the donor pool and shows raw vs target-basis distributions, summary statistics, a
  three-player Shapley decomposition (tail regime, size, concentration --- all eight
  coalitions, summing exactly to target minus raw) and per-syndicate-year worked examples.
  All data and dependencies are embedded — open in any browser, no server required.
- **`pdf_extraction/exposure_analysis.html`** — static dashboard that loads
  `exposure_results.json` and renders tables/charts (no computation of its own).

## The model (summary)

For syndicate *i* in reporting year *t*, severity `S = PYD / opening_reserves`:

```
S_it ~ Student-t(nu_it, 0, sigma_it)
sigma_it = exp( s_t + beta_RITC * 1[RITC] )
           * sqrt( sigma_undiv^2 + sigma_div^2 * [ (R/R_ref)(1/H)^gamma ]^{2(k-1)} )
nu_it    = nu_clean                      (clean years)
         = nu_clean * exp(-lambda_RITC)  (RITC years: a separate regime; its ordering
                                           against the clean one is not imposed)
```

with `mu = 0` fixed, pooling exponent `k ∈ [0.5, 1]`, concentration via the effective line count
`n_eff = 1/H`, a positive undiversifiable floor `sigma_undiv`, a reporting-year shared shock
`s_t`, and a Student-t tail split into a **clean** and an **RITC** regime (external
reinsurance-to-close is a separate regime with its own tail index and a fitted log-scale
shift `beta_RITC`; its ordering against the clean regime is not imposed and is not
resolved (the headline fit below gives `P(nu_ritc < nu_clean)`); the transfer operator omits the
scale shift — a structural simplification worth about 0.9% of the vignette stresses,
not an established zero; see
[docs/current-results.md](docs/current-results.md)).

Headline fit (n=691 gross-basis syndicate-years, 11 reporting years, single-currency GBP
data — see [docs/fx-conversion.md](docs/fx-conversion.md)): `k ≈ 0.56`, `gamma ≈ 0.30`,
`sigma_undiv ≈ 0.031`, `nu_clean ≈ 4.34`, `nu_ritc ≈ 6.61`, `P(nu_ritc < nu_clean) = 0.31`.

## The transfer operator

The operator applies the fitted base scale law `sigma(R,H)` and the two fitted tail
indices; it omits the fitted RITC scale multiplier `exp(beta_RITC * 1[RITC])` (a measured
structural simplification worth about 0.9% of the vignette stresses) and carries the donor's realised year effect in the
observed severity rather than re-drawing it. It is **shape-aware**: a donor severity at
`(R_s, H_s)` transfers to a target `(R_t, H_t)` by

```
S_adj = sigma(R_t,H_t) * F_inv[ nu_t ]( F[ nu_s ]( S_src / sigma(R_s,H_s) ) )
```

where `F` is the Student-t CDF. When `nu_s = nu_t` this collapses to the pure rescale
`S_src · sigma(R_t,H_t)/sigma(R_s,H_s)`; when the donor is an RITC year and the target is clean,
it **de-RITCs** the donor — mapping its residual from the fitted RITC tail index to the clean
one, which thins the tail when the RITC index is the heavier and fattens it when it is the
lighter (the fit's ordering is not a constraint). This is an
upstream distributional adjustment, not a tail-fitting or capital-setting method: the
regime step applies the two fitted Student-t indices; it does not fit a tail to the
target or set capital.

## Statistical analyses

- **N0** — descriptive statistics and data-quality classification
- **N1** — LoB weight distributions and concentration (HHI)
- **N2** — severity distributions and tail analysis
- **N3** — panel regression of PYD on LoB weights (RE-GLS with James–Stein shrinkage)
- **N4** — bootstrap and leave-one-out robustness checks
- **Dispersion model** — the robust Bayesian pooling model above (size, concentration, floor,
  heavy tails, RITC tail regime), calibrated by `calibrate_dispersion_ritc.py`

## Project structure

All analysis scripts live in `src/` and are run from the repo root as
`python src/<script>.py`. Generated artifacts and reference inputs are organised into
subfolders:

```
├── src/                            # All analysis scripts (run as `python src/<name>.py`)
├── README.md                       # Start here
├── docs/current-results.md         # Current fitted values (GENERATED)
├── scaling_analysis_writeup.md     # ARCHIVE - historical development record
├── distortion_tool.html            # Portfolio basis-transfer tool (generated deliverable)
├── requirements.txt                # Direct dependency constraints
├── requirements.lock               # Clean Python 3.12.6 environment (transitives pinned)
│
├── model/                          # Shared pipeline artifacts (generated)
│     exposure_results.json           – results bundle emitted by run_analysis.py
│     dispersion_calibration*.json    – calibrated parameters (ritc / systemic / … )
│     dispersion_posterior_draws*.npz – posterior draws
│     fx_rates_h10.json               – Fed H.10 GBP/USD spot rates
├── results/                        # Per-analysis output JSONs (*_results.json, worklist)
├── figures/                        # Standalone-script figures + project infographic
├── assets/                         # HTML template + inlined Chart.js for the tool
├── data/                           # Reference inputs (market_active_syndicates, inception years)
│
├── pdf_extraction/                 # Input syndicate JSONs + ritc_scan/currency_scan + dashboard
├── vignettes/                      # Generated vignette bundles
├── paper_pack/                     # Generated paper figures and LaTeX tables
├── specifications/                 # Analysis and vignette specifications
└── docs/                           # Methodology notes, data provenance, referee checks
```

Each script anchors its paths to the repo root (`Path(__file__).resolve().parent.parent`),
so it reads/writes these subfolders automatically regardless of the working directory — no
configuration is needed for repository-relative inputs and outputs. The one script that
reads files outside this repository, `src/currency_scan.py`, takes the source-PDF folder
from `--pdf-dir` or `LLOYDS_SYNDICATE_PDF_DIR` (see [docs/fx-conversion.md](docs/fx-conversion.md)).

## Setup

The recorded and supported environment uses Python 3.12.6. Create a project-specific
environment and install the complete project lock, which pins all transitive
requirements:

```bash
python3.12 -m venv .venv
source .venv/bin/activate              # Windows: .venv\Scripts\activate
python -m pip install --upgrade pip
python -m pip install -r requirements.lock
```

## Reproducing the paper's results

```bash
python -m pip install -r requirements.lock
python reproduce.py --check     # environment and committed inputs, no fitting
python reproduce.py --list      # every script in the manifest, in order, with runtimes
python reproduce.py             # run everything (no C++ toolchain needed)
```

No C++ toolchain is needed, and the committed outputs were produced with none
present. That second clause matters for bit-for-bit reproduction: with a toolchain on
the path PyTensor compiles the operations it otherwise runs in Python, and on the
reference machine that changed every posterior draw from the first one (posterior
means moved by roughly a fiftieth of a posterior SD, so no conclusion moves).
`reproduce.py --check` reports a detected toolchain for that reason; remove it from
PATH to reproduce the committed outputs exactly.

Two parallelism switches exist and neither changes an output. `PYMC_CORES` (default
1) is the number of chains each fit samples in parallel; round 53 ran the manifest
sequentially in full and in parallel through step 33 of 60 (stopped there when the
temp-directory leak below was diagnosed), and the 38 outputs both runs completed
were identical (JSON after the volatile fields, binaries byte for byte) apart from
one run identifier that hashes the code state. The default stays sequential because a fit's time is
compilation, not sampling (a 1,500-draw chain of the adopted model samples in
seconds), and on Windows each parallel chain is a spawned process that repeats the
start-up cost, measured at about 50 s per fit, on every one of the manifest's many
short fits. A related pitfall: PyTensor's NUMBA backend writes about a thousand
temporary files per compiled fit into the system temp directory and does not remove
them, so a long-used `%TEMP%` becomes slow (round 53 found 1.5 million entries and
40 ms per file creation, which multiplied every fit's time by five); point `TEMP`
and `TMP` at an empty directory for a manifest run.
`PROXY_WORKERS` (default 12) is the number of processes across which
`proxy_stress_bayes.py` spreads its independent fits, every fit seeded the same way
whichever process runs it; that script is where the manifest's hours go (209 minutes sequentially), and
`PROXY_WORKERS=1` restores the sequential order.

`reproduce.py` first rebuilds the working sample from the extraction records
(`build_working_sample.py`, the loader pass every calibrator reads), then runs the
calibration, then the referee checks, then `run_analysis.py` again to embed the fitted
calibration in its outputs, and reports which succeeded. The order is the data
dependency order and `src/test_manifest_order.py` fails if any step reads an artefact
that only a later step produces (before round 52 the calibrations ran on the previous
sample whenever the records changed). Every fitting
script seeds itself. What reproduction means here is stated precisely, because the
verifier checks exactly this: every output DECLARED by a manifest step is compared with
the committed version -- `.npz`, figures and other binaries byte for byte; `.json`
as canonical JSON after excluding the three documented volatile fields
(`runtime_seconds`, `analysis_timestamp`, `retrieved_utc`); text outputs (`.tex`,
`.csv`, `.md`, `.html`, `.txt`) with line endings normalised. A recorded pass writes
`reproduce-run-report.json` (committed): the commit, command, environment, per-script
status and per-output SHA-256, so the claim is auditable from a clean clone rather
than resting on a local, gitignored stamp.

Use `python reproduce.py --verify` rather than `git status` to check a run. Without
either a local run stamp or a committed run report, an untouched checkout proves
nothing. This repository includes a committed full-manifest run report, so `--verify`
validates that report in a clean clone: it prints how many of the manifest's scripts
the recorded run covers (all of them for the committed report), and would mark a
smaller record PARTIAL and state that the outputs of the scripts it did not run are
not evidence of reproduction. It does not rerun anything. The fitted `.json` outputs
record `runtime_seconds`, `analysis_timestamp` and (the rates file) `retrieved_utc`,
which vary run to run, so `git status` flags them as modified when every fitted number
in them is identical; `--verify` excludes exactly those three fields, compares text
outputs with line endings normalised, and byte-compares everything else (including the `.npz` posterior draws, which
the old verifier's `.json` filter could not see), and fails on any changed output that
no ran script declared.

The whole manifest has been rerun as a recorded pass from a clean clone of the
committed analysis (every manifest script, no failures; the posterior-draw `.npz` files and the
figures reproduced byte for byte). `reproduce-run-report.json` (committed) records the commit, a
`worktree_dirty_src` flag, the environment, and per-output hashes -- canonical
SHA-256 for JSON (volatile fields excluded), byte SHA-256 for binaries -- and
`--verify` VALIDATES that report against history: a dirty recorded run is rejected,
and every recorded hash is checked against the blob at the recorded commit. In a
clean clone with no local run, that validation is the whole verdict; comparing an
untouched tree with its own `HEAD` proves nothing and is not done. `--verify` prints
the coverage -- `N of M manifest scripts recorded as run`, with M read from the
manifest itself -- and marks a smaller record `PASS (PARTIAL run)` rather than
implying more. A verdict without its coverage was the earlier defect: the
clean-clone path printed `PASS` alone while this file claimed it said partial.

The environment is machine-enforced: `requirements.lock` pins every package
(transitives included) at the versions of record. `--check` enforces Python 3.12.6
and parses every PEP 508 entry, including extras, direct URLs and VCS references; the
run report records the material versions.

This setup was validated on 31 August 2026 in a newly created Python 3.12.6 virtual
environment: installation from `requirements.lock`, `reproduce.py --check`, clean-clone
`--verify`, and the test suite all passed. The suite has grown since; its current
record, stamped here by `record_tests.py` from `tests-run-report.json`, is
(866 passed, 14 skipped), which is not the count of that 31 August run. A calibration smoke
run of `calibrate_dispersion.py` completed 6,000 posterior draws with zero divergences
and maximum R-hat 1.000. The full-manifest record described above was made on
15 September 2026 on a source tree with no uncommitted change; the distinction between re-runnable and
demonstrated above remains deliberate.

One test crosses into the manuscript: `test_vignette_estimator.py` reads Section 5.2's
scale-ratio range out of `paper/main.tex` and checks it against
`check_vignette2_sign_results.json`, so that the range is the record's rather than a
number retyped at each refit. It looks for the paper in the main project folder, which is
where the current paper lives. Set `LLOYDS_PAPER_REPO` to a different checkout to point
it there -- while a revision round is in progress the paper in play is the branch's copy,
and the test failing against the main folder is the true statement that the main folder is
behind, not a fault in the test. Without a manuscript at either location the test skips,
and says in its skip reason what to set.

That test count is not typed. `python src/record_tests.py` runs the suite, writes
`tests-run-report.json` (counts, collected total, commit, dirty flag, environment)
and stamps the number above from what it observed; `--check` then fails if any stated
count disagrees with the record, or if the suite has changed size since the record was
written -- a record nothing revalidates goes stale exactly the way the prose it
replaced did. The previous count was typed by hand and was wrong by one test on the
day it was written.

It does **not** re-run the PDF extraction, which needs the source reports and paid LLM
API access; its output is committed as `model/exposure_results.json`. Everything
downstream of that file is *re-runnable* from this checkout through the manifest;
what has been *demonstrated* is the recorded clean full-manifest run described above
(`--verify` prints its exact coverage).

Individual steps still work on their own:

```bash
python src/calibrate_dispersion_ritc.py   # (re-)fit the dispersion model when the data change
python src/run_analysis.py                # the analysis pipeline and paper-pack outputs
```

`run_analysis.py` reads all `pdf_extraction/syndicate_*_*.json` files and writes:

- `model/exposure_results.json` — structured results for the dashboard
- `paper_pack/` — figures (PNG) and tables (LaTeX)
- `vignettes/` — worked-example bundles for two hypothetical syndicate vignettes
- `distortion_tool.html` — self-contained portfolio basis-transfer tool

Vignette VaR intervals and EVT cross-checks:

```bash
python src/vignette_uncertainty.py && python src/gpd_var_uncertainty.py && python src/bayesian_gpd.py
python src/appendix_c_tail_comparison.py
```

### Data provenance

The structured inputs are produced by a separate extraction project,
[lloyds-reserve-stress-testing](https://github.com/colinpriest/lloyds-reserve-stress-testing).
See [docs/data-provenance.md](docs/data-provenance.md) for what is imported and
[docs/appendix-data-audit.md](docs/appendix-data-audit.md) for the coverage audit
(the working sample's share of active syndicate-years is stamped in the audit; about
67% at the round-53 sample, 2014–2024).

All monetary amounts are **GBP millions**: USD-presented reports (26% of observations) are
converted at the reporting-date Fed H.10 spot rate, with per-report currency provenance from
the source PDFs — see [docs/fx-conversion.md](docs/fx-conversion.md), `currency_scan.py`
(→ `pdf_extraction/currency_scan.json`) and `fetch_h10_rates.py` (→ `fx_rates_h10.json`).

### Dashboard

Open `pdf_extraction/exposure_analysis.html` in a browser and load `exposure_results.json`.

### Portfolio basis-transfer tool

Open `distortion_tool.html` directly in a browser. All data (691 donors) and Chart.js are
embedded — no server, no additional files, no internet connection required. It shows KDE density
plots of raw vs target-basis PYD distributions, the adverse-tail survivor function, a statistics
table with raw-to-adjusted deltas, a three-player Shapley waterfall of VaR99.5 (tail-regime,
reserve-size and concentration effects, summing exactly to target minus raw), and
click-through worked examples.
