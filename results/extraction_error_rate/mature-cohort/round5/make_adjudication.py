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
                 "restated_base, Q7 undeterminable: the same validity class. Nothing changes.",
    "3500_2023": "RITCs of seven syndicates and an LPT effective 1 January 2023 (p5, p30-31; note 7 'Reinsurance of new "
                 "liabilities 3,225,818'), the history 2-3.6 times the 2022 report's. R is 5,803.136m USD = 2,962.436 + "
                 "2,840.7 (the register's amount leaves out the 201.9m LPT already in the opening and the 183.2m LPT). "
                 "Nothing changes. Flag: the table's movement does not tie to note 7's change in estimates (-52.1m for "
                 "u <= 2022 against -184.8m, P7; Q8: neither ties); rule 1 does not reach it (the history change is "
                 "explained) and no rule covers an explained take-on table that fails the tie.",
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
                 "the RITC and ADC through premium and claims incurred (353.8m) with no transfer line, and neither reading "
                 "prints the transferred gross amount (P7's 'about 270m' is the change in the balance sheet, an "
                 "inference). Rule 5 applies but cannot be applied: no entry, record unchanged, OUTSTANDING (a reading of "
                 "the transferred gross amount).",
    "1458_2024": "a stated external RITC 'in the year' of the 2020 and 2021 underwriting years shown in the history (p47); "
                 "note 4's roll-forward (p31) has no RITC line and neither reading gives the amount (P1: +164m of restated "
                 "incurred history, not reserves). Whether R carries the acquired reserves cannot be told: no entry, "
                 "record unchanged, OUTSTANDING (a reading of the amount and its effective date). The M stands at "
                 "-33.258m (both readings).",
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
         "Decision of the Claude analysis session, 23 October 2026, applying the decision rules of `rules.md` (written "
         "before the adjudication) record by record to the 83 records of the round: the 82 records the rebase screen "
         "(`screen/rebase_screen.py` over the primary's 649 records at 35a259c) asked to read, each read by one P-arm and "
         "one Q-arm reader (`readings/P1..P8`, `Q1..Q8`, brief `briefs/brief_r5.md`), and 2689/2023 (V1, V2; W1, W2 "
         "recomputed its figure; `briefs/brief_2689.md`). The two records whose readings disagreed on the facts "
         "(1609/2024, 4444/2017) were decided on the tie-break readings Z5 and Z6 (`briefs/brief_r6.md`). Every number "
         "below is a reader's, with the page the reader gives, or the session's arithmetic on cells the readers quote.", "",
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
         "- Rule 1's control. Two of the five rule-1 records do not tie within 5% on the raw incurred control: 4747/2024 "
         "(-7.2%, while its outstanding ties exactly and the year t miss is -81.9%) and 780/2016 (+9.5%, the same gap the "
         "'2010 & prior' years outside the cells make in year t). The session read the control as tying once its basis "
         "is allowed for, as the rule allows the year t test. This is the session's reading of the rule, flagged for "
         "the author: read strictly, both would fall outside rule 1 and no other rule, and would stand.",
         "- Rule 1 does not reach a year t-1 column: 2015/2022's table restates only its UY2021 column (outside M) and "
         "stands.", ""]
counts = {}
for k, a in adj.items():
    counts.setdefault(a["outcome"], []).append(k)
lines += ["## Outcomes", "", "| outcome | rule | records | keys |", "|---|---|---|---|"]
for o in ("excluded", "corrected", "take_on_base", "take_on_base_and_least_certain", "take_on_amount_not_read",
          "least_certain", "stands"):
    ks = sorted(counts.get(o, []), key=order)
    rules = sorted({adj[k]["rule"] for k in ks})
    lines.append("| %s | %s | %d | %s |" % (o, ", ".join(rules), len(ks), ", ".join(ks)))
lines += ["", "Primary at 35a259c: 649 records. Leaving: the five of rule 1 and 3000/2022 (rule 2): 643. Four figures "
          "corrected. The 25 records of rule 6 stay and join the least-certain sensitivity.", ""]

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
          "exchange factor (+19.871m). The year's exchange factor is the 2008 column's end-2015 cell over the 2015 "
          "report's, 209,137 / 213,518 = 0.979482 (both readers quote both cells; the screen's common factor; the other "
          "years run 0.968-0.989).", "",
          "- corrected 2012 end-2015 cell: 178,987 x 0.979482 = 175,314.5",
          "- 2012 term: 185,418 - 175,314.5 = +10,103.5",
          "- other six years (2008 -681, 2009 +564, 2010 +2,491, 2011 +3,607, 2013 -3,166, 2014 +10,625): +13,440",
          "- M = 13,440 + 10,103.5 = +23,543.5, i.e. +23.5435m USD (GBP 19.084m at the loader's rate), against +57.503m "
          "as printed",
          "- check: the table's implied incurred with the corrected cell is 260,042 - 44,063 + 10,103.5 = 226,082.5 "
          "against 230,541 in the accounts (-1.9%; the paid test ties at -1.9% either way)", "",
          "The readings support the correction's inputs and the diagnosis (both call the cell a misprint and quote every "
          "cell used; Q4 makes the same replacement); neither gives the exchange-adjusted figure, which is the session's "
          "arithmetic on their cells, as rules.md instructs. The build recomputes it from each reader's own quoted cells "
          "(`build_mature_cohort_figures.misprint_figure`).", ""]


def section(title, keys, body):
    out = ["## %s" % title, ""]
    for k in sorted(keys, key=order):
        out.append("### %s (rule %s: %s)" % (k, adj[k]["rule"], adj[k]["outcome"]))
        out.append("")
        for rid, v in READS[k]:
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
lines += section("Rules 3 and 4: corrected", [k for k in adj if adj[k]["outcome"] == "corrected"], corr_body)
lines += section("Rule 5: take-on bases", [k for k in adj if adj[k]["rule"].startswith("5")], lambda k: WHY[k])
lines += section("Rule 6: least certain, stays", [k for k in adj if adj[k]["outcome"] == "least_certain"], hist_body)
lines += section("Rule 7: stands", [k for k in adj if adj[k]["outcome"] == "stands"], lambda k: "Rule 7: " + WHY[k])
missing = [k for k in adj if adj[k]["outcome"] in ("stands", "take_on_base", "take_on_base_and_least_certain",
                                                   "take_on_amount_not_read") and k not in WHY]
if missing:
    raise SystemExit("no reason written for %s" % missing)
with io.open(out_path, "w", encoding="utf-8", newline="") as fh:
    fh.write("\n".join(lines) + "\n")
print("wrote %s (%d lines)" % (out_path, len(lines)))
