r"""Merge and score the readings after the repairs (error-rate-protocol.md, fifth amendment, points 2 and 3).

merge
  - A record the carry-over decision kept takes its merged row from the census, second- or first-sample merge it
    was read in; every other record takes its first reading from error-rate-verdicts-third-batch-N.json, validated.
  - Figure source from the brief; a record read afresh must agree with its latest replay log; a carried record's
    source and clarified verdict must equal its earlier merge.
  - Verification set: the protocol's rule (score_error_rate.must_verify) over the third-sample and entrant records,
    plus a seeded random fifth of their remaining corrects, and every repaired record (fifth amendment, point 2).
    A carried record's second reading is copied from its earlier verification file, where it stands.
score
  - A's sampled records: the second sample's records still in A, a repaired one taking its reading after the
    repair, and the 110 of the third sample. Jeffreys posterior over their adjudicable records.
  - E, the entrants, read in full: counts.
  - The working sample's rate: 200,000 draws of A's rate from its posterior (numpy default_rng(20260914)), with
    A's adjudicable share estimated from its sample and E's errors counted in full. When E is empty it is A's.
  - Beside it: the 110 alone, and the 110 under the first readers' instruction.

    python score_error_rate_third.py check
    python score_error_rate_third.py merge
    python score_error_rate_third.py score
"""
import glob
import io
import json
import sys
from pathlib import Path

import numpy as np

SCR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCR))
import score_error_rate as ser  # noqa: E402
import score_error_rate_after_rerun as rr  # noqa: E402

THIRD = SCR / "error-rate-sample-third.json"
BRIEFS = SCR / "error-rate-briefs-third.json"
CARRY = SCR / "error-rate-carry-over-third.json"
MERGED = SCR / "error-rate-verdicts-third.json"
VSET = SCR / "error-rate-verification-set-third.json"
VERIFIED = SCR / "error-rate-verification-third.json"
RESULT = SCR / "error-rate-result-third.json"
FROM = {"census": (SCR / "error-rate-verdicts-census.json", SCR / "error-rate-verification-census.json"),
        "second sample": (SCR / "error-rate-verdicts-after.json", SCR / "error-rate-verification-after.json"),
        "first sample": (SCR / "error-rate-verdicts.json", SCR / "error-rate-verification.json")}
MC_SEED, MC_DRAWS = 20260914, 200000


def load(p):
    return json.load(io.open(str(p), encoding="utf-8"))


def briefs_of():
    return {b["stem"]: b for b in load(BRIEFS)}


def carried():
    return {d["stem"]: d["carried_from"] for d in load(CARRY)["decisions"] if d["carry_over"]}


def log_blocks_after_r213():
    """Each record's latest replay-log block: the R209 replays, then the R213 full replay, then the replay of the two
    records added to the extraction's register (replay-r213b.log). A later block replaces an earlier one."""
    blocks = rr.log_blocks()
    for name in ("replay-r213-full.log", "replay-r213b.log"):
        path = SCR / name
        if not path.exists():
            raise SystemExit("%s is missing: the records' latest replay log cannot be read" % name)
        current = None
        for ln in io.open(str(path), encoding="utf-8", errors="replace"):
            m = rr.HEADER.match(ln)
            if m:
                current = "syndicate_%s_%s" % (m.group(1), m.group(2))
                blocks[current] = []
                continue
            if current:
                blocks[current].append(ln.rstrip("\n"))
    return blocks


def batch_rows(stems, carry, problems):
    rows = {}
    for p in sorted(glob.glob(str(SCR / "error-rate-verdicts-third-batch-*.json"))):
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
            v["first_reader"] = "after repairs, %s" % Path(p).stem.replace("error-rate-verdicts-third-", "")
            rows[s] = v
    return rows


def check():
    briefs = briefs_of()
    stems = list(briefs)
    carry = carried()
    overruled = ser.overruled_stems()
    blocks = log_blocks_after_r213()
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
    print("readings %d of the %d records read afresh; without a reading: %s"
          % (len(rows), len(fresh), sorted(set(fresh) - set(rows))))
    for pr in problems:
        print("  PROBLEM " + pr)
    print("problems: %d" % len(problems))


def merge():
    briefs = briefs_of()
    stems = list(briefs)
    carry = carried()
    earlier = {name: {r["stem"]: r for r in load(paths[0])} for name, paths in FROM.items()}
    overruled = ser.overruled_stems()
    blocks = log_blocks_after_r213()
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

    sampled = [s for s in stems if briefs[s]["role"] in ("third", "entrant")]
    repaired = [s for s in stems if briefs[s]["role"] == "repaired"]
    sets = ser.must_verify(sampled, rows, briefs, overruled)
    rest = sorted(s for s in sampled if s not in sets["all"] and rows[s]["clarified_verdict"] == "correct")
    rng = np.random.default_rng(ser.SEED)
    k = int(np.ceil(0.2 * len(rest)))
    pick = sorted(rest[int(i)] for i in rng.choice(len(rest), size=k, replace=False)) if rest else []
    vset = {name: sorted(members) for name, members in sets.items() if name != "all"}
    vset.update({"random_fifth_of_remaining_corrects": pick, "seed": ser.SEED, "every_repaired_record": sorted(repaired),
                 "all": sorted(set(sets["all"]) | set(pick) | set(repaired))})
    io.open(str(VSET), "w", encoding="utf-8").write(json.dumps(vset, indent=1))
    carried_second = []
    for name, (_merged, verification) in FROM.items():
        if verification.exists():
            carried_second += [dict(v, carried_over_from=verification.name) for v in load(verification)
                               if carry.get(v["stem"]) == name]
    existing = load(VERIFIED) if VERIFIED.exists() else []
    have = {v["stem"] for v in existing}
    existing += [v for v in carried_second if v["stem"] not in have]
    io.open(str(VERIFIED), "w", encoding="utf-8").write(json.dumps(existing, indent=1, ensure_ascii=False))
    done = {v["stem"] for v in existing}
    print("verification set %d; second readings carried over %d; still to read %d: %s"
          % (len(vset["all"]), len(carried_second), len(set(vset["all"]) - done), sorted(set(vset["all"]) - done)))


