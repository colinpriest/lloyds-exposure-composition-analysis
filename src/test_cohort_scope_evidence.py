r"""An override annotation is evidence of a triangle only when the route beside it names one (R208).

The extraction driver wrote "[RAG OVERRIDE: ... RAG triangle computed X ...]" whenever its RAG step's
figure moved the model's, whatever the method, so a provisions-note figure carried a triangle's words.
pyd_cohort_scope read that annotation as a triangle route and called the figure cohort-enforced, and
pyd_basis took the basis from whatever triangle the block held. Eight observations in the working
sample were cohort-enforced on no triangle that way.

These build model blocks by hand: the route as the driver wrote it, the corrected route, a triangle's
figure, a code override, and a block extracted before the route field existed.
"""
import os
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(HERE, "src"))
import run_analysis as ra  # noqa: E402

ANNOTATION = "[RAG OVERRIDE: Model said PYD=23.342, RAG triangle computed 31.6. Using RAG value.]"
TRIANGLE_ROUTE = {"source": "rag_triangle", "value": 31.6, "model_value": 23.342, "triangle_type": "gross",
                  "triangle_units": "thousands", "triangle_source_page": 40, "note": "overrode the model value"}
MISLABELLED = {"source": "rag_triangle", "value": 31.6, "model_value": 23.342, "note": "overrode the model value"}
CORRECTED = {"source": "rag_provisions", "value": 31.6, "model_value": 23.342, "note": "overrode the model value"}


def block(route=None, notes=ANNOTATION, claims_triangle="gross", figure=31.6):
    cm = {"prior_year_development_gbp_m": figure, "data_quality_notes": notes,
          "_claims_triangle": {"type": claims_triangle} if claims_triangle else None}
    if route is not None:
        cm["_pyd_route"] = dict(route)
    return cm


def test_a_triangles_annotation_enforces_the_cohort():
    assert ra.pyd_cohort_scope(block(TRIANGLE_ROUTE)) == (ra.COHORT_ENFORCED, "triangle")


def test_a_mislabelled_provisions_route_does_not_enforce_the_cohort():
    """1206/2014 as the driver wrote it: route 'rag_triangle' with no triangle, the provisions
    fallback's +31.6m, and an annotation saying a triangle computed it."""
    assert ra.pyd_cohort_scope(block(MISLABELLED)) == (ra.COHORT_DISCLOSED, "disclosed")


def test_a_corrected_route_does_not_enforce_the_cohort_whatever_the_annotation_says():
    assert ra.pyd_cohort_scope(block(CORRECTED)) == (ra.COHORT_DISCLOSED, "disclosed")


def test_a_mislabelled_route_takes_no_basis_from_an_unrelated_triangle():
    """2008/2019: its basis came from the models' own gross claims triangle, which did not
    produce the provisions note's +249.0m."""
    basis = ra.pyd_basis(block(MISLABELLED), "9999_2019", {})
    assert not basis[1].startswith("triangle-"), basis


def test_a_code_override_is_a_triangles():
    notes = ("[CODE OVERRIDE: Model said PYD=1947.812, but code computed 435.491 from triangle "
             "(OVERRIDE from gemini-2.5-flash triangle). Using code value.]")
    cm = block(None, notes=notes, figure=435.491)
    assert ra.pyd_cohort_scope(cm) == (ra.COHORT_ENFORCED, "triangle")
    assert ra.pyd_basis(cm, "9999_2022", {}) == ("gross", "triangle-override:gross", "")


def test_a_block_from_before_the_route_field_keeps_its_annotation():
    assert ra.pyd_cohort_scope(block(None)) == (ra.COHORT_ENFORCED, "triangle")


def test_the_corrected_annotation_is_not_read_as_a_triangles():
    """What the corrected driver writes over the provisions fallback."""
    notes = "[RAG OVERRIDE: Model said PYD=23.342, RAG provisions computed 31.6. Using RAG value.]"
    assert ra.OVERRIDE_TAG.findall(notes) == []
    assert ra.pyd_cohort_scope(block(CORRECTED, notes=notes)) == (ra.COHORT_DISCLOSED, "disclosed")
