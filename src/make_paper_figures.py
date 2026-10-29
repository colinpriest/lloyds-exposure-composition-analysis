"""Four paper figures on the working-sample RITC-regime fit (n read from the data).

  fig_corpus_coverage   - by-year active vs corpus vs working sample (+ listed syndicates in the sample, 2020-24)
  fig_size_dispersion   - |S| vs the reserve base R (log-log): the observed vigintile medians of |S| against the
                          posterior-predictive medians of |S| for the same records (with a 90% band), the base scale
                          s(R) as a labelled reference, and the floor; its record,
                          results/size_dispersion_ppc_results.json, holds every plotted bin (the edit review of
                          27 October 2026, item 21: a Student-t scale is not a median of |S|, so the medians are now
                          compared with model-implied medians, like with like)
  fig_hhi_dispersion    - size-standardised |S| vs HHI + fitted concentration curve, from the gamma-free fit
                          (the headline fixes gamma at 0 in the likelihood since option B, 10 October 2026, so
                          the concentration channel is that fit's, the overlay's source; the legend says so)
  fig_goodness_of_fit   - QQ of base-scale residuals z = S / s(R) (the base size scale only: no reporting-year
                          shock and no RITC scale term, so the Student-t line is a reference, not the full model's
                          conditional residual distribution) vs Student-t (clean & RITC),
                          and mean|z| by size / HHI decile (flat = no residual
                          scale pattern across deciles; not a test of tail shape); its record,
                          results/goodness_of_fit_results.json, also holds the clean residuals' tails
                          (clean_tail: the extremes beyond +/-3 and the tail-skew ratio with its
                          by-syndicate cluster-bootstrap interval, Section 4.6)

Each is drawn at the width the manuscript prints it at, with 9 pt labels and 8 pt ticks and legends
(paper_figure_style.py), so its text prints at its drawn size.

Writes paper_pack/<name>.{png,pdf}, results/size_dispersion_ppc_results.json and results/goodness_of_fit_results.json.
Run: python src/make_paper_figures.py
"""
import collections, io, json
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


def _records(d):
    """The working-sample records the figures plot, in the loader's order."""
    return [o for o in d["observations"]
            if o.get("s_raw_a") is not None and o.get("opening_reserves_gbp_m") and o.get("hhi") is not None]


def syndicates():
    """The syndicate of each record load() returns, in the same order (Figure 4's tail record resamples by it)."""
    with io.open(SD / "model" / "exposure_results.json", encoding="utf-8") as _fh:
        d = json.load(_fh)
    return np.array([o["syndicate"] for o in _records(d)], int)


def load():
    with io.open(SD / "model" / "exposure_results.json", encoding="utf-8") as _fh:
        d = json.load(_fh)
    with io.open(SD / "model" / "dispersion_calibration_ritc.json", encoding="utf-8") as _fh:
        cal = json.load(_fh)
    # the concentration figure's fit: the gamma-free calibration (the headline has gamma = 0)
    with io.open(SD / "model" / "dispersion_calibration_ritc_gamma_free.json", encoding="utf-8") as _fh:
        cal_gf = json.load(_fh)
    occ = assumed_business.keys()
    recs = _records(d)
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


def listed_in_sample(yr, syn):
    """{year: (listed syndicates with a working-sample record, listed syndicates, sample records off the list)} for
    the years with an official list of active syndicates (2020-2024). The working sample and the list are not nested
    sets: a sample record whose syndicate is not on its year's list counts in neither of the first two (the fresh
    review of 28 October 2026, finding 3)."""
    out = {}
    for y, listed in market_active.official_lists().items():
        have = {int(s) for s, t in zip(syn, yr) if int(t) == y}
        out[y] = (len(have & listed), len(listed), len(have - listed))
    return out


