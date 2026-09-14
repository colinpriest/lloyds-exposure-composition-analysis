r"""Merge and score the eighth amendment's census (error-rate-protocol.md), never pooled with a random sample.

check   first readings from error-rate-verdicts-eighth-batch-N.json, validated as a first reading is; each must answer
        every census part its brief names (census_check.<part>.finding true, false or null).
merge   the census's first readings: the batch readings and, for a record the carry-over kept, its earlier merged
        reading, whose figure source and clarified verdict must still follow from its brief. Second readings the
        carry-over kept are copied into error-rate-verification-eighth.json. Writes error-rate-verdicts-eighth.json.
score   every census record needs a second reading. Per part: the records flagged, decided and read, and how many both
        readings found the mechanism in (true), both found absent (false), or left unsettled. A reading carried from an
        earlier sample answers a part other than takeon_triangle by its verdict: correct is false, anything else is
        unsettled. Repair drafts under point 5: a confirmed error whose readings agree on the filing's figure; a net table
        both readings find; a take-on both find dominating the figure; opening reserves both find to be another line,
        with gross figures agreeing within 2%; and, for the owner, an error both readings confirm with no figure in the
        filing. Writes error-rate-census-eighth-result.json and eighth-repairs-draft.json.

    python score_error_rate_eighth.py check | merge | score
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

ADOPTED = "adopted_prior_year_development_m_report_currency"
OPENING = "adopted_opening_reserves_m_report_currency"
CENSUS = SCR / "error-rate-census-eighth.json"
BRIEFS = SCR / "error-rate-briefs-eighth.json"
CARRY = SCR / "error-rate-carry-over-eighth.json"
MERGED = SCR / "error-rate-verdicts-eighth.json"
VERIFIED = SCR / "error-rate-verification-eighth.json"
RESULT = SCR / "error-rate-census-eighth-result.json"
DRAFT = SCR / "eighth-repairs-draft.json"
PARTS = ("movement", "transposed", "net_table", "provisions_row", "opening", "takeon_triangle")
SETS = {"third sample": ("error-rate-verdicts-third.json", "error-rate-verification-third.json"),
        "take-on census": ("error-rate-verdicts-takeon.json", "error-rate-verification-takeon.json"),
        "found in passing": ("error-rate-verdicts-passing.json", "error-rate-verification-passing.json"),
        "census": ("error-rate-verdicts-census.json", "error-rate-verification-census.json"),
        "second sample": ("error-rate-verdicts-after.json", "error-rate-verification-after.json"),
        "first sample": ("error-rate-verdicts.json", "error-rate-verification.json")}


def load(p):
    return json.load(io.open(str(p), encoding="utf-8"))


def briefs_of():
    return {b["stem"]: b for b in load(BRIEFS)}


def decisions_of():
    return {d["stem"]: d for d in load(CARRY)["decisions"]}


def batch_rows(briefs, decisions, problems):
    stems = list(briefs)
    rows = {}
    for p in sorted(glob.glob(str(SCR / "error-rate-verdicts-eighth-batch-*.json"))):
        for v in load(p):
            s = v.get("stem")
            why = rr.validate(v, stems)
            if s in briefs:
                cc = v.get("census_check") if isinstance(v.get("census_check"), dict) else {}
                for part in briefs[s]["census_parts"]:
                    ans = cc.get(part)
                    if not isinstance(ans, dict) or "finding" not in ans or ans["finding"] not in (True, False, None):
                        why.append("no answer for census part %s" % part)
                if decisions[s]["carry_first"]:
                    why.append("its first reading is carried, so it is not read again")
            if s in rows:
                why.append("duplicate")
            if why:
                problems.append("%s: %s" % (s, "; ".join(why)))
                continue
            v["first_reader"] = "eighth census, %s" % Path(p).stem.replace("error-rate-verdicts-eighth-", "")
            rows[s] = v
    return rows


def check():
    briefs, decisions = briefs_of(), decisions_of()
    problems = []
    rows = batch_rows(briefs, decisions, problems)
    fresh = [s for s in briefs if not decisions[s]["carry_first"]]
    print("first readings %d of the %d records read afresh; without one: %s" % (len(rows), len(fresh), sorted(set(fresh) - set(rows))))
    for pr in problems:
        print("  PROBLEM " + pr)
    print("problems: %d" % len(problems))


def merge():
    briefs, decisions = briefs_of(), decisions_of()
    overruled = ser.overruled_stems()
    problems = []
    rows = batch_rows(briefs, decisions, problems)
    earlier = {}
    for s, d in decisions.items():
        if d["carry_first"]:
            name = d["carry_first"]
            earlier.setdefault(name, {r["stem"]: r for r in load(SCR / SETS[name][0])})
            row = dict(earlier[name][s])
            row["first_reader"] = "%s (carried over from the %s)" % (row.get("first_reader"), name)
            row["carried_from"] = name
            rows[s] = row
    missing = [s for s in briefs if s not in rows]
    if missing:
        problems.append("no first reading for %s" % missing)
    for s in briefs:
        if s not in rows:
            continue
        source, source_why = ser.figure_source(briefs[s], overruled)
        verdict, verdict_why = ser.clarified(rows[s], briefs[s], overruled)
        if decisions[s]["carry_first"] and (source, verdict) != (rows[s].get("figure_source"), rows[s].get("clarified_verdict")):
            problems.append("%s: carried, but its source or clarified verdict (%s, %s) no longer follows from its brief (%s, %s)"
                            % (s, rows[s].get("figure_source"), rows[s].get("clarified_verdict"), source, verdict))
        rows[s]["figure_source"], rows[s]["figure_source_why"] = source, source_why
        rows[s]["clarified_verdict"], rows[s]["clarified_why"] = verdict, verdict_why
    for pr in problems:
        print("  PROBLEM " + pr)
    if problems:
        raise SystemExit("merge refused")
    io.open(str(MERGED), "w", encoding="utf-8").write(json.dumps([rows[s] for s in briefs], indent=1, ensure_ascii=False))
    existing = load(VERIFIED) if VERIFIED.exists() else []
    have = {v["stem"] for v in existing}
    copied = 0
    for s, d in decisions.items():
        if d["carry_second"] and s not in have:
            name = d["carry_first"]
            sec = next(v for v in load(SCR / SETS[name][1]) if v["stem"] == s)
            existing.append(dict(sec, carried_over_from=SETS[name][1]))
            copied += 1
    io.open(str(VERIFIED), "w", encoding="utf-8", newline="").write(json.dumps(existing, indent=1, ensure_ascii=False) + "\n")
    done = {v["stem"] for v in existing}
    print("merged %d first readings (%d carried); second readings copied %d; still to read %d: %s"
          % (len(rows), sum(1 for d in decisions.values() if d["carry_first"]), copied, len(set(briefs) - done),
             sorted(set(briefs) - done)))
    print("clarified verdicts: %s" % {v: sum(1 for s in briefs if rows[s]["clarified_verdict"] == v) for v in ser.VERDICTS})


def answer(reading, part, carried):
    cc = reading.get("census_check") if isinstance(reading.get("census_check"), dict) else {}
    if part in cc:
        return cc[part].get("finding")
    if carried and part != "takeon_triangle":
        return False if (reading.get("clarified_verdict") or reading.get("verdict")) == "correct" else None
    return "missing"


def detail(reading, part, key):
    cc = reading.get("census_check") if isinstance(reading.get("census_check"), dict) else {}
    return (cc.get(part) or {}).get(key)


def score():
    briefs, decisions, census = briefs_of(), decisions_of(), load(CENSUS)
    rows = {v["stem"]: v for v in load(MERGED)}
    second = {v["stem"]: v for v in load(VERIFIED)}
    missing = [s for s in briefs if s not in second]
    if missing:
        raise SystemExit("not yet second-read: %s" % missing)
    out, drafts, problems = [], [], []
    for s in briefs:
        f, v = rows[s], second[s]
        rec = {"stem": s, "parts": briefs[s]["census_parts"], "adopted_m": briefs[s][ADOPTED], "opening_m": briefs[s][OPENING],
               "first_verdict": f["clarified_verdict"], "second_verdict": v["verdict"],
               "first_figure_m": f.get("filing_figure_m"), "second_figure_m": v.get("filing_figure_m"),
               "first_carried_from": decisions[s]["carry_first"], "second_carried_from": v.get("carried_over_from"),
               "findings": {}}
        for part in rec["parts"]:
            a1 = answer(f, part, bool(decisions[s]["carry_first"]))
            a2 = answer(v, part, bool(v.get("carried_over_from")))
            if "missing" in (a1, a2):
                problems.append("%s: no answer for %s" % (s, part))
            rec["findings"][part] = {"first": a1, "second": a2, "confirmed": a1 is True and a2 is True,
                                     "absent": a1 is False and a2 is False}
        both_error = rec["first_verdict"] == "error" and rec["second_verdict"] == "error"
        f1, f2 = rec["first_figure_m"], rec["second_figure_m"]
        agree = f1 is not None and f2 is not None and abs(float(f1) - float(f2)) <= max(0.5, 0.05 * abs(float(f2)))
        rec["confirmed_error"] = both_error
        base = {"stem": s, "pages": sorted(set((f.get("pages") or []) + (v.get("pages") or []))), "quote": v.get("quote"),
                "readings": ["first reading (%s): %s; %s" % (f.get("first_reader"), f.get("clarified_verdict"), f.get("reasoning")),
                             "second reading (editor, %s): %s; %s" % (v.get("recorded"), v.get("verdict"), v.get("why"))]}
        if both_error and agree:
            drafts.append(dict(base, kind="confirmed figure", figure_m=f2, figure_kind="to decide from the readings",
                               triangle_recomputation_m=[f.get("triangle_recomputation_m"), v.get("triangle_recomputation_m")]))
        elif both_error:
            drafts.append(dict(base, kind="for the owner: an error both readings confirm without an agreed figure",
                               figures=[f1, f2]))
        if rec["findings"].get("net_table", {}).get("confirmed"):
            drafts.append(dict(base, kind="net basis"))
        if rec["findings"].get("takeon_triangle", {}).get("confirmed"):
            drafts.append(dict(base, kind="take-on", takeon_amount_m=[detail(f, "takeon_triangle", "takeon_amount_m"),
                                                                     detail(v, "takeon_triangle", "takeon_amount_m")]))
        if rec["findings"].get("opening", {}).get("confirmed"):
            g1, g2 = detail(f, "opening", "gross_opening_m"), detail(v, "opening", "gross_opening_m")
            ok = g1 is not None and g2 is not None and abs(float(g1) - float(g2)) <= 0.02 * abs(float(g2))
            drafts.append(dict(base, kind="opening reserves" if ok else "for the owner: opening reserves without agreed gross figures",
                               gross_opening_m=[g1, g2]))
        out.append(rec)
    for pr in problems:
        print("  PROBLEM " + pr)
    if problems:
        raise SystemExit("score refused")
    parts = {}
    for part in PARTS:
        flagged = sorted(census["parts"][part])
        recs = [r for r in out if part in r["findings"]]
        parts[part] = {"flagged": len(flagged), "decided": sorted(s for s in flagged if s in census["decided"]),
                       "read": len(recs),
                       "found_by_both": sorted(r["stem"] for r in recs if r["findings"][part]["confirmed"]),
                       "absent_by_both": len([r for r in recs if r["findings"][part]["absent"]]),
                       "unsettled": sorted(r["stem"] for r in recs if not r["findings"][part]["confirmed"]
                                           and not r["findings"][part]["absent"])}
    result = {"protocol": "error-rate-protocol.md, eighth amendment (purposive: counts, never pooled)",
              "census_n": len(briefs), "decided_n": len(census["decided"]), "parts": parts,
              "confirmed_errors": sorted(r["stem"] for r in out if r["confirmed_error"]),
              "verdicts": {"first": {x: sum(1 for r in out if r["first_verdict"] == x) for x in ser.VERDICTS},
                           "second": {x: sum(1 for r in out if r["second_verdict"] == x) for x in ser.VERDICTS}},
              "records": out, "repairs_draft": DRAFT.name}
    io.open(str(RESULT), "w", encoding="utf-8").write(json.dumps(result, indent=1, ensure_ascii=False))
    io.open(str(DRAFT), "w", encoding="utf-8").write(json.dumps(drafts, indent=1, ensure_ascii=False))
    for part, p in parts.items():
        print("%-16s flagged %3d decided %2d read %3d found by both %s; absent by both %d; unsettled %s"
              % (part, p["flagged"], len(p["decided"]), p["read"], p["found_by_both"], p["absent_by_both"], p["unsettled"]))
    print("confirmed errors: %s" % result["confirmed_errors"])
    print("repair drafts: %s" % [(d["stem"], d["kind"]) for d in drafts])
    print("written: %s, %s" % (RESULT.name, DRAFT.name))


if __name__ == "__main__":
    {"check": check, "merge": merge, "score": score}[sys.argv[1]]()
