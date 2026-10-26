# Census for the source-history rule: the affected population

Written 26 October 2026, 12:16 Brisbane time. Out of scope, always: the paper's AI declaration and anything about AI use.

The rule (recommendation of the Codex analysis, adopted on Colin's instruction): set aside an observation when specific
source evidence raises a material unresolved concern about overlapping claims history, gross/net mixing or cohort
reassignment through closure, and the declared gross original-cohort outcome cannot be defensibly reconstructed or
validated; regardless of the outcome's size or sign. An unexpired exposure, ordinary internal RITC, funds-withheld
arrangement, unusual business, youth or SPA status is not sufficient by itself. A calendar/triangle inequality alone is
insufficient where FX or accounting scope differs.

This file defines and lists the population the rule must assess. It decides no record: each selected record is for the
two readings (a third where they conflict). The criteria are a decision of the Claude analysis session.

## How the population was chosen

- The universe is the 643-record primary: `model/exposure_results.json` observations with `s_raw_a`, opening reserves
  and HHI present (`src/adopted_model.load_sample`), analysis `D:/tmp/r62/oc/A` (branch `oc`, 9c227e7a). Only the keys
  were read.
- Selection reads source characteristics only: what the filings say about the syndicate's structure, closures and
  presentation, and what the analysis's registers and readings already record. No outcome value (S, PYD, `figure_m`),
  sign or size was used to choose. (Two outcome values were seen incidentally and not used: the 6131 figures in the
  Codex note and the round-5 screen file, and the cells quoted in the 4472/2022 confirmed-figure entry.)
- The criteria were fixed from the rule's three mechanisms and the registers' structure, then applied by script
  (`s20_build_population.py`) to every primary record.

## Timing

M is the difference between two diagonals of the year t report's gross table (end of t less end of t-1, cohorts
u <= t-2). A closure changes what those diagonals measure when it takes effect at the opening of year t (1 January t,
the same instant as 31 December t-1) or during year t: the year t table may then show the closed or acquired years on
one diagonal and not the other, or restate them "as if always", and the year t-1 report's base differs. A closure that
took effect before the opening of year t sits behind both diagonals; one at the close of year t (a subsequent event)
is not in the year t table. So S2, S3, S6 and H use the window "at the opening of or during year t". S1 has no window,
because an SPA's years close every year (36-month ventures by RITC into the next venture or the host).

## Selection criteria (any one selects the record)

**S1 SPA vehicle.** The syndicate's own filing (any year of the corpus) says the syndicate is or was a Special Purpose
Arrangement or Special Purpose Syndicate writing a quota share of a host, and at least one selected cohort (u <= t-2)
is a year of account it wrote as an SPA. Lloyd's 61xx numbering is a cross-check, not the test. Why: SPA years run as
ventures on a funds-withheld quota share and close by net RITC into the next venture or the host; this is the structure
in which 6131/2021's overlapping closed-venture history and gross/net RITC arose.

**S2 Inward closure into the syndicate's own cohorts.** Another syndicate's liabilities (external or merger RITC, an
accepted loss portfolio or portfolio transfer, or an SPA's year accepted by its successor syndicate) were taken into the
syndicate at the opening of or during year t, as the analysis's registers record (`src/assumed_business.sources`:
`pdf_extraction/ritc_scan.json` `ritc_occurred`, `pdf_extraction/audit/portfolio_transfer_adjudication.json` genuine
inward or both, `data/opening_reserves_takeon_base.json`), round-5 rule 5b, or the year t filing. Excluded: Lloyd's
internal RITC between the syndicate's own years (settled), and a closure whose ceding party is the syndicate's own SPA
(that is H).

**S3 Outward closure of the syndicate's own cohorts.** Some of the syndicate's own years of account were reinsured to
close or transferred to another syndicate at the opening of or during year t: `data/outbound_transfer_retained_base.json`
(confirmed, and named_not_adjusted except the two entries the register itself places elsewhere), or the transfer
adjudication's outward entries.

**S4 Gross/net signature on the selected table.** A reading or register reports, for the table the selected outcome
uses, net figures labelled gross, gross and net cells that coincide for a cohort that carries reinsurance, or a net RITC
amount inside gross cumulative claims, and no register has resolved it. (It selects no record beyond S1: 6131/2021's
signature is part of its S1 evidence, and 4472/2022's is resolved by `data/pyd_confirmed_figures.json`.)

**S5 Another vehicle's closed-year development passed into a selected cohort.** The year t filing states a continuing
arrangement (an experience account) under which development on another syndicate's closed year accrues to one of the
selected cohorts.

**S6 Partial reallocation between the syndicate's own years through a closure.** At the opening of or during year t a
class or share of business moved between the syndicate's own years of account under an RITC agreement (not the ordinary
whole-year internal RITC).

