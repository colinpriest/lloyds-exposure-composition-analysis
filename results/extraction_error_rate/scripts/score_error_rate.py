r"""Merge the error-rate verdicts, apply the protocol's clarification, pick what the second reader verifies, and compute the posterior.

The protocol (error-rate-protocol.md: fixed 11 September 2026, amended twice before any
adjudication, clarified after batch 1's first reading and before any second reading, and refined
three times) scores each sampled record correct, error or undeterminable against its filing.

First readings. Six readers worked from the same brief, pack and page tool. Every verdict must
carry pages, a quotation (unless undeterminable) and arithmetic or reasoning, or the merge refuses
it. Their instruction preferred a movement the filing states over its triangle.

The clarification. A figure whose source is a triangle is checked against the triangle recomputed
over underwriting years up to t-2, because that is the manuscript's numerator; any other figure
against the movement the filing states. The source is read from the pipeline's own record
(figure_source), not from the route field alone:
  stated    the sign veto overruled the route's triangle (refinement 1: the R197 register);
  triangle  a rag_triangle route that carries its triangle;
  stated    a rag_triangle route that carries no triangle: the RAG step's fallback (refinement 3);
  triangle  an empty route whose notes carry a code override that computed the adopted figure
            (refinement 3);
  stated    anything else.
The merge refuses to run if a sampled rag_triangle route disagrees with its own replay log. A route
that carries a triangle must print no other method, unless the register lists it, in which case the
log must print the in-RAG sign check. A route that carries none must print one. The evidence is
fallback-routes-pre-r208.json, frozen from measure_fallback_routes.py before R208 renamed the routes.

For a triangle-sourced record the clarified verdict is:
  undeterminable  if the first reader scored undeterminable;
  error           if the first reader recorded an error of another kind than magnitude or sign
                  (scope, basis): it stands for the second reader to settle;
  undeterminable  if no recomputation was recorded;
  error           if the signs differ (both non-zero; the protocol's (b) has no threshold), or
                  |adopted - recomputation| > max(0.5, 0.05 x |adopted|);
  correct         otherwise.
Other records keep the first reader's verdict. The verdict without refinement 3 (route field and
refinement 1 only) is kept beside it, because the protocol says the result reports what refinement 3
moved.

Second reading. The second reader (the editor) verifies against the filing: every clarified error,
every first-reader error, every record whose clarified verdict differs from the first reader's, every
undeterminable, every triangle-sourced record with no recomputation, every record whose source is not
what its route field says (refinements 1 and 3), and a seeded random fifth of the remaining corrects.
A second reading stands over both.

    python score_error_rate.py merge      merge, validate, clarify, pick the verification set
    python score_error_rate.py score      apply the verification; posterior under both rules

Estimator: Jeffreys prior Beta(1/2, 1/2); posterior Beta(1/2 + e, 1/2 + n - e) for e errors among
n adjudicable records. Undeterminable records are counted and excluded from n.
"""
import io
import json
import re
import sys
from pathlib import Path

import numpy as np
from scipy import stats

SCR = Path(__file__).resolve().parent
SAMPLE = SCR / "error-rate-sample.json"
BRIEFS = SCR / "error-rate-briefs.json"
MERGED = SCR / "error-rate-verdicts.json"
VSET = SCR / "error-rate-verification-set.json"
VERIFIED = SCR / "error-rate-verification.json"
RESULT = SCR / "error-rate-result.json"
ROUTE_EVIDENCE = SCR / "fallback-routes-pre-r208.json"
OVERRULED = Path(r"D:/dev/lloyds_reserve_stress_testing/pdf_extraction/audit/triangle_overruled_by_sign_veto.json")
VERDICTS = ("correct", "error", "undeterminable")
SEED = 42
TRIANGLE_KEYS = ("triangle_type", "triangle_units", "triangle_source_page")
# the verify_triangles override, computed from the models' own triangles
CODE_OVERRIDE = re.compile(r"\[CODE OVERRIDE: (?:Model|LLM) said PYD=-?\d+(?:\.\d+)?[^\]]*?"
                           r"but code computed \+?(-?\d+(?:\.\d+)?)")


