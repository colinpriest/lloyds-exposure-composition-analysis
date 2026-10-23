# Rebased development tables in the primary sample (read-only screen)

Script: `rebase_screen.py` (screen) and `rebase_report.py` (this report); output `rebase_screen.json`. Offline, no API.

## Population

- Primary sample: **649** records (`s_raw_a` present, R, HHI present, gross: `check_cohort_scope.in_working_sample` on `model/exposure_results.json`).
- No year t grid: 1 (3334_2018). No year t-1 record file: 8 (218_2015, 1955_2018, 2008_2023, 3330_2017, 3500_2018, 3500_2021, 3623_2024, 4711_2017).
- Year t-1 record present but **no gross grid** to compare: **92** (of which 58 are 2015 reports, whose 2014 report holds no stored triangle).
    - 50: t-1 triangle block has no development rows (type none)
    - 36: t-1 record holds no triangle block
    - 3: t-1 triangle is net only
    - 3: t-1 triangle is a loss-ratio percentage table
- Gross grids in both years: **548**. Of these **535** share at least one single (non-aggregated, on the latest diagonal) underwriting year and were compared (RAG against RAG for 513; 22 compare against the year t-1 claims triangle); 12 share none (misshapen or offset grids: 1183_2016, 2012_2016, 2012_2017, 2088_2016, 2088_2019, 5000_2017, 510_2020, 5151_2019, 6111_2016, 6112_2016, 727_2020, 780_2018); 1 has a units label that cannot be converted.

Verdicts over the 649 records:

| verdict | records |
|---|---|
| clean | 423 |
| no_gross_grid_prev | 92 |
| rebase | 41 |
| units_case | 40 |
| rebase_oldest_column_only | 13 |
| no_common_single_year | 12 |
| no_prev_record | 8 |
| rebase_year_t1_only | 7 |
| alignment_uncertain | 6 |
| no_identity_evidence | 4 |
| cell_scale_slip | 2 |
| no_gross_grid_year_t | 1 |

## Method

