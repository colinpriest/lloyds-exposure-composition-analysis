r"""The clarified verdict rule in score_error_rate.py, on constructed readings, before any real scoring.

    python -m pytest -q test_score_clarified.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import score_error_rate as ser  # noqa: E402

CODE_OVERRIDE_4444 = ("[CODE OVERRIDE: Model said PYD=1947.812, but code computed 435.491 from triangle "
                      "(OVERRIDE from gemini-2.5-flash triangle). Using code value.]")


def brief(adopted, route="rag_triangle", triangle=True, cohort=("disclosed-prior-year", "disclosed"), notes=""):
    """As make_adjudication_briefs.py writes one: every route key present, None where the record has none."""
    r = {"source": route, "value": adopted, "model_value": None, "triangle_type": None,
         "triangle_units": None, "triangle_source_page": None, "note": None}
    if route == "rag_triangle" and triangle:
        r.update(triangle_type="gross", triangle_units="thousands", triangle_source_page=40)
    return {"adopted_prior_year_development_m_report_currency": adopted, "route": r,
            "loader_cohort_scope": list(cohort), "model_notes": notes}


def first(verdict="correct", rec=None, kind=None):
    v = {"verdict": verdict, "error_kind": kind}
    if rec is not None:
        v["triangle_recomputation_m"] = rec
    return v


def test_within_tolerance_is_correct():
    assert ser.clarified(first("error", rec=-13.9, kind="magnitude"), brief(-13.922))[0] == "correct"


def test_outside_tolerance_is_an_error():
    # tolerance max(0.5, 0.05 * 13.922) = 0.696
    assert ser.clarified(first("correct", rec=-14.7), brief(-13.922))[0] == "error"
    assert ser.clarified(first("correct", rec=-14.6), brief(-13.922))[0] == "correct"


def test_opposite_sign_is_an_error_whatever_the_size():
    assert ser.clarified(first("correct", rec=0.2), brief(-0.3))[0] == "error"


def test_a_zero_is_not_a_sign_error():
    assert ser.clarified(first("correct", rec=0.0), brief(-0.3))[0] == "correct"


def test_no_recomputation_is_undeterminable():
    assert ser.clarified(first("correct"), brief(-5.0))[0] == "undeterminable"


def test_a_first_undeterminable_stays():
    assert ser.clarified(first("undeterminable", rec=-5.0), brief(-5.0))[0] == "undeterminable"


def test_a_scope_or_basis_error_stands_for_the_second_reader():
    assert ser.clarified(first("error", rec=-5.0, kind="basis-net"), brief(-5.0))[0] == "error"


def test_an_overruled_triangle_is_checked_against_the_stated_movement():
    """1414/2024's route field says triangle, but the pipeline overruled that triangle (+86.7m,
    the opposite sign to the provisions note) and adopted the note's -15.6m. Scoring it against
    the triangle would call a correct figure a sign error."""
    b = dict(brief(-15.6), stem="syndicate_1414_2024")
    got = ser.clarified(first("correct", rec=86.745), b, overruled=frozenset({"syndicate_1414_2024"}))
    assert got[0] == "correct", got
    # without the register, the same reading would be a sign error: the case the rule exists for
    assert ser.clarified(first("correct", rec=86.745), b)[0] == "error"


def test_a_record_not_through_the_triangle_keeps_the_first_verdict():
    assert ser.clarified(first("error", kind="magnitude"), brief(-5.0, route=None))[0] == "error"
    assert ser.clarified(first("correct"), brief(-5.0, route=None))[0] == "correct"


def test_a_triangle_route_that_carries_no_triangle_is_checked_against_the_stated_movement():
    """Refinement 3. 1994/2024's route reads rag_triangle, but the RAG step found no usable triangle
    and used the provisions note ('Using provisions PYD as fallback: +22.300m'), so the route carries
    no triangle. A recomputation from the printed table (+14.4m) is not the figure's source."""
    b = dict(brief(22.3, triangle=False), stem="syndicate_1994_2024")
    got = ser.clarified(first("correct", rec=14.395), b)
    assert got[0] == "correct", got
    # the same reading against a route that carries its triangle is an error: the case the rule exists for
    assert ser.clarified(first("correct", rec=14.395), dict(brief(22.3), stem="syndicate_1994_2024"))[0] == "error"


def test_a_code_override_figure_with_an_empty_route_is_checked_against_the_triangle():
    """Refinement 3. 4444/2022's route field is empty, but its notes carry the code override whose
    computed value is the adopted figure: the figure is a triangle's, so rule 1 applies."""
    b = dict(brief(435.491, route=None, cohort=("mature-enforced", "triangle"), notes=CODE_OVERRIDE_4444),
             stem="syndicate_4444_2022")
    got = ser.clarified(first("correct", rec=34.9), b)
    assert got[0] == "error", got
    # the loader's cohort label alone is not evidence of a triangle: the loader also reads, as a
    # triangle, the RAG annotation the driver writes over a provisions fallback
    b2 = dict(brief(435.491, route=None, cohort=("mature-enforced", "triangle")), stem="syndicate_4444_2022")
    assert ser.clarified(first("correct", rec=34.9), b2)[0] == "correct"
    # a code override whose computed value is not the adopted figure is not the figure's source
    b3 = dict(brief(12.0, route=None, notes=CODE_OVERRIDE_4444), stem="syndicate_4444_2022")
    assert ser.clarified(first("correct", rec=34.9), b3)[0] == "correct"


