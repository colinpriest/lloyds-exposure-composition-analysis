#!/usr/bin/env python3
"""Figure layout: nothing printed over the data it labels (review of 29 September 2026, M-16).

Figure 5 (Vignette 1 adverse tail): the VaR99.5 label sat on the curves and markers at the 99.5% level.
Figure 6 (corpus coverage): the legend sat over the 2014-2016 bars. Each script now places its text and
refuses to write a figure where it is struck; these tests run those checks on the committed inputs, show
that each check sees the placement it replaced, and exercise the checks on figures built to fail.

All six paper figures also printed their text at 3.4-4.8 pt (the manuscript's gate CC): drawn 6.9-10.9 inches
wide, they were printed 4.2-5.0 inches wide. Each is now drawn at its printed width (paper_figure_style.py), and
the last tests here render every one through its script's own save path and measure its text as the gate does.

Run:  python -m pytest src/test_figure_layout.py -q
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
from vignette_uncertainty import var_q    # noqa: E402

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@pytest.fixture(autouse=True)
def _close_figures():
    yield
    plt.close("all")


# ------------------------------------------------------------------ Figure 5 ------
@pytest.mark.parametrize("mode", TO.MODES)
def test_the_survivor_label_is_clear_of_every_curve_marker_and_the_legend(mode):
    """Each mode's pool is computed from its own regenerated fit."""
    raw, transferred, sqrt_r, _ritc = SURV.pools(mode)
    fig, ax, note, obstacles = SURV.build_figure(raw, transferred, sqrt_r, mode)
    assert SURV.text_is_clear(fig, ax, note, obstacles)
    assert len(obstacles) == 3 + 6 + 1, "three curves, six VaR markers and the legend must all be obstacles"


@pytest.mark.parametrize("mode", TO.MODES)
def test_the_check_sees_the_placement_it_replaced(mode):
    """The first superseded label, midway between the two coincident VaR99.5 points just below the 99.5% line, is
    struck on the figure as now drawn. Each mode's pool is computed from its own regenerated fit."""
    raw, transferred, sqrt_r, _ritc = SURV.pools(mode)
    fig, ax, _note, obstacles = SURV.build_figure(raw, transferred, sqrt_r, mode)
    v = var_q(transferred, 0.995)
    old = ax.text(v, (1 - 0.995) * 0.62, "VaR$_{99.5}$: %.3f$\\to$%.3f" % (v, v), ha="center", fontsize=8)
    assert not SURV.text_is_clear(fig, ax, old, obstacles)


# ------------------------------------------------------------------ Figure 3 (the edit review of 27 October 2026) ------
def test_the_survivor_draws_raw_the_size_only_transfer_and_the_square_root_benchmark():
    """Item 25: the pure-rescale curve, which coincided with the transferred one at the cutpoint, gave way to the
    square-root benchmark; the transfer drawn is the headline's (the rank map applied), the benchmark is
    check_operator_backtest's rule S sqrt(R_donor / R_target)."""
    raw, transferred, sqrt_r, _ritc = SURV.pools(TO.HEADLINE)
    fig, ax, _note, _obs = SURV.build_figure(raw, transferred, sqrt_r, TO.HEADLINE)
    labels = [t.get_text() for t in ax.get_legend().get_texts()]
    assert labels[:3] == ["Raw (untransferred)", "Square-root benchmark", "Size-only transfer (headline)"], labels
    assert not [t for t in labels if "rescale" in t.lower() or "de-ritc" in t.lower()], labels
    import vignette_uncertainty as VU
    S, R, _H, _synd, _year = VU.load_pool()
    assert np.array_equal(raw, S) and np.allclose(sqrt_r, S * np.sqrt(R / 500.0), rtol=0, atol=0)


