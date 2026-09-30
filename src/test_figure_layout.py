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
    raw, pure, deritc, _ritc = SURV.pools(mode)
    fig, ax, note, obstacles = SURV.build_figure(raw, pure, deritc, mode)
    assert SURV.text_is_clear(fig, ax, note, obstacles)
    assert len(obstacles) == 3 + 6 + 1, "three curves, six VaR markers and the legend must all be obstacles"


@pytest.mark.parametrize("mode", TO.MODES)
def test_the_check_sees_the_placement_it_replaced(mode):
    """The superseded label, midway between the two VaR99.5 points just below the 99.5% line, is struck."""
    raw, pure, deritc, _ritc = SURV.pools(mode)
    fig, ax, _note, obstacles = SURV.build_figure(raw, pure, deritc, mode)
    v_pure, v_der = var_q(pure, 0.995), var_q(deritc, 0.995)
    old = ax.text((v_pure + v_der) / 2, (1 - 0.995) * 0.62, "VaR$_{99.5}$: %.3f$\\to$%.3f" % (v_pure, v_der),
                  ha="center", fontsize=8)
    assert not SURV.text_is_clear(fig, ax, old, obstacles)


def test_the_title_names_the_headline_operator():
    raw, pure, deritc, _ritc = SURV.pools(TO.HEADLINE)
    _fig, ax, _note, _obs = SURV.build_figure(raw, pure, deritc, TO.HEADLINE)
    assert "size-only operator, $\\gamma=0$" in ax.get_title()


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


def test_with_no_clear_place_the_script_refuses():
    fig, ax, curve = _toy()
    with pytest.raises(SystemExit):
        SURV.place_annotation(fig, ax, "label", (0.5, 0.5), curve, candidates=((0.5, 0.5), (0.3, 0.3)))
    assert SURV.place_annotation(fig, ax, "label", (0.5, 0.5), curve, candidates=((0.5, 0.5), (0.2, 0.8))) \
        is not None, "the first clear candidate must be taken"


# ------------------------------------------------------------------ Figure 6 ------
@pytest.fixture(scope="module")
def coverage_inputs():
    _S, _R, _H, yr, _ritc, _cal, corpus_by_year = MPF.load()
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


# ------------------------------------------------------------------ printed text size ------
@pytest.fixture(scope="module")
def rendered(tmp_path_factory):
    """Every paper figure, written by its script's own save path into a scratch folder."""
    out = tmp_path_factory.mktemp("paper_figures")
    (out / "results").mkdir()
    (out / "paper_pack").mkdir()
    S, R, H, yr, ritc, cal, corpus_by_year = MPF.load()
    keep = (MPF.PP, MPF.SD, SURV.SCRIPT_DIR)
    try:
        MPF.PP, MPF.SD = out, out          # fig_gof also writes results/goodness_of_fit_results.json: here
        MPF.fig_coverage(yr, corpus_by_year)
        MPF.fig_size(S, R, H, cal)
        MPF.fig_hhi(S, R, H, cal)
        MPF.fig_gof(S, R, H, ritc, cal)
        SURV.SCRIPT_DIR = out
        SURV.main()
    finally:
        MPF.PP, MPF.SD, SURV.SCRIPT_DIR = keep
        plt.close("all")
    # the profile's inputs come from a 500-replicate PPC; its recorded bins and the M1 draws stand in for them
    bins = json.load(io.open(os.path.join(HERE, "results", "systemic_ppc_results.json"), encoding="utf-8"))
    bins = bins["ppc"]["bins"]
    dz = np.load(os.path.join(HERE, "model", "dispersion_posterior_draws_systemic.npz"))
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
        src = io.open(os.path.join(paper, doc), encoding="utf-8").read()
        src = "\n".join(line for line in src.splitlines() if not line.lstrip().startswith("%"))
        for frac, fname in re.findall(r"\\includegraphics\[width=([0-9.]+)\\(?:line|text)width\]\{([^}]+)\}", src):
            found[fname[:-4] if fname.endswith(".pdf") else fname] = float(frac)
        # both documents take the medium layout (journal=aas), whose text width is the line the figures print on
        assert re.search(r"\\documentclass\[[^\]]*journal=aas[^\]]*\]\{cup-journal\}", src), doc
    assert {k: found.get(k) for k in PFS.PRINTED_FRACTION} == PFS.PRINTED_FRACTION
    cls = io.open(os.path.join(paper, "cup-journal.cls"), encoding="utf-8").read()
    medium = re.search(r"\\newcommand\*\\cup@layout@medium\{.*?\\geometry\{([^}]*)\}", cls, re.S).group(1)
    mm = {k: float(v) * (10.0 if unit == "cm" else 1.0)
          for k, v, unit in re.findall(r"(paperwidth|left|right)=([0-9.]+)(mm|cm)", medium)}
    assert PFS.LINE_WIDTH_PT == pytest.approx((mm["paperwidth"] - mm["left"] - mm["right"]) / 25.4 * 72.0)
    gate = io.open(os.path.join(paper, "audit_numbers.py"), encoding="utf-8").read()
    assert float(re.search(r"(?m)^FIGURE_MIN_PRINTED_PT = ([0-9.]+)", gate).group(1)) == PFS.MIN_PRINTED_PT