def counts(final):
    e = sum(1 for v in final.values() if v == "error")
    c = sum(1 for v in final.values() if v == "correct")
    u = sum(1 for v in final.values() if v == "undeterminable")
    return {"errors": e, "correct": c, "undeterminable": u, "adjudicable_n": e + c, "posterior": ser.posterior(e, e + c)}


def score():
    third = load(THIRD)
    briefs = briefs_of()
    stems = list(briefs)
    rows = {v["stem"]: v for v in load(MERGED)}
    vset = load(VSET)
    verified = {v["stem"]: v for v in load(VERIFIED)}
    if set(vset["all"]) - set(verified):
        raise SystemExit("not yet verified: %s" % sorted(set(vset["all"]) - set(verified)))
    now = {s: (verified[s]["verdict"] if s in verified else rows[s]["clarified_verdict"]) for s in stems}
    after_final = load(SCR / "error-rate-result-after-rerun.json")["rules"]["clarified"]["final_verdicts"]
    census_final = load(SCR / "error-rate-census-result.json")["final_verdicts"]

    A_final = {}
    for s in third["second_sample_still_in_A"]:
        A_final[s] = now[s] if briefs.get(s, {}).get("role") == "repaired" else after_final[s]
    for s in third["third"]["stems"]:
        A_final[s] = now[s]
    E_final = {s: now[s] for s in third["E_entrants"]["stems"]}
    T_final = {s: now[s] for s in third["third"]["stems"]}
    T_first = {s: rows[s]["verdict"] for s in third["third"]["stems"]}
    A, E, T, T1 = counts(A_final), counts(E_final), counts(T_final), counts(T_first)

    nA = A["adjudicable_n"] + A["undeterminable"]
    share = A["adjudicable_n"] / nA
    NA_adj = third["A"]["n"] * share
    draws = np.random.default_rng(MC_SEED).beta(0.5 + A["errors"], 0.5 + A["correct"], size=MC_DRAWS)
    ws = (NA_adj * draws + E["errors"]) / (NA_adj + E["adjudicable_n"])
    repaired = [{"stem": s, "before": after_final.get(s, census_final.get(s)), "after": now[s],
                 "why": briefs[s].get("repaired_why")} for s in stems if briefs[s]["role"] == "repaired"]
    result = {
        "protocol": "error-rate-protocol.md, fifth amendment, points 2 and 3",
        "exposure_results_run_id": third["exposure_results_run_id"],
        "A_sampled": dict(A, n_records=len(A_final), description="second-sample records still in A (a repaired one "
                          "read after its repair) and the third sample"),
        "E_entrants": dict(E, n_records=len(E_final)),
        "working_sample": {"mean": float(ws.mean()), "ci95_equal_tailed": [float(np.percentile(ws, 2.5)),
                                                                           float(np.percentile(ws, 97.5))],
                           "A_n": third["A"]["n"], "A_adjudicable_share": share, "mc_draws": MC_DRAWS, "mc_seed": MC_SEED},
        "third_sample_alone": T,
        "third_sample_first_readers_instruction": T1,
        "repaired_records": repaired,
        "final_verdicts": {"A": A_final, "E": E_final},
        "second_readings": len(verified),
    }
    io.open(str(RESULT), "w", encoding="utf-8").write(json.dumps(result, indent=1))
    p = A["posterior"]
    print("A: %d records, errors %d, correct %d, undeterminable %d; mean %.4f, 95%% CrI [%.4f, %.4f]"
          % (len(A_final), A["errors"], A["correct"], A["undeterminable"], p["mean"], *p["ci95_equal_tailed"]))
    print("E: %d entrants, errors %d, correct %d, undeterminable %d" % (len(E_final), E["errors"], E["correct"], E["undeterminable"]))
    print("working sample: mean %.4f, 95%% CrI [%.4f, %.4f]" % (ws.mean(), np.percentile(ws, 2.5), np.percentile(ws, 97.5)))
    print("third sample alone: errors %d of %d; first readers' instruction: errors %d of %d"
          % (T["errors"], T["adjudicable_n"], T1["errors"], T1["adjudicable_n"]))
    for r in repaired:
        print("  repaired %-22s %s -> %s" % (r["stem"], r["before"], r["after"]))
    print("written: %s" % RESULT.name)


if __name__ == "__main__":
    {"merge": merge, "score": score, "check": check}[sys.argv[1]]()
