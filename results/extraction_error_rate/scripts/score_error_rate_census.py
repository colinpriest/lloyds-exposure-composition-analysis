r"""Merge and score the census of the two error mechanisms (error-rate-protocol.md, fifth amendment, point 1).

The census is purposive, so it is reported as counts by mechanism and never pooled with a random sample.

merge
  - A record the carry-over decision kept (error-rate-carry-over-census.json) takes its merged row from the merge
    of the sample it was read in. Every other record takes its first reading from
    error-rate-verdicts-census-batch-N.json, validated as a first reading is.
  - Each record's figure source is read from its census brief; for a record read afresh the route must agree with
    its latest replay log. A carried record's source and clarified verdict must equal its sample's merge.
  - The verification set is every census record (each gets a second reading). A carried record's second reading
    is copied from its sample's verification file, where it stands.
score
  - Every census record must have a second reading. Writes error-rate-census-result.json (counts by mechanism and
    rule) and error-rate-confirmed-errors.json: the errors confirmed before repair, from the second sample's and
    the census's final verdicts, with the adopted figure, the filing's figure and the opening reserves in the
    report's currency (the propagation's error shifts; the first sample's errors belong to a superseded extraction
    and are not included).

    python score_error_rate_census.py check
    python score_error_rate_census.py merge
    python score_error_rate_census.py score
"""
import glob
import io
import json
import sys
from pathlib import Path

SCR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCR))
import score_error_rate as ser  # noqa: E402
import score_error_rate_after_rerun as rr  # noqa: E402

CENSUS = SCR / "error-rate-census.json"
BRIEFS = SCR / "error-rate-briefs-census.json"
CARRY = SCR / "error-rate-carry-over-census.json"
MERGED = SCR / "error-rate-verdicts-census.json"
VSET = SCR / "error-rate-verification-set-census.json"
VERIFIED = SCR / "error-rate-verification-census.json"
RESULT = SCR / "error-rate-census-result.json"
CONFIRMED = SCR / "error-rate-confirmed-errors.json"
ADOPTED = "adopted_prior_year_development_m_report_currency"
OPENING = "adopted_opening_reserves_m_report_currency"
FROM = {"second sample": (SCR / "error-rate-verdicts-after.json", SCR / "error-rate-verification-after.json"),
        "first sample": (SCR / "error-rate-verdicts.json", SCR / "error-rate-verification.json")}


def load(p):
    return json.load(io.open(str(p), encoding="utf-8"))


def stems_of():
    return load(CENSUS)["stems"]


def carried():
    return {d["stem"]: d["carried_from"] for d in load(CARRY)["decisions"] if d["carry_over"]}


def batch_rows(stems, carry, problems):
    rows = {}
    for p in sorted(glob.glob(str(SCR / "error-rate-verdicts-census-batch-*.json"))):
        for v in load(p):
            s = v.get("stem")
            why = rr.validate(v, stems)
            if s in rows:
                why.append("duplicate")
            if s in carry:
                why.append("a carried-over record was read again")
            if why:
                problems.append("%s: %s" % (s, "; ".join(why)))
                continue
            v["first_reader"] = "census, %s" % Path(p).stem.replace("error-rate-verdicts-census-", "")
            rows[s] = v
    return rows


def check():
    stems = stems_of()
    briefs = {b["stem"]: b for b in load(BRIEFS)}
    carry = carried()
    overruled = ser.overruled_stems()
    blocks = rr.log_blocks()
    problems = []
    rows = batch_rows(stems, carry, problems)
    for s, v in rows.items():
        source = ser.figure_source(briefs[s], overruled)[0]
        if source == "triangle" and v.get("verdict") != "undeterminable" and v.get("triangle_recomputation_m") is None:
            problems.append("%s: triangle-sourced, but no triangle recomputation recorded" % s)
        disagreement = rr.route_disagrees_with_log(briefs[s], source, blocks.get(s))
        if disagreement:
            problems.append("%s: %s" % (s, disagreement))
    fresh = [s for s in stems if s not in carry]
    print("readings %d of the %d census records read afresh; without a reading: %s"
          % (len(rows), len(fresh), sorted(set(fresh) - set(rows))))
    for pr in problems:
        print("  PROBLEM " + pr)
    print("problems: %d" % len(problems))


