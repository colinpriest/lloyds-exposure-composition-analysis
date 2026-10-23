"""Write the round-5 adjudication (adjudication.md) from repo A's registers and the archived readings, with the
session's reasons for the records no register bucket carries. Usage: make_adjudication.py <repo> <out.md>"""
import io
import json
import os
import sys

repo, out_path = sys.argv[1:3]
sys.path.insert(0, os.path.join(repo, "src"))
import build_restated_base_excluded as rb  # noqa: E402
import build_mature_cohort_figures as bm  # noqa: E402

with io.open(os.path.join(repo, "data", "restated_base_excluded.json"), encoding="utf-8") as fh:
    REG = json.load(fh)
with io.open(os.path.join(repo, "data", "mature_cohort_figures.json"), encoding="utf-8") as fh:
    MC = json.load(fh)
with io.open(os.path.join(repo, "data", "fx_untranslated_excluded.json"), encoding="utf-8") as fh:
    FX = json.load(fh)
READS = rb.load_readings()

#: the session's reasons for the records of rules 5 and 7 (facts from both readings, pages as the readings give them)
WHY = {
    # rule 5: take-on bases
    "1686_2021": "RITC of Syndicates 2007 and 6129 into the 2019 year of account, effective 1 January 2021, shown as if "
                 "always in the 2016-2018 columns (p6, p9; p25 'Effect of RITC 903,214'); the table ties (incurred +0.26%, "
                 "control +3.7%). The analysis's R is 2,076.819m USD = 1,173.605 + 903.214 (take-on base register): R "
                 "already includes the transfer, nothing changes.",
    "1856_2024": "RITC of Syndicate 3268 effective 1 January 2024, its data in the pre-2022 periods (p63; note 13 p101 "
                 "'RITC from Syndicate 3268 96,610'); the table ties (incurred -3.8%). R is 696.978m = 600.368 + 96.61: "
                 "already includes it.",
    "1884_2021": "RITC of the 2018 years of account of Syndicates 1861 and 1955 effective 1 January 2021, as if always "
                 "(p4, p33); the closing reserve ties. R is 913.496m = 73.709 + 839.787: already includes it.",
    "2488_2019": "RITC of Syndicate 1882 effective 1 January 2019, its data in the earlier periods (p49, p7; 143.8m "
                 "gross); incurred -3.8%. R is 1,100.269m = 956.51 + 143.759: already includes it.",
    "3000_2016": "RITC of Syndicate 1400's 2013 year of account accepted 1 January 2016, the table restated as if always and "
                 "revalued (p38; p37 'RITC accepted from Syndicate 1400 248,822'). R is 986.744m = 737.922 + 248.822: "
                 "already includes it. P4 valid, Q5 restated_base on the same facts: rule 6's label clause also lists it.",
    "3500_2022": "RITCs of Syndicates 1897, 2468, 1980/2014/2001 effective 1 January 2022 and LPTs in 2022 (p4; note 7 p30 "
                 "'Reinsurance of new liabilities 1,728,476'), the history re-bucketed with them. R is 3,955.045m USD = "
                 "2,615.345 + 1,339.7 (the 1 January RITCs; the amount is the ninth census's decision). The mature "
                 "columns move -291.8m against note 7's change in estimates incl. FX of -293.1m (0.4%, P6). P6 "
                 "restated_base, Q7 undeterminable: the same validity class. Rule 5 changes nothing. After review 8 "
                 "(decision of the Claude analysis session, 23 October 2026) it joins 3500/2023 on the least-certain "
                 "list under the rule-6 clause take_on_table_unreconciled, on the same all-prior-years scope: the "
                 "table's movement on every column that existed at end-2021 (2013-2019 and 2021) is -291.756m - "
                 "98.057m = -389.8m against note 7's -293.1m, and the whole table is -26.4m, a gap of 266.7m (P6, "
                 "Q7); only the 2013-2019 columns alone tie (0.4%). The readings conflict on the loss portfolio "
                 "transfers: P6 reads the mid-2022 LPTs of Syndicates 1200 and 1686 (293.8m and 67.1m) as entering "
                 "the history as if always, the ninth census (data/opening_reserves_takeon_base.json) places all four "
                 "LPTs (388.7m) in the 2022 column, outside M and R. Either way the acquired share outside R is at most "
                 "9.1% of R (360.9m of 3,955.0m; 9.8% with all four), so rule 5b would list it too "
                 "(data/restated_base_excluded.json, history_restated).",
    "3500_2023": "RITCs of seven syndicates and an LPT effective 1 January 2023 (p5, p30-31; note 7 'Reinsurance of new "
                 "liabilities 3,225,818'), the history 2-3.6 times the 2022 report's. R is 5,803.136m USD = 2,962.436 + "
                 "2,840.7 (the register's amount leaves out the 201.9m LPT already in the opening and the 183.2m LPT). "
                 "Rule 5 changes nothing. The table's movement does not tie to note 7's change in estimates (-52.1m for "
                 "u <= 2022 against -184.8m, P7; Q8: neither ties); rule 1 does not reach it (the history change is "
                 "explained) and no rule covered an explained take-on table that fails the tie. Round 7 (23 October "
                 "2026): it stays in the primary and joins the least-certain list, under the rule-6 clause "
                 "take_on_table_unreconciled (data/restated_base_excluded.json, history_restated).",
    "4000_2022": "RITC of Syndicate 3334 effective 1 January 2022, the 2019 column as if always (p5); the table ties "
                 "(incurred +3.2%, control +1.1%). R is 555.661m = 374.414 + 181.247: already includes it.",
    "4444_2018": "RITC of Syndicate 958's 2015 year of account effective 1 January 2018, as if always; the balance to pay "
                 "ties (1,949,555); incurred +6.1% on an ultimate basis. R is 1,824.548m = 1,547.219 + 277.329: already "
                 "includes it.",
    "4444_2023": "screen misread (end-2021 cells read as end-2022); 2019 and 2020 rebased x1.7 and x1.5 by the stated RITC "
                 "of Syndicate 1861's 2020 year of account from 1 January 2023 (gross provision +313,953). R is "
                 "2,681.837m = 2,367.884 + 313.953: already includes it.",
    "1110_2022": "RITC of Syndicate 5678's 2018 and 2019 years of account and the Hiscox ADC in 2022 (p5, p33), the history "
                 "carried as if always (2017 column x5.98, 2019 x2.09); R is the opening 221.885m alone. The accounts book "
                 "the RITC and ADC through premium and claims incurred (353.8m) with no transfer line, and neither "
                 "round-5 reading prints the transferred gross amount (P7's 'about 270m' is the change in the balance "
                 "sheet, an inference). Round 7 (brief_r7.md, readings U1, U2; 23 October 2026) read the filing for the "
                 "amount: it is not printed (the gross roll-forward, p27, has no transfer row), the Hiscox ADC is "
                 "INWARD (the Gibson Re quota share is outward and moves the reinsurers' share only), reserves rise from "
                 "221.885m to 489.603m and gross written premium from 1.366m to 333.442m; U2 derives a take-on of about "
                 "221.9m less the unknown development on the opening book, about 100% of R. Rule 5b: the acquired share "
                 "could exceed 10% of R by a wide margin, so the record leaves the primary as an unmeasurable take-on "
                 "(data/restated_base_excluded.json, bucket takeon_unmeasurable, tag TAKEON_BASE_UNMEASURABLE; the "
                 "existing data/takeon_not_development.json does not fit: its entries describe the step of a displaced "
                 "mature-cohort figure and apply under a figure_route this record's own triangle figure does not have).",
    "1458_2024": "a stated external RITC 'in the year' of the 2020 and 2021 underwriting years shown in the history (p47); "
                 "note 4's roll-forward (p31) has no RITC line and neither round-5 reading gives the amount (P1: +164m of "
                 "restated incurred history, not reserves). Round 7 (U1, U2; 23 October 2026): the amount is not printed; "
                 "the only ADC is outward and dated 2020; R (USD 2,050.580m, GBP 1,637.71m) is the filing's opening and "
                 "holds no acquired reserves. The filing bounds the take-on: the acquired cumulative incurred at the "
                 "latest comparable ages is USD 164.078m (+105.138m on the 2020 column, +58.940m on the 2021 column), and "
                 "the reserves taken on cannot exceed it: at most 8.0% of R. The table carries the acquired years as if "
                 "always, so the movement within it (-33.258m USD = -26.56m GBP, u <= 2022, equal to the analysis figure) "
                 "excludes the take-on. Rule 5b: bounded at or below 10% of R, so the record stays and joins the "
                 "least-certain list (data/restated_base_excluded.json, history_restated, clause take_on_base_bounded).",
    # rule 7: stands
    "382_2017": "screen misread: it compared balance-sheet pages and read an incremental table as levels (no identity "
                "evidence); M from the printed increments +7.401m equals the analysis figure (P7, Q6).",
    "382_2020": "screen misread (incremental table, wrong pages); the end-2019 history differs by the stated closing-rate "
                "retranslation (-1.6% to -5.7%); the re-cut of the first two rows and UY2019 are outside M; M +29.62m.",
    "435_2016": "screen misaligned (end-2014 cells); aligned, the history is the 2015 report's times a uniform 1.12-1.19, "
                "the stated December-2016 retranslation (+15.2% on opening); M -44.233m.",
    "510_2015": "screen compared the 2015 gross table with the 2014 net table (no 2014 gross table); incurred +4.8%; M +0.1m.",
    "1084_2016": "the only flagged year is u = 2015 (t-1, outside M); mature years 1.03-1.075 (translation); M +3.4m.",
    "1218_2016": "screen compared the 2016 gross table with the 2015 net table; net to net a uniform 1.12-1.15; M -8.941m.",
    "1274_2022": "screen took the year t net table; on the gross table a stated 2-3% retranslation, incurred +0.25% "
                 "(control 0.2%); M +8.96m.",
    "1274_2024": "screen compared with the 2023 net table (its row label misprinted 'gross'); gross history moves by a "
                 "uniform 0.986 (stated retranslation); incurred -0.4%; M +53.399m.",
    "1301_2016": "the only flagged year is u = 2015 (t-1): a change from ultimate to earned basis; mature columns move by the "
                 "common exchange ratio; M -1.6m (P4 valid, Q5 screen_misread: same class).",
    "1416_2024": "units slip in the stored 2024 grid ('millions' by default; printed $'000); M's scale unaffected (-0.302m "
                 "equals the stored figure); the 2022 column moves -1.5%.",
    "1492_2019": "units and currency slip in the stored 2018 grid; no restatement beyond the stated closing-rate rebasing; "
                 "M +10.889m.",
    "1856_2021": "the 2019 and 2020 end-2020 cells fall by the 2020 report's unearned claims reserve (31.2m) as the 2021 "
                 "table moved to an earned basis, stated in its footnote (Q1; P2 reports the same footnote); the table "
                 "ties (incurred -0.4%, paid -3.5%); explained, M -16.186m stands.",
    "1880_2015": "screen compared the 2015 gross table with the 2014 net ultimate table (no 2014 gross table); incurred "
                 "-1.2%; M -5.8m.",
    "1897_2019": "the history moves by the stated retranslation and by the 2016 Property class transferred to the 2017 "
                 "year of account under the syndicate's own RITC (p33): an internal RITC between its own years is not a "
                 "take-on (Lloyd's internal RITC rule); the table ties (incurred -6.1% on an underwriting-year basis, "
                 "control 2.9%); M +11.964m. Both readings note the 2017 term may carry the transferred claims.",
    "1910_2016": "the only flagged year is u = 2015 (t-1); the mature years move by the stated balance-sheet-rate "
                 "retranslation; M -8.28m.",
    "1945_2016": "the history moves by the stated closing-rate retranslation (1.10-1.17), both readings; incurred ties once "
                 "the ultimate basis is allowed for (control 2.1%); M -10.776m.",
    "1945_2018": "the one outlier (2013, ratio 0.755) is a defect of the 2017 report's table (both readings); M from the "
                 "2018 table's own cells; the table ties (+11.5% on an ultimate basis, paid +1.5%); M +8.067m.",
    "1947_2020": "the 2019 report's 2018 cell is a misprint (the outstanding printed as the estimate, paid '-'), both "
                 "readings; the 2020 table ties; M -3.502m.",
    "1955_2023": "screen used end-2021 cells; the right cells differ by the retranslation (0.94-0.98); the table ties within "
                 "2%; M +6.565m.",
    "1967_2022": "the 2021 report's 2020 cell (216,548) is a misprint of 416,548 proved by its own paid and balance rows "
                 "(both readings); the 2022 table ties (-2.6%); M +45.457m.",
    "2007_2016": "a change from an ultimate table with an unearned deduction (2015) to an earned table (2016), plus the "
                 "retranslation (both readings); the screen's factor was not an exchange ratio; the table ties (+6.5%); "
                 "M +54.8m.",
    "2015_2022": "the mature cells move by the stated retranslation (1.08-1.09); only the year t-1 column (UY2021) is "
                 "restated, +28.4m beyond FX and unexplained, which is why the whole-table incurred test misses (-28.5%); "
                 "rule 1 reads the history of u <= t-2 or the table as a whole, and M's years are untouched; M +3.421m.",
    "2121_2018": "the flagged 2017 cell (t-1) is a misread 121,848; the rest is the stated 5.4% retranslation; M +27.589m.",
    "2357_2024": "the stored 2024 grid's units default to 'millions' (printed $'000); the analysis figure -64.757m is in the "
                 "right scale; the history moves at most -2.5%.",
    "2623_2023": "screen set the $m triangle against the 2022 report's percentage block; the $m rows agree within 0.5%; the "
                 "table ties (paid +2.7%, incurred +0.8%); M -472.2m.",
    "2786_2024": "label slip in the stored 2024 grid (USD millions); both printed tables are GBP thousands; the table ties "
                 "(-1.6%); the analysis figure +5.989m is in the right scale (P7 screen_misread, Q6 units_slip: same "
                 "class).",
    "2791_2022": "screen misaligned the 2021 table (its greyed '2010 and prior' column); every year moves by the stated "
                 "1.10-1.12; M -17.497m (the round-2 decision on its older-years column stands).",
    "2988_2020": "label slip in the stored 2019 grid; the base moved 2.1-2.6% uniformly (stated); M +3.155m.",
    "3000_2018": "the history moves by the stated year-end revaluation; the flagged 2013 move comes from a faulty 2017 print "
                 "(both readings); the reallocation P7 names in 2011 and 2014 is under the screen's 1%-of-R flag, and the "
                 "end-2017 reserve agrees with the 2017 report within 0.7%; M +17.88m.",
    "3624_2018": "a change of presentation currency to US dollars (1.32-1.34 on every mature year); only the t-1 first-year "
                 "cell is a misprint; M +22.902m.",
    "4444_2022": "the screen's year t cells were one column off; the history moves 1.07-1.10 (translation); the table ties "
                 "(3.3%, control 3.2%); the figure +34.9m is the confirmed one (data/pyd_confirmed_figures.json).",
    "4472_2022": "screen compared the 2022 net table with the 2021 gross; gross to gross the stated retranslation only; the "
                 "analysis figure +122.3m is the gross table's (Q5 notes the stored 2022 grid holds the net block under a "
                 "gross label: the adopted figure does not come from it).",
    "4472_2024": "screen compared the 2024 gross table with the 2023 net table; gross to gross 1.006-1.016; the table ties "
                 "(4.0%, control -3.0%); M +216.776m.",
    "5000_2018": "a zero-filled blank read by the screen; a uniform 1.036-1.054 retranslation; the table ties (+2.4%, paid "
                 "0.05%); M +38.47m.",
    "5151_2020": "screen compared against a zero placeholder; the history is identical; the table ties (paid -1.2%, "
                 "incurred -1.4%); M +68.015m.",
    "5678_2016": "an alignment artefact; the history moves by the FX factor 1.13-1.15; M +0.861m.",
    "6107_2023": "screen compared $m with a loss-ratio percentage grid on the wrong page; the history is unchanged within "
                 "1.4%; the table ties; M -11.6m.",
}