**H Host side of an SPA closure (conditional).** The syndicate's own SPA closed a year of account into it at the opening
of or during year t (the host reassuming the share it ceded). Listed apart because the host's gross table already holds
100% of the business it ceded; Colin decides whether H is read (see the final section).

Not criteria, by the rule: an SPA as counterparty, a host's quota share cession, ordinary internal RITC, funds withheld,
run-off status, unexpired exposure, youth, unusual business, a calendar/triangle inequality, outcome size or sign.

## How 6131/2020 and 6131/2021 enter

Both enter by S1, by the same test: 6131 is Dale's SPA from the 2018 year of account (whole account quota share of host
1729, funds withheld; syndicate_6131_2021.pdf p5, p20), and the selected cohorts are SPA ventures (2018 for the 2020
record; 2018 and 2019 for the 2021 record). 6131/2021 also carries Codex's specific evidence (the 2019 cumulative paid
row reproduces the closed 2018 venture's gross paid plus the outgoing 2019 net RITC; the 2018 row equal on gross and net
bases), which is the rule's first case. 6131/2020 is selected by the same criterion and is to be read under the same
protocol; Codex reports that its 2018 cohort is bridged by the separate 2018 closing account, with no inherited
predecessor year. Neither record's disposition is decided here.

## For Colin to decide

1. **Host side (H, 20 records).** Include in the readings or not. Facts: 4242's roll-forwards (2020 to 2022) enter
   "RITC accepted from SPA 6123" with the gross column '-' (reinsurance assets and net only); 1686/2021 p21 says the
   SPA 6129 elimination had no impact on total gross; but 2791's underwriting accounts show a gross RITC premium
   receivable from 6103 each year, and reading Z1 calls 2791's 6103 wording an "as if always" restatement. Options:
   (a) read all 20 twice (cost: 40 readings); (b) one reading each that checks only whether the SPA closure enters the
   host's gross roll-forward or triangle, and a second only where it does (about 20 to 26 readings); (c) leave H out
   (cost nil; risk: 2791's six records unchecked). Recommendation: (b), because the mechanism is a single factual
   check per filing and the 4242 and 1686 evidence suggests most hosts are unaffected on the gross basis.
2. **S1 breadth.** All 34 SPA records, or only those whose filing records a closure in the window. Recommendation: all
   34, because every SPA year closes by RITC and the 6131 problem sat in the venture history, not in a dated event.
3. **2088 (SPS for 2012 to 2014, stand-alone from 2015).** Its five records qualify under S1 because their selected
   cohorts include SPS years; the later ones are mostly stand-alone years. Recommendation: keep all five (the test is
   the same for every syndicate).
4. **Later years after a closure (T1, 47 records)** are out by the timing argument; some (4000/2023 and 4000/2024, whose
   2018 and 2019 columns are Syndicate 3334's years) carry another syndicate's history in their selected cohorts,
   consistently on both diagonals. Recommendation: out, as listed.
5. **Round-5 history records not otherwise selected (T2).** They were read twice under rules that test the year t table
   against the year's accounts; the new rule's validation limb is met where they tie. Recommendation: out.
6. **Recall.** 1,377 pages of the 643 primary filings have no text layer and no committed OCR text (most in 2024
   filings, e.g. 33/2024 107 pages, 1969/2024 85, 1971/2024 81); a statement on those pages is not seen. Recall check
   for S1: a self-statement scan of every corpus filing (all years, 947 filings) of every primary syndicate
   (`s16_spa_selfscan.py`, `spa_selfscan.json`) found no SPA beyond the 17 syndicates S1 already uses; its other hits
   are hosts naming their SPA (1969 of 6133, 4000 of 6110, 1492 of the AdA SPA). It also dates 5623's SPA years from
   2018 (syndicate_5623_2018.pdf p5).
7. **Size of the work.** Core 81 records (two readings each, 162) plus H by your choice above. No count of exclusions
   is implied: the rule sets a record aside only when the readings find the concern material and unresolved.