def coverage_figure(yr, corpus_by_year, syn=None):
    """The coverage figure at its printed width, its legend BELOW the axes: in the plot area it sat over the
    2014-2016 bars (review of 29 September 2026, M-16). Returns (fig, ax, legend).

    The bars are counts. The line is the share of each year's officially listed syndicates that have a working-sample
    record, drawn for 2020-2024 only: the assembled 2014-2019 inputs contain counts but no membership lists, so
    membership cannot be checked from them and sample over active is a ratio of different populations, not coverage."""
    years = list(range(2014, 2025))
    samp = {y: int((yr == y).sum()) for y in years}
    corp = corpus_by_year or samp
    active = market_active.active_by_year()
    act = [active[y] for y in years]; cor = [corp.get(y, 0) for y in years]; sam = [samp[y] for y in years]
    listed = listed_in_sample(yr, syndicates() if syn is None else syn)
    x = np.arange(len(years)); w = 0.27
    with PFS.style():
        fig, ax = PFS.figure("fig_corpus_coverage", 3.5)
        ax.bar(x - w, act, w, label="Active syndicates (market)", color=C_ACT)
        ax.bar(x, cor, w, label="Corpus (extracted, in scope)", color=C_COR)
        ax.bar(x + w, sam, w, label="Working sample", color=C_SAM)
        ax2 = ax.twinx()
        lx = [years.index(y) for y in sorted(listed)]
        cov = [100 * listed[y][0] / listed[y][1] for y in sorted(listed)]
        ax2.plot(lx, cov, "o-", color="#b2182b", lw=1.5, ms=3.5, label="Listed in sample % (2020-24)")
        ax2.set_ylabel("Listed in sample (%)", color="#b2182b"); ax2.set_ylim(0, 100)
        ax2.tick_params(axis="y", colors="#b2182b", labelsize=PFS.SMALL_PT)
        ax.set_xticks(x); ax.set_xticklabels([str(y)[2:] for y in years]); ax.set_ylabel("Syndicate-years")
        ax.set_xlabel("Reporting year (20xx)")
        ax.tick_params(labelsize=PFS.SMALL_PT)
        have = sum(v[0] for v in listed.values()); size = sum(v[1] for v in listed.values())
        ax.set_title(f"Corpus and sample by reporting year\n(2020-24: {have} of {size} listed in the sample)")
        handles = ax.get_legend_handles_labels()[0] + ax2.get_legend_handles_labels()[0]
        labels = ax.get_legend_handles_labels()[1] + ax2.get_legend_handles_labels()[1]
        legend = ax.legend(handles, labels, loc="upper center", bbox_to_anchor=(0.5, -0.24), ncol=2,
                           frameon=False)
        fig.tight_layout()
    return fig, ax, legend


def fig_coverage(yr, corpus_by_year, syn=None):
    fig, ax, legend = coverage_figure(yr, corpus_by_year, syn)
    if not legend_clear_of_bars(fig, ax, legend):
        raise SystemExit("fig_corpus_coverage: the legend overlaps the bars")
    with PFS.style():
        save(fig, "fig_corpus_coverage")


def fig_size(S, R, H, cal, yr, ritc):
    ppc = size_ppc(S, R, yr, ritc, cal)
    with PFS.style():
        fig, ax, legend = size_figure(S, R, H, cal, yr, ritc, ppc=ppc)
        if points_under_legend(fig, ax, legend):
            raise SystemExit("fig_size_dispersion: the legend covers plotted points")
        save(fig, "fig_size_dispersion")
    out = SD / "results" / "size_dispersion_ppc_results.json"
    with io.open(out, "w", encoding="utf-8", newline="") as _fh:
        _fh.write(json.dumps(ppc, indent=2))
    print("wrote results/size_dispersion_ppc_results.json  observed median outside the %d%% band in %d of %d vigintiles"
          % (round(ppc["band_percentiles"][1] - ppc["band_percentiles"][0]), ppc["n_bins_outside_band"],
             len(ppc["bins"])))


#: Figure 2's posterior-predictive check: the headline fit's saved posterior draws, the seed, and the band's percentiles
HEADLINE_DRAWS = SD / "model" / "dispersion_posterior_draws_ritc.npz"
PPC_SEED, PPC_BAND = 20261027, (0.05, 0.95)
N_VIGINTILES = 20


def vigintiles(R):
    """The vigintile of each record's reserve base R (0..19), Figure 2's bins, as the figure has always drawn them."""
    edges = np.percentile(R, np.linspace(0, 100, N_VIGINTILES + 1))
    return np.clip(np.digitize(R, edges) - 1, 0, N_VIGINTILES - 1)


