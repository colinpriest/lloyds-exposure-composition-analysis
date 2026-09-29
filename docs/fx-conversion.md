# Currency Determination and FX Conversion to GBP

All monetary amounts in the analysis dataset are expressed in **GBP millions**.
Syndicate annual reports are presented in either GBP or USD; USD-presented reports
are converted to GBP at the **reporting-date spot rate**. This note documents (1) how
each report's currency was determined, with provenance; (2) where the exchange rates
come from and exactly which rates are used; and (3) how and where the conversion is
applied.

## 1 Report-currency determination (`currency_scan.py`)

The relevant concept is the **presentational currency** — the currency the published
amounts are stated in. It is *not* always the functional currency: e.g. syndicate
1861 (2014) has a USD functional currency but presents its accounts in sterling,
while syndicate 33 presented in sterling up to 2017 and in US dollars from 2018.

For every report, `src/currency_scan.py` opens the source PDF from the extraction
repository's `syndicate_reports/pdfs/` folder, supplied by `--pdf-dir` or the
`LLOYDS_SYNDICATE_PDF_DIR` environment variable and validated before any report
is read (a run with source PDFs missing stops before writing unless
`--allow-llm-fallback` is given, and then writes `currency_scan_llm_fallback.json`
unless `--replace-canonical` is also given; `--out` may name any other file but
not the canonical one under that fallback), and applies an
evidence hierarchy, recording **provenance** — the page number, the nearest section
heading, and a verbatim quote of the sentence (or the unit-header tally) that
establishes the currency — in `pdf_extraction/currency_scan.json`:

1. **`presentational_statement`** — an explicit accounting-policy statement, e.g.
   *"These annual accounts are presented in US Dollars, which is the Syndicate's
   functional currency"* (typically in *Notes to the accounts → Basis of
   preparation / Foreign currency*). Clause-aware parsing: currency tokens
   attached to a *functional*-currency clause are not read as presentational;
   parentheticals ("(previously GBP)") and statements about **future** currency
   changes ("will change to US Dollars in 2018") or the **prior** presentation
   ("previously reported in Sterling") are excluded, keyed to the reporting year.
2. **`unit_headers`** — dominance of monetary unit headers in the statements
   themselves ("US$'000" vs "£'000"; at least 3 hits and at least 3× dominance).
3. **`functional_statement`** — a functional-currency statement only (no
   presentational statement, no unit dominance). Flagged.
4. **`llm_field`** — the dual-LLM extraction's `currency` field ("Reporting
   currency of the financial statements"), used only where the scan cannot decide:
   the PDF has no usable text layer (scanned documents), its text matches none of
   the patterns above, or there is no PDF (the 95 filings of 2024 published only as
   HTML, which the scan does not read). Flagged.

Every classification is cross-checked against the LLM extraction field and the
unit-header tally.

**Outcome (1,065 reports):** 747 GBP, 284 USD, 34 undetermined. The 34 are no-model
files (no extraction model read them) that never enter the analysis dataset; none is in
the analysis corpus (below). **Zero** disagreements with the dual-LLM field when the scan ran.
Taken one model at a time, the fields differ from the scan for 12
corpus records: 10 left it blank, one wrote "US$", and in 780/2015 one model reads GBP
where the filing states "The Syndicate's functional and presentational currency is US
Dollars" (a change that year; the scan and the loader take USD). One flagged statement-vs-units conflict
(3622_2020: the policy note states sterling explicitly, twice; the unit tally is
blind there because the report's £ glyph does not survive text extraction —
classified GBP). **No currency other than GBP or USD was found** in a report the scan or
a model read. 1100/2024, published only as HTML and read by neither, states the euro in its
accounting policies; it has no model reading and never enters the analysis.

For the eight 2024 filings the round-62 re-extraction read (published only as HTML), the
scan takes the models' field: USD for 1988, 2689, 2880, 3456 and 5183, GBP for 1902, 2525
and 4747. Each filing's own statement agrees ("The financial statements are presented in
USD" or "in GBP", with the matching unit headers).

