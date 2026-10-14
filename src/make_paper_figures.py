"""Four paper figures on the working-sample RITC-regime fit (n read from the data).

  fig_corpus_coverage   - by-year active vs corpus vs working sample (+ coverage %)
  fig_size_dispersion   - |S| vs opening reserves (log-log) + the headline's fitted sigma(R) curve (gamma = 0) & floor
  fig_hhi_dispersion    - size-standardised |S| vs HHI + fitted concentration curve, from the gamma-free fit
                          (the headline fixes gamma at 0 in the likelihood since option B, 10 October 2026, so
                          the concentration channel is that fit's, the overlay's source; the legend says so)
  fig_goodness_of_fit   - QQ of standardised residuals vs Student-t (clean & RITC),
                          and mean|z| by size / HHI decile (flat = no residual
                          scale pattern across deciles; not a test of tail shape)

Each is drawn at the width the manuscript prints it at, with 9 pt labels and 8 pt ticks and legends
(paper_figure_style.py), so its text prints at its drawn size.

Writes paper_pack/<name>.{png,pdf}. Run: python src/make_paper_figures.py
"""
import io, json
from pathlib import Path
import numpy as np
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from scipy import stats
import assumed_business
import market_active
import paper_figure_style as PFS


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

SD = Path(__file__).resolve().parent.parent
PP = SD / "paper_pack"
REF, HLO, HCE = 500.0, 0.01, 1.0
C_ACT, C_COR, C_SAM = "#adb5bd", "#4a7ba6", "#1b4965"

# by-year active syndicates (2014-2019 Lloyd's reports/register; 2020-2024 official lists): read from
# market_active.py. The typed copy here kept 97/91/92/94/94 for 2020-2024, the list without Syndicate 33.


def load():
    d = json.load(io.open(SD / "model" / "exposure_results.json", encoding="utf-8"))
    cal = json.load(io.open(SD / "model" / "dispersion_calibration_ritc.json", encoding="utf-8"))
    # the concentration figure's fit: the gamma-free calibration (the headline has gamma = 0)
    cal_gf = json.load(io.open(SD / "model" / "dispersion_calibration_ritc_gamma_free.json", encoding="utf-8"))
    occ = assumed_business.keys()
    recs = [o for o in d["observations"]
            if o.get("s_raw_a") is not None and o.get("opening_reserves_gbp_m") and o.get("hhi") is not None]
    S = np.array([o["s_raw_a"] for o in recs], float)
    R = np.array([o["opening_reserves_gbp_m"] for o in recs], float)
    H = np.clip(np.array([o["hhi"] for o in recs], float), HLO, HCE)
    yr = np.array([o["year"] for o in recs], int)
    ritc = np.array([f"{o['syndicate']}_{o['year']}" in occ for o in recs])
    corpus_by_year = {int(y): int(c) for y, c in d["meta"]["yearly_observations"].items()} \
        if "yearly_observations" in d.get("meta", {}) else None
    return S, R, H, yr, ritc, cal, cal_gf, corpus_by_year


def sigma(R, H, cal):
    reff = (np.maximum(R, 1e-9) / REF) * (1.0 / np.clip(H, HLO, HCE)) ** cal["gamma"]
    return np.sqrt(cal["sd_undiv"] ** 2 + cal["sd_div"] ** 2 * reff ** (2.0 * (cal["k"] - 1.0)))


def save(fig, name):
    _savefig_retry(fig, PP / f"{name}.png", dpi=150, bbox_inches="tight")
    _savefig_retry(fig, PP / f"{name}.pdf", bbox_inches="tight", metadata={"CreationDate": None})
    plt.close(fig); print(f"wrote paper_pack/{name}.png (+pdf)")


def legend_clear_of_bars(fig, ax, legend):
    """True when no bar of `ax` overlaps the legend's box (display coordinates)."""
    fig.canvas.draw()
    box = legend.get_window_extent(fig.canvas.get_renderer())
    return not any(box.overlaps(p.get_window_extent()) for p in ax.patches)