def test_the_survivor_transfer_is_the_headline_operators_pool_with_the_rank_map():
    """The curve drawn as the size-only transfer is the headline operator's pool, the RITC rank map applied to the
    accepted-liability donors (as check_operator_backtest's vignette figures transfer them): the clean donors' values
    are the pure rescale's, and the RITC donors' are not. The pure rescale reproduces the record's VaR99 and VaR99.5
    as well (the two pools coincide there), so the record check alone cannot tell them apart."""
    import vignette_uncertainty as VU
    raw, transferred, _sqrt_r, ritc = SURV.pools(TO.HEADLINE)
    S, R, H, _synd, _year = VU.load_pool()
    draws, ref, hlo, hce = VU.load_draws(TO.HEADLINE)
    v1, _, _ = VU.load_targets()
    th = TO.params({p: float(draws[p].mean()) for p in draws}, TO.HEADLINE)
    pure = VU.transfer(S, R, H, v1, th, (ref, hlo, hce), ritc=None)
    ritc = np.asarray(ritc, bool)
    assert ritc.sum() > 0
    assert np.array_equal(transferred[~ritc], pure[~ritc])
    moved = transferred[ritc] != pure[ritc]
    assert moved.sum() == int((S[ritc] != 0).sum()) > 0, "the rank map moves every nonzero RITC donor"


def test_the_survivor_callout_gives_the_main_transfer_from_the_record():
    """The callout reads raw -> size-only at 99.5%, with the benchmark beneath, each figure as the backtest record holds
    it; it has no leader and is not the RITC map's 'x -> x'."""
    raw, transferred, sqrt_r, _ritc = SURV.pools(TO.HEADLINE)
    rec = SURV.recorded_figures()
    printed = SURV.check_against_record(raw, transferred, sqrt_r, rec)
    fig, ax, note, _obs = SURV.build_figure(raw, transferred, sqrt_r, TO.HEADLINE, printed)
    text = note.get_text()
    want = ("raw %.3f $\\to$ size-only %.3f" % (rec["raw"]["v995"], rec["transferred"]["v995"]),
            "square-root benchmark %.3f" % rec["sqrt"]["v995"])
    assert all(w in text for w in want), text
    assert "%.3f" % rec["raw"]["v995"] != "%.3f" % rec["transferred"]["v995"], "raw and size-only must differ"
    assert not hasattr(note, "arrow_patch"), "the callout has no leader"
    assert [t for t in ax.texts if "VaR 99.5%" in t.get_text()] == [note], "one callout"


def test_the_survivor_refuses_pools_that_do_not_reproduce_the_record():
    raw, transferred, sqrt_r, _ritc = SURV.pools(TO.HEADLINE)
    rec = SURV.recorded_figures()
    assert SURV.check_against_record(raw, transferred, sqrt_r, rec)["sqrt"] == rec["sqrt"]["v995"]
    for key in ("raw", "transferred", "sqrt"):
        bad = {k: dict(v) for k, v in rec.items()}
        bad[key]["v995"] *= 1.001
        with pytest.raises(SystemExit, match="do not reproduce"):
            SURV.check_against_record(raw, transferred, sqrt_r, bad)


def test_a_leader_from_the_former_callout_place_would_cross_a_curve():
    """Why the callout has no leader: from the former place (PREFERRED, lower left) a leader to the size-only 99.5%
    point crosses a curve on the figure as now drawn."""
    raw, transferred, sqrt_r, _ritc = SURV.pools(TO.HEADLINE)
    fig, ax, _note, obstacles = SURV.build_figure(raw, transferred, sqrt_r, TO.HEADLINE)
    old = ax.text(SURV.PREFERRED[0], SURV.PREFERRED[1], "VaR 99.5%", transform=ax.transAxes, ha="center",
                  va="center")
    assert not SURV.leader_is_clear(fig, ax, old, (var_q(transferred, 0.995), 1 - 0.995), obstacles)


def test_the_title_names_the_headline_operator():
    """The headline pool is computed from the regenerated (gamma = 0) fit."""
    raw, transferred, sqrt_r, _ritc = SURV.pools(TO.HEADLINE)
    _fig, ax, _note, _obs = SURV.build_figure(raw, transferred, sqrt_r, TO.HEADLINE)
    assert "size-only transfer, $\\gamma=0$" in ax.get_title()


