r"""Record the second reader's verdict on one record in error-rate-verification.json.

    python record_second_read.py syndicate_1183_2017 correct --pages 34 41 \
        --quote "The release in 2020 amounted to $42.8m" --why "the note labels it gross; within tolerance"
    python record_second_read.py syndicate_1200_2023 correct --after ...   the new sample, into
        error-rate-verification-after.json (protocol, fourth amendment)

A record already verified is refused unless --replace is given, so a verdict cannot be overwritten by
accident. The verdict must be one of the protocol's three, and --why must say what settles it.
"""
import argparse
import datetime
import io
import json
import sys
from pathlib import Path

SCR = Path(__file__).resolve().parent
VERDICTS = ("correct", "error", "undeterminable")

ap = argparse.ArgumentParser()
ap.add_argument("stem")
ap.add_argument("verdict", choices=VERDICTS)
ap.add_argument("--pages", nargs="+", type=int, required=True)
ap.add_argument("--quote", default="")
ap.add_argument("--filing-figure", type=float, default=None)
ap.add_argument("--error-kind", default=None)
ap.add_argument("--why", required=True)
ap.add_argument("--replace", action="store_true")
# a re-reading after a later change to the extraction is recorded apart from the original second
# readings, which stand for the extraction as it was scored (protocol, third amendment)
ap.add_argument("--out", default=None)
# the new sample drawn after R209 and R210 (protocol, fourth amendment): its own sample file and,
# unless --out says otherwise, its own verification file
ap.add_argument("--after", action="store_true")
# the tail stratum, computed after the refit: its stems are error-rate-tail.json's, its second readings
# go to error-rate-verification-tail.json
ap.add_argument("--tail", action="store_true")
# the census of the two error mechanisms (fifth amendment, point 1): its stems are error-rate-census.json's, its
# second readings go to error-rate-verification-census.json
ap.add_argument("--census", action="store_true")
# the take-on census (sixth amendment): error-rate-census-takeon.json's stems, second readings to
# error-rate-verification-takeon.json, each with the reader's answer to the census question
ap.add_argument("--takeon", action="store_true")
ap.add_argument("--is-takeon", choices=("true", "false", "null"), default=None)
ap.add_argument("--takeon-amount", type=float, default=None)
# records found in passing (seventh amendment, point 2): error-rate-census-passing.json's stems, second readings to
# error-rate-verification-passing.json
ap.add_argument("--passing", action="store_true")
# the records read after the repairs (fifth amendment, points 2 and 3): every record briefed in
# error-rate-briefs-third.json (the third sample, the entrants and the repaired records), second readings to
# error-rate-verification-third.json
ap.add_argument("--third", action="store_true")
# the eighth amendment's census: error-rate-census-eighth.json's stems, second readings to
# error-rate-verification-eighth.json, each with the reader's finding for every census part the record sits in
ap.add_argument("--eighth", action="store_true")
ap.add_argument("--finding", action="append", default=[], help="PART=true|false|null, once per census part")
ap.add_argument("--gross-opening", type=float, default=None)
# the ninth amendment's take-on base census: error-rate-census-ninth.json's stems, second readings to
# error-rate-verification-ninth.json, each with --finding takeon_base=..., the amount, the gross opening and where the
# business sits
ap.add_argument("--ninth", action="store_true")
ap.add_argument("--carried", default=None)
a = ap.parse_args()
if sum((a.tail, a.after, a.census, a.takeon, a.passing, a.third, a.eighth, a.ninth)) > 1:
    raise SystemExit("give at most one of --after, --tail, --census, --takeon, --passing, --third, --eighth and --ninth")
if a.takeon and a.is_takeon is None:
    raise SystemExit("a take-on census reading needs --is-takeon true, false or null")
OUT = SCR / (a.out or ("error-rate-verification-ninth.json" if a.ninth else
                       "error-rate-verification-eighth.json" if a.eighth else
                       "error-rate-verification-third.json" if a.third else
                       "error-rate-verification-passing.json" if a.passing else
                       "error-rate-verification-takeon.json" if a.takeon else
                       "error-rate-verification-census.json" if a.census else
                       "error-rate-verification-tail.json" if a.tail else
                       "error-rate-verification-after.json" if a.after else "error-rate-verification.json"))