- Grid: the adopted one (the register's `triangle.model` for a register record, else the canonical model's `_rag_triangle`; the `_claims_triangle` only where no RAG grid is stored). The year t-1 grid is the year t-1 report's stored gross RAG grid (claims triangle as a fallback, which then needs two years agreeing before the table is accepted as the same table).
- Years: every integer-labelled underwriting year in both grids except a column an `aggregated_cohort` anchor marks (either grid) and years the grid shapes do not align. The year t cell at the end of year t-1 is the year t table's second-last cell of the column, set against the year t-1 table's last cell (each grid's latest cell is its own report year's); the shift is moved by one or two cells when the grids' latest diagonals trail their report years by different amounts (lag read from the first row label), and a record whose lag cannot be reconciled is `alignment_uncertain`.
- Factor: the brief asks for the median ratio. A median over 3 to 4 years can sit on a restated year (2689_2023: ratios 1.506, 1.262, 1.003, median 1.262, which would flag the unchanged 2022 cell). The screen therefore takes, as the factor, the ratio shared by the most years (within 2%), an unchanged year (within 1% of 1) winning a tie, and falls back to the median where no ratio is shared. `factor_median` and `flagged_years_under_median_factor` are kept for every flagged record so that the brief's median rule can be compared.
- Flag: a year's cell departs from `factor x` (year t-1 cell) by more than 5% **and** by more than max(1% of R, 1m) in the year t table's terms. R is the loader's opening reserves in the grid's currency (USD at the year-end H.10 rate for USD grids).
- Tiers: `rebase` = flagged in underwriting years u <= t-2 with the oldest column of either grid left out (it may be an unmarked aggregated column); `rebase_oldest_column_only` = flagged only through that oldest column; `rebase_year_t1_only` = flagged only through underwriting year t-1 (outside M's years). Sizes use every flagged single year (oldest column included); `core_gross_over_R` leaves the oldest column out.
- Size against R: sum of |year t cell - factor x year t-1 cell| over the flagged years, over R. Effect on M: the table's M (sum over u <= t-2 of latest less previous estimate, read within the year t table) differs from the movement against what the t-1 report printed by minus the sum of those differences over the years u <= t-2; shown in millions and against |M|.
- Cell slips of about 1000 (a misread unit in one cell, 2121_2019 and 2001_2018) are set apart as `cell_scale_slip`, not rebases.

## Flagged records (61), ordered by size against R

`conf` is `high` unless a note under the table applies. Years are underwriting years; `diff` is the flagged cell less factor x the t-1 cell (m, grid currency).

| key | kind | conf | gross/R | core/R | M effect m (/|M|) | factor (median) | flagged years: cell t vs cell t-1 [ratio; diff m] | pg t / t-1 | V1 rank |
|---|---|---|---|---|---|---|---|---|---|
| 2121_2018 | year_t1_only | check | 3.348 | 3.347 | 1.9 (0.07) | 1.054 (1.053) | 2017: 1,218,481 vs 115,473 [10.552; 1096.8] | 55 / 58 | - |
| 1686_2021 | core | high | 1.496 | 1.496 | -3106.9 (29.44) | 1.000 (1.000) | 2016: 1,125,373 vs 256,846 [4.381; 868.5]; 2017: 1,382,452 vs 381,938 [3.620; 1000.5]; 2018: 1,594,488 vs 356,605 [4.471; 1237.9] | 32 / 33 | - |
| 3500_2023 | core | check | 1.400 | 1.386 | -3945.7 (105.48) | 2.049 (2.099) | 2017: 6,136,837 vs 2,181,257 [2.813; 1668.2]; 2018: 5,915,022 vs 1,728,542 [3.422; 2373.8]; 2019: 1,627,934 vs 447,479 [3.638; 711.2]; 2021: 946,566 vs 922,611 [1.026; -943.5]; 2022: 65,516 vs 363,424 [0.180; -679.0] | 24 / 24 | - |
| 6107_2023 | core | check | 1.219 | 1.219 | -126.2 (10.88) | 0.424 (0.634) | 2014: 7.2 vs 29.1 [0.247; -5.1]; 2017: 70.7 vs 127.5 [0.554; 16.6]; 2018: 64 vs 100.9 [0.634; 21.2]; 2019: 35.8 vs 52.7 [0.679; 13.5]; 2020: 62.6 vs 74 [0.846; 31.2]; 2021: 77.3 vs 67.1 [1.152; 48.9]; 2022: 60.4 vs 65.7 [0.919; 32.5] | 30 / 14 | - |
| 4747_2024 | core | high | 0.887 | 0.842 | -6.8 (0.61) | 1.000 (1.208) | 2022: 24,572 vs 17,343 [1.417; 7.2]; 2023: 34,726 vs 7,482 [4.641; 27.2] | None / 39 | - |
| 4444_2022 | core | check | 0.818 | 0.788 | 1633.3 (46.80) | 1.388 (1.108) | 2013: 568,628 vs 453,051 [1.255; -60.2]; 2015: 861,281 vs 685,502 [1.256; -90.1]; 2017: 899,889 vs 996,073 [0.903; -482.6]; 2018: 683,114 vs 836,008 [0.817; -477.2]; 2019: 587,818 vs 626,135 [0.939; -281.2]; 2020: 515,216 vs 536,074 [0.961; -228.8] | 15 / 14 | - |
| 1880_2015 | core | check | 0.585 | 0.442 | -64.4 (7.53) | 1.002 (1.002) | 2011: 478.8 vs 452.6 [1.058; 25.4]; 2012: 180.3 vs 135.9 [1.327; 44.2]; 2013: 86.9 vs 91.9 [0.946; -5.2]; 2014: 51.7 vs 92.1 [0.561; -40.6] | 31 / 26 | - |
| 2791_2022 | core | check | 0.579 | 0.579 | -97.3 (5.56) | 0.832 (1.021) | 2013: 91,571 vs 73,872 [1.240; 30.1]; 2014: 81,280 vs 68,845 [1.181; 24.0]; 2017: 132,755 vs 124,196 [1.069; 29.4]; 2018: 138,373 vs 109,681 [1.262; 47.1]; 2019: 121,853 vs 232,635 [0.524; -71.8]; 2020: 260,206 vs 267,228 [0.974; 37.8] | 82 / 38 | - |
| 2689_2023 | core | high | 0.560 | 0.183 | -61.0 (1.44) | 1.003 (1.262) | 2020: 123,040 vs 81,688 [1.506; 41.1]; 2021: 97,435 vs 77,230 [1.262; 19.9] | 46 / 46 | 12 |
| 3000_2016 | core | check | 0.511 | 0.387 | -16.7 (0.61) | 1.947 (1.947) | 2011: 584,362 vs 226,131 [2.584; 144.2]; 2012: 445,510 vs 193,364 [2.304; 69.1]; 2014: 230,985 vs 219,634 [1.052; -196.6]; 2015: 103,960 vs 102,097 [1.018; -94.8] | 38 / 36 | - |
| 6118_2018 | oldest_column_only | high | 0.454 | 0.000 | 82.9 (10.94) | 1.033 (1.035) | 2014: 21,267 vs 101,239 [0.210; -83.3] | 39 / 36 | - |
| 780_2017 | core | check | 0.431 | 0.266 | 60.3 (37.72) | 1.272 (1.272) | 2011: 242.2 vs 236.9 [1.022; -59.2]; 2012: 120.9 vs 109 [1.109; -17.8]; 2015: 160.1 vs 113.2 [1.414; 16.1]; 2016: 79.4 vs 29.2 [2.719; 42.2] | 31 / 30 | - |
| 510_2015 | core | high | 0.358 | 0.357 | -44.5 (444.52) | 1.214 (1.204) | 2012: 663.8 vs 502.3 [1.321; 54.1]; 2014: 295.8 vs 517.5 [0.572; -332.3] | 52 / 44 | - |
| 1301_2016 | year_t1_only | high | 0.355 | 0.355 | 2.3 (1.43) | 1.116 (1.109) | 2015: 66.1 vs 102.7 [0.644; -48.5] | None / 40 | - |
| 1967_2022 | core | high | 0.348 | 0.352 | -184.0 (4.05) | 0.972 (0.967) | 2020: 406,166 vs 216,548 [1.876; 195.7] | 36 / 36 | - |
| 3500_2022 | core | check | 0.335 | 0.319 | -986.6 (3.38) | 1.125 (1.125) | 2013: 1,169,214 vs 1,094,861 [1.068; -62.4]; 2017: 2,224,525 vs 1,759,449 [1.264; 245.4]; 2018: 1,761,919 vs 833,123 [2.115; 824.8]; 2021: 1,020,668 vs 1,078,053 [0.947; -192.0] | 24 / 25 | - |
| 1274_2024 | core | check | 0.285 | 0.258 | -211.6 (3.96) | 1.127 (1.126) | 2015: 238,380 vs 238,709 [0.999; -30.7]; 2016: 512,563 vs 303,880 [1.687; 170.1]; 2017: 508,881 vs 398,852 [1.276; 59.4]; 2019: 375,997 vs 304,070 [1.236; 33.3]; 2020: 243,561 vs 230,055 [1.059; -15.7]; 2023: 125,325 vs 125,351 [1.000; -16.0] | 47 / 36 | - |
| 1274_2022 | core | check | 0.276 | 0.260 | 193.7 (21.62) | 0.860 (0.860) | 2013: 176,592 vs 185,893 [0.950; 16.8]; 2014: 216,152 vs 238,459 [0.906; 11.1]; 2015: 231,577 vs 238,967 [0.969; 26.1]; 2016: 290,336 vs 534,138 [0.544; -168.9]; 2017: 375,782 vs 492,802 [0.762; -47.9]; 2019: 300,772 vs 379,722 [0.792; -25.7] | 37 / 36 | - |
| 1947_2020 | oldest_column_only | check | 0.270 | 0.000 | -5.0 (1.44) | 1.190 (1.190) | 2018: 28,901 vs 20,046 [1.442; 5.0]; 2019: 24,715 vs 26,330 [0.939; -6.6] | 30 / None | - |
| 4020_2018 | core | high | 0.241 | 0.241 | -105.7 (2.41) | 0.896 (0.980) | 2011: 191,003 vs 182,435 [1.047; 27.5]; 2013: 220,123 vs 184,146 [1.195; 55.1]; 2015: 195,916 vs 199,945 [0.980; 16.7]; 2017: 136,949 vs 129,594 [1.057; 20.8] | 39 / 41 | - |
| 2001_2016 | core | high | 0.230 | 0.230 | -127.8 (1.45) | 0.968 (1.016) | 2012: 805.5 vs 750.3 [1.074; 79.0]; 2015: 681.1 vs 404.2 [1.685; 289.7] | 35 / 31 | - |
| 1856_2021 | core | check | 0.227 | 0.233 | 9.0 (0.56) | 1.003 (0.976) | 2019: 82,463 vs 88,776 [0.929; -6.6]; 2020: 74,946 vs 100,281 [0.747; -25.7] | 40 / 40 | - |
| 1609_2024 | core | check | 0.219 | 0.144 | -22.1 (119.51) | 0.989 (0.989) | 2021: 66,053 vs 44,451 [1.486; 22.1]; 2023: 43,731 vs 66,700 [0.656; -22.2] | 51 / 41 | - |
| 2488_2019 | core | high | 0.218 | 0.197 | 162.8 (55.03) | 1.288 (1.227) | 2011: 377,123 vs 274,825 [1.372; 23.1]; 2013: 261,822 vs 219,423 [1.193; -20.8]; 2016: 329,541 vs 296,244 [1.112; -52.0]; 2017: 301,503 vs 317,778 [0.949; -107.8]; 2018: 101,458 vs 106,872 [0.949; -36.2] | 49 / 51 | - |
| 2007_2016 | core | check | 0.218 | 0.218 | -118.3 (2.16) | 0.791 (0.791) | 2011: 421.7 vs 383.5 [1.100; 118.3]; 2015: 209.8 vs 434.7 [0.483; -134.1] | 35 / 37 | - |
| 4444_2018 | core | check | 0.207 | 0.135 | -53.8 (0.61) | 1.278 (1.287) | 2011: 586,573 vs 355,885 [1.648; 131.7]; 2012: 569,744 vs 383,618 [1.485; 79.5]; 2016: 723,929 vs 696,895 [1.039; -166.7] | 24 / 25 | - |
| 4141_2022 | core | high | 0.199 | 0.199 | -0.0 (0.00) | 1.119 (1.119) | 2018: 110,645 vs 120,983 [0.914; -24.7]; 2019: 183,970 vs 142,425 [1.292; 24.7] | 31 / 30 | - |
| 1897_2019 | core | high | 0.195 | 0.194 | 33.0 (2.76) | 0.964 (0.963) | 2016: 69,041 vs 105,882 [0.652; -33.0] | 38 / 37 | - |
| 4472_2022 | core | check | 0.173 | 0.173 | -157.0 (1.28) | 0.728 (0.741) | 2013: 654.4 vs 700.8 [0.934; 144.0]; 2014: 741.8 vs 840.4 [0.883; 129.7]; 2015: 668.5 vs 853 [0.784; 47.2]; 2016: 677.6 vs 992 [0.683; -44.9]; 2017: 874.7 vs 1,376.6 [0.635; -128.0]; 2021: 419.6 vs 472.5 [0.888; 75.5] | 53 / 51 | - |
| 1729_2023 | core | check | 0.171 | 0.171 | -60.7 (3.62) | 1.201 (1.204) | 2021: 180,947 vs 101,902 [1.776; 58.5] | 44 / 45 | - |
| 2001_2017 | core | check | 0.153 | 0.152 | 53.4 (0.35) | 0.996 (0.996) | 2013: 900.3 vs 804.4 [1.119; 99.2]; 2014: 946 vs 862.3 [1.097; 87.3]; 2015: 918.4 vs 1,164 [0.789; -240.8] | 33 / 35 | - |
| 2015_2022 | year_t1_only | check | 0.151 | 0.154 | 1.0 (0.28) | 1.090 (1.090) | 2021: 92,384 vs 59,188 [1.561; 27.9] | 43 / 43 | - |
| 4000_2022 | oldest_column_only | high | 0.143 | 0.000 | -79.3 (2.69) | 1.095 (1.097) | 2019: 296,211 vs 198,065 [1.496; 79.3] | 32 / 31 | - |
| 1176_2019 | oldest_column_only | check | 0.137 | 0.062 | -2.3 (0.28) | 0.941 (0.943) | 2011: 17,001 vs 14,924 [1.139; 3.0]; 2018: 8,722 vs 6,647 [1.312; 2.5] | 29 / 29 | - |
| 1967_2018 | oldest_column_only | high | 0.118 | 0.000 | -26.1 (0.84) | 0.934 (0.934) | 2011: 110,704 vs 87,553 [1.264; 28.9] | 48 / 46 | - |
| 1945_2018 | core | high | 0.111 | 0.107 | 15.1 (1.87) | 1.041 (1.031) | 2013: 34,327 vs 45,440 [0.755; -13.0] | 40 / 39 | - |
| 3624_2018 | year_t1_only | check | 0.108 | 0.109 | -15.6 (0.68) | 1.322 (1.331) | 2017: 102,410 vs 140,574 [0.729; -83.4] | 33 / 34 | - |
| 4242_2022 | core | check | 0.079 | 0.079 | 35.6 (0.80) | 1.000 (0.998) | 2020: 277,405 vs 310,094 [0.895; -32.7] | 44 / 46 | - |
| 2468_2019 | oldest_column_only | check | 0.072 | 0.000 | -10.4 (0.23) | 1.046 (1.046) | 2016: 108,562 vs 93,806 [1.157; 10.4]; 2018: 164,248 vs 170,258 [0.965; -13.9] | 43 / 41 | - |
| 1274_2016 | core | high | 0.071 | 0.068 | 36.9 (0.64) | 0.980 (0.978) | 2012: 141,355 vs 178,987 [0.790; -34.0] | 41 / 41 | - |
| 382_2022 | core | high | 0.069 | 0.069 | 40.6 (1.19) | 1.092 (1.088) | 2018: 246,344 vs 256,954 [0.959; -34.2] | 45 / 46 | - |
| 1967_2017 | core | high | 0.068 | 0.070 | 3.6 (0.32) | 1.149 (1.150) | 2015: 107,045 vs 98,158 [1.091; -5.7]; 2016: 66,510 vs 62,721 [1.060; -5.5] | 46 / 48 | - |
| 1686_2022 | core | high | 0.064 | 0.064 | 175.0 (8.18) | 1.000 (1.000) | 2018: 1,474,049 vs 1,612,609 [0.914; -138.6] | 31 / 32 | - |
| 1910_2016 | year_t1_only | high | 0.056 | 0.047 | 3.1 (0.37) | 1.167 (1.145) | 2015: 43,330 vs 41,733 [1.038; -5.4] | 39 / 37 | - |
| 2232_2020 | core | high | 0.053 | 0.041 | 7.8 (0.14) | 0.967 (0.967) | 2013: 60,045 vs 57,184 [1.050; 4.8]; 2018: 149,992 vs 165,562 [0.906; -10.0]; 2019: 70,998 vs 79,802 [0.890; -6.1] | 49 / 47 | - |
| 382_2023 | core | high | 0.052 | 0.018 | -38.2 (4.84) | 0.977 (0.992) | 2016: 219,990 vs 214,054 [1.028; 10.9]; 2019: 175,595 vs 170,766 [1.028; 8.8]; 2020: 150,063 vs 140,149 [1.071; 13.1] | 45 / 45 | - |
| 4242_2017 | oldest_column_only | high | 0.043 | 0.000 | 1.0 (1.27) | 0.995 (1.000) | 2011: 11,539 vs 12,925 [0.893; -1.3] | 46 / 51 | - |
| 1218_2016 | core | high | 0.043 | 0.030 | -7.1 (0.79) | 1.552 (1.552) | 2011: 74,245 vs 51,509 [1.441; -5.7]; 2013: 99,675 vs 55,453 [1.798; 13.6] | 37 / 35 | - |
| 2468_2020 | oldest_column_only | high | 0.042 | 0.000 | 16.4 (0.23) | 0.982 (0.982) | 2016: 97,252 vs 115,879 [0.839; -16.5] | 45 / 43 | - |
| 1947_2022 | oldest_column_only | high | 0.037 | 0.000 | -5.2 (0.36) | 1.105 (1.113) | 2018: 30,563 vs 23,731 [1.288; 4.3] | 29 / 30 | - |
| 2488_2016 | oldest_column_only | check | 0.036 | 0.000 | -41.1 (1.54) | 1.149 (1.167) | 2011: 285,823 vs 220,173 [1.298; 32.7] | 51 / 42 | - |
| 1945_2016 | core | high | 0.034 | 0.031 | 3.5 (0.33) | 1.171 (1.155) | 2012: 26,379 vs 23,953 [1.101; -1.7] | 38 / 38 | - |
| 3000_2018 | core | check | 0.028 | 0.028 | -28.4 (1.59) | 1.015 (1.015) | 2013: 325,043 vs 285,280 [1.139; 35.5] | 40 / 39 | - |
| 1910_2018 | core | check | 0.021 | 0.021 | 7.6 (3.98) | 1.043 (1.042) | 2016: 73 vs 76.5 [0.954; -6.8] | 36 / 35 | - |
| 4444_2017 | core | check | 0.021 | 0.021 | 41.6 (0.35) | 1.047 (1.039) | 2015: 467,615 vs 471,111 [0.993; -25.5] | 25 / 24 | - |
| 2232_2017 | year_t1_only | high | 0.021 | 0.021 | -0.0 (0.00) | 1.000 (1.000) | 2016: 64,631 vs 69,352 [0.932; -4.7] | 40 / 40 | - |
| 3000_2022 | core | check | 0.016 | 0.016 | 30.5 (0.27) | 1.079 (1.070) | 2020: 324,795 vs 318,487 [1.020; -18.8] | 44 / 43 | - |
| 6134_2022 | oldest_column_only | high | 0.016 | 0.000 | 3.0 (0.26) | 1.087 (1.087) | 2019: 41,615 vs 41,013 [1.015; -3.0] | 45 / 44 | - |
| 1084_2016 | year_t1_only | check | 0.013 | 0.013 | -40.5 (11.92) | 1.031 (1.051) | 2015: 290.5 vs 261.3 [1.112; 21.1] | 33 / 35 | - |
| 2232_2019 | oldest_column_only | high | 0.012 | 0.000 | -9.5 (0.74) | 0.986 (0.996) | 2013: 62,099 vs 58,400 [1.063; 4.5] | 47 / 43 | - |
| 5000_2023 | oldest_column_only | check | 0.012 | 0.000 | -10.2 (0.55) | 0.957 (0.957) | 2014: 191.4 vs 189.8 [1.008; 9.7] | 28 / 36 | - |

Notes on the `check` flags (what to look at before relying on a flag):

- 2121_2018: another model/field pair of grids gives ['alignment_uncertain', 'clean']
- 3500_2023: grid currencies differ (EUR against USD)
- 6107_2023: year t-1 grid is the claims triangle (not the RAG triangle); another model/field pair of grids gives ['alignment_uncertain']
- 4444_2022: year t-1 grid is the claims triangle (not the RAG triangle); year t grid is the claims triangle; flagged under the latest-cell alignment and the lag-implied one; 1 single years skipped as misshapen
- 1880_2015: no unchanged year or shared ratio: the whole table differs, so it may be another table
- 2791_2022: year t-1 grid is the claims triangle (not the RAG triangle); another model/field pair of grids gives ['alignment_uncertain', 'clean']; flagged under the latest-cell alignment and the lag-implied one
- 3000_2016: no unchanged year or shared ratio: the whole table differs, so it may be another table
- 780_2017: no unchanged year or shared ratio: the whole table differs, so it may be another table
- 3500_2022: another model/field pair of grids gives ['no_common_single_year']
- 1274_2024: another model/field pair of grids gives ['alignment_uncertain', 'clean']
- 1274_2022: another model/field pair of grids gives ['alignment_uncertain', 'clean']
- 1947_2020: no unchanged year or shared ratio: the whole table differs, so it may be another table
- 1856_2021: another model/field pair of grids gives ['alignment_uncertain']
- 1609_2024: no unchanged year or shared ratio: the whole table differs, so it may be another table
- 2007_2016: no unchanged year or shared ratio: the whole table differs, so it may be another table; 3 single years skipped as misshapen
- 4444_2018: another model/field pair of grids gives ['alignment_uncertain', 'no_common_single_year']; flagged under the latest-cell alignment and the lag-implied one
- 4472_2022: another model/field pair of grids gives ['alignment_uncertain']
- 1729_2023: grid currencies differ (USD against GBP)
- 2001_2017: grid currencies differ (USD against GBP)
- 2015_2022: another model/field pair of grids gives ['alignment_uncertain']
- 1176_2019: another model/field pair of grids gives ['alignment_uncertain']
- 3624_2018: grid currencies differ (USD against GBP)
- 4242_2022: another model/field pair of grids gives ['alignment_uncertain']
- 2468_2019: no unchanged year or shared ratio: the whole table differs, so it may be another table
- 2488_2016: another model/field pair of grids gives ['no_common_single_year']
- 3000_2018: another model/field pair of grids gives ['alignment_uncertain']
- 1910_2018: another model/field pair of grids gives ['alignment_uncertain', 'no_common_single_year']; grid currencies differ (GBP against USD)
- 4444_2017: another model/field pair of grids gives ['alignment_uncertain', 'no_common_single_year']
- 3000_2022: another model/field pair of grids gives ['alignment_uncertain']
- 1084_2016: another model/field pair of grids gives ['alignment_uncertain']
- 5000_2023: grid currencies differ (USD against GBP)

## Units cases (40): the two grids state different units

Reported apart; not rebases. Sub-type is read from the ratios of the single years common to both grids: converted by the stated units (`conv`), and as raw numbers (`raw`).

| key | t units / t-1 units | sub-type | conv ratios | raw ratios | verdict as labelled / as raw | pg t / t-1 | V1 rank |
|---|---|---|---|---|---|---|---|
| 218_2019 | millions / thousands | genuine change of units | [1.0, 1.0, 1.0] | [0.001, 0.001, 0.001] | clean / clean | 36 / 32 | - |
| 386_2024 | thousands / millions | genuine change of units | [0.984, 0.985, 0.99, 0.992, 0.99] | [983.607, 984.73, 989.74, 992.328, 990.329] | clean / clean | 53 / 45 | - |
| 510_2024 | thousands / millions | genuine change of units | [1.001, 1.001, 1.004, 1.004, 1.004] | [1000.912, 1000.534, 1004.422, 1003.776, 1004.063] | clean / clean | 73 / 36 | - |
| 623_2024 | thousands / millions | genuine change of units | [0.999, 0.998, 1.0, 1.0, 1.0] | [999.176, 997.825, 999.564, 1000.458, 1000.278] | clean / clean | 51 / 47 | - |
| 1084_2024 | thousands / millions | genuine change of units | [0.992, 0.985, 0.988, 1.019, 0.985] | [992.326, 985.259, 987.673, 1018.62, 985.033] | clean / clean | 47 / 37 | - |
| 1183_2024 | thousands / millions | genuine change of units | [0.996, 0.995, 0.997, 0.996, 0.996] | [996.383, 994.782, 996.513, 995.949, 995.638] | clean / clean | 54 / 45 | 10 |
| 1200_2024 | thousands / millions | genuine change of units | [0.982, 0.981, 0.969] | [981.621, 981.281, 969.477] | clean / clean | 42 / 43 | - |
| 1225_2024 | thousands / millions | genuine change of units | [1.002, 1.005, 1.007, 1.005, 1.006] | [1002.237, 1005.051, 1006.554, 1005.013, 1006.003] | clean / clean | 34 / 32 | - |
| 1301_2024 | thousands / millions | genuine change of units | [0.992, 0.992, 0.993] | [991.55, 992.102, 993.138] | clean / clean | 70 / 70 | - |
| 1856_2023 | millions / thousands | genuine change of units | [0.954, 0.948, 0.931, 0.931, 0.954] | [0.001, 0.001, 0.001, 0.001, 0.001] | clean / clean | 33 / 38 | - |
| 1880_2024 | thousands / millions | genuine change of units | [1.003, 1.009, 1.009, 1.011, 1.011] | [1003.18, 1008.726, 1009.297, 1010.888, 1011.186] | clean / clean | 69 / 33 | - |
| 1884_2024 | thousands / millions | genuine change of units | [1.004, 1.003, 1.005, 1.002, 1.018] | [1003.873, 1003.239, 1005.106, 1001.915, 1017.754] | clean / clean | 44 / 33 | - |
| 1910_2024 | thousands / millions | genuine change of units | [1.005, 1.011, 1.01] | [1005.118, 1011.243, 1010.42] | clean / clean | 39 / 36 | - |
| 2001_2024 | thousands / millions | genuine change of units | [1.002, 1.005, 1.005, 1.004, 0.999] | [1002.06, 1005.296, 1004.671, 1004.46, 998.83] | clean / clean | 61 / 57 | 15 |
| 2003_2017 | millions / thousands | genuine change of units | [1.024, 1.029, 1.025, 1.023, 1.024] | [0.001, 0.001, 0.001, 0.001, 0.001] | clean / clean | 44 / 43 | - |
| 2007_2018 | thousands / millions | genuine change of units | [1.045, 1.055] | [1045.113, 1055.386] | clean / clean | 29 / 33 | - |
| 2019_2024 | thousands / millions | genuine change of units | [1.0, 1.0, 1.0, 1.0] | [1000.047, 1000.015, 999.94, 1000.092] | clean / clean | None / 37 | - |
| 2623_2024 | thousands / millions | genuine change of units | [0.999, 0.998, 1.0, 1.0, 1.0] | [999.316, 997.657, 999.735, 1000.406, 1000.402] | clean / clean | 49 / None | - |
| 2987_2024 | thousands / millions | genuine change of units | [0.989, 0.992, 0.994, 0.992, 0.992] | [989.472, 991.721, 993.503, 992.31, 991.807] | clean / clean | 54 / 47 | - |
| 2988_2021 | millions / thousands | genuine change of units | [1.007, 1.005, 1.005, 1.004] | [0.001, 0.001, 0.001, 0.001] | clean / clean | None / 42 | - |
| 5623_2024 | thousands / millions | genuine change of units | [0.994, 0.997, 0.998, 0.999, 0.996] | [994.267, 997.048, 997.823, 999.33, 996.033] | clean / clean | 41 / 36 | - |
| 1492_2019 | thousands / millions | label slip | [0.001, 0.001, 0.001, 0.001] | [0.961, 0.979, 0.972, 0.974] | clean / clean | 69 / 65 | - |
| 2357_2024 | millions / thousands | label slip | [998.513, 986.775, 975.534, 993.877, 991.63] | [0.999, 0.987, 0.976, 0.994, 0.992] | clean / clean | 27 / 26 | - |
| 2786_2024 | millions / thousands | label slip | [972.525, 987.37, 987.547, 982.508, 969.538] | [0.973, 0.987, 0.988, 0.983, 0.97] | clean / clean | 50 / 45 | - |
| 2988_2020 | thousands / millions | label slip | [0.001, 0.001, 0.001] | [0.974, 0.977, 0.979] | clean / clean | 42 / 39 | - |
| 318_2024 | thousands / millions | units differ and the cells do not agree either way | [0.706, 0.927, 0.424, 0.977, 1.012] | [706.148, 926.996, 423.891, 976.953, 1012.081] | rebase / rebase | 69 / 60 | - |
| 780_2016 | millions / thousands | units differ and the cells do not agree either way | [0.917, 0.837, 0.729, 0.643, 0.279] | [0.001, 0.001, 0.001, 0.001, 0.0] | rebase / clean | 30 / 28 | - |
| 1110_2022 | thousands / millions | units differ and the cells do not agree either way | [0.001, 0.001, 0.001, 0.001, 0.006] | [1.082, 1.08, 1.153, 1.337, 5.983] | rebase / rebase | 37 / 16 | - |
| 1416_2024 | millions / thousands | units differ and the cells do not agree either way | [984.789, 297.408] | [0.985, 0.297] | rebase_oldest_column_only / rebase_oldest_column_only | 41 / 34 | - |
| 1458_2024 | thousands / millions | units differ and the cells do not agree either way | [0.0, 0.0, 0.0, 0.0, 0.0] | [0.001, 0.001, 0.001, 0.001, 0.001] | rebase / rebase | 47 / 45 | - |
| 1618_2024 | thousands / millions | units differ and the cells do not agree either way | [-0.992, -0.994, -0.992] | [-991.911, -993.844, -992.146] | clean / clean | 51 / 50 | - |
| 1856_2024 | thousands / millions | units differ and the cells do not agree either way | [1.545, 1.431, 1.322, 1.664, 2.184] | [1544.561, 1431.135, 1321.764, 1664.43, 2184.054] | rebase / rebase | 65 / 33 | 7 |
| 1884_2021 | millions / thousands | units differ and the cells do not agree either way | [-8.553, -5.834, -8.401, -10.753] | [-0.009, -0.006, -0.008, -0.011] | rebase / clean | 32 / 33 | - |
| 1910_2017 | millions / thousands | units differ and the cells do not agree either way | [0.917, 0.911, 0.93, 0.868, 0.907] | [0.001, 0.001, 0.001, 0.001, 0.001] | clean / clean | 35 / 39 | - |
| 1919_2018 | thousands / millions | units differ and the cells do not agree either way | [0.001, 0.001, 0.001, 0.001, 0.001] | [1.328, 1.324, 1.324, 1.319, 1.326] | clean / clean | None / 40 | - |
| 1955_2021 | thousands / millions | units differ and the cells do not agree either way | [1.002, 0.82] | [1002.05, 820.399] | alignment_uncertain / alignment_uncertain | 48 / 51 | - |
| 2121_2020 | millions / thousands | units differ and the cells do not agree either way | [0.971, 0.976, 0.979, 0.974, 0.977] | [0.001, 0.001, 0.001, 0.001, 0.001] | cell_scale_slip / cell_scale_slip | 56 / 56 | - |
| 2999_2019 | millions / thousands | units differ and the cells do not agree either way | [1.444] | [0.001] | no_identity_evidence / no_identity_evidence | 41 / 20 | - |
| 4472_2024 | thousands / millions | units differ and the cells do not agree either way | [1.364, 1.686, 1.71, 1.557, 1.673] | [1364.113, 1686.006, 1710.119, 1557.432, 1673.354] | rebase / rebase | 57 / 53 | - |
| 5623_2023 | millions / percentage | units differ and the cells do not agree either way | [] | [] | unit_unknown / unit_unknown | 36 / 24 | - |

Units cases that also show a rebase pattern (under the labelled or the raw units): 318_2024, 780_2016, 1110_2022, 1416_2024, 1458_2024, 1856_2024, 1884_2021, 4472_2024.

Sub-type counts: genuine change of units 21, label slip 4, units differ and the cells do not agree either way 15.

## Other records the screen sets apart

- `alignment_uncertain` (6): 1955_2023, 435_2016, 4444_2023, 5000_2018, 5151_2020, 5678_2016
- `no_identity_evidence` (4, the year t-1 grid is the claims triangle and no two years agree, so it is probably another table): 2623_2023, 382_2017, 382_2020, 382_2021
- `cell_scale_slip` (2): 2001_2018, 2121_2019

## Validation

- 2689_2023: **rebase** (ratios {2020: 1.5062, 2021: 1.2616, 2022: 1.0034}; pages 46 / 46). Factor 1.0034 from the unchanged 2022 cell; flagged [(2020, 41.076), (2021, 19.944)]; 56% of R in all, 18% of R without the oldest column (the 2020 column).
- 5820_2016: **clean**, ratios {2011: 1.1336, 2012: 1.1046, 2013: 1.1125, 2014: 1.1302, 2015: 1.144} (pages 42 / 25).
- 4020_2016: **not comparable** (t-1 record holds no triangle block): the 2015 report stores no triangle block, so the screen cannot test it; it is not flagged.
- 1301_2016: **rebase_year_t1_only**, ratios {2011: 1.0821, 2012: 1.1163, 2013: 1.1092, 2014: 1.1184, 2015: 0.6436} (pages None / 40).
- 6119_2016: **not comparable** (t-1 record holds no triangle block): the 2015 report stores no triangle block, so the screen cannot test it; it is not flagged.

- Of those, 179 have a retranslation factor more than 2% from 1 (the earlier diagonals' median ratio, measure 1 of the fx study) and are the genuine one-rate retranslations: verdicts {'clean': 163, 'no_common_single_year': 1, 'rebase': 5, 'rebase_oldest_column_only': 3, 'alignment_uncertain': 1, 'units_case': 2, 'rebase_year_t1_only': 4}; flagged: 1729_2023, 1910_2018, 1945_2018, 1947_2020, 2015_2022, 2121_2018, 2232_2017, 2468_2019, 3624_2018, 4141_2022, 4747_2024, 6134_2022.
  A flag on such a record is not for the retranslation: the one rate is divided out as the factor. It comes from a single year whose t-1 cell departs from that rate (1729_2023: 2021 at 1.776 against 1.20 for the other eight years; 4141_2022: 2018 and 2019 at 0.914 and 1.292 against 1.118; 1301_2016: underwriting year 2015 only).
- Records the earlier fx-translation measure classed as retranslated at one rate (cells `changed`, `one_rate`) that are in the 649: 323; flagged now: 13 (1176_2019, 1729_2023, 1910_2018, 1945_2018, 1947_2020, 2015_2022, 2121_2018, 2232_2017, 2468_2019, 3624_2018, 4141_2022, 4747_2024, 6134_2022); verdicts {'clean': 282, 'units_case': 25, 'no_common_single_year': 1, 'rebase_oldest_column_only': 4, 'rebase': 5, 'alignment_uncertain': 1, 'cell_scale_slip': 1, 'rebase_year_t1_only': 4}.
- Crude screen (`flagged.json`): 138 rows, 137 of them in the 649. Verdict of the new screen on those: {'clean': 64, 'no_common_single_year': 11, 'cell_scale_slip': 1, 'units_case': 10, 'rebase': 35, 'rebase_oldest_column_only': 9, 'alignment_uncertain': 4, 'no_identity_evidence': 1, 'rebase_year_t1_only': 2}.
  Of the crude hits in the 649, 16 have an aggregated-cohort anchor in one of the two grids and 10 state different units.
  Flagged now (rebase tiers) but not by the crude screen: 1176_2019, 1301_2016, 1729_2023, 1910_2018, 1945_2018, 1947_2020, 2015_2022, 2121_2018, 2232_2017, 2468_2019, 3624_2018, 4141_2022, 4242_2022, 4747_2024, 6134_2022.

## The brief's median factor against the shared-ratio factor

Over the compared records (units, alignment and identity cases left out), flagged in underwriting years u <= t-2 under both factors: 55; under the shared-ratio factor only: 3 (1856_2021, 1945_2016, 4444_2017); under the median only: 3 (2001_2018, 2001_2019, 2121_2019); under neither: 424.

## Which flagged records need a page reading

A. High-confidence flags in years u <= t-2 (RAG against RAG, an unchanged year or shared ratio present, one currency, no disagreement from the other model's grids) with size >= 5% of R: **17**: 1686_2021 (150%), 4747_2024 (89%), 2689_2023 (56%), 510_2015 (36%), 1967_2022 (35%), 4020_2018 (24%), 2001_2016 (23%), 2488_2019 (22%), 4141_2022 (20%), 1897_2019 (19%), 1945_2018 (11%), 1274_2016 (7%), 382_2022 (7%), 1967_2017 (7%), 1686_2022 (6%), 2232_2020 (5%), 382_2023 (5%). A reading decides whether the filing restates the history (then M is not the year's movement) or the stored grid misreads a cell. 2689_2023 is the reference case.
A2. High-confidence flags under 5% of R (2): 1218_2016, 1945_2016. Lower priority.
A3. High-confidence flags only through the oldest column or only through underwriting year t-1 (11): 6118_2018 (oldest_column_only), 1301_2016 (year_t1_only), 4000_2022 (oldest_column_only), 1967_2018 (oldest_column_only), 1910_2016 (year_t1_only), 4242_2017 (oldest_column_only), 2468_2020 (oldest_column_only), 1947_2022 (oldest_column_only), 2232_2017 (year_t1_only), 6134_2022 (oldest_column_only), 2232_2019 (oldest_column_only). The oldest-column ones need the table's own heading read for an unmarked 'and prior' column first.
B. Flags the screen cannot vouch for (31; the reasons are listed under the table above): 2121_2018, 3500_2023, 6107_2023, 4444_2022, 1880_2015, 2791_2022, 3000_2016, 780_2017, 3500_2022, 1274_2024, 1274_2022, 1947_2020, 1856_2021, 1609_2024, 2007_2016, 4444_2018, 4472_2022, 1729_2023, 2001_2017, 2015_2022, 1176_2019, 3624_2018, 4242_2022, 2468_2019, 2488_2016, 3000_2018, 1910_2018, 4444_2017, 3000_2022, 1084_2016, 5000_2023.
C. Units cases with a rebase pattern: 318_2024, 780_2016, 1110_2022, 1416_2024, 1458_2024, 1856_2024, 1884_2021, 4472_2024. Label slips (the raw cells agree, so one of the two units labels is wrong; the t grid's label sets the scale of that record's M): 1492_2019 (t cells 0.3918 of R, t-1 cells 400.9135 of R, as labelled), 2357_2024 (t cells 791.8535 of R, t-1 cells 0.793 of R, as labelled), 2786_2024 (t cells 189.0933 of R, t-1 cells 0.1945 of R, as labelled), 2988_2020 (t cells 0.7283 of R, t-1 cells 745.2672 of R, as labelled).
D. `alignment_uncertain`: 1955_2023, 435_2016, 4444_2023, 5000_2018, 5151_2020, 5678_2016; `no_identity_evidence`: 2623_2023, 382_2017, 382_2020, 382_2021; `cell_scale_slip`: 2001_2018, 2121_2019 (a single misread cell each, in the t grid or the t-1 grid).
E. Not screenable (8 + 92 + 12 records: no year t-1 record, no t-1 gross grid, no common single year). Among Vignette 1's top 20 donors: 1991_2015 (rank 6), 1699_2024 (rank 17), 2526_2015 (rank 18).

## Vignette 1 top-20 donors

| rank | donor | verdict | size / R | note |
|---|---|---|---|---|
| 1 | 1991_2020 | clean | - |  |
| 2 | 1945_2020 | clean | - |  |
| 3 | 3010_2024 | clean | - |  |
| 4 | 5820_2016 | clean | - |  |
| 5 | 1991_2019 | clean | - |  |
| 6 | 1991_2015 | no_gross_grid_prev | - | t-1 record holds no triangle block |
| 7 | 1856_2024 | units_case | - |  |
| 8 | 1991_2016 | clean | - |  |
| 9 | 3334_2016 | clean | - |  |
| 10 | 1183_2024 | units_case | - |  |
| 11 | 1991_2018 | clean | - |  |
| 12 | 2689_2023 | rebase | 0.560 |  |
| 13 | 2999_2022 | clean | - |  |
| 14 | 1991_2017 | clean | - |  |
| 15 | 2001_2024 | units_case | - |  |
| 16 | 609_2024 | clean | - |  |
| 17 | 1699_2024 | no_gross_grid_prev | - | t-1 record holds no triangle block |
| 18 | 2526_2015 | no_gross_grid_prev | - | t-1 record holds no triangle block |
| 19 | 1969_2018 | clean | - |  |
| 20 | 1729_2024 | clean | - |  |