def test_the_survivor_speaks_the_papers_vocabulary():
    """The rewrite of 27 October 2026: the worked target is named by its size (read from the targets, GBP 500m), not as
    'Vignette 1', and S is the measured movement, not a 'PYD ratio'."""
    import vignette_uncertainty as VU
    raw, transferred, sqrt_r, _ritc = SURV.pools(TO.HEADLINE)
    _fig, ax, _note, _obs = SURV.build_figure(raw, transferred, sqrt_r, TO.HEADLINE)
    title, xlabel = ax.get_title(), ax.get_xaxis().get_label().get_text()
    assert title.startswith("£%.0fm target: adverse tail" % VU.load_targets()[0][0]), title
    assert xlabel == "Measured movement $S$ (adverse side)", xlabel
    for t in (title, xlabel, ax.get_ylabel()):
        assert "Vignette" not in t and "PYD" not in t, t


def _toy():
    fig, ax = plt.subplots(figsize=(4, 3))
    ax.plot([0, 1], [0, 1])
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    return fig, ax, [np.array([[0.0, 0.0], [1.0, 1.0]])]


def test_the_check_sees_a_curve_through_a_label_and_passes_one_beside_it():
    fig, ax, curve = _toy()
    struck = ax.text(0.5, 0.5, "label", ha="center", va="center")
    clear = ax.text(0.15, 0.85, "label", ha="center", va="center")
    assert not SURV.text_is_clear(fig, ax, struck, curve)
    assert SURV.text_is_clear(fig, ax, clear, curve)


def test_the_check_sees_a_leader_that_crosses_a_curve_and_passes_one_that_does_not():
    """The annotation's leader line must reach its target without crossing a curve (the figure's box sat beyond the
    raw curve and its leader crossed that curve on its way to the de-RITC one)."""
    fig, ax, curve = _toy()
    label = ax.text(0.1, 0.9, "label", ha="center", va="center")
    assert not SURV.leader_is_clear(fig, ax, label, (0.9, 0.5), curve)       # y = x lies between the two
    assert SURV.leader_is_clear(fig, ax, label, (0.1, 0.5), curve)           # straight down, y = x is not met
    assert SURV.leader_is_clear(fig, ax, label, (0.1, 0.1), curve)           # ends on the curve itself: not counted


def test_the_check_refuses_a_box_that_leaves_the_axes():
    fig, ax, curve = _toy()
    outside = ax.text(0.99, 0.9, "a long label running out of the axes", ha="center", va="center")
    assert not SURV.text_is_clear(fig, ax, outside, [])


@pytest.mark.parametrize("mode", TO.MODES)
def test_the_survivor_callout_lies_inside_the_axes_and_the_check_sees_one_that_is_struck(mode):
    """The callout has no leader (27 October 2026); its box lies inside the axes clear of every curve, and the same
    check refuses a box moved onto the curves at the 99.5% point."""
    raw, transferred, sqrt_r, _ritc = SURV.pools(mode)
    fig, ax, note, obstacles = SURV.build_figure(raw, transferred, sqrt_r, mode)
    assert SURV.text_is_clear(fig, ax, note, obstacles)
    note.set_transform(ax.transData)
    note.set_position((var_q(transferred, 0.995), 1 - 0.995))
    assert not SURV.text_is_clear(fig, ax, note, obstacles)


def test_with_no_clear_place_the_callout_is_refused():
    fig, ax, curve = _toy()
    with pytest.raises(SystemExit, match="CALLOUT_CANDIDATES"):
        SURV.place_callout(fig, ax, "label", curve, candidates=((0.5, 0.5), (0.3, 0.3)))
    assert SURV.place_callout(fig, ax, "label", curve, candidates=((0.5, 0.5), (0.2, 0.8))) is not None


def test_with_no_clear_place_the_script_refuses():
    fig, ax, curve = _toy()
    with pytest.raises(SystemExit):
        SURV.place_annotation(fig, ax, "label", (0.5, 0.5), curve, candidates=((0.5, 0.5), (0.3, 0.3)))
    assert SURV.place_annotation(fig, ax, "label", (0.5, 0.5), curve, candidates=((0.5, 0.5), (0.2, 0.8))) \
        is not None, "the first clear candidate must be taken"


