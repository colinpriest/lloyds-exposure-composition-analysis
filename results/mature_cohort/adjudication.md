# Adjudication of the 86 restored and entering records, and the primary sample's rules

Read-only, 22 October 2026, written from 19:36 Brisbane (09:36 UTC by the clock). Inputs: analysis `D:/tmp/r62/pub4`
(e9e6645), manuscript `D:/tmp/r62/fin8/M` (c9074a1), extraction `D:/dev/lloyds_reserve_stress_testing` (read only),
the design study `D:/tmp/r62/oc/design/`, and the five readings `D:/tmp/r62/oc/readings/{A1..A4,B1}/readings.json`. No
repository was changed, no API was called. The AI declaration is out of scope and was not touched.

Decisions here are the Claude adjudication session's, under the rules the analysis already applies. The questions
the existing rules do not settle are put to the author at the end, with options, counts and a recommendation.

Files in this folder:

| File | What it is |
|---|---|
| `decisions.csv` | one row per record of the 86: status, figure, rule (file and function), evidence (reading file, pages), readers and agreement, notes |
| `measure_pop.py` -> `pop_measures.json` | per record of the 657 (571 + 86): census class, CO_g, table reserve, located pages, older-years lines and "earned" lines on the table's pages (offline, the census's own text loader) |
| `classify_pop.py` -> `pop_classified.json` | the earned-basis and coverage classes of the 657 |
| `make_decisions.py` | writes `decisions.csv` from the readings and the rules below |
| `sets.json` | the 672, the 571, the 86 and the design's 657 |

## Result

**Primary sample: 653 records** (the design proposed 657).

| Route | Records |
|---|---|
| triangle records already in the 672 (cohort-enforced) | 571 |
| restored to the triangle's figure | 58 of 61 |
| entrants (gross triangle displaced on sign) | 24 of 25 |
| **primary** | **653** |
| of which in the RITC (assumed-business) regime | 34 (31 of the 571; 1686/2021, 3000/2016, 4000/2022) |
| of which opening reserves adjusted for a take-on | 14 (11 of the 571 already registered; 1686/2021, 3000/2016, 4000/2022 to be registered) |
| of which run-off begun in or after the year (PART/AFTER) | 3 of the 86 (5151/2020, 1301/2020, 6125/2020), and the 571's own |

Leave the primary (4): 1861/2020 (an entrant; does not enter), 1084/2022, 2001/2022 and 6134/2023 (restored records:
they stay in the 672 sensitivity on their current figures). All four are transactions in the step (Q1, Q2).

Every restored figure was recomputed exactly from the printed gross table by every reader (86 of 86 match the
stored-grid figure; 20 records read twice). Readers disagree on 3 records (1225/2016, 1699/2024, 2015/2021),
resolved in Q7.

## Q1. A year-t RITC accepted or transferred in

**Existing treatment.** Three rules, all applied to the 571:

