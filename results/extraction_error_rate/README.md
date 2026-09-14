# Extraction error rate

The probability that a record drawn at random from the working sample carries a materially wrong adopted
prior-year development figure, judged against the syndicate's own filing (PLAN R163). The protocol,
`protocol/error-rate-protocol.md`, was fixed on 11 September 2026, before any sample was drawn. Its 9
amendments, its clarification and its 5 implementation notes are dated, and each says what prompted it.

## Results

Errors / correct / undeterminable, and the mean and 95% equal-tailed credible interval of the Beta(1/2, 1/2)
posterior over the adjudicable records. The clarified rule is the protocol's. The first readers' instruction
is reported beside it, without second-reading corrections, which were made under the clarified rule.

| Extraction | Drawn | Clarified rule | Mean [95% CrI] | First readers' instruction | Mean [95% CrI] |
|---|---|---|---|---|---|
| Before R209 and R210 | 60 of 707 | 7 / 48 / 5 | 0.134 [0.059, 0.234] | 19 / 33 / 8 | 0.368 [0.245, 0.501] |
| After R209 and R210 | 60 of 698 | 2 / 53 / 5 | 0.045 [0.008, 0.112] | 16 / 34 / 10 | 0.324 [0.204, 0.457] |
| Tail stratum (after refit 3) | the 20 largest transferred severities | 1 / 18 / 1 | 0.075 [0.006, 0.221] | 8 / 11 / 1 | 0.425 [0.223, 0.641] |

The first sample was drawn from a working sample of 707. R208 then removed one record that was not drawn
(1947/2019), and the third amendment explains why the drawn records remain a simple random sample of the 706
that stayed. The second row is the extraction after PLAN R209 and R210. They changed the working sample after
the first result was scored, and a record entered it, so the study was re-run from step 1 with a new draw
(fourth amendment). 16 records held by both samples kept their readings, because nothing their verdicts were
read against had changed, and 44 were read afresh. Second readings: 37 on the first sample, 35 on the second.

The third row is the tail stratum: the 20 largest Vignette-1 transferred severities, computed after the refit
(analysis run 4ead3fba-e346-5e93-a1e8-39384d7da303). It is purposive, so it is reported apart and never pooled with either random sample. 9
of its records kept readings from a primary sample, and 11 were read afresh.

## After the second sample: the error mechanisms, the repairs, a third sample and the effect on the VaR

The second sample's two errors are mechanisms, not one-off misreadings. The fifth amendment counted and repaired
them, drew a larger random sample from the repaired working sample, and measured the errors' effect on Vignette
1's VaR99.5. The sixth and seventh amendments added the take-on census, the records found in passing and the
repair by a confirmed figure. Each census and each list of records found in passing is purposive, so it is
reported on its own and never pooled with a random sample.

### The census of the two mechanisms (`census/`)

6 records, each read twice (6 second readings, 0 overturned a first reading):

- replay stopped: 1 record(s); error 2008/2021; correct none; undeterminable none.
- aggregated older cohort omitted: 5 record(s); error 3624/2015; correct none; undeterminable 2007/2015, 4242/2021, 4242/2022, 4242/2023.

### The take-on census (`takeon-census/`)

9 working-sample records in the RITC regime take a movement the filing states as their figure. Each
was read twice for whether that figure is the take-on itself, the reserves a transfer brought in. Take-ons, which
leave the working sample: 2008/2021. Other errors the same readings confirmed: 2008/2019.

### Records found in passing (`found-in-passing/`)

4 records the mapping of the extraction code named, each read twice. Confirmed errors:
1225/2022. Readings that split: 623/2014. Undeterminable in both readings:
623/2022, 1206/2014. A record whose readings do not agree on an error and its filing figure is left as it is
(seventh amendment, point 2). `syndicate_623_2014_p45.png` is the rendered page the second reading of 623/2014 used.

### The repairs (`repairs/`)

