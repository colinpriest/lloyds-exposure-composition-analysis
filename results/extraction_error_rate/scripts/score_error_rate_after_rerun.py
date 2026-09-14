r"""Merge and score the error-rate study's new sample (protocol, fourth amendment).

The new primary sample (error-rate-sample-after.json: 60 records from the rebuilt working sample of 698)
is read and scored by the first sample's rules, with the fourth amendment's carry-over.

merge
  - A record the carry-over decision kept (error-rate-carry-over.json) takes its merged row from the first
    merge (error-rate-verdicts.json). Every other record takes its first reading from
    error-rate-verdicts-after-batch-N.json, validated as score_error_rate.py validates a first reading.
  - Each record's figure source is read by score_error_rate.figure_source from its new brief. For a record
    read afresh, the route must agree with the record's own latest replay log: the label the driver printed
    when it applied a RAG figure to the canonical model ("PYD overridden by RAG triangle", "... by RAG
    provisions", ...), or, for an empty route whose figure is a triangle's, a triangle cross-check line.
    R208 made the route name what produced the figure, so this checks that route, notes and log say the
    same thing. The merge refuses to run if any record read afresh disagrees.
  - The clarified verdict is computed for all 60 by score_error_rate.clarified. A carried record's must
    equal the one the first merge recorded.
  - The verification set is score_error_rate.must_verify over all 60, plus a seeded random fifth
    (numpy default_rng(42)) of the remaining corrects. Every second reading of a carried record
    (error-rate-verification.json) is copied to error-rate-verification-after.json, where it stands.
score
  - Every record in the verification set must have a second reading. The posterior is computed as
    score_error_rate.py computes it, under the clarified rule and under the first readers' instruction,
    and written beside the first result.

    python score_error_rate_after_rerun.py merge
    python score_error_rate_after_rerun.py score
"""
import glob
import io
import json
import re
import sys
from pathlib import Path

import numpy as np

SCR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCR))
import score_error_rate as ser  # noqa: E402

SAMPLE = SCR / "error-rate-sample-after.json"
BRIEFS = SCR / "error-rate-briefs-after.json"
CARRY = SCR / "error-rate-carry-over.json"
FIRST_MERGED = SCR / "error-rate-verdicts.json"
FIRST_VERIFIED = SCR / "error-rate-verification.json"
FIRST_RESULT = SCR / "error-rate-result.json"
MERGED = SCR / "error-rate-verdicts-after.json"
VSET = SCR / "error-rate-verification-set-after.json"
VERIFIED = SCR / "error-rate-verification-after.json"
RESULT = SCR / "error-rate-result-after-rerun.json"
HEADER = re.compile(r"^\[\d+/\d+\] Syndicate (\S+) / (\d{4})\b")
APPLIED = re.compile(r"^\s*\[([^\]]+)\] PYD (?:overridden|confirmed|filled) (?:by|from) (.+?):")
CROSS_CHECK = re.compile(r"^\s*\[([^\]]+)\] Triangle verification: (?:OVERRIDE|FILL|CONFIRMED)")
LABEL_ROUTE = {"RAG triangle": "rag_triangle", "RAG triangle (net triangle)": "rag_triangle",
               "RAG provisions": "rag_provisions", "RAG provisions text": "rag_provisions_text",
               "RAG general narrative": "rag_general_narrative", "RAG yoa narrative": "rag_yoa_narrative",
               "RAG pl narrative": "rag_pl_narrative"}


def load(p):
    return json.load(io.open(str(p), encoding="utf-8"))


def log_blocks():
    """Each record's latest replay-log block: the R209 replay, then R209's correction replay over it."""
    blocks = {}
    paths = sorted(glob.glob(str(SCR / "r209-replay-*.log"))) + [str(SCR / "r209-depth-replay.log")]
    if len(paths) != 9:
        raise SystemExit("expected the 8 R209 replay logs and the correction's replay log, found %d" % len(paths))
    for p in paths:
        current = None
        for ln in io.open(p, encoding="utf-8", errors="replace"):
            m = HEADER.match(ln)
            if m:
                current = "syndicate_%s_%s" % (m.group(1), m.group(2))
                blocks[current] = []
                continue
            if current:
                blocks[current].append(ln.rstrip("\n"))
    return blocks


#: a replay that stopped at an uncached call before writing the record (the offline guard)
STOPPED = re.compile(r"would call an external API \(cache miss\)|Skipping syndicate_\S+ and continuing")


