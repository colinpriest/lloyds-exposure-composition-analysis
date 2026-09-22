r"""The tenth amendment's censuses (error-rate-protocol.md): three mechanisms a frozen external review found on
21 September 2026, and the records found in passing.

Each census is computed from the state before the repairs, with the rule the repair applies:

  first-year   run_analysis.no_mature_cohort: a lone model reading with no route, the two readings disagreeing, and
               no triangle year up to t-2. 1884/2016 defines it.
  provision    run_analysis.declares_provision_movement: the adopted model's own notes describe its figure as the
               year's movement in the claims provision, or as closing less opening outstanding. 1884/2016,
               3622/2017 and 6107/2020 define it.
  transfer     a working-sample record whose development figure a route filled after both models left it blank,
               each blaming a transfer (src/test_filled_blank_transfers.blamed_on_a_transfer), with the regime that
               held it before R221 (the RITC scan and the transfer register at the extraction commit the analysis
               last copied) and after (assumed_business.sources() now). 1856/2018 and 3268/2020 define it.
  premium      premium mixes whose class sum falls below 80% of a total two independent readings agree on within 2%:
               the investigation's census, copied under tenth-census/partial-premium/ with its script. 1856/2018
               defines it.

The records found in passing are listed with the two readings' verdicts (tenth-census/readings/). Nothing here reads
a filing. The adopted block is resolved as load_and_classify resolves it; the working sample is the committed
model/exposure_results.json's. The script refuses unless the analysis's records and results are still the committed
ones, and unless each part lists the records that define it.

    python results/extraction_error_rate/scripts/make_census_tenth.py
"""
import csv
import datetime
import glob
import io
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
OUT = os.path.join(ROOT, "results", "extraction_error_rate", "tenth-census")
sys.path.insert(0, os.path.join(ROOT, "src"))

import assumed_business  # noqa: E402
import run_analysis as ra  # noqa: E402
from test_filled_blank_transfers import blamed_on_a_transfer  # noqa: E402


def git(*args):
    r = subprocess.run(["git", "-C", ROOT] + list(args), capture_output=True)
    if r.returncode:
        raise SystemExit("git %s: %s" % (" ".join(args), r.stderr.decode("utf-8", "replace")))
    return r.stdout.decode("utf-8")


def adopted(record):
    models = record.get("models") or {}
    keys = sorted(models)
    if not keys:
        return None
    if (record.get("validation") or {}).get("passed") is True:
        return models[keys[0]]
    cands = [(k, models[k].get("prior_year_movement_confidence", 0) or 0) for k in keys
             if models[k].get("prior_year_development_pct") is not None]
    if not cands:
        return None
    return models[cands[0][0] if len(cands) == 1 else max(cands, key=lambda x: x[1])[0]]


