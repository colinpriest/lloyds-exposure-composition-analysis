"""Four paper figures on the n=790 / RITC-regime fit.

  fig_corpus_coverage   - by-year active vs corpus vs working sample (+ coverage %)
  fig_size_dispersion   - |S| vs opening reserves (log-log) + fitted sigma(R) curve & floor
  fig_hhi_dispersion    - size-standardised |S| vs HHI + fitted concentration curve
  fig_goodness_of_fit   - QQ of standardised residuals vs Student-t (clean & RITC),
                          and mean|z| by size / HHI decile (flat = shape-adequate)

Writes paper_pack/<name>.{png,pdf}. Run: python src/make_paper_figures.py
"""
import io, json
from pathlib import Path
import numpy as np
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from scipy import stats

SD = Path(__file__).resolve().parent.parent
PP = SD / "paper_pack"
REF, HLO, HCE = 500.0, 0.01, 1.0
C_ACT, C_COR, C_SAM = "#adb5bd", "#4a7ba6", "#1b4965"

# by-year active syndicates (2014-2019 Lloyd's reports/register; 2020-2024 official lists)
ACTIVE = {2014: 92, 2015: 94, 2016: 99, 2017: 95, 2018: 99, 2019: 93,
          2020: 97, 2021: 91, 2022: 92, 2023: 94, 2024: 94}


def load():
    d = json.load(io.open(SD / "model" / "exposure_results.json", encoding="utf-8"))
    cal = json.load(io.open(SD / "model" / "dispersion_calibration_ritc.json", encoding="utf-8"))
    rs = json.load(io.open(SD / "pdf_extraction" / "ritc_scan.json", encoding="utf-8"))
    occ = {k for k, v in rs.items() if v.get("ritc_occurred")}
    recs = [o for o in d["observations"]
            if o.get("s_raw_a") is not None and o.get("opening_reserves_gbp_m") and o.get("hhi") is not None]
    S = np.array([o["s_raw_a"] for o in recs], float)
    R = np.array([o["opening_reserves_gbp_m"] for o in recs], float)
    H = np.clip(np.array([o["hhi"] for o in recs], float), HLO, HCE)
    yr = np.array([o["year"] for o in recs], int)
    ritc = np.array([f"{o['syndicate']}_{o['year']}" in occ for o in recs])
    corpus_by_year = {int(y): int(c) for y, c in d["meta"]["yearly_observations"].items()} \
        if "yearly_observations" in d.get("meta", {}) else None
    return S, R, H, yr, ritc, cal, corpus_by_year


def sigma(R, H, cal):
    reff = (np.maximum(R, 1e-9) / REF) * (1.0 / np.clip(H, HLO, HCE)) ** cal["gamma"]
    return np.sqrt(cal["sd_undiv"] ** 2 + cal["sd_div"] ** 2 * reff ** (2.0 * (cal["k"] - 1.0)))


def save(fig, name):
    fig.savefig(PP / f"{name}.png", dpi=150, bbox_inches="tight")
    fig.savefig(PP / f"{name}.pdf", bbox_inches="tight", metadata={"CreationDate": None})
    plt.close(fig); print(f"wrote paper_pack/{name}.png (+pdf)")


def fig_coverage(yr, corpus_by_year):
    years = list(range(2014, 2025))
    samp = {y: int((yr == y).sum()) for y in years}
    corp = corpus_by_year or samp
    act = [ACTIVE[y] for y in years]; cor = [corp.get(y, 0) for y in years]; sam = [samp[y] for y in years]
    x = np.arange(len(years)); w = 0.27
    fig, ax = plt.subplots(figsize=(8, 4.4))
    ax.bar(x - w, act, w, label="Active syndicates (market)", color=C_ACT)
    ax.bar(x, cor, w, label="Corpus (extracted, in scope)", color=C_COR)
    ax.bar(x + w, sam, w, label="Working sample", color=C_SAM)
    ax2 = ax.twinx()
    cov = [100 * s / a for s, a in zip(sam, act)]
    ax2.plot(x, cov, "o-", color="#b2182b", lw=1.5, ms=4, label="Sample coverage %")
    ax2.set_ylabel("Sample coverage (%)", color="#b2182b"); ax2.set_ylim(0, 100)
    ax2.tick_params(axis="y", colors="#b2182b")
    ax.set_xticks(x); ax.set_xticklabels(years); ax.set_ylabel("Syndicate-years")
    ax.set_title(f"Corpus coverage by reporting year (n=790 sample, 907 corpus; overall {100*sum(sam)/sum(act):.0f}%)",
                 fontsize=10)
    ax.legend(loc="upper left", fontsize=8, frameon=False)
    fig.tight_layout(); save(fig, "fig_corpus_coverage")


