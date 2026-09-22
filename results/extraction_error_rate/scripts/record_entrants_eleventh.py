r"""The eleventh and twelfth amendments' readings (error-rate-protocol.md; implementation notes 9 and 11), recorded
from the readers' reports in tenth-census/entrants/readings/: the five records the tenth amendment's repairs brought
into the working sample, the one unread donor entering Vignette 1's top 20, and 1609/2023, which the second reader
found in passing and a third reader read again (eleventh amendment); and 1729/2024, the one unread donor entering the
top 20 of the refit after those repairs (twelfth amendment).

Each verdict and figure below is transcribed from the reports (reader-C.txt to reader-G.txt), in the report's
currency, and each outcome is the register entry it led to (data/pyd_confirmed_figures.json), which the script
checks. Writes tenth-census/entrants/entrants-result.json.

    python results/extraction_error_rate/scripts/record_entrants_eleventh.py
"""
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
OUT = os.path.join(ROOT, "results", "extraction_error_rate", "tenth-census", "entrants", "entrants-result.json")
REG = os.path.join(ROOT, "data", "pyd_confirmed_figures.json")

RECORDS = [
    {"stem": "3010_2022", "why": "entered the working sample; first of Vignette 1's top 20 in the refit",
     "currency": "USD", "adopted_m": 146.569, "adopted_route": "model reading of the provisions note's prior-year line",
     "readings": {"C": {"verdict": "error", "figure_m": -10.926},
                  "D": {"verdict": "correct as a reading (refinement 2); the paper's rule gives the triangle figure",
                        "figure_m": -10.926}},
     "outcome": "repaired", "figure_m": -10.926,
     "note": ("both readings give the printed gross triangle over underwriting years 2013-2020; the note's line carries "
              "the 2021 year (+157.640m, 108% of it); implementation note 9, point 3")},
    {"stem": "2468_2014", "why": "entered the working sample", "currency": "GBP", "adopted_m": 27.7,
     "adopted_route": "model reading of the directors' report",
     "readings": {"C": {"verdict": "error", "figure_m": None}, "D": {"verdict": "error", "figure_m": None}},
     "outcome": "unknown basis", "figure_m": None,
     "note": ("a net attribution of the year's loss, including a fall in reinsurance recoveries; the filing states no "
              "gross prior-year movement and prints no triangle")},
    {"stem": "1458_2018", "why": "entered the working sample", "currency": "GBP", "adopted_m": 45.431,
     "adopted_route": "gross triangle",
     "readings": {"C": {"verdict": "correct", "figure_m": 45.431}, "D": {"verdict": "correct", "figure_m": 45.431}},
     "outcome": "stands", "figure_m": 45.431, "note": "the narrative's -1.7m is net and by accident year"},
    {"stem": "1609_2024", "why": "entered the working sample", "currency": "USD", "adopted_m": -0.185,
     "adopted_route": "gross triangle",
     "readings": {"C": {"verdict": "correct", "figure_m": -0.185}, "D": {"verdict": "correct", "figure_m": -0.185}},
     "outcome": "stands", "figure_m": -0.185, "note": "the note's -15.263m is split by year of loss"},
    {"stem": "3623_2024", "why": "entered the working sample", "currency": "USD", "adopted_m": -56.671,
     "adopted_route": "gross triangle",
     "readings": {"C": {"verdict": "correct", "figure_m": -56.671}, "D": {"verdict": "correct", "figure_m": -56.671}},
     "outcome": "stands", "figure_m": -56.671, "note": "the stated -55.001m agrees within tolerance"},
    {"stem": "1969_2018", "why": "an unread donor entering Vignette 1's top 20 (rank 20)", "currency": "USD",
     "adopted_m": 80.1, "adopted_route": "gross triangle",
     "readings": {"C": {"verdict": "correct", "figure_m": 80.1}, "D": {"verdict": "correct", "figure_m": 80.1}},
     "outcome": "stands", "figure_m": 80.1, "note": "the stated 48.466m is net"},
    {"stem": "1609_2023", "why": "found in passing by reader D, read a second time by reader E", "currency": "USD",
     "adopted_m": 11.657, "adopted_route": "gross triangle, read as labelled",
     "readings": {"D": {"verdict": "error (found in passing)", "figure_m": 8.834}, "E": {"verdict": "error", "figure_m": 8.834}},
     "outcome": "repaired", "figure_m": 8.834,
     "note": "the 2023 table is printed transposed; the 2022 and 2024 tables and the 2021 year's loss ratios show it"},
    {"stem": "1729_2024",
     "why": "an unread donor entering Vignette 1's top 20 after the eleventh amendment's repairs (rank 20; twelfth "
            "amendment)",
     "currency": "USD", "adopted_m": 77.918, "adopted_route": "gross triangle",
     "readings": {"F": {"verdict": "correct", "figure_m": 77.918}, "G": {"verdict": "correct", "figure_m": 77.918}},
     "outcome": "stands", "figure_m": 77.918,
     "note": ("the printed gross triangle over underwriting years 2014-2022 gives it exactly, and the opening reserves "
              "are right; the models' 39.5 was three drivers the commentary prints in sterling")},
]


def main():
    reg = json.load(io.open(REG, encoding="utf-8"))
    for r in RECORDS:
        e = reg.get(r["stem"])
        if r["outcome"] == "stands":
            if e is not None:
                raise SystemExit("%s stands but is registered" % r["stem"])
            continue
        if e is None or e.get("figure_m") != r["figure_m"]:
            raise SystemExit("%s: the register does not hold the outcome (%s)" % (r["stem"], e and e.get("figure_m")))
        if r["outcome"] == "unknown basis" and e.get("basis") != "unknown":
            raise SystemExit("%s: the register's basis is %s" % (r["stem"], e.get("basis")))
    out = {"_about": ("the eleventh and twelfth amendments' readings and outcomes (implementation notes 9 and 11), "
                      "transcribed from tenth-census/entrants/readings/ by "
                      "results/extraction_error_rate/scripts/record_entrants_eleventh.py"),
           "recorded": "2026-09-22", "records": RECORDS,
           "read_n": len(RECORDS),
           "amendment_n": sum(1 for r in RECORDS if not r["why"].startswith("found in passing")),
           "repaired": [r["stem"] for r in RECORDS if r["outcome"] == "repaired"],
           "excluded": [r["stem"] for r in RECORDS if r["outcome"] == "unknown basis"],
           "stands": [r["stem"] for r in RECORDS if r["outcome"] == "stands"]}
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with io.open(OUT, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(out, indent=1, ensure_ascii=False) + "\n")
    print("read %d: repaired %s, excluded %s, stand %d" % (len(RECORDS), out["repaired"], out["excluded"],
                                                           len(out["stands"])))
    return 0


if __name__ == "__main__":
    sys.exit(main())
