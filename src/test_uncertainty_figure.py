#!/usr/bin/env python3
"""The uncertainty figure (make_uncertainty_figure.py): Vignette 1's GBP 500m VaR99.5, each source of uncertainty shown
on its own and none added to another.

  * the shape: four bands in a fixed order, each row's centre and interval read from the file that holds it (compared
    here with an independent read of the same JSON), the overlay labelled exploratory, the raw pool marked off scale;
  * no combined total: no band, row, key or text of the record or the figure carries a sum, a total or a combined
    interval, and the record says the sources are not added;
  * the checks: the headline centre read from each of nine files must be the same figure, and the overlay's two records
    must agree, or nothing is drawn;
  * the figure: its text prints at 8 points or more at the width the manuscript will give it, its PDF carries no
    creation date (two runs give the same bytes), its values are the record's;
  * the values record is what was plotted, in reserve fractions and GBP m.

The sources are the committed result files, whose layout this reads; their numbers are not pinned here.

Run:  python -m pytest src/test_uncertainty_figure.py -q
"""
import copy
import hashlib
import io
import json
import os
import sys
import time

import numpy as np
import pytest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(HERE, "src"))

import matplotlib  # noqa: E402
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

import make_uncertainty_figure as UF  # noqa: E402
import paper_figure_style as PFS  # noqa: E402

RESULTS = os.path.join(HERE, "results")
VOLATILE = ("runtime_seconds", "analysis_timestamp", "retrieved_utc", "execution_timestamp_utc", "git_commit_or_hash",
            "analysis_commit", "tree_dirty_src_model_results")
ORDER = ["parameter_and_donor_weights", "measurement_definition", "influential_donors", "model_alternatives"]
ROWS = {"parameter_and_donor_weights": ["headline"],
        "measurement_definition": ["construction_672", "depth_t_minus_3", "earned_basis", "older_years_bucket",
                                   "least_certain"],
        "influential_donors": ["most_adverse_donor_out"],
        "model_alternatives": ["concentration_overlay", "square_root_scaling", "raw_pool"]}


def read(name):
    with io.open(os.path.join(RESULTS, name), encoding="utf-8") as fh:
        return json.load(fh)


@pytest.fixture(scope="module")
def src():
    return UF.load_sources()


@pytest.fixture(scope="module")
def values(src):
    return UF.compute(src)


def row_of(values, rid):
    return {r["id"]: r for b in values["bands"] for r in b["rows"]}[rid]


# ---------------------------------------------------------------------------------------------------- the shape
def test_four_bands_in_a_fixed_order_with_the_named_rows(values):
    assert [b["id"] for b in values["bands"]] == ORDER
    assert {b["id"]: [r["id"] for r in b["rows"]] for b in values["bands"]} == ROWS
    assert [b["title"] for b in values["bands"]] == [UF.BAND_TITLES[i] for i in ORDER]
    assert values["vignette"] == "Vignette 1" and values["reserve_size_gbp_m"] == 500.0


def test_each_row_is_read_from_the_file_that_holds_it(values):
    vu, g0, bt = read("vignette_uncertainty_results.json"), read("check_gamma0_vignette_results.json"), read(
        "check_operator_backtest_results.json")
    r = row_of(values, "headline")
    assert r["point"] == vu["centres_full_pool_posterior_mean"]["V1_adj"]["v995"]
    assert r["interval"] == [vu["vignette1"]["adjusted"]["var995"]["lo"], vu["vignette1"]["adjusted"]["var995"]["hi"]]
    cs = read("check_cohort_scope_results.json")["vignettes"]
    r = row_of(values, "construction_672")
    assert r["point"] == cs["precedence_672"]["centre"]["V1_v995"]
    assert r["interval"] == [cs["posterior_intervals"]["precedence_672"]["V1_v995"]["lo"],
                             cs["posterior_intervals"]["precedence_672"]["V1_v995"]["hi"]]
    d = read("check_cohort_depth_sensitivity_results.json")["cohort_depth_t_minus_3"]["vignettes"]
    r = row_of(values, "depth_t_minus_3")
    assert r["point"] == d["centre"]["V1_v995"] and r["interval"] == [d["intervals"]["V1_v995"]["lo"],
                                                                      d["intervals"]["V1_v995"]["hi"]]
    for rid, fname in (("earned_basis", "check_earned_basis_sensitivity_results.json"),
                       ("older_years_bucket", "check_bucket_share_sensitivity_results.json"),
                       ("least_certain", "check_low_confidence_sensitivity_results.json")):
        v = read(fname)["vignettes"]
        r = row_of(values, rid)
        assert r["point"] == v["centre"]["V1_v995"], rid
        assert r["interval"] == [v["intervals"]["V1_v995"]["lo"], v["intervals"]["V1_v995"]["hi"]], rid
        assert r["source"] == "results/" + fname
    don = read("check_donor_influence_results.json")["fits"]["without"]["V1_VaR995"]
    r = row_of(values, "most_adverse_donor_out")
    assert r["point"] == don["centre"] and r["interval"] == [don["lo"], don["hi"]]
    ov = vu["overlay_sensitivity"]
    r = row_of(values, "concentration_overlay")
    assert r["point"] == ov["centres_full_pool_posterior_mean"]["V1_adj"]["v995"] == g0["overlay"]["centre"]["V1_v995"]
    assert r["interval"] == [ov["vignette1"]["adjusted"]["var995"]["lo"], ov["vignette1"]["adjusted"]["var995"]["hi"]]
    r = row_of(values, "square_root_scaling")
    assert r["point"] == bt["vignette_figures"]["sqrt_R"]["V1"]["v995"] and r["interval"] is None
    r = row_of(values, "raw_pool")
    assert r["point"] == bt["vignette_figures"]["raw_pool"]["v995"] and r["interval"] is None