def size_ppc(S, R, yr, ritc, cal, draws_path=HEADLINE_DRAWS, seed=PPC_SEED, band=PPC_BAND):
    """Figure 2's model-implied medians: for each saved posterior draw of the headline fit (gamma = 0), replicate |S| for
    every plotted record and take each vigintile's median, so the observed vigintile median is compared with the same
    statistic of the same records under the model (the edit review of 27 October 2026, item 21).

    A replicate draws S_rep = sigma_it T_nu, with nu = nu_clean or nu_RITC and
    sigma_it = exp(s_t + beta_RITC 1[RITC]) s(R), s(R) = sqrt(sd_undiv^2 + sd_div^2 (R/500)^{2(k-1)}), each parameter at
    the draw's value. The calibration saves neither tau_s's draws nor the fitted reporting-year shocks s_t, so the year
    shock is integrated out as for a new set of years: one s_t ~ N(0, tau_s) per reporting year and draw, shared by that
    year's records, with tau_s at its recorded posterior mean. This is a check of the size law with the year shocks
    integrated out, not conditional on the ten fitted year effects (that would need a refit that saves them)."""
    with np.load(str(draws_path)) as z:
        dr = {key: np.asarray(z[key], float) for key in ("k", "sd_undiv", "sd_div", "nu_clean", "nu_ritc",
                                                          "beta_ritc", "gamma")}
    if np.any(dr["gamma"] != 0) or cal["gamma"] != 0:
        raise SystemExit("Figure 2's check is of the size-only headline (gamma = 0); these draws carry a gamma")
    tau = float(cal["params"]["tau_s"]["mean"])
    S, R = np.asarray(S, float), np.asarray(R, float)
    ritc = np.asarray(ritc, bool)
    years = np.unique(yr)
    yidx = np.searchsorted(years, yr)
    b = vigintiles(R)
    bins = [i for i in range(N_VIGINTILES) if (b == i).sum() > 2]
    rng = np.random.default_rng(seed)
    nd = len(dr["k"])
    logr = np.log(np.maximum(R, 1e-9) / REF)
    reps = np.empty((nd, len(bins)))
    for c0 in range(0, nd, 500):                            # draws in blocks: 500 x n replicates at a time
        sl = slice(c0, min(c0 + 500, nd))
        k, su, sdv = dr["k"][sl, None], dr["sd_undiv"][sl, None], dr["sd_div"][sl, None]
        base = np.sqrt(su ** 2 + sdv ** 2 * np.exp(2.0 * (k - 1.0) * logr[None, :]))
        s_t = rng.normal(0.0, tau, size=(base.shape[0], len(years)))
        sig = np.exp(s_t[:, yidx] + dr["beta_ritc"][sl, None] * ritc[None, :]) * base
        nu = np.where(ritc[None, :], dr["nu_ritc"][sl, None], dr["nu_clean"][sl, None])
        a = np.abs(sig * rng.standard_t(nu))
        for j, i in enumerate(bins):
            reps[sl, j] = np.median(a[:, b == i], axis=1)
    aS = np.abs(S)
    rows = []
    for j, i in enumerate(bins):
        m = b == i
        obs = float(np.median(aS[m]))
        lo, mid, hi = (float(x) for x in np.quantile(reps[:, j], [band[0], 0.5, band[1]]))
        rows.append({"vigintile": int(i + 1), "n": int(m.sum()), "n_ritc": int(ritc[m].sum()),
                     "median_R_gbp_m": float(np.median(R[m])), "observed_median_abs_S": obs,
                     "ppc_median_abs_S": mid, "band_lo": lo, "band_hi": hi,
                     "share_replicates_at_or_above_observed": float((reps[:, j] >= obs).mean()),
                     "observed_outside_band": bool(obs < lo or obs > hi)})
    return {"figure": "paper_pack/fig_size_dispersion.pdf and .png",
            "statistic": "median |S| of the records in each vigintile of the reserve base R: observed, and replicated "
                         "under the headline fit (gamma = 0) for the same records, one replicate per saved posterior "
                         "draw",
            "replicate": "S_rep = exp(s_t + beta_RITC 1[RITC]) s(R) T_nu, s(R) = sqrt(sd_undiv^2 + sd_div^2 "
                         "(R/500)^{2(k-1)}), nu = nu_clean or nu_RITC, each at the draw's value",
            "year_shock": "integrated out: s_t ~ N(0, tau_s) drawn once per reporting year and posterior draw, shared by "
                          "that year's records; tau_s at its recorded posterior mean (the calibration saves neither "
                          "tau_s draws nor the fitted year shocks, so the check is not conditional on them)",
            "tau_s_used": tau,
            "tau_s_rule": "fixed at its recorded posterior mean, %.3f (model/dispersion_calibration_ritc.json, "
                          "params.tau_s.mean): its draws are not saved, so its uncertainty is not propagated" % tau,
            "band_definition": "the %gth to %gth percentile, across the posterior draws, of each vigintile's "
                               "replicated median |S|; the line is the 50th" % (100 * band[0], 100 * band[1]),
            "draws": str(Path(draws_path).relative_to(SD)).replace("\\", "/")
            if Path(draws_path).is_relative_to(SD) else str(draws_path),
            "n_draws": int(nd), "seed": int(seed), "band_percentiles": [100 * band[0], 100 * band[1]],
            "n": int(len(S)), "n_ritc": int(ritc.sum()), "bins": rows,
            "n_bins_outside_band": int(sum(r["observed_outside_band"] for r in rows)),
            "base_scale_reference": "s(R) at the posterior means (sd_undiv %.6g, sd_div %.6g, k %.6g): a clean record "
                                    "with a zero year shock; a Student-t scale, not a median of |S|"
                                    % (cal["sd_undiv"], cal["sd_div"], cal["k"])}


