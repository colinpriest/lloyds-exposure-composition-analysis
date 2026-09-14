r"""Merge and score the ninth amendment's take-on base census (error-rate-protocol.md), never pooled with a random sample.

check   first readings from error-rate-verdicts-ninth-batch-N.json, validated as a first reading is; each must answer
        census_check.takeon_base (finding true, false or null; takeon_amount_m and gross_opening_m a number or null;
        carried, where the adopted figure's table or line carries the business).
merge   the census's first readings: the batch readings and, for a record the carry-over kept, the eighth census's
        first reading with the answer the editor recorded from it. The carried second readings are copied into
        error-rate-verification-ninth.json with their recorded answers. Writes error-rate-verdicts-ninth.json and lists
        the records that need a second reading (point 4): every first reading except one that finds no covered transfer,
        or a covered transfer under 5% of the opening reserves.
score   every record that needs a second reading has one. A record is adjusted when both readings find a covered
        transfer, agree on its gross amount within 2%, the amount is 5% or more of the adopted opening reserves, and each
        reading's gross opening reserves, where it gives them, are the adopted figure within 2% (point 5). Every other
        record is left as it is, with the reason. Writes error-rate-census-ninth-result.json (each record's answers,
        outcome and severity before and after) and ninth-repairs-draft.json.

    python score_error_rate_ninth.py check | merge | score
"""
import glob
import io
import json
import sys
from pathlib import Path

SCR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCR))
import score_error_rate_after_rerun as rr  # noqa: E402

ADOPTED = "adopted_prior_year_development_m_report_currency"
OPENING = "adopted_opening_reserves_m_report_currency"
BRIEFS = SCR / "error-rate-briefs-ninth.json"
CARRY = SCR / "error-rate-carry-over-ninth.json"
MERGED = SCR / "error-rate-verdicts-ninth.json"
VERIFIED = SCR / "error-rate-verification-ninth.json"
RESULT = SCR / "error-rate-census-ninth-result.json"
DRAFT = SCR / "ninth-repairs-draft.json"
MATERIAL = 0.05
AGREE = 0.02


def load(p):
    return json.load(io.open(str(p), encoding="utf-8"))


def answer(v):
    return ((v or {}).get("census_check") or {}).get("takeon_base")


def is_amount(x):
    return x is None or (isinstance(x, (int, float)) and not isinstance(x, bool))


def answer_gaps(ans):
    if not isinstance(ans, dict):
        return ["no census_check.takeon_base"]
    why = []
    if "finding" not in ans or ans["finding"] not in (True, False, None):
        why.append("finding must be true, false or null")
    for k in ("takeon_amount_m", "gross_opening_m"):
        if k not in ans or not is_amount(ans[k]):
            why.append("%s must be a number or null" % k)
    if not str(ans.get("carried") or "").strip():
        why.append("carried must say where the adopted figure's table or line carries the business")
    return why


def needs_second(ans, opening):
    """Point 4: a first reading that finds no covered transfer, or a transferred amount under 5% of the opening reserves
    (whatever it finds about coverage), gets no second reading; every other first reading gets one."""
    if ans["finding"] is False:
        return False
    amt = ans["takeon_amount_m"]
    if amt is not None and opening is not None and opening > 0 and amt < MATERIAL * opening:
        return False
    return True


def briefs_of():
    return {b["stem"]: b for b in load(BRIEFS)}


def decisions_of():
    return {d["stem"]: d for d in load(CARRY)["decisions"]}


def batch_rows(briefs, decisions, problems):
    stems = list(briefs)
    rows = {}
    for p in sorted(glob.glob(str(SCR / "error-rate-verdicts-ninth-batch-*.json"))):
        for v in load(p):
            s = v.get("stem")
            why = rr.validate(v, stems)
            if s in briefs:
                why += answer_gaps(answer(v))
                if decisions[s]["carry"]:
                    why.append("its readings were carried, so it is not read again")
            if s in rows:
                why.append("duplicate")
            if why:
                problems.append("%s: %s" % (s, "; ".join(why)))
                continue
            v["first_reader"] = "ninth census, %s" % Path(p).stem.replace("error-rate-verdicts-ninth-", "")
            rows[s] = v
    return rows