def m_of(v):
    for f in ("m_recomputed_m", "M_m_usd", "recomputed_mature_figure_m"):
        x = v.get(f)
        if isinstance(x, (int, float)):
            return x
        if isinstance(x, dict):
            for g, y in x.items():
                if isinstance(y, (int, float)) and g.startswith(("from_t_table", "rows_are", "on_2017_table")):
                    return y
    return None


def pct(t):
    if not isinstance(t, dict):
        return None
    for f in ("diff_pct", "t_diff_pct", "diff_pct_own_table"):
        if f in t and t[f] is not None:
            return t[f]
    for sub in ("year_t", "t"):
        if isinstance(t.get(sub), dict):
            return t[sub].get("diff_pct")
    return None


def reading_line(rid, v):
    return "%s %s, M %s, paid %s, incurred %s" % (rid, v.get("verdict"), m_of(v), pct(v.get("paid_test")),
                                                   pct(v.get("incurred_test")))


adj = REG["_adjudicated"]
order = rb.order_key
lines = ["# Round-5 adjudication: tables whose history moved between reports", "",
         "Decision of the Claude analysis session, 23 October 2026, applying the decision rules of `rules.md` record by "
         "record (rules 1 to 7 were written before the adjudication; rule 5b, rule 6's take-on clause and rule 1's exact "
         "control clause were added after particular readings or review 8, and `rules.md` names them) to the 83 records "
         "of the round: the 82 records the rebase screen "
         "(`screen/rebase_screen.py` over the primary's 649 records at 35a259c) asked to read, each read by one P-arm and "
         "one Q-arm reader (`readings/P1..P8`, `Q1..Q8`, brief `briefs/brief_r5.md`), and 2689/2023 (V1, V2; W1, W2 "
         "recomputed its figure; `briefs/brief_2689.md`). The two records whose readings disagreed on the facts "
         "(1609/2024, 4444/2017) were decided on the tie-break readings Z5 and Z6 (`briefs/brief_r6.md`). Every number "
         "below is a reader's, with the page the reader gives, or the session's arithmetic on cells the readers quote.", "",
         "Round 7 (23 October 2026, same session): the two take-ons whose transferred amount the round-5 readings did not "
         "print (1110/2022, 1458/2024) were read again for the amount (readings U1 and U2, `briefs/brief_r7.md`), and "
         "rule 5b was added to `rules.md` before they were applied: a take-on the filing does not print leaves the "
         "primary as an unmeasurable take-on when the readings show the acquired share of the base could exceed 10% of "
         "R, and stays on the least-certain list when the filing bounds it at or below 10%. 3500/2023, whose take-on is "
         "in R but whose table does not reconcile with note 7, joined the least-certain list under rule 6's added "
         "clause. The outcomes below are those after round 7 and review 8.", "",
         "Review 8 (23 October 2026, same session; the decisions below are those of the Claude analysis session after "
         "the review's findings): 4242/2022 moves from rule 1 to rule 3 (the 2021 report's printed base reconciles with "
         "the accounts once the merged '2016 & Prior' column is set aside; both readers give -80.015m USD); rule 1's "
         "control clause is made exact and re-applied to every record; 3500/2022 joins the least-certain list; "
         "1274/2016's corrected figure becomes a derived one (+22.694m USD, the 2012 column's own exchange factor), "
         "kept apart from the readers' figures, and the record joins the list; 2001/2016 was checked against rule 6's "
         "1% of R and stays. Rules 1 to 7 were written before the adjudication; rule 5b, rule 6's take-on clause "
         "(take_on_table_unreconciled) and rule 1's exact control clause were added after particular readings or the "
         "review (`rules.md` names them).", "",
         "## How the rules were read", "",
         "- Validity classes. A 'label' disagreement (rule 6) is one between the classes valid, screen_misread, units_slip "
         "and restated_base, undeterminable (the classes `compare_r5.py` uses for 'VERDICTS DIFFER'). A record whose two "
         "readings agree on the cells and the tests but not on the class is a label disagreement; one whose readings give "
         "different cells, figures or test results is a fact disagreement and went to a third reading (1609/2024, "
         "4444/2017).",
         "- Rule 6's first clause reads the screen's flag (a year u <= t-2 moved more than 5% beyond the common exchange "
         "factor and by more than max(1% of R, 1m)) together with the readings: the move is 'without explanation' when "
         "neither reading finds a cause in either filing (a stated retranslation explains a uniform move, not a "
         "year-specific one; a misprint in the year t-1 report, a basis change the filing states, an RITC, or a screen "
         "misread explains it).",
         "- Rule 1's control (made exact on 23 October 2026, after review 8, and re-applied to every record). The year "
         "t-1 control ties within 5%; or within 10% when the same basis gap explains both years (an '& prior' column "
         "outside the cells, an ultimate basis against earned accounts) and the year t miss is at least three times the "
         "control's. Two of the four rule-1 records need the 10% clause: 780/2016 (control +9.5% from the '2010 & prior' "
         "years outside the cells; year t paid identity +79.8%, 8.4 times) and 4747/2024 (control -7.2%, outstanding "
         "tying exactly; year t -81.9%, 11.4 times; neither reader names its basis gap, which the session reads as the "
         "table's own underwriting-year basis, the place the clause leans on judgement). Under the exact clause "
         "2232/2017, 2488/2016, 382/2021, 1967/2017 and 1729/2023 do not meet rule 1 and stay on the least-certain "
         "list, each entry saying why. Re-applying the clause to every record changed no outcome: 780/2016 and "
         "4747/2024 meet it only through its 10% branch, and 4242/2022's move from rule 1 to rule 3 did not come from "
         "the clause (its control, -1.1%, ties under either reading) but from review 8's separate decision to set aside "
         "the merged '2016 & Prior' column.",
         "- Rule 1 does not reach a year t-1 column: 2015/2022's table restates only its UY2021 column (outside M) and "
         "stands.", ""]
