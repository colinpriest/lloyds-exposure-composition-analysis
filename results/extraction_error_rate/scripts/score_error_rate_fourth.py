r"""Score the fourth random draw (protocol/error-rate-protocol-fourth.md), written and committed before any reading.

Three steps, each refusing to overwrite what it writes:

    python score_error_rate_fourth.py merge  [--readings DIR] [--out DIR]
        Merges the first readings of batches 1-4 (first-batch-<n>.json) and the census stratum's two readings
        (census-reader-A.json, census-reader-B.json); refuses a reading without pages, a quotation (unless
        undeterminable), arithmetic or reasoning, a record outside its batch, a duplicate or a missing record, and a
        drawn rag_triangle route that does not carry its triangle. Applies the clarification and its refinements, with
        the protocol's one extension (a code_triangle route is a triangle's). Picks the verification set by the first
        protocol's rule (score_error_rate.must_verify, with the code_triangle route read as the triangle it names) and a
        random fifth of the remaining corrects from numpy.random.default_rng(seed), the draw's seed. Writes
        error-rate-verdicts-fourth.json, error-rate-census-fourth.json, error-rate-verification-set-fourth.json and
        error-rate-second-briefs-fourth.json: the BLIND briefs for the second reader, which carry the draw's brief and
        nothing of the first reading.

    python score_error_rate_fourth.py score  [--readings DIR] [--out DIR]
        Reads the second readings (second-readings.json; one per record of the verification set, each the first
        readings' schema) and writes error-rate-result-fourth.json: draw four's Jeffreys posterior under the clarified
        rule (a second reading stands over the first), under the first readers' instruction (no second-reading
        corrections), and with every undeterminable counted as an error; beside them, never pooled, the pooled rate and
        its 161 records still in the working sample; P(theta4 > 0.052); the census stratum's outcomes; and the
        working sample's rate built from F, K and C (protocol, "The analysis", point 3).

Readings default to fourth-sample/readings/ and outputs to fourth-sample/. The checks are
checks_score_error_rate_fourth.py beside this file (named so that the analysis suite does not collect it; run it with
python -m pytest -q checks_score_error_rate_fourth.py), and mutate_score_error_rate_fourth.py mutation-checks them.
"""
import argparse
import io
import json
import math
import sys
from pathlib import Path

import numpy as np
from scipy import stats

SCR = Path(__file__).resolve().parent
STUDY = SCR.parent
AN = STUDY.parent.parent
sys.path.insert(0, str(SCR))
import score_error_rate as ser  # noqa: E402

DRAW = STUDY / "fourth-sample" / "error-rate-sample-fourth.json"
FRAME = STUDY / "fourth-sample" / "error-rate-frame-fourth.json"
READINGS = STUDY / "fourth-sample" / "readings"
OUT = STUDY / "fourth-sample"
POOLED = STUDY / "third-sample" / "error-rate-result-third.json"
PROPAGATION = AN / "results" / "error_rate_propagation_results.json"
ADOPTED = "adopted_prior_year_development_m_report_currency"
VERDICTS = ser.VERDICTS
BATCHES = (1, 2, 3, 4)
CENSUS_READERS = ("A", "B")
PAPER_RATE = 0.052
WS_DRAWS = 200000
TRIANGLE_ROUTES = ("rag_triangle", "code_triangle")
#: the fields of a reading; none of them may reach the second reader's brief
READING_FIELDS = ("verdict", "filing_figure_m", "stated_movement_m", "pages", "quote", "arithmetic", "error_kind",
                  "basis_check", "page_binding_check", "opening_reserves", "triangle_recomputation_m",
                  "triangle_pages", "triangle_arithmetic", "reasoning", "clarified_verdict", "clarified_why",
                  "first_reader")


def load(p):
    return json.load(io.open(str(p), encoding="utf-8"))


def write_once(path, obj):
    path = Path(path)
    if path.exists():
        raise SystemExit("%s exists; it is written once" % path.name)
    path.parent.mkdir(parents=True, exist_ok=True)
    io.open(str(path), "w", encoding="utf-8", newline="\n").write(json.dumps(obj, indent=1, ensure_ascii=False) + "\n")