def test_the_rows_with_no_interval_say_so_and_the_overlay_is_exploratory(values):
    assert row_of(values, "square_root_scaling")["interval_kind"] is None
    assert "exploratory" in row_of(values, "concentration_overlay")["label"].lower()
    assert row_of(values, "headline")["interval_kind"] == UF.KIND_CREDIBLE
    assert row_of(values, "depth_t_minus_3")["interval_kind"] == UF.KIND_CONDITIONAL
    assert "not a posterior" not in UF.KIND_CREDIBLE and "conditional resampling" in UF.KIND_CONDITIONAL


def test_gbp_values_are_the_fractions_times_the_reserves(values):
    for b in values["bands"]:
        for r in b["rows"]:
            assert r["point_gbp_m"] == r["point"] * 500.0
            if r["interval"]:
                assert r["interval_gbp_m"] == [x * 500.0 for x in r["interval"]]
            else:
                assert r["interval_gbp_m"] is None
    assert values["headline_centre_gbp_m"] == values["headline_centre"] * 500.0


def test_the_raw_pool_is_off_scale_and_nothing_else_is(values):
    off = [r["id"] for b in values["bands"] for r in b["rows"] if r["off_scale"]]
    assert off == ["raw_pool"]
    xmax = values["x_axis_reserve_fraction"][1]
    # every other point and interval end is inside the axis
    for b in values["bands"]:
        for r in b["rows"]:
            if r["id"] != "raw_pool":
                assert r["point"] <= xmax and all(x <= xmax for x in (r["interval"] or []))


def test_a_raw_pool_inside_the_axis_is_drawn_not_marked_off_scale(src):
    s = copy.deepcopy(src)
    s["backtest"]["vignette_figures"]["raw_pool"]["v995"] = 0.2
    v = UF.compute(s)
    assert not row_of(v, "raw_pool")["off_scale"]


# ------------------------------------------------------------------------------------------ no combined total
def _walk_keys(x):
    if isinstance(x, dict):
        for k, v in x.items():
            yield k
            yield from _walk_keys(v)
    elif isinstance(x, list):
        for v in x:
            yield from _walk_keys(v)


def test_the_record_has_no_total_sum_or_combined_interval(values):
    bad = [k for k in _walk_keys(values) if any(w in str(k).lower() for w in ("total", "sum", "combined", "pooled"))]
    # the one key that mentions a sum is the sentence that says there is none
    assert bad == [] or all(k == "reading" for k in bad), bad
    assert "not added together" in values["reading"] and "no combined interval" in values["reading"]
    assert len(values["bands"]) == 4 and all("interval" not in b for b in values["bands"])
    # each band's rows are its own: no row spans another band's, and no row is built from two sources
    assert len({r["id"] for b in values["bands"] for r in b["rows"]}) == sum(len(r) for r in ROWS.values())
    assert all(isinstance(r["source"], str) and r["source"].startswith("results/") for b in values["bands"]
               for r in b["rows"])


def test_the_figure_shows_no_total(values):
    with PFS.style():
        fig = UF.build_figure(values)
    fig.canvas.draw()
    texts = [t.get_text().lower() for t in fig.findobj(matplotlib.text.Text) if t.get_text()]
    plt.close(fig)
    assert not [t for t in texts if "total" in t or "combined" in t or "overall" in t], texts
    assert any("conditional resampling interval" in t for t in texts)


