# Source-backed maturity proxy repair

Frozen analysis pin: `fb2f0c28b409038465f3efcd0728eebfb5b0d9f6`. All changes were developed and tested in an isolated copy; frozen and user checkout originals were not changed. The source fixture is `data/maturity_proxy_source_overrides.json`. It records the filing identifiers, page references and SHA-256 hashes; source reports are not redistributed in this repository.

The original producer sometimes treated incremental claims as current cumulative totals, selected an incorrectly labelled or net triangle, or omitted an available cumulative gross older group. Source-backed replacements are tied to the selected extraction fingerprint. For groups, the existing rule assigns all years the latest labelled age; the true age mix is unknown, so finite-delta run-off weights are approximate. An underlying group without a compatible gross incurred/ultimate total is not invented.

382/2019–20, 5820 and 727 use estimates on premium earned to date; they are not measured opening reserves. For 727/2024 the filing omits the 2014 label; the 2013-and-prior group is included with its actual label and the gap remains. For 4242 the recovered grouped incurred amount is gross paid plus gross outstanding. For 1274/2022 and 1225/2021 gross diagonals replace selected net triangles. For 2088/2019 a source-verified missing cohort required a reconstructed vector.

The 382/2016 maturity extract contains incorrect incremental cells for 2008–2010; the fix transcribes printed current totals. The headline observation already uses the independent confirmed-figure register, gross movement −£14.328m; the source and test verify it is unchanged.

The primary 632-observation all-delta guard changes from 607 to 608 observations; 382/2020 enters and none leave. The comparison covers exactly the 70 rows below. Old and corrected infinity shares are shown to four decimals; the regenerated `model/maturity_share.json` records all four deltas. A separate sensitivity removes newly recovered older groups and replaces the 1225 grouped totals with source-supported pure-year figures. Other previously captured groups remain, so it is not a complete no-group sensitivity.

The 457/2018 and 457/2021 selected monetary values have a uniform source-unit discrepancy; the phi ratio is invariant to uniform scaling. In 457/2015 the filing has conflicting underwriting-year and accident-year headings; the primary retains its stated underwriting basis. These uncertainties and groups not disclosed on the verified gross cumulative basis remain limitations. Source review was targeted and does not establish every one of the 798 proxy records is free from extraction errors.

All source correction records name the filing, page and SHA, selected extraction fingerprint, and complete values in `data/maturity_proxy_source_overrides.json`. iXBRL page references are printed report page numbers.

