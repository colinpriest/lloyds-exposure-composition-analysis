r"""Checks of score_error_rate_fourth.py on synthetic readings, written before any reading of draw four.

The file is named checks_*.py, not test_*.py, so that the analysis suite (whose recorded collection count a gate
compares) does not collect it. Run it by name:

    python -m pytest -q -p no:cacheprovider checks_score_error_rate_fourth.py

Every reading here is made up. The last two checks read the archive's earlier files (no filing, no draw-four record).
"""
import json
import math
import sys
from pathlib import Path

import numpy as np
import pytest
from scipy import stats

sys.path.insert(0, str(Path(__file__).resolve().parent))
import score_error_rate as ser  # noqa: E402
import score_error_rate_fourth as s4  # noqa: E402

A = s4.ADOPTED
SEED = 123456789012345678901234567890


def route(source, triangle):
    r = {"source": source, "value": None, "model_value": None, "triangle_type": None, "triangle_units": None,
         "triangle_source_page": None, "note": None}
    if triangle:
        r.update(triangle_type="gross", triangle_units="thousands", triangle_source_page=30)
    return r


def rec(stem, batch, adopted, source="rag_triangle", triangle=True, role="draw4"):
    b = {"stem": stem, "role": role, "batch": batch, A: adopted, "route": route(source, triangle),
         "loader_cohort_scope": ["mature-enforced", "enforced"], "model_notes": "", "report_currency": "GBP",
         "cited_pages": {"prior_year_movement": 10, "opening_reserves": 4, "triangle": 30 if triangle else None}}
    if role == "census4":
        b["census_why"] = "synthetic"
    return b


def synthetic_draw():
    recs = []
    for n in (1, 2, 3, 4):
        recs += [rec("syndicate_%d01_2020" % n, n, 10.0), rec("syndicate_%d02_2020" % n, n, -5.0),
                 rec("syndicate_%d03_2020" % n, n, 2.0, source="rag_provisions", triangle=False),
                 rec("syndicate_%d04_2020" % n, n, 20.0), rec("syndicate_%d05_2020" % n, n, 30.0)]
    recs.append(rec("syndicate_105_2021", 1, 8.0, source="code_triangle", triangle=True))
    recs += [rec("syndicate_901_2019", 5, 4.0, role="census4"), rec("syndicate_902_2019", 5, -3.0, role="census4"),
             rec("syndicate_903_2019", 5, 1.0, role="census4")]
    return {"seed": {"seed": str(SEED)}, "records": recs}


def reading(stem, verdict="correct", recomputation=None, kind=None, adopted=None, figure=None, quote="QUOTE-%s"):
    return {"stem": stem, "verdict": verdict, "adopted_figure_m": adopted, "filing_figure_m": figure,
            "pages": [10], "quote": (quote % stem if "%s" in quote else quote) if verdict != "undeterminable" else "",
            "arithmetic": "synthetic", "error_kind": kind, "triangle_recomputation_m": recomputation,
            "reasoning": "synthetic"}


def first_readings(draw, overrides=None):
    """Every drawn record read correct, its recomputation equal to its adopted figure, unless overridden."""
    overrides = overrides or {}
    out = {n: [] for n in (1, 2, 3, 4)}
    for b in draw["records"]:
        if b["role"] != "draw4":
            continue
        v = overrides.get(b["stem"]) or reading(b["stem"], recomputation=b[A], adopted=b[A], figure=b[A])
        if v != "omit":
            out[b["batch"]].append(v)
    return out


def write_readings(d, draw, overrides=None, census=None):
    d.mkdir(parents=True, exist_ok=True)
    for n, rows in first_readings(draw, overrides).items():
        (d / ("first-batch-%d.json" % n)).write_text(json.dumps(rows), encoding="utf-8")
    census = census or {}
    for r in ("A", "B"):
        rows = [census.get((b["stem"], r)) or reading(b["stem"], recomputation=b[A], adopted=b[A], figure=b[A])
                for b in draw["records"] if b["role"] == "census4"]
        (d / ("census-reader-%s.json" % r)).write_text(json.dumps(rows), encoding="utf-8")


@pytest.fixture
def setup(tmp_path):
    draw = synthetic_draw()
    overrides = {
        # a magnitude error the recomputation shows
        "syndicate_101_2020": reading("syndicate_101_2020", "correct", recomputation=20.0, adopted=10.0, figure=20.0),
        # a first-reader error the clarification turns correct (stated movement differs, triangle agrees)
        "syndicate_102_2020": reading("syndicate_102_2020", "error", recomputation=-5.1, kind="magnitude", adopted=-5.0,
                                      figure=-9.0),
        # an undeterminable
        "syndicate_201_2020": reading("syndicate_201_2020", "undeterminable", adopted=10.0),
        # triangle-sourced without a recomputation
        "syndicate_202_2020": reading("syndicate_202_2020", "correct", recomputation=None, adopted=-5.0, figure=-5.0),
        # a stated figure the first reader calls an error
        "syndicate_303_2020": reading("syndicate_303_2020", "error", kind="sign", adopted=2.0, figure=-2.0),
        # a code_triangle record whose recomputation is far off: an error only if its source is a triangle
        "syndicate_105_2021": reading("syndicate_105_2021", "correct", recomputation=-8.0, adopted=8.0, figure=-8.0),
    }
    write_readings(tmp_path / "readings", draw, overrides)
    return draw, tmp_path / "readings", tmp_path / "out"