1. The assumed-business (RITC) regime, `src/assumed_business.py` `sources()`: the RITC scan's flag
   (`pdf_extraction/ritc_scan.json`, a classifier decision that excludes Lloyd's internal year-of-account RITC rows),
   confirmed inward transfers (`pdf_extraction/audit/portfolio_transfer_adjudication.json`) and confirmed take-ons
   (`data/opening_reserves_takeon_base.json`). A record in the regime stays in the sample with its own tail regime.
2. A triangle restated "as if" to carry the take-on on both diagonals of the step: the figure stands and the opening
   reserves become the 1 January gross claims outstanding plus the gross reserves taken on, where two readings agree
   on the amount within 2% and it is at least 5% of the opening reserves (error-rate protocol, ninth amendment points
   2 and 5; `data/opening_reserves_takeon_base.json`; `run_analysis.py` `apply_takeon_base`). Paper: Equation (1)'s
   paragraph and App 2.2. 15 records are registered, 11 of them in the 571 (1856/2024, 1884/2021, 2008/2023,
   2488/2019, 3268/2020, 3500/2019, 3500/2021, 3500/2022, 3500/2023, 4444/2018, 4444/2023); the other four (2008/2015,
   2016, 2018, 2019) carry stated figures.
3. A take-on that enters the step without restatement and dominates the figure: the record leaves as
   `TAKEON_NOT_DEVELOPMENT` (sixth amendment; eighth amendment point 5; `data/takeon_not_development.json`, read in
   `load_and_classify`): 1274/2018 (RITC 93% of the step), 2003/2018 (76%), 1856/2018 (55-85%, the amount inferred by
   both readings, implementation note 6). A smaller one is recorded for the owner.

**Whole population.** 31 of the 571 are in the regime: 14 RITC only, 5 RITC with a registered take-on, 5 inward
transfer only, 4 RITC with transfer and take-on, 2 take-on only, 1 RITC with transfer. 25 of the 31 were read by the
ninth (take-on base) census: 11 restated and adjusted; restated but under 5% (2791/2015, 2017, 2018, 2022, 2023;
1110/2022); not covered (the RITC in the report year's column, after the balance sheet date, internal, or nil:
435/2018, 1084/2021, 1110/2020, 1254/2023, 1969/2022, 1969/2023, 3000/2017, 3330/2017). **6 were never read on the
question** (they entered the regime or the sample after the census): 1884/2022, 1884/2023, 1971/2022, 1971/2023,
3330/2018 and 3500/2018 (see "Changes outside the 86").

**Decisions (same rules).**

| Record | Readings | Kind | Decision |
|---|---|---|---|
| 1686/2021 | A1, B1 transaction | restated: 2016-2018 at t-1 carry Syndicate 2007's history (1,125,373 against 256,846 printed in 2020) | primary, RITC regime; take-on base 903.214 (p25 'Effect of RITC 903,214'), opening 1,173.605 -> 2,076.819 USD m; S 0.0899 -> 0.0508 |
| 3000/2016 | A1, B1 transaction | restated (p38 'restated to reflect the historical information for Syndicate 1400') | primary, RITC regime; take-on base 248.822, opening 737.922 -> 986.744; S 0.0370 -> 0.0277 |
| 4000/2022 | A1, B1 transaction | restated: adds Syndicate 3334's 2015-2018 columns, 2019 at t-1 296,211 against 198,065 | primary, RITC regime; take-on base 181.247, opening 374.414 -> 555.661; S 0.0789 -> 0.0531 |
| 1861/2020 | A3, B1 transaction | in the step, not restated: 2017 'three years later' carries the 5820/1206 RITC; the filing calls the development 'apparent' | excluded as a take-on (the 2017 step +253.961 is 71% of +357.194); does not enter |
| 1084/2022 | A3, B1 transaction | in the step, not restated (t-1 column = the 2021 filing at FX): RITC of 2088, 95.0m | excluded as a take-on; dominance inferred, not printed (see below) |

All three take-on base amounts are at least 5% of the opening reserves (77%, 34%, 48%), both readings quote the same
printed line, and each record's adopted opening reserves equal the 1 January figure exactly in both model blocks, so
`apply_takeon_base` accepts them. Each needs a register entry with two readings, pages and a quote, as the 15 have.

1084/2022: Syndicate 2088's years of account run to 2019 (2088 merged into 1084 from the 2020 year), all mature at
t-2 = 2020; in a pure-year table the 95.0 lands in mature columns, which is 72% of +131.3; B1 finds no lump on the
2022 year. Both readings say the figure is moved by the take-on; B1 says the allocation is inferred and could be read
as undeterminable. Either reading excludes the record from the primary (a take-on, or no determinable mature figure),
so the outcome does not depend on it. It was in the ninth census (first reading only, under 5% of opening reserves for
the base), which asked about the base, not about dominance of a triangle figure.

## Q2. A ceded RITC distorting the tables, and a merger of years into one column

**2001/2022.** No rule names a ceded RITC, but two settle it. A figure dominated by an outward transfer is not
development: 1856/2020 (the quota share commuted back to Syndicate 1955) is in `data/takeon_not_development.json`
(implementation notes 6, 7, 10). And the design's validity rule (a valid figure is a printed table's development with
no transaction in the step). The filing says so itself: p52 'The development tables above are distorted by the impact
of the P&C UK 2019 & Prior YOA RITC'; the table's 2022 increments exceed the year's gross claims incurred by about
1,186.8m (B1). **Decision: excluded from the primary; no mature figure.** It stays in the 672 sensitivity on -256.3,
but p51 says that line also includes the RITC's impact: see the author's questions.