# --- the figure's source and the clarified verdict, with the protocol's one extension ------------------------------

def figure_source(brief, overruled=frozenset()):
    """score_error_rate.figure_source, with a code_triangle route read as the triangle it names (protocol, "What
    counts as an error")."""
    if (brief.get("route") or {}).get("source") == "code_triangle":
        return "triangle", "a code_triangle route: the code override computed the adopted figure from a triangle"
    return ser.figure_source(brief, overruled)


def route_field_says(brief):
    return "triangle" if (brief.get("route") or {}).get("source") in TRIANGLE_ROUTES else "stated"


def clarified(first, brief, overruled=frozenset()):
    """score_error_rate.clarified, with figure_source above."""
    source, why = figure_source(brief, overruled)
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
    adopted = float(brief[ADOPTED])
    if adopted != 0 and rec != 0 and (adopted > 0) != (rec > 0):
        return "error", "sign: adopted %+.3f against the triangle's %+.3f" % (adopted, rec)
    if abs(adopted - rec) > ser.tolerance(adopted):
        return "error", "magnitude: adopted %+.3f, triangle %+.3f, tolerance %.3f" % (adopted, rec,
                                                                                       ser.tolerance(adopted))
    return "correct", "adopted %+.3f within %.3f of the triangle's %+.3f" % (adopted, ser.tolerance(adopted), rec)


def must_verify(stems, rows, briefs, overruled=frozenset()):
    """score_error_rate.must_verify, with figure_source and route_field_says above."""
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


# --- merge ---------------------------------------------------------------------------------------------------------

def reading_problems(v, allowed):
    why = []
    if v.get("stem") not in allowed:
        why.append("not a record of this file")
    if v.get("verdict") not in VERDICTS:
        why.append("verdict %r" % v.get("verdict"))
    if not v.get("pages"):
        why.append("no pages")
    if v.get("verdict") != "undeterminable" and not (v.get("quote") or "").strip():
        why.append("no quotation")
    if not (v.get("arithmetic") or v.get("reasoning") or "").strip():
        why.append("no arithmetic or reasoning")
    return why


def read_file(path, allowed, label, problems):
    """{stem: reading} from one readings file, each reading validated; problems appended."""
    rows = {}
    if not Path(path).exists():
        problems.append("%s missing (%s)" % (label, Path(path).name))
        return rows
    for v in load(path):
        why = reading_problems(v, allowed)
        if v.get("stem") in rows:
            why.append("duplicate")
        if why:
            problems.append("%s %s: %s" % (label, v.get("stem"), "; ".join(why)))
            continue
        rows[v["stem"]] = v
    missing = sorted(set(allowed) - set(rows))
    if missing:
        problems.append("%s: no reading for %s" % (label, missing))
    return rows


def triangle_route_problems(briefs):
    """Since R208 a rag_triangle route names a triangle only when its figure was computed from it (protocol)."""
    return ["%s: a rag_triangle route without its triangle" % s for s, b in briefs.items()
            if (b.get("route") or {}).get("source") == "rag_triangle" and not ser.carries_triangle(b["route"])]


def census_outcome(a, b):
    """The census stratum's outcome from its two readings (protocol, "The analysis", point 3): an error both find is an
    error; both correct is correct; anything else is undeterminable."""
    va, vb = a["clarified_verdict"], b["clarified_verdict"]
    if va == vb == "error":
        figs = (a.get("filing_figure_m"), b.get("filing_figure_m"))
        agree = None not in figs and abs(figs[0] - figs[1]) <= ser.tolerance(figs[0])
        return "error", ("both readings find an error; their filing figures %s within the tolerance"
                         % ("agree" if agree else "do not agree"))
    if va == vb == "correct":
        return "correct", "both readings find it correct"
    if va == vb == "undeterminable":
        return "undeterminable", "neither reading settles it"
    return "undeterminable", "the readings disagree (%s, %s)" % (va, vb)


