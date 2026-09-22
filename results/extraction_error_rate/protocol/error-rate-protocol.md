# Extraction error rate: protocol, fixed before any record is adjudicated

Written 11 September 2026, before the sample was drawn and before any verdict was
recorded. The point of writing it first is that the definition of an error cannot then be
chosen to suit the result.

## Why this exists

The paper's sample is produced by an LLM-assisted extraction whose error rate has never
been measured. The external review of 11 September 2026 hand-checked the ten largest
transferred donors and found three materially wrong and one imprecise; a fifth error
(780/2018) was found in this round by adjudicating the largest movements. Those five were
found by looking where errors do the most damage, and the review said plainly that such a
targeted sample "cannot establish a corpus-wide error rate". Five known errors and no
denominator is not a statement a referee can weigh.

## What is being estimated

**θ, the probability that a record drawn at random from the working sample carries a
materially wrong adopted prior-year development figure**, where "materially wrong" is
defined below and judged against the syndicate's own filing.

θ is a property of the *shipped* extraction. The study is therefore run on the corpus as
it stands after the round-56 rule corrections and the prompt-2.12 re-extraction, not on
the corpus the review read. Measuring the superseded pipeline would answer a question
nobody is asking.

## Sampling

1. **Primary (unbiased) sample.** A simple random sample **without replacement of n = 60**
   records drawn from the working sample — the records that enter the model, not the
   corpus — using `numpy.random.default_rng(42)`, the seed used throughout this project.
   The drawn stems are written to `error-rate-sample.json` **before** any adjudication and
   are not changed afterwards. A record that turns out to be hard to adjudicate is *not*
   replaced; it is recorded as undeterminable (see below).

2. **Tail stratum, reported separately.** The **20 largest transferred severities**. This
   is where an error moves the headline, and it is deliberately *not* pooled with the
   primary sample: pooling a purposive stratum into a random one would bias θ upward. It
   supports a separate statement about the tail, with its own denominator.

Two samples, two numbers, never added together.

## What is checked, and what counts as an error

For each sampled record, the adopted figure — the one the loader would use — is compared
against what the syndicate's own filing settles.

A record is scored **error** when any of these holds:

- the adopted `prior_year_development_gbp_m` differs from the filing's own figure by more
  than `max(0.5, 0.05 × |adopted|)` in the report's currency and millions;
- the adopted figure has the opposite sign to the filing's;
- the adopted figure's scope is wrong in a way the filing makes plain — it includes the
  two most recent underwriting years, or it is a cohort's cumulative total, or it is net
  where the record claims gross.

A record is scored **correct** when the filing settles the figure and it agrees within
that tolerance.

A record is scored **undeterminable** when the filing does not settle the question from
the pages available — for example when the only development table is a loss-ratio grid
with no underwriting-year premiums. Undeterminable records are reported as their own
count and are **excluded from the denominator**, because θ is about records the filing
can adjudicate. That exclusion is itself a limitation and is reported as one.

The opening reserves are checked at the same time, against a 2% tolerance, and reported
separately. An error there matters because severity is the ratio.

Each verdict is recorded with the page and the arithmetic that settles it, in
`error-rate-verdicts.json`, so any reader can disagree with a specific call rather than
with the total.

## Estimator

A Beta-Binomial with the Jeffreys prior Beta(½, ½): posterior Beta(½ + e, ½ + n − e) for
e errors in n adjudicable records. Reported as the posterior mean and a 95% **credible
interval**, in keeping with the paper's Bayesian idiom. A frequentist interval is not
reported, because the paper does not report them elsewhere and two intervals for one
quantity invite exactly the confusion the review has been correcting.

The tail stratum is reported the same way, with its own n.

## What the result cannot say

- It is a rate for **this** extraction, after the round-56 corrections. It says nothing
  about the corpus the review read.
- n = 60 is small. A posterior mean near a few per cent will carry an interval several
  times its own width, and the write-up must say so rather than quoting the mean alone.
- It measures the *adopted figure*, not every field in the record.
- It cannot detect an error that the filing itself presents ambiguously and that I
  therefore read the same wrong way the extraction did. That is a correlated-error
  limitation with no fix available from inside this design, and it belongs in the
  limitations.
- A record scored correct is correct *on the pages the extraction cited*. A figure taken
  from the right-looking table on the wrong page of a companion syndicate's section would
  be caught only if the page binding is checked too — so the page binding is checked.

## Pre-registered, in this order

1. Finish the prompt-2.12 re-extraction.
2. Rebuild the working sample.
3. Draw the sample with seed 42 and write it out.
4. Adjudicate, recording evidence per record.
5. Compute the posterior and write it up.

The sample file is written at step 3 and is not redrawn. If the extraction changes again
after step 3, the study is re-run from step 1 and both results are reported.

## Amendment, 13 September 2026, written before the sample was drawn

No record had been drawn or adjudicated when this was written.

1. **Which extraction.** Step 1 named the prompt-2.12 re-extraction. Version 2.12 was
   withdrawn, the corpus was re-extracted under 2.13, and after R193 (the revert of R164) it
   was replayed offline from the committed caches. The study runs on that corpus and on the
   working sample rebuilt from it on 13 September 2026.
2. **Population.** The draw script first written for this protocol rebuilt eligibility from
   the extraction records and did not apply the loader's gross-basis rule, so its population
   was not the working sample this protocol names. It was never run. The population is now
   read from the rebuilt working sample itself -- the observations of
   `model/exposure_results.json` that `adopted_model.load_sample` retains -- with that file's
   run identifier and SHA-256 recorded in the sample file.
3. **Tail stratum.** The largest transferred severities depend on the fitted operator, and
   the operator is refitted on the rebuilt sample. The tail is therefore computed after the
   refit, mechanically: the vignette-1 transfer of every donor, as `src/donor_review.py`
   ranks its top adverse transferred donors, under the refit's posterior-mean parameters; its
   20 stems are written to their own file before any tail record is adjudicated. The primary
   sample does not depend on the fit and is drawn now.

Nothing else changes: n = 60, seed 42, the definition of an error, the tolerances, the
Jeffreys-prior estimator, and the rule that the two strata are never pooled.

## Second amendment, 13 September 2026, before any record was adjudicated

The primary sample drawn at 11:35 came from a working sample that a loader defect had wrong. The
loader decided a USD record's basis after converting its figure to GBP (PLAN R205), so six net or
unstated figures were inside the working sample and 18 gross triangle figures were outside it; the
corrected sample holds 707 records where the first held 695. One of the 60 records drawn,
1183/2020, is among the six.

No record of that draw was adjudicated and no verdict was recorded. One pack, 1183/2020's, was
opened to check the pack's format. The first draw is kept, with its packs, as
`error-rate-sample-superseded-1.json` and `packs-error-rate-superseded-1/`, and is not used for
any estimate. The sample is drawn again by the same script, with the same n and seed, from the
corrected working sample. The run identifier the first draw failed to record (it read a key the
results file does not have) is now read from `analysis_run_id`.

## Clarification, 13 September 2026, after the first readings of batch 1 and before any second reading

This clarification was prompted by a first reading, and it says so: batch 1's reader scored
1218/2024 an error because the filing's stated "Change in estimates of prior year provisions"
(-18.337m) differs from the adopted figure (-13.922m), which came from the filing's gross claims
development triangle.