def points_under_legend(fig, ax, legend):
    """How many plotted points of `ax` (scatter offsets, and the vertices of marker-only lines) the legend's box
    covers, in display coordinates (a point outside the view limits is not drawn and not counted). The committed
    Figure 3's legend, inside the axes upper right, covered 18 points; with Figure 2's axis cropped at 1e-4 no corner
    inside its axes was clear at the former 3.2-inch height, 6 points at best (the checks of 15 October 2026). Both
    legends now sit below their axes."""
    fig.canvas.draw()
    box = legend.get_window_extent(fig.canvas.get_renderer())
    pts = [np.asarray(c.get_offsets(), float) for c in ax.collections if len(c.get_offsets())]
    pts += [np.column_stack([ln.get_xdata(), ln.get_ydata()]).astype(float) for ln in ax.lines
            if ln.get_linestyle() in ("None", "none", " ", "") and len(ln.get_xdata())]
    if not pts:
        return 0
    with np.errstate(divide="ignore", invalid="ignore"):      # |S| = 0 on a log axis: not drawn, not counted
        disp = ax.transData.transform(np.vstack(pts))
    a = ax.bbox                                               # a point outside the view limits is not drawn
    drawn = np.isfinite(disp).all(axis=1) & (disp[:, 0] >= a.x0) & (disp[:, 0] <= a.x1) & (disp[:, 1] >= a.y0) \
        & (disp[:, 1] <= a.y1)
    return int((drawn & (disp[:, 0] >= box.x0) & (disp[:, 0] <= box.x1) & (disp[:, 1] >= box.y0)
                & (disp[:, 1] <= box.y1)).sum())


def coverage_figure(yr, corpus_by_year):
    """The coverage figure at its printed width, its legend BELOW the axes: in the plot area it sat over the
    2014-2016 bars (review of 29 September 2026, M-16). Returns (fig, ax, legend)."""
    years = list(range(2014, 2025))
    samp = {y: int((yr == y).sum()) for y in years}
    corp = corpus_by_year or samp
    active = market_active.active_by_year()
    act = [active[y] for y in years]; cor = [corp.get(y, 0) for y in years]; sam = [samp[y] for y in years]
    x = np.arange(len(years)); w = 0.27
    with PFS.style():
        fig, ax = PFS.figure("fig_corpus_coverage", 3.5)
        ax.bar(x - w, act, w, label="Active syndicates (market)", color=C_ACT)
        ax.bar(x, cor, w, label="Corpus (extracted, in scope)", color=C_COR)
        ax.bar(x + w, sam, w, label="Working sample", color=C_SAM)
        ax2 = ax.twinx()
        cov = [100 * s / a for s, a in zip(sam, act)]
        ax2.plot(x, cov, "o-", color="#b2182b", lw=1.5, ms=3.5, label="Sample coverage %")
        ax2.set_ylabel("Sample coverage (%)", color="#b2182b"); ax2.set_ylim(0, 100)
        ax2.tick_params(axis="y", colors="#b2182b", labelsize=PFS.SMALL_PT)
        ax.set_xticks(x); ax.set_xticklabels([str(y)[2:] for y in years]); ax.set_ylabel("Syndicate-years")
        ax.set_xlabel("Reporting year (20xx)")
        ax.tick_params(labelsize=PFS.SMALL_PT)
        ax.set_title(f"Corpus coverage by reporting year\n(n={sum(sam)} sample, {sum(cor)} corpus; "
                     f"overall {100*sum(sam)/sum(act):.0f}%)")
        handles = ax.get_legend_handles_labels()[0] + ax2.get_legend_handles_labels()[0]
        labels = ax.get_legend_handles_labels()[1] + ax2.get_legend_handles_labels()[1]
        legend = ax.legend(handles, labels, loc="upper center", bbox_to_anchor=(0.5, -0.24), ncol=2,
                           frameon=False)
        fig.tight_layout()
    return fig, ax, legend


def fig_coverage(yr, corpus_by_year):
    fig, ax, legend = coverage_figure(yr, corpus_by_year)
    if not legend_clear_of_bars(fig, ax, legend):
        raise SystemExit("fig_corpus_coverage: the legend overlaps the bars")
    with PFS.style():
        save(fig, "fig_corpus_coverage")


def fig_size(S, R, H, cal):
    with PFS.style():
        fig, ax, legend = size_figure(S, R, H, cal)
        if points_under_legend(fig, ax, legend):
            raise SystemExit("fig_size_dispersion: the legend covers plotted points")
        save(fig, "fig_size_dispersion")