def merge(draw, readings_dir, out_dir, overruled=frozenset()):
    out_dir = Path(out_dir)
    targets = [out_dir / n for n in ("error-rate-verdicts-fourth.json", "error-rate-census-fourth.json",
                                     "error-rate-verification-set-fourth.json", "error-rate-second-briefs-fourth.json")]
    done = [t.name for t in targets if t.exists()]
    if done:
        raise SystemExit("already merged: %s exist; the verification set is picked once" % done)
    recs = draw["records"]
    drawn = [b for b in recs if b["role"] == "draw4"]
    census = [b for b in recs if b["role"] == "census4"]
    briefs = {b["stem"]: b for b in recs}
    stems = [b["stem"] for b in drawn]
    problems = triangle_route_problems({s: briefs[s] for s in stems})
    rows = {}
    for n in BATCHES:
        allowed = [b["stem"] for b in drawn if b["batch"] == n]
        got = read_file(Path(readings_dir) / ("first-batch-%d.json" % n), allowed, "batch %d" % n, problems)
        for s, v in got.items():
            v["first_reader"] = "batch %d" % n
        rows.update(got)
    census_rows = {}
    cstems = [b["stem"] for b in census]
    for r in CENSUS_READERS:
        census_rows[r] = read_file(Path(readings_dir) / ("census-reader-%s.json" % r), cstems, "census reader %s" % r,
                                   problems)
    warnings = ["%s: the reading's adopted %s is not the brief's %s" % (s, v.get("adopted_figure_m"), briefs[s][ADOPTED])
                for s, v in rows.items()
                if v.get("adopted_figure_m") is None or abs(float(v["adopted_figure_m"]) - briefs[s][ADOPTED]) > 0.001]
    if problems:
        raise SystemExit("merge refused:\n  " + "\n  ".join(problems))
    for s in stems:
        rows[s]["figure_source"], rows[s]["figure_source_why"] = figure_source(briefs[s], overruled)
        rows[s]["clarified_verdict"], rows[s]["clarified_why"] = clarified(rows[s], briefs[s], overruled)
    for r in CENSUS_READERS:
        for s, v in census_rows[r].items():
            v["reader"] = r
            v["figure_source"] = figure_source(briefs[s], overruled)[0]
            v["clarified_verdict"], v["clarified_why"] = clarified(v, briefs[s], overruled)
    outcomes = []
    for s in cstems:
        o, why = census_outcome(census_rows["A"][s], census_rows["B"][s])
        outcomes.append({"stem": s, "outcome": o, "why": why, "census_why": briefs[s].get("census_why"),
                         "readings": {r: census_rows[r][s] for r in CENSUS_READERS}})
    seed = int(draw["seed"]["seed"])
    sets = must_verify(stems, rows, briefs, overruled)
    rest = sorted(s for s in stems if s not in sets["all"] and rows[s]["clarified_verdict"] == "correct")
    k = int(math.ceil(0.2 * len(rest)))
    pick = sorted(rest[int(i)] for i in np.random.default_rng(seed).choice(len(rest), size=k, replace=False)) if rest else []
    vset = {name: sorted(m) for name, m in sets.items() if name != "all"}
    vset.update({"random_fifth_of_remaining_corrects": pick, "seed": str(seed), "all": sorted(sets["all"] | set(pick))})
    blind = [{k_: v_ for k_, v_ in briefs[s].items() if k_ not in READING_FIELDS} for s in vset["all"]]
    write_once(targets[0], {"warnings": warnings, "rows": [rows[s] for s in stems]})
    write_once(targets[1], outcomes)
    write_once(targets[2], vset)
    write_once(targets[3], blind)
    return rows, outcomes, vset, blind, warnings


# --- score ---------------------------------------------------------------------------------------------------------

def posterior(e, n):
    post = stats.beta(0.5 + e, 0.5 + n - e)
    return {"prior": "Beta(0.5, 0.5)", "alpha": 0.5 + e, "beta": 0.5 + n - e, "mean": float(post.mean()),
            "ci95_equal_tailed": [float(post.ppf(0.025)), float(post.ppf(0.975))]}


def tally(final):
    e = sum(1 for v in final.values() if v == "error")
    c = sum(1 for v in final.values() if v == "correct")
    u = sum(1 for v in final.values() if v == "undeterminable")
    return e, c, u