def check():
    briefs, decisions = briefs_of(), decisions_of()
    problems = []
    rows = batch_rows(briefs, decisions, problems)
    fresh = [s for s in briefs if not decisions[s]["carry"]]
    print("first readings %d of the %d records read afresh; without one: %s" % (len(rows), len(fresh), sorted(set(fresh) - set(rows))))
    for pr in problems:
        print("  PROBLEM " + pr)
    print("problems: %d" % len(problems))


def merge():
    briefs, decisions = briefs_of(), decisions_of()
    problems = []
    rows = batch_rows(briefs, decisions, problems)
    e_first = {v["stem"]: v for v in load(SCR / "error-rate-verdicts-eighth.json")}
    e_second = {v["stem"]: v for v in load(SCR / "error-rate-verification-eighth.json")}
    for s, d in decisions.items():
        if d["carry"]:
            rows[s] = dict(e_first[s], census_check={"takeon_base": d["first"]}, carried_from="eighth census",
                           first_reader="%s (carried from the eighth census)" % e_first[s].get("first_reader"))
    missing = [s for s in briefs if s not in rows]
    if missing:
        problems.append("no first reading for %s" % missing)
    for pr in problems:
        print("  PROBLEM " + pr)
    if problems:
        raise SystemExit("merge refused")
    io.open(str(MERGED), "w", encoding="utf-8").write(json.dumps([rows[s] for s in briefs], indent=1, ensure_ascii=False))
    existing = load(VERIFIED) if VERIFIED.exists() else []
    have = {v["stem"] for v in existing}
    copied = []
    for s, d in decisions.items():
        if d["carry"] and s not in have:
            existing.append(dict(e_second[s], census_check={"takeon_base": d["second"]}, carried_from="eighth census"))
            copied.append(s)
    io.open(str(VERIFIED), "w", encoding="utf-8", newline="").write(json.dumps(existing, indent=1, ensure_ascii=False) + "\n")
    have = {v["stem"] for v in existing}
    need = [s for s in briefs if needs_second(answer(rows[s]), briefs[s][OPENING])]
    print("merged %d first readings (%d carried); second readings copied %d; need a second reading %d; still to read %d: %s"
          % (len(rows), sum(1 for d in decisions.values() if d["carry"]), len(copied), len(need),
             len([s for s in need if s not in have]), [s for s in need if s not in have]))


def decide(f, g, opening):
    # point 4 first: such a first reading decides the record, whatever a carried second reading says
    if not needs_second(f, opening):
        if f["finding"] is False:
            return "not adjusted", "the first reading finds no transfer the adopted figure covers (point 4)"
        return "not adjusted", ("the first reading's transferred amount %s is under 5%% of the opening reserves %s (point 4)"
                                % (f["takeon_amount_m"], opening))
    if g is None:
        raise ValueError("a record that needs a second reading has none")
    if f["finding"] is not True or g["finding"] is not True:
        return "not adjusted", "the readings do not both find a covered transfer (%s, %s)" % (f["finding"], g["finding"])
    a1, a2 = f["takeon_amount_m"], g["takeon_amount_m"]
    if a1 is None or a2 is None:
        return "not adjusted", "a reading gives no transferred amount (%s, %s)" % (a1, a2)
    if abs(a1 - a2) > AGREE * max(abs(a1), abs(a2)):
        return "not adjusted", "the readings' amounts differ by more than 2%% (%s, %s)" % (a1, a2)
    if opening is None or opening <= 0 or a2 < MATERIAL * opening:
        return "not adjusted", "the amount %s is under 5%% of the opening reserves %s" % (a2, opening)
    for which, ans in (("first", f), ("second", g)):
        go = ans["gross_opening_m"]
        if go is not None and abs(go - opening) > AGREE * opening:
            return "not adjusted", "the %s reading's gross opening reserves %s are not the adopted %s within 2%%" % (which, go, opening)
    return "adjusted", "both readings find a covered transfer of %s (%.1f%% of the opening reserves)" % (a2, 100.0 * a2 / opening)


