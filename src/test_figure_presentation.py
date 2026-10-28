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
        fig, ax, _leg = MPF.size_figure(S, R, H, cal, yr, ritc)
        out["fig_size_dispersion"] = (fig, [ax])
        fig, ax, _leg = MPF.hhi_figure(S, R, H, cal_gf)
        out["fig_hhi_dispersion"] = (fig, [ax])
        fig, axes, _gof = MPF.gof_figure(S, R, H, ritc, cal)
        out["fig_goodness_of_fit"] = (fig, list(axes))
        raw, transferred, sqrt_r, _r = SURV.pools(TO.HEADLINE)
        fig, ax, _note, _obs = SURV.build_figure(raw, transferred, sqrt_r, TO.HEADLINE)
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
    extra = (inputs[3], inputs[4]) if build == "size_figure" else ()      # Figure 2's check needs the years and regime
    with PFS.style():
        fig, ax, legend = getattr(MPF, build)(S, R, H, inputs[which], *extra)
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


def test_figure_2_labels_the_scale_curve_a_base_scale_reference(figures, inputs):
    """The edit review of 27 October 2026, item 21: the Student-t scale is not a median of |S|; the curve stays only as a
    reference and its legend says so, and the medians are compared with the posterior-predictive medians."""
    texts = _legend_texts(figures["fig_size_dispersion"][1])
    assert any("base scale $s(R)$" in t and "reference, not a median" in t for t in texts), texts
    assert any(t.startswith("posterior-predictive") and "median" in t and "90% band" in t for t in texts), texts
    assert "observed vigintile median" in texts, texts
    assert not [t for t in texts if r"\sigma" in t], texts


def test_figure_2_refuses_a_fit_with_a_concentration_exponent(inputs):
    S, R, H, yr, ritc, _cal, cal_gf, _c = inputs
    assert cal_gf["gamma"] > 0
    with PFS.style(), pytest.raises(SystemExit, match="size-only headline"):
        MPF.size_figure(S, R, H, cal_gf, yr, ritc)


def _ppc_line(ax):
    """Figure 2's posterior-predictive median line: the one solid connected line through the bins."""
    lines = [ln for ln in ax.lines if ln.get_linestyle() == "-" and ln.get_marker() in ("None", "none", "", None)
             and len(ln.get_xdata()) <= MPF.N_VIGINTILES]
    assert len(lines) == 1, [ln.get_label() for ln in ax.lines]
    return lines[0]


def test_figure_2_plots_the_recorded_check_like_for_like(figures, inputs):
    """The observed points are each vigintile's median |S| and the model line is the record's posterior-predictive
    median of the same statistic for the same records, at the same bins."""
    S, R, H, yr, ritc, cal, _gf, _c = inputs
    with io.open(os.path.join(HERE, "results", "size_dispersion_ppc_results.json"), encoding="utf-8") as _fh:
        rec = json.load(_fh)
    assert rec == json.loads(json.dumps(MPF.size_ppc(S, R, yr, ritc, cal))), "the record is the script's own check"
    b = MPF.vigintiles(R)
    assert [r["n"] for r in rec["bins"]] == [int((b == i).sum()) for i in range(MPF.N_VIGINTILES)]
    assert sum(r["n"] for r in rec["bins"]) == len(S) and sum(r["n_ritc"] for r in rec["bins"]) == int(ritc.sum())
    ax = figures["fig_size_dispersion"][1][0]
    line = _ppc_line(ax)
    assert list(line.get_ydata()) == [r["ppc_median_abs_S"] for r in rec["bins"]]
    obs = [ln for ln in ax.lines if ln.get_marker() == "s"]
    assert len(obs) == 1 and list(obs[0].get_ydata()) == [float(np.median(np.abs(S)[b == i])) for i in range(20)]
    for r in rec["bins"]:
        assert r["band_lo"] < r["ppc_median_abs_S"] < r["band_hi"]
        assert r["observed_outside_band"] == (not r["band_lo"] <= r["observed_median_abs_S"] <= r["band_hi"])
    assert rec["n_bins_outside_band"] == sum(r["observed_outside_band"] for r in rec["bins"])
    # the record says how the year shock's spread and the band are set (the figure does not)
    assert rec["tau_s_used"] == cal["params"]["tau_s"]["mean"] and rec["band_percentiles"] == [5.0, 95.0]
    assert ("posterior mean, %.3f" % cal["params"]["tau_s"]["mean"]) in rec["tau_s_rule"]
    assert rec["band_definition"].startswith("the 5th to 95th percentile")