#: Figure 2's vertical axis starts at the decade below this quantile of the nonzero |S|. Left to autoscale it ran to
#: 1e-06 for the four movements below 1e-04 (one at 1.2e-06), four decades the eye reads as empty (the final review of
#: 14 October 2026, P30); the points below the axis are counted in the legend
SIZE_AXIS_QUANTILE = 0.01
#: the drawn heights of Figures 2 and 3, in inches: 3.2 with the legend inside the axes, taller now it sits below them
SIZE_HEIGHT_IN, HHI_HEIGHT_IN = 3.75, 3.55
#: the legends below Figures 2 and 3's axes: where they hang, in axes fractions, and their spacing
LEGEND_BELOW = dict(frameon=False, loc="upper center", bbox_to_anchor=(0.45, -0.17), ncol=2, handlelength=1.6,
                    columnspacing=1.2)


def size_axis_floor(aS):
    """Figure 2's lower vertical limit: the decade at or below the SIZE_AXIS_QUANTILE quantile of the nonzero |S|."""
    return float(10.0 ** np.floor(np.log10(np.quantile(aS[aS > 0], SIZE_AXIS_QUANTILE))))


def size_figure(S, R, H, cal):
    """Figure 2 at its printed width (call inside PFS.style()); returns (fig, ax, legend).

    It plots the headline's scale law, which since option B (10 October 2026) has gamma = 0 in the likelihood, so the
    curve is sigma(R) and the legend says so: it read sigma(R, H-bar), a size-and-concentration law the headline does
    not have (the final review of 14 October 2026, P30). A fit with a concentration exponent is refused."""
    if cal["gamma"] != 0:
        raise SystemExit("fig_size_dispersion plots the size-only headline (gamma = 0); this fit has gamma = %g"
                         % cal["gamma"])
    aS = np.abs(S)
    fig, ax = PFS.figure("fig_size_dispersion", SIZE_HEIGHT_IN)
    ax.scatter(R, aS, s=6, alpha=0.28, color="#4a7ba6", edgecolors="none", label="$|S|$, syndicate-year")
    # vigintile bin means
    edges = np.percentile(R, np.linspace(0, 100, 21)); b = np.clip(np.digitize(R, edges) - 1, 0, 19)
    bx = [np.median(R[b == i]) for i in range(20) if (b == i).sum() > 2]
    by = [np.median(aS[b == i]) for i in range(20) if (b == i).sum() > 2]
    ax.plot(bx, by, "s", color="#1b4965", ms=4, label="vigintile median")
    # the fitted sigma(R) (gamma = 0: H does not enter), and the floor
    Rgrid = np.logspace(np.log10(R.min()), np.log10(R.max()), 100)
    curve = sigma(Rgrid, 1.0, cal)
    ax.plot(Rgrid, curve, "-", color="#b2182b", lw=2, label=r"fitted $\sigma(R)$, size-only")
    ax.axhline(cal["sd_undiv"], ls="--", color="#333", lw=1,
               label="undiversifiable floor %.3f" % cal["sd_undiv"])
    ax.set_xscale("log"); ax.set_yscale("log")
    lo = size_axis_floor(aS)
    ax.set_ylim(lo, 1.3 * max(float(aS.max()), float(curve.max())))
    n_below = int((aS < lo).sum())
    if n_below:      # a legend entry with no symbol: the count of the points under the axis (|S| = 0 among them)
        ax.plot([], [], " ", label="%d below %g not shown" % (n_below, lo))
    ax.set_xlabel("Opening reserves $R$ (£m)"); ax.set_ylabel("Severity $|S|$ (absolute PYD ratio)")
    # the title describes the axes and the fitted law, not the floor: the paper holds the floor to be a structural
    # specification, not a measured feature of these points (the review of 2 October 2026, P-27)
    ax.set_title("Size$-$dispersion: $|S|$ against opening reserves\nand the fitted scale ($k=%.2f$)" % cal["k"])
    # below the axes: with the axis cropped at 1e-4, every corner inside them covered points (points_under_legend)
    legend = ax.legend(**LEGEND_BELOW)
    ax.grid(True, which="both", alpha=0.2)
    ax.tick_params(which="both", labelsize=PFS.SMALL_PT)
    PFS.plain_log_ticks(ax)
    fig.tight_layout()
    return fig, ax, legend