#: Figure 2's vertical axis starts at the decade below this quantile of the nonzero |S|. Left to autoscale it ran to
#: 1e-06 for the four movements below 1e-04 (one at 1.2e-06), four decades the eye reads as empty (the final review of
#: 14 October 2026, P30); the points below the axis are counted in the legend
SIZE_AXIS_QUANTILE = 0.01
#: the drawn heights of Figures 2 and 3, in inches: 3.2 with the legend inside the axes, taller now it sits below them
SIZE_HEIGHT_IN, HHI_HEIGHT_IN = 4.1, 3.55
#: the legends below Figures 2 and 3's axes: where they hang, in axes fractions, and their spacing
LEGEND_BELOW = dict(frameon=False, loc="upper center", bbox_to_anchor=(0.45, -0.17), ncol=2, handlelength=1.6,
                    columnspacing=1.2)


def size_axis_floor(aS, extra=()):
    """Figure 2's lower vertical limit: the decade at or below the SIZE_AXIS_QUANTILE quantile of the nonzero |S| and of
    the other things the axis plots (`extra`: the medians and the fitted curve), so that the decade below the first
    plotted points never reads as empty (test_figure_presentation, which takes the quantile of everything plotted)."""
    v = np.concatenate([aS[aS > 0], np.asarray(extra, float)[np.asarray(extra, float) > 0]])
    return float(10.0 ** np.floor(np.log10(np.quantile(v, SIZE_AXIS_QUANTILE))))