# ------------------------------------------------------------------ Figure 6 ------
@pytest.fixture(scope="module")
def coverage_inputs():
    """make_paper_figures.load reads the gamma-free calibration the regeneration writes."""
    _S, _R, _H, yr, _ritc, _cal, _cal_gf, corpus_by_year = MPF.load()
    return yr, corpus_by_year


def test_the_coverage_legend_is_clear_of_the_bars(coverage_inputs):
    fig, ax, legend = MPF.coverage_figure(*coverage_inputs)
    assert MPF.legend_clear_of_bars(fig, ax, legend)
    assert len(legend.get_texts()) == 4, "the three bar series and the coverage line share one legend"


def test_the_bar_check_sees_the_legend_it_replaced(coverage_inputs):
    """The superseded placement: inside the axes, upper left, over the 2014-2016 bars."""
    fig, ax, legend = MPF.coverage_figure(*coverage_inputs)
    legend.remove()
    old = ax.legend(loc="upper left", fontsize=8, frameon=False)
    assert not MPF.legend_clear_of_bars(fig, ax, old)


# ------------------------------------------------------------------ the supplement's profile ------
def _profile():
    """The profile as its script draws it, from the recorded PPC bins and the M1 draws (as the `rendered` fixture)."""
    with io.open(os.path.join(HERE, "results", "systemic_ppc_results.json"), encoding="utf-8") as _fh:
        bins = json.load(_fh)["ppc"]["bins"]
    with np.load(os.path.join(HERE, "model", "dispersion_posterior_draws_systemic.npz")) as _npz:
        dz = {key: _npz[key] for key in _npz.files}
    grid = np.logspace(np.log10(20), np.log10(4000), 60)
    band = np.array([[b["band_5"] for b in bins], [b["band_95"] for b in bins]])
    return SPPC.profile_figure([80.0, 280.0, 1100.0], band, [b["observed_mean_rho"] for b in bins], grid,
                               SPPC.implied_curve(dz, grid))


def test_the_profiles_legend_is_clear_of_every_line_and_the_band():
    """23 October 2026 (the manuscript's gate CC): the legend entry 'M1 implied rho(R), equal-size pairs' was crossed by
    the observed series' first segment and marker. No line, marker or band is under the legend now."""
    fig, ax = _profile()
    assert PFS.data_under_legend(fig, ax, ax.get_legend(), pad_pt=SPPC.LEGEND_CLEARANCE_PT) == []
    assert PFS.data_under_legend(fig, ax, ax.get_legend(), pad_pt=60.0) != [], "the padding is read: a wide one reaches the data"
    assert len(ax.get_legend().get_texts()) == 3, "the band, the observed series and the implied curve"


def test_the_check_sees_the_profiles_legend_where_it_was():
    """The superseded drawing: the same legend over the autoscaled vertical axis is crossed by the observed series."""
    fig, ax = _profile()
    legend = ax.get_legend()
    assert ax.get_ylim()[1] > 0.19, "the figure leaves room above the data (it autoscaled to 0.18)"
    with PFS.style():
        ax.set_ylim(-0.0285, 0.1825)               # the limits Matplotlib chose from the data before
        hits = PFS.data_under_legend(fig, ax, legend)
    assert "Observed mean pairwise Spearman rho" in hits, hits


def test_the_script_makes_room_where_it_can_and_refuses_where_it_cannot(monkeypatch):
    """Headroom clears a legend struck by a line along the top; with too few steps to clear it, the script refuses."""
    def toy():
        fig, ax = plt.subplots(figsize=(4, 3))
        ax.plot([0.0, 1.0], [0.92, 0.92], label="along the top")
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        return fig, ax, ax.legend(loc="upper left")
    fig, ax, legend = toy()
    assert PFS.data_under_legend(fig, ax, legend) == ["along the top"]
    SPPC.make_room_for_legend(fig, ax, legend)
    assert PFS.data_under_legend(fig, ax, legend) == [] and ax.get_ylim()[1] > 1.0
    monkeypatch.setattr(SPPC, "LEGEND_HEADROOM_STEPS", 2)
    fig, ax, legend = toy()
    with pytest.raises(SystemExit, match="still over the data"):
        SPPC.make_room_for_legend(fig, ax, legend)


