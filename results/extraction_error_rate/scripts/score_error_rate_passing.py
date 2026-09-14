r"""Merge and score the records found in passing (error-rate-protocol.md, seventh amendment, point 2).

Reported apart, never pooled with a random sample and never counted as a mechanism's census.

check / merge
  - first readings from error-rate-verdicts-passing-batch-1.json, validated as a first reading is; figure source and
    clarified verdict as for every other reading.
score
  - every record needs a second reading (record_second_read.py --passing). A record is a confirmed error when the
    clarified first reading and the second reading both find an error and their filing figures agree within the
    protocol's tolerance, max(0.5, 5% of the figure); that record is repaired by the second reading's figure.
    Any other record is left as it is, with its readings recorded. Writes error-rate-passing-result.json.

    python score_error_rate_passing.py check
    python score_error_rate_passing.py merge
    python score_error_rate_passing.py score
"""
import io
import json
import sys
from pathlib import Path

SCR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCR))
import score_error_rate as ser  # noqa: E402
import score_error_rate_after_rerun as rr  # noqa: E402

CENSUS = SCR / "error-rate-census-passing.json"
BRIEFS = SCR / "error-rate-briefs-passing.json"
BATCH = SCR / "error-rate-verdicts-passing-batch-1.json"
MERGED = SCR / "error-rate-verdicts-passing.json"
VERIFIED = SCR / "error-rate-verification-passing.json"
RESULT = SCR / "error-rate-passing-result.json"
ADOPTED = "adopted_prior_year_development_m_report_currency"
OPENING = "adopted_opening_reserves_m_report_currency"


def load(p):
    return json.load(io.open(str(p), encoding="utf-8"))


def first_rows(problems):
    stems = load(CENSUS)["stems"]
    rows = {}
    for v in (load(BATCH) if BATCH.exists() else []):
        s = v.get("stem")
        why = rr.validate(v, stems)
        if s in rows:
            why.append("duplicate")
        if why:
            problems.append("%s: %s" % (s, "; ".join(why)))
            continue
        v["first_reader"] = "found in passing, batch-1"
        rows[s] = v
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
    if set(stems) - set(rows):
        problems.append("no first reading for %s" % sorted(set(stems) - set(rows)))
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
    print("merged %d; clarified verdicts %s" % (len(rows), {s: rows[s]["clarified_verdict"] for s in stems}))


def score():
    stems = load(CENSUS)["stems"]
    briefs = {b["stem"]: b for b in load(BRIEFS)}
    rows = {v["stem"]: v for v in load(MERGED)}
    second = {v["stem"]: v for v in load(VERIFIED)} if VERIFIED.exists() else {}
    if set(stems) - set(second):
        raise SystemExit("not yet second-read: %s" % sorted(set(stems) - set(second)))
    out, confirmed = [], []
    for s in stems:
        f1, f2 = rows[s].get("filing_figure_m"), second[s].get("filing_figure_m")
        both_error = rows[s]["clarified_verdict"] == "error" and second[s]["verdict"] == "error"
        agree = (f1 is not None and f2 is not None
                 and abs(float(f1) - float(f2)) <= max(0.5, 0.05 * abs(float(f2))))
        rec = {"stem": s, "adopted_m": briefs[s][ADOPTED], "opening_m": briefs[s][OPENING],
               "first_verdict": rows[s]["clarified_verdict"], "second_verdict": second[s]["verdict"],
               "first_filing_m": f1, "second_filing_m": f2, "confirmed_error": bool(both_error and agree),
               "error_kind": second[s].get("error_kind") or rows[s].get("error_kind")}
        out.append(rec)
        if rec["confirmed_error"]:
            confirmed.append(rec)
    io.open(str(RESULT), "w", encoding="utf-8").write(json.dumps(
        {"protocol": "error-rate-protocol.md, seventh amendment, point 2 (reported apart, never pooled)",
         "records": out, "confirmed_errors": [r["stem"] for r in confirmed]}, indent=1, ensure_ascii=False))
    for r in out:
        print("  %-22s first %-14s second %-14s filing %s / %s confirmed %s"
              % (r["stem"], r["first_verdict"], r["second_verdict"], r["first_filing_m"], r["second_filing_m"],
                 r["confirmed_error"]))
    print("confirmed errors: %s; written %s" % ([r["stem"] for r in confirmed], RESULT.name))


if __name__ == "__main__":
    {"check": check, "merge": merge, "score": score}[sys.argv[1]]()