def test_merge_writes_its_files_and_the_second_reader_sees_nothing_of_the_first(setup):
    draw, rd, out = setup
    rows, outcomes, vset, blind, warnings = s4.merge(draw, rd, out)
    for name in ("error-rate-verdicts-fourth.json", "error-rate-census-fourth.json",
                 "error-rate-verification-set-fourth.json", "error-rate-second-briefs-fourth.json"):
        assert (out / name).exists()
    assert len(rows) == 21 and len(outcomes) == 3 and warnings == []
    text = (out / "error-rate-second-briefs-fourth.json").read_text(encoding="utf-8")
    assert "QUOTE-" not in text and '"arithmetic"' not in text and '"verdict"' not in text
    assert [b["stem"] for b in blind] == vset["all"]
    for b in blind:
        assert not set(b) & set(s4.READING_FIELDS)
        assert b[A] == next(r for r in draw["records"] if r["stem"] == b["stem"])[A]


def test_the_clarified_verdicts(setup):
    draw, rd, out = setup
    rows = s4.merge(draw, rd, out)[0]
    assert rows["syndicate_101_2020"]["clarified_verdict"] == "error"
    assert rows["syndicate_102_2020"]["clarified_verdict"] == "correct"
    assert rows["syndicate_201_2020"]["clarified_verdict"] == "undeterminable"
    assert rows["syndicate_202_2020"]["clarified_verdict"] == "undeterminable"
    assert rows["syndicate_303_2020"]["clarified_verdict"] == "error"
    assert rows["syndicate_105_2021"]["clarified_verdict"] == "error"
    assert rows["syndicate_105_2021"]["figure_source"] == "triangle"


def test_a_code_triangle_route_is_a_triangle_where_score_error_rate_alone_reads_it_stated():
    b = rec("syndicate_105_2021", 1, 8.0, source="code_triangle")
    first = {"verdict": "correct", "error_kind": None, "triangle_recomputation_m": -8.0}
    assert s4.figure_source(b)[0] == "triangle" and ser.figure_source(b)[0] == "stated"
    assert s4.clarified(first, b)[0] == "error" and ser.clarified(first, b)[0] == "correct"


@pytest.mark.parametrize("source,triangle,verdict,recomputation,kind,adopted", [
    ("rag_triangle", True, "correct", -14.7, None, -13.922),
    ("rag_triangle", True, "correct", -14.6, None, -13.922),
    ("rag_triangle", True, "correct", 0.2, None, -0.3),
    ("rag_triangle", True, "correct", 0.0, None, -0.3),
    ("rag_triangle", True, "error", -5.0, "basis-net", -5.0),
    ("rag_triangle", True, "undeterminable", -5.0, None, -5.0),
    ("rag_triangle", True, "correct", None, None, -5.0),
    ("rag_provisions", False, "error", None, "sign", 2.0),
    ("rag_provisions", False, "correct", 9.0, None, 2.0),
    ("model_reading", False, "correct", None, None, 2.0),
])
def test_the_clarification_is_score_error_rates_on_every_other_route(source, triangle, verdict, recomputation, kind,
                                                                       adopted):
    b = rec("syndicate_1_2020", 1, adopted, source=source, triangle=triangle)
    first = {"verdict": verdict, "error_kind": kind, "triangle_recomputation_m": recomputation}
    assert s4.clarified(first, b) == ser.clarified(first, b)