def main():
    dirty = git("status", "--porcelain", "--", "pdf_extraction/syndicate_*.json", "model/exposure_results.json")
    if dirty.strip():
        raise SystemExit("the census reads the committed records and results; these have changed:\n" + dirty)
    head = git("rev-parse", "HEAD").strip()
    ex = json.load(io.open(os.path.join(ROOT, "model", "exposure_results.json"), encoding="utf-8"))
    ws = {"%s_%s" % (o["syndicate"], o["year"]) for o in ex["observations"]
          if o.get("s_raw_a") is not None and o.get("opening_reserves_gbp_m") and o.get("hhi") is not None}

    first_year, provision, blamed = [], [], []
    for path in sorted(glob.glob(os.path.join(ROOT, "pdf_extraction", "syndicate_*_*.json"))):
        stem = os.path.basename(path)[len("syndicate_"):-len(".json")]
        rec = json.load(io.open(path, encoding="utf-8"))
        cm = adopted(rec)
        if cm is not None:
            if ra.no_mature_cohort(rec, cm, int(stem.split("_")[1])):
                first_year.append({"stem": stem, "in_working_sample": stem in ws,
                                   "figure_m": cm.get("prior_year_development_gbp_m"),
                                   "triangle_years": sorted(set(ra.triangle_years(rec)))})
            sentence = ra.declares_provision_movement(cm)
            if sentence:
                provision.append({"stem": stem, "in_working_sample": stem in ws,
                                  "figure_m": cm.get("prior_year_development_gbp_m"), "notes_say": sentence})
        if blamed_on_a_transfer(rec):
            blamed.append(stem)

    # the regime before R221: the RITC scan and the register as the analysis last copied them (HEAD)
    scan_before = json.loads(git("show", "HEAD:pdf_extraction/ritc_scan.json"))
    reg_before = json.loads(git("show", "HEAD:pdf_extraction/audit/portfolio_transfer_adjudication.json"))
    before = {k for k, v in scan_before.items() if isinstance(v, dict) and v.get("ritc_occurred")}
    before |= {r["stem"] for r in reg_before["records"] + reg_before.get("found_by_hand", [])
               if r.get("verdict") == "genuine" and r.get("direction") in ("inward", "both")}
    after = assumed_business.sources()
    transfer = [{"stem": k, "in_working_sample": k in ws, "in_regime_before": k in before,
                 "sources_after": after.get(k)} for k in sorted(blamed)]

    rows = list(csv.DictReader(io.open(os.path.join(OUT, "partial-premium", "m03_census_final.csv"), encoding="utf-8")))
    by_mech = {}
    for r in rows:
        by_mech.setdefault(r["mechanism"], [0, 0])
        by_mech[r["mechanism"]][0] += 1
        by_mech[r["mechanism"]][1] += r["working_sample"] == "True"
    premium = {"by_the_rule": len(rows), "by_the_rule_in_working_sample": sum(r["working_sample"] == "True" for r in rows),
               "added_on_its_own_grid": ["1225_2017"],
               "total": len(rows) + 1, "total_in_working_sample": sum(r["working_sample"] == "True" for r in rows) + 1,
               "by_mechanism": {k: {"records": v[0], "in_working_sample": v[1]} for k, v in sorted(by_mech.items())},
               "defines_it": "1856_2018" in {r["stem"].replace("syndicate_", "") for r in rows}}

    passing = [
        {"stem": "3334_2018", "verdict": "error", "adopted_m": -37.982, "filing_figure_m": 5.109,
         "what": "an outward reinsurance-to-close transfer of the run-off years adopted as development",
         "repair": ("confirmed figure (data/pyd_confirmed_figures.json); the opening reserves stay the printed "
                    "116.773m, pending the owner's answer (implementation note 7)")},
        {"stem": "1206_2014", "verdict": "error", "adopted_m": 31.6, "filing_figure_m": 23.342,
         "what": "one class's calendar-year incurred claims adopted as the prior-year movement",
         "repair": "confirmed figure (data/pyd_confirmed_figures.json)"},
        {"stem": "1856_2018", "verdict": "take-on inside the step", "adopted_m": 59.638, "filing_figure_m": None,
         "what": "15.4% of Syndicate 1955's 2015-and-prior reserves, 55-85% of the step (about 69% at the centre)",
         "repair": ("a take-on, not development (data/takeon_not_development.json): the protocol's eighth "
                    "amendment, point 5 (implementation note 6); the record is in the RITC regime")},
        {"stem": "1856_2020", "verdict": "commutation inside the step", "adopted_m": -62.513, "filing_figure_m": None,
         "what": "the same quota share commuted back to Syndicate 1955, about 76-79% of the step",
         "repair": ("a transfer, not development (data/takeon_not_development.json), the recommendation put to "
                    "the owner, applied pending the answer (implementation note 7)")},
        {"stem": "1971_2024", "verdict": "not a transfer year", "adopted_m": 10.055, "filing_figure_m": None,
         "what": "a standing run-off quota share of 1971's own SPA shares, effective 31 December 2023",
         "repair": "none: the figure stands"},
    ]

    checks = {"first-year lists 1884/2016": any(r["stem"] == "1884_2016" for r in first_year),
              "provision lists 1884/2016, 3622/2017, 6107/2020":
                  {"1884_2016", "3622_2017", "6107_2020"} <= {r["stem"] for r in provision},
              "transfer lists 1856/2018 and 3268/2020": {"1856_2018", "3268_2020"} <= set(blamed),
              "premium lists 1856/2018": premium["defines_it"]}
    failed = [k for k, ok in checks.items() if not ok]
    if failed:
        raise SystemExit("the census does not list the records that define it: %s" % failed)
    out = {"_about": ("the tenth amendment's censuses, computed on the committed state before the repairs "
                      "(results/extraction_error_rate/scripts/make_census_tenth.py)"),
           "generated": datetime.datetime.now().astimezone().isoformat(timespec="minutes"),
           # the day the two readers read the records found in passing (tenth-census/readings/)
           "recorded": "2026-09-21",
           "analysis_commit": head, "working_sample_n": len(ws),
           "first_year": first_year, "provision_movement": provision, "transfer_blamed_blanks": transfer,
           "partial_premium": premium, "found_in_passing": passing, "checks": checks}
    os.makedirs(OUT, exist_ok=True)
    with io.open(os.path.join(OUT, "census-tenth-result.json"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(out, indent=1, ensure_ascii=False) + "\n")
    print("first-year: %d (%d in the working sample); provision: %d (%d); transfer-blamed blanks in the sample: %d, "
          "%d of them outside the regime before R221; partial premium: %d (%d)"
          % (len(first_year), sum(r["in_working_sample"] for r in first_year), len(provision),
             sum(r["in_working_sample"] for r in provision), sum(r["in_working_sample"] for r in transfer),
             sum(1 for r in transfer if r["in_working_sample"] and not r["in_regime_before"]),
             premium["total"], premium["total_in_working_sample"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