# ------------------------------------------------------------------------------------------- the consistency checks
def test_the_headline_centre_is_read_from_nine_files_and_they_agree(src):
    cen = UF.headline_centres(src)
    assert len(cen) == 9
    out = UF.check_consistency(src)
    assert out["headline_centre"] == cen["vignette_uncertainty"] and len(out["centres_read"]) == 9


@pytest.mark.parametrize("path", [
    ("gamma0", "size_only", "centre", "V1_v995"),
    ("backtest", "vignette_figures", "operator_size_only", "V1", "v995"),
    ("cohort_scope", "vignettes", "headline", "centre", "V1_v995"),
    ("depth", "primary", "vignette_centre", "V1_v995"),
    ("earned", "vignettes", "primary_centre", "V1_v995"),
    ("bucket", "vignettes", "primary_centre", "V1_v995"),
    ("least_certain", "vignettes", "primary_centre", "V1_v995"),
    ("donors", "fits", "with", "V1_VaR995", "centre"),
])
def test_a_file_from_another_pass_stops_the_run(src, path):
    s = copy.deepcopy(src)
    node = s
    for k in path[:-1]:
        node = node[k]
    node[path[-1]] = node[path[-1]] * 1.001
    with pytest.raises(SystemExit, match="headline centre differs"):
        UF.compute(s)


def test_an_overlay_centre_that_differs_between_records_stops_the_run(src):
    s = copy.deepcopy(src)
    s["gamma0"]["overlay"]["centre"]["V1_v995"] *= 1.001
    with pytest.raises(SystemExit, match="overlay's centre differs"):
        UF.compute(s)


def test_an_absent_source_names_the_file(tmp_path):
    with pytest.raises(SystemExit, match="vignette_uncertainty_results.json is absent"):
        UF.load_sources(tmp_path)


def test_every_source_file_is_declared_in_the_record(values):
    assert set(values["inputs"]) == set(UF.SOURCES)
    for k, v in values["inputs"].items():
        assert v["file"] == "results/" + UF.SOURCES[k]
        # the canonical content: the file with the volatile keys removed and keys sorted (reproduce.py's own definition,
        # retyped here from run_analysis's description so the test does not rest on the helper alone)
        with open(os.path.join(RESULTS, UF.SOURCES[k]), "rb") as fh:
            obj = json.loads(fh.read().decode("utf-8"))

        def strip(x):
            if isinstance(x, dict):
                return {a: strip(b) for a, b in x.items() if a not in VOLATILE}
            return [strip(i) for i in x] if isinstance(x, list) else x

        canon = json.dumps(strip(obj), sort_keys=True, separators=(",", ":")).encode("utf-8")
        assert v["sha256"] == hashlib.sha256(canon).hexdigest()


def test_the_stamp_is_the_headline_operators(values):
    assert (values["operator"], values["operator_role"]) == ("size_only", "headline")


# ------------------------------------------------------------------------------------------------- the figure
def _save(values, tmp_path, stem):
    with PFS.style():
        fig = UF.build_figure(values)
        UF.save_figure(fig, tmp_path / (stem + ".png"), tmp_path / (stem + ".pdf"))
    plt.close(fig)
    return tmp_path / (stem + ".png"), tmp_path / (stem + ".pdf")


def test_the_figure_has_four_bands_and_draws_each_row(values):
    with PFS.style():
        fig = UF.build_figure(values)
    fig.canvas.draw()
    main = [a for a in fig.axes if a.get_title(loc="left")]
    # each band's heading carries the letter the caption and text give it: (a) to (d), then the title
    assert [a.get_title(loc="left") for a in main] == ["(%s) %s" % (c, UF.BAND_TITLES[i])
                                                       for c, i in zip("abcd", ORDER)]
    for ax, band in zip(main, values["bands"]):
        assert sorted(t.get_text() for t in ax.get_yticklabels()) == sorted(
            UF.row_label_text(r["label"]) for r in band["rows"])
        # one vertical reference line at the headline centre
        lines = [ln for ln in ax.lines if len(ln.get_xdata()) == 2 and ln.get_xdata()[0] == ln.get_xdata()[1]]
        assert [ln.get_xdata()[0] for ln in lines] == [values["headline_centre"]]
    plt.close(fig)


def test_a_dot_is_drawn_at_each_rows_centre_except_off_scale_ones(values):
    with PFS.style():
        fig = UF.build_figure(values)
    main = [a for a in fig.axes if a.get_title(loc="left")]
    for ax, band in zip(main, values["bands"]):
        xs = sorted(round(float(ln.get_xdata()[0]), 12) for ln in ax.lines
                    if len(ln.get_xdata()) == 1 and ln.get_marker() in ("o", "D"))
        want = sorted(round(r["point"], 12) for r in band["rows"] if not r["off_scale"])
        assert xs == want
    plt.close(fig)