| Observation | Source page | Measure | Group treatment | phi inf before | phi inf after |
|---|---:|---|---:|---:|---:|
| 382/2015 | 46 | ultimate claims | — | 0.9925 | 0.8924 |
| 382/2016 | 46 | ultimate claims | — | 0.4651 | 0.8785 |
| 382/2017 | 47 | ultimate claims | — | 0.5462 | 0.8889 |
| 382/2018 | 46 | ultimate claims | — | 0.7307 | 0.8749 |
| 382/2019 | 46 | earned claims | — | 0.5733 | 0.8844 |
| 382/2020 | 47 | earned claims | — | 0.3009 | 0.9309 |
| 435/2015 | 34 | gross cumulative claims, verified current diagonal | — | 0.8610 | 0.7844 |
| 727/2015 | 59 | gross current cumulative claims; selected individual cohort values verified against filing | 2010 and prior: 1273782 GBP thousand | 0.7811 | 0.9677 |
| 727/2016 | 61 | gross current cumulative claims; selected individual cohort values verified against filing | 2010 and prior: 1466319 GBP thousand | 0.8275 | 0.9710 |
| 727/2017 | 67 | gross ultimate claims on premium earned to date | 2010 and prior: 1360153 GBP thousand | 0.8517 | 0.9710 |
| 727/2018 | 69 | gross ultimate claims on premium earned to date | 2010 and prior: 1421358 GBP thousand | 0.8697 | 0.9716 |
| 727/2020 | 70 | gross ultimate claims on premium earned to date | 2010 and prior: 1323317 GBP thousand | 0.8921 | 0.9708 |
| 727/2021 | 70 | gross ultimate claims on premium earned to date | 2011 and prior: 1406103 GBP thousand | 0.8739 | 0.9677 |
| 727/2022 | 70 | gross ultimate claims on premium earned to date | 2012 and prior: 1601764 GBP thousand | 0.8696 | 0.9674 |
| 727/2023 | 71 | gross ultimate claims on premium earned to date | 2013 and prior: 1589038 GBP thousand | 0.8661 | 0.9662 |
| 727/2024 | 73 | gross ultimate claims on premium earned to date | 2013 and prior: 1641568 GBP thousand | 0.8875 | 0.9708 |
| 1084/2015 | 35 | gross current cumulative claims | 2010 and prior: 814.5 GBP million | 0.7091 | 0.7852 |
| 1084/2016 | 33 | gross current cumulative claims | 2010 and prior: 781.7 GBP million | 0.8160 | 0.8544 |
| 1084/2017 | 28 | gross current cumulative claims | 2010 and prior: 745.2 GBP million | 0.8539 | 0.8806 |
| 1084/2019 | 29 | gross current cumulative claims | 2010 and prior: 863.5 USD million | 0.8507 | 0.8691 |
| 1084/2020 | 29 | gross current cumulative claims; selected individual cohort values verified against filing | 2010 and prior: 860.1 USD million | 0.8784 | 0.8915 |
| 1084/2021 | 31 | gross current cumulative claims; original extraction labels shifted one year | 2011 and prior: 1637.1 USD million | 0.9288 | 0.9001 |
| 1084/2023 | 37 | gross current cumulative claims; selected individual cohort values verified against filing | 2013 and prior: 2118 USD million | 0.8738 | 0.9010 |
| 1176/2016 | 29 | gross current cumulative claims | 2010 and prior: 13771 GBP thousand | 0.7495 | 0.8137 |
| 1176/2017 | 29 | gross current cumulative claims | 2010 and prior: 12702 GBP thousand | 0.7060 | 0.7694 |
| 1176/2018 | 29 | gross current cumulative claims | 2010 and prior: 3524 GBP thousand | 0.8250 | 0.8365 |
| 1176/2019 | 29 | gross current cumulative claims | 2010 and prior: 10056 GBP thousand | 0.8171 | 0.8477 |
| 1176/2020 | 32 | gross current cumulative claims; selected individual cohort values verified against filing | 2010 and prior: 9449 GBP thousand | 0.8049 | 0.8346 |
| 1176/2021 | 33 | gross current cumulative claims; selected individual cohort values verified against filing | 2011 and prior: 22853 GBP thousand | 0.7830 | 0.8622 |
| 1176/2022 | 36 | gross current cumulative claims; selected individual cohort values verified against filing | 2012 and prior: 22809 GBP thousand | 0.8057 | 0.8780 |
| 1176/2023 | 36 | gross current cumulative claims; selected individual cohort values verified against filing | 2013 and prior: 25727 GBP thousand | 0.6888 | 0.8115 |
| 1200/2018 | 43 | gross cumulative claims, verified current diagonal | 2012 and prior: 712.3 GBP million | 0.9080 | 0.8198 |
| 1200/2019 | 42 | gross current cumulative claims; selected individual cohort values verified against filing | 2012 and prior: 716.8 GBP million | 0.8469 | 0.8870 |
| 1200/2020 | 43 | gross current cumulative claims; selected individual cohort values verified against filing | 2013 and prior: 918.6 GBP million | 0.8460 | 0.8924 |
| 1225/2016 | 27 | gross ultimate; 2011-and-prior replaces incomplete 2011-only earned estimate | group replaces individual year | 0.8130 | 0.9334 |
| 1225/2017 | 26 | gross ultimate; 2012-and-prior replaces incomplete 2012-only earned estimate | group replaces individual year | 0.7549 | 0.9172 |
| 1225/2018 | 28 | gross ultimate; 2013-and-prior replaces incomplete 2013-only earned estimate | group replaces individual year | 0.7593 | 0.9182 |
| 1225/2019 | 29 | gross ultimate; 2014-and-prior replaces incomplete 2014-only earned estimate | group replaces individual year | 0.7653 | 0.9218 |
| 1225/2020 | 29 | gross ultimate; 2015-and-prior replaces incomplete 2015-only earned estimate | group replaces individual year | 0.7594 | 0.9176 |
| 1225/2021 | 29 | gross ultimate grouped 2016-and-prior and gross earned individual cohorts; selected triangle was net | group replaces individual year | 0.7772 | 0.9219 |
| 1225/2022 | 32 | gross ultimate; 2017-and-prior replaces incomplete 2017-only earned estimate | group replaces individual year | 0.7496 | 0.9108 |
| 1274/2019 | 34 | gross current cumulative claims; selected individual cohort values verified against filing | 2010 and prior: 602757 USD thousand | 0.8372 | 0.8710 |
| 1274/2020 | 36 | gross current cumulative claims; selected individual cohort values verified against filing | 2010 and prior: 621803 USD thousand | 0.8723 | 0.8953 |
| 1274/2021 | 36 | gross current cumulative claims; selected individual cohort values verified against filing | 2011 and prior: 785917 USD thousand | 0.9038 | 0.9239 |
| 1274/2022 | 36 | gross cumulative claims; selected triangle was net, replaced with gross filing values | 2012 and prior: 946246 USD thousand | 0.9132 | 0.9394 |
| 1274/2023 | 35 | gross current cumulative claims; selected individual cohort values verified against filing | 2013 and prior: 1139908 USD thousand | 0.9037 | 0.9291 |
| 1458/2019 | 41 | gross current cumulative claims incurred | 2009 and prior: 8.244487 GBP million | 0.7670 | 0.7682 |
| 1458/2020 | 45 | gross current cumulative claims; selected individual cohort values verified against filing | 2010 and prior: 39.023755 GBP million | 0.8083 | 0.8119 |
| 1458/2021 | 45 | gross current cumulative claims incurred | 2011 and prior: 122.017776 USD million | 0.8201 | 0.8264 |
| 1458/2022 | 45 | gross current cumulative claims incurred | 2012 and prior: 194.271313 USD million | 0.8252 | 0.8334 |
| 1458/2023 | 45 | gross current cumulative claims incurred | 2013 and prior: 289.444987 USD million | 0.8377 | 0.8472 |
| 1458/2024 | 47 | gross current cumulative claims incurred | 2014 and prior: 447207 USD thousand | 0.9082 | 0.9156 |
| 2003/2015 | 42 | gross current cumulative claims; selected individual cohort values verified against filing | 2010 and prior: 20340887 USD thousand | 0.7443 | 0.9425 |
| 2003/2016 | 43 | gross current cumulative claims; selected individual cohort values verified against filing | 2011 and prior: 21234414 USD thousand | 0.7440 | 0.9459 |
| 2003/2017 | 44 | gross current cumulative claims; selected individual cohort values verified against filing | 2011 and prior: 21744 USD million | 0.7489 | 0.9331 |
| 2003/2019 | 46 | gross current cumulative claims; selected individual cohort values verified against filing | 2011 and prior: 21735 USD million | 0.8421 | 0.9404 |
| 2003/2020 | 46 | gross current cumulative claims; selected individual cohort values verified against filing | 2011 and prior: 16076 GBP million | 0.8549 | 0.9387 |
| 2007/2015 | 37 | gross current cumulative claims; selected individual cohort values verified against filing | 2010 and prior: 1559.3 GBP million | 0.7355 | 0.8741 |
| 2088/2017 | 34 | gross estimate of incurred claims | 2012 and prior: 34998 GBP thousand | 0.6436 | 0.7015 |
| 2088/2018 | 35 | gross incurred claims | 2013 and prior: 70138 GBP thousand | 0.5495 | 0.6351 |
| 2088/2019 | 24 | gross incurred claims; extraction years shifted | 2012 and prior: 35827 GBP thousand | 0.9097 | 0.7195 |
| 2623/2023 | 46 | gross current cumulative claims; original extraction labels shifted one year | 2013 and prior: 8824.7 USD million | 0.8413 | 0.9047 |
| 2999/2021 | 46 | gross current cumulative claims; original extraction labels shifted one year | — | 0.9306 | 0.8985 |
| 4242/2021 | 46 | gross current cumulative claims; selected individual cohort values verified against filing | 2015 and prior: 76292 USD thousand | 0.7460 | 0.7609 |
| 4242/2022 | 44 | gross current cumulative claims; selected individual cohort values verified against filing | 2016 and prior: 155574 USD thousand | 0.8490 | 0.8660 |
| 4242/2023 | 45 | gross current cumulative claims; selected individual cohort values verified against filing | 2017 and prior: 467625 USD thousand | 0.8353 | 0.8858 |
| 5820/2015 | 25 | gross ultimate claims on premium earned to date; long earning pattern | 2010 and prior: 12.0 GBP million | 0.8210 | 0.8311 |
| 5820/2016 | 42 | gross ultimate claims on premium earned to date; long earning pattern | 2010 and prior: 11.8 GBP million | 0.8525 | 0.8579 |
| 5820/2017 | 41 | gross ultimate claims on premium earned to date; long earning pattern | 2010 and prior: 9.0 GBP million | 0.8300 | 0.8340 |
| 6107/2023 | 30 | gross current cumulative claims; original extraction labels shifted one year | 2013 and prior: 41.0 USD million | 0.9417 | 0.8924 |