def test_the_verification_set(setup):
    draw, rd, out = setup
    rows, _o, vset, _b, _w = s4.merge(draw, rd, out)
    assert vset["clarified_errors"] == ["syndicate_101_2020", "syndicate_105_2021", "syndicate_303_2020"]
    assert vset["first_reader_errors"] == ["syndicate_102_2020", "syndicate_303_2020"]
    assert set(vset["verdicts_the_clarification_changed"]) == {"syndicate_101_2020", "syndicate_102_2020",
                                                                "syndicate_105_2021", "syndicate_202_2020"}
    assert set(vset["undeterminable"]) == {"syndicate_201_2020", "syndicate_202_2020"}
    assert vset["triangle_sourced_without_recomputation"] == ["syndicate_201_2020", "syndicate_202_2020"]
    assert vset["source_is_not_the_route_field"] == []
    named = set().union(*(set(v) for k, v in vset.items() if isinstance(v, list) and k not in ("all",
                                                                  "random_fifth_of_remaining_corrects")))
    rest = sorted(s for s in rows if s not in named and rows[s]["clarified_verdict"] == "correct")
    assert len(vset["random_fifth_of_remaining_corrects"]) == math.ceil(0.2 * len(rest)) == 3
    assert set(vset["random_fifth_of_remaining_corrects"]) <= set(rest)
    idx = np.random.default_rng(SEED).choice(len(rest), size=3, replace=False)
    assert vset["random_fifth_of_remaining_corrects"] == sorted(rest[int(i)] for i in idx)
    assert vset["all"] == sorted(named | set(vset["random_fifth_of_remaining_corrects"]))


def test_a_sign_veto_record_is_second_read_because_its_source_is_not_its_route_field(setup, tmp_path):
    draw, rd, _out = setup
    vset = s4.merge(draw, rd, tmp_path / "out2", overruled=frozenset({"syndicate_401_2020"}))[2]
    assert vset["source_is_not_the_route_field"] == ["syndicate_401_2020"]
    assert "syndicate_401_2020" in vset["all"]


@pytest.mark.parametrize("change,problem", [
    ({"syndicate_104_2020": "omit"}, "no reading for"),
    ({"syndicate_104_2020": reading("syndicate_104_2020", "correct", recomputation=20.0, adopted=20.0, quote="")},
     "no quotation"),
    ({"syndicate_104_2020": dict(reading("syndicate_104_2020", recomputation=20.0, adopted=20.0), pages=[])}, "no pages"),
    ({"syndicate_104_2020": dict(reading("syndicate_104_2020", recomputation=20.0, adopted=20.0), verdict="fine")},
     "verdict"),
    ({"syndicate_104_2020": dict(reading("syndicate_104_2020", recomputation=20.0, adopted=20.0), arithmetic="",
                                 reasoning="")}, "no arithmetic"),
    ({"syndicate_104_2020": reading("syndicate_204_2020", recomputation=20.0, adopted=20.0)}, "not a record of this file"),
])
def test_the_merge_refuses_a_bad_or_missing_reading(tmp_path, change, problem):
    draw = synthetic_draw()
    write_readings(tmp_path / "r", draw, change)
    with pytest.raises(SystemExit) as e:
        s4.merge(draw, tmp_path / "r", tmp_path / "o")
    assert problem in str(e.value)
    assert not (tmp_path / "o" / "error-rate-verification-set-fourth.json").exists()


def test_the_merge_refuses_a_duplicate_and_a_missing_file(tmp_path):
    draw = synthetic_draw()
    write_readings(tmp_path / "r", draw)
    p = tmp_path / "r" / "first-batch-2.json"
    rows = json.loads(p.read_text(encoding="utf-8"))
    p.write_text(json.dumps(rows + rows[:1]), encoding="utf-8")
    (tmp_path / "r" / "census-reader-B.json").unlink()
    with pytest.raises(SystemExit) as e:
        s4.merge(draw, tmp_path / "r", tmp_path / "o")
    assert "duplicate" in str(e.value) and "census reader B missing" in str(e.value)


def test_the_merge_refuses_a_rag_triangle_route_without_its_triangle(tmp_path):
    draw = synthetic_draw()
    draw["records"][0]["route"] = route("rag_triangle", False)
    write_readings(tmp_path / "r", draw)
    with pytest.raises(SystemExit) as e:
        s4.merge(draw, tmp_path / "r", tmp_path / "o")
    assert "without its triangle" in str(e.value)


def test_the_merge_and_the_score_are_written_once(setup):
    draw, rd, out = setup
    s4.merge(draw, rd, out)
    with pytest.raises(SystemExit):
        s4.merge(draw, rd, out)


def test_the_census_outcomes(tmp_path):
    draw = synthetic_draw()
    census = {("syndicate_901_2019", "A"): reading("syndicate_901_2019", "correct", recomputation=7.0, adopted=4.0, figure=7.0),
              ("syndicate_901_2019", "B"): reading("syndicate_901_2019", "correct", recomputation=7.1, adopted=4.0, figure=7.1),
              ("syndicate_902_2019", "A"): reading("syndicate_902_2019", "correct", recomputation=5.0, adopted=-3.0),
              ("syndicate_902_2019", "B"): reading("syndicate_902_2019", "correct", recomputation=-3.0, adopted=-3.0)}
    write_readings(tmp_path / "r", draw, census=census)
    outcomes = {o["stem"]: o for o in s4.merge(draw, tmp_path / "r", tmp_path / "o")[1]}
    assert outcomes["syndicate_901_2019"]["outcome"] == "error"
    assert "figures agree" in outcomes["syndicate_901_2019"]["why"]
    assert outcomes["syndicate_902_2019"]["outcome"] == "undeterminable"
    assert outcomes["syndicate_903_2019"]["outcome"] == "correct"