The protocol compares the adopted figure with "the filing's own figure" and does not say which
figure that is when a filing prints both a stated prior-year movement and a gross development
triangle. The instruction given to the first readers filled the gap by preferring the stated
movement. That contradicts the protocol's own error (c) and the manuscript's definition: the
numerator is the change in the gross estimate over underwriting years up to t-2, which is exactly
what a triangle route computes, while a movement stated for "prior years" can also include year
t-1 (the loader records this distinction on every observation as the cohort scope, and the
manuscript reports it). A triangle-routed figure that differs from a stated movement by year t-1's
development is not wrong in the paper's own terms.

So, for all 60 records alike:

1. A figure whose route is the triangle is checked against the triangle recomputed from the
   filing's printed table over underwriting years up to t-2: the right table, the right basis,
   the cells read correctly.
2. A figure from any other route is checked against the movement the filing states.
3. Where a filing prints both and the two differ by more than the tolerance, the difference is
   recorded for that record; it is not itself an error.

The second reader applies this to every record whose adopted figure is triangle-routed, not only
to those a first reader scored as errors, so that no verdict is re-examined because of its
outcome.

Refinement, written while preparing the second reading of 1414/2024 and before any verdict on it
was recorded: a record's route field is not always its figure's source. For 30 records the pipeline
computed a triangle, found that it disagreed in sign with the filing's provisions note, adopted the
note's figure, and left the route field reading "rag_triangle"; each is listed, confirmed from its
own replay log, in `pdf_extraction/audit/triangle_overruled_by_sign_veto.json` (PLAN R197). For
those the figure's source is the provisions note, so rule 2 applies to them and rule 1 does not.
1414/2024 is one: its triangle gives +86.7m, the adopted -15.6m is the note's "Change in estimates of
prior year provisions" (15,592) $000, and scoring it against the triangle would call a correct
figure a sign error.

Refinement 2, written after batch 4's first readings and before any second reading under it (prompted
by 3000/2024, which a first reader scored an error because the note's prior-year line includes the
2023 underwriting year): error (c)'s "it includes the two most recent underwriting years" is read
against the scope the record itself claims, which the loader records on every observation.

- A figure recorded as cohort-enforced (a triangle over underwriting years up to t-2) is wrong in
  scope if it includes year t-1 or year t.
- A figure recorded as cohort-disclosed (a movement the filing states for "prior years") may include
  year t-1 by definition: the manuscript admits such figures and reports how many there are. It is
  wrong in scope only if it includes the current year t, or if the filing makes plain that it is not
  a prior-year movement at all.

A faithfully read disclosed figure is therefore not an extraction error because a prior-year line
includes year t-1. Where a first reader found that year t-1 dominates such a line, it is recorded
with the record. The rate is reported under this clarification, and the rate under the first readers'
instruction is reported beside it.

Refinement 3, written after all six batches' first readings, before the verdicts were merged and
before any second reading under it. First readings prompted it. The readers of 1994/2024 and
4020/2023 recorded triangle recomputations of +14.4m and +0.2m against adopted figures of +22.3m and
-36.4m. 4444/2022's reader noted that its route field is empty although its figure came from a
triangle. Refinement 1's principle, that a record's route field is not always its figure's source, is
applied in both directions and read from the pipeline's own record:

- A route that reads "rag_triangle" is not a triangle when the RAG step's figure came from another
  method. The driver writes that route whenever its RAG step returns a figure, whatever the method: the
  provisions note, provisions text or the narrative parsers. The method is read from the record's own
  replay log. For both sampled records the log prints "No triangle, but found 1 reserve text page(s)"
  and "Using provisions PYD as fallback", the route carries no triangle (the driver writes a triangle's
  type, units and page only when one came back), and the adopted figure is the provisions note's.
  Rule 2 applies. In the sample, the routes whose log prints another method are exactly the routes
  that carry no triangle. Across the corpus, 3 routes carry a triangle although their log prints
  another method. None is sampled, and the merge refuses to run if a sampled record breaks the
  correspondence.
- A figure whose route field is empty, but whose notes carry the pipeline's code-override annotation
  with a computed value equal to the adopted figure, is a triangle's. Rule 1 applies. 4444/2022 is the
  only such record in the sample ("[CODE OVERRIDE: ... code computed 435.491 from triangle ..."). The
  loader's cohort label is not used as the evidence. The loader also counts as a triangle the RAG
  annotation that the driver writes over a provisions fallback, and six working-sample records carry
  that label without any triangle.

Under rule 1, both readings this moves to rule 2 would be errors. Under rule 2, both first readers
scored them correct. The result says so. The refinement changes no verdict under the first readers'
instruction. Every record whose figure's source is not its route field (refinements 1 and 3) is
second-read, whatever its first verdict. The mislabelled route is itself a pipeline defect, and it is
measured and recorded separately.

## Third amendment, 13 September 2026, after the first readings and before scoring: the working sample changed after the draw