def load(p):
    return json.load(io.open(str(p), encoding="utf-8"))


def tolerance(adopted):
    return max(0.5, 0.05 * abs(adopted))


def overruled_stems():
    """Records whose route field says 'rag_triangle' although the pipeline overruled the triangle
    and adopted the filing's provisions note (R197): their figure's source is the note."""
    reg = load(OVERRULED)
    return frozenset(r["stem"] for r in reg["sign_veto_overrides"]["records"]
                     if r.get("source_of_adopted_figure") == "the filing's provisions note")


def carries_triangle(route):
    return any((route or {}).get(k) is not None for k in TRIANGLE_KEYS)


def route_field_says(brief):
    return "triangle" if (brief.get("route") or {}).get("source") == "rag_triangle" else "stated"


def figure_source(brief, overruled=frozenset(), refinement_3=True):
    """('triangle' | 'stated', why): where the adopted figure came from, read from the pipeline's own record."""
    route = brief.get("route") or {}
    if brief.get("stem") in overruled:
        return "stated", ("the sign veto overruled the route's triangle and the provisions note's figure "
                          "was adopted (refinement 1)")
    if not refinement_3:
        return route_field_says(brief), "the route field (without refinement 3)"
    if route.get("source") == "confirmed_figure":
        if route.get("figure_kind") == "triangle":
            return "triangle", ("a figure two readings confirmed from a printed triangle "
                                "(data/pyd_confirmed_figures.json)")
        return "stated", "a figure two readings confirmed as the filing states it (data/pyd_confirmed_figures.json)"
    if route.get("source") == "rag_triangle":
        if carries_triangle(route):
            return "triangle", "a rag_triangle route that carries its triangle"
        return "stated", "a rag_triangle route that carries no triangle: the RAG step's fallback (refinement 3)"
    adopted = brief.get("adopted_prior_year_development_m_report_currency")
    tags = CODE_OVERRIDE.findall(brief.get("model_notes") or "")
    if route.get("source") is None and tags and adopted is not None:
        computed, adopted = float(tags[-1]), float(adopted)
        if abs(computed - adopted) <= max(0.01, 0.005 * abs(adopted)):
            return "triangle", "an empty route whose code override computed the adopted figure (refinement 3)"
    return "stated", "no triangle produced the adopted figure"


def clarified(first, brief, overruled=frozenset(), refinement_3=True):
    """The clarified verdict and why, from the first reading and the brief."""
    source, why = figure_source(brief, overruled, refinement_3)
    if source != "triangle":
        return first["verdict"], "checked against the stated movement (%s): the first reader's verdict" % why
    if first["verdict"] == "undeterminable":
        return "undeterminable", "the first reader could not settle it"
    kind = str(first.get("error_kind") or "")
    if first["verdict"] == "error" and kind and kind not in ("magnitude", "sign"):
        return "error", "the first reader's %s error stands for the second reader" % kind
    rec = first.get("triangle_recomputation_m")
    if rec is None:
        return "undeterminable", "triangle-sourced, but no triangle recomputation was recorded"
    adopted = float(brief["adopted_prior_year_development_m_report_currency"])
    # the protocol's error (b) has no magnitude threshold: any opposite sign, both figures non-zero
    if adopted != 0 and rec != 0 and (adopted > 0) != (rec > 0):
        return "error", "sign: adopted %+.3f against the triangle's %+.3f" % (adopted, rec)
    if abs(adopted - rec) > tolerance(adopted):
        return "error", "magnitude: adopted %+.3f, triangle %+.3f, tolerance %.3f" % (adopted, rec, tolerance(adopted))
    return "correct", "adopted %+.3f within %.3f of the triangle's %+.3f" % (adopted, tolerance(adopted), rec)