def test_the_legend_check_counts_a_line_that_crosses_without_a_vertex_in_the_box():
    """What the point count missed: a connected series passing through the legend between two vertices outside it."""
    fig, ax = plt.subplots(figsize=(4, 3))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.plot([0.05, 0.95], [0.95, 0.95], "o-", label="across the top")      # vertices at the two ends, none under it
    ax.plot([0.05, 0.95], [0.05, 0.05], "o-", label="across the bottom")
    ax.axhline(0.9, color="0.5", label="a reference mark")                  # a blended transform: not data
    legend = ax.legend(loc="upper center")
    hits = PFS.data_under_legend(fig, ax, legend)
    assert hits == ["across the top"], hits
    assert PFS.data_under_legend(fig, ax, ax.legend(loc="center")) == []
    band = ax.fill_between([0.0, 1.0], [0.4, 0.4], [0.6, 0.6], label="band")
    assert band in ax.collections and PFS.data_under_legend(fig, ax, ax.legend(loc="center")) == ["band"]


# ------------------------------------------------------------------ printed text size ------
@pytest.fixture(scope="module")
def rendered(tmp_path_factory):
    """Every paper figure, written by its script's own save path into a scratch folder. The concentration figure
    is drawn from the gamma-free fit, as make_paper_figures.main draws it (option B, 10 October 2026).
    It needs both regenerated calibrations."""
    out = tmp_path_factory.mktemp("paper_figures")
    (out / "results").mkdir()
    (out / "paper_pack").mkdir()
    S, R, H, yr, ritc, cal, cal_gf, corpus_by_year = MPF.load()
    syn = MPF.syndicates()
    keep = (MPF.PP, MPF.SD, SURV.SCRIPT_DIR)
    try:
        MPF.PP, MPF.SD = out, out          # fig_gof also writes results/goodness_of_fit_results.json: here
        MPF.fig_coverage(yr, corpus_by_year, syn)
        MPF.fig_size(S, R, H, cal, yr, ritc)
        MPF.fig_hhi(S, R, H, cal_gf)
        MPF.fig_gof(S, R, H, ritc, cal, syn, yr)
        SURV.SCRIPT_DIR = out
        SURV.main()
    finally:
        MPF.PP, MPF.SD, SURV.SCRIPT_DIR = keep
        plt.close("all")
    # the profile's inputs come from a 500-replicate PPC; its recorded bins and the M1 draws stand in for them
    with io.open(os.path.join(HERE, "results", "systemic_ppc_results.json"), encoding="utf-8") as _fh:
        bins = json.load(_fh)
    bins = bins["ppc"]["bins"]
    with np.load(os.path.join(HERE, "model", "dispersion_posterior_draws_systemic.npz")) as _npz:
        dz = {key: _npz[key] for key in _npz.files}
    grid = np.logspace(np.log10(20), np.log10(4000), 60)
    band = np.array([[b["band_5"] for b in bins], [b["band_95"] for b in bins]])
    fig, _ax = SPPC.profile_figure([80.0, 280.0, 1100.0], band, [b["observed_mean_rho"] for b in bins], grid,
                                   SPPC.implied_curve(dz, grid))
    SPPC.save_profile_figure(fig, out / "systemic_correlation_profile.png", out / "systemic_correlation_profile.pdf")
    files = {}
    for name in PFS.PRINTED_FRACTION:
        hits = [p for p in (out / (name + ".pdf"), out / "paper_pack" / (name + ".pdf")) if p.exists()]
        assert len(hits) == 1, name
        files[name] = hits[0]
    return files


@pytest.mark.parametrize("name", sorted(PFS.PRINTED_FRACTION))
def test_every_paper_figure_prints_its_text_at_the_floor_or_above(rendered, name):
    sizes = PFS.printed_text_sizes(rendered[name], name)
    assert sizes, "no text read from %s" % name
    assert sizes[0] >= PFS.MIN_PRINTED_PT, "%s prints text from %.2f pt" % (name, sizes[0])