The errors two readings confirmed before repair, in the report's currency (`error-rate-confirmed-errors.json`):

| Record | Found by | Adopted | Filing | Opening reserves |
|---|---|---|---|---|
| 1225/2022 | found in passing | -6.1m | +18.6m | +932.2m |
| 2008/2019 | take-on census | +249m | +14.053m | +1331.49m |
| 2008/2021 | second sample | +383.9m | -67.153m | +1297.112m |
| 2010/2018 | third sample | +179.777m | -15.755m | +488.317m |
| 2010/2019 | first sample, persisting | +132.679m | -18.659m | +485.327m |
| 2791/2015 | eighth census | -141.318m | -2.131m | +342.27m |
| 3010/2018 | eighth census | +20.101m | -4.14m | +54.774m |
| 3010/2019 | third sample | +25.459m | -1.925m | +58.14m |
| 3624/2015 | second sample | -0.912m | +5.025m | +346.998m |
| 382/2015 | third sample | -15.848m | +2.626m | +235.385m |
| 382/2016 | third sample | -50.211m | -14.328m | +249.68m |
| 382/2017 | eighth census | +49.14m | +7.401m | +343.077m |
| 382/2018 | third sample | +13.51m | +24.988m | +425.362m |
| 382/2019 | third sample | +173.514m | +12.549m | +493.738m |
| 4444/2022 | first sample, persisting | +435.491m | +34.9m | +1980.61m |
| 5678/2015 | eighth census | +5.3m | -8.135m | +96.644m |

- Repaired in the extraction (extraction repository 5bf65452,
  `pdf_extraction/audit/triangle_figures_confirmed_by_hand.json`): the pipeline's deterministic triangle gives the
  confirmed figure, which its sign check had refused, and the register lets that figure stand for these records
  only: 3624/2015, 1225/2022, 2010/2019.
- Repaired by the analysis loader (analysis repository 3d6376a, `data/pyd_confirmed_figures.json`): no extraction
  route produces the confirmed figure, so the loader adopts it and discloses the correction in the record:
  1880/2014, 2008/2019, 2010/2015, 2010/2018, 2791/2015, 3010/2018, 3010/2019, 382/2015, 382/2016, 382/2017, 382/2018, 382/2019, 4444/2022, 510/2014, 5678/2015.
- Excluded as take-ons (`data/takeon_not_development.json`): 1274/2018, 1980/2018, 2003/2018, 2008/2021.

`mechanism-variants-scan.json` records the scan of every committed extraction record for the mechanisms these
records showed. `replay-r213-full.log` is the full offline replay of 940 data-carrying records
under the repaired pipeline, and `replay-r213b.log` the replay of the two records then added to the extraction's
register.

### The third sample (`third-sample/`)

Drawn on 2026-09-13T21:49:29 from analysis run a5d20430-0850-5d23-bbab-ea27f8ccb7e3, before any of its records was read. The rebuilt
working sample holds 697 records; A, the records the second sample's population also holds,
697; entrants 0; left: 2008/2021. 110 records were drawn from the
638 records of A that the second sample had not drawn (seed 20260914). 5 kept readings from an
earlier sample or census, because nothing their verdicts were read against had changed; 106 were read afresh,
in batches of 10, 10, 10, 10, 10, 10, 10, 10, 10, 10 and 6. A second-sample record whose adopted figure a repair changed was read again:
3624/2015. Second readings: 62. The first briefs, set aside
before any reading, are in `superseded-before-reading/` (implementation note 2).

| Rate after the repairs | Records | Errors / correct / undeterminable | Mean [95% CrI] |
|---|---|---|---|
| A's sampled records: the second sample still in A and the third sample | 169 | 8 / 154 / 7 | 0.052 [0.024, 0.091] |
| The third sample alone, clarified rule | 110 | 8 / 100 / 2 | 0.078 [0.036, 0.135] |
| The third sample alone, first readers' instruction | 110 | 37 / 63 / 10 | 0.371 [0.280, 0.467] |

