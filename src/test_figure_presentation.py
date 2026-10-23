#!/usr/bin/env python3
"""The paper's figures as a reader sees them (the final review of 14 October 2026, P30).

The review found Figure 2's legend naming sigma(R, H-bar), a law the gamma = 0 headline does not have, and its
vertical axis running to 1e-06, four decades the eye read as empty; Figure 3's caption pointing at a legend that did
not say what the caption said it did; and Figure 5's four-line title. The checks of 15 October 2026 then found Figure
3's legend over 18 plotted points, and no clear corner inside Figure 2's axes once its axis was cropped. Each rule here is checked on every paper figure, built from
the committed inputs by its own script's builder, so a new figure is held to it as well:

  * no title runs to more than two lines;
  * no legend covers a plotted point;
  * a log axis starts no more than a decade below the 1st percentile of what it plots and ends no more than a decade
    above the largest value, so no near-empty decades are shown;
  * a note that points are not shown counts exactly the points the axis hides;
  * a figure drawn from the headline (gamma = 0) names no concentration in its legend, and Figure 3's legend names the
    gamma-free fit and its gamma, so the caption need not.

Run:  python -m pytest src/test_figure_presentation.py -q
"""
import io
import json
import os
import re

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt   # noqa: E402
import numpy as np                # noqa: E402
import pytest                     # noqa: E402

import make_paper_figures as MPF          # noqa: E402
import make_v1_ritc_survivor as SURV      # noqa: E402
import paper_figure_style as PFS          # noqa: E402
import systemic_ppc as SPPC               # noqa: E402
import transfer_operator as TO            # noqa: E402

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
#: the headline-fit figures: drawn from the gamma = 0 fit, their legends may not name a concentration term
HEADLINE_FIGURES = ("fig_size_dispersion", "fig_goodness_of_fit", "fig_v1_ritc_survivor")
CONCENTRATION_TERMS = (r"\bar H", r"\bar{H}", "R,H", "R, H", r"R,\bar")


@pytest.fixture(scope="module")
def inputs():
    return MPF.load()


@pytest.fixture(scope="module")
def figures(inputs):
    """{name: (fig, axes)} for every paper figure in paper_figure_style.PRINTED_FRACTION."""
    S, R, H, yr, ritc, cal, cal_gf, corpus_by_year = inputs
    out = {}
    fig, ax, _leg = MPF.coverage_figure(yr, corpus_by_year)
    out["fig_corpus_coverage"] = (fig, fig.axes)
    with PFS.style():
        fig, ax, _leg = MPF.size_figure(S, R, H, cal)
        out["fig_size_dispersion"] = (fig, [ax])
        fig, ax, _leg = MPF.hhi_figure(S, R, H, cal_gf)
        out["fig_hhi_dispersion"] = (fig, [ax])
        fig, axes, _gof = MPF.gof_figure(S, R, H, ritc, cal)
        out["fig_goodness_of_fit"] = (fig, list(axes))
        raw, pure, deritc, _r = SURV.pools(TO.HEADLINE)
        fig, ax, _note, _obs = SURV.build_figure(raw, pure, deritc, TO.HEADLINE)
        out["fig_v1_ritc_survivor"] = (fig, [ax])
    # the profile's inputs come from a 500-replicate PPC; its recorded bins and the M1 draws stand in for them, as in
    # test_figure_layout.py
    with io.open(os.path.join(HERE, "results", "systemic_ppc_results.json"), encoding="utf-8") as _fh:
        bins = json.load(_fh)["ppc"]["bins"]
    with np.load(os.path.join(HERE, "model", "dispersion_posterior_draws_systemic.npz")) as _npz:
        dz = {key: _npz[key] for key in _npz.files}
    grid = np.logspace(np.log10(20), np.log10(4000), 60)
    band = np.array([[b["band_5"] for b in bins], [b["band_95"] for b in bins]])
    fig, ax = SPPC.profile_figure([80.0, 280.0, 1100.0], band, [b["observed_mean_rho"] for b in bins], grid,
                                  SPPC.implied_curve(dz, grid))
    out["systemic_correlation_profile"] = (fig, [ax])
    assert set(out) == set(PFS.PRINTED_FRACTION), "every paper figure is checked"
    yield out
    plt.close("all")


def _titles(fig, axes):
    t = [a.get_title() for a in axes if a.get_title()]
    sup = getattr(fig, "_suptitle", None)
    return t + ([sup.get_text()] if sup is not None and sup.get_text() else [])


def _legend_texts(axes):
    return [t.get_text() for a in axes if a.get_legend() is not None for t in a.get_legend().get_texts()]


def _plotted(ax, axis):
    """The data coordinates along `axis` ('x' or 'y') of what `ax` plots: scatter offsets and data-space lines (a
    horizontal or vertical reference line, drawn in a blended transform, is not data)."""
    col = 0 if axis == "x" else 1
    vals = [np.asarray(c.get_offsets(), float)[:, col] for c in ax.collections
            if len(c.get_offsets()) and c.get_offset_transform() == ax.transData]
    vals += [np.asarray(ln.get_xdata() if axis == "x" else ln.get_ydata(), float) for ln in ax.lines
             if ln.get_transform() == ax.transData and len(ln.get_xdata())]
    v = np.concatenate(vals) if vals else np.array([])
    return v[np.isfinite(v) & (v > 0)]


# ------------------------------------------------------------------ every figure ------
@pytest.mark.parametrize("name", sorted(PFS.PRINTED_FRACTION))
def test_no_title_runs_to_more_than_two_lines(figures, name):
    fig, axes = figures[name]
    titles = _titles(fig, axes)
    assert titles, "no title read from %s" % name
    long = [t for t in titles if t.count("\n") + 1 > 2]
    assert long == [], "%s: %s" % (name, long)