#: the paper's vocabulary (the rewrite of 27 October 2026): S is "the measured movement" and the worked target is named
#: by its size. The supplement's correlation profile (systemic_ppc.py) is outside this check: its axis reads "Within-pair
#: PYD correlation", and its producer runs refits, so it is relabelled only with a recorded pass
OLD_VOCABULARY = ("PYD", "Vignette", "Severity")


@pytest.mark.parametrize("name", sorted(set(PFS.PRINTED_FRACTION) - {"systemic_correlation_profile"}))
def test_the_figures_speak_the_papers_vocabulary(figures, name):
    fig, axes = figures[name]
    texts = _titles(fig, axes) + _legend_texts(axes) + [a.get_xlabel() for a in axes] + [a.get_ylabel() for a in axes]
    assert texts
    bad = [t for t in texts for w in OLD_VOCABULARY if w in t]
    assert bad == [], (name, bad)


def test_figure_2_names_the_measured_movement(figures):
    ax = figures["fig_size_dispersion"][1][0]
    assert ax.get_ylabel() == "Measured movement $|S|$ (absolute)", ax.get_ylabel()


def _toy_draws(tmp_path, n=400, **over):
    p = {"k": 1.0, "sd_undiv": 0.05, "sd_div": 0.0, "nu_clean": 1e6, "nu_ritc": 1e6, "beta_ritc": 0.0, "gamma": 0.0}
    p.update(over)
    path = tmp_path / ("d%d.npz" % len(list(tmp_path.iterdir())))
    np.savez(path, **{k: np.full(n, float(v)) for k, v in p.items()})
    return path


def test_the_check_replicates_the_median_of_abs_s_not_the_scale(tmp_path):
    """With a normal tail, no size term and no year shock, a record's |S| is half-normal: its median is 0.6745 times the
    scale. The check's model median must be that, not the scale itself (which is what the figure used to draw)."""
    n = 4000
    R = np.linspace(10.0, 4000.0, n)
    S, yr, ritc = np.zeros(n), np.full(n, 2020), np.zeros(n, bool)
    cal = {"gamma": 0.0, "params": {"tau_s": {"mean": 0.0}}, "sd_undiv": 0.05, "sd_div": 0.0, "k": 1.0}
    rec = MPF.size_ppc(S, R, yr, ritc, cal, draws_path=_toy_draws(tmp_path))
    meds = [r["ppc_median_abs_S"] for r in rec["bins"]]
    assert np.allclose(meds, 0.05 * 0.6744897501960817, rtol=0.03), meds