def _kind(r):
    if r["interval"] is None:
        return "point"
    return "credible" if r["interval_kind"] == UF.KIND_CREDIBLE else "conditional"


def test_each_kind_of_mark_is_drawn_differently(values):
    """The edit review of 27 October 2026, item 26: a credible interval is a solid bar with a filled circle, a
    conditional resampling interval a dashed bar with an open circle, a centre with no interval a diamond; the three
    differ in line style and in marker, so they read apart in grey print."""
    fig, main = _drawn_figure(values)
    seen = set()
    for ax, band in zip(main, values["bands"]):
        bars = [c for c in ax.collections if len(c.get_segments())]
        for r in band["rows"]:
            if r["off_scale"]:
                continue
            kind = _kind(r)
            seen.add(kind)
            (dot,) = [ln for ln in ax.lines if len(ln.get_xdata()) == 1 and ln.get_xdata()[0] == r["point"]]
            if kind == "point":
                assert dot.get_marker() == "D"
                assert not [c for c in bars if c.get_segments()[0][0][0] <= r["point"] <= c.get_segments()[0][1][0]
                            and abs(c.get_segments()[0][0][1] - dot.get_ydata()[0]) < 1e-9]
                continue
            (bar,) = [c for c in bars if abs(c.get_segments()[0][0][1] - dot.get_ydata()[0]) < 1e-9]
            offset, dashes = bar.get_linestyle()[0]
            assert dot.get_marker() == "o"
            if kind == "credible":
                assert dashes is None and matplotlib.colors.same_color(dot.get_markerfacecolor(), dot.get_color())
            else:
                assert dashes is not None and len(dashes) >= 2 and min(dashes) > 0
                assert matplotlib.colors.same_color(dot.get_markerfacecolor(), "white")
    assert seen == {"credible", "conditional", "point"}
    plt.close(fig)


def test_the_key_shows_the_three_marks_with_handles_long_enough_for_the_dashes(values):
    """The key's samples were too short to show the dash under the marker (the 300-DPI crop of the review). Each label
    calls the marker a centre, and the dashed sample is long enough for several dash periods."""
    fig, _main = _drawn_figure(values)
    (leg,) = fig.legends
    texts = [t.get_text() for t in leg.get_texts()]
    assert texts == [UF.LEGEND_LABELS[k] for k in ("credible", "conditional", "point", "headline")], texts
    assert all(t.startswith("centre") for t in texts[:3]), texts
    assert leg.handlelength >= 4.0
    fontsize_pt = leg.prop.get_size_in_points()
    period_pt = sum(UF.DASH_CONDITIONAL[1]) * UF.LW_CONDITIONAL
    assert leg.handlelength * fontsize_pt >= 3 * period_pt, "fewer than three dash periods in the key's sample"
    plt.close(fig)


def test_the_record_defines_every_rows_centre(values):
    assert values["centre_definition"] == UF.CENTRE_DEFINITION and "posterior means" in UF.CENTRE_DEFINITION
    assert set(values["marks"]) == {"credible", "conditional_resampling", "no_interval"}
    assert "size-only" in row_of(values, "headline")["label"] and "primary" in row_of(values, "headline")["label"]


def _drawn_figure(values):
    with PFS.style():
        fig = UF.build_figure(values)
    fig.canvas.draw()
    return fig, [a for a in fig.axes if a.get_title(loc="left")]


def test_no_figure_text_carries_the_ascii_inequality_and_the_depth_row_has_the_symbol(values):
    """The depth row printed 'u <= t-3'; the figure sets it as u <= t-3 in mathtext (the record keeps its label)."""
    fig, main = _drawn_figure(values)
    texts = [t.get_text() for ax in main for t in ax.get_yticklabels()] + [ax.get_title(loc="left") for ax in main]
    assert not [t for t in texts if "<=" in t], texts
    assert r"Cohort depth $u\leq t-3$" in texts
    assert row_of(values, "depth_t_minus_3")["label"] == "Cohort depth u <= t-3"
    plt.close(fig)


def test_the_off_scale_note_is_clear_of_the_headline_line_and_of_the_axes(values):
    """The raw pool's note printed across the dotted headline line: no text may straddle or touch it."""
    fig, main = _drawn_figure(values)
    renderer = fig.canvas.get_renderer()
    checked = 0
    for ax in main:
        line_x = ax.transData.transform((values["headline_centre"], 0))[0]
        box_ax = ax.get_window_extent(renderer)
        for t in ax.texts:
            box = t.get_window_extent(renderer)
            checked += 1
            assert not (box.x0 - 3 <= line_x <= box.x1 + 3), (t.get_text(), box.x0, box.x1, line_x)
            assert box_ax.x0 <= box.x0 and box.x1 <= box_ax.x1 and box_ax.y0 <= box.y0 and box.y1 <= box_ax.y1
    assert checked == 1, "the raw pool is the one off-scale row"
    plt.close(fig)