def fig_hhi(S, R, H, cal):
    with PFS.style():
        fig, ax, legend = hhi_figure(S, R, H, cal)
        if points_under_legend(fig, ax, legend):
            raise SystemExit("fig_hhi_dispersion: the legend covers plotted points")
        save(fig, "fig_hhi_dispersion")


def hhi_figure(S, R, H, cal):
    """Figure 3 at its printed width, from the gamma-free fit (call inside PFS.style()); returns (fig, ax, legend).

    The fitted curve's legend entry names its fit, the gamma-free one, and its gamma: the caption had to say "which the
    legend calls the gamma-free fit" while the legend said nothing of the kind (the final review of 14 October 2026,
    P30)."""
    # size-standardise: divide |S| by sigma(R, H=1) so only the concentration channel remains
    z_size = np.abs(S) / sigma(R, 1.0, cal)
    fig, ax = PFS.figure("fig_hhi_dispersion", HHI_HEIGHT_IN)
    ax.scatter(H, z_size, s=6, alpha=0.28, color="#5a8a5a", edgecolors="none",
               label="size-standardised $|S|$")
    edges = np.percentile(H, np.linspace(0, 100, 11)); b = np.clip(np.digitize(H, edges) - 1, 0, 9)
    bx = [np.median(H[b == i]) for i in range(10) if (b == i).sum() > 2]
    by = [np.median(z_size[b == i]) for i in range(10) if (b == i).sum() > 2]
    ax.plot(bx, by, "s", color="#1b4965", ms=4, label="decile median")
    Hgrid = np.linspace(max(H.min(), 0.05), H.max(), 100)
    # the fitted curve is a scale ratio (~1); the plotted points are median |S|/sigma
    # (~median|z| ~ 0.67), so anchor the curve to the data's median level. This
    # standardisation identifies the concentration *slope*, not its level.
    ratio_grid = sigma(REF, Hgrid, cal) / sigma(REF, 1.0, cal)
    ratio_obs = sigma(REF, H, cal) / sigma(REF, 1.0, cal)
    anchor = np.median(z_size) / np.median(ratio_obs)
    ax.plot(Hgrid, anchor * ratio_grid, "-", color="#b2182b", lw=2,
            label="fitted concentration slope, $\\gamma$-free fit\n($\\gamma=%.2f$; scaled to the median)"
            % cal["gamma"])
    ax.set_xlabel("HHI (higher = more concentrated)")
    ax.set_ylabel(r"$|S|\,/\,\sigma(R,H{=}1)$")
    # crop the y-axis so the near-flat concentration slope is legible; a few
    # heavy-tail outliers run to ~25 and are noted in the title rather than shown (inside the axes the
    # note collided with the legend at the printed width)
    ax.set_ylim(0, 3)
    n_above = int((z_size > 3).sum())
    # two lines at most: the fit and its gamma are named in the legend, beside the curve they label
    ax.set_title("Concentration$-$dispersion, size removed%s"
                 % (("\n(%d points above 3 not shown)" % n_above) if n_above else ""))
    # below the axes: inside them, upper right, it covered 18 points (points_under_legend)
    legend = ax.legend(**LEGEND_BELOW)
    ax.grid(True, alpha=0.2)
    ax.tick_params(labelsize=PFS.SMALL_PT)
    fig.tight_layout()
    return fig, ax, legend


def fig_gof(S, R, H, ritc, cal):
    with PFS.style():
        fig, _axes, gof = gof_figure(S, R, H, ritc, cal)
        save(fig, "fig_goodness_of_fit")
    out = SD / "results" / "goodness_of_fit_results.json"
    io.open(out, "w", encoding="utf-8").write(json.dumps(gof, indent=2))
    print(f"wrote results/goodness_of_fit_results.json  size p={gof['size']['kruskal_p']:.3f}"
          f"  hhi p={gof['hhi']['kruskal_p']:.3f}")


