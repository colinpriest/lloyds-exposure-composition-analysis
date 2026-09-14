r"""The editor's carry-over decisions for the ninth amendment's take-on base census (point 4), recorded before any new
reading, for the 34 listed records the eighth census read in its takeon_triangle part.

A record keeps both eighth-census readings when both answer where the adopted figure's table carries the transferred
business and how much was transferred. Each carried answer is as that reading states it; its gross opening reserves are
the first reading's filing figure and, for the second reading, the adopted figure its text confirms ('as adopted').
Six records are read afresh: the first readings of 2008/2023, 4444/2017 and 4444/2018 do not say where the business
sits, and both readings of 3500/2021, 3500/2022 and 3500/2023 recorded note 7's whole 'Reinsurance of new liabilities',
which holds loss portfolio transfers carried in the report year's own column (and, in 2023, a transfer that replaces
one the opening reserves already hold), so the part the figure covers is not settled.

    python record_carry_ninth.py carry_decisions_ninth.py
"""
import io
import json
from pathlib import Path

SCR = Path(__file__).resolve().parent
_FIRST = {v["stem"]: v for v in json.load(io.open(str(SCR / "error-rate-verdicts-eighth.json"), encoding="utf-8"))}
_BRIEFS = {b["stem"]: b for b in json.load(io.open(str(SCR / "error-rate-briefs-ninth.json"), encoding="utf-8"))}


def carried(key, finding, amounts, first_text, second_text, reason):
    stem = "syndicate_" + key
    return {"carry": True, "reason": reason,
            "first": {"finding": finding, "takeon_amount_m": amounts[0],
                      "gross_opening_m": (_FIRST[stem].get("opening_reserves") or {}).get("filing_m"),
                      "carried": first_text},
            "second": {"finding": finding, "takeon_amount_m": amounts[1],
                       "gross_opening_m": _BRIEFS[stem]["adopted_opening_reserves_m_report_currency"],
                       "carried": second_text}}


def fresh(reason):
    return {"carry": False, "reason": reason}