def size_figure(S, R, H, cal, yr, ritc, ppc=None):
    """Figure 2 at its printed width (call inside PFS.style()); returns (fig, ax, legend).

    The observed vigintile medians of |S| are compared with the posterior-predictive medians of |S| for the same records
    (size_ppc: the headline fit's draws, its RITC scale and tails, the year shock integrated out), with the 90% band:
    like with like (the edit review of 27 October 2026, item 21). The figure drew the medians against the fitted
    Student-t scale, which is not a median of |S| and sat above every median. That scale stays as a thin reference
    labelled for what it is: the base scale s(R) of a clean record in a year with a zero shock. The headline has gamma = 0
    in the likelihood (option B, 10 October 2026), so s(R) does not depend on H; a fit with a concentration exponent is
    refused."""
    if cal["gamma"] != 0:
        raise SystemExit("fig_size_dispersion plots the size-only headline (gamma = 0); this fit has gamma = %g"
                         % cal["gamma"])
    if ppc is None:
        ppc = size_ppc(S, R, yr, ritc, cal)
    aS = np.abs(S)
    fig, ax = PFS.figure("fig_size_dispersion", SIZE_HEIGHT_IN)
    ax.scatter(R, aS, s=6, alpha=0.28, color="#4a7ba6", edgecolors="none", label="$|S|$, syndicate-year")
    rows = ppc["bins"]
    b = vigintiles(R)
    bx = [float(np.median(R[b == r["vigintile"] - 1])) for r in rows]
    by = [r["observed_median_abs_S"] for r in rows]
    if [r["median_R_gbp_m"] for r in rows] != bx or by != [float(np.median(aS[b == r["vigintile"] - 1])) for r in rows]:
        raise SystemExit("fig_size_dispersion: the check's bins are not these records' vigintiles")
    pm_, plo, phi = ([r[k] for r in rows] for k in ("ppc_median_abs_S", "band_lo", "band_hi"))
    band = ax.fill_between(bx, plo, phi, color="#e08214", alpha=0.25, lw=0, zorder=1)
    (pline,) = ax.plot(bx, pm_, "-", color="#b35806", lw=1.6, zorder=2)
    ax.plot(bx, by, "s", color="#1b4965", ms=4, zorder=3, label="observed vigintile median")
    # the base scale s(R) of a clean record with a zero year shock (gamma = 0: H does not enter), a reference only
    Rgrid = np.logspace(np.log10(R.min()), np.log10(R.max()), 100)
    curve = sigma(Rgrid, 1.0, cal)
    ax.plot(Rgrid, curve, "--", color="#7f7f7f", lw=1.0, zorder=1,
            label="base scale $s(R)$, clean:\nreference, not a median")
    ax.axhline(cal["sd_undiv"], ls=":", color="#333", lw=1,
               label="undiversifiable floor %.3f" % cal["sd_undiv"])
    ax.set_xscale("log"); ax.set_yscale("log")
    lo = size_axis_floor(aS, list(by) + list(curve) + list(pm_) + list(plo) + list(phi))
    ax.set_ylim(lo, 1.3 * max(float(aS.max()), float(curve.max())))
    n_below = int((aS < lo).sum())
    if n_below:      # a legend entry with no symbol: the count of the points under the axis (|S| = 0 among them)
        ax.plot([], [], " ", label="%d below %g not shown" % (n_below, lo))
    ax.set_xlabel("Reserve base $R$ (£m)"); ax.set_ylabel("Measured movement $|S|$ (absolute)")
    # the title describes the axes and the fitted law, not the floor: the paper holds the floor to be a structural
    # specification, not a measured feature of these points (the review of 2 October 2026, P-27)
    ax.set_title("Size$-$dispersion: vigintile medians of $|S|$,\nobserved and posterior-predictive ($k=%.2f$)"
                 % cal["k"])
    # below the axes: with the axis cropped at 1e-4, every corner inside them covered points (points_under_legend).
    # The posterior-predictive median and its band share one entry, placed after the observed medians
    handles, labels = ax.get_legend_handles_labels()
    at = labels.index("observed vigintile median") + 1
    handles.insert(at, (band, pline))
    labels.insert(at, "posterior-predictive\nmedian, %d%% band" % round(ppc["band_percentiles"][1] - ppc["band_percentiles"][0]))
    legend = ax.legend(handles, labels, **LEGEND_BELOW)
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


def fig_gof(S, R, H, ritc, cal, syn, yr):
    with PFS.style():
        fig, _axes, gof = gof_figure(S, R, H, ritc, cal)
        save(fig, "fig_goodness_of_fit")
    gof["clean_tail"] = clean_tail(S, R, H, ritc, syn, yr, cal)
    out = SD / "results" / "goodness_of_fit_results.json"
    with io.open(out, "w", encoding="utf-8", newline="") as _fh:
        _fh.write(json.dumps(gof, indent=2))
    ct = gof["clean_tail"]
    print(f"wrote results/goodness_of_fit_results.json  size p={gof['size']['kruskal_p']:.3f}"
          f"  hhi p={gof['hhi']['kruskal_p']:.3f}  clean: {ct['above_3']} above +3, {ct['below_3']} below -3;"
          f" tail-skew ratio {ct['tail_skew_ratio']:.3f} [{ct['interval_95'][0]:.3f}, {ct['interval_95'][1]:.3f}]")