def gof_figure(S, R, H, ritc, cal):
    """Figure 4 at its printed width (call inside PFS.style()); returns (fig, axes, the record it plots)."""
    z = S / sigma(R, H, cal)
    fig, axes = PFS.figure("fig_goodness_of_fit", 3.3, ncols=2)
    # (a) QQ vs Student-t
    ax = axes[0]
    for mask, nu, col, lab in [(~ritc, cal["nu_clean"], "#1b7837", "clean"),
                               (ritc, cal["nu_ritc"], "#b2182b", "RITC")]:
        zz = np.sort(z[mask]); n = len(zz)
        q = stats.t.ppf((np.arange(1, n + 1) - 0.5) / n, df=nu)
        ax.plot(q, zz, "o", ms=2, alpha=0.5, color=col, label=f"{lab}, n={n}")
    lim = 8
    ax.plot([-lim, lim], [-lim, lim], "k-", lw=0.8)
    ax.set_xlim(-lim, lim); ax.set_ylim(-lim, lim)
    ax.set_xlabel("Student-$t$ quantile"); ax.set_ylabel("residual $z=S/\\sigma$")
    # the tail indices in the title keep the legend short enough for the empty upper-left corner at the
    # printed width (with them the legend ran over the points and the reference line)
    ax.set_title("QQ vs Student-$t$\n($\\nu$ = %.2f clean, %.2f RITC)" % (cal["nu_clean"], cal["nu_ritc"]))
    ax.legend(frameon=False, loc="upper left"); ax.grid(True, alpha=0.2)
    ax.tick_params(labelsize=PFS.SMALL_PT)
    # (b) mean|z| by size and HHI decile, with the Kruskal-Wallis test the body quotes:
    # does |z| separate across the ten groups? Recorded so the p-values have a source.
    ax = axes[1]
    gof = {"n": int(len(z)), "groups": 10, "statistic": "|z| = |S| / sigma(R, H) at the posterior-mean"
           " two-regime parameters; equal-count decile groups; Kruskal-Wallis across groups"}
    for arr, col, lab, key in [(R, "#4a7ba6", "size decile", "size"), (H, "#5a8a5a", "HHI decile", "hhi")]:
        edges = np.percentile(arr, np.linspace(0, 100, 11)); b = np.clip(np.digitize(arr, edges) - 1, 0, 9)
        groups = [np.abs(z[b == i]) for i in range(10)]
        med = [float(np.median(g)) for g in groups]
        kw = stats.kruskal(*groups)
        gof[key] = {"median_abs_z_by_decile": med, "mean_abs_z_by_decile": [float(g.mean()) for g in groups],
                    "n_by_decile": [int(len(g)) for g in groups],
                    "kruskal_H": float(kw.statistic), "kruskal_p": float(kw.pvalue)}
        ax.plot(range(1, 11), med, "o-", color=col, lw=1.5, label=lab)
    ax.axhline(np.median(np.abs(z)), ls="--", color="#333", lw=1, label="overall median |z|")
    ax.set_xlabel("decile"); ax.set_ylabel("median |z| within bin")
    # the title names what the panel shows and claims nothing about it: median |z| by size decile ranges from about
    # 0.54 to 0.96 in the record this file writes (results/goodness_of_fit_results.json, before the 13 October 2026
    # refit), so the earlier title's "flat" was a claim the panel does not support
    ax.set_title("Median |z| by size\nand HHI decile")
    ax.set_ylim(0, 1.6 * max(ax.get_ylim()[1], 1e-9))
    ax.legend(frameon=False, loc="upper center", ncol=1); ax.grid(True, alpha=0.2)
    ax.tick_params(labelsize=PFS.SMALL_PT)
    fig.suptitle(f"Goodness of fit: standardised residuals (n={len(z)})")
    fig.tight_layout(rect=[0, 0, 1, 0.97])
    gof["single_line_H1"] = {"n": int((H >= 1.0 - 1e-9).sum()),
                             "mean_abs_z": float(np.abs(z[H >= 1.0 - 1e-9]).mean()) if (H >= 1.0 - 1e-9).any() else None,
                             "pool_median_abs_z": float(np.median(np.abs(z)))}
    return fig, axes, gof


def main():
    S, R, H, yr, ritc, cal, cal_gf, corpus_by_year = load()
    print(f"n={len(S)}  RITC={int(ritc.sum())}  k={cal['k']:.3f} gamma={cal['gamma']:.3f} "
          f"floor={cal['sd_undiv']:.4f} nu_clean={cal['nu_clean']:.2f} nu_ritc={cal['nu_ritc']:.2f}")
    fig_coverage(yr, corpus_by_year)
    fig_size(S, R, H, cal)
    fig_hhi(S, R, H, cal_gf)              # the concentration channel is the gamma-free fit's (option B)
    fig_gof(S, R, H, ritc, cal)


if __name__ == "__main__":
    main()