def route_evidence_problems(stems, briefs, overruled, evidence=None):
    """Sampled rag_triangle routes that disagree with their own replay log (refinement 3's correspondence)."""
    rows = {r["stem"]: r for r in (evidence if evidence is not None else load(ROUTE_EVIDENCE)["rows"])}
    problems = []
    for s in stems:
        route = briefs[s].get("route") or {}
        if route.get("source") != "rag_triangle":
            continue
        logged = (rows.get(s) or {}).get("non_triangle_methods_in_log")
        if logged is None:
            problems.append("%s: no replay-log evidence for its route" % s)
        elif s in overruled:
            if "provisions_over_triangle" not in logged:
                problems.append("%s: in the sign-veto register, but its log does not print the in-RAG sign check" % s)
        elif carries_triangle(route) and logged:
            problems.append("%s: the route carries a triangle but its log prints %s" % (s, logged))
        elif not carries_triangle(route) and not logged:
            problems.append("%s: the route carries no triangle but its log prints no other method" % s)
    return problems


def must_verify(stems, rows, briefs, overruled=frozenset()):
    """The records the second reader must verify, by reason, and their union."""
    src = {s: figure_source(briefs[s], overruled)[0] for s in stems}
    sets = {
        "clarified_errors": {s for s in stems if rows[s]["clarified_verdict"] == "error"},
        "first_reader_errors": {s for s in stems if rows[s]["verdict"] == "error"},
        "verdicts_the_clarification_changed": {s for s in stems if rows[s]["verdict"] != rows[s]["clarified_verdict"]},
        "undeterminable": {s for s in stems if "undeterminable" in (rows[s]["verdict"], rows[s]["clarified_verdict"])},
        "triangle_sourced_without_recomputation": {s for s in stems if src[s] == "triangle"
                                                    and rows[s].get("triangle_recomputation_m") is None},
        "source_is_not_the_route_field": {s for s in stems if src[s] != route_field_says(briefs[s])},
    }
    sets["all"] = set().union(*sets.values())
    return sets


def merge():
    stems = load(SAMPLE)["primary"]["stems"]
    briefs = {b["stem"]: b for b in load(BRIEFS)}
    rows, problems = {}, []
    for b in range(1, 7):
        p = SCR / ("error-rate-verdicts-batch-%d.json" % b)
        if not p.exists():
            problems.append("batch %d missing" % b)
            continue
        for v in load(p):
            s = v.get("stem")
            why = []
            if s not in stems:
                why.append("not in the sample")
            if v.get("verdict") not in VERDICTS:
                why.append("verdict %r" % v.get("verdict"))
            if not v.get("pages"):
                why.append("no pages")
            if v.get("verdict") != "undeterminable" and not (v.get("quote") or "").strip():
                why.append("no quotation")
            if not (v.get("arithmetic") or v.get("reasoning") or "").strip():
                why.append("no arithmetic or reasoning")
            if s in rows:
                why.append("duplicate")
            if why:
                problems.append("%s: %s" % (s, "; ".join(why)))
                continue
            v["first_reader"] = "batch %d" % b
            rows[s] = v
    missing = [s for s in stems if s not in rows]
    if missing:
        problems.append("no verdict for: %s" % missing)
    overruled = overruled_stems()
    problems += route_evidence_problems(stems, briefs, overruled)
    print("verdicts merged: %d of %d" % (len(rows), len(stems)))
    for pr in problems:
        print("  PROBLEM " + pr)
    if problems:
        raise SystemExit("merge refused: fix the batches or the route evidence first")
    for s in stems:
        rows[s]["figure_source"], rows[s]["figure_source_why"] = figure_source(briefs[s], overruled)
        rows[s]["clarified_verdict"], rows[s]["clarified_why"] = clarified(rows[s], briefs[s], overruled)
        rows[s]["clarified_verdict_without_refinement_3"] = clarified(rows[s], briefs[s], overruled, refinement_3=False)[0]
    io.open(str(MERGED), "w", encoding="utf-8").write(json.dumps([rows[s] for s in stems], indent=1, ensure_ascii=False))

    sets = must_verify(stems, rows, briefs, overruled)
    rest = sorted(s for s in stems if s not in sets["all"] and rows[s]["clarified_verdict"] == "correct")
    rng = np.random.default_rng(SEED)
    k = int(np.ceil(0.2 * len(rest)))
    pick = sorted(rest[int(i)] for i in rng.choice(len(rest), size=k, replace=False)) if rest else []
    vset = {name: sorted(members) for name, members in sets.items() if name != "all"}
    vset.update({"random_fifth_of_remaining_corrects": pick, "seed": SEED, "all": sorted(sets["all"] | set(pick))})
    io.open(str(VSET), "w", encoding="utf-8").write(json.dumps(vset, indent=1))
    count = lambda key: {v: sum(1 for s in stems if rows[s][key] == v) for v in VERDICTS}
    print("figure source: %s" % {src: sum(1 for s in stems if rows[s]["figure_source"] == src) for src in ("triangle", "stated")})
    print("first readers' rule:        %s" % count("verdict"))
    print("clarified rule:             %s" % count("clarified_verdict"))
    print("clarified, no refinement 3: %s" % count("clarified_verdict_without_refinement_3"))
    print("refinement 3 moved: %s" % [s for s in stems
                                      if rows[s]["clarified_verdict"] != rows[s]["clarified_verdict_without_refinement_3"]])
    for name in vset:
        if isinstance(vset[name], list):
            print("  %-42s %2d  %s" % (name, len(vset[name]), vset[name] if len(vset[name]) <= 8 else ""))