#: the tail-skew ratio's by-syndicate cluster bootstrap: resamples and seed (the review of 2 October 2026, P-16; the
#: manuscript's Section 4.6 prints the ratio with this interval, and its claim registry recomputes it with these)
CLEAN_TAIL_RESAMPLES, CLEAN_TAIL_SEED = 4000, 20261006


def tail_skew_ratio(x):
    """(q90 - q50) / (q50 - q10): above one when the upper tail reaches further from the median than the lower."""
    q10, q50, q90 = np.percentile(x, [10, 50, 90])
    return float((q90 - q50) / (q50 - q10))


def clean_tail(S, R, H, ritc, syn, yr, cal, resamples=CLEAN_TAIL_RESAMPLES, seed=CLEAN_TAIL_SEED):
    """Figure 4's clean residuals in the tails (the review of 2 October 2026, P-16): z = S / sigma(R, H) at the
    posterior-mean parameters, the residual panel (a) plots, on the records outside the RITC regime. The counts beyond
    +3 and -3 against the t(nu_clean) expectation per tail, the syndicates and reporting years the extremes come from,
    and the tail-skew ratio with a by-syndicate cluster bootstrap: each resample draws as many syndicates as there are,
    with replacement, and pools every clean residual of each drawn syndicate; the interval is the 2.5th and 97.5th
    percentiles of the resampled ratios. No p-value: the extremes cluster by syndicate and year, so a test treating
    them as independent is not calibrated."""
    z = np.asarray(S, float) / sigma(R, H, cal)
    m = ~np.asarray(ritc, bool)
    zc, sc, yc = z[m], np.asarray(syn)[m], np.asarray(yr)[m]
    up, dn = zc > 3, zc < -3
    ext = up | dn
    by_syn = collections.Counter(int(s) for s in sc[ext]).most_common()
    rng = np.random.default_rng(seed)
    groups = {s: zc[sc == s] for s in np.unique(sc)}
    keys = np.array(list(groups))
    boot = np.empty(resamples)
    for b in range(resamples):
        pick = rng.choice(keys, size=len(keys), replace=True)
        boot[b] = tail_skew_ratio(np.concatenate([groups[k] for k in pick]))
    return {"residual": "base-scale residual z = S / s(R) at the posterior-mean parameters (the base size scale only: "
                        "no reporting-year shock and no RITC scale term), records outside the RITC regime (the "
                        "goodness-of-fit figure, panel (a), clean); the expected count per tail is a unit Student-t "
                        "reference, not the full model's expectation for these residuals",
            "n_clean": int(m.sum()), "nu_clean": float(cal["nu_clean"]),
            "above_3": int(up.sum()), "below_3": int(dn.sum()), "n_extremes": int(ext.sum()),
            "expected_per_tail": float(m.sum() * stats.t.sf(3.0, df=cal["nu_clean"])),
            "n_syndicates_with_extremes": len(by_syn),
            "extremes_by_syndicate": [[s, c] for s, c in by_syn],
            "extremes_by_year": {str(y): int((yc[ext] == y).sum()) for y in sorted(set(yc[ext].tolist()))},
            "tail_skew_ratio": tail_skew_ratio(zc),
            "tail_skew_ratio_definition": "(q90 - q50) / (q50 - q10) of the clean residuals, percentiles by linear "
                                          "interpolation",
            "interval_95": [float(np.percentile(boot, 2.5)), float(np.percentile(boot, 97.5))],
            "bootstrap": {"kind": "by-syndicate cluster bootstrap", "resamples": int(resamples), "seed": int(seed),
                          "n_syndicates": int(len(keys)), "percentiles": [2.5, 97.5]}}


