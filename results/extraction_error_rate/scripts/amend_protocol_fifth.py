r"""The error-rate protocol's fifth amendment, written before any census record is read, any repair is made and any
new draw is taken (13 September 2026, 19:45).

    python amend_protocol_fifth.py
"""
import io
from pathlib import Path

P = Path(__file__).resolve().parent / "error-rate-protocol.md"
TEXT = r'''
## Fifth amendment, 13 September 2026, 19:45, after both results were scored and before any record below is read, any repair is made or any new record is drawn: the two error mechanisms, their repair, a second random draw, and the errors' effect on the headline

The second sample's two errors are mechanisms, not one-off misreadings. On 13 September 2026 the owner asked
for both mechanisms to be counted and repaired, for a larger random sample, and for the errors' effect on
Vignette 1's VaR to be measured. This amendment fixes how, before any of it is done.

1. Census of the two mechanisms. It is purposive, so it is reported on its own and never pooled with a random
   sample.
   - Replay stopped: every working-sample record listed in `pdf_extraction/audit/offline_unservable.json` at
     extraction commit 40eb31aa. Seven of the 698 are listed: 1301/2016, 1969/2015, 2008/2021, 2988/2021,
     2988/2022, 2988/2023 and 623/2016.
   - Aggregated older cohort omitted: every working-sample record whose adopted figure comes from a triangle
     that leaves out an aggregated older cohort the filing prints. The round-56 check named two, 3624/2015 and
     2007/2015. What that check covered is recorded with the census, and a record it missed is added if found.
   Each record gets a first and a second reading, from the same kind of brief, pack and page tool, under the
   same instruction, clarification and refinements. 2008/2021 and 3624/2015 keep their second-sample readings
   (fourth amendment, point 3).
2. Repair. Each error the census confirms is repaired at its mechanism, and so are the second sample's two
   errors.
   - A record whose replay stopped is re-extracted with the calls its caches lack, made under the pipeline's
     cost guards and cached. The owner authorised these Azure calls on 13 September 2026. No prompt changes,
     and no other record's cache is touched.
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

No other part of the protocol changes.
'''

raw = io.open(str(P), encoding="utf-8", newline="").read()
if "## Fifth amendment" in raw:
    raise SystemExit("already amended")
io.open(str(P), "a", encoding="utf-8", newline="").write(TEXT.replace("\n", "\r\n") if "\r\n" in raw else TEXT)
print("error-rate-protocol.md: the fifth amendment appended")