def second_readings(rd, vset, verdicts):
    rows = [dict(reading(s, verdicts.get(s, "correct"), recomputation=1.0, adopted=1.0, figure=1.0)) for s in vset["all"]]
    (rd / "second-readings.json").write_text(json.dumps(rows), encoding="utf-8")


BESIDE = {"pooled": {"posterior": {"alpha": 8.5, "beta": 154.5}}}


def test_the_score(setup):
    draw, rd, out = setup
    vset = s4.merge(draw, rd, out)[2]
    # the second reader overturns 101 (error -> correct) and finds 201 correct; 202 stays undeterminable
    second_readings(rd, vset, {"syndicate_105_2021": "error", "syndicate_303_2020": "error",
                               "syndicate_202_2020": "undeterminable"})
    r = s4.score(draw, rd, out, BESIDE, {"syndicate_7_2018": "error", "syndicate_8_2018": "correct"}, frame_n=100)
    cl = r["clarified"]
    assert (cl["errors"], cl["correct"], cl["undeterminable"]) == (2, 18, 1)
    assert cl["posterior"]["alpha"] == 2.5 and cl["posterior"]["beta"] == 18.5
    assert {o["stem"] for o in cl["second_reading_overturned"]} == {"syndicate_101_2020", "syndicate_201_2020"}
    fr = r["first_readers_instruction"]
    assert (fr["errors"], fr["correct"], fr["undeterminable"]) == (2, 18, 1)
    assert r["undeterminables_as_errors"]["errors"] == 3 and r["undeterminables_as_errors"]["adjudicable_n"] == 21
    assert r["P_theta4_gt_0_052"] == pytest.approx(stats.beta(2.5, 18.5).sf(0.052))
    assert r["beside_never_pooled"] == BESIDE
    assert r["known_verdicts_K_and_C"]["syndicate_7_2018"] == "error"
    assert r["known_verdicts_K_and_C"]["syndicate_903_2019"] == "correct"
    assert (out / "error-rate-result-fourth.json").exists()
    with pytest.raises(SystemExit):
        s4.score(draw, rd, out, BESIDE, {}, frame_n=100)


def test_the_score_refuses_until_every_record_of_the_verification_set_is_read_again(setup):
    draw, rd, out = setup
    vset = s4.merge(draw, rd, out)[2]
    rows = [reading(s, "correct", recomputation=1.0, adopted=1.0) for s in vset["all"][1:]]
    (rd / "second-readings.json").write_text(json.dumps(rows), encoding="utf-8")
    with pytest.raises(SystemExit) as e:
        s4.score(draw, rd, out, BESIDE, {}, frame_n=100)
    assert vset["all"][0] in str(e.value)


def test_the_working_sample_rate():
    known = {"a": "error", "b": "correct", "c": "correct", "d": "undeterminable"}
    r = s4.working_sample_rate(4, 96, 100, 400, known, SEED, draws=400000)
    assert r["adjudicable_unread_in_F"] == 288 and r["known"] == {"errors": 1, "adjudicable": 3, "undeterminable": 1,
                                                                    "n": 4}
    expect = (288 * 4.5 / 97.0 + 4 + 1) / (288 + 96 + 3)
    assert r["mean"] == pytest.approx(expect, rel=0.01)
    lo, hi = r["ci95_equal_tailed"]
    assert lo < r["mean"] < hi
    assert s4.working_sample_rate(4, 96, 100, 400, known, SEED) == s4.working_sample_rate(4, 96, 100, 400, known, SEED)
    more = s4.working_sample_rate(4, 96, 100, 400, dict(known, e="error"), SEED)
    assert more["mean"] > s4.working_sample_rate(4, 96, 100, 400, dict(known, e="correct"), SEED)["mean"]


def test_the_rates_beside_draw_four_are_the_archives_own():
    b = s4.beside_rates()
    assert b["pooled"]["posterior"]["alpha"] == 8.5 and b["pooled"]["posterior"]["beta"] == 154.5
    assert b["pooled_161_still_in_W"]["n"] == 161
    assert b["pooled_161_still_in_W"]["posterior"]["alpha"] == 6.5


def test_every_checked_record_has_a_final_verdict():
    k = s4.k_final_verdicts()
    frame = s4.load(s4.FRAME)
    assert set(k) == {r["stem"] for r in frame["K_checked"]["records"]} and len(k) == 267
    assert set(k.values()) <= set(s4.VERDICTS)
    # repaired to the readings' figure: correct now
    for s in ("syndicate_382_2019", "syndicate_4444_2022", "syndicate_1225_2022", "syndicate_3010_2022"):
        assert k[s] == "correct"