def short(text, n=480):
    text = " ".join(str(text or "").split())
    return text if len(text) <= n else text[:n].rsplit(" ", 1)[0] + " ..."


def score():
    briefs = briefs_of()
    merged = {v["stem"]: v for v in load(MERGED)}
    verified = {v["stem"]: v for v in load(VERIFIED)} if VERIFIED.exists() else {}
    problems, table, drafts = [], [], []
    for s, b in briefs.items():
        f, opening, pyd = answer(merged[s]), b[OPENING], b[ADOPTED]
        g = answer(verified[s]) if s in verified else None
        if needs_second(f, opening) and g is None:
            problems.append("%s needs a second reading" % s)
            continue
        if g is not None and answer_gaps(g):
            problems.append("%s: its second reading's answer: %s" % (s, "; ".join(answer_gaps(g))))
            continue
        outcome, reason = decide(f, g, opening)
        takeon = g["takeon_amount_m"] if outcome == "adjusted" else None
        row = {"stem": s, "first": f, "second": g, "adopted_figure_m": pyd, "opening_m": opening, "outcome": outcome,
               "reason": reason, "severity_pct": None if not opening or pyd is None else round(100.0 * pyd / opening, 3),
               "severity_pct_adjusted": None if takeon is None or pyd is None else round(100.0 * pyd / (opening + takeon), 3)}
        table.append(row)
        if outcome == "adjusted":
            v1, v2 = merged[s], verified[s]
            pages = []
            for p in (v2.get("pages") or []) + (v1.get("pages") or []):
                if isinstance(p, int) and not isinstance(p, bool) and p not in pages:
                    pages.append(p)
            drafts.append({"stem": s, "opening_reserves_m": opening, "takeon_m": takeon,
                           "takeon_m_readings": [f["takeon_amount_m"], g["takeon_amount_m"]], "pages": pages,
                           "quote": v2.get("quote") or v1.get("quote"),
                           "readings": ["%s: %s; carried: %s; %s" % (v1.get("first_reader"), f["finding"], f["carried"],
                                                                       short((f.get("evidence") if isinstance(f, dict) else None)
                                                                             or v1.get("reasoning"))),
                                        "second reading (%s): %s; carried: %s; %s" % (v2.get("recorded") or v2.get("reader"),
                                                                                     g["finding"], g["carried"], short(v2.get("why")))]})
    for pr in problems:
        print("  PROBLEM " + pr)
    if problems:
        raise SystemExit("score refused")
    counts = {}
    for r in table:
        counts[r["outcome"]] = counts.get(r["outcome"], 0) + 1
    io.open(str(RESULT), "w", encoding="utf-8").write(json.dumps(
        {"protocol": "error-rate-protocol.md, ninth amendment", "records": len(table), "outcomes": counts,
         "adjusted": [d["stem"] for d in drafts], "table": table}, indent=1, ensure_ascii=False))
    io.open(str(DRAFT), "w", encoding="utf-8").write(json.dumps(drafts, indent=1, ensure_ascii=False))
    print("records %d; outcomes %s" % (len(table), counts))
    for r in table:
        if r["outcome"] == "adjusted":
            print("  adjusted %-22s take-on %-10s opening %-10s severity %s%% -> %s%%"
                  % (r["stem"], r["second"]["takeon_amount_m"], r["opening_m"], r["severity_pct"], r["severity_pct_adjusted"]))
    print("written: %s, %s" % (RESULT.name, DRAFT.name))


if __name__ == "__main__":
    {"check": check, "merge": merge, "score": score}[sys.argv[1]]()
