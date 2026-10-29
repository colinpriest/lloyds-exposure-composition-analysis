# Conditional inclusion of Syndicate 1254/2022

This is an inclusion sensitivity, **not a correction adopted into the primary sample**. It asks how the adopted model and example donor pool respond if the 2022 whole-account gross incurred movement is treated as development of the inherited mature-cohort liabilities. The accounts support that interpretation but do not print the necessary exact cohort split.

## Source and conditional construction

The [2022 annual accounts](https://assets.lloyds.com/media/a72ff857-c214-4790-b81b-177b3f910515/SRA1254a.pdf), SHA-256 `faa232fe62f1b2d3d8f8f4034abdf1611126cab59ca1de2fae784b32050d2932`, say the newly formed syndicate took an inward reinsurance-to-close (RITC) of Syndicate 2689's 2017, 2018 and 2019 years of account, effective 1 January 2022. Its own accounting opening balance was nil. The mature-cohort cutoff in 2022 is 2020 or earlier, so those three inherited years are mature by that rule.

The gross claims-outstanding reconciliation on PDF page 41 gives the following amounts, in £m:

| Item | Gross £m |
| --- | ---: |
| Own accounting opening balance | 0.000 |
| RITC liabilities taken on | 75.257 |
| Change in provision through the technical account | −27.481 |
| Foreign exchange movement | +7.798 |
| Closing gross provision | 55.574 |

The change and exchange movements reconcile to the closing provision: 75.257 − 27.481 + 7.798 = 55.574. PDF page 16 gives gross paid claims of £22.748m. Paid claims plus the technical-account provision change are therefore **−£4.733m gross incurred**, using positive for adverse development. The separate FX movement is not added to that incurred figure. The accounts show £4.733m as a credit in the underwriting-results table on page 36. The £75.243m RITC premium is net; it is not substituted for the £75.257m gross liabilities.

The scenario uses a reserve base of **£75.257m**, including the acquired reserves despite the nil accounting opening balance, and severity **−4.733 / 75.257 = −0.0628912**. This assumes the whole-account incurred figure is attributable to the inherited 2017–2019 years. Page 36 says the year's premiums were understood to be reinstatement and adjustment premiums on existing quota-share contracts, with the last contract issued in 2019; this supports the scenario but does not establish an exact claims allocation. The RITC scan flags 1254/2022 as strong assumed business and the fit uses that regime.

Page 30 prints a gross development triangle that includes estimates made by the cedant before the RITC. Its latest-minus-previous cells total **−£28.229m**, not −£4.733m. Its three closing gross reserves total **£55.276m**, £0.298m below the £55.574m balance-sheet gross provision. Neither difference is silently repaired or assumed to have a particular cause. The sensitivity uses the gross whole-account roll-forward, not the inherited-triangle difference; the missing cohort allocation and gross closing mismatch remain limitations.

## Premium-mix proxy and fitted model

Page 36 discloses 2022 gross written premium of £2.507m: casualty £0.503m, property £1.571m, marine £0.230m, energy £0.191m, motor £0m and aviation £0.012m. Applying the existing analysis classifier to those class labels produces HHI **0.4471843**. The amounts are adjustments and reinstatements on quota shares; they do not measure the inherited reserve mix, and the table places them under reinsurance acceptances. The category labels follow the existing classifier's treatment of those rows. The adopted headline fixes concentration exponent gamma to zero, so HHI does not affect the fitted scale or the headline transfer, although a complete proxy is needed to append the observation under the sample definition.

`src/check_1254_2022_inclusion.py` adds the conditional observation to the 632-observation headline sample and independently rebuilds the 633-donor pool. Syndicate 1254 already contributes a 2023 observation, so the number of syndicates stays at 117. It runs the adopted gamma-zero model using four chains, 1,500 tuning and 1,500 retained draws per chain, target acceptance 0.98 and seed 42. It independently recomputes the headline vignette centres and requires exact equality before comparing them. Pool-only, fit-only and combined legs are saved. Vignette numbers are equal-donor empirical inverse-CDF points at posterior-mean parameters, not posterior intervals; no cross-validation or vignette interval is refitted.

## Targeted result

The conditional fit gives **k = 0.625 [0.522, 0.733]** (95% highest-density interval) and an undiversifiable floor of **0.0290**. All chains completed with zero divergences; maximum R-hat was **1.0031**, minimum bulk effective sample size **1,883**, and minimum tail effective sample size **2,146**, across the reported full summary.

The reconstructed headline Vignette 1 VaR99.5 is **0.342408**; after the refit and donor-pool rebuild it is **0.343243** (**+0.244%**). Adding the donor with the headline parameters held fixed leaves that particular point unchanged; the change arises from the refit. The conditional donor's transferred Vignette 1 severity is **−0.03622** and it is not the upper-tail threshold donor. These figures test the impact of the stated construction; they do not establish that construction as the primary observation.

`results/conditional_1254_2022_inclusion_results.json` contains the fit, scenario inputs, diagnostic values and point estimates. The separate provenance record captures input and producer hashes, execution environment, base commit and the fact that the producer and source fixture were uncommitted when the targeted run took place. Full posterior and sampler draws were retained separately in local research. The older full-manifest reproduction report does not cover this sensitivity.