def fig_size(S, R, H, cal):
    aS = np.abs(S)
    fig, ax = plt.subplots(figsize=(7, 5))
    ax.scatter(R, aS, s=10, alpha=0.28, color="#4a7ba6", edgecolors="none", label="|S| (syndicate-year)")
    # vigintile bin means
    edges = np.percentile(R, np.linspace(0, 100, 21)); b = np.clip(np.digitize(R, edges) - 1, 0, 19)
    bx = [np.median(R[b == i]) for i in range(20) if (b == i).sum() > 2]
    by = [np.median(aS[b == i]) for i in range(20) if (b == i).sum() > 2]
    ax.plot(bx, by, "s", color="#1b4965", ms=6, label="vigintile median |S|")
    # fitted sigma(R) at median H, and floor
    Rgrid = np.logspace(np.log10(R.min()), np.log10(R.max()), 100)
    ax.plot(Rgrid, sigma(Rgrid, np.median(H), cal), "-", color="#b2182b", lw=2,
            label=r"fitted $\sigma(R,\bar H)$")
    ax.axhline(cal["sd_undiv"], ls="--", color="#333", lw=1,
               label=r"floor $\sigma_{\mathrm{undiv}}=%.3f$" % cal["sd_undiv"])
    ax.set_xscale("log"); ax.set_yscale("log")
    ax.set_xlabel("Opening reserves $R$ (£m)"); ax.set_ylabel("|Signed PYD ratio|  $|S|$")
    ax.set_title(r"Size$-$dispersion: $|S|$ decays with size toward the floor ($k=%.2f$)" % cal["k"], fontsize=10)
    ax.legend(fontsize=8, frameon=False); ax.grid(True, which="both", alpha=0.2)
    fig.tight_layout(); save(fig, "fig_size_dispersion")


def fig_hhi(S, R, H, cal):
    # size-standardise: divide |S| by sigma(R, H=1) so only the concentration channel remains
    z_size = np.abs(S) / sigma(R, 1.0, cal)
    fig, ax = plt.subplots(figsize=(7, 5))
    ax.scatter(H, z_size, s=10, alpha=0.28, color="#5a8a5a", edgecolors="none",
               label="size-standardised |S|")
    edges = np.percentile(H, np.linspace(0, 100, 11)); b = np.clip(np.digitize(H, edges) - 1, 0, 9)
    bx = [np.median(H[b == i]) for i in range(10) if (b == i).sum() > 2]
    by = [np.median(z_size[b == i]) for i in range(10) if (b == i).sum() > 2]
    ax.plot(bx, by, "s", color="#1b4965", ms=6, label="decile median")
    Hgrid = np.linspace(max(H.min(), 0.05), H.max(), 100)
    # the fitted curve is a scale ratio (~1); the plotted points are median |S|/sigma
    # (~median|z| ~ 0.67), so anchor the curve to the data's median level. This
    # standardisation identifies the concentration *slope*, not its level.
    ratio_grid = sigma(REF, Hgrid, cal) / sigma(REF, 1.0, cal)
    ratio_obs = sigma(REF, H, cal) / sigma(REF, 1.0, cal)
    anchor = np.median(z_size) / np.median(ratio_obs)
    ax.plot(Hgrid, anchor * ratio_grid, "-", color="#b2182b", lw=2,
            label=r"fitted concentration slope (scaled to median)")
    ax.set_xlabel("HHI (higher = more concentrated)")
    ax.set_ylabel(r"$|S|\,/\,\sigma(R,H{=}1)$")
    ax.set_title(r"Concentration$-$dispersion (size removed): weak, $\gamma=%.2f$" % cal["gamma"], fontsize=10)
    ax.legend(fontsize=8, frameon=False); ax.grid(True, alpha=0.2)
    # crop the y-axis so the near-flat concentration slope is legible; a few
    # heavy-tail outliers run to ~25 and are noted rather than shown
    ax.set_ylim(0, 3)
    n_above = int((z_size > 3).sum())
    if n_above:
        ax.text(0.01, 0.98, f"{n_above} points $>3$ not shown", transform=ax.transAxes,
                ha="left", va="top", fontsize=7, color="#666")
    fig.tight_layout(); save(fig, "fig_hhi_dispersion")