R208 (PLAN: a figure's route names what produced it) changed provenance fields on 58 extraction
records after the primary sample was drawn. It changed no adopted figure. The working sample was
rebuilt, and compare_working_sample.py checked the result against the prediction written before the
replay (analysis run 4877d6b1-bbee-502e-8918-5ffa61c6122e to dc0caa61-b805-501c-8bf3-a466163a1f24).
One record left, 1947/2019. Its basis is now decided by gpt-5-mini's declaration (net), where before
it rested on a two-year triangle that did not produce its figure. No record entered. Severity,
opening reserves and HHI are identical on the other 706. 1947/2019 is not among the 60 sampled
records.

The protocol says a changed extraction re-runs the study from step 1. It is not re-run, for this
reason, stated before any scoring. Take a simple random sample of 60 from 707 without replacement,
condition on its not containing one given record, and it is a simple random sample of 60 from the
other 706. The excluded record was fixed by the pipeline, not by the draw. So the drawn sample is a
simple random sample of the rebuilt working sample. No sampled record's adopted figure changed, so no
verdict depends on which extraction it was read from. For five sampled records the route label
changed (1414/2024, 1994/2024, 3000/2024, 382/2024 and 4020/2023 now read rag_provisions). Refinements
1 and 3 already check each of them against the stated movement, so the check applied is the same. A
fresh draw from 706 with seed 42 would pick other records only because the population is indexed
differently.

The rate is reported for the rebuilt working sample of 706, with this amendment beside it.

A later change to the extraction is handled by the same reasoning. The final sentence below was
revised on 13 September 2026, before any scoring; the first version re-ran the study from step 1
whenever a sampled figure changed. That redraw adds nothing statistically. The drawn sample stays a
simple random sample of the changed population provided no record enters it, and a verdict depends
only on the adopted figure and the filing. The rule is therefore this:
- if a change adds a record to the working sample, the study is re-run from step 1;
- if a change alters sampled records' adopted figures, only those records are adjudicated again
  from their filings, with a first and a second reading as before;
- the rate is reported for the extraction before and after the change.

## Fourth amendment, 13 September 2026, after the first result was scored and before a new sample is drawn: a record entered the working sample

Two PLAN goals changed the extraction and the loader after the first result was scored.

- R209 reads an aggregated older cohort ("2010 and prior") as a triangle's oldest column when the
  column runs by calendar year. A year that a split label had taken returns to its own column. Every
  data-carrying record was replayed offline from the committed caches. Each of the 58 stored
  triangles that changed is reproduced from its committed table by the parser before R209 and by
  R209, and 35 adopted figures moved. A correction for a column printed by development age changed no
  figure.
- R210 reads basis wordings the rule had missed. Figures their own models called net, or of unstated
  basis, leave the gross sample.

The working sample was rebuilt (analysis run dc0caa61-b805-501c-8bf3-a466163a1f24 to
59da1151-3c18-5781-b5e0-bd47eb2cd2d3) and checked against predictions written before the rebuild
(compare_r209_r210.py). It holds 698 records where it held 706:
- nine left, exactly the nine R210 predicted: 1919/2014, 2121/2014, 2623/2014, 2623/2020, 3010/2017,
  3623/2014, 3623/2020, 382/2014 and 623/2015;
- one entered: 2121/2017, whose figure R209 now takes from its gross triangle in place of a model's
  reading;
- 32 severities moved, each where R209 moved the figure. Opening reserves and HHI are unchanged.

Among the 60 sampled records, 3623/2020 left, and four figures moved: 218/2017, 218/2020, 4020/2016
and 4020/2017.

The third amendment's rule decides this, by its first case: a record entered the working sample, so
the study is re-run from step 1. The drawn sample is not a simple random sample of the new
population, because 2121/2017 had no chance of being drawn.

1. The first result stands as the rate for the extraction before R209 and R210: 60 records drawn
   from 706 (`error-rate-sample.json`, `error-rate-result.json`). It is reported beside the new
   result, as the protocol requires.
2. A new primary sample is drawn from the rebuilt working sample of 698 by the first draw's method:
   the observations `adopted_model.load_sample` retains, as stems sorted lexicographically, n = 60,
   `numpy.random.default_rng(42)`. It is written to `error-rate-sample-after.json` before any of its
   records is read. The first sample's file is not changed.
3. A verdict depends only on the adopted figure and the filing (third amendment). So a record that
   both samples hold keeps its readings (first, clarified and second), provided nothing its verdict
   was read against has changed: the adopted figure, the opening reserves, the figure's source
   (triangle or stated, as `score_error_rate.py` reads it), the basis and the cohort scope the loader
   records. The route label is not compared: R208 renamed five sampled routes without changing their
   source, and the third amendment explains why that changes no check. This is decided for every such
   record before any new reading, whatever its verdict.
4. Every other record in the new sample is read afresh. It gets a first reading from the same kind of
   brief, pack and page tool, under the first readers' instruction, with a triangle recomputation
   recorded for every triangle-routed figure. The clarification and refinements 1 to 3 are applied at
   the merge exactly as before.
5. The second reader verifies by the same rule over all 60. That rule is `score_error_rate.py`'s
   verification set: every clarified or first-reader error, every verdict the clarification changed,
   every undeterminable, every triangle-sourced figure without a recomputation, every figure whose
   source is not its route field, and a seeded random fifth of the remaining corrects. A carried-over
   second reading stands. A carried-over record that the rule selects and that has no second reading
   is read now.
6. The tail stratum is not affected. It is computed after the refit, from the rebuilt working sample.

No other part of the protocol changes.

## Fifth amendment, 13 September 2026, 19:29-19:33, after both results were scored and before any record below is read, any repair is made or any new record is drawn: the two error mechanisms, their repair, a second random draw, and the errors' effect on the headline

The second sample's two errors are mechanisms, not one-off misreadings. On 13 September 2026 the owner asked
for both mechanisms to be counted and repaired, for a larger random sample, and for the errors' effect on
Vignette 1's VaR to be measured. This amendment fixes how, before any of it is done.

1. Census of the two mechanisms. It is purposive, so it is reported on its own and never pooled with a random
   sample.
   - Replay stopped: every working-sample record that `pdf_extraction/audit/offline_unservable.json` at
     extraction commit 40eb31aa lists as not servable offline now (its `stems`: this replay's unservable reports
     and the reports with no usable cache). One of the 698 is listed, 2008/2021. (Correction, 19:33-19:35, before any
     census record was read: the first version of this point listed seven records. The six others, 1301/2016,
     1969/2015, 2988/2021, 2988/2022, 2988/2023 and 623/2016, come from the file's round-55 measurement, and the
     file records each of them as served in the round-56 replay.)
   - Aggregated older cohort omitted: every working-sample record whose adopted figure comes from a triangle
     that leaves out an aggregated older cohort the filing prints. The round-56 check
     (`cohort-manifestations.json`) lists five working-sample records whose adopted figure equals a cohort
     table's triangle without the cohort: 2007/2015 and 3624/2015, where the models' triangle decides, and
     4242/2021, 4242/2022 and 4242/2023, where the deterministic triangle decides and the check could not
     compute the figure with the cohort. What that check covered is recorded with the census, and a record it
     missed is added if found. (Correction, 19:35, before any census record was read: the first version named
     only the first two.)
   Each record gets a first and a second reading, from the same kind of brief, pack and page tool, under the
   same instruction, clarification and refinements. 2008/2021 and 3624/2015 keep their second-sample readings
   (fourth amendment, point 3).
2. Repair. Each error the census confirms is repaired at its mechanism, and so are the second sample's two
   errors.
   - A record whose replay stopped is re-extracted with the calls its caches lack, made under the pipeline's
     cost guards and cached. The owner authorised the paid calls for these repairs, Azure included, on 13
     September 2026. 2008/2021's missing response is a gemini-2.5-flash page-triangle call (page 53). No prompt
     changes, and no other record's cache is touched.
   - An omitted aggregated cohort is repaired in the parser or the estimator where the filing's printed table
     supports it. Otherwise the record is re-extracted.
   A repair that could change another record is first run on fixed inputs, and every decision it changes is
   read. Every record a repair changes is read again from its filing, with a first and a second reading.
3. A second random draw. After the repairs the working sample is rebuilt. Let A be the records in both the
   rebuilt working sample and the second sample's population of 698, and E the records that entered it.
   - 110 records are drawn from A without the 60 already drawn, by the earlier draws' method (the observations
     `adopted_model.load_sample` retains, as stems sorted lexicographically, `numpy.random.default_rng(20260914)`),
     and written to `error-rate-sample-third.json` before any is read. With the second sample's 60, less any
     that left, they are a simple random sample of A (third amendment).
   - Every record of E is read, as a census stratum. For these repairs this replaces the third amendment's first
     case: a fresh draw from step 1 adds nothing that reading every entrant does not, and E is known before any
     of its records is read.
   - A second-sample record whose adopted figure a repair changed is read again from its filing (third
     amendment, second case).
   - The rate for the repaired extraction is the Jeffreys posterior over the sampled records of A, with E's
     errors counted in full and weighted by E's share of the working sample. The 110 alone are reported beside
     it.
   The verification set, the clarification and refinements 1 to 3 apply unchanged.
4. The tail stratum is computed after the final refit, from the rebuilt working sample, as the fourth amendment
   says.
