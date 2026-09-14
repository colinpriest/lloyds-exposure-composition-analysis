r"""Merge and score the take-on census (error-rate-protocol.md, sixth amendment), never pooled with a random sample.

check / merge
  - first readings from error-rate-verdicts-takeon-batch-N.json (validated as a first reading is, and each must
    answer the census question with a takeon_check); 2008/2021's first reading is the second sample's, carried,
    and its answer is read from that reading (see FIRST_ANSWER_2008_2021);
  - every record gets a second reading (record_second_read.py --takeon, with --is-takeon).
score
  - a record leaves the working sample only when both readings answer is_takeon true (point 3). Writes
    error-rate-takeon-result.json and takeon-register-draft.json (the confirmed records, each with its pages,
    quotes, amounts and both readings), from which the extraction repository's register is written.

    python score_error_rate_takeon.py check
    python score_error_rate_takeon.py merge
    python score_error_rate_takeon.py score
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

CENSUS = SCR / "error-rate-census-takeon.json"
BRIEFS = SCR / "error-rate-briefs-takeon.json"
MERGED = SCR / "error-rate-verdicts-takeon.json"
VERIFIED = SCR / "error-rate-verification-takeon.json"
RESULT = SCR / "error-rate-takeon-result.json"
DRAFT = SCR / "takeon-register-draft.json"
CARRIED = "syndicate_2008_2021"
# The second sample's first reading of 2008/2021 answers the census question in its own words ("it is the entire
# 2021 gross claims charge, essentially the first-year recognition of the Hiscox loss portfolio transfer written into
# the 2021 year of account"); recorded here as that reading's answer, with its pages, before the census is scored.
FIRST_ANSWER_2008_2021 = {"is_takeon": True, "takeon_amount_m": 384.7, "pages": [6, 7, 44, 53, 54],
                          "evidence": "carried from the second sample's first reading (error-rate-verdicts-after.json)"}


def load(p):
    return json.load(io.open(str(p), encoding="utf-8"))


def stems_of():
    return load(CENSUS)["stems"]


def first_rows(problems):
    stems = stems_of()
    rows = {}
    for p in sorted(glob.glob(str(SCR / "error-rate-verdicts-takeon-batch-*.json"))):
        for v in load(p):
            s = v.get("stem")
            why = rr.validate(v, stems)
            tc = v.get("takeon_check")
            if not isinstance(tc, dict) or tc.get("is_takeon") not in (True, False, None) or "is_takeon" not in tc:
                why.append("no answer to the census question")
            if s == CARRIED:
                why.append("2008/2021's first reading is carried, not read again")
            if s in rows:
                why.append("duplicate")
            if why:
                problems.append("%s: %s" % (s, "; ".join(why)))
                continue
            v["first_reader"] = "take-on census, %s" % Path(p).stem.replace("error-rate-verdicts-takeon-", "")
            rows[s] = v
    after = {r["stem"]: r for r in load(SCR / "error-rate-verdicts-after.json")}
    if CARRIED in stems:
        row = dict(after[CARRIED])
        row["takeon_check"] = dict(FIRST_ANSWER_2008_2021)
        row["first_reader"] = "%s (carried over from the second sample)" % row.get("first_reader")
        rows[CARRIED] = row
    return stems, rows


def check():
    problems = []
    stems, rows = first_rows(problems)
    print("first readings %d of %d; without one: %s" % (len(rows), len(stems), sorted(set(stems) - set(rows))))
    for pr in problems:
        print("  PROBLEM " + pr)
    print("problems: %d" % len(problems))


def merge():
    problems = []
    stems, rows = first_rows(problems)
    missing = sorted(set(stems) - set(rows))
    if missing:
        problems.append("no first reading for %s" % missing)
    briefs = {b["stem"]: b for b in load(BRIEFS)}
    overruled = ser.overruled_stems()
    for s in stems:
        if s in rows:
            rows[s]["figure_source"], rows[s]["figure_source_why"] = ser.figure_source(briefs[s], overruled)
            rows[s]["clarified_verdict"], rows[s]["clarified_why"] = ser.clarified(rows[s], briefs[s], overruled)
    for pr in problems:
        print("  PROBLEM " + pr)
    if problems:
        raise SystemExit("merge refused")
    io.open(str(MERGED), "w", encoding="utf-8").write(json.dumps([rows[s] for s in stems], indent=1, ensure_ascii=False))
    print("merged %d; first answers: %s" % (len(rows), {s: rows[s]["takeon_check"]["is_takeon"] for s in stems}))
    print("clarified verdicts: %s" % {v: sum(1 for s in stems if rows[s]["clarified_verdict"] == v) for v in ser.VERDICTS})


def score():
    stems = stems_of()
    rows = {v["stem"]: v for v in load(MERGED)}
    second = {v["stem"]: v for v in load(VERIFIED)} if VERIFIED.exists() else {}
    if set(stems) - set(second):
        raise SystemExit("not yet second-read: %s" % sorted(set(stems) - set(second)))
    out, confirmed = [], []
    briefs = {b["stem"]: b for b in load(BRIEFS)}
    for s in stems:
        a1 = rows[s]["takeon_check"]["is_takeon"]
        a2 = (second[s].get("takeon_check") or {}).get("is_takeon")
        both = a1 is True and a2 is True
        rec = {"stem": s, "regime_sources": briefs[s]["regime_sources"],
               "adopted_m": briefs[s]["adopted_prior_year_development_m_report_currency"],
               "first_answer": a1, "second_answer": a2, "leaves_the_working_sample": both,
               "first_verdict": rows[s]["clarified_verdict"], "second_verdict": second[s]["verdict"]}
        out.append(rec)
        if both:
            confirmed.append({
                "stem": s, "regime_sources": briefs[s]["regime_sources"], "adopted_m": rec["adopted_m"],
                "takeon_amount_m": [rows[s]["takeon_check"].get("takeon_amount_m"),
                                    (second[s].get("takeon_check") or {}).get("takeon_amount_m")],
                "pages": sorted(set((rows[s]["takeon_check"].get("pages") or []) + (second[s].get("pages") or []))),
                "quote": second[s].get("quote"),
                "readings": ["first reading (%s): %s" % (rows[s].get("first_reader"), rows[s]["takeon_check"].get("evidence")),
                             "second reading (editor, %s): %s" % (second[s].get("recorded"), second[s].get("why"))]})
    result = {"protocol": "error-rate-protocol.md, sixth amendment (purposive: counts, never pooled)",
              "census_n": len(stems), "records": out, "leaving": [c["stem"] for c in confirmed]}
    io.open(str(RESULT), "w", encoding="utf-8").write(json.dumps(result, indent=1, ensure_ascii=False))
    io.open(str(DRAFT), "w", encoding="utf-8").write(json.dumps(confirmed, indent=1, ensure_ascii=False))
    for r in out:
        print("  %-22s first %-5s second %-5s leaves %-5s verdicts %s / %s"
              % (r["stem"], r["first_answer"], r["second_answer"], r["leaves_the_working_sample"],
                 r["first_verdict"], r["second_verdict"]))
    print("leaving the working sample: %s" % result["leaving"])
    print("written: %s, %s" % (RESULT.name, DRAFT.name))


if __name__ == "__main__":
    {"check": check, "merge": merge, "score": score}[sys.argv[1]]()
