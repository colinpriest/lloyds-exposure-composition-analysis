r"""error-rate-protocol.md: the eighth amendment, written before any record it lists is read and before any repair
it names is made. The time in its heading is the clock's when this runs; the figures are read from the third sample's
result file.

    python amend_protocol_eighth.py
"""
import datetime
import io
import json
from pathlib import Path

SCR = Path(__file__).resolve().parent
PROTOCOL = SCR / "error-rate-protocol.md"
CENSUS = SCR / "error-rate-census-eighth.json"
if CENSUS.exists():
    raise SystemExit("%s exists: the amendment must come before the census file" % CENSUS.name)
for p in SCR.glob("error-rate-verdicts-eighth-batch-*.json"):
    raise SystemExit("%s exists: the amendment must come before any reading" % p.name)
res = json.load(io.open(str(SCR / "error-rate-result-third.json"), encoding="utf-8"))
A, W = res["A_sampled"], res["working_sample"]
if (A["errors"], A["correct"], A["undeterminable"]) != (8, 154, 7):
    raise SystemExit("the third result is not the one this amendment describes: %s" % A)
now = datetime.datetime.now()
stamp = now.strftime("%H:%M")

TEXT = r'''
## Eighth amendment, 14 September 2026, %(stamp)s, after the third result was scored and before any record below is read or any repair below is made: the third sample's errors, their families, and their repair

The third sample was scored on 13 September 2026 (error-rate-result-third.json). A, the 169 sampled records, holds
%(e)d errors, %(c)d correct and %(u)d undeterminable; the working sample's rate is %(m).1f%% (95%% credible interval
%(l).1f%% to %(h).1f%%). The eight errors are mechanisms the earlier repairs did not reach:
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
Both readings of 1274/2018 find its triangle figure (+294.748m) about 93%% the Motor RITC it accepted on 1 January 2018
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
     within 5%% of the report year's first estimate in its own triangle;
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
   both find its opening reserves another line of the filing and agree on the gross figure within 2%%, its opening
   reserves; both find a figure that is not development or not an amount and nothing to replace it, an unknown basis.
   Any other record is left as it is, with its readings recorded.
6. The refit and the headline. The analysis is refitted once more (refit 3) on the committed tree after the repairs.
   The fifth amendment's point 5 then compares Vignette 1's VaR99.5 from refit 1 (before any repair, analysis db8eba4)
   with refit 3's, and simulates undetected errors on refit 3 at the third sample's posterior, with N the working-sample
   records read in no sample or census, this census included.
7. The tail stratum is computed after refit 3, from its working sample (fourth amendment).

No other part of the protocol changes.
''' % {"stamp": stamp, "e": A["errors"], "c": A["correct"], "u": A["undeterminable"], "m": 100 * W["mean"],
       "l": 100 * W["ci95_equal_tailed"][0], "h": 100 * W["ci95_equal_tailed"][1]}

raw = io.open(str(PROTOCOL), encoding="utf-8", newline="").read()
if "## Eighth amendment" in raw:
    raise SystemExit("the eighth amendment is already written")
io.open(str(PROTOCOL), "a", encoding="utf-8", newline="").write(TEXT.replace("\n", "\r\n") if "\r\n" in raw else TEXT)
print("error-rate-protocol.md: eighth amendment written at %s" % now.isoformat(timespec="seconds"))