5. The errors' effect on the headline, fixed here before it is computed.
   - The repaired errors: Vignette 1's VaR99.5 is reported from the refit before the repairs and from the refit
     after them. The two refits differ only by the repaired records.
   - Errors not yet found: on the refit after the repairs, 2,000 replicates with `numpy.random.default_rng(20260915)`.
     Each replicate draws an error rate p from the repaired extraction's posterior; a count K from Binomial(N, p),
     where N is the working-sample records read in no sample or census (each treated as adjudicable, the
     conservative reading of the undeterminable share); and K of those records at random. Each chosen record's
     severity is changed under three error models, reported separately: its sign reversed; replaced by a
     severity drawn at random from the working sample; and shifted by a shift drawn from the errors confirmed
     before repair (adopted minus filing figure, over the record's opening reserves), with a random sign. The
     transferred pool and its VaR99.5 are recomputed at the posterior-mean parameters, and the change from the
     unperturbed VaR99.5 is recorded.
   - Reported for each error model: the median and the 2.5% and 97.5% points of the change and of the relative
     change; the probability that the relative change exceeds 5% in absolute value; and the same with p fixed
     at the posterior's 97.5% point.
   - A relative change of 5% is the materiality line, the tolerance the protocol's own error definition uses.
   The script and its output are committed with the study.

The times in this amendment are bounded by the file system's times: the amendment's script was written at 19:29 and the first correction's at 19:33, the second correction left the protocol at 19:35:53, and the census file was written at 19:35:55. The first versions carried times I had estimated (19:45, 19:58 and 20:05); they were corrected at 19:46.

No other part of the protocol changes.

## Sixth amendment, 13 September 2026, 20:08, before any record below is read: the take-on mechanism

The fifth amendment's replay repair was made. 2008/2021's missing gemini-2.5-flash page-image call (page 53) was
made under the cost guards and cached, and the record now replays offline. Its adopted figure did not change: the
page-image triangle also fails the pipeline's structure check, so the provisions note's "change in prior year
provisions" of +383.9m is adopted again. The second sample's first reading shows that figure to be the whole 2021
gross claims charge, the first-year recognition of a loss portfolio transfer written into the report year's year of
account. So the error's mechanism is not the stopped replay. It is a stated movement adopted as development in a year
the syndicate took on another's liabilities, where the movement is the take-on.

On 13 September 2026 the owner decided that a record whose filing shows its adopted figure to be the take-on itself
leaves the working sample, because it is not development.

1. Census of the take-on mechanism. It is purposive, reported on its own and never pooled with a random sample: every
   working-sample record in the RITC regime (its recorded sources: an accepted RITC or a confirmed inward transfer)
   whose adopted figure is a stated movement (score_error_rate.figure_source on its brief, with 2008/2021 read from
   its record after the replay repair). The records are computed from the refit's exposure_results.json and the
   records, and written to error-rate-census-takeon.json before any is read.
2. Each record gets a first and a second reading from the same brief, pack and page tool, under the same instruction
   and one added question: is the adopted figure the year's take-on (the RITC premium or the reserves transferred in,
   or a charge dominated by them), or the change in the estimate for earlier years? The reading records the filing's
   evidence. 2008/2021 keeps its first reading, which answers the question, and gets a second reading on it.
3. A record whose two readings both find the adopted figure to be the take-on leaves the working sample, through a
   register in the extraction repository that the analysis loader reads, with the page and quote. A record that the
   readings do not both find so stays. A record that leaves the second sample's population is dropped from A, and
   the drawn sample is conditioned on not containing it (third amendment).
4. The fifth amendment's random draw (point 3) is taken after this repair, from the working sample it leaves.

No other part of the protocol changes.

## Seventh amendment, 13 September 2026, 20:35, before any record below is read: confirmed errors the samples left in the data, records found in passing, and repair by a confirmed figure

Two facts came to light after the sixth amendment. First, the first sample confirmed seven errors, and the fourth
amendment redrew the sample without repairing them. Three are still in the working sample with the same adopted
figure (persisting-first-sample-errors.json): 3624/2015, now repaired (fifth amendment), 2010/2019 (+132.679m against
the filing's -18.659m) and 4444/2022 (+435.491m against +34.9m). Second, the read-only mapping of the extraction code
named four working-sample records whose figures it could not reconcile with their filings: 1225/2022, 623/2014,
623/2022 and 1206/2014.

On 13 September 2026 the owner decided that a confirmed error whose correct figure the pipeline cannot produce is
repaired by the figure two readings of the filing confirm, through a register the analysis reads, each hand correction
disclosed. The record stays in the working sample.

1. 2010/2019 and 4444/2022 are confirmed errors (the first sample's first and second readings). Their confirmed figures
   are the second readings' filing figures. They are repaired so.
2. 1225/2022, 623/2014, 623/2022 and 1206/2014 are each read twice, as a census record is. They are reported apart,
   never pooled with a random sample, and never counted as a mechanism's census. A record whose two readings find an
   error and agree on the filing's figure is repaired by that figure; any other record is left as it is, with its
   readings recorded.
3. A repair by a confirmed figure changes the record's adopted figure, so the record is read again only if a random
   sample holds it (third amendment, second case). None of the six is in the second sample.
4. The fifth amendment's random draw (point 3) is taken after these repairs, from the working sample they leave.
5. (Added 20:39, before the record it concerns was second-read.) The take-on census's first readings found one
   error that is not a take-on: 2008/2019 adopts +249.0m where the filing's gross change in prior year provisions is
   +14.053m. An error that a census's two readings confirm, and whose correct figure the pipeline cannot produce, is
   repaired by the confirmed figure under the owner's decision above, like the records of points 1 and 2.

No other part of the protocol changes.

## Implementation note, 13 September 2026, before the third sample is drawn (written 21:45)

The protocol compares "the adopted figure -- the one the loader would use" with the filing. Since the seventh amendment the loader replaces two records' figures with confirmed ones (4444/2022 and 2008/2019, data/pyd_confirmed_figures.json). The third sample's briefs therefore apply that register as the loader does (make_adjudication_briefs_third.py, through run_analysis.apply_confirmed_figure), so a drawn record carries the figure the model uses. A confirmed figure is checked by its kind: one read from a printed triangle as a triangle figure, one the filing states as a stated figure (score_error_rate.figure_source). The records the extraction repairs (3624/2015, 1225/2022, 2010/2019) carry their figures in the records themselves. No part of the protocol changes.

## Implementation note 2, 13 September 2026 (written 21:51), before any reading of the third sample

The first briefs for the records read after the repairs were built with a defect: make_adjudication_briefs_third.py took "still in the working sample" from every parsed observation, so 2008/2021, which the take-on register keeps in the corpus but not in the working sample, was briefed as a repaired record to be read again. The script now takes the working sample from adopted_model.load_sample, the source the draw used, and the briefs, the carry-over decisions and the batches were rebuilt. The first files are kept in superseded-before-reading-215105. No reading of the third sample had begun (no first-reading file existed). The draw itself is unchanged.

## Eighth amendment, 14 September 2026, 08:39, after the third result was scored and before any record below is read or any repair below is made: the third sample's errors, their families, and their repair

The third sample was scored on 13 September 2026 (error-rate-result-third.json). A, the 169 sampled records, holds
8 errors, 154 correct and 7 undeterminable; the working sample's rate is 5.2% (95% credible interval
2.4% to 9.1%). The eight errors are mechanisms the earlier repairs did not reach:
- Syndicate 382's movement tables, differenced as if they held cumulative estimates: 382/2015 (adopted -15.848m, filing
  +2.626m), 382/2016 (-50.211m, -14.328m), 382/2018 (+13.51m, +24.988m), 382/2019 (+173.514m, +12.549m);
- a provisions note whose prior-year line holds the current year of account, as in 2010/2019: 2010/2018 (+179.777m,
  -15.755m) and 3010/2019 (+25.459m, -1.925m);
- a net table taken for gross: 1880/2014 (-13.6m; the filing prints no gross table and states no gross movement);
- a loss portfolio transfer's premium taken for development: 1980/2018 (+30.4m, the class's written premium in the
  syndicate's first year; nothing can replace it).
