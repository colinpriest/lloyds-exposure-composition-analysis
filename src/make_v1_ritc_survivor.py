"""Vignette-1 adverse-tail survivor function: raw vs the size-only transfer vs the square-root benchmark.

Shows the main transfer, the raw donor pool's empirical 99.5% quantile carried to the GBP 500m target by the headline
operator, by overlaying the empirical survivor function P(S > x) on the adverse side for:

  - raw                  : donor severities, untransferred
  - size-only transfer   : the headline operator (gamma = 0, with the RITC rank map for the accepted-liability donors,
                           as transfer_operator applies it), each donor's S * s(target) / s(donor)
  - square-root benchmark: S * sqrt(R_donor / R_target), the simple scaling of check_operator_backtest.py (k = 1/2, no
                           floor, no tail map)

Evaluated at the operator posterior mean on the full donor pool (V1 target R=500, H=0.17), under the paper's headline
size-only transfer operator (the headline fit, gamma fixed at 0 in the likelihood, at its posterior means:
transfer_operator.py); the two-line title names it, and the legend keys the VaR markers.
Writes paper_pack/fig_v1_ritc_survivor.{png,pdf}.

The edit review of 27 October 2026 (item 25): the figure drew the pure rescale (RITC tails carried) and the rank-mapped
pool, two curves that coincide at the cutpoint, and its one callout read "0.342 -> 0.342", the RITC map's zero effect
there. The callout now gives the main transfer, raw -> size-only, with the square-root benchmark's figure, and the
pure-rescale curve gave way to the square-root benchmark; the RITC map's zero effect at the cutpoint is the caption's.
The three figures printed are read from results/check_operator_backtest_results.json (vignette_figures) and the
script stops unless the drawn pools reproduce them exactly.

The VaR99.5 annotation is placed where no plotted curve, marker or the legend crosses it, and
the script refuses to write a figure in which it would be struck through: the published
figure's annotation sat on the transferred curve's vertical step (review of 29 September 2026,
M-16). place_callout() and text_is_clear() are that check, and
src/test_figure_layout.py runs them on the figure built from the committed inputs. The callout has no leader (it
names the squares it reports; see CALLOUT_PREFERRED), and its box must lie inside the axes. place_annotation() and
leader_is_clear(), the leader check (the next review found a leader crossing the raw curve on its way to the de-RITC
one), stay for an annotation with a leader and are tested on toy figures.

Run: python src/make_v1_ritc_survivor.py
"""
import numpy as np
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.path import Path as MplPath
from matplotlib.text import Text
from matplotlib.transforms import Bbox
from pathlib import Path

import paper_figure_style as PFS
import transfer_operator
from vignette_uncertainty import load_pool, load_draws, load_ritc, load_targets, transfer, var_q


def _savefig_retry(fig, path, attempts=8, wait=0.5, **kw):
    """savefig with a short retry: on Windows a file just written beside this one can be
    held briefly by an indexer or scanner, and the open for writing fails with
    [Errno 22]/[Errno 13]; two manifest runs in round 52 died that way at this step."""
    import time
    for attempt in range(attempts):
        try:
            fig.savefig(path, **kw)
            return
        except OSError:
            if attempt == attempts - 1:
                raise
            time.sleep(wait)

SCRIPT_DIR = Path(__file__).resolve().parent.parent

#: candidate places for the VaR99.5 annotation, in axes fractions: a grid over the plot, tried
#: nearest-first from PREFERRED (the empty corner below and left of the transferred curve, beside
#: the 99.5% point it names); the first place where no curve, marker or legend crosses the box
#: or its leader line is used
PREFERRED = (0.17, 0.12)
#: display pixels at the leader's target left uncounted: the leader ends on the curve it points at
LEADER_END_PX = 8.0
ANNOTATION_CANDIDATES = tuple(sorted(
    ((round(x, 2), round(y, 2)) for x in np.arange(0.08, 0.90, 0.03) for y in np.arange(0.05, 0.92, 0.03)),
    key=lambda p: (p[0] - PREFERRED[0]) ** 2 + (p[1] - PREFERRED[1]) ** 2))
#: the callout of the main transfer (27 October 2026) names the three VaR99.5 squares by curve, with no leader: the
#: size-only square sits between the raw curve above, its own steps and the benchmark's step below, and no straight
#: leader from a box with three lines reaches it clear of them. It is placed nearest-first from the empty upper right
#: (the legend now sits below the axes), clear of every curve, marker and the legend
CALLOUT_PREFERRED = (0.75, 0.72)
CALLOUT_CANDIDATES = tuple(sorted(ANNOTATION_CANDIDATES, key=lambda p: (p[0] - CALLOUT_PREFERRED[0]) ** 2
                                  + (p[1] - CALLOUT_PREFERRED[1]) ** 2))