def posterior(e, n):
    post = stats.beta(0.5 + e, 0.5 + n - e)
    return {"prior": "Beta(0.5, 0.5)", "alpha": 0.5 + e, "beta": 0.5 + n - e,
            "mean": float(post.mean()), "ci95_equal_tailed": [float(post.ppf(0.025)), float(post.ppf(0.975))]}


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
                     "posterior": posterior(e, e + c), "second_reading_overturned": overturned,
                     "final_verdicts": final}
    moved = [{"stem": s, "clarified": rows[s]["clarified_verdict"],
              "without_refinement_3": rows[s]["clarified_verdict_without_refinement_3"],
              "figure_source_why": rows[s]["figure_source_why"]}
             for s in stems if rows[s]["clarified_verdict"] != rows[s]["clarified_verdict_without_refinement_3"]]
    result = {"protocol": ("error-rate-protocol.md (fixed 11 September 2026; amended twice, clarified and refined "
                           "three times on 13 September 2026, before any second reading under each)"),
              "population_n": load(SAMPLE)["population"]["n"], "sample_n": len(stems),
              "second_readings": len(verified), "rules": out,
              "refinement_3_moved_before_second_reading": moved,
              "note": ("the clarified rule is the protocol's; the first readers' instruction is reported for comparison, "
                       "without second-reading corrections, which were made under the clarified rule")}
    io.open(str(RESULT), "w", encoding="utf-8").write(json.dumps(result, indent=1))
    for rule in out:
        r = out[rule]
        print("%-26s errors %d, correct %d, undeterminable %d; mean %.4f, 95%% CrI [%.4f, %.4f]"
              % (rule, r["errors"], r["correct"], r["undeterminable"], r["posterior"]["mean"],
                 r["posterior"]["ci95_equal_tailed"][0], r["posterior"]["ci95_equal_tailed"][1]))
    print("second readings overturned under the clarified rule: %d" % len(out["clarified"]["second_reading_overturned"]))
    print("verdicts refinement 3 moved before second reading: %s" % [m["stem"] for m in moved])


if __name__ == "__main__":
    {"merge": merge, "score": score}[sys.argv[1]]()