def fig_gof(S, R, H, ritc, cal):
    z = S / sigma(R, H, cal)
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.6))
    # (a) QQ vs Student-t
    ax = axes[0]
    for mask, nu, col, lab in [(~ritc, cal["nu_clean"], "#1b7837", "clean"),
                               (ritc, cal["nu_ritc"], "#b2182b", "RITC")]:
        zz = np.sort(z[mask]); n = len(zz)
        q = stats.t.ppf((np.arange(1, n + 1) - 0.5) / n, df=nu)
        ax.plot(q, zz, "o", ms=3, alpha=0.5, color=col, label=f"{lab} ($\\nu={nu:.2f}$, n={n})")
    lim = 8
    ax.plot([-lim, lim], [-lim, lim], "k-", lw=0.8)
    ax.set_xlim(-lim, lim); ax.set_ylim(-lim, lim)
    ax.set_xlabel("Student-$t$ theoretical quantile"); ax.set_ylabel("standardised residual $z=S/\\sigma$")
    ax.set_title("QQ vs Student-$t$ (regime-specific $\\nu$)", fontsize=10)
    ax.legend(fontsize=8, frameon=False); ax.grid(True, alpha=0.2)
    # (b) mean|z| by size and HHI decile
    ax = axes[1]
    for arr, col, lab in [(R, "#4a7ba6", "size decile"), (H, "#5a8a5a", "HHI decile")]:
        edges = np.percentile(arr, np.linspace(0, 100, 11)); b = np.clip(np.digitize(arr, edges) - 1, 0, 9)
        med = [np.median(np.abs(z[b == i])) for i in range(10)]
        ax.plot(range(1, 11), med, "o-", color=col, lw=1.5, label=lab)
    ax.axhline(np.median(np.abs(z)), ls="--", color="#333", lw=1, label="overall median |z|")
    ax.set_xlabel("decile"); ax.set_ylabel("median |z| within bin")
    ax.set_title("Residual scale is flat across size & HHI (shape-adequate)", fontsize=10)
    ax.legend(fontsize=8, frameon=False); ax.grid(True, alpha=0.2); ax.set_ylim(bottom=0)
    fig.suptitle("Goodness of fit / shape adequacy (n=790)", fontsize=11)
    fig.tight_layout(rect=[0, 0, 1, 0.96]); save(fig, "fig_goodness_of_fit")


def main():
    S, R, H, yr, ritc, cal, corpus_by_year = load()
    print(f"n={len(S)}  RITC={int(ritc.sum())}  k={cal['k']:.3f} gamma={cal['gamma']:.3f} "
          f"floor={cal['sd_undiv']:.4f} nu_clean={cal['nu_clean']:.2f} nu_ritc={cal['nu_ritc']:.2f}")
    fig_coverage(yr, corpus_by_year)
    fig_size(S, R, H, cal)
    fig_hhi(S, R, H, cal)
    fig_gof(S, R, H, ritc, cal)


if __name__ == "__main__":
    main()
