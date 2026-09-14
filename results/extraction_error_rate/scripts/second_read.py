r"""The second reader's view of one sampled record: the brief, the first reading, and the filing pages it cites.

    python second_read.py syndicate_1183_2017                 cited pages as the first reader gave them
    python second_read.py syndicate_1183_2017 --pages 34 41   other pages too
    python second_read.py syndicate_780_2020 --rotate 180
    python second_read.py syndicate_1200_2023 --after         the new sample (protocol, fourth amendment)

Reads error-rate-verdicts.json (after `score_error_rate.py merge`) or, before the merge, the batch
files. With --after it reads the new sample's files instead: error-rate-briefs-after.json and
error-rate-verdicts-after.json (after `score_error_rate_after_rerun.py merge`) or its batch files.
Prints and writes nothing else.
"""
import argparse
import io
import json
import subprocess
import sys
from pathlib import Path

SCR = Path(__file__).resolve().parent
EXT = Path(r"D:/dev/lloyds_reserve_stress_testing")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ap = argparse.ArgumentParser()
ap.add_argument("stem")
ap.add_argument("--pages", nargs="*", type=int, default=None)
ap.add_argument("--rotate", type=int, default=0)
ap.add_argument("--after", action="store_true", help="the new sample drawn under the fourth amendment")
ap.add_argument("--tail", action="store_true", help="the tail stratum (error-rate-briefs-tail.json, its readings)")
ap.add_argument("--census", action="store_true",
                help="the census of the two error mechanisms (error-rate-briefs-census.json, its readings)")
ap.add_argument("--takeon", action="store_true",
                help="the take-on census (error-rate-briefs-takeon.json, its readings; sixth amendment)")
ap.add_argument("--passing", action="store_true",
                help="records found in passing (error-rate-briefs-passing.json, its readings; seventh amendment)")
ap.add_argument("--third", action="store_true",
                help="the records read after the repairs: the third sample, the entrants and the repaired records "
                     "(error-rate-briefs-third.json, its readings; fifth amendment, points 2 and 3)")
ap.add_argument("--ninth", action="store_true",
                help="the ninth amendment's take-on base census (error-rate-briefs-ninth.json, its readings; a record "
                     "whose readings were carried shows the eighth census's two readings and the carried answers)")
ap.add_argument("--eighth", action="store_true",
                help="the eighth amendment's census (error-rate-briefs-eighth.json, its readings; a carried first "
                     "reading is read from the sample or census it was carried from)")
a = ap.parse_args()

tag = ("-ninth" if a.ninth else "-eighth" if a.eighth else "-third" if a.third else "-passing" if a.passing else "-takeon" if a.takeon else "-census" if a.census
       else "-tail" if a.tail else "-after" if a.after else "")
FIRST_FROM_SECOND_SAMPLE = a.takeon and a.stem == "syndicate_2008_2021"   # its first reading is carried (sixth amendment, point 2)
brief = next(b for b in json.load(io.open(str(SCR / ("error-rate-briefs%s.json" % tag)), encoding="utf-8")) if b["stem"] == a.stem)
first = None
merged = SCR / ("error-rate-verdicts%s.json" % tag)
sources = [merged] if merged.exists() else sorted(SCR.glob("error-rate-verdicts%s-batch-*.json" % tag))
if FIRST_FROM_SECOND_SAMPLE:
    sources = [SCR / "error-rate-verdicts-after.json"]
for src in sources:
    for v in json.load(io.open(str(src), encoding="utf-8")):
        if v.get("stem") == a.stem:
            first = v
CARRIED_FROM = {"third sample": "-third", "take-on census": "-takeon", "found in passing": "-passing",
                "census": "-census", "second sample": "-after", "first sample": ""}
if a.ninth and first is None:
    decisions = json.load(io.open(str(SCR / "error-rate-carry-over-ninth.json"), encoding="utf-8"))["decisions"]
    d = next((x for x in decisions if x["stem"] == a.stem), None)
    if d and d["carry"]:
        e1 = next(v for v in json.load(io.open(str(SCR / "error-rate-verdicts-eighth.json"), encoding="utf-8")) if v["stem"] == a.stem)
        e2 = next(v for v in json.load(io.open(str(SCR / "error-rate-verification-eighth.json"), encoding="utf-8")) if v["stem"] == a.stem)
        first = {"carried_from": "eighth census", "carry_decision": d, "eighth_first_reading": e1,
                 "eighth_second_reading": e2, "pages": sorted(set((e1.get("pages") or []) + (e2.get("pages") or [])))}
if a.eighth and first is None:
    decisions = json.load(io.open(str(SCR / "error-rate-carry-over-eighth.json"), encoding="utf-8"))["decisions"]
    carried = next((d["carry_first"] for d in decisions if d["stem"] == a.stem), None)
    if carried:
        for v in json.load(io.open(str(SCR / ("error-rate-verdicts%s.json" % CARRIED_FROM[carried])), encoding="utf-8")):
            if v.get("stem") == a.stem:
                first = dict(v, carried_from=carried)
print("=" * 90)
print("BRIEF  %s  currency %s  canonical %s" % (a.stem, brief["report_currency"], brief["canonical_model"]))
print("  adopted development %s   adopted opening %s" % (brief["adopted_prior_year_development_m_report_currency"],
                                                         brief["adopted_opening_reserves_m_report_currency"]))
print("  route %s" % json.dumps(brief["route"]))
print("  cited %s   loader basis %s   cohort %s" % (brief["cited_pages"], brief["loader_basis"], brief["loader_cohort_scope"]))
if a.eighth or a.ninth:
    print("  census parts %s" % brief.get("census_parts"))
    for part, reasons in (brief.get("census_reasons") or {}).items():
        for r in reasons:
            print("    %s: %s" % (part, r[:600]))
print("FIRST READING")
print(json.dumps(first, indent=1, ensure_ascii=False) if first else "  (none yet)")
pages = a.pages if a.pages else ((first or {}).get("pages") or [])
if pages:
    cmd = [sys.executable, str(SCR / "filing_pages.py"), a.stem] + [str(p) for p in pages]
    if a.rotate:
        cmd += ["--rotate", str(a.rotate)]
    print("FILING PAGES %s" % pages)
    out = subprocess.run(cmd, cwd=str(EXT), capture_output=True, text=True, encoding="utf-8", errors="replace")
    print(out.stdout[-60000:])
    if out.returncode:
        print(out.stderr[-2000:])