counts = {}
for k, a in adj.items():
    counts.setdefault(a["outcome"], []).append(k)
lines += ["## Outcomes", "", "| outcome | rule | records | keys |", "|---|---|---|---|"]
for o in ("excluded", "corrected", "corrected_least_certain", "take_on_base", "take_on_base_and_least_certain",
          "take_on_unmeasurable", "take_on_bounded_least_certain", "least_certain", "stands"):
    ks = sorted(counts.get(o, []), key=order)
    rules = sorted({adj[k]["rule"] for k in ks})
    lines.append("| %s | %s | %d | %s |" % (o, ", ".join(rules), len(ks), ", ".join(ks)))
lines += ["", "Primary at 35a259c: 649 records. Leaving: the four of rule 1, 3000/2022 (rule 2) and 1110/2022 (rule 5b, after "
          "the round-7 readings): 643. Five figures corrected (318/2024, 1274/2016, 1609/2024, 2232/2020, 4242/2022). "
          "The 29 records listed under history_restated (the 25 of rule 6, 1458/2024 under rule 5b, 3500/2023 and "
          "3500/2022 under rules 5 and 6, and 1274/2016 under rules 4 and 6) stay and join the least-certain "
          "sensitivity.", ""]

lines += ["## Label disagreements settled by the rules", ""]
for k in sorted(adj, key=order):
    vs = [(rid, e.get("verdict")) for rid, e in READS[k] if rid[0] in "PQVZ"]
    cl = {("v" if v in rb.VALID else "i") for _, v in vs if v in rb.VALID + rb.INVALID}
    if len(cl) > 1 or len({v for _, v in vs}) > 1:
        lines.append("- %s: %s. %s" % (k, ", ".join("%s %s" % p for p in vs),
                                       {"1609_2024": "Fact disagreement (literal against transposed reading): the "
                                                     "tie-break readers Z5 and Z6 both read the body as transposed "
                                                     "(+13.935m USD), so rule 4.",
                                        "4444_2017": "Fact disagreement on whether the year's flows tie: Z5 and Z6 "
                                                     "confirm Q8's facts (restated_base, moderate confidence); rule 1 is "
                                                     "not met on a same-table basis (incurred +6.3%, paid +30.8% only as a "
                                                     "cross-report proxy), so rule 6."}.get(
                                           k, "Same facts; the rule decides: %s (rule %s)." % (adj[k]["outcome"],
                                                                                             adj[k]["rule"]))))
