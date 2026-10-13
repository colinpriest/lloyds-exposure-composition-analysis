# Extraction error rate: the fourth random draw, fixed before it is drawn

Written 13 October 2026, from 12:53 to 13:10 (Brisbane, UTC+10, read from `date`), before the seed exists, before any
record is drawn and before any record of the draw is read. It is committed with the sampling script and the frame
file, and the draw is taken only after that commit (the script refuses otherwise). The point of fixing it first is the
first protocol's: the definition of an error, the population and the analysis cannot then be chosen to suit the result.

The first protocol (`error-rate-protocol.md`, with its twelve amendments and eleven implementation notes) still governs
everything this one does not change. Where this file says "as before", it means that protocol's rule.

## Why this exists

The paper's error rate, 5.2% (95% credible interval 2.4% to 9.1%), pools the second sample (drawn after R209 and R210)
and the third (drawn after the first repairs). It is then applied to a working sample that has since received further
repairs and rule changes: records entered and left, and 122 premium mixes were reconciled again. A frozen review of the
submission in round 62 (item T6-d) objects that no fresh random draw validates the final extraction, and asks for one
pre-registered draw of about 100 records on it. The author decided on 13 October 2026 to run one. This is that draw.

## What is being estimated

**θ4, the probability that a record drawn at random from F carries a materially wrong adopted prior-year development
figure**, judged against the syndicate's own filing, where F is the frame defined below: the records of the final
working sample that no sample or census of this study has read.

θ4 is a property of the final extraction: the records and registers at analysis commit de0e840, which the recorded run
`model/exposure_results.json` (analysis run 55637e7e-d22a-5068-89c5-c108c2019ffd; without calibration
746c8f78-1cdf-5d4a-974b-99a357868174) was built from, and the extraction repository at 713c77b3, whose committed records
for the 674 working-sample records are byte for byte the analysis copies (line endings aside).

F is also exactly the set the propagation (`src/error_rate_propagation.py`) calls unread and perturbs. So θ4 is the
rate the propagation needs: the rate among the records nobody has read.

## Population

All counts are computed by `scripts/draw_error_rate_fourth.py frame` and written to
`fourth-sample/error-rate-frame-fourth.json`, committed with this file.

1. **W, the working sample: 674 records.** The stems `adopted_model.load_sample` retains from
   `model/exposure_results.json` (SHA-256 2825f30f...ae7, recorded in full in the frame file). Its disposition flow
   says 674 too. The script refuses if either differs.