def route_disagrees_with_log(brief, source, lines):
    """Why the route, the figure source and the replay log do not say the same thing, or None.

    A record whose latest replay stopped at an uncached call was not written by that replay, so its log
    cannot speak for the route. The record's own route is then the evidence: a rag_triangle route must carry
    its triangle (refinement 3), and the record is noted as checked from the record rather than the log."""
    if lines is None:
        return "no replay-log block"
    model = brief["canonical_model"]
    route = (brief.get("route") or {}).get("source")
    if any(STOPPED.search(ln) for ln in lines):
        if route == "rag_triangle" and not ser.carries_triangle(brief.get("route")):
            return "the latest replay stopped at an uncached call, and the rag_triangle route carries no triangle"
        print("  NOTE %s: the latest replay stopped at an uncached call and did not write the record; its route "
              "(%s) is checked from the record, which carries its triangle: %s"
              % (brief["stem"], route, ser.carries_triangle(brief.get("route"))))
        return None
    labels = [m.group(2) for m in (APPLIED.match(ln) for ln in lines) if m and m.group(1) == model]
    mapped = [LABEL_ROUTE[x] for x in labels if x in LABEL_ROUTE]
    if route is not None:
        if not mapped or mapped[-1] != route:
            return "route %s, but the log's last RAG figure applied to %s is %s" % (route, model, labels[-1:] or "none")
        return None
    if mapped:
        return "empty route, but the log applies a RAG figure to %s: %s" % (model, labels[-1])
    if source == "triangle" and not any((CROSS_CHECK.match(ln) or [None, None])[1] == model
                                        for ln in lines if CROSS_CHECK.match(ln)):
        return "an empty route read as a triangle's figure, but the log prints no triangle cross-check for %s" % model
    return None


def validate(v, stems):
    why = []
    if v.get("stem") not in stems:
        why.append("not in the sample")
    if v.get("verdict") not in ser.VERDICTS:
        why.append("verdict %r" % v.get("verdict"))
    if not v.get("pages"):
        why.append("no pages")
    if v.get("verdict") != "undeterminable" and not (v.get("quote") or "").strip():
        why.append("no quotation")
    if not (v.get("arithmetic") or v.get("reasoning") or "").strip():
        why.append("no arithmetic or reasoning")
    return why


def merge():
    stems = load(SAMPLE)["primary"]["stems"]
    briefs = {b["stem"]: b for b in load(BRIEFS)}
    carry = {d["stem"]: d["carry_over"] for d in load(CARRY)["decisions"]}
    first = {r["stem"]: r for r in load(FIRST_MERGED)}
    overruled = ser.overruled_stems()
    blocks = log_blocks()
    rows, problems = {}, []
    for p in sorted(glob.glob(str(SCR / "error-rate-verdicts-after-batch-*.json"))):
        for v in load(p):
            s = v.get("stem")
            why = validate(v, stems)
            if s in rows:
                why.append("duplicate")
            if s in carry and carry[s]:
                why.append("a carried-over record was read again")
            if why:
                problems.append("%s: %s" % (s, "; ".join(why)))
                continue
            v["first_reader"] = "new sample, %s" % Path(p).stem.replace("error-rate-verdicts-after-", "")
            rows[s] = v
    for s in stems:
        if carry.get(s):
            row = dict(first[s])
            row["first_reader"] = "%s (carried over from the first sample)" % row.get("first_reader")
            rows[s] = row
    missing = [s for s in stems if s not in rows]
    if missing:
        problems.append("no reading for: %s" % missing)
    for s in stems:
        if s not in rows:
            continue
        source, source_why = ser.figure_source(briefs[s], overruled)
        verdict, verdict_why = ser.clarified(rows[s], briefs[s], overruled)
        if carry.get(s):
            if (source, verdict) != (first[s]["figure_source"], first[s]["clarified_verdict"]):
                problems.append("%s: carried over, but its source or clarified verdict differs from the first merge "
                                "(%s/%s against %s/%s)" % (s, source, verdict, first[s]["figure_source"],
                                                           first[s]["clarified_verdict"]))
        else:
            disagreement = route_disagrees_with_log(briefs[s], source, blocks.get(s))
            if disagreement:
                problems.append("%s: %s" % (s, disagreement))
        rows[s]["figure_source"], rows[s]["figure_source_why"] = source, source_why
        rows[s]["clarified_verdict"], rows[s]["clarified_why"] = verdict, verdict_why
        rows[s]["clarified_verdict_without_refinement_3"] = ser.clarified(rows[s], briefs[s], overruled,
                                                                          refinement_3=False)[0]
    print("readings: %d of %d (%d carried over)" % (len(rows), len(stems), sum(1 for s in stems if carry.get(s))))
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

    carried_second = [dict(v, carried_over_from="error-rate-verification.json") for v in load(FIRST_VERIFIED)
                      if carry.get(v["stem"])]
    existing = load(VERIFIED) if VERIFIED.exists() else []
    have = {v["stem"] for v in existing}
    existing += [v for v in carried_second if v["stem"] not in have]
    io.open(str(VERIFIED), "w", encoding="utf-8").write(json.dumps(existing, indent=1, ensure_ascii=False))

    count = lambda key: {v: sum(1 for s in stems if rows[s][key] == v) for v in ser.VERDICTS}
    print("figure source: %s" % {src: sum(1 for s in stems if rows[s]["figure_source"] == src) for src in ("triangle", "stated")})
    print("first readers' rule:        %s" % count("verdict"))
    print("clarified rule:             %s" % count("clarified_verdict"))
    print("clarified, no refinement 3: %s" % count("clarified_verdict_without_refinement_3"))
    for name in vset:
        if isinstance(vset[name], list):
            print("  %-42s %2d  %s" % (name, len(vset[name]), vset[name] if len(vset[name]) <= 8 else ""))
    done = {v["stem"] for v in existing}
    print("second readings carried over: %d; still to read: %s" % (len(carried_second), sorted(set(vset["all"]) - done)))