def working_sample_rate(e4, n4, n_drawn, frame_n, known, seed, draws=WS_DRAWS):
    """The working sample's rate from F, K and C (protocol, "The analysis", point 3).

    theta4 ~ Beta(1/2 + e4, 1/2 + n4 - e4); F's unread records (frame_n - n_drawn) hold round(unread x q) adjudicable
    records, q = n4 / n_drawn, and Binomial(that, theta4) errors; draw four's own e4 errors and n4 adjudicable records
    are added; `known` is {stem: verdict} for K and C, counted in full."""
    rng = np.random.default_rng(seed)
    unread = frame_n - n_drawn
    a_unread = int(round(unread * n4 / n_drawn))
    theta = rng.beta(0.5 + e4, 0.5 + n4 - e4, size=draws)
    errs_unread = rng.binomial(a_unread, theta)
    e_known = sum(1 for v in known.values() if v == "error")
    a_known = sum(1 for v in known.values() if v in ("error", "correct"))
    rate = (errs_unread + e4 + e_known) / float(a_unread + n4 + a_known)
    return {"mean": float(rate.mean()), "ci95_equal_tailed": [float(np.percentile(rate, 2.5)),
                                                             float(np.percentile(rate, 97.5))],
            "draws": draws, "seed": str(seed), "unread_in_F": unread, "adjudicable_unread_in_F": a_unread,
            "draw_four": {"errors": e4, "adjudicable": n4},
            "known": {"errors": e_known, "adjudicable": a_known,
                      "undeterminable": sum(1 for v in known.values() if v == "undeterminable"), "n": len(known)}}


def score(draw, readings_dir, out_dir, beside, known_k, frame_n):
    out_dir = Path(out_dir)
    target = out_dir / "error-rate-result-fourth.json"
    if target.exists():
        raise SystemExit("%s exists; draw four is scored once" % target.name)
    merged = load(out_dir / "error-rate-verdicts-fourth.json")["rows"]
    rows = {v["stem"]: v for v in merged}
    vset = load(out_dir / "error-rate-verification-set-fourth.json")
    outcomes = load(out_dir / "error-rate-census-fourth.json")
    problems = []
    second = read_file(Path(readings_dir) / "second-readings.json", vset["all"], "second readings", problems)
    if problems:
        raise SystemExit("score refused:\n  " + "\n  ".join(problems))
    stems = [b["stem"] for b in draw["records"] if b["role"] == "draw4"]
    clar, first, overturned = {}, {}, []
    for s in stems:
        first[s] = rows[s]["verdict"]
        clar[s] = rows[s]["clarified_verdict"]
        if s in second:
            if second[s]["verdict"] != clar[s]:
                overturned.append({"stem": s, "was": clar[s], "now": second[s]["verdict"],
                                   "second_filing_figure_m": second[s].get("filing_figure_m"),
                                   "first_filing_figure_m": rows[s].get("filing_figure_m")})
            clar[s] = second[s]["verdict"]
    e, c, u = tally(clar)
    fe, fc, fu = tally(first)
    seed = int(draw["seed"]["seed"])
    post = stats.beta(0.5 + e, 0.5 + c)
    known = dict(known_k)
    known.update({o["stem"]: o["outcome"] for o in outcomes})
    result = {
        "protocol": "protocol/error-rate-protocol-fourth.md",
        "n_drawn": len(stems), "frame_n": frame_n, "second_readings": len(second),
        "clarified": {"errors": e, "correct": c, "undeterminable": u, "adjudicable_n": e + c,
                      "posterior": posterior(e, e + c), "second_reading_overturned": overturned, "final_verdicts": clar},
        "first_readers_instruction": {"errors": fe, "correct": fc, "undeterminable": fu, "adjudicable_n": fe + fc,
                                      "posterior": posterior(fe, fe + fc),
                                      "note": "without second-reading corrections, as before"},
        "undeterminables_as_errors": {"errors": e + u, "adjudicable_n": e + c + u, "posterior": posterior(e + u, e + c + u)},
        "P_theta4_gt_0_052": float(post.sf(PAPER_RATE)),
        "beside_never_pooled": beside,
        "census_stratum": [{k: o[k] for k in ("stem", "outcome", "why", "census_why")} for o in outcomes],
        "working_sample_rate": working_sample_rate(e, e + c, len(stems), frame_n, known, seed),
        "known_verdicts_K_and_C": known,
    }
    write_once(target, result)
    return result