Both readings of each agree on the error, and where the filing gives a figure they agree on it exactly. The
opening-reserve check, which the protocol reports apart, finds one error in 250 first readings: 2003/2018 adopts the
reinsurers' share at 1 January 2018 (1,659.705m) where gross claims outstanding is 5,344.064m (p44; both readings).
Both readings of 1274/2018 find its triangle figure (+294.748m) about 93% the Motor RITC it accepted on 1 January 2018
(317.39m gross). The second reading of 623/2014, found in passing, shows its -17.3 to be a sum of loss-ratio points a
model stored as millions; the first reading scored it undeterminable.

On 14 September 2026 the owner decided: repair these errors and count their mechanisms in a census, then refit; exclude
1274/2018, whose figure is dominated by a take-on; replace 2003/2018's opening reserves with the confirmed figure; and
exclude 623/2014, whose figure is not an amount.

1. The rate. The working sample's rate stays the one the third sample measured. It was measured before the repairs
   below, so for the repaired extraction it is conservative. The sample is not re-scored after its errors are repaired
   (PLAN R213: that would be the incomplete solution).
2. Repairs, through registers the analysis loader reads, each entry with its pages, a quote and both readings. No
   extraction record changes and no paid call is made.
   - Confirmed figures (data/pyd_confirmed_figures.json), each the printed gross triangle over the underwriting years up
     to t-2: 382/2015 +2.626m, 382/2016 -14.328m, 382/2018 +24.988m, 382/2019 +12.549m, 2010/2018 -15.755m, 3010/2019
     -1.925m.
   - A basis the readings established. 1880/2014 is registered with the net table's figure (-13.6m) and a net basis, so
     it is recorded and excluded as a net-basis record. 623/2014 is registered with an unknown basis and no figure, so
     it is recorded and excluded as an unknown-basis record; the loader accepts an entry without a figure only for a net
     or unknown basis (implementation, test-first: src/test_confirmed_openings_and_bases.py).
   - Take-ons (data/takeon_not_development.json): 1274/2018 (the Motor RITC, 317.39m gross) and 1980/2018 (the
     portfolio transferred at 1 January 2018, 163.213m).
   - Opening reserves (data/opening_reserves_confirmed.json, a new register the loader applies before the FX conversion,
     recomputing the percentage; implementation, test-first): 2003/2018 5,344.064m.
3. A census of the mechanisms, purposive, reported on its own and never pooled with a random sample. Its records are
   computed by make_census_eighth.py from refit 2's outputs (analysis 8addc04, run a5d20430) and the records, and written
   to error-rate-census-eighth.json before any is read. Six parts; the script's docstring states each rule, and the
   census file copies it:
   - movement: every working-sample record of Syndicate 382, and every stored triangle shaped like a movement table;
   - transposed: every working-sample record of Syndicates 2010 and 3010, and every record whose adopted figure lies
     within 5% of the report year's first estimate in its own triangle;
   - net_table: every triangle figure whose triangle page names a net table and has no gross heading;
   - provisions_row: every figure the provisions route read from a row that is not a movement line bound to the report
     year;
   - opening: every record whose opening reserves are under half or over twice both neighbouring years' where those
     two agree within a factor of two;
   - takeon_triangle: every triangle figure whose filing records a transfer into the syndicate in the report year (the
     RITC scan's decision, an inward passage naming another syndicate or a portfolio transfer, or an RITC roll-forward
     row).
   Each part refuses unless its rule flags the records that define it. The records already decided (the eight errors,
   1274/2018, 623/2014, 2003/2018, and the records the seventh amendment repaired) are listed and not read.
   Three rules were tightened, and one comparison corrected, on dry runs that listed the scans' hits and read no filing
   for a verdict (census-eighth-dryrun.log, -dryrun2.log, -dryrun3.log): the first rules flagged 224 records, mostly
   narrative about net claims beside gross tables, ordinary year-on-year changes in reserves, and managing agents' changes
   of management.
4. Readings. A record read in an earlier sample or census keeps its readings when nothing its verdict was read against
   has changed (fourth amendment, point 3), except in takeon_triangle, whose question is new; a record with only a first
   reading gets a second. Every other record gets a first reading, from the same brief, pack and page tool under the same
   instruction, with the census questions its parts ask (make_reader_prompts_eighth.py), and a second reading.
5. Repair of what the census confirms, under the owner's decisions above. A record whose two readings find an error and
   agree on the filing's figure within the protocol's tolerance is repaired by that figure. A record whose two readings
   both find a net table is registered with a net basis; both find a take-on dominating its triangle figure, a take-on;
   both find its opening reserves another line of the filing and agree on the gross figure within 2%, its opening
   reserves; both find a figure that is not development or not an amount and nothing to replace it, an unknown basis.
   Any other record is left as it is, with its readings recorded.
6. The refit and the headline. The analysis is refitted once more (refit 3) on the committed tree after the repairs.
   The fifth amendment's point 5 then compares Vignette 1's VaR99.5 from refit 1 (before any repair, analysis db8eba4)
   with refit 3's, and simulates undetected errors on refit 3 at the third sample's posterior, with N the working-sample
   records read in no sample or census, this census included.
7. The tail stratum is computed after refit 3, from its working sample (fourth amendment).

No other part of the protocol changes.

## Implementation note 3, 14 September 2026 (written 08:51), before the tail stratum is drawn

The tail's brief builder and scorer were written before the third sample and the censuses. Before the tail is drawn
from refit 3, make_adjudication_briefs_tail.py applies the loader's registers to each record as load_and_classify
applies them (the confirmed figure, then the confirmed opening reserves; implementation note 1 did the same for the third
sample), and resolves the filing's PDF as the packs do. A tail record keeps the readings of the latest sample or census
that read it, the eighth census and the third sample included, under the fourth amendment's rule (point 3): nothing its
verdict was read against has changed. score_error_rate_tail.py takes the carried reading and its second reading from
that sample or census, and compares a route with the record's latest replay log, as the third sample's merge does. No
part of the protocol changes.

## Ninth amendment, 14 September 2026, 12:13, after the eighth census was scored and before any repair below is made or any record below is read: the census's repairs, and the take-on base

The eighth census was scored on 14 September 2026 (error-rate-census-eighth-result.json). Of its 68 records, 58 were
read afresh and 10 carried their first reading; every record has two readings. The clarified verdicts are 54 correct,
9 errors and 5 undeterminable. Both readings find six errors: 2010/2015, 2791/2015, 3010/2018, 382/2017, 510/2014 and
5678/2015. By part, both readings find the mechanism in: movement, 382/2017; transposed, 3010/2018 and 5678/2015;
net_table, 382/2017 and 510/2014; opening, 1225/2018 and 609/2023; provisions_row, none; takeon_triangle, none (35
records absent on both readings). Unsettled: transposed, 1945/2021, 2010/2014 and 2010/2023; provisions_row, 1206/2014.
The readings also record mechanisms no part names: 2010/2015's provisions-text route dropped the brackets of a negative
line and put the result over the models' correct sign (a scan of every record's routes finds no other,
scan-provisions-sign-overrides.txt), and 2791/2015's triangle route read the cell 139,326 as 139.326.

On 14 September 2026 the owner decided two things the eighth amendment does not settle. 2010/2015, which both readings
find a sign error with different figures, is repaired by the note's gross prior-year line, -9.646m: rule 2 checks a
stated route against that line, and both readings quote it; the first reading recorded the 2013 and prior accounts'
-41.232m (p13) as its figure. And the take-on base below is repaired by adjusting the opening reserves.