Within the 939-observation analysis corpus: **692 GBP, 247 USD (26%)**, none
undetermined. Provenance methods: 601 presentational statements, 71 unit-header, 15 functional-statement, 252 LLM-field
(151 scanned PDFs, 86 filings published only as HTML, 15 PDFs whose text matched no pattern) (the four counts sum to the corpus;
recomputed from `currency_scan.json` by `src/test_fx_doc.py`). The loader applies an
undetermined currency as GBP, with no conversion; `src/test_fx_doc.py` fails if an
undetermined corpus record is read otherwise by either extraction model.
The USD share rises from 7% of observations in 2014 to 44% in 2024.

## 2 Exchange rates (`fetch_h10_rates.py` → `fx_rates_h10.json`)

- **Source:** Federal Reserve statistical release **H.10, Foreign Exchange Rates**,
  historical data for the United Kingdom:
  <https://www.federalreserve.gov/releases/h10/hist/dat00_uk.htm>
- **Series:** business-day spot exchange rate, quoted as **US dollars per 1 pound
  sterling** (noon buying rates in New York for cable transfers, as certified by
  the Federal Reserve Bank of New York). The stored series runs from 2000-01-03 to a fixed
  bound of 2025-12-31 (`series_end` in the file; the release runs to the present, and an
  open-ended store changed with every fetch, round 53); 6,518 daily observations.
- **Rate selection:** Lloyd's syndicate annual accounts have a 31 December
  reporting date. For reporting year *Y* we use the **last published business-day
  rate on or before 31 December *Y*** ("reporting-date spot rate"). The full daily
  series and the retrieval timestamp are stored in `fx_rates_h10.json` for audit.

The rates used:

| Reporting year | Rate date used | USD per GBP |
|---|---|---|
| 2014 | 2014-12-31 | 1.5578 |
| 2015 | 2015-12-31 | 1.4746 |
| 2016 | 2016-12-30 | 1.2337 |
| 2017 | 2017-12-29 | 1.3529 |
| 2018 | 2018-12-31 | 1.2763 |
| 2019 | 2019-12-31 | 1.3269 |
| 2020 | 2020-12-31 | 1.3662 |
| 2021 | 2021-12-30 | 1.3500 |
| 2022 | 2022-12-30 | 1.2077 |
| 2023 | 2023-12-29 | 1.2743 |
| 2024 | 2024-12-31 | 1.2521 |

(Where 31 December falls on a weekend/holiday the preceding business day is used —
that is the H.10 print for the reporting date.)

## 3 Conversion (`run_analysis.py`)

Applied at load time, before any classification, filtering or computation, to the
canonical model record and the deterministic `_adobe_lob` block of each
USD-presented report:

```
amount_GBP_m = amount_USD_m / (USD per GBP at the reporting date)
```

Every numeric field with the `_gbp_m` suffix is converted (opening reserves, PYD,
gross premiums written, premium-mix amounts, LoB movement amounts). Ratios are
currency-invariant and are **not** touched: `pyd_pct`, LoB weights, HHI, and the
severity `S = PYD / opening_reserves` (numerator and denominator are in the same
report currency). The conversion therefore changes the **size** variables (reserves,
premiums) that enter the pooling law and eligibility thresholds, not the severities.

A single reporting-date rate is applied to all amounts in a report, including
opening reserves (which economically date from the prior year-end); this is the
documented design choice — using the opening-date rate for opening reserves would
leave the severity ratio inconsistent within a filing.

Each observation in `exposure_results.json` carries `report_currency`,
`fx_applied`, `fx_rate_usd_per_gbp`, and `fx_rate_date`; the bundle carries an
`fx_conversion` metadata block (policy, source, rates used, counts).

Non-GBP/USD currencies, if ever encountered, make `run_analysis.py` fail loudly —
they require explicit instructions rather than silent handling.

## 4 Reproduction order

```bash
python src/fetch_h10_rates.py    # refresh fx_rates_h10.json from the Fed H.10 page
python src/currency_scan.py --pdf-dir <extraction-repository>/syndicate_reports/pdfs \
    --allow-llm-fallback --replace-canonical
                                 # refresh currency_scan.json from the source PDFs (the
                                 # 2024 filings published only as HTML have none)
python src/run_analysis.py       # rebuild exposure_results.json (GBP, converted)
python src/calibrate_dispersion.py && python src/calibrate_dispersion_ritc.py
python src/run_analysis.py       # rebuild vignettes/tool on the new calibration
# ... downstream analysis scripts
```
