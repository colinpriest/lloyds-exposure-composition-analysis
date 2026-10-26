# Reading brief, round 9: the source-history rule census (BAJ paper)

Out of scope, always: the paper's AI declaration and anything about AI use.

Tools and discipline exactly as `D:/tmp/r62/oc/readings/brief.md` (read it first) and the round-5 brief
`D:/tmp/r62/oc/readings/brief_r5.md` (the incurred and paid tests, the verdict style). Filings: PDFs in
`D:/tmp/r62/finalv/Efull` (HTML filings via its converted copies; image pages via the OCR cache in
`D:/tmp/r62/finalv/E`). Write ONLY in your own folder (named in your prompt). Do not open any other reader's folder,
`D:/tmp/r62/oc/codex/`, or any adjudication. Rewrite `readings.json` after each record. No paid API; no network.
LLOYDS_EXTRACTION_OFFLINE=1. Never `cd` in Bash; scripts with the Write tool, never heredocs.

## The rule being applied (to every record in your batch, whatever its outcome's size or sign)
"Set aside an observation when specific source evidence raises a material unresolved concern about overlapping claims
history, gross/net mixing or cohort reassignment through closure, and the declared gross original-cohort outcome cannot
be defensibly reconstructed or validated. An unexpired exposure, ordinary internal RITC, funds-withheld arrangement,
unusual business, youth or SPA status is not sufficient by itself. A calendar/triangle inequality alone is insufficient
where FX or accounting scope differs."

The outcome: M = sum over underwriting years u <= t-2 of (the end-year-t cell less the end-year-(t-1) cell) in the
year-t report's GROSS claims development table (t = the reporting year), divided by the opening gross claims
outstanding R. Your batch file gives each record's selection criterion and evidence (why it was chosen: SPA vehicle,
inward or outward closure, a continuing arrangement, an own-years transfer, or the host side of an SPA closure).

## For each record, report from the pages (cells with page, unit, currency)
1. The gross development table used (page; heading; basis: earned, ultimate, incurred; any '& prior' column) and the
   cells of u <= t-2 at both dates; compute M. If the filing is a combined report for several syndicates, confirm the
   table is this syndicate's.
2. The selection event: what closed, transferred or was taken in, when (effective date), and which cohorts it touched.
   Did it fall at the opening of year t or during year t (so between the two diagonals), or outside them?
3. Overlapping history: does any u <= t-2 row carry another vehicle's or another year's history (a closed venture's
   paid history, an acquired book shown "as if always", a cohort reassigned or merged)? Quote the evidence.
4. Gross/net: is any cell or row on a net basis, or equal on gross and net where it should not be, or does a net RITC
   premium or recovery enter a gross row? Compare the gross and net tables where both print.
5. The accounts test (incurred first): implied gross incurred for year t from the table (latest diagonal less the one
   before, all printed years) against the year's gross claims incurred in the accounts (paid plus change in gross
   provision; page); the same for year t-1 from the previous report where it prints a table (the control). Paid test
   only where the table gives no implied incurred.
6. Can the gross original-cohort outcome M be defensibly reconstructed or validated (a bridge: cumulative cells against
   paid plus outstanding by cohort, a closing account, a roll-forward)? Say how, or why not.
7. Verdict: `stands` (no material unresolved concern), `concern_resolved` (a concern, and the outcome is reconstructed
   or validated: say how), `set_aside` (a material unresolved concern and no defensible reconstruction), or
   `undeterminable` (the pages do not settle it). Give the reason in two or three sentences.

For host-side records (the syndicate's own SPA closed a year into it at the opening of or during year t): say first
whether the SPA closure enters the host's GROSS roll-forward or triangle at all (a gross RITC accepted line, a gross
premium receivable, an "as if always" restatement), then items 3-7.

Specific checks: 33/2021-24 (a combined Hiscox report for Syndicates 33 and 6104: confirm the table is Syndicate 33's,
and whether the named RITC is the SPA's own closing); 3000/2017 (the 1400 RITC was effective 1 January 2016: is the 2017
flag only the comparative year?); 6131/2020 and 6131/2021 (SPA ventures; the 2018 and 2019 closing accounts, if in the
corpus); 2088/2015-19 (an SPS 2012-14, stand-alone from 2015).

## Report
`readings.json`: per record, the items above with cells and pages, the verdict and reason. Final message: one line
per record (id, verdict, reason in a few words), and anything that contradicts the batch file's evidence.