lines.append("")

lines += ["## 1274/2016: the corrected figure (rule 4)", "",
          "Both readings quote the same cells of the 2016 table (p41, USD'000): the 2012 column runs 102,670 / 158,484 / "
          "174,440 / 141,355 / 185,418, so its end-2015 cell (141,355) sits between 174,440 and 185,418 and implies a "
          "reserve of 12,005 against 47,564 in the 2015 report, whose own 2012 cell is 178,987 (p41). P3 reads it as a "
          "misprint 'not correctable from the filing'; Q4 reads it as a misprint and gives the replacement without the "
          "exchange factor (+19.871m). Before review 8 the exchange factor was the 2008 column's end-2015 cell over the "
          "2015 report's, 209,137 / 213,518 = 0.979482 (the screen's common factor; the other years run 0.968-0.989). "
          "Review 8 changed it: the replaced cell belongs to the 2012 column, so the column's own factor is used, from "
          "its paid cells at end-2015, which both readers quote and which the misprint does not touch: 129,350 (2016 "
          "table) against 131,423 (2015 report), f = 0.98423.", "",
          "- corrected 2012 end-2015 cell: 178,987 x 0.98423 = 176,163.7",
          "- 2012 term: 185,418 - 176,163.7 = +9,254.3",
          "- other six years (2008 -681, 2009 +564, 2010 +2,491, 2011 +3,607, 2013 -3,166, 2014 +10,625): +13,440",
          "- M = 13,440 + 9,254.3 = +22,694.3, i.e. +22.6943m USD (GBP 18.395m at the loader's rate), against +57.503m "
          "as printed and +23.5435m before review 8 (the 2008 column's factor)",
          "- check: the table's implied incurred with the corrected cell is 260,042 - 44,063 + 9,254.3 = 225,233.3 "
          "against 230,541 in the accounts (-2.3%; the paid test ties at -1.9% either way)",
          "- range: the other columns' end-2015 ratios (0.96766 to 0.98919) as the factor give +21.806m to +25.659m "
          "(review 8: +21.8m to +25.6m); no factor (the 2015 cell as printed) gives Q4's +19.871m", "",
          "The readings support the correction's inputs and the diagnosis (both call the cell a misprint and quote every "
          "cell used); neither gives the figure. It is the session's derivation from cells both readers quote, stored "
          "apart from the readers' own figures (derived_figure_m; each reading keeps its figure_m, +57.503m as printed), "
          "allowed only while both readers quote every cell used and the derivation is recorded. The build recomputes it "
          "from each reader's own quoted cells (`build_mature_cohort_figures.misprint_figure`). Because it rests on a "
          "choice of factor, 1274/2016 also joins the least-certain list (rule 6, clause derived_correction).", ""]