def test_the_figures_text_prints_at_eight_points_or_more(values, tmp_path):
    import fitz
    png, pdf = _save(values, tmp_path, "t")
    with fitz.open(str(pdf)) as doc:
        page = doc[0]
        scale = UF.PRINTED_FRACTION * PFS.LINE_WIDTH_PT / page.rect.width
        sizes = sorted(s["size"] * scale for b in page.get_text("dict")["blocks"] for ln in b.get("lines", [])
                       for s in ln["spans"] if s["text"].strip())
    assert sizes and sizes[0] >= PFS.MIN_PRINTED_PT, sizes[:5]
    assert png.exists() and png.stat().st_size > 5000


def test_two_runs_give_the_same_pdf_bytes(values, tmp_path):
    _png, first = _save(values, tmp_path, "a")
    t = time.time()
    while time.time() - t < 1.2:                  # cross a second boundary: the creation-date defect
        pass
    _png2, second = _save(values, tmp_path, "b")
    assert first.read_bytes() == second.read_bytes()


def test_the_pdf_writer_omits_the_creation_date():
    with open(os.path.join(HERE, "src", "make_uncertainty_figure.py"), encoding="utf-8") as fh:
        text = fh.read()
    assert 'metadata={"CreationDate": None}' in text


def test_the_figure_text_names_the_statistic_and_the_book(values):
    with PFS.style():
        fig = UF.build_figure(values)
    fig.canvas.draw()
    texts = " | ".join(t.get_text() for t in fig.findobj(matplotlib.text.Text) if t.get_text())
    plt.close(fig)
    assert "VaR 99.5%" in texts and "GBP 500m" in texts and "headline centre" in texts


def test_the_declared_outputs_are_the_manifests():
    sys.path.insert(0, HERE)
    import reproduce
    steps = [s for s, _stage, _m in reproduce.STEPS]
    assert "make_uncertainty_figure.py" in steps
    assert steps.index("make_uncertainty_figure.py") > max(
        steps.index(s) for s in ("vignette_uncertainty.py", "check_operator_backtest.py", "check_cohort_scope.py",
                                 "check_cohort_depth_sensitivity.py", "check_earned_basis_sensitivity.py",
                                 "check_bucket_share_sensitivity.py", "check_low_confidence_sensitivity.py",
                                 "check_donor_influence.py", "check_gamma0_vignette.py"))
    assert reproduce.OUTPUTS["make_uncertainty_figure.py"] == (
        "paper_pack/fig_uncertainty_sources.pdf", "paper_pack/fig_uncertainty_sources.png",
        "results/make_uncertainty_figure_results.json")
    assert UF.OUT_PNG.name == "fig_uncertainty_sources.png" and UF.OUT_PDF.name == "fig_uncertainty_sources.pdf"


def test_the_recorded_input_hashes_ignore_a_volatile_field_and_see_a_change_of_content(tmp_path, monkeypatch):
    """The sources carry runtime_seconds, which differs on every pass: the hashes are of the canonical content."""
    import shutil
    for fname in UF.SOURCES.values():
        shutil.copy(os.path.join(RESULTS, fname), tmp_path / fname)
    monkeypatch.setattr(UF, "RESULTS", tmp_path)
    first = UF.compute(UF.load_sources(tmp_path))["inputs"]
    path = tmp_path / UF.SOURCES["backtest"]
    d = json.loads(path.read_text(encoding="utf-8"))
    d["runtime_seconds"] = {"total": 12345.6, "fold_fits_wall": 1.0, "workers": 7}
    path.write_text(json.dumps(d, indent=2) + "\n", encoding="utf-8")
    assert UF.compute(UF.load_sources(tmp_path))["inputs"] == first
    d["n"] = d["n"] + 1
    path.write_text(json.dumps(d), encoding="utf-8")
    second = UF.compute(UF.load_sources(tmp_path))["inputs"]
    assert second["backtest"]["sha256"] != first["backtest"]["sha256"]
    assert all(second[k] == first[k] for k in first if k != "backtest")


def test_the_volatile_keys_this_test_strips_are_reproduces():
    sys.path.insert(0, HERE)
    import reproduce
    assert tuple(reproduce.VOLATILE) == VOLATILE