The working sample's rate, A's posterior weighted by its adjudicable share with the entrants' errors counted in
full (200000 draws, seed 20260914): mean 0.052, 95% CrI [0.024, 0.091].

### What the third sample found, and the eighth amendment (`third-sample/findings/`, `eighth-census/`)

The third sample's errors are mechanisms the earlier repairs did not reach: 1880/2014, 1980/2018, 2010/2018, 3010/2019, 382/2015, 382/2016, 382/2018, 382/2019. The opening
reserves, which the protocol checks against a 2% tolerance and reports apart from the rate, fell outside it in
3 first reading(s): 1225/2018 (adopted 206.7, filing 595.8, p27; error-rate-verdicts-eighth.json); 609/2023 (adopted 254.964, filing 1171.381, p41; error-rate-verdicts-eighth.json); 2003/2018 (adopted 1659.705, filing 5344.064, p44; error-rate-verdicts-third.json).

On 14 September 2026 the owner decided to repair them, count their mechanisms in a census and refit again
(eighth amendment). The rate above is the one the third sample measured, before those repairs. The repairs, all
by registers the analysis loader reads (analysis repository 3d6376a):

- figures: every entry of `data/pyd_confirmed_figures.json` with a figure is listed under the repairs above;
- a basis the readings established, the record excluded like any net or unknown-basis record: 1880/2014 (net), 510/2014 (net), 623/2014 (unknown);
- opening reserves (`data/opening_reserves_confirmed.json`): 1225/2018 (595.8m), 2003/2018 (5344.064m), 609/2023 (1171.381m);
- take-ons (`data/takeon_not_development.json`): listed under the repairs above.

The census (`eighth-census/`) was computed and written on 2026-09-14T08:39:57, before any of its records was
read, from six rules the amendment states; a record may sit in more than one part. 68 records were
read or kept earlier readings, and 12 already decided were not read. 58 were read afresh,
in batches of 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5 and 3; batch 12's reader stopped on its spend limit after one record, and batch 12b read the other
two. The dry runs that tightened three rules before any reading are kept beside it.

| Part | Flagged | Decided | Read | Found by both readings | Absent by both | Unsettled |
|---|---|---|---|---|---|---|
| movement | 12 | 4 | 8 | 382/2017 | 7 | none |
| transposed | 21 | 3 | 18 | 3010/2018, 5678/2015 | 13 | 1945/2021, 2010/2014, 2010/2023 |
| net_table | 7 | 3 | 4 | 382/2017, 510/2014 | 2 | none |
| provisions_row | 6 | 2 | 4 | none | 3 | 1206/2014 |
| opening | 3 | 1 | 2 | 1225/2018, 609/2023 | 0 | none |
| takeon_triangle | 37 | 2 | 35 | none | 35 | none |

Errors both readings confirmed: 2010/2015, 2791/2015, 3010/2018, 382/2017, 510/2014, 5678/2015.

### The eighth census's repairs and the take-on base (`ninth-census/`)

The eighth census's confirmed errors are repaired through the same registers (ninth amendment, point 1), with the
owner deciding 2010/2015's figure. The census also found a take-on base: a triangle restated to carry business
taken on in the report year covers it on both diagonals of its step, while the opening reserves at 1 January
exclude it, so the severity is overstated. On 14 September 2026 the owner decided to adjust the opening reserves.

The take-on base census was computed and written on 2026-09-14T12:34:55, before any of its records was read,
from three rules over the 692 records of the working sample the loader predicted for
refit 3 (scan 30, passage 28, row 16; a record may meet several). On dry runs that read no filing for a verdict, the row rule was
tightened twice: 175 records listed, then 107, then 50.
50 records were listed: 28 kept both eighth-census readings, and 22 were read
afresh, in batches of 5, 5, 5, 5 and 2. Adjusted (`data/opening_reserves_takeon_base.json`, analysis repository 3d6376a):