def section(title, keys, body):
    out = ["## %s" % title, ""]
    for k in sorted(keys, key=order):
        out.append("### %s (rule %s: %s)" % (k, adj[k]["rule"], adj[k]["outcome"]))
        out.append("")
        for rid, v in READS[k]:
            if rid in rb.AMOUNT_READERS:
                g = v["gross_transferred_in"]
                out.append("- %s (round 7, the transferred gross amount): %s; opening R %s, closing %s" % (
                    rid, "not printed" if g.get("value_m") is None else "%s" % g["value_m"],
                    v["opening_R"]["value_m"], v["closing"]["value_m"]))
            else:
                out.append("- %s" % reading_line(rid, v))
        out.append("- %s" % body(k))
        out.append("")
    return out


def excl_body(k):
    c = REG["excluded"][k]["conditions"]
    return ("Rule 1. History differs, unexplained: %s. Year t fails the accounts: %s. Control ties: %s. The year t-1 "
            "base does not reconcile: %s. Outcome: excluded (data/restated_base_excluded.json, tag "
            "RESTATED_BASE_TABLE)." % (c["history_differs_unexplained"]["facts"], c["year_t_fails_accounts"]["facts"],
                                       c["control_ties"]["facts"], c["previous_base_reconciles"]["facts"]))