def survivor(x):
    """Distinct positive support values and their full-sample strict survivor P(S > x).

    A strict empirical survivor is right-continuous: tied observations all leave the
    tail at their common value.  The maximum therefore has survival zero, which is
    off the logarithmic axis; its endpoint still completes the preceding step.
    """
    sample = np.asarray(x, dtype=float)
    if sample.ndim != 1 or not np.isfinite(sample).all():
        raise ValueError("survivor expects a finite one-dimensional sample")
    positive = np.unique(sample[sample > 0])
    if not len(positive):
        return positive, np.empty(0, dtype=float)
    ordered = np.sort(sample)
    probabilities = (len(sample) - np.searchsorted(ordered, positive, side="right")) / len(sample)
    return positive, probabilities


def step_vertices(xs, ps):
    """The polyline ax.step(xs, ps, where='post') actually draws, in data coordinates."""
    vx, vy = [], []
    for i in range(len(xs)):
        if i:
            vx.append(xs[i]); vy.append(ps[i - 1])
        vx.append(xs[i]); vy.append(ps[i])
    return np.column_stack([vx, vy])


def text_is_clear(fig, ax, text, obstacles, pad=1.15):
    """True when `text`'s box, padded, is crossed by none of `obstacles`: polylines in data
    coordinates (a curve), or display-coordinate boxes (a marker, the legend)."""
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    # the TEXT's own box: an annotation's get_window_extent also spans its arrow, which is meant to
    # reach the curve it points at
    box = Text.get_window_extent(text, renderer=renderer).expanded(pad, pad)
    if not ax.get_window_extent(renderer).contains(box.x0, box.y0)             or not ax.get_window_extent(renderer).contains(box.x1, box.y1):
        return False                                    # the box must lie inside the axes
    for ob in obstacles:
        if hasattr(ob, "overlaps"):                     # a Bbox in display coordinates
            if box.overlaps(ob):
                return False
            continue
        disp = ax.transData.transform(np.asarray(ob, float))
        if MplPath(disp).intersects_bbox(box, filled=False):
            return False
    return True


def leader_is_clear(fig, ax, text, xy, obstacles):
    """True when the straight leader from `text` to the data point `xy` meets none of `obstacles` (curves in data
    coordinates, boxes in display coordinates) before it lands: the last LEADER_END_PX pixels at the target are left
    uncounted, since the leader ends on the curve and marker it points at."""
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    box = Text.get_window_extent(text, renderer=renderer)
    start = np.array([(box.x0 + box.x1) / 2, (box.y0 + box.y1) / 2])
    end = np.asarray(ax.transData.transform(xy), float)
    length = float(np.hypot(*(end - start)))
    if length <= LEADER_END_PX:
        return True
    leader = MplPath([start, end - (end - start) / length * LEADER_END_PX])
    for ob in obstacles:
        if hasattr(ob, "overlaps"):
            if leader.intersects_bbox(ob, filled=False):
                return False
            continue
        if leader.intersects_path(MplPath(ax.transData.transform(np.asarray(ob, float))), filled=False):
            return False
    return True


def place_annotation(fig, ax, label, xy, obstacles, candidates=ANNOTATION_CANDIDATES):
    """Put `label` at the first candidate where it and its leader to `xy` are clear, or refuse."""
    for cx, cy in candidates:
        t = ax.annotate(label, xy=xy, xytext=(cx, cy), textcoords="axes fraction", xycoords="data",
                        ha="center", va="center", fontsize=PFS.SMALL_PT,
                        bbox=dict(boxstyle="round,pad=0.25", fc="white", ec="#999", lw=0.6),
                        arrowprops=dict(arrowstyle="->", color="#333", lw=0.8,
                                        shrinkA=2, shrinkB=4))
        if text_is_clear(fig, ax, t, obstacles) and leader_is_clear(fig, ax, t, xy, obstacles):
            return t
        t.remove()
    raise SystemExit("make_v1_ritc_survivor: no candidate place for the VaR99.5 annotation is clear of the "
                     "curves, markers and legend; add one to ANNOTATION_CANDIDATES")


def place_callout(fig, ax, label, obstacles, candidates=CALLOUT_CANDIDATES):
    """Put `label`, a text box with no leader, at the first candidate where nothing plotted crosses it, or refuse."""
    for cx, cy in candidates:
        t = ax.text(cx, cy, label, transform=ax.transAxes, ha="center", va="center", fontsize=PFS.SMALL_PT,
                    bbox=dict(boxstyle="round,pad=0.3", fc="white", ec="#999", lw=0.6), zorder=6)
        if text_is_clear(fig, ax, t, obstacles):
            return t
        t.remove()
    raise SystemExit("make_v1_ritc_survivor: no candidate place for the VaR99.5 callout is clear of the curves, "
                     "markers and legend; add one to CALLOUT_CANDIDATES")


