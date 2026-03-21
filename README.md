# IME Lloyd's Exposure Composition Analysis

Analyses the exposure composition and prior-year reserve development of Lloyd's syndicates, using data extracted from syndicate annual reports (PDFs → JSON).

## Overview

The project has two components:

- **`run_analysis.py`** — Python script that reads syndicate JSON extractions from `pdf_extraction/`, classifies data quality, computes line-of-business (LoB) weights, severity distributions, runs statistical analyses, and emits `exposure_results.json`.
- **`pdf_extraction/exposure_analysis.html`** — Static HTML dashboard that loads `exposure_results.json` and renders tables, charts, and drill-through detail. It performs no computation of its own.

## Lines of Business

The analysis covers 13 LoB categories: Property, Casualty, Marine, Energy, Motor, Aviation, Reinsurance (Property/Casualty/Specialty), Professional Lines, Accident & Health, Cyber, and Aggregate.

## Statistical Analyses

- **N0** — Descriptive statistics and data-quality classification
- **N1** — LoB weight distributions and concentration (HHI)
- **N2** — Severity distributions and tail analysis
- **N3** — Panel regression of prior-year development on LoB weights (RE-GLS with James-Stein shrinkage)
- **N4** — Bootstrap and leave-one-out robustness checks

## Project Structure

```
├── run_analysis.py            # Main analysis script
├── exposure_results.json      # Output results bundle (generated)
├── pdf_extraction/            # Input syndicate JSONs + HTML dashboard
│   ├── syndicate_*_*.json     # Extracted syndicate data (per syndicate per year)
│   └── exposure_analysis.html # Dashboard viewer
├── paper_pack/                # Generated figures and LaTeX tables
├── specifications/            # Analysis specification document
├── docs/                      # Design and methodology notes
└── requirements.txt           # Python dependencies
```

## Setup

Requires Python 3.9+.

```bash
pip install -r requirements.txt
```

## Usage

```bash
python run_analysis.py
```

This reads all `pdf_extraction/syndicate_*_*.json` files, runs the full analysis pipeline, and writes:

- `exposure_results.json` — structured results for the dashboard
- `paper_pack/` — figures (PNG) and tables (LaTeX) for the research paper

Then open `pdf_extraction/exposure_analysis.html` in a browser to explore the results interactively.
