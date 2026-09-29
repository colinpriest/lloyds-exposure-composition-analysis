#!/usr/bin/env python3
"""Figure layout: nothing printed over the data it labels (review of 29 September 2026, M-16).

Figure 5 (Vignette 1 adverse tail): the VaR99.5 label sat on the curves and markers at the 99.5% level.
Figure 6 (corpus coverage): the legend sat over the 2014-2016 bars. Each script now places its text and
refuses to write a figure where it is struck; these tests run those checks on the committed inputs, show
that each check sees the placement it replaced, and exercise the checks on figures built to fail.

Run:  python -m pytest src/test_figure_layout.py -q
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt   # noqa: E402
import numpy as np                # noqa: E402
import pytest                     # noqa: E402

import make_paper_figures as MPF          # noqa: E402
import make_v1_ritc_survivor as SURV      # noqa: E402
import transfer_operator as TO            # noqa: E402
from vignette_uncertainty import var_q    # noqa: E402


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