2. **R, the records the study has read: 293 stems, 274 of them in W.** R is every `syndicate_NNNN_YYYY` string in the
   two files `src/error_rate_propagation.py` reads as its read set, `propagation/error-rate-read-stems.json` (the
   first, second and third samples, the census of the two mechanisms, the take-on census, the records found in passing,
   the eighth and ninth censuses, the reading of 2003/2018, the tail stratum) and
   `tenth-census/error-rate-read-stems-tenth.json` (the tenth census's records found in passing, 1884/2016, and the
   eleventh and twelfth amendments' records). The rule (`stems_in`) is the propagation's, so the set is the same.
   The 274 split:
   - 161: the pooled rate's sample (the second sample's records and the third sample's) still in W. This is the 161
     that `results/error_rate_propagation_results.json` reports as `n_in_current_working_sample`, with 6 errors, 148
     correct and 7 undeterminable: 4.2% (1.6% to 7.9%).
   - 35: the first sample's records in neither later sample.
   - 78: records only the censuses, the tail stratum, the records found in passing and the entrants read.
3. **Why all 274 are excluded, not only the 161.** The request named the 161. Excluding only them would leave the 113
   records the first sample, the censuses and the tail read inside the frame. Three reasons to exclude all 274:
   - F is then exactly the propagation's unread set, so θ4 is the rate the propagation applies, with no reweighting.
   - The censuses read their records twice, on purpose where errors were expected, and the errors they confirmed were
     repaired. A random reading spent on one of them looks again where the study has already looked.
   - Every record of W then falls in exactly one of F, K and C below, so the working sample's rate can be built from
     parts that are each accounted for.
4. **K, read and checked at the final figures: 267 records.** A record of W and R is checked when the latest verdict on
   its figure read what the record carries now. That is the first protocol's fourth amendment, point 3, with each field
   read for what the check uses (`census_reason` in the script):
   - the figure: the latest figure verdict read the adopted figure the record carries now; or it now carries a figure
     two readings confirmed (`data/pyd_confirmed_figures.json`); or the first and second reading of that verdict both
     give the figure it now carries (the extraction has since moved the figure to the readings' own, as for 1225/2022,
     218/2020 and 5000/2017);
   - the opening reserves: unchanged since that verdict, or from a register two readings confirmed
     (`data/opening_reserves_confirmed.json`, `data/opening_reserves_takeon_base.json`);
   - the figure's source (triangle or stated): unchanged, unless the record now carries a confirmed figure;
   - the basis: unchanged;
   - the cohort scope: unchanged, for a stated figure only. A triangle figure is checked against the triangle over
     underwriting years up to t-2 whatever its scope label says (clarification, rule 1). The loader has since relabelled
     many triangle figures from "disclosed-prior-year" to "mature-enforced"; no figure moved with the label.
   The tenth census's and the eleventh and twelfth amendments' two-reader verdicts on a figure count as verdicts. A
   reading on another question only (whether a transfer is genuine, the take-on base) does not.
5. **C, read but not checked at the final figures: 7 records**, each read twice as a census (below), reported apart and
   never pooled with the draw:
   - 1861/2019, 2232/2022, 2232/2023, 318/2024: the take-on base census read them on its own question; their fresh
     first readings were neither clarified nor scored (first protocol, implementation note 5);
   - 1971/2024: the tenth census read it on whether a transfer was genuine, not on its figure;
   - 4020/2016 (18.492 to 25.303) and 4020/2017 (17.285 to 21.188): read in the first sample; R209 moved their figures
     after it (first protocol, fourth amendment), and no reading has checked the new figures.
6. **F, the frame: 400 records**, W less R, sorted lexicographically. By year: 2014 9, 2015 47, 2016 37, 2017 41,
   2018 37, 2019 49, 2020 39, 2021 29, 2022 37, 2023 38, 2024 37. 310 GBP and 90 USD. By the figure's source, 342
   triangle and 58 stated. By route: rag_triangle 336, model_reading 30, rag_provisions 25, code_triangle 3,
   confirmed_figure 3, and one each of rag_yoa_narrative, rag_general_narrative and no route. Every record of F has
   its filing on disk (a filed PDF, or the extraction's PDF conversion of an HTML report). Three records of F carry a
   figure that a review outside this study confirmed (2121/2019, 382/2020 and 6112/2016, in
   `data/pyd_confirmed_figures.json`). They stay in F, because the propagation counts them unread, and a drawn one is
   read afresh like any other.

F, K and C partition W (400 + 267 + 7 = 674). The script refuses otherwise.

## Sample size

**n = 100**, a simple random sample of F without replacement: 25% of it.

The earlier samples' undeterminable share was 2% to 8% (pooled, 7 of 169), so about 96 records should be adjudicable.
At a true rate near the earlier ones, the Jeffreys posterior from 96 adjudicable records would be about:

| Adjudicable | Errors | Mean | 95% credible interval | Width |
|---|---|---|---|---|
| 50 | 2 (4% or 5%) | 4.9% | 0.8% to 12.2% | 11.4 points |
| 96 | 4 (4%) | 4.6% | 1.4% to 9.6% | 8.2 points |
| 96 | 5 (5%) | 5.7% | 2.0% to 11.0% | 9.0 points |
| 150 | 6 (4%) | 4.3% | 1.7% to 8.1% | 6.4 points |
| 150 | 8 (5%) | 5.6% | 2.6% to 9.8% | 7.3 points |
| 200 | 8 (4%) | 4.2% | 1.9% to 7.4% | 5.5 points |
| 200 | 10 (5%) | 5.2% | 2.6% to 8.7% | 6.1 points |

For comparison, the pooled rate's interval is 6.7 points wide (162 adjudicable), the third sample's alone 9.9 points
(108), and the 161 records' 6.2 points (154).

So 100 gives an interval about as wide as the third sample's, on a population none of the earlier draws covered. 150
would narrow it by about a fifth for half as many readings again; 200 by about a third for twice the readings. 100 is
the size the review asks for, and four batches of 25 are a reading load that four agents can finish in one sitting.
The draw can tell a rate near 4.5% from a rate near zero: at θ = 4.5% the chance of finding no error in 96 is 1.2%,
and if none is found the 97.5% point falls to 2.6%. It cannot tell 4% from 6%; nor could any size the readings allow.

Because 100 is a quarter of F, the number of errors among the other 300 is known more tightly than θ4 is. The rate is
reported as θ4, the probability for a record drawn from F, as every earlier rate was. The finite-population view is
narrower, so the reported interval is the conservative one.

## The seed

The seed is taken from the clock after the commit that holds this file, the script and the frame:

    TS=$(date '+%Y-%m-%dT%H:%M:%S%z')          # Git Bash on the PC; its clock is Brisbane, UTC+10
    python results/extraction_error_rate/scripts/draw_error_rate_fourth.py draw --timestamp "$TS"

The script computes `seed = int(SHA-256(TS as ASCII bytes), 16)`, the whole 256-bit digest as an integer, and records
the timestamp, the digest and the seed. Anyone can check the digest with `printf '%s' "<TS>" | sha256sum`. The script
refuses a timestamp that is not in that format, one not later than the pre-registration commit, one in the future, a
frame or script or protocol that is uncommitted or changed, and an `exposure_results.json` that is not the one the
frame was computed from. The draw is taken once and its file is never rewritten.

## The sampling code

`scripts/draw_error_rate_fourth.py draw`: `numpy.random.default_rng(seed).choice(400, size=100, replace=False)` over
F's sorted list. The draw order allocates records to readers: draw positions 1-25 are batch 1, 26-50 batch 2, 51-75
batch 3 and 76-100 batch 4, so the allocation is random too. C's seven records are batch 5. For each record the draw
file (`fourth-sample/error-rate-sample-fourth.json`) holds the brief: the adopted figure and opening reserves in the
report's currency, the loader's registers applied as `load_and_classify` applies them (confirmed figure, confirmed
opening reserves, take-on base); the route; the figure's source; the cited pages; the basis and cohort scope; the
record's path in both repositories; the filing's path; the observation's GBP figures. The script checks each brief's
figures against the observation, converted as the loader converts them, and refuses on any difference. A drawn record
is never replaced: one that proves hard to read is scored undeterminable.

## The reading procedure

For each record, a reader:

1. Generates nothing and edits nothing except its own output file. The evidence pack is written before reading, by the
   extraction repository's pack generator, which reads committed records and caches and makes no call:
   `python D:/dev/lloyds_reserve_stress_testing/scripts/adjudication_pack.py --stems <batch stems> --out <packs dir>`.
2. Reads the brief: the adopted figure, the route, the figure's source and the page hints (the prior-year movement
   page, the triangle's page and the opening reserves' page). The hints say where the pipeline looked. They are not
   evidence.
3. Opens the filing with the page tool, `scripts/filing_pages.py` (text layer, or Tesseract OCR for a scanned page;
   `--find` for a pattern, `--rotate` for a page printed sideways). Page numbers are the PDF's own order from 1.
4. Compares:
   - for a triangle-sourced figure: the gross claims development table the filing prints, recomputed as the sum over
     underwriting (or accident) years up to t-2 of the latest diagonal less the one before, in the table's units,
     divided to millions in the report's currency; the right table (gross, this syndicate), the right cells;
   - for a stated figure: the gross prior-year movement the filing states for the report year;
   - in both cases, where the filing prints both, both are recorded;
   - the opening reserves: the gross claims outstanding at 1 January of the report year, against a 2% tolerance;
   - the page binding: the figure is this syndicate's, not a companion's in a combined report.
5. Records, per record: the verdict; the filing's figure; the stated movement where one is printed; the triangle
   recomputation, its pages and its arithmetic where the figure is triangle-sourced or a triangle is printed; the pages;
   a verbatim quotation of the cells or text that settle it; the arithmetic against the tolerance; the error kind; the
   basis and page-binding checks; the opening reserves (adopted, filing, page, within 2%); and the reasoning.

The first readers' instruction is the third sample's (`third-sample/reader-prompt-third-batch-1.txt`), word for word
in its definitions, with this draw's paths, so that the rate under that instruction stays comparable. The output schema
is the third sample's with one field added, `stated_movement_m`. A reader opens no earlier verdict, verification or
result file of any sample or census, and no other batch's output. The brief for each batch says exactly what to open
and what to write.

Batches 1 to 4 each have one first reader. C's seven records each get two readings, by two readers reading
independently of each other, as the eleventh amendment's records did.

Second readings follow the rule the first protocol fixed (`score_error_rate.must_verify`): every clarified error,
every first-reader error, every verdict the clarification changed, every undeterminable, every triangle-sourced figure
without a recomputation, every figure whose source is not what its route field says, and a random fifth of the
remaining corrects, drawn with `numpy.random.default_rng(seed)` from this draw's seed. One change makes them stricter:
the second reader is a separate agent, given the brief, the pack and the page tool but not the first reading's verdict,
figures or arithmetic. As before, a second reading stands over the first. Every disagreement is recorded.

## What counts as an error

Unchanged from the first protocol. A record is scored **error** when any of these holds:

- (a) the adopted `prior_year_development_gbp_m` (in the report's currency, millions) differs from the filing's own
  figure by more than `max(0.5, 0.05 × |adopted|)`;
- (b) the adopted figure has the opposite sign to the filing's (both non-zero; no threshold);
- (c) its scope is wrong in a way the filing makes plain: it includes the two most recent underwriting years, or it is
  a cohort's cumulative total, or it is net where the record claims gross.

**Correct** when the filing settles the figure and it agrees within the tolerance. The clarification and its three
refinements apply at the merge exactly as before: a triangle-sourced figure is checked against the triangle recomputed
over underwriting years up to t-2; any other figure against the movement the filing states; a difference between the
two is recorded and is not itself an error; the R197 register's records are stated figures; a stated figure recorded
as disclosed may include year t-1 (refinement 2).

One extension, for a route name the extraction added after `score_error_rate.figure_source` was written: a
`code_triangle` route is the deterministic triangle's code override, the figure refinement 3 read from an empty route
and its CODE OVERRIDE note, so its source is a triangle (`figure_source` in the script). `score_error_rate.figure_source`
alone reads all six such routes in W as stated (three of them are in F). Refinement 3's frozen route evidence
(`fallback-routes-pre-r208.json`) predates R208. Since R208 a `rag_triangle` route names a triangle only when its figure
was computed from it. The frame step checked that every `rag_triangle` route in W carries its triangle (all do), and
the merge refuses a drawn record that breaks this.

## Undeterminable records

As before: **undeterminable** when the filing does not settle the question from its pages (for example the only table
is a loss-ratio grid without premiums, a page is illegible, or the filing's own figures conflict and it does not say
which is the gross prior-year development). The reason is recorded. Undeterminable records are reported as their own
count and excluded from the denominator. Beside the rate, the bound with every undeterminable counted as an error is
reported, so a reader can see how much the exclusion matters.

## The analysis

1. **Draw four alone.** The Jeffreys posterior Beta(1/2 + e, 1/2 + n − e), for e errors among the n adjudicable drawn
   records, under the clarified rule (the protocol's), with its mean and 95% equal-tailed credible interval. Beside it:
   the same under the first readers' instruction, without second-reading corrections (as before); and the bound with
   the undeterminables counted as errors.
2. **Beside the earlier rates, never pooled with them.** The earlier draws were taken from other populations at other
   stages of repair, so no pooled figure is formed. Reported side by side: draw four's posterior; the pooled rate,
   5.2% (2.4% to 9.1%), Beta(8.5, 154.5); and its 161 records still in W, 4.2% (1.6% to 7.9%), Beta(6.5, 148.5). And
   the posterior probability that θ4 exceeds 0.052, the rate the paper has used, P(θ4 > 0.052 | draw four).
3. **The working sample's rate, as a secondary figure.** Built from its three parts: F through draw four (200,000
   draws of θ4 from its posterior, `numpy.random.default_rng(seed)`, the errors among F's 300 unread records drawn as
   Binomial(round(300 q), θ4) with q draw four's adjudicable share, plus draw four's own errors); K through each record's
   final verdict at its final figure (the latest set's second reading where one exists, else its clarified verdict; a
   record whose figure a register or the extraction has since repaired to the readings' figure is correct); C through
   its two readings (an error both find is an error; a disagreement is undeterminable). Reported as the mean and 95%
   interval of errors over adjudicable records. K's and C's verdicts are listed per record with the result.
4. The result file is `fourth-sample/error-rate-result-fourth.json`. The scorer, `scripts/score_error_rate_fourth.py`,
   reuses `score_error_rate`'s merge, clarification, verification set and posterior with the `code_triangle` extension,
   and is written and committed before any first reading is merged.

## What happens to the errors draw four finds

They are recorded with their pages, quotes and both readings. The rate is reported as measured, before any repair
(first protocol, eighth amendment, point 1). Whether to repair them is the author's decision, put to him with each
record's facts. A repair moves working-sample figures, so it needs a refit and the recorded run on the PC, and every
headline figure would move with it.

## What happens to the propagation

The propagation, `src/error_rate_propagation.py` (a manifest step), is re-run on the current fit with two changes,
made after draw four is scored and before the next recorded run:

- its rate is draw four's posterior, Beta(1/2 + e, 1/2 + n − e), the rate among unread records, applied to unread
  records; the pooled Beta(8.5, 154.5) is run beside it as a sensitivity, with the same seed and replicates;
- its read set adds draw four's 100 records and C's 7, so N, the unread records it perturbs, falls from 400 to 300.
  Draw four's records join the read set whether or not their errors are repaired: a known error left unrepaired stays
  in the fit as it is, and is listed with the result.

Nothing else in it changes: 2,000 replicates, `numpy.random.default_rng(20260915)`, the three error models, the shifts
from the confirmed errors, and the 5% materiality line. The code change, the refit and the recorded run are PC steps of
a later stage. This protocol fixes what they compute.

## What the result cannot say

- θ4 is the rate on F, the 59% of W nobody had read. It says nothing new about K, whose figures earlier verdicts
  checked; the working sample's rate (analysis, point 3) leans on those verdicts.
- 100 is still small. An interval about 8 to 9 points wide will sit around a mean of a few per cent, and the write-up
  must give the interval, not the mean alone.
- It measures the adopted figure and checks the opening reserves. It does not check every field of a record.
- It cannot detect an error that the filing presents ambiguously and that a reader reads the same wrong way the
  extraction did. That correlated-error limitation stands as before.

## Pre-registered, in this order

1. Commit this file, `scripts/draw_error_rate_fourth.py` and `fourth-sample/error-rate-frame-fourth.json`, with
   `MANIFEST.json` rebuilt, on branch `draw4` of a fresh clone of the analysis repository. This is the
   pre-registration. Nothing is pushed until the author says so.
2. Take the timestamp, draw, and commit `fourth-sample/error-rate-sample-fourth.json`.
3. Write the packs; read batches 1 to 4 (first readings) and C (two readings each).
4. Write and commit `scripts/score_error_rate_fourth.py`; merge and clarify; pick the verification set.
5. Second readings of the verification set.
6. Score; write the result; report it beside the earlier rates.
7. Put the repairs to the author. Then the propagation's change and the recorded run, on the PC.

No other part of the first protocol changes.

## Implementation note 1, 13 October 2026 (written 13:32, Brisbane), before any record of draw four is read

1. The scorer, `scripts/score_error_rate_fourth.py`, is written and committed before any reading exists (step 4 above,
   moved ahead of step 3). It does what "The analysis" and the reading procedure fix: the merge of the first readings
   and the census stratum's two readings, the clarification with the `code_triangle` extension, the verification set
   and its random fifth (from the draw's seed), the blind briefs for the second reader, the posterior under both rules
   and with the undeterminables counted as errors, the rates beside it, P(θ4 > 0.052) and the working sample's rate.
   Readings are staged in `fourth-sample/readings/` before the merge.
2. Its checks, `scripts/checks_score_error_rate_fourth.py`, run it on synthetic readings (30 checks, all passing), and
   `scripts/mutate_score_error_rate_fourth.py` breaks it 17 ways; each break turns the checks red. The checks file is
   named `checks_*.py`, not `test_*.py`, so the analysis suite, whose recorded collection count (2096 at de0e840) a gate
   compares, does not collect it. It is run by name: `python -m pytest -q checks_score_error_rate_fourth.py`.
3. The evidence packs are written by the extraction repository's `scripts/adjudication_pack.py` at 713c77b3 from the
   batch stems lists, and kept in `fourth-sample/packs/batch_<n>/` (107 packs: 25 for each of batches 1 to 4 and 7 for
   batch 5), so each reader's evidence is fixed before reading. Nobody has opened a pack's contents.
4. The working sample's rate (analysis, point 3) needs each K record's final verdict. The scorer reads it from the
   archive by the stated rule (`k_final_verdicts`): at the de0e840 records, 255 of the 267 are correct at their final
   figures and 12 undeterminable; none is an unrepaired error.

No other part of this protocol changes.

## Implementation note 2, 13 October 2026 (written 14:02, Brisbane), after the first readings and the merge, before any second reading

1. The first readings (batches 1 to 4) and the census stratum's two readings were staged into `fourth-sample/readings/`
   by `scripts/stage_readings_fourth.py`. Five files are copied byte for byte. Batch 4's file needed a mechanical
   repair: its reader rewrote the file after each record through a step that read it as cp1252 and wrote it as UTF-8,
   so each non-ASCII character (here only £) of an earlier record's text was re-encoded once per later rewrite, and
   the file reached 231.8 MB. 35 text fields of 19 records are repaired by undoing that step, from 1 to 22 rounds; each
   repair is accepted only because re-applying its rounds reproduces the stored field exactly, and the script refuses
   any repair that would change a verdict, a figure, a page list or an error kind. The log, with the stored file's
   SHA-256, is `fourth-sample/readings/first-batch-4-encoding-repair.json`. The stored file is not committed: it
   exceeds a git host's file limit, and its hash identifies it.
2. The merge (`score_error_rate_fourth.py merge`) refused nothing and warned of nothing. The verification set and the
   blind second-reader briefs it wrote are committed before any second reading. The second readers' batches are cut
   from the blind briefs in their sorted order, eight records each. Their outputs are staged as
   `fourth-sample/readings/second-readings.json` before the score.
3. The census stratum's outcome is computed from each reading's clarified verdict (the protocol's rule, "The
   analysis", point 3, with the clarification applied to every reading). Both readings of 4020/2017 recompute the
   printed gross triangle at the adopted 21.188; reader A scored it an error under the first readers' instruction
   because the filing's stated movement (8.718) differs. Under the clarification (rule 1, a triangle-sourced figure is
   checked against the triangle; rule 3, a difference from the stated movement is recorded and is not itself an error)
   both readings are correct, and the record's outcome is correct. Both raw verdicts are kept in
   `error-rate-census-fourth.json`.

No other part of this protocol changes.

## Implementation note 3, 13 October 2026 (written 14:19, Brisbane), after the second readings and the score

1. The three blind second-reading batches were staged as `fourth-sample/readings/second-readings.json` by
   `scripts/stage_readings_fourth.py --second`. It refuses a file that is not strict UTF-8 JSON, a field that looks
   re-encoded (refused, not repaired), a reading outside the verification set or outside the batch whose briefs named
   it, a duplicate, a record of the set with no reading, and a malformed reading (the merge's rule); each refusal was
   checked on synthetic readings before the real ones were staged. All 24 staged without a repair or a refusal, and
   each reader's adopted figure is the brief's. The files' SHA-256 are in `second-readings-sources.json`.
2. `score_error_rate_fourth.py score` wrote `error-rate-result-fourth.json`. Two second readings differ from the
   clarified first verdicts, and stand over them as the protocol says: 1458/2022 (undeterminable to correct, filing
   -63.2m) and 780/2014 (error to undeterminable). The second readings confirm 1274/2023 and 4472/2022 as errors, both
   a net table read as gross.

No other part of this protocol changes.

## Implementation note 4, 13 October 2026 (written 21:50, Brisbane), the author's decisions on draw four's errors and the propagation's change

1. The author decided on 13 October 2026 to repair both of draw four's errors to the printed gross triangle, the
   figure both readings give: 1274/2023 +87.073 USD m (gross table p35; the record used the net table on p36) and
   4472/2022 +122.3 GBP m (the first table on p53 is gross; the second, used, is net). They are registered in
   `data/pyd_confirmed_figures.json` with both readings. 4472/2022's entry in `data/pyd_basis_register.json` (a net
   narrative figure, superseded since 13 September 2026) is not read for it: `pyd_basis` reads a confirmed figure's
   basis first.
2. The same decision, on the triangle-table census (`error-rate-protocol-table-scan.md`, implementation note 3),
   repairs 1274/2022 and 4472/2023, registers 1218/2015 on the net basis and excludes 4020/2017, a record of this
   draw's census stratum C, under a new rule (`gross_triangle_does_not_reconcile`).
3. The propagation (`src/error_rate_propagation.py`) makes the change "What happens to the propagation" fixes: its
   rate is draw four's posterior under the clarified rule, Beta(2.5, 96.5); the pooled Beta(8.5, 154.5) runs beside
   it with the same seed and replicates; its read set adds `fourth-sample/error-rate-sample-fourth.json`, whose
   records are draw four's 100 and C's 7. On the working sample this draw was taken from (674) the unread records
   fall from 400 to 300. After the decisions above the working sample is 672: 4020/2017 was read (C) and 1218/2015
   was in F but not drawn, so the unread records are 299. Draw four's errors are listed with the result, each with
   whether a register repaired it (both are). Nothing else changes: 2,000 replicates, the seed 20260915, the three
   error models, the confirmed errors' shifts, and the lines at 4%, 5%, 6% and 10% with the share between 4% and 6%.

No other part of this protocol changes.