SAMPLE = SCR / ("error-rate-census-ninth.json" if a.ninth else
                "error-rate-census-eighth.json" if a.eighth else
                "error-rate-briefs-third.json" if a.third else
                "error-rate-census-passing.json" if a.passing else
                "error-rate-census-takeon.json" if a.takeon else "error-rate-census.json" if a.census else
                "error-rate-tail.json" if a.tail else
                "error-rate-sample-after.json" if a.after else "error-rate-sample.json")

drawn = json.load(io.open(str(SAMPLE), encoding="utf-8"))
listed = a.census or a.takeon or a.passing or a.eighth or a.ninth
stems = ([b["stem"] for b in drawn] if a.third else drawn["stems"] if listed else drawn["tail"]["stems"] if a.tail
         else drawn["primary"]["stems"])
if a.stem not in stems:
    raise SystemExit("%s is not in the %s of %s" % (a.stem, "briefed records" if a.third else "census" if listed
                                                    else "tail" if a.tail else "primary sample", SAMPLE.name))
if a.verdict != "undeterminable" and not a.quote.strip():
    raise SystemExit("a correct or error verdict needs --quote from the filing")
rows = json.load(io.open(str(OUT), encoding="utf-8")) if OUT.exists() else []
existing = [r for r in rows if r["stem"] == a.stem]
if existing and not a.replace:
    raise SystemExit("%s is already verified (%s); pass --replace to change it" % (a.stem, existing[0]["verdict"]))
rows = [r for r in rows if r["stem"] != a.stem]
row = {"stem": a.stem, "verdict": a.verdict, "pages": a.pages, "quote": a.quote,
       "filing_figure_m": a.filing_figure, "error_kind": a.error_kind, "why": a.why,
       "reader": "second reader (editor)",
       "recorded": datetime.datetime.now().strftime("%Y-%m-%d %H:%M")}
if a.takeon:
    row["takeon_check"] = {"is_takeon": {"true": True, "false": False, "null": None}[a.is_takeon],
                           "takeon_amount_m": a.takeon_amount}
if a.eighth:
    census_briefs = {b["stem"]: b for b in json.load(io.open(str(SCR / "error-rate-briefs-eighth.json"), encoding="utf-8"))}
    parts = census_briefs[a.stem]["census_parts"]
    given = dict(f.split("=", 1) for f in a.finding)
    if sorted(given) != sorted(parts) or any(v not in ("true", "false", "null") for v in given.values()):
        raise SystemExit("an eighth-census reading needs --finding PART=true|false|null for each of %s" % parts)
    row["census_check"] = {p: {"finding": {"true": True, "false": False, "null": None}[given[p]]} for p in parts}
    if "opening" in parts:
        row["census_check"]["opening"]["gross_opening_m"] = a.gross_opening
    if "takeon_triangle" in parts:
        row["census_check"]["takeon_triangle"]["takeon_amount_m"] = a.takeon_amount
if a.ninth:
    given = dict(f.split("=", 1) for f in a.finding)
    if sorted(given) != ["takeon_base"] or given["takeon_base"] not in ("true", "false", "null"):
        raise SystemExit("a ninth-census reading needs --finding takeon_base=true|false|null")
    if not (a.carried or "").strip():
        raise SystemExit("a ninth-census reading needs --carried: where the adopted figure's table or line carries the business")
    row["census_check"] = {"takeon_base": {"finding": {"true": True, "false": False, "null": None}[given["takeon_base"]],
                                           "takeon_amount_m": a.takeon_amount, "gross_opening_m": a.gross_opening,
                                           "carried": a.carried}}
rows.append(row)
rows.sort(key=lambda r: stems.index(r["stem"]) if r["stem"] in stems else len(stems))
io.open(str(OUT), "w", encoding="utf-8", newline="").write(json.dumps(rows, indent=1, ensure_ascii=False) + "\n")
print("recorded %s: %s in %s (%d verified so far)" % (a.stem, a.verdict, OUT.name, len(rows)))