def score():
    stems = load(SAMPLE)["primary"]["stems"]
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
    first = load(FIRST_RESULT)
    carry = {d["stem"]: d["carry_over"] for d in load(CARRY)["decisions"]}
    result = {"protocol": "error-rate-protocol.md, fourth amendment (13 September 2026)",
              "population_n": load(SAMPLE)["population"]["n"], "sample_n": len(stems),
              "carried_over": sum(1 for s in stems if carry.get(s)), "read_afresh": sum(1 for s in stems if not carry.get(s)),
              "second_readings": len(verified), "rules": out,
              "before_R209_R210": {"population_n": first["population_n"], "sample_n": first["sample_n"],
                                   "clarified": {k: first["rules"]["clarified"][k]
                                                 for k in ("errors", "correct", "undeterminable", "adjudicable_n", "posterior")},
                                   "first_readers_instruction": {k: first["rules"]["first_readers_instruction"][k]
                                                                 for k in ("errors", "correct", "undeterminable", "adjudicable_n", "posterior")}},
              "note": ("the clarified rule is the protocol's; the first readers' instruction is reported for comparison, "
                       "without second-reading corrections, which were made under the clarified rule")}
    io.open(str(RESULT), "w", encoding="utf-8").write(json.dumps(result, indent=1))
    for label, rules, n_pop in (("before (706)", result["before_R209_R210"], first["population_n"]),
                                ("after (%d)" % result["population_n"], out, result["population_n"])):
        for rule in ("clarified", "first_readers_instruction"):
            r = rules[rule]
            print("%-13s %-26s errors %d, correct %d, undeterminable %d; mean %.4f, 95%% CrI [%.4f, %.4f]"
                  % (label, rule, r["errors"], r["correct"], r["undeterminable"], r["posterior"]["mean"],
                     r["posterior"]["ci95_equal_tailed"][0], r["posterior"]["ci95_equal_tailed"][1]))
    print("second readings overturned under the clarified rule: %d" % len(out["clarified"]["second_reading_overturned"]))
    print("written: %s" % RESULT.name)


def check():
    """Validate the batch files present, as merge will, and write nothing.

    Structure (stems against the batch's own briefs, pages, quotation, arithmetic), a carried-over record
    read again, a triangle-sourced figure without its triangle recomputation (the readers' instruction asks
    for one), and route against the replay log. It prints problems and counts, and no verdict.

        python score_error_rate_after_rerun.py check
    """
    stems = load(SAMPLE)["primary"]["stems"]
    briefs = {b["stem"]: b for b in load(BRIEFS)}
    carry = {d["stem"]: d["carry_over"] for d in load(CARRY)["decisions"]}
    overruled = ser.overruled_stems()
    blocks = log_blocks()
    seen, problems = {}, []
    paths = sorted(glob.glob(str(SCR / "error-rate-verdicts-after-batch-*.json")))
    for p in paths:
        name = Path(p).name
        batch = load(p)
        want = {b["stem"] for b in load(SCR / name.replace("verdicts-after", "briefs-after"))}
        got = {v.get("stem") for v in batch}
        if got != want:
            problems.append("%s: stems not in its briefs %s; briefs without a reading %s"
                            % (name, sorted(got - want), sorted(want - got)))
        for v in batch:
            s = v.get("stem")
            why = validate(v, stems)
            if s in seen:
                why.append("duplicate (also in %s)" % seen[s])
            if carry.get(s):
                why.append("a carried-over record was read again")
            if s in briefs:
                source = ser.figure_source(briefs[s], overruled)[0]
                if source == "triangle" and v.get("verdict") != "undeterminable" and v.get("triangle_recomputation_m") is None:
                    why.append("triangle-sourced, but no triangle recomputation recorded")
                disagreement = route_disagrees_with_log(briefs[s], source, blocks.get(s))
                if disagreement:
                    why.append(disagreement)
            seen[s] = name
            if why:
                problems.append("%s (%s): %s" % (s, name, "; ".join(why)))
    fresh = [s for s in stems if not carry.get(s)]
    print("batch files %d; readings %d of the %d records read afresh; without a reading: %s"
          % (len(paths), len(seen), len(fresh), sorted(set(fresh) - set(seen))))
    for pr in problems:
        print("  PROBLEM " + pr)
    print("problems: %d" % len(problems))


if __name__ == "__main__":
    {"merge": merge, "score": score, "check": check}[sys.argv[1]]()