def build_figure(raw, transferred, sqrt_r, mode, printed=None, target_gbp_m=None):
    """The figure, with the annotation placed clear of everything plotted; returns (fig, ax, annotation, obstacles).

    `printed` holds the three VaR99.5 figures the annotation prints ({"raw", "transferred", "sqrt"}); main() passes the
    recorded ones after checking the pools reproduce them, and without it they are the pools' own."""
    series = [
        ("Raw (untransferred)", raw, "#6c757d", "-"),
        ("Square-root benchmark", sqrt_r, "#2166ac", "--"),
        ("Size-only transfer (headline)", transferred, "#1b7837", "-"),
    ]
    if printed is None:
        printed = {"raw": var_q(raw, 0.995), "transferred": var_q(transferred, 0.995), "sqrt": var_q(sqrt_r, 0.995)}

    fig, ax = PFS.figure("fig_v1_ritc_survivor", 4.0)   # 3.4 with the legend inside the axes
    curves, marker_pts, plotted_curves = [], [], []
    for label, arr, col, ls in series:
        xs, ps = survivor(arr)
        plotted_curves.extend(ax.step(xs, ps, where="post", color=col, ls=ls, lw=2.0, label=label))
        curves.append(step_vertices(xs, ps))
        for a, mark in ((0.99, "o"), (0.995, "s")):
            v = var_q(arr, a)
            # The empirical strict survivor at VaR need not equal the nominal tail
            # probability, especially when there are ties or a finite donor pool.
            exceedance = float(np.count_nonzero(arr > v) / len(arr))
            if exceedance > 0:  # zero cannot be plotted on the logarithmic axis
                ax.plot(v, exceedance, mark, color=col, ms=5, zorder=5)
                marker_pts.append((v, exceedance))
    # the markers' key, in the legend: it was the title's fourth line (the final review of 14 October 2026, P30)
    for mark, txt in (("o", "VaR 99% (each curve)"), ("s", "VaR 99.5% (each curve)")):
        ax.plot([], [], mark, color="#6c757d", ms=5, label=txt)

    ax.set_yscale("log")
    ax.set_xlim(left=0)
    # Matplotlib sends zero-survival endpoints far below the log axes in its PDF
    # path and clips them only at rendering time. Bound the invisible part of each
    # endpoint at the already selected lower plot limit, preserving the visible
    # step while keeping the exported paths out of the labels and legend.
    ylim = ax.get_ylim()
    for line in plotted_curves:
        line.set_ydata(np.maximum(np.asarray(line.get_ydata(), dtype=float), ylim[0]))
    ax.set_ylim(*ylim)
    # 99 / 99.5 guide lines
    for a, txt in ((0.99, "99%"), (0.995, "99.5%")):
        ax.axhline(1 - a, color="#adb5bd", lw=0.8, ls=":", zorder=0)
        ax.text(ax.get_xlim()[1], 1 - a, f" {txt}", va="center", ha="left", fontsize=PFS.SMALL_PT,
                color="#6c757d")

    # the paper's vocabulary (the rewrite of 27 October 2026): S is the measured movement, and the worked target is
    # named by its size, not as "Vignette 1"
    ax.set_xlabel("Measured movement $S$ (adverse side)")
    ax.set_ylabel("Exceedance probability  $P(S > x)$")
    # two lines: the figure and its operator. The title ran to four lines with the RITC step's reading and the
    # markers' key (the final review of 14 October 2026, P30); the key is in the legend, the annotation gives the
    # step's two figures, and the reading belongs to the caption
    op = ("size-only transfer, $\\gamma=0$" if mode == transfer_operator.SIZE_ONLY
          else "concentration overlay, fitted $\\gamma$")
    if target_gbp_m is None:
        target_gbp_m = float(load_targets()[0][0])
    ax.set_title("£%.0fm target: adverse tail\n(%s)" % (target_gbp_m, op))
    # below the axes (27 October 2026): inside them, upper right, it left no place for the callout's three lines
    legend = ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.17), ncol=2, frameon=False, handlelength=2.6,
                       columnspacing=1.2)
    ax.tick_params(which="both", labelsize=PFS.SMALL_PT)
    PFS.plain_log_ticks(ax)
    ax.grid(True, which="both", alpha=0.2)
    fig.tight_layout()

    # the VaR99.5 annotation, where nothing plotted crosses it
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    marker_boxes = []
    for (mx, my) in marker_pts:
        px, py = ax.transData.transform((mx, my))
        marker_boxes.append(Bbox([[px - 6, py - 6], [px + 6, py + 6]]))
    obstacles = curves + marker_boxes + [legend.get_window_extent(renderer)]
    note = place_callout(fig, ax, annotation_text(printed), obstacles)
    return fig, ax, note, obstacles