**6134/2023.** The 2019 and 2020 years of account, reinsured to close into Syndicate 2121 and reassumed under the 2021
quota share, sit in the 2021 column's t cell and not its t-1 cell (p43). That is an inward take-on entering the step
without restatement, dominating it (both readings; note 10's prior-UY incurred 23.807 shows the mature cohorts did not
move +77.9), and an aggregated column whose last step is not the report year's movement, which App 2.1 leaves out
("one printed by development age is left out, because its last step is not the report year's movement"). **Decision:
excluded from the primary.** 2007/2015, the existing case of a non-like-for-like aggregated column, is consistent: its
adopted code-triangle figure leaves that column out, so it stays.

## Q3. Table reconciliation (`gross_triangle_does_not_reconcile`)

**Existing rule, as the loader applies it.** An entry under the rule must carry the table's latest diagonal and the
filing's printed gross total of latest estimates, more than 2% apart (`run_analysis.py` `_confirmed_figure_gaps`; the
loader refuses an entry that reconciles), and the figure must still be the triangle's (`unreconciled_triangle_route_defect`).
It tests a total the filing prints for the table itself. One record: 4020/2017.

**Was it applied to all the 571?** The check was: the 13 October census covered all 573 triangle-sourced records of the
674, which are the 571 plus 4020/2017 and 1218/2015. Result: A 551, B 5, C 17. The 5 B (net tables) were repaired or
excluded. Of the 17 C, only 4020/2017 failed a printed total of the table; **the other 16 remain in the 571 unread**,
each C because its table's reserves miss CO_g by more than 2% for a reason of scope the eye placements record: older
years omitted (all 1225 years, 510/2015-2016, 2987/2015, 1880/2015-2016, 1221/2015), an earned or ultimate basis
(1225, 1919/2020, 1955/2015), or a transfer the table may not carry (1110/2020). The 16: 1110/2020, 1221/2015,
1225/2015, 1225/2017, 1225/2018, 1225/2019, 1225/2020, 1225/2021, 1225/2022, 1880/2015, 1880/2016, 1919/2020,
1955/2015, 2987/2015, 510/2015, 510/2016. None prints a gross total of latest estimates.

The displaced triangles of the 86 were not in that census (they were not triangle-sourced then). The design ran the
census's own script on them (`scan_restored.json`: A 80, B 1, C 3, D 2) and the readings settled all six: 1084/2020,
2015/2021, 2987/2023, 3000/2024 and 780/2016 reconcile exactly to gross claims outstanding on the page (the batch's
class came from a net CO_g or an unplaced total); 1225/2016 misses CO_g by 12% (480.7 against 545.9) and B1 places
the gap as the pre-2011 years the table omits (p27 '2011&prior' 106.5 less p28's 2011 reserve 40.7 = 65.8 against
65.2; 2012-2016 agree within 0.2%). So the reconciliation has now been run on all 657.

**Decision for 1225/2016: primary.** The filing prints no gross total of latest estimates and the table no total
(census D), so the rule as applied cannot fire, and the shortfall is the same omitted-years scope as 1225/2015 and
2017-2022, which are kept. It is a coverage gap (Q5), not a faulty table.

**If the author reads the paper's words more broadly** ("does not reconcile to the filing's totals", including CO_g),
17 records would leave: the 16 above and 1225/2016. Not recommended: a table that omits its older years would fail
while one that prints them as a reserve line (the 113+ records with a bucket line, Q5) would pass, for the same scope.

## Q4. Earned-basis tables whose youngest mature year is still earning