def corr_body(k):
    e = MC[k]
    return ("%s. Cause: %s. Derivation: %s. Outcome: corrected from %s to %s (report currency, %s), "
            "data/mature_cohort_figures.json, displaced.by %s." % (
                e["correction"]["rule"][:6].capitalize(), e["correction"]["cause"], e["correction"]["derivation"],
                e["correction"]["figure_as_printed_m"], e["figure_m"], e["report_currency"], e["displaced"]["by"]))


def hist_body(k):
    e = REG["history_restated"][k]
    return ("Rule 6 (%s): %s. Outcome: stays in the primary, listed under history_restated." % (
        ", ".join(e["clauses"]), e["facts"]))


fx = FX["excluded"]["3000_2022"]
lines += section("Rule 1: excluded", REG["excluded"], excl_body)
lines += section("Rule 2: excluded under the author's rule B", ["3000_2022"], lambda k: (
    "Both readings: the 2022 table's end-2021 incurred and cumulative paid are both lifted by the same amount in every "
    "column (2013: +20,536 on each; P2 and Q1), so the paid history is retranslated (about 8%%) and the end-2021 reserves "
    "are not, and (end-2022 less end-2021) mixes exchange bases; the gross roll-forward prints 'Movement due to foreign "
    "exchange 91,879' on an opening 1,146,474 (note 17, p42; balance sheet p25): %.2f%% of R. Neither filing explains the "
    "history. Rule 2 decides before rule 1. Outcome: excluded (data/fx_untranslated_excluded.json)." % fx[
        "fx_line_pct_of_opening"]))
lines += section("Rules 3 and 4: corrected", [k for k in adj if adj[k]["outcome"].startswith("corrected")], corr_body)
lines += section("Rule 5: take-on bases", [k for k in adj if adj[k]["rule"].startswith("5")], lambda k: WHY[k])
lines += section("Rule 6: least certain, stays", [k for k in adj if adj[k]["outcome"] == "least_certain"], hist_body)
lines += section("Rule 7: stands", [k for k in adj if adj[k]["outcome"] == "stands"], lambda k: "Rule 7: " + WHY[k])
missing = [k for k in adj if adj[k]["outcome"] in ("stands", "take_on_base", "take_on_base_and_least_certain",
                                                   "take_on_unmeasurable", "take_on_bounded_least_certain")
           and k not in WHY]
if missing:
    raise SystemExit("no reason written for %s" % missing)
with io.open(out_path, "w", encoding="utf-8", newline="") as fh:
    fh.write("\n".join(lines) + "\n")
print("wrote %s (%d lines)" % (out_path, len(lines)))