def test_figure_source_reads_the_pipelines_own_record():
    over = frozenset({"syndicate_1414_2024"})
    assert ser.figure_source(dict(brief(-15.6), stem="syndicate_1414_2024"), over)[0] == "stated"
    assert ser.figure_source(dict(brief(22.3, triangle=False), stem="s"), over)[0] == "stated"
    assert ser.figure_source(dict(brief(-13.9), stem="s"), over)[0] == "triangle"
    assert ser.figure_source(dict(brief(435.491, route=None, notes=CODE_OVERRIDE_4444), stem="s"), over)[0] == "triangle"
    assert ser.figure_source(dict(brief(435.491, route=None, cohort=("mature-enforced", "triangle")), stem="s"),
                             over)[0] == "stated"
    assert ser.figure_source(dict(brief(1.8, route=None), stem="s"), over)[0] == "stated"


def test_every_record_whose_source_is_not_its_route_field_is_second_read():
    """Refinements 1 and 3 decide a figure's source from more than the route field; each record they
    reclassify is second-read whatever its first verdict."""
    stems = ["syndicate_1_2024", "syndicate_2_2024", "syndicate_3_2024", "syndicate_4_2024"]
    briefs = {"syndicate_1_2024": dict(brief(22.3, triangle=False), stem="syndicate_1_2024"),
              "syndicate_2_2024": dict(brief(-13.9), stem="syndicate_2_2024"),
              "syndicate_3_2024": dict(brief(435.491, route=None, notes=CODE_OVERRIDE_4444), stem="syndicate_3_2024"),
              "syndicate_4_2024": dict(brief(-15.6), stem="syndicate_4_2024")}
    rows = {s: dict(first("correct", rec=briefs[s]["adopted_prior_year_development_m_report_currency"]), stem=s)
            for s in stems}
    rows["syndicate_1_2024"]["triangle_recomputation_m"] = 14.4
    over = frozenset({"syndicate_4_2024"})
    for s in stems:
        rows[s]["clarified_verdict"], rows[s]["clarified_why"] = ser.clarified(rows[s], briefs[s], over)
    sets = ser.must_verify(stems, rows, briefs, over)
    assert sets["source_is_not_the_route_field"] == {"syndicate_1_2024", "syndicate_3_2024", "syndicate_4_2024"}, sets
    assert "syndicate_2_2024" not in sets["all"]


def _evidence(stem, logged):
    return {"stem": stem, "non_triangle_methods_in_log": logged}


def test_the_merge_refuses_a_route_its_own_replay_log_contradicts():
    briefs = {"syndicate_1_2024": dict(brief(-13.9), stem="syndicate_1_2024"),
              "syndicate_2_2024": dict(brief(22.3, triangle=False), stem="syndicate_2_2024"),
              "syndicate_3_2024": dict(brief(-15.6), stem="syndicate_3_2024")}
    stems = sorted(briefs)
    over = frozenset({"syndicate_3_2024"})
    good = [_evidence("syndicate_1_2024", []), _evidence("syndicate_2_2024", ["provisions_fallback"]),
            _evidence("syndicate_3_2024", ["provisions_over_triangle"])]
    assert ser.route_evidence_problems(stems, briefs, over, good) == []
    bad = [_evidence("syndicate_1_2024", ["provisions_fallback"]), _evidence("syndicate_2_2024", []),
           _evidence("syndicate_3_2024", [])]
    got = ser.route_evidence_problems(stems, briefs, over, bad)
    assert len(got) == 3, got
    # a sampled route with no replay-log evidence at all is refused too
    assert len(ser.route_evidence_problems(stems, briefs, over, good[:2])) == 1


def test_the_verdict_without_refinement_3_is_kept_for_the_report():
    b = dict(brief(22.3, triangle=False), stem="syndicate_1994_2024")
    assert ser.clarified(first("correct", rec=14.395), b, refinement_3=False)[0] == "error"
    assert ser.clarified(first("correct", rec=14.395), b)[0] == "correct"


def test_a_first_readers_scope_error_stands_without_a_recomputation():
    """4444/2022's reader recorded a scope error with the recomputation in the arithmetic only;
    the error stands for the second reader rather than turning undeterminable."""
    b = dict(brief(435.491, route=None, notes=CODE_OVERRIDE_4444), stem="syndicate_4444_2022")
    assert ser.clarified(first("error", kind="scope-recent-years"), b)[0] == "error"