**Existing treatment.** None. The maturity proxy (`src/build_maturity_share.py`, phi = mature share of opening
reserves) and its guard (`check_maturity_denominator.py`, PHI_MIN = 0.10, "623 with a proxy, 7 failing") belong to the
maturity-denominator sensitivity only; they exclude nothing from the sample, and they measure reserve shares, not
earning. phi for 1699/2024 is 0.50 (delta inf) to above 0.10 at every weighting, 2015/2021 0.74, 780/2016 0.82,
1225/2016 0.81: the guard would not catch them. One existing rule bears on it: where a filing contradicts itself on
direction, the register reads its printed table (main.tex App 2.2, error-rate paragraph).

**Whole population** (`classify_pop.py`, text of the table's page and the page before; a lower bound, since a scanned
or reflowed page can hide the wording, and 1699/2024, 2015/2021 and 780/2016 were found only by reading):

| | 571 | 86 | 657 |
|---|---|---|---|
| earned-basis table wording ("estimates of earned ultimate", "claims on premium earned", "pure year earned", ...) | 116 | 14 (+3 by reading) | 130 (+3) |
| first diagonal only on an earned basis (218, 1856) | 8 | 0 | 8 |
| ultimate basis with the unearned portion deducted | 26 | 0 | 26 |
| filing states earning continues past the second year ("up to 24 months beyond the underwriting year", 2121; "long earning patterns", 5820) | 11 | 1 (2121/2021) | 12 |
| filing prints an unearned portion still on the t-2 cohort at year end (1225/2017-2022: e.g. 1225/2020 '(7.1)' on 2018) | 6 | 1 (1225/2016, 8.2 on 2014) | 7 |

Earning in the youngest mature cohort is in the incurred movement of many kept records, and only a reading can say
how much. **Decision under existing rules: 1699/2024, 2015/2021, 780/2016 and 1225/2016 enter the primary**, as the
earned-basis records of the 571 are in it.

**Options for the author** (one rule for all records, or none):

| Option | Records it moves | Strength | Weakness |
|---|---|---|---|
| A. No earned-basis rule; disclose (recommended) | none | the measure is the printed gross table's movement, as for the 116+ kept; no new reading | the youngest mature step of a still-earning cohort mixes earning with re-estimation (1699/2024: +22.6m while the filing says the 2022 ultimate fell) |
| B. Exclude where the filing states the t-2 cohort was still earning in year t | at least 1699/2024, 2015/2021, 1225/2016, 1225/2017-2022, 2121/2015-2024 (10), 5820/2015 and 2017: about 21, and more after reading the 130+ earned-basis records | removes the clearest cases | needs reading all earned-basis records (PC, no API); the count is open; drops 1699/2024 (S +0.372, a top donor) |
| C. For earned-basis tables, sum only u <= t-3 | every earned-basis record's figure changes (130+) | clean in principle | a second outcome definition; recomputation and a new register for 130+ records |

Recommendation: A, with a sentence in App 2.1 and a sensitivity dropping the records of B that the filing itself
names (the 21), reported beside the headline.

## Q5. "X and prior" buckets printed without development

**Does Equation (1) need the bucket's movement?** Yes: it sums over every u <= t-2, and the denominator R holds the
bucket's reserves. The computation takes "the underwriting years up to t-2 that the table develops" (App 2.1), so a
bucket printed as a reserve with no development is outside M and inside R, which pulls |S| toward zero by up to the
bucket's share.