def merge():
    stems = stems_of()
    briefs = {b["stem"]: b for b in load(BRIEFS)}
    carry = carried()
    earlier = {name: {r["stem"]: r for r in load(paths[0])} for name, paths in FROM.items()}
    overruled = ser.overruled_stems()
    blocks = rr.log_blocks()
    problems = []
    rows = batch_rows(stems, carry, problems)
    for s in stems:
        if s in carry:
            row = dict(earlier[carry[s]][s])
            row["first_reader"] = "%s (carried over from the %s)" % (row.get("first_reader"), carry[s])
            rows[s] = row
    missing = [s for s in stems if s not in rows]
    if missing:
        problems.append("no reading for: %s" % missing)
    for s in stems:
        if s not in rows:
            continue
        source, source_why = ser.figure_source(briefs[s], overruled)
        verdict, verdict_why = ser.clarified(rows[s], briefs[s], overruled)
        if s in carry:
            before = earlier[carry[s]][s]
            if (source, verdict) != (before["figure_source"], before["clarified_verdict"]):
                problems.append("%s: carried over, but its source or clarified verdict differs from the %s's merge"
                                % (s, carry[s]))
        else:
            disagreement = rr.route_disagrees_with_log(briefs[s], source, blocks.get(s))
            if disagreement:
                problems.append("%s: %s" % (s, disagreement))
        rows[s]["figure_source"], rows[s]["figure_source_why"] = source, source_why
        rows[s]["clarified_verdict"], rows[s]["clarified_why"] = verdict, verdict_why
    print("readings: %d of %d (%d carried over)" % (len(rows), len(stems), len(carry)))
    for pr in problems:
        print("  PROBLEM " + pr)
    if problems:
        raise SystemExit("merge refused")
    io.open(str(MERGED), "w", encoding="utf-8").write(json.dumps([rows[s] for s in stems], indent=1, ensure_ascii=False))
    io.open(str(VSET), "w", encoding="utf-8").write(json.dumps(
        {"rule": "fifth amendment, point 1: every census record gets a second reading", "all": sorted(stems)}, indent=1))
    carried_second = []
    for name, (_merged, verification) in FROM.items():
        carried_second += [dict(v, carried_over_from=verification.name) for v in load(verification)
                           if carry.get(v["stem"]) == name]
    existing = load(VERIFIED) if VERIFIED.exists() else []
    have = {v["stem"] for v in existing}
    existing += [v for v in carried_second if v["stem"] not in have]
    io.open(str(VERIFIED), "w", encoding="utf-8").write(json.dumps(existing, indent=1, ensure_ascii=False))
    count = lambda key: {v: sum(1 for s in stems if rows[s][key] == v) for v in ser.VERDICTS}
    print("first readers' rule: %s" % count("verdict"))
    print("clarified rule:      %s" % count("clarified_verdict"))
    done = {v["stem"] for v in existing}
    print("second readings carried over: %d; still to read: %s" % (len(carried_second), sorted(set(stems) - done)))


def score():
    stems = stems_of()
    census = load(CENSUS)
    briefs = {b["stem"]: b for b in load(BRIEFS)}
    rows = {v["stem"]: v for v in load(MERGED)}
    verified = {v["stem"]: v for v in load(VERIFIED)}
    if set(stems) - set(verified):
        raise SystemExit("not yet second-read: %s" % sorted(set(stems) - set(verified)))
    final = {s: verified[s]["verdict"] for s in stems}
    by_mechanism = {}
    for name, block in census["mechanisms"].items():
        members = block["stems"]
        by_mechanism[name] = {v: sorted(s for s in members if final[s] == v) for v in ser.VERDICTS}
    overturned = [{"stem": s, "clarified": rows[s]["clarified_verdict"], "second": final[s],
                   "why": verified[s].get("why")} for s in stems if rows[s]["clarified_verdict"] != final[s]]
    result = {"protocol": "error-rate-protocol.md, fifth amendment, point 1 (purposive: counts, never pooled)",
              "exposure_results_run_id": census["exposure_results_run_id"], "census_n": len(stems),
              "carried_over": len(carried()), "second_readings": len(verified),
              "final_verdicts": final, "by_mechanism": by_mechanism, "second_reading_overturned": overturned}
    io.open(str(RESULT), "w", encoding="utf-8").write(json.dumps(result, indent=1))

    confirmed = {}
    after_final = load(SCR / "error-rate-result-after-rerun.json")["rules"]["clarified"]["final_verdicts"]
    after_briefs = {b["stem"]: b for b in load(SCR / "error-rate-briefs-after.json")}
    after_second = {v["stem"]: v for v in load(SCR / "error-rate-verification-after.json")}
    after_rows = {v["stem"]: v for v in load(SCR / "error-rate-verdicts-after.json")}
    def filing_figure(second_row, first_row):
        """The filing's figure for an error's shift: the second reading's, else the first reading's, else -- for a
        scope error whose filing states no clean figure (2008/2021: the whole charge is a transfer's first-year
        recognition) -- the first reading's triangle recomputation, recorded as the stand-in. Fixed before the
        census was scored (13 September 2026)."""
        for row, key, how in ((second_row, "filing_figure_m", "second reading"),
                              (first_row, "filing_figure_m", "first reading"),
                              (first_row, "triangle_recomputation_m", "first reading's triangle recomputation (stand-in)")):
            if (row or {}).get(key) is not None:
                return row[key], how
        return None, None

    for s, v in after_final.items():
        if v == "error":
            fig, how = filing_figure(after_second.get(s), after_rows[s])
            confirmed[s] = {"stem": s, "from": "second sample", "adopted_m": after_briefs[s][ADOPTED],
                            "filing_m": fig, "filing_figure_from": how, "opening_m": after_briefs[s][OPENING]}
    for s in stems:
        if final[s] == "error" and s not in confirmed:
            fig, how = filing_figure(verified[s], rows[s])
            confirmed[s] = {"stem": s, "from": "census", "adopted_m": briefs[s][ADOPTED], "filing_m": fig,
                            "filing_figure_from": how, "opening_m": briefs[s][OPENING]}
    bad = [c["stem"] for c in confirmed.values() if None in (c["adopted_m"], c["filing_m"], c["opening_m"])]
    if bad:
        raise SystemExit("an error without an adopted figure, a filing figure or opening reserves: %s" % bad)
    io.open(str(CONFIRMED), "w", encoding="utf-8").write(json.dumps(sorted(confirmed.values(), key=lambda c: c["stem"]),
                                                                  indent=1))
    for name, counts in by_mechanism.items():
        print("%-34s %s" % (name, {v: len(x) for v, x in counts.items()}))
        for v, members in counts.items():
            if members:
                print("   %-15s %s" % (v, members))
    print("second reading overturned: %s" % overturned)
    print("confirmed errors before repair: %s" % sorted(confirmed))
    print("written: %s, %s" % (RESULT.name, CONFIRMED.name))


if __name__ == "__main__":
    {"merge": merge, "score": score, "check": check}[sys.argv[1]]()
