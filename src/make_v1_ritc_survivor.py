"""Vignette-1 adverse-tail survivor function: raw vs pure-rescale vs de-RITC.

Shows how the shape-aware (de-RITC) operator lightens the transferred tail relative to the
pure rescale, by overlaying the empirical survivor function P(S > x) on the adverse side for:

  - raw            : donor severities, untransferred
  - pure rescale   : S * sigma(target)/sigma(donor)          (RITC tails carried)
  - de-RITC        : shape-aware operator (RITC tails re-mapped to the clean regime)

Evaluated at the operator posterior mean on the full donor pool (V1 target R=500, H=0.17),
under the paper's headline size-only transfer operator (gamma zeroed in the posterior means,
not a refit: transfer_operator.py); the title names it.
Writes paper_pack/fig_v1_ritc_survivor.{png,pdf}.

The VaR99.5 annotation is placed where no plotted curve, marker or the legend crosses it, and
the script refuses to write a figure in which it would be struck through: the published
figure's annotation sat on the transferred curve's vertical step (review of 29 September 2026,
M-16). place_annotation() and text_is_clear() are that check, and
src/test_figure_layout.py runs them on the figure built from the committed inputs.

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
#: nearest-first from PREFERRED (the empty band between the transferred and the raw tails at
#: the 99.5% level); the first place no curve, marker or legend crosses is used
PREFERRED = (0.58, 0.10)
ANNOTATION_CANDIDATES = tuple(sorted(
    ((round(x, 2), round(y, 2)) for x in np.arange(0.20, 0.86, 0.04) for y in np.arange(0.06, 0.92, 0.04)),
    key=lambda p: (p[0] - PREFERRED[0]) ** 2 + (p[1] - PREFERRED[1]) ** 2))


def survivor(x):
    """Empirical survivor on the adverse (positive) side: sorted x>0 and P(S>=x)."""
    xp = np.sort(x[x > 0])[::-1]
    n = len(x)
    # exceedance prob over the FULL sample (so levels match VaR quantiles)
    p = (np.arange(1, len(xp) + 1)) / n
    return xp[::-1], p[::-1]


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
    for ob in obstacles:
        if hasattr(ob, "overlaps"):                     # a Bbox in display coordinates
            if box.overlaps(ob):
                return False
            continue
        disp = ax.transData.transform(np.asarray(ob, float))
        if MplPath(disp).intersects_bbox(box, filled=False):
            return False
    return True


def place_annotation(fig, ax, label, xy, obstacles, candidates=ANNOTATION_CANDIDATES):
    """Put `label` at the first candidate where it is clear, with an arrow to `xy`, or refuse."""
    for cx, cy in candidates:
        t = ax.annotate(label, xy=xy, xytext=(cx, cy), textcoords="axes fraction", xycoords="data",
                        ha="center", va="center", fontsize=PFS.SMALL_PT,
                        bbox=dict(boxstyle="round,pad=0.25", fc="white", ec="#999", lw=0.6),
                        arrowprops=dict(arrowstyle="->", color="#333", lw=0.8,
                                        shrinkA=2, shrinkB=4))
        if text_is_clear(fig, ax, t, obstacles):
            return t
        t.remove()
    raise SystemExit("make_v1_ritc_survivor: no candidate place for the VaR99.5 annotation is clear of the "
                     "curves, markers and legend; add one to ANNOTATION_CANDIDATES")


def build_figure(raw, pure, deritc, mode):
    """The figure, with the annotation placed clear of everything plotted; returns (fig, ax, annotation)."""
    series = [
        ("Raw (untransferred)", raw, "#6c757d", "-"),
        ("Pure rescale (RITC carried)", pure, "#b2182b", "--"),
        ("De-RITC (shape-aware)", deritc, "#1b7837", "-"),
    ]

    fig, ax = PFS.figure("fig_v1_ritc_survivor", 3.7)
    curves, marker_pts = [], []
    for label, arr, col, ls in series:
        xs, ps = survivor(arr)
        ax.step(xs, ps, where="post", color=col, ls=ls, lw=2.0, label=label)
        curves.append(step_vertices(xs, ps))
        for a, mark in ((0.99, "o"), (0.995, "s")):
            v = var_q(arr, a)
            ax.plot(v, 1 - a, mark, color=col, ms=5, zorder=5)
            marker_pts.append((v, 1 - a))

    ax.set_yscale("log")
    ax.set_xlim(left=0)
    # 99 / 99.5 guide lines
    for a, txt in ((0.99, "99%"), (0.995, "99.5%")):
        ax.axhline(1 - a, color="#adb5bd", lw=0.8, ls=":", zorder=0)
        ax.text(ax.get_xlim()[1], 1 - a, f" {txt}", va="center", ha="left", fontsize=PFS.SMALL_PT,
                color="#6c757d")

    ax.set_xlabel("Signed PYD ratio $S$ (adverse side)")
    ax.set_ylabel("Exceedance probability  $P(S > x)$")
    # the title states what the figure shows: the RITC step at the 99.5% point can be
    # zero when no flagged donor reaches that level (round 54)
    step = var_q(pure, 0.995) - var_q(deritc, 0.995)
    headline = ("de-RITC lightens the transferred tail" if step > 5e-4
                else "de-RITC leaves the 99.5% point unchanged\n(no flagged donor at that level)")
    op = ("size-only operator, $\\gamma=0$" if mode == transfer_operator.SIZE_ONLY
          else "concentration overlay, fitted $\\gamma$")
    ax.set_title("Vignette 1 adverse tail (%s):\n%s\n"
                 "(markers: VaR 99%% circle, VaR 99.5%% square)" % (op, headline))
    legend = ax.legend(loc="upper right", frameon=False)
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
    v_pure, v_der = var_q(pure, 0.995), var_q(deritc, 0.995)
    note = place_annotation(fig, ax, f"VaR 99.5%: {v_pure:.3f}$\\to${v_der:.3f}",
                            (v_der, 1 - 0.995), obstacles)
    return fig, ax, note, obstacles


def pools(mode=transfer_operator.HEADLINE):
    """(raw, pure rescale, de-RITC) Vignette 1 pools under the transfer operator `mode`."""
    S, R, H, synd, year = load_pool()
    draws, ref, hlo, hce = load_draws(); cfg = (ref, hlo, hce)
    ritc = load_ritc(synd, year)
    v1, _, _ = load_targets()
    thbar = transfer_operator.params({p: float(draws[p].mean()) for p in draws}, mode)
    pure = transfer(S, R, H, v1, thbar, cfg, ritc=None)   # no de-RITC
    deritc = transfer(S, R, H, v1, thbar, cfg, ritc=ritc)  # shape-aware
    return S, pure, deritc, ritc


def main():
    mode = transfer_operator.HEADLINE
    raw, pure, deritc, ritc = pools(mode)
    with PFS.style():                     # drawn at its printed width with 9/8 pt text (paper_figure_style)
        fig, ax, note, obstacles = build_figure(raw, pure, deritc, mode)
        if not text_is_clear(fig, ax, note, obstacles):
            raise SystemExit("make_v1_ritc_survivor: the VaR99.5 annotation is struck by a plotted element")
        out_png = SCRIPT_DIR / "paper_pack" / "fig_v1_ritc_survivor.png"
        _savefig_retry(fig, out_png, dpi=150, bbox_inches="tight")
        _savefig_retry(fig, out_png.with_suffix(".pdf"), bbox_inches="tight", metadata={"CreationDate": None})
    plt.close(fig)

    print(f"operator: {mode} (gamma in force 0)")
    print(f"raw   VaR99/99.5 = {var_q(raw,0.99):.3f} / {var_q(raw,0.995):.3f}")
    print(f"pure  VaR99/99.5 = {var_q(pure,0.99):.3f} / {var_q(pure,0.995):.3f}")
    print(f"deritc VaR99/99.5 = {var_q(deritc,0.99):.3f} / {var_q(deritc,0.995):.3f}")
    print(f"n_ritc donors re-mapped = {int(ritc.sum())} of {len(raw)}")
    print(f"Wrote {out_png} (+ .pdf)")


if __name__ == "__main__":
    main()