**Does the paper disclose it?** In words, not in size: App 2.1 ("A cohort column with no development of its own is not
part of the triangle"), App 2.2 ("A triangle figure is checked over the years the filing's table prints"), and the
supplement's maturity proxy ("the triangle window omits the oldest mature years"). No count or share is given.

**Existing treatment.** Kept, throughout the 571; the ninth amendment's take-on base treats such a line as uncovered
(435/2018, 2008/2023).

**Whole population** (the census's table reserve against CO_g where both were placed; a script measure, not a
reading; 157 records have no placed table reserve and 117 print a bucket line whose share was not measured):

| | 571 | 86 | 657 |
|---|---|---|---|
| older-years column developed in the grid | 22 | 1 | 23 |
| table covers CO_g within 2% | 167 | 28 | 195 |
| reserves outside the developed years, measured | 137 | 28 | 165 |
| ... above 5% / 10% / 20% / 30% / 50% | 104 / 67 / 24 / 11 / 3 | 14 / 4 / 0 / 0 / 0 | 118 / 71 / 24 / 11 / 3 |
| bucket line printed, share not measured | 103 | 14 | 117 |
| not measured | 142 | 15 | 157 |

Median measured gap: 10%. Readers' shares among the 86: 780/2016 65%, 3000/2016 29%, 2003/2016 28%, 1084/2015 17%,
2001/2016 15%, 2525/2016 13%, 1221/2023 9%, 2010/2020 7%, 2987/2021 6%, 2010/2023 5.5%, 2987/2023 5.4%, 1084/2024
5.3%, and 13 more under 5%. Measured above 30% in the 571: 1492/2023 (70%), 5678/2016 (70%), 1176/2022 (59%),
727/2017 (47%), 2488/2015 (46%), 435/2016 (34%), 1218/2016 (34%), 2488/2017 (33%), 4472/2015 (33%), 2488/2018 (31%),
2008/2023 (31%); the first three should be read before they are trusted.

**Decision under existing rules:** the 86 are kept as the 571 are. 780/2016 (65%) enters the primary.

**Options for the author:**

| Option | Records | Strength | Weakness |
|---|---|---|---|
| A. Keep and disclose the count and share distribution (recommended) | none | the existing treatment; the definition already says "the years the table develops" | |S| understated where the bucket is large |
| B. Exclude above a share threshold (30%) | at least 12 (11 measured in the 571, 780/2016), more among the 274 unmeasured | removes the worst cases | needs the share for 274 records (a script pass, then reading); a threshold is arbitrary |
| C. Divide by the covered reserves (R less the bucket's opening reserve) | every record with a bucket | matches numerator and denominator | needs the t-1 bucket reserve per record; changes the size axis R too |

Recommendation: A, plus a sensitivity that drops records whose bucket is above 30% once the script has measured the
274 (no API; PC or cloud).

## Q6. Run-off

**Existing rules.** `run_analysis.py` excludes a year whose premium is zero, or negative with a statement of run-off
(`runoff_by_statement`), and a year the corpus register reads as run-off for the whole year, unless the year is in the
RITC regime (`whole_year_runoff`, category WHOLE; author's decision of 1 October 2026). PART, AFTER and NOTCOUNT stay.

| Record | Register | Decision |
|---|---|---|
| 5151/2020 | AFTER: 'cease underwriting with effect from 31st December 2020' (p6); the 100% LPT to the parent is effective 1 January 2021 (t+1), so it does not move year t (ninth amendment: a transfer after the balance sheet date gets no adjustment) | primary |
| 1301/2020 | PART: run-off from 10 June 2020 | primary |
| 6125/2020 | PART: run-off from November 2020 | primary |

None has a premium at or below zero (the loader ran on all 86 in `sim.py` with no run-off exit). 5151/2020's earlier
diagonals are not retranslated (A2); no rule excludes that, and 5151/2016, 2018 and 2019 share the presentation.

## Q7. Reader disagreements

- **1225/2016** (A4 table_invalid, B1 confirmed): primary. A4's reason is the 12% CO_g shortfall; B1 places it as the
  pre-2011 years the table omits; the rule needs a printed total of latest estimates and there is none (Q3). Both
  agree on +12.1. Earned basis, 8.2 unearned left on 2014 (Q4, option B would remove it).
- **1699/2024** (A2 confirmed, B1 table_invalid): primary under existing rules (Q4). Both agree on +22.635 and an
  exact reconciliation; B1's objection is earning, which no rule excludes. Option B would remove it.
- **2015/2021** (A3 confirmed, B1 table_invalid): primary under existing rules (Q4); same as 1699/2024. Both agree on
  +12.037; reconciles exactly through the companion balance-to-pay table (184.872).
- 780/2016 (both confirmed) carries both caveats: earned basis and the 65% bucket.

## Changes the rules imply OUTSIDE the 86

1. **Year-t inward transfers in the 571 never read on the take-on question** (Q1; the ninth census predates them):
   - 3330/2018: accepted the RITC of Syndicate 3334's 2012-2014 years effective 1 January 2018 (ritc_scan p6); 3334's
     transfer out was 37.982m (implementation note 7), against 3330/2018's adopted opening reserves of 11.701m, so the
     take-on may be about three times the opening reserves (figure -1.384m). Read: restated (base) or in the step (dominance).
   - 1884/2022 and 1884/2023: loss portfolio transfers from Syndicate 33 (2018 and prior; 2019 and prior), inward,
     genuine.
   - 1971/2022 and 1971/2023: standing 80-90% quota shares of Syndicate 1969's run-off years, inward, genuine.
   - 3500/2018: the 30 November 2018 LPT from Syndicate 2987 (about 560m gross) against adopted opening reserves of
     42.799m; the author decided its figure on 4 October 2026 (-0.408, "stays in the transfer regime"), but the base
     question was not asked.
   Two readings each, on the ninth amendment's question, before the refit.
2. **The 16 class-C records** (Q3): no change under the rule as applied; 16 leave if the author reads the rule broadly.
3. **Earned basis** (Q4): no change under option A; under option B at least 17 of the 571 leave (1225/2017-2022,
   2121/2015-2020 and 2022-2024, 5820/2015 and 2017), more after reading.
4. **Older-years buckets** (Q5): no change under option A; under option B at least 11 of the 571 leave (listed).
5. **2001/2022 in the 672 sensitivity**: its -256.3 includes the outward RITC's impact (p51); under 1856/2020's rule it
   may be no development figure either. Sensitivity only.
6. **6134/2023 and the transfer register**: a reassumption of earlier years under a quota share, like 1971's, is
   absent from `portfolio_transfer_adjudication.json`; relevant to the 672 sensitivity's regime only.
7. **2007/2015**: consistent; no change (Q2).

## For the author

1. Q4 earned basis: A (no rule, disclose, sensitivity on the 21 named) is recommended; B or C change the sample.
2. Q5 older-years buckets: A (keep, disclose counts, sensitivity above 30%) is recommended.
3. Q3: confirm the rule stays as applied (a printed total of the table's own), not the broad CO_g reading (17 records).
4. 1084/2022: confirm exclusion with an inferred allocation, as for 1856/2018 (the outcome is the same if read as
   undeterminable).
5. 2001/2022 in the 672 sensitivity (item 5 above).

Outstanding before any refit: register entries (two readings, pages, quote) for the 82 primary figures and the three
take-on bases; readings of the six transfer records in item 1; the share measure for the 274 unmeasured bucket
records if Q5's sensitivity is wanted. Nothing here was run on the PC's recorded pass.

## Corrections and settlements after the adjudication (22 October 2026)

Copied into the analysis repository with the five readings files (`readings/A1.json` ... `readings/B1.json`), the
decisions table (`decisions.csv`) and the design study (`design.md`, `design_per_record.csv`), from which
`src/build_mature_cohort_figures.py` builds `data/mature_cohort_figures.json`.

1. 3500/2018: the year-t transfers total GBP 199.935m (two loss portfolio transfers, both in the 2018 column). The
   "about 560m" above belongs to 3500/2019, which is already registered (`data/opening_reserves_takeon_base.json`).
2. The six transfer records of "Changes outside the 86", item 1 (3330/2018, 3500/2018, 1884/2022, 1884/2023,
   1971/2022, 1971/2023) were read twice (`readings/T1.json`, `readings/T2.json`). Both readings find every one
   `no_effect`: the year-t take-on sits in the report year's own column, outside u <= t-2, or there is none; both
   recompute the adopted figure and match the opening reserves. None needs a take-on base or a take-on entry, and none
   of their figures changes. The 1971 records' RITC-regime flag rests on the transfer register's classifier decision
   and is left as it is.
3. 6134/2023 is settled under Appendix 2.1's aggregated-column rule (a column whose last step is not the report
   year's movement is left out; without it the table holds no column up to t-2): an entry with no figure and that
   reason. 2001/2022 is settled under the rule of 1856/2020 (`data/takeon_not_development.json`: a figure the filing
   shows to be dominated by an outward transfer is not development), with the transfer the filing states (p8, GBP
   187.3m, outward). Both decisions of the Claude analysis session.
