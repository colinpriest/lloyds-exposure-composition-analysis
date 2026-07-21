"""Vignette-1 adverse-tail survivor function: raw vs pure-rescale vs de-RITC.

Shows how the shape-aware (de-RITC) operator lightens the transferred tail relative to the
pure rescale, by overlaying the empirical survivor function P(S > x) on the adverse side for:

  - raw            : donor severities, untransferred
  - pure rescale   : S * sigma(target)/sigma(donor)          (RITC tails carried)
  - de-RITC        : shape-aware operator (RITC tails thinned to the clean regime)

Evaluated at the operator posterior mean on the full donor pool (V1 target R=500, H=0.17).
Writes paper_pack/fig_v1_ritc_survivor.{png,pdf}.

Run: python make_v1_ritc_survivor.py
"""
import numpy as np
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from pathlib import Path

from vignette_uncertainty import load_pool, load_draws, load_ritc, load_targets, transfer, var_q

SCRIPT_DIR = Path(__file__).resolve().parent.parent


def survivor(x):
    """Empirical survivor on the adverse (positive) side: sorted x>0 and P(S>=x)."""
    xp = np.sort(x[x > 0])[::-1]
    n = len(x)
    # exceedance prob over the FULL sample (so levels match VaR quantiles)
    p = (np.arange(1, len(xp) + 1)) / n
    return xp[::-1], p[::-1]


def main():
    S, R, H, synd, year = load_pool()
    draws, ref, hlo, hce = load_draws(); cfg = (ref, hlo, hce)
    ritc = load_ritc(synd, year)
    v1, _, _ = load_targets()
    thbar = {p: float(draws[p].mean()) for p in draws}

    raw = S
    pure = transfer(S, R, H, v1, thbar, cfg, ritc=None)   # no de-RITC
    deritc = transfer(S, R, H, v1, thbar, cfg, ritc=ritc)  # shape-aware

    series = [
        ("Raw (untransferred)", raw, "#6c757d", "-"),
        ("Pure rescale (RITC carried)", pure, "#b2182b", "--"),
        ("De-RITC (shape-aware)", deritc, "#1b7837", "-"),
    ]

    fig, ax = plt.subplots(figsize=(7.2, 5.0))
    for label, arr, col, ls in series:
        xs, ps = survivor(arr)
        ax.step(xs, ps, where="post", color=col, ls=ls, lw=2.0, label=label)
        for a, mark in ((0.99, "o"), (0.995, "s")):
            v = var_q(arr, a)
            ax.plot(v, 1 - a, mark, color=col, ms=7, zorder=5)

    # 99 / 99.5 guide lines
    for a, txt in ((0.99, "99%"), (0.995, "99.5%")):
        ax.axhline(1 - a, color="#adb5bd", lw=0.8, ls=":", zorder=0)
        ax.text(ax.get_xlim()[1], 1 - a, f" {txt}", va="center", ha="left", fontsize=8, color="#6c757d")

    ax.set_yscale("log")
    ax.set_xlim(left=0)
    ax.set_xlabel("Signed PYD ratio $S$ (adverse side)")
    ax.set_ylabel("Exceedance probability  $P(S > x)$")
    ax.set_title("Vignette 1 adverse tail: de-RITC lightens the transferred tail\n"
                 "(markers = VaR$_{99}$ circle, VaR$_{99.5}$ square)", fontsize=10)
    ax.legend(loc="upper right", frameon=False, fontsize=9)
    ax.grid(True, which="both", alpha=0.2)

    # annotate the VaR99.5 gap
    v_pure, v_der = var_q(pure, 0.995), var_q(deritc, 0.995)
    ax.annotate("", xy=(v_der, 1 - 0.995), xytext=(v_pure, 1 - 0.995),
                arrowprops=dict(arrowstyle="<->", color="#333", lw=1.0))
    ax.text((v_pure + v_der) / 2, (1 - 0.995) * 0.62,
            f"VaR$_{{99.5}}$: {v_pure:.3f}$\\to${v_der:.3f}", ha="center", fontsize=8)

    fig.tight_layout()
    out_png = SCRIPT_DIR / "paper_pack" / "fig_v1_ritc_survivor.png"
    fig.savefig(out_png, dpi=150, bbox_inches="tight")
    fig.savefig(out_png.with_suffix(".pdf"), bbox_inches="tight")
    plt.close(fig)

    print(f"raw   VaR99/99.5 = {var_q(raw,0.99):.3f} / {var_q(raw,0.995):.3f}")
    print(f"pure  VaR99/99.5 = {var_q(pure,0.99):.3f} / {var_q(pure,0.995):.3f}")
    print(f"deritc VaR99/99.5 = {var_q(deritc,0.99):.3f} / {var_q(deritc,0.995):.3f}")
    print(f"n_ritc donors carried/thinned = {int(ritc.sum())} of {len(S)}")
    print(f"Wrote {out_png} (+ .pdf)")


if __name__ == "__main__":
    main()
