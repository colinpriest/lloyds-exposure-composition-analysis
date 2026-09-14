r"""Merge and score the error-rate study's tail stratum (protocol, amendment point 3), never pooled with a primary sample.

The tail (error-rate-tail.json) is read and scored by the primary samples' rules.

merge
  - A record the carry-over decision kept (error-rate-carry-over-tail.json) takes its merged row from the merge
    of the sample it was read in: error-rate-verdicts-after.json (second sample) or error-rate-verdicts.json
    (first sample). Every other record takes its first reading from error-rate-verdicts-tail-batch-N.json,
    validated as score_error_rate.py validates a first reading.
  - Each record's figure source is read by score_error_rate.figure_source from its tail brief. For a record read
    afresh, the route must agree with the record's latest replay log (score_error_rate_after_rerun's check). A
    carried record's source and clarified verdict must equal the ones its sample's merge recorded.
  - The verification set is score_error_rate.must_verify over the tail, plus a seeded random fifth
    (numpy default_rng(42)) of the remaining corrects. A carried record's second reading is copied from its
    sample's verification file to error-rate-verification-tail.json, where it stands.
score
  - Every record in the verification set must have a second reading. The posterior is computed under the
    clarified rule and under the first readers' instruction, with the tail's own n.

    python score_error_rate_tail.py merge
    python score_error_rate_tail.py check
    python score_error_rate_tail.py score
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
from score_error_rate_third import log_blocks_after_r213  # noqa: E402

TAIL = SCR / "error-rate-tail.json"
BRIEFS = SCR / "error-rate-briefs-tail.json"
CARRY = SCR / "error-rate-carry-over-tail.json"
MERGED = SCR / "error-rate-verdicts-tail.json"
VSET = SCR / "error-rate-verification-set-tail.json"
VERIFIED = SCR / "error-rate-verification-tail.json"
RESULT = SCR / "error-rate-tail-result.json"
# every sample and census a tail reading may be carried from (implementation note 3; the take-on base census is not
# one, implementation note 5)
FROM = {name: paths for name, paths in (
    ("eighth census", (SCR / "error-rate-verdicts-eighth.json", SCR / "error-rate-verification-eighth.json")),
    ("third sample", (SCR / "error-rate-verdicts-third.json", SCR / "error-rate-verification-third.json")),
    ("take-on census", (SCR / "error-rate-verdicts-takeon.json", SCR / "error-rate-verification-takeon.json")),
    ("found in passing", (SCR / "error-rate-verdicts-passing.json", SCR / "error-rate-verification-passing.json")),
    ("census", (SCR / "error-rate-verdicts-census.json", SCR / "error-rate-verification-census.json")),
    ("second sample", (SCR / "error-rate-verdicts-after.json", SCR / "error-rate-verification-after.json")),
    ("first sample", (SCR / "error-rate-verdicts.json", SCR / "error-rate-verification.json")))
    if paths[0].exists()}


def load(p):
    return json.load(io.open(str(p), encoding="utf-8"))


def stems_of():
    return load(TAIL)["tail"]["stems"]


def carried():
    return {d["stem"]: d["carried_from"] for d in load(CARRY)["decisions"] if d["carry_over"]}


def merge():
    stems = stems_of()
    briefs = {b["stem"]: b for b in load(BRIEFS)}
    carry = carried()
    earlier = {name: {r["stem"]: r for r in load(paths[0])} for name, paths in FROM.items()}
    overruled = ser.overruled_stems()
    blocks = log_blocks_after_r213()
    rows, problems = {}, []
    for p in sorted(glob.glob(str(SCR / "error-rate-verdicts-tail-batch-*.json"))):
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
            v["first_reader"] = "tail, %s" % Path(p).stem.replace("error-rate-verdicts-tail-", "")
            rows[s] = v
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

    sets = ser.must_verify(stems, rows, briefs, overruled)
    rest = sorted(s for s in stems if s not in sets["all"] and rows[s]["clarified_verdict"] == "correct")
    rng = np.random.default_rng(ser.SEED)
    k = int(np.ceil(0.2 * len(rest)))
    pick = sorted(rest[int(i)] for i in rng.choice(len(rest), size=k, replace=False)) if rest else []
    vset = {name: sorted(members) for name, members in sets.items() if name != "all"}
    vset.update({"random_fifth_of_remaining_corrects": pick, "seed": ser.SEED, "all": sorted(sets["all"] | set(pick))})
    io.open(str(VSET), "w", encoding="utf-8").write(json.dumps(vset, indent=1))

    carried_second = []
    for name, (_merged, verification) in FROM.items():
        if not verification.exists():
            continue
        carried_second += [dict(v, carried_over_from=verification.name) for v in load(verification)
                           if carry.get(v["stem"]) == name]
    existing = load(VERIFIED) if VERIFIED.exists() else []
    have = {v["stem"] for v in existing}
    existing += [v for v in carried_second if v["stem"] not in have]
    io.open(str(VERIFIED), "w", encoding="utf-8").write(json.dumps(existing, indent=1, ensure_ascii=False))
    count = lambda key: {v: sum(1 for s in stems if rows[s][key] == v) for v in ser.VERDICTS}
    print("figure source: %s" % {src: sum(1 for s in stems if rows[s]["figure_source"] == src) for src in ("triangle", "stated")})
    print("first readers' rule: %s" % count("verdict"))
    print("clarified rule:      %s" % count("clarified_verdict"))
    for name in vset:
        if isinstance(vset[name], list):
            print("  %-42s %2d  %s" % (name, len(vset[name]), vset[name] if len(vset[name]) <= 8 else ""))
    done = {v["stem"] for v in existing}
    print("second readings carried over: %d; still to read: %s" % (len(carried_second), sorted(set(vset["all"]) - done)))


def check():
    """Validate the tail batch files present, as merge will, and write nothing."""
    stems = stems_of()
    briefs = {b["stem"]: b for b in load(BRIEFS)}
    carry = carried()
    overruled = ser.overruled_stems()
    blocks = log_blocks_after_r213()
    seen, problems = {}, []
    for p in sorted(glob.glob(str(SCR / "error-rate-verdicts-tail-batch-*.json"))):
        name = Path(p).name
        batch = load(p)
        want = {b["stem"] for b in load(SCR / name.replace("verdicts-tail", "briefs-tail"))}
        got = {v.get("stem") for v in batch}
        if got != want:
            problems.append("%s: stems not in its briefs %s; briefs without a reading %s"
                            % (name, sorted(got - want), sorted(want - got)))
        for v in batch:
            s = v.get("stem")
            why = rr.validate(v, stems)
            if s in seen:
                why.append("duplicate (also in %s)" % seen[s])
            if s in carry:
                why.append("a carried-over record was read again")
            if s in briefs:
                source = ser.figure_source(briefs[s], overruled)[0]
                if source == "triangle" and v.get("verdict") != "undeterminable" and v.get("triangle_recomputation_m") is None:
                    why.append("triangle-sourced, but no triangle recomputation recorded")
                disagreement = rr.route_disagrees_with_log(briefs[s], source, blocks.get(s))
                if disagreement:
                    why.append(disagreement)
            seen[s] = name
            if why:
                problems.append("%s (%s): %s" % (s, name, "; ".join(why)))
    fresh = [s for s in stems if s not in carry]
    print("readings %d of the %d tail records read afresh; without a reading: %s"
          % (len(seen), len(fresh), sorted(set(fresh) - set(seen))))
    for pr in problems:
        print("  PROBLEM " + pr)
    print("problems: %d" % len(problems))


def score():
    stems = stems_of()
    rows = {v["stem"]: v for v in load(MERGED)}
    vset = load(VSET)
    verified = {v["stem"]: v for v in load(VERIFIED)}
    if set(vset["all"]) - set(verified):
        raise SystemExit("not yet verified: %s" % sorted(set(vset["all"]) - set(verified)))
    out = {}
    for rule, key in (("clarified", "clarified_verdict"), ("first_readers_instruction", "verdict")):
        final, overturned = {}, []
        for s in stems:
            base = rows[s][key]
            if s in verified and rule == "clarified":
                v = verified[s]["verdict"]
                if v != base:
                    overturned.append({"stem": s, "was": base, "now": v, "why": verified[s].get("why")})
                final[s] = v
            else:
                final[s] = base
        e = sum(1 for s in stems if final[s] == "error")
        c = sum(1 for s in stems if final[s] == "correct")
        u = sum(1 for s in stems if final[s] == "undeterminable")
        out[rule] = {"errors": e, "correct": c, "undeterminable": u, "adjudicable_n": e + c,
                     "posterior": ser.posterior(e, e + c), "second_reading_overturned": overturned,
                     "final_verdicts": final}
    tail = load(TAIL)
    carry = carried()
    result = {"protocol": "error-rate-protocol.md, amendment point 3 (the tail stratum, never pooled)",
              "tail_n": len(stems), "definition": tail["definition"],
              "exposure_results_run_id": tail["exposure_results_run_id"],
              "carried_over": len(carry), "read_afresh": len(stems) - len(carry),
              "second_readings": len(verified), "rules": out,
              "overlap_with_primary_after": tail.get("overlap_with_primary_after"),
              "note": ("the clarified rule is the protocol's; the first readers' instruction is reported for comparison, "
                       "without second-reading corrections, which were made under the clarified rule")}
    io.open(str(RESULT), "w", encoding="utf-8").write(json.dumps(result, indent=1))
    for rule in ("clarified", "first_readers_instruction"):
        r = out[rule]
        print("tail (%d) %-26s errors %d, correct %d, undeterminable %d; mean %.4f, 95%% CrI [%.4f, %.4f]"
              % (len(stems), rule, r["errors"], r["correct"], r["undeterminable"], r["posterior"]["mean"],
                 r["posterior"]["ci95_equal_tailed"][0], r["posterior"]["ci95_equal_tailed"][1]))
    print("written: %s" % RESULT.name)


if __name__ == "__main__":
    {"merge": merge, "score": score, "check": check}[sys.argv[1]]()