1. The census's repairs, through the registers under the eighth amendment's point 5, with no extraction change and no
   paid call (register_eighth_repairs.py):
   - Confirmed figures (data/pyd_confirmed_figures.json): 2791/2015 -2.131m, 3010/2018 -4.140m and 382/2017 +7.401m
     (triangle, gross); 5678/2015 -8.135m and 2010/2015 -9.646m (stated, gross).
   - 382/2017's readings also both find the net table its route read. Point 5's net-basis sentence serves a record
     whose only figure is net. 382/2017's readings agree on the gross table's figure, which point 5's first sentence
     repairs, so the record keeps a gross basis.
   - A net basis: 510/2014, with the net table's figure (-48.4m, triangle, net), recorded and excluded as 1880/2014 is.
   - Opening reserves (data/opening_reserves_confirmed.json): 1225/2018 595.8m and 609/2023 1,171.381m, the gross
     claims outstanding at 1 January, where the adopted figures were the reinsurers' share.
   - Left as they are, with their readings recorded: 2010/2020, 2010/2022 and 2010/2023, errors on their first readings
     only; 1206/2014, 1945/2021 and 2010/2014, undeterminable on both readings; 780/2018 and 2008/2023, undeterminable on
     their first readings only.
2. The take-on base. Severity is the development figure over the opening reserves. A record's adopted development can
   cover business taken into the syndicate in the report year while its adopted opening reserves, the gross claims
   outstanding at 1 January before the transfer, do not. The eighth census's readings show two forms: a triangle that
   carries the transferred business on both diagonals of the step (restated: 3500/2019, 3500/2021, 3500/2022,
   3500/2023, 1884/2021, 1856/2024, 2488/2019, 3268/2020, 4444/2018 and 4444/2023), and a provisions note whose
   prior-year line follows a take-on row in the same roll-forward (2008/2019: 'RITC take on reserves 701,118' above
   'Change in prior year provisions 14,053'). Each figure is read correctly; their scopes differ. 1884/2021's severity is
   -27.3% on its 73.709m of opening reserves, and -2.2% on those reserves with the 839.787m taken on.
   The repair: the opening reserves become the gross claims outstanding at 1 January plus the gross claims reserves the
   filing states were transferred in the report year (the take-on row of its gross claims reconciliation, or the
   adjusted opening balance it prints, as 4444/2023's 'Adjusted 1 January 2,681,837'). There is no adjustment where the
   adopted figure does not cover the transfer: the business sits in the report year's own column, or in a column or line
   with no development rows (435/2018's 2010 and prior; 2008/2023's provision in respect of prior years); the transfer
   came in an earlier year (the opening reserves hold it already), after the balance sheet date, or from a quota-share
   reinsurer of the syndicate's own business (the gross figures hold it already); or it is outward. A take-on that
   enters a triangle's step without restatement stays under the sixth amendment: one dominating the figure is a take-on,
   and a smaller one is recorded for the owner.
3. The take-on base census: purposive, reported on its own and never pooled with a random sample. Its records are
   computed by make_census_ninth.py from the working sample the loader predicts for refit 3 on the committed registers,
   after point 1's repairs, and written to error-rate-census-ninth.json before any is read. A record is listed when its
   filing records a transfer into the syndicate in the report year, by any of: the RITC scan's inward decision for the
   report year; an inward passage naming another syndicate or a portfolio transfer (the eighth census's takeon_triangle
   rule, for every figure source); or a row naming a take-on (a reinsurance to close or RITC accepted, received, taken
   on, adjusted or from a syndicate; reinsurance of new liabilities; a take-on of reserves or balances; a portfolio
   transfer or LPT). The rule refuses unless it lists 1884/2021, 3500/2021 and 2008/2019, which define it.
4. Readings. The question is new. The eighth census's takeon_triangle part asked each reader where the table carries the
   transferred business and how much the report says was transferred. A record it read keeps both readings when both
   answer that; the editor records which records they settle, before any new reading, in error-rate-carry-over-ninth.json.
   Every other listed record gets a first reading, from the same brief, pack and page tool under the same instruction,
   with the take-on base question (make_reader_prompts_ninth.py). A first reading that finds no transfer the adopted
   figure covers, or a transferred amount under 5% of the opening reserves (it moves the severity by under 5% of itself,
   the protocol's tolerance), gets no second reading and no adjustment. Every other first reading gets a second.
5. Repair. A record whose two readings both find a transfer the adopted figure covers, of 5% or more of the opening
   reserves, and agree on its gross amount within 2%, is registered in data/opening_reserves_takeon_base.json with the
   gross claims outstanding at 1 January and the amount transferred, each entry with its pages, a quote and both
   readings. The loader (apply_takeon_base; implementation, test-first: src/test_takeon_base.py) applies the register
   after the confirmed opening reserves and before the FX conversion. It adds the amount to the block's opening
   reserves, recomputes the percentage, says so in the record's notes and counts the records, and it refuses an entry
   whose 1 January figure is not the block's within 2%. The run identifier hashes the register. Any other record is left
   as it is, with its readings recorded.
6. Refit 3, the headline and the tail stratum (eighth amendment, points 6 and 7) follow these repairs. The comparison of
   refit 1 with refit 3 therefore covers the census's repairs and the take-on base together; the report says so and
   lists each adjusted record's severity before and after. The tail's brief builder applies the take-on base register
   after the confirmed opening reserves (implementation note 3).
7. The rate stays the third sample's (eighth amendment, point 1). The take-on base is not an extraction error, and no
   sample is re-scored.

No other part of the protocol changes.

## Implementation note 4, 14 September 2026 (written 13:50), after the take-on base census was scored and before 2003/2018 is read on the sixth amendment's question

The take-on base census was scored on 14 September 2026 (error-rate-census-ninth-result.json). Of its 50 records, 15
are adjusted and 35 are left as they are, and data/opening_reserves_takeon_base.json holds the 15
(register_ninth_takeon_base.py). Two corrections to the scorer changed no outcome. It had asked for a second reading of
a first reading with coverage unsettled and a transferred amount under 5% of the opening reserves, which point 4 does
not, so 1084/2022 and 2232/2020 were not read a second time. And a first reading that point 4 decides now keeps that
reason where a carried second reading exists (2791/2024, 4444/2017).

Both of the census's readings of 2003/2018 find Syndicate 1209's 532.9m of gross claims outstanding, reinsured to close
into the syndicate on 1 January 2018, entering the adopted triangle's step without restatement: the table's end-2017
diagonal is the 2017 report's, retranslated. Under point 2 the record stays under the sixth amendment, whose question no
reader has put to it: the third sample's readings gave the verdict, the eighth census listed the record as decided and
did not read it, and the census's first reading answered the take-on base question. The editor's census reading answers
it as well, and finds that the take-on dominates the +419m figure. So the record gets one more reading, from the same
brief, pack and page tool under the same instruction, with the eighth census's takeon_triangle question
(make_brief_2003_sixth.py, reader-prompt-ninth-sixth-2003.txt). The reader opens no earlier reading. If it too finds the
take-on dominating the figure, the eighth amendment's point 5 makes the record a take-on; because the owner decided this
record on 14 September while the restatement was unsettled, the editor asks the owner before registering it. Otherwise
the record is left as it is, with its readings recorded for the owner. No part of the protocol changes.

(Added after the reading and the owner's decision.) The reader finds the take-on dominating the figure
(error-rate-verdicts-ninth-sixth-2003.json). Syndicate 1209's own 2017 report puts 59.5% of its gross reserves in
underwriting years 2012-2015: 317.1m of the 532.9m, 76% of the +419m step. The rest is in years this table prints only
as '2011 and prior', which has no step. Its verdict on the figure is undeterminable, as the census's first reading's
was; no sample is re-scored. The owner decided to exclude the record, and register_2003_takeon.py registered it in
data/takeon_not_development.json at 14:43.

## Implementation note 5, 14 September 2026 (written 15:09), before the tail stratum is drawn

Implementation note 3 carries a tail record's readings from the latest sample or census that read it. The take-on base
census is not one of those for the tail. Its question was the take-on base: its 22 fresh first readings were neither
clarified nor scored, and its 28 carried readings are the eighth census's, which the tail's brief builder already
consults. So a tail record that census read keeps the readings of the latest earlier sample or census that read it when
nothing its verdict was read against has changed (the fourth amendment's rule, point 3), and is otherwise read afresh.
A record the take-on base register adjusts has new opening reserves, so under that rule it is read afresh. No part of
the protocol changes.

## Tenth amendment, 21 September 2026, written 17:16, after two readings of the records in point 4 began (16:51) and before either is scored or any repair below is run on the data (the loader's rules in point 1 were written at 17:05): three mechanisms a frozen external review found, and records found in passing

A frozen review of the submission (21 September 2026, frozen at 05:14 UTC) found three mechanisms that the samples
and censuses above had not reached. Each is counted across the whole corpus by a script written before its records
are read, and is reported on its own, never pooled with a random draw.

1. A figure that is not development, adopted from one model. 1884/2016 began underwriting in April 2015, so its 2016
   report has no underwriting year up to t-2 and no prior-year line. One model left the figure blank; the other read
   the 2015 year's closing outstanding less the whole opening outstanding, +15.044m, and the loader adopted that lone
   reading. The tail stratum's reading had already scored it an error. The loader now counts a lone model reading with
   no route, where the two readings disagreed, in a report whose triangles hold no year up to t-2, with the skipped
   first-year reports. It gives no severity to a model reading whose own notes describe its figure as the year's
   movement in the claims provision, or as closing less opening outstanding (src/run_analysis.py). The census is those
   two rules run over all 1,065 records before any record was read for it: the first flags 1884/2016 (in the working
   sample) and 6133/2018 (out); the second flags 1884/2016, 3622/2017 and 6107/2020 (both out). The extraction's
   first-year skip is repaired too, and its offline replay writes 1884/2016 as a first-year stub.
2. An inward transfer of another syndicate's older reserves, described without a transaction noun. 1856/2018's report
   says the class grew because of "15.4% of the 2015 and prior year of account of reserves from Syndicate 1955 being
   transferred into the 2016 year of account of Syndicate 1856". Neither scanner could see the sentence, and the
   transfer register had filed the record as a current-business false positive. The census is the transfer scanner,
   with a path for such a sentence, run over every filing, PDF and HTML. Every new flag is adjudicated by hand into the
   register, as before. 1856/2018 enters the RITC regime. Whether its take-on dominates the step it sits in is the
   sixth amendment's question, and goes to the owner with two readings (point 4).
3. A premium table read in part: "Reinsurance acceptances" rows with a premium dropped as section headers, labelled
   classes dropped as subtotals, and a text fallback that read some classes and whose class sum the driver wrote over
   both models' totals, so that the loader's reconciliation compared the mix with itself. The census compares each
   record's class sum with a premium total that two independent readings agree on within 2%: 147 records fall below
   80% of it, 122 of them in the working sample. The repair is in the extraction (the deterministic parse refuses a
   table whose total it cannot reconcile, the models' total is kept, and a refused mix falls back to the models'
   cached mix) and an offline replay from the committed caches, with each changed record listed. The loader compares
   the mix with an independent total.
4. Records found in passing, each read twice as a census record is (seventh amendment, point 2): 1856/2018's take-on
   share of its +59.638m step; 1856/2020 (the same quota share commuted back to Syndicate 1955 in 2020); 1971/2024 (a
   standing run-off quota share); 3334/2018 (an "External RITC transfer (run-off years)" line adopted as development);
   and 1206/2014 (a "Liability (2013 and prior years of account)" balance adopted as development, whose earlier two
   readings were undeterminable). A record whose two readings find an error and agree on the filing's figure is
   repaired by it. One whose readings find no qualifying gross figure is recorded and not modelled, as a net-basis
   record is.
5. The tail stratum's one error, 1884/2016, is repaired by point 1. The stratum was drawn from refit 3 and is reported
   as drawn; donors that enter the top 20 of the refit that follows these repairs are listed with whether a sample or
   census has read them.

No other part of the protocol changes.

## Implementation note 6, 21 September 2026 (written 18:37), after the two readings of the tenth amendment's point 4 and before any of its repairs is run on the data

The tenth amendment's point 2 sent the question whether 1856/2018's take-on dominates its step to the owner. The
eighth amendment's point 5 already decides it under the owner's standing decisions: a record whose two readings both
find a take-on dominating its triangle figure is a take-on. Both readings find the take-on unrestated and above half
of the +59.638m step on every bound (55-85%, about 69% at the centre), so the record is registered as a take-on in
data/takeon_not_development.json, with the readings' inferred amount marked as inferred: no filing prints it.
Two questions no point covers go to the owner: 1856/2020, whose -62.513m figure is mostly an outward transfer (the
commutation of the same quota share back to Syndicate 1955, effective 1 January 2020), and 3334/2018's opening
reserves, 116.773m printed, which include 37.982m of run-off reserves transferred out effective 31 December 2017
and not covered by the repaired figure. No other part of the protocol changes.

## Implementation note 7, 21 September 2026 (written 22:20), after the extraction's replay and before the regeneration

The owner had not answered the two questions of implementation note 6 when the extraction's replay ended. The run
applies the recommendations put to the owner; either is reversed by one register entry and a rerun.

1. 1856/2020 is registered in data/takeon_not_development.json as a transfer, not development. Both readings find
   the commutation of the quota share back to Syndicate 1955, effective 1 January 2020 (the refund, £49.1m, p48),
   at 76-79% of the -62.513m figure. The frozen review asks for the same rule on analogous quota-share transfers
   (M02), and this is the mirror of 1856/2018's take-on. The register's amount is the refund with a negative sign;
   the reserves 1856 released are not printed.
2. 3334/2018 keeps the opening reserves its filing prints, 116.773m, the paper's 1 January definition. They include
   the 37.982m of run-off reserves transferred out effective 31 December 2017, which the repaired figure (+5.109m)
   does not cover, so its severity is 5.109/116.773; on the retained reserves it would be 5.109/78.791.

No other part of the protocol changes.

## Implementation note 8, 21 September 2026 (written 22:35), after the extraction's replay, with the regeneration running

The tenth amendment's point 3 repairs the loader too: it compares a mix with an independent total. Run over the
committed records and the replayed ones with the same code, two details of that comparison decided records for
reasons the amendment does not name, and the loader now handles both (src/run_analysis.py, before the regeneration).

1. A class with a negative premium (a return or a commutation in a closing book) is part of the partition its total
   sums, so the classes are summed with their signs; the weights stay the positive classes' shares. Summed without
   them, 17 replayed mixes fail to reconcile where the filing's total agrees with the signed sum (3624/2019: 417.386m
   of positive classes, 408.141m with the negative ones, the total 408.141m).
2. Each model now keeps the premium total it read, where the extraction used to write the table's over both. A block
   whose model read no total, or one its mix does not reconcile with, takes the other reader's total that the mix
   does reconcile with (7 replayed records, 1969/2024 among them).

With both, and before 1856/2020's register entry (implementation note 7, which takes it out of either), the working
sample the loader builds is 688 records on the committed records and 687 on the replayed ones: 5 enter (1458/2018,
1609/2024, 2468/2014, 3010/2022, 3623/2024), each with a complete table that reconciles with a model's total, and 6
leave (1110/2021, 1840/2024, 2468/2021, 6118/2016, 6118/2017, 6129/2018): two with a negative premium total, and four
whose adopted model's mix names no class of business, a single reinsurance line (6118/2016, 6129/2018), direct and
reinsurance only (1110/2021), or none (6118/2017). No development figure of a record in both changes. On the replayed records, point 3's census rule finds no working-sample mix below 80% of a total two
independent readings agree on, and none more than 2% (or 0.2m) from every such total; 2 records have no such pair, because
their tables print the total with a currency sign the parser does not read, and each reconciles with one model's
total. A model's own mix checked against that model's own total is no independent check, and the one record that
would rest on it alone (727/2019) stays out. No other part of the protocol changes.

## Eleventh amendment, 22 September 2026, written 03:39, after the refit that follows the tenth amendment's repairs and before any record below is read: the records the repairs brought into the working sample

The tenth amendment's repairs changed the working sample. Five records entered it, each because its premium mix now
reconciles with an independent total: 1458/2018, 1609/2024, 2468/2014, 3010/2022 and 3623/2024. No sample or census had
read any of them: each census was computed on a working sample they were not in. One, 3010/2022, meets the eighth
amendment's transposed rule (every working-sample record of Syndicate 3010), and it now gives Vignette 1's largest
transferred severity, 0.607 (the next is 0.402). Its adopted figure, +146.569m (USD), is the provisions note's "Change in
prior year provisions", while the extraction's own gross triangle over underwriting years up to t-2 gives -10.926m, which
the sign check refused because both models read the note's figure. The tenth amendment's point 5 lists one more unread
donor in the top 20 of the refit: 1969/2018 (rank 20).

1. The six records are read twice, by two readers reading independently of each other, as records found in passing
   (seventh amendment, point 2), each with the question its record raises.
2. A record whose two readings find an error and agree on the filing's figure within the protocol's tolerance is
   repaired by that figure; the other outcomes follow the eighth amendment's point 5. A repair is followed by a refit
   before the recorded pass, and the tenth amendment's propagation and tail listing are computed on that refit.
3. The readings are reported with the tenth census's, apart from any random draw, and the working sample's rate is not
   re-estimated.

No other part of the protocol changes.

## Implementation note 9, 22 September 2026 (written 04:18), after the eleventh amendment's readings and before any repair they lead to

Two readers read the eleventh amendment's six records, each without the other's reading (tenth-census/entrants/).

1. They agree that four are correct: 1458/2018, 1609/2024, 3623/2024 and 1969/2018. Each is a triangle figure that the
   printed gross table reproduces, with the right opening reserves.
2. They agree that 2468/2014 is an error. Its +27.7m is the directors' attribution of the year's loss to four items,
   one of them a reduction in reinsurance recoverables: a net figure, and not a prior-year movement. The filing states
   no gross prior-year movement and prints no triangle, so under the eighth amendment's point 5 the record is registered
   with an unknown basis and leaves the working sample.
3. On 3010/2022 they agree on every number. The printed gross triangle over underwriting years 2013-2020 gives
   -10.926m; the note's "Change in prior year provisions", +146.569m, carries the 2021 underwriting year (t-1), which
   moved +157.640m on the triangle, 108% of the line; the opening reserves are right. They differ on the score. One
   reads the record as the eighth amendment's family and a scope error. The other reads a faithful extraction of a
   prior-year line, which refinement 2 records and does not score, and states that the paper's rule gives -10.926m.
   The paper defines M on mature underwriting years, from the triangle where one supplies it, and both readings give
   that figure, so the record is repaired to it (data/pyd_confirmed_figures.json). The score is recorded as each reading
   gives it, and no rate uses it (eleventh amendment, point 3).
4. The second reader found 1609/2023 in passing: its 2023 table appears to be printed transposed, so its adopted
   +11.657m would be +8.834m. It is read a second time before any repair (seventh amendment, point 2).

No other part of the protocol changes.

## Implementation note 10, 22 September 2026 (written 09:16): the owner's answers to implementation note 6

The owner answered the two questions of implementation note 6 on 22 September 2026, before the recorded refit.

1. 1856/2020 is excluded as a transfer, not development, as implementation note 7 registered it; the register entry's
   decision is now the owner's (data/takeon_not_development.json).
2. 3334/2018's opening reserves are the reserves retained at 1 January 2018: the printed 116.773m less the 37.982m of
   run-off reserves the external RITC took out effective 31 December 2017, 78.791m, which is what the repaired figure
   (+5.109m, the gross triangle over the retained years) covers. It is registered in data/opening_reserves_confirmed.json
   with both readings, which give the transfer and the retained figure. Its severity is 5.109/78.791.

The analysis is refitted on these registers before the recorded pass. No other part of the protocol changes.

## Twelfth amendment, 22 September 2026, written 14:18, after the refit on the registers of implementation notes 9 and 10 and before any record below is read: the unread donor in that refit's top 20

The refit on the registers of implementation notes 9 and 10 has a working sample of 685 records. Against the tail
stratum, three donors enter Vignette 1's top 20 (tenth-census/tail-entrants-tenth.json): 3010/2020 (rank 18) and
1969/2018 (rank 19), both read, and 1729/2024 (rank 20, transferred severity 0.166), which no sample, census or reading
has read. Its adopted figure, +77.918m (USD), is a gross triangle the extraction read in thousands, which overrode both
models' +39.5m, the sum of three amounts in the report's commentary. The two models disagree on its opening reserves:
368.826m, adopted, and 291.287m, which that model's own note describes as a conversion to sterling.

1. 1729/2024 is read twice, by two readers reading independently of each other, as the eleventh amendment's records
   were.
2. Its outcome follows the eleventh amendment's point 2: a repair is followed by a refit before the recorded pass, and
   the tenth amendment's propagation and tail listing are computed on that refit. A donor that refit brings into the
   top 20 unread is read the same way.
3. The readings are reported with the eleventh amendment's, and the working sample's rate is not re-estimated.

No other part of the protocol changes.

## Implementation note 11, 22 September 2026 (written 14:41), after the twelfth amendment's readings

Two readers read 1729/2024, each without the other's reading (tenth-census/entrants/readings/reader-F.txt and
reader-G.txt). They agree that it is correct. The printed gross triangle ($'000, USD) over underwriting years 2014-2022
gives +77.918m, the adopted figure, and the opening reserves, 368.826m, are the filing's gross claims outstanding at
1 January 2024. The models' +39.5m was the sum of three drivers the commentary prints in sterling, which the triangle
route had already overridden; the other model's 291.287m is the opening figure converted to sterling, and was not
adopted. No repair follows, so the refit on the registers of implementation notes 9 and 10 is the one the recorded
pass reproduces, and the tenth amendment's propagation and tail listing are computed on it.

No other part of the protocol changes.