def gof_figure(S, R, H, ritc, cal):
    """The goodness-of-fit figure at its printed width (call inside PFS.style()); returns (fig, axes, the record it
    plots).

    The residual is the base-scale residual z = S / s(R): s(R) = sigma(R, H, cal) at the headline's posterior means with
    gamma = 0, the base size scale only. It carries no reporting-year shock exp(s_t) (the calibration does not save the
    fitted shocks) and no RITC scale exp(beta_RITC). So it diagnoses what size leaves behind, with the market-year
    variation still in it, and the Student-t line is a reference: under the full model a base-scale residual is a scale
    mixture over the year shocks, not exactly a unit t (the edit review of 27 October 2026, item 28). The axis labels
    and the titles say so."""
    if cal["gamma"] != 0:
        raise SystemExit("the goodness-of-fit figure plots the size-only headline's base scale (gamma = 0); this fit "
                         "has gamma = %g" % cal["gamma"])
    z = S / sigma(R, H, cal)
    fig, axes = PFS.figure("fig_goodness_of_fit", 3.6, ncols=2)      # 3.3 with a one-line suptitle
    # (a) QQ vs Student-t
    ax = axes[0]
    for mask, nu, col, lab in [(~ritc, cal["nu_clean"], "#1b7837", "clean"),
                               (ritc, cal["nu_ritc"], "#b2182b", "RITC")]:
        zz = np.sort(z[mask]); n = len(zz)
        q = stats.t.ppf((np.arange(1, n + 1) - 0.5) / n, df=nu)
        ax.plot(q, zz, "o", ms=2, alpha=0.5, color=col, label=f"{lab}, n={n}")
    lim = 8
    # the reference line is named by the title and the horizontal axis: a third legend entry ran over 24 points
    ax.plot([-lim, lim], [-lim, lim], "k-", lw=0.8)
    ax.set_xlim(-lim, lim); ax.set_ylim(-lim, lim)
    ax.set_xlabel("Student-$t$ quantile (reference)"); ax.set_ylabel("base-scale residual $S/s(R)$")
    # the tail indices in the title keep the legend short enough for the empty upper-left corner at the
    # printed width (with them the legend ran over the points and the reference line)
    ax.set_title("QQ vs Student-$t$ reference\n($\\nu$ = %.2f clean, %.2f RITC)" % (cal["nu_clean"], cal["nu_ritc"]))
    ax.legend(frameon=False, loc="upper left"); ax.grid(True, alpha=0.2)
    ax.tick_params(labelsize=PFS.SMALL_PT)
    # (b) mean|z| by size and HHI decile, with the Kruskal-Wallis test the body quotes:
    # does |z| separate across the ten groups? Recorded so the p-values have a source.
    ax = axes[1]
    gof = {"n": int(len(z)), "groups": 10, "statistic": "|z| = |S| / s(R), the base-scale residual: the base size "
           "scale at the posterior-mean two-regime parameters, with no reporting-year shock and no RITC scale term; "
           "equal-count decile groups; Kruskal-Wallis across groups"}
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
    # two lines: on one, the title widened the saved page and its text printed below 8 pt
    fig.suptitle(f"Goodness of fit: base-scale residuals $z=S/s(R)$\n(no year or RITC scale term; n={len(z)})")
    fig.tight_layout(rect=[0, 0, 1, 0.94])
    gof["single_line_H1"] = {"n": int((H >= 1.0 - 1e-9).sum()),
                             "mean_abs_z": float(np.abs(z[H >= 1.0 - 1e-9]).mean()) if (H >= 1.0 - 1e-9).any() else None,
                             "pool_median_abs_z": float(np.median(np.abs(z)))}
    return fig, axes, gof


def main():
    S, R, H, yr, ritc, cal, cal_gf, corpus_by_year = load()
    print(f"n={len(S)}  RITC={int(ritc.sum())}  k={cal['k']:.3f} gamma={cal['gamma']:.3f} "
          f"floor={cal['sd_undiv']:.4f} nu_clean={cal['nu_clean']:.2f} nu_ritc={cal['nu_ritc']:.2f}")
    fig_coverage(yr, corpus_by_year, syndicates())
    fig_size(S, R, H, cal, yr, ritc)
    fig_hhi(S, R, H, cal_gf)              # the concentration channel is the gamma-free fit's (option B)
    fig_gof(S, R, H, ritc, cal, syndicates(), yr)


if __name__ == "__main__":
    main()