@pytest.mark.parametrize("name", sorted(PFS.PRINTED_FRACTION))
def test_no_legend_covers_a_plotted_point(figures, name):
    fig, axes = figures[name]
    legends = [(a, a.get_legend()) for a in axes if a.get_legend() is not None]
    assert legends, "no legend read from %s" % name
    for ax, legend in legends:
        assert MPF.points_under_legend(fig, ax, legend) == 0, name
        # and no connected line, band or bar under it either (a series joined by a line is not a point)
        assert PFS.data_under_legend(fig, ax, legend) == [], name


@pytest.mark.parametrize("build, which, old_loc", [("size_figure", 5, "lower left"), ("hhi_figure", 6, "upper right")])
def test_the_point_check_sees_the_legend_it_replaced(inputs, build, which, old_loc):
    """The superseded placements, inside the axes: Figure 2's lower left (Matplotlib's own choice before) and Figure 3's
    upper right (the script's) both cover points of the figures as now drawn."""
    S, R, H = inputs[0], inputs[1], inputs[2]
    with PFS.style():
        fig, ax, legend = getattr(MPF, build)(S, R, H, inputs[which])
        assert MPF.points_under_legend(fig, ax, legend) == 0
        legend.remove()
        old = ax.legend(frameon=False, loc=old_loc)
        assert MPF.points_under_legend(fig, ax, old) > 0
    plt.close(fig)


@pytest.mark.parametrize("name", sorted(PFS.PRINTED_FRACTION))
def test_a_log_axis_shows_no_near_empty_decades(figures, name):
    fig, axes = figures[name]
    fig.canvas.draw()
    for ax in axes:
        for axis, scale, lim in (("x", ax.get_xscale(), ax.get_xlim()), ("y", ax.get_yscale(), ax.get_ylim())):
            if scale != "log":
                continue
            v = _plotted(ax, axis)
            assert len(v), (name, axis)
            lo, hi = min(lim), max(lim)
            assert np.log10(np.quantile(v, 0.01)) - np.log10(lo) <= 1.0, (name, axis, lo, np.quantile(v, 0.01))
            assert np.log10(hi) - np.log10(v.max()) <= 1.0, (name, axis, hi, v.max())


def test_every_log_axis_is_checked(figures):
    """The rule above would pass a figure with no log axis: Figures 2 and 5 and the profile have one each."""
    logs = {name for name, (_f, axes) in figures.items() for a in axes if "log" in (a.get_xscale(), a.get_yscale())}
    assert {"fig_size_dispersion", "fig_v1_ritc_survivor", "systemic_correlation_profile"} <= logs


NOT_SHOWN = re.compile(r"(\d+) (?:points )?(above|below) ([0-9.]+) not shown")


def test_every_not_shown_note_counts_the_points_the_axis_hides(figures):
    seen = []
    for name, (fig, axes) in figures.items():
        texts = _titles(fig, axes) + _legend_texts(axes)
        for m in (NOT_SHOWN.search(t) for t in texts):
            if not m:
                continue
            n, side, edge = int(m.group(1)), m.group(2), float(m.group(3))
            ax = axes[0]
            y = np.concatenate([np.asarray(c.get_offsets(), float)[:, 1] for c in ax.collections
                                if c.get_offset_transform() == ax.transData])
            lo, hi = ax.get_ylim()
            assert (edge == pytest.approx(hi) if side == "above" else edge == pytest.approx(lo)), (name, edge)
            hidden = int((y > edge).sum()) if side == "above" else int((y < edge).sum())
            assert n == hidden, (name, n, hidden)
            seen.append(name)
    assert sorted(seen) == ["fig_hhi_dispersion", "fig_size_dispersion"], seen


# ------------------------------------------------------------------ the fits the figures name ------
@pytest.mark.parametrize("name", HEADLINE_FIGURES)
def test_a_headline_figure_names_no_concentration_term(figures, inputs, name):
    assert inputs[5]["gamma"] == 0.0, "the headline fit has gamma = 0 in the likelihood (option B)"
    _fig, axes = figures[name]
    texts = _legend_texts(axes)
    assert texts
    bad = [t for t in texts for term in CONCENTRATION_TERMS if term in t]
    assert bad == [], (name, bad)


def test_figure_2_names_the_size_only_scale_it_plots(figures, inputs):
    texts = _legend_texts(figures["fig_size_dispersion"][1])
    assert any(r"\sigma(R)" in t and "size-only" in t for t in texts), texts


def test_figure_2_refuses_a_fit_with_a_concentration_exponent(inputs):
    S, R, H, _yr, _ritc, _cal, cal_gf, _c = inputs
    assert cal_gf["gamma"] > 0
    with PFS.style(), pytest.raises(SystemExit, match="size-only headline"):
        MPF.size_figure(S, R, H, cal_gf)


def test_figure_3_legend_names_the_gamma_free_fit_and_its_gamma(figures, inputs):
    cal_gf = inputs[6]
    fig, axes = figures["fig_hhi_dispersion"]
    curve = [t for t in _legend_texts(axes) if "concentration slope" in t]
    assert len(curve) == 1, _legend_texts(axes)
    assert r"$\gamma$-free fit" in curve[0] and r"$\gamma=%.2f$" % cal_gf["gamma"] in curve[0], curve


def test_figure_5_keys_its_markers_in_the_legend(figures):
    texts = _legend_texts(figures["fig_v1_ritc_survivor"][1])
    assert any(t.startswith("VaR 99%") for t in texts) and any(t.startswith("VaR 99.5%") for t in texts), texts
