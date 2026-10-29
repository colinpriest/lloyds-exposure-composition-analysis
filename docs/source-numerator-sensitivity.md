# Sensitivity to two source-derived numerator figures

The headline sample contains two figures derived from accounts rather than directly read as a final mature-cohort movement. Neither source supports treating these assumptions as independently established facts. This sensitivity quantifies their effects on the fitted size-only operator and on the empirical vignette donor pool; it does not identify the true figures.

For 3330/2017, the £0.559m figure is the gross whole-account claims roll-forward, not a disclosed mature-cohort split. The [2016 accounts](https://assets.lloyds.com/assets/pdf-syndicate-reports-and-accounts-2016-3330-a/1/pdf-syndicate-reports-and-accounts-2016_3330_a.pdf) show £14.059m opening claims reserves split between 2011 and 2012 underwriting years; the 2017 accounts show £11.701m closing reserves in those cohorts. The reports do not allocate the year's aggregate £2.270m gross paid claims and £0.647m exchange adjustment by cohort. Hence the exact contribution of any other business to the aggregate incurred figure remains unestablished. The source-based roll-forward is preferable to treating the printed prior triangle values as unquestionably comparable, but is still an approximation.

For 1274/2016, the current +USD 22.6943m figure corrects a suspicious 2012-cohort cell using the ratio of two reports' historical paid values. Those values are printed, but the paid-ratio exchange adjustment and misprint diagnosis are inferred. The 2016 table as printed implies +USD 57.503m; using the previous-year cell without that inferred retranslation implies +USD 19.871m. Both are alternative constructions, not validated corrections or proven bounds.

## Design and interpretation

`src/check_source_numerator_sensitivity.py` runs five separate four-chain refits of the same gamma-zero likelihood as the headline: exclude 3330/2017, exclude 1274/2016, exclude both, use the printed 1274/2016 figure, and use its un-retranslated alternative. It uses the adopted posterior and vignette functions rather than a hand-written transfer operator. For each case, it rebuilds the donor pool consistently, separately reporting changes from the pool alone, the fit alone, and both together. The centres use the empirical inverse-CDF quantile at posterior-mean parameter values and the same rounded donor pool as the shipped tool. They are **point estimates**, not posterior intervals, and there is no refitted cross-validation here.

A baseline reconstruction is required to equal the repository's stored headline vignette centres exactly. Each fit's complete posterior and sampler statistics are saved in an explicitly specified external output folder; the compact result file in `results/source_numerator_sensitivity_results.json` contains the fit summaries, diagnostic checks and SHA-256 fingerprints. The output records the analysis commit and the producer's uncommitted state at the time it ran, rather than asserting a clean full-repository reproduction.

Reproduction requires Python 3.12.6, NumPy 2.1.3, SciPy 1.14.1, PyMC 5.25.1, PyTensor 2.31.7, Numba 0.61.2, and ArviZ 0.22.0. The recorded run uses four chains, 1,500 tuning iterations and 1,500 retained draws per chain, random seed 42, target acceptance 0.98, a single core and the `NUMBA` mode of `check_cohort_scope.py`. The `PYTENSOR_FLAGS` compiler/cache setting and the working-tree status are described with the local run logs.

The source check used these retained-file hashes: 1274/2015 `0c3b92ddd79afb25ec3d4460fd4c212ac7b32861ecebe09ab8afc549f7175a0f`, 1274/2016 `94514a7ef10976c05d270bd80b5f0fa3f6a510c36e4372c4f2d0898f77da1769`, 3330/2016 `be280824f88ec3829c87da8c9f637c3d63db7f8fe2a19e6b589786121ec61ea0`, and 3330/2017 `40151f9d45ae272bb96c49f1e72fa5579803ec7ef934f9e5e03ca5478d7bce0a`. PDF pages for 1274 are 40–41 of the 2015 and 2016 reports; 3330 uses pages 12, 28–29 of the 2017 report and the 2016 gross triangle on printed page 27.

## Results

The reproduced headline Vignette 1 VaR99.5 is 0.342408. The table reports 95% highest-density intervals for $k$ and the sensitivity vignette point, followed by its relative change from that headline point. The intervals for $k$ are from the refits; they are not intervals for the vignette points.

| Source assumption | Fit / donors | $k$ (95% HDI) | V1 VaR99.5 | Relative change |
| --- | ---: | ---: | ---: | ---: |
| Exclude 3330/2017 | 631 | 0.618 [0.519, 0.722] | 0.339745 | -0.78% |
| Exclude 1274/2016 | 631 | 0.624 [0.514, 0.726] | 0.342445 | +0.01% |
| Exclude both | 630 | 0.618 [0.510, 0.716] | 0.339576 | -0.83% |
| 1274: printed 2016 cells | 632 | 0.626 [0.522, 0.731] | 0.342981 | +0.17% |
| 1274: prior cell without retranslation | 632 | 0.623 [0.516, 0.725] | 0.342048 | -0.10% |

All five fits had zero divergent transitions and maximum R-hat below 1.004 across the recorded summary. Holding the headline fit fixed while changing the pool alone leaves V1 VaR99.5 unchanged in each case. The movements shown arise from the refits. These five comparisons are targeted checks; they do not verify the two reconstructions or all other figures. The existing primary can be retained with the assumptions and sensitivity disclosed, rather than selectively excluding these records without applying a comparable source-quality rule across the sample.
