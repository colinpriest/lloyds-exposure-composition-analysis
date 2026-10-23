# Reading brief: why 2689's 2023 table restates its end-2022 diagonal (BAJ paper)

Out of scope, always: the paper's AI declaration and anything about AI use.

Tools and discipline exactly as `D:/tmp/r62/oc/readings/brief.md` (read it first): page text tool `filing_pages.py`,
page images via `render.py` (copy PNGs you use into your own `renders/`), read only, no paid API, no network, NEVER
`cd` in Bash, Write tool for scripts, UTF-8 with LF, never invent a number, every figure with page and verbatim cells.
Write ONLY in your own folder (named in your prompt). Do not open any other reader's folder. Rewrite `readings.json`
after each step.

## The question
Syndicate 2689's 2023 report (`syndicate_2689_2023`, gross development table p46, USD'000) gives a mature-cohort gross
movement M (underwriting years u <= 2021, latest estimate less the end-2022 estimate printed in the same table) of
+42.378m USD: 2020 +2,881 (123,040 to 125,921) and 2021 +39,497 (97,435 to 136,932). But the 2022 report
(`syndicate_2689_2022`) printed different end-2022 estimates: 2020 at 81,688, 2021 at 77,230, 2022 at 33,142 (the
2023 table shows 123,040, 97,435, 33,254). Measured from the 2022 report's own diagonal, the movement would be about
104m. 2689 transferred its 2019 and prior years by an external RITC to Syndicate 1254 immediately after 31 December
2021 (2022 report p35, "External RITC (101,597)").

Find out, from both filings:
1. Is the 2023 table on the same basis as the 2022 table (gross; the same currency; underwriting year; cumulative
   incurred or ultimate; the same treatment of unexpired risk / unearned premium; the same presentation)? Quote both
   headings and any basis note.
2. Does either filing explain the restatement of the end-2022 figures (a restatement note, a change of presentation, a
   correction, a change of reserving basis, business transferred in or out, a merger, an RITC received, a quota share,
   a change of managing agent)? Quote it with its page. Search widely (`--find` for restat, represent, prior year
   adjust, change in accounting, RITC, transfer, merge, novation, quota share, reclassif).
3. Does the 2023 table reconcile to the 2023 balance sheet's gross claims outstanding, and the 2022 table to the 2022
   balance sheet's? Give both.
4. The 2023 report's own roll-forward of gross claims outstanding: opening, claims incurred (current and prior years),
   paid, RITC or transfers, FX, closing. Does its prior-year line agree with M's sign and size, or with the 104m?
5. Verdict: `development` (M is a genuine 2023 movement of the 2020-2021 underwriting years, the restatement being
   presentation only), `restated_base` (M rests on a restated base that is not 2023 development; say what the true
   2023 movement is, if the filing gives it), `transaction` (a transfer or RITC in 2023 moves the figures), or
   `undeterminable` (say why).

Output entry `2689_2023` in `readings.json`: `read_by`, `pages`, `basis_2022`, `basis_2023`, `explanation` (quotes),
`reconciliation_2022`, `reconciliation_2023`, `rollforward_2023`, `verdict`, `true_movement_m` (if given), `note`.