def beside_rates():
    """The pooled rate and its 161 records still in the working sample, as their own files record them."""
    a = load(POOLED)["A_sampled"]
    rp = load(PROPAGATION)["rate_population"]
    return {"pooled": {"source": "third-sample/error-rate-result-third.json A_sampled", "errors": a["errors"],
                       "adjudicable_n": a["adjudicable_n"], "posterior": a["posterior"]},
            "pooled_161_still_in_W": {"source": "results/error_rate_propagation_results.json rate_population",
                                      "n": rp["n_in_current_working_sample"],
                                      "verdicts": rp["verdicts_in_current_working_sample"],
                                      "posterior": rp["posterior_in_current_working_sample"]}}


def k_final_verdicts():
    """Each K record's final verdict at its final figure (protocol, "The analysis", point 3): the latest set's second
    reading where one exists, else its clarified verdict; a record whose figure a register or the extraction has since
    moved to the readings' figure is correct."""
    import draw_error_rate_fourth as d4
    frame = load(FRAME)
    loader = d4.Loader()
    sets = {name: ({b["stem"]: b for b in load(STUDY / bf)},
                   {v["stem"]: v for v in load(STUDY / vf) if v.get("clarified_verdict")},
                   {v["stem"]: v for v in load(STUDY / sf)}) for name, bf, vf, sf in d4.SCORED}
    later = {"syndicate_" + r["stem"]: r for r in load(STUDY / "tenth-census" / "entrants" / "entrants-result.json")["records"]}
    later_fip = {"syndicate_" + r["stem"]: r for r in load(STUDY / "tenth-census" / "census-tenth-result.json")["found_in_passing"]}
    out = {}
    for k in frame["K_checked"]["records"]:
        s, name = k["stem"], k["latest_figure_verdict"]
        now = loader.brief(s)[ADOPTED]
        if name in sets:
            briefs, merged, second = sets[name]
            read = briefs[s][ADOPTED]
            final = second[s]["verdict"] if s in second else merged[s]["clarified_verdict"]
        else:
            r = later.get(s) or later_fip[s]
            read = r["adopted_m"]
            vs = [str(v.get("verdict", "")) for v in (r.get("readings") or {}).values()] or [r.get("verdict", "")]
            final = "error" if all(v.startswith("error") for v in vs) else (
                "correct" if all(v.startswith("correct") for v in vs) else "undeterminable")
        out[s] = "correct" if abs(float(read) - float(now)) > 1e-9 else final
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("step", choices=("merge", "score"))
    ap.add_argument("--readings", default=str(READINGS))
    ap.add_argument("--out", default=str(OUT))
    a = ap.parse_args(argv)
    draw = load(DRAW)
    if a.step == "merge":
        rows, outcomes, vset, blind, warnings = merge(draw, a.readings, a.out, ser.overruled_stems())
        print("merged %d first readings and %d census records; verification set %d (random fifth %d)"
              % (len(rows), len(outcomes), len(vset["all"]), len(vset["random_fifth_of_remaining_corrects"])))
        for w in warnings:
            print("  WARNING " + w)
    else:
        r = score(draw, a.readings, a.out, beside_rates(), k_final_verdicts(), load(FRAME)["F_frame"]["n"])
        cl = r["clarified"]
        print("draw four, clarified: %d errors, %d correct, %d undeterminable; mean %.4f, 95%% CrI [%.4f, %.4f]; "
              "P(theta4 > 0.052) = %.3f" % (cl["errors"], cl["correct"], cl["undeterminable"], cl["posterior"]["mean"],
                                           cl["posterior"]["ci95_equal_tailed"][0], cl["posterior"]["ci95_equal_tailed"][1],
                                           r["P_theta4_gt_0_052"]))


if __name__ == "__main__":
    main()