| Record | Opening reserves | Taken on and covered | Severity before | Severity after |
|---|---|---|---|---|
| 1856/2024 | 600.368m | 96.61m | 23.47% | 20.21% |
| 1884/2021 | 73.709m | 839.787m | -27.27% | -2.20% |
| 2008/2015 | 308.138m | 85.227m | -2.66% | -2.08% |
| 2008/2016 | 327.957m | 148.677m | -3.93% | -2.71% |
| 2008/2018 | 369.552m | 1251.064m | 0.00% | 0.00% |
| 2008/2019 | 1331.49m | 701.118m | 1.05% | 0.69% |
| 2008/2023 | 1186.259m | 234.962m | 6.68% | 5.57% |
| 2488/2019 | 956.51m | 143.759m | -0.31% | -0.27% |
| 3268/2020 | 71.068m | 20.66m | 5.93% | 4.60% |
| 3500/2019 | 259.79m | 552.752m | 10.18% | 3.25% |
| 3500/2021 | 770.428m | 1357.5m | 14.16% | 5.13% |
| 3500/2022 | 2615.345m | 1339.7m | -11.16% | -7.38% |
| 3500/2023 | 2962.436m | 2840.7m | -1.61% | -0.82% |
| 4444/2018 | 1547.219m | 277.329m | 5.72% | 4.86% |
| 4444/2023 | 2367.884m | 313.953m | 2.04% | 1.80% |

Not adjusted: 23 records with no transfer the adopted figure covers; 9 whose covered
transfer is under 5% of the opening reserves; and 1084/2014 (the two readings do not both find a covered transfer), 1110/2022 (the filing states no amount for the covered transfer), 609/2014 (the filing states no amount for the covered transfer). Later first readings of an adjusted record find its
opening reserves outside the 2% check, as they must: 1856/2024 (brief 696.978, the filing's 1 January 600.368, p101; error-rate-verdicts-tail.json).

2003/2018 is one of the records with no covered transfer: both readings find Syndicate 1209's reinsurance to close
entering its triangle's step without restatement, which point 2 leaves to the sixth amendment. Under
implementation note 4 it was read once more, on that amendment's question (`error-rate-briefs-ninth-sixth-2003.json`,
`reader-prompt-ninth-sixth-2003.txt`, `error-rate-verdicts-ninth-sixth-2003.json`). That reading and the editor's
both find the take-on dominating the figure, and on the owner's decision of 14 September 2026 the record is
excluded as a take-on (`data/takeon_not_development.json`, analysis repository 3d6376a).

### The effect on Vignette 1's VaR99.5 (`propagation/`)

Computed on analysis commit 2d0df44. The repairs moved VaR99.5 from 0.3433 to
0.3142 (-8.5%). For errors not yet found, 2000 replicates (seed
20260915) drew an error rate from the posterior Beta(8.5, 154.5), a count among the
415 working-sample records no sample or census read, and changed each chosen record's severity under
three error models. The materiality line is a relative change of 5.0%.

| Error model | Relative change, rate from the posterior: median [2.5%, 97.5%] | P(abs > 5%) | Rate at the posterior's 97.5% point (0.091): median [2.5%, 97.5%] | P(abs > 5%) |
|---|---|---|---|---|
| sign | 0.0% [0.0%, 0.0%] | 0.000 | 0.0% [0.0%, 0.0%] | 0.000 |
| replace | 0.0% [0.0%, 17.4%] | 0.417 | 8.9% [0.0%, 27.7%] | 0.603 |
| shift | 17.4% [0.0%, 41.0%] | 0.886 | 24.7% [7.3%, 55.9%] | 0.979 |

`error-rate-propagation-SMOKE-refit1-placeholder-rate.json` is a smoke run of the same script on the refit before
the repairs, with placeholder rate inputs, made to test the script before the refit after the repairs existed. No
estimate uses it.