@pytest.mark.parametrize("name", PFS.SAVED_UNCROPPED)
def test_an_uncropped_figure_prints_its_text_with_the_margin(rendered, name):
    """30 September 2026: the supplement's profile, saved uncropped and drawn from the article figures' 402.6 pt,
    printed its 8 pt text at 7.94 pt in supplement.pdf; the line is 399.69 pt. Drawn from the line width over the
    margin, it prints at 8.16 pt, and the manuscript asks for 8.1 pt at least."""
    sizes = PFS.printed_text_sizes(rendered[name], name)
    assert sizes[0] >= 8.1, "%s prints text from %.3f pt" % (name, sizes[0])
    import fitz
    with fitz.open(str(rendered[name])) as doc:
        assert doc[0].rect.width == pytest.approx(PFS.width_in(name) * 72.0, abs=0.01), "the page is the drawn width"


def test_the_measure_sees_a_figure_drawn_wider_than_it_prints(tmp_path):
    """The failure the gate found: 8 pt text on a 7-inch figure printed 4.2 inches wide prints below 5 pt."""
    fig, ax = plt.subplots(figsize=(7.0, 5.0))
    ax.set_title("title", fontsize=8)
    fig.savefig(tmp_path / "wide.pdf")
    plt.close(fig)
    sizes = PFS.printed_text_sizes(tmp_path / "wide.pdf", "fig_size_dispersion")
    assert sizes[0] < 5.0 < PFS.MIN_PRINTED_PT


def test_the_printed_widths_are_the_manuscripts():
    """Each figure's printed fraction is the one the manuscript's \\includegraphics gives it."""
    root = os.environ.get("LLOYDS_PAPER_REPO") or os.path.join("D:" + os.sep, "Latex projects",
                                                                "BAJ - Lloyds reserves rescaling")
    paper = os.path.join(root, "paper")
    if not os.path.exists(os.path.join(paper, "main.tex")):
        pytest.skip("no manuscript at %s: set LLOYDS_PAPER_REPO to the paper repository, or this "
                    "cross-repository check does not run" % paper)
    found = {}
    for doc in ("main.tex", "supplement.tex"):
        with io.open(os.path.join(paper, doc), encoding="utf-8") as _fh:
            src = _fh.read()
        src = "\n".join(line for line in src.splitlines() if not line.lstrip().startswith("%"))
        for frac, fname in re.findall(r"\\includegraphics\[width=([0-9.]+)\\(?:line|text)width\]\{([^}]+)\}", src):
            found[fname[:-4] if fname.endswith(".pdf") else fname] = float(frac)
        # both documents take the medium layout (journal=aas), whose text width is the line the figures print on
        assert re.search(r"\\documentclass\[[^\]]*journal=aas[^\]]*\]\{cup-journal\}", src), doc
    assert {k: found.get(k) for k in PFS.PRINTED_FRACTION} == PFS.PRINTED_FRACTION
    with io.open(os.path.join(paper, "cup-journal.cls"), encoding="utf-8") as _fh:
        cls = _fh.read()
    medium = re.search(r"\\newcommand\*\\cup@layout@medium\{.*?\\geometry\{([^}]*)\}", cls, re.S).group(1)
    mm = {k: float(v) * (10.0 if unit == "cm" else 1.0)
          for k, v, unit in re.findall(r"(paperwidth|left|right)=([0-9.]+)(mm|cm)", medium)}
    assert PFS.LINE_WIDTH_PT == pytest.approx((mm["paperwidth"] - mm["left"] - mm["right"]) / 25.4 * 72.0)
    with io.open(os.path.join(paper, "audit_numbers.py"), encoding="utf-8") as _fh:
        gate = _fh.read()
    assert float(re.search(r"(?m)^FIGURE_MIN_PRINTED_PT = ([0-9.]+)", gate).group(1)) == PFS.MIN_PRINTED_PT