RESTATED_6103 = "Syndicate 6103's reinsurances to close are shown as if always 2791's liabilities, so both diagonals of the step carry them"
D = {
    "1084_2021": carried("1084_2021", False, (40.4, None),
                         "no transfer in the 2021 report: its only RITC, Syndicate 2088's, is a 2022 event; the 6130 RITC is in the 2020 report, and 6130 only reinsured the syndicate as host",
                         "no transfer in this report's claims notes; 6130, an SPA that reinsured the syndicate, held none of its gross business",
                         "both readings find no transfer the 2021 figure covers"),
    "1084_2023": carried("1084_2023", False, (95.0, 95.0),
                         "Syndicate 2088's RITC came on 1 January 2022, in the end-2022 diagonal and the opening reserves",
                         "the 2088 RITC was effected on 1 January 2022; no transfer is recorded in 2023",
                         "both readings: the only transfer came in an earlier year"),
    "1110_2020": carried("1110_2020", False, (6.2, 6.2),
                         "Syndicate 3330's RITC went into the 2019 year of account, the ADC and the QBE LPT into 2020: t-1 and t columns",
                         "the 3330 RITC is in the 2019 year of account and the ADC and QBE LPT in 2020, outside the years summed",
                         "both readings place the 2020 transfers outside the step"),
    "1110_2022": carried("1110_2022", True, (None, None),
                         "the table restates earlier diagonals to include the 5678 RITC business (a 2018 column with a full history); the ADC is in the 2022 column; no transferred amount stated",
                         "the table restates the history to include the acquired business; the ADC sits in the 2022 column; the report states no transferred amount",
                         "both readings: the 5678 RITC is restated onto both diagonals, and neither finds an amount in the filing"),
    "1254_2023": carried("1254_2023", False, (0.0, 0.0),
                         "the 2023 inwards RITC line is nil; the 2022 RITC is shown look-through in every diagonal",
                         "no transfer into the syndicate in 2023 (the inwards RITC line is nil)",
                         "both readings: no transfer in 2023"),
    "1686_2020": carried("1686_2020", False, (None, None),
                         "the RITC of Syndicates 2007 and 6129 took effect at the end of 2020 into the 2019 year of account; the 2020 movement has no transfer line",
                         "the 2020 movement has no transfer line, and the business would sit in the 2019 column",
                         "both readings: no transfer in the 2020 accounts"),
    "1856_2024": carried("1856_2024", True, (96.61, 96.61),
                         "the 3268 RITC of 1 January 2024 is restated into the data before 2022 (p63), so both diagonals carry it",
                         "the table restates the earlier data to include the 3268 RITC (p63); the diagonals' change matches claims incurred",
                         "both readings: restated onto both diagonals, 96.61m gross (note 13)"),
    "1884_2021": carried("1884_2021", True, (839.787, 839.787),
                         "the table restates every diagonal to include the assumed 2018 years of Syndicates 1861 and 1955 (p33)",
                         "the table shows the assumed reserves by pure underwriting year with every diagonal restated",
                         "both readings: restated onto both diagonals, 839.787m gross (note 3)"),
    "1969_2022": carried("1969_2022", False, (None, None),
                         "the 6133 RITC is an event after the balance sheet date, and 6133 was a quota-share reinsurer of the syndicate's own business",
                         "the 6133 RITC is a subsequent event; note 6 has no transfer line",
                         "both readings: no transfer in 2022"),
    "1969_2023": carried("1969_2023", False, (None, None),
                         "the 6133 and 1971 RITCs are events after the balance sheet date; both were quota-share reinsurers; no transfer line in 2023",
                         "the RITCs are subsequent events of quota-share reinsurers; note 6 has no transfer line",
                         "both readings: no gross transfer in 2023"),
    "2003_2019": carried("2003_2019", False, (532.922, None),
                         "the S1209 RITC is the 2018 comparative: in the end-2018 balance and both diagonals of the 2019 step",
                         "note 12's 2019 reconciliation has no transfer line; the S1209 RITC is the 2018 comparative",
                         "both readings: the transfer came in 2018, an earlier year"),
    "2008_2023": fresh("the first reading leaves open whether Syndicate 1301's business sits on both diagonals or in the provision in respect of prior years"),
    "2488_2019": carried("2488_2019", True, (143.759, 143.759),
                         "p49: the periods before 2019 include Syndicate 1882's data, so the end-2018 diagonal is restated",
                         "p49: the end-2018 diagonal the step starts from already holds 1882's business",
                         "both readings: restated onto both diagonals, 143.759m gross (note 16)"),
    "2791_2015": carried("2791_2015", True, (4.168, 4.168), RESTATED_6103, RESTATED_6103, "both readings: restated, 4.168m gross"),
    "2791_2017": carried("2791_2017", True, (0.102, 0.102), RESTATED_6103, RESTATED_6103, "both readings: restated, 0.102m gross"),
    "2791_2018": carried("2791_2018", True, (0.041, 0.041), RESTATED_6103, RESTATED_6103, "both readings: restated, 0.041m gross"),
    "2791_2022": carried("2791_2022", True, (1.903, 1.903), RESTATED_6103, RESTATED_6103, "both readings: restated, 1.903m gross"),
    "2791_2023": carried("2791_2023", True, (7.411, 7.411), RESTATED_6103, RESTATED_6103, "both readings: restated, 7.411m gross"),
    "2791_2024": carried("2791_2024", True, (3.694, None), RESTATED_6103, RESTATED_6103,
                         "both readings: restated; the second records no amount, and 3.694m is under 5% of the opening reserves"),
    "3000_2017": carried("3000_2017", False, (0.0, 0.0),
                         "the 2017 RITC line is nil; Syndicate 1400's RITC came in 2016 and is restated",
                         "the RITC line is nil for 2017",
                         "both readings: no transfer in 2017"),
    "3268_2020": carried("3268_2020", True, (20.66, 20.66),
                         "the 2017 column starts at two years later (end-2019), before 3268 held the business: the diagonal the step starts from carries it",
                         "the 2017 column starts at the end-2019 diagonal, which already carries the transferred business",
                         "both readings: restated onto both diagonals, 20.66m gross (note 4)"),
    "3268_2021": carried("3268_2021", False, (0.0, 0.0),
                         "note 4's 2021 RITC row is nil",
                         "note 4's 2021 RITC row is nil",
                         "both readings: no transfer in 2021"),
    "3330_2017": carried("3330_2017", False, (None, None),
                         "the 2017 RITC moved liabilities between 3330's own years of account; nothing entered the syndicate",
                         "the 1 January 2017 RITC is between 3330's own years of account; the 3334 RITC is not in these accounts",
                         "both readings: no transfer into the syndicate in 2017"),
    "3500_2019": carried("3500_2019", True, (552.752, 552.752),
                         "p23: the RITC liabilities are shown in their original underwriting years, 2011-2016, with earlier diagonals restated",
                         "p23: the liabilities are shown in their original underwriting years, so the 2011-2016 columns carry them on both diagonals",
                         "both readings: restated onto both diagonals, 552.752m gross (note 7); the table has no 2019 column"),
    "3500_2021": fresh("both readings recorded note 7's 2,425.117m, which holds loss portfolio transfers carried in the 2021 column"),
    "3500_2022": fresh("both readings recorded note 7's 1,728.476m, which holds loss portfolio transfers carried in the 2022 column"),
    "3500_2023": fresh("both readings recorded note 7's 3,225.818m, which holds a 183.2m LPT in the 2023 column and a transfer replacing a 2022 LPT the opening reserves hold"),
    "4000_2023": carried("4000_2023", False, (181.247, None),
                         "no transfer in 2023: note 14 has no RITC row; the 3334 RITC came in 2022",
                         "note 14's 2023 reconciliation has no transfer line; the 3334 transfer came in 2022",
                         "both readings: no transfer in 2023"),
    "435_2017": carried("435_2017", False, (None, None),
                        "the Syndicate 2255 RITC took effect on 1 January 2018",
                        "the 2255 RITC took effect on 1 January 2018; the table holds none of 2255's liabilities",
                        "both readings: no transfer in 2017"),
    "435_2018": carried("435_2018", False, (83.8, 83.8),
                        "the 2255 business sits in the 2010 and prior column, which prints no estimates; the 2011-2016 columns are the 2017 report's retranslated",
                        "the 2011-2016 cells are the 2017 report's retranslated; the 2010 and prior reserve rises and prints no estimates",
                        "both readings: the transfer is outside the figure"),
    "4444_2016": carried("4444_2016", False, (None, None),
                         "the Syndicate 260 RITC is not booked in the 2016 accounts",
                         "note 24 has no RITC line; the 260 loan remains at the year end",
                         "both readings: no transfer in 2016"),
    "4444_2017": fresh("the first reading does not say which column carries Syndicate 260's business, booked as 'Other 37,196'"),
    "4444_2018": fresh("the first reading does not say where Syndicate 958's business sits, only that it is not in the step"),
    "4444_2023": carried("4444_2023", True, (313.953, 313.953),
                         "p26: the 2019 and 2020 columns include the business assumed from Syndicate 1861, restated",
                         "p26: the 2019 and 2020 columns include 1861's business on both diagonals",
                         "both readings: restated onto both diagonals, 313.953m gross (note 25)"),
}
DECISIONS = {"syndicate_" + k: v for k, v in D.items()}