## Who read the filings

Every reading was made by Claude, reading the filing page by page under the protocol. This is a use of AI in
building the evidence, and the manuscript declares it as one. No reading was made by a person.

- First readers: Claude Code agents running Claude Opus 5 (`claude-opus-5`), one per batch. The first sample
  was read in six batches of 10 records, the second sample's fresh records in batches of 10, 10, 10, 10 and 4, the third sample's in batches of 10, 10, 10, 10, 10, 10, 10, 10, 10, 10 and 6, the eighth
  census's in batches of 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5 and 3 (and batch 12b of two), and the take-on base census's in batches of 5, 5, 5, 5 and 2, with one further reader for
  2003/2018 (implementation note 4).
  The censuses and the records found in passing were read the same way. Each reader was given the protocol's
  definitions, a brief of what the loader adopted, an adjudication pack and a page tool
  (`scripts/filing_pages.py`). The instruction each was given is kept as `reader-prompt-*.txt`.
- Second reader: the Claude Code session that ran the study (Claude Opus 5). It read the protocol's
  verification set: every clarified or first-reader error, every verdict the clarification changed, every
  undeterminable, every triangle-sourced figure without a recomputation, every figure whose source is not
  its route field, and a seeded random fifth of the remaining corrects. It read every record of each census and
  every record found in passing.

## Files

- `first-sample/`: the draw (`error-rate-sample.json`: analysis run 2a2cd765-a4c1-580d-87ed-318909431a20, seed 42), the briefs, reader
  prompts and first readings per batch, the merged and clarified verdicts, the verification set, the second
  readings and the result. `packs/` holds the evidence pack each reader was given.
- `second-sample/`: the same for the draw from analysis run 59da1151-3c18-5781-b5e0-bd47eb2cd2d3, with `error-rate-carry-over.json` (which
  readings carried over, decided before any new reading, and why) and the merge's check and log.
- `tail/`: the tail stratum's definition and stems (`error-rate-tail.json`, with the calibration's and donor
  pool's hashes), its briefs, carry-over decision, readings, verification and result, and `packs/` for the
  records read afresh.
- `census/`, `takeon-census/`, `found-in-passing/`: each list of records, its briefs, reader prompts, first
  readings, second readings and result, with `packs/`.
- `repairs/`, `third-sample/`, `propagation/`: as described above.
- `third-sample/findings/` and `eighth-census/`: as described above; `eighth-census/packs/` holds the census's
  evidence packs.
- `ninth-census/`: the take-on base census, its dry runs and probe, briefs, carry-over skeleton and decisions,
  reader prompts, first and second readings, result and draft, and implementation note 4's brief, prompt and
  reading of 2003/2018; `ninth-census/packs/` holds its evidence packs.
- `superseded/`: the draw of 13 September from a working sample of 695 that a loader defect had made wrong
  (PLAN R205). It was withdrawn before any record was read (second amendment), and no estimate uses it. The
  draw script first written for the protocol is kept beside it: it was never run (amendment, point 2).
- `checks/`: `compare_working_sample.py` (R208: analysis run 4877d6b1-bbee-502e-8918-5ffa61c6122e against its successor) and
  `compare_r209_r210.py` with `compare-r209-r210.txt` (R209 and R210: analysis run dc0caa61-b805-501c-8bf3-a466163a1f24 against run 59da1151-3c18-5781-b5e0-bd47eb2cd2d3), each
  with the prediction it tests and the working sample it started from.
- `scripts/`: the scripts as they ran. Their paths name the working copies they ran in. The adjudication pack
  generator is `scripts/adjudication_pack.py` in the extraction repository.
- `MANIFEST.json`: every file with its SHA-256.
- `.gitattributes`: marks every file here `-text`, so git converts no line endings and a checkout on any platform
  holds the bytes MANIFEST.json hashes.