def annotation_text(printed):
    """The callout: the main transfer, raw -> size-only, at the 99.5% squares, with the benchmark's figure beneath."""
    return ("VaR 99.5%% (squares):\nraw %.3f $\\to$ size-only %.3f\nsquare-root benchmark %.3f"
            % (printed["raw"], printed["transferred"], printed["sqrt"]))


def pools(mode=transfer_operator.HEADLINE):
    """(raw, size-only transfer, square-root benchmark, RITC flags): the Vignette 1 pools, the transfer under the
    operator `mode` with the RITC rank map applied as transfer_operator applies it (the headline's pool)."""
    S, R, H, synd, year = load_pool()
    draws, ref, hlo, hce = load_draws(mode); cfg = (ref, hlo, hce)    # the operator's own fit
    ritc = load_ritc(synd, year)
    v1, _, _ = load_targets()
    thbar = transfer_operator.params({p: float(draws[p].mean()) for p in draws}, mode)
    transferred = transfer(S, R, H, v1, thbar, cfg, ritc=ritc)        # the operator, rank map included
    sqrt_r = S * np.sqrt(R / v1[0])                                    # check_operator_backtest's sqrt_R rule
    return S, transferred, sqrt_r, ritc


#: the record whose Vignette 1 figures the annotation prints (check_operator_backtest.py's vignette_figures)
RECORD = SCRIPT_DIR / "results" / "check_operator_backtest_results.json"


def recorded_figures(record=RECORD):
    """{raw, transferred, sqrt: {v99, v995}} as results/check_operator_backtest_results.json records them."""
    import io, json
    with io.open(str(record), encoding="utf-8") as fh:
        vf = json.load(fh)["vignette_figures"]
    if vf.get("operator") != transfer_operator.HEADLINE:
        raise SystemExit("make_v1_ritc_survivor: the record's vignette figures are not the headline operator's")
    return {"raw": vf["raw_pool"], "transferred": vf["operator_size_only"]["V1"], "sqrt": vf["sqrt_R"]["V1"]}


def check_against_record(raw, transferred, sqrt_r, rec, tol=1e-12):
    """Stop unless the drawn pools' VaR99 and VaR99.5 are the record's, exactly (to rounding); returns the printed
    VaR99.5 figures, read from the record."""
    drawn = {"raw": raw, "transferred": transferred, "sqrt": sqrt_r}
    off = {(k, lv): (var_q(drawn[k], a), rec[k][lv]) for k in drawn for lv, a in (("v99", 0.99), ("v995", 0.995))
           if abs(var_q(drawn[k], a) - rec[k][lv]) > tol}
    if off:
        raise SystemExit("make_v1_ritc_survivor: the drawn pools do not reproduce %s: %s" % (RECORD.name, off))
    return {k: float(rec[k]["v995"]) for k in drawn}


def main():
    mode = transfer_operator.HEADLINE
    raw, transferred, sqrt_r, ritc = pools(mode)
    printed = check_against_record(raw, transferred, sqrt_r, recorded_figures())
    with PFS.style():                     # drawn at its printed width with 9/8 pt text (paper_figure_style)
        fig, ax, note, obstacles = build_figure(raw, transferred, sqrt_r, mode, printed)
        if not text_is_clear(fig, ax, note, obstacles):
            raise SystemExit("make_v1_ritc_survivor: the VaR99.5 callout is struck by a plotted element")
        out_png = SCRIPT_DIR / "paper_pack" / "fig_v1_ritc_survivor.png"
        _savefig_retry(fig, out_png, dpi=150, bbox_inches="tight")
        _savefig_retry(fig, out_png.with_suffix(".pdf"), bbox_inches="tight", metadata={"CreationDate": None})
    plt.close(fig)

    print(f"operator: {mode} (gamma in force 0)")
    print(f"raw          VaR99/99.5 = {var_q(raw,0.99):.3f} / {var_q(raw,0.995):.3f}")
    print(f"size-only    VaR99/99.5 = {var_q(transferred,0.99):.3f} / {var_q(transferred,0.995):.3f}")
    print(f"square-root  VaR99/99.5 = {var_q(sqrt_r,0.99):.3f} / {var_q(sqrt_r,0.995):.3f}")
    print(f"n_ritc donors rank-mapped = {int(ritc.sum())} of {len(raw)}; figures checked against {RECORD.name}")
    print(f"Wrote {out_png} (+ .pdf)")


if __name__ == "__main__":
    main()