def test_the_check_carries_the_ritc_scale_and_the_year_shock(tmp_path):
    """The RITC records' replicates carry exp(beta_RITC), and the year shock widens the band: a check that dropped
    either would not be the adopted model's."""
    n = 2000
    R = np.linspace(10.0, 4000.0, n)
    S, yr = np.zeros(n), np.repeat(np.arange(2015, 2025), n // 10)
    ritc = np.ones(n, bool)
    cal = {"gamma": 0.0, "params": {"tau_s": {"mean": 0.0}}, "sd_undiv": 0.05, "sd_div": 0.0, "k": 1.0}
    base = MPF.size_ppc(S, R, yr, ritc, cal, draws_path=_toy_draws(tmp_path))
    up = MPF.size_ppc(S, R, yr, ritc, cal, draws_path=_toy_draws(tmp_path, beta_ritc=np.log(2.0)))
    ratio = [u["ppc_median_abs_S"] / b["ppc_median_abs_S"] for u, b in zip(up["bins"], base["bins"])]
    assert np.allclose(ratio, 2.0, rtol=0.05), ratio
    cal_tau = dict(cal, params={"tau_s": {"mean": 0.3}})
    wide = MPF.size_ppc(S, R, yr, ritc, cal_tau, draws_path=_toy_draws(tmp_path))
    w0 = np.mean([r["band_hi"] / r["band_lo"] for r in base["bins"]])
    w1 = np.mean([r["band_hi"] / r["band_lo"] for r in wide["bins"]])
    assert w1 > 1.5 * w0, (w0, w1)
    assert wide["tau_s_used"] == 0.3


def test_figure_5_says_it_plots_the_base_scale_residual(figures, inputs):
    """The edit review of 27 October 2026, item 28: the residual divides by the base size scale s(R) only, with no year
    shock and no RITC scale term; the axis labels and the titles say so (the Student-t line a reference), and the
    plotted residuals are exactly S / s(R) for both regimes."""
    S, R, H, _yr, ritc, cal, _gf, _c = inputs
    fig, axes = figures["fig_goodness_of_fit"]
    ax = axes[0]
    assert "base-scale residual" in ax.get_ylabel() and "s(R)" in ax.get_ylabel(), ax.get_ylabel()
    assert "Student-$t$ reference" in ax.get_title() and "reference" in ax.get_xlabel()
    assert "base-scale" in fig._suptitle.get_text() and "no year or RITC scale term" in fig._suptitle.get_text()
    s_r = np.sqrt(cal["sd_undiv"] ** 2 + cal["sd_div"] ** 2 * (R / 500.0) ** (2.0 * (cal["k"] - 1.0)))
    pts = {ln.get_label().split(",")[0]: np.asarray(ln.get_ydata(), float) for ln in ax.lines if ln.get_marker() == "o"}
    assert np.allclose(pts["clean"], np.sort(S[~ritc] / s_r[~ritc]), rtol=1e-12, atol=0)
    assert np.allclose(pts["RITC"], np.sort(S[ritc] / s_r[ritc]), rtol=1e-12, atol=0)


def test_figure_3_legend_names_the_gamma_free_fit_and_its_gamma(figures, inputs):
    cal_gf = inputs[6]
    fig, axes = figures["fig_hhi_dispersion"]
    curve = [t for t in _legend_texts(axes) if "concentration slope" in t]
    assert len(curve) == 1, _legend_texts(axes)
    assert r"$\gamma$-free fit" in curve[0] and r"$\gamma=%.2f$" % cal_gf["gamma"] in curve[0], curve


def test_figure_5_keys_its_markers_in_the_legend(figures):
    texts = _legend_texts(figures["fig_v1_ritc_survivor"][1])
    assert any(t.startswith("VaR 99%") for t in texts) and any(t.startswith("VaR 99.5%") for t in texts), texts


def test_the_coverage_figure_counts_listed_syndicates_not_sample_over_active(inputs, figures):
    """The fresh review of 28 October 2026, finding 3: six working-sample records are off their year's official list
    (1110/2020, 1884/2022, 1110/2023, 1884/2023, 1110/2024, 1884/2024), so sample / active is not a coverage. The line
    is the listed syndicates' share in the sample, 2020-2024 only, from the lists' membership."""
    yr = inputs[3]
    got = MPF.listed_in_sample(yr, MPF.syndicates())
    assert {y: v[:2] for y, v in got.items()} == {2020: (61, 98), 2021: (54, 92), 2022: (56, 93), 2023: (67, 95),
                                                   2024: (72, 95)}
    assert sum(v[2] for v in got.values()) == 6
    fig, axes = figures["fig_corpus_coverage"]
    line = [ln for ax in axes for ln in ax.lines if "Listed" in ln.get_label()]
    assert len(line) == 1 and list(line[0].get_xdata()) == [6, 7, 8, 9, 10]
    title = axes[0].get_title()
    assert "310 of 473 listed" in title and "overall" not in title, title


def test_an_off_list_record_does_not_count_as_a_listed_syndicate_in_the_sample():
    import market_active
    year = 2024
    listed = sorted(market_active.official_lists()[year])
    off = max(listed) + 1
    yr = np.array([year, year, year])
    syn = np.array([listed[0], listed[1], off])
    got = MPF.listed_in_sample(yr, syn)[year]
    assert got == (2, len(listed), 1)
