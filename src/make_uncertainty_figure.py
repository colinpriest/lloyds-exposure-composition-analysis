"""The sources of uncertainty in Vignette 1's GBP 500m VaR99.5, shown separately.

One figure, and a JSON of every plotted value. The stress is the entrant's 1-in-200 loss (the headline size-only
operator's VaR at 99.5%) as a fraction of the book's GBP 500m opening reserves. Four kinds of source are drawn in four
bands, each from the result file that already holds it, and NO band is added to another: the figure and the record carry
no combined interval, and the sources do not share a population, a model or an estimator.

  parameter_and_donor_weights  the headline's own interval, a Bayesian bootstrap over syndicates crossed with one joint
                               posterior draw per replicate (vignette_uncertainty_results.json);
  measurement_definition       the primary refitted under another reading of the outcome or another sample: the 672
                               construction (check_cohort_scope), cohort depth u <= t-3 (check_cohort_depth_sensitivity),
                               the earned-basis records out (check_earned_basis_sensitivity), the large older-years
                               bucket out (check_bucket_share_sensitivity) and the least-certain records out
                               (check_low_confidence_sensitivity);
  influential_donors           the most adverse donor out (check_donor_influence);
  model_alternatives           the concentration overlay (the gamma-free fit, exploratory), square-root scaling with no
                               floor, and the raw pool with no transfer (check_operator_backtest's vignette figures).

A dot is the row's centre. A solid bar is a credible interval (the headline's estimator); a dashed bar is the
conditional resampling interval of a refit whose own record holds no posterior interval. Both are conditional on the
row's data, its model and the dependence treatment. A row without a bar has no interval in its record. A value beyond
the axis is marked at the axis edge with its figures, beside its own row label. The vertical line is the headline centre.

Before anything is drawn the headline centre read from each file is checked equal (vignette_uncertainty, the gamma = 0
vignette record, the backtest's vignette figures, and each refit's recorded primary centre); the overlay's centre is
checked against the gamma = 0 vignette record's. A disagreement stops the run: the files would be from different
passes.

Writes paper_pack/fig_uncertainty_sources.{png,pdf} and make_uncertainty_figure_results.json.
Usage:  python src/make_uncertainty_figure.py
"""
import io
import json
import sys
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt                                     # noqa: E402
from matplotlib.lines import Line2D                                 # noqa: E402

import paper_figure_style as PFS                                    # noqa: E402
# a `from` import: this record is a display of other records' figures and takes the headline stamp only
from transfer_operator import HEADLINE, stamp                       # noqa: E402

SD = Path(__file__).resolve().parent.parent
RESULTS = SD / "results"
NAME = "fig_uncertainty_sources"
OUT_PNG = SD / "paper_pack" / (NAME + ".png")
OUT_PDF = SD / "paper_pack" / (NAME + ".pdf")
OUT_JSON = RESULTS / "make_uncertainty_figure_results.json"
#: the share of \linewidth the manuscript will give the figure; drawn at that printed width (paper_figure_style)
PRINTED_FRACTION = 0.95
#: the saved page is the content plus a 0.1 inch pad on each side (bbox_inches="tight"), and the manuscript scales that
#: page to PRINTED_FRACTION of the line width: so the figure is drawn that much narrower than the printed width, and its
#: 8 pt text prints at 8 pt or more (paper_figure_style's gate-CC floor)
DRAWN_WIDTH_IN = (PRINTED_FRACTION * PFS.LINE_WIDTH_PT - 2 * 0.1 * 72.0 - 4.0) / 72.0
TOL = 1.0e-12

SOURCES = {
    "vignette_uncertainty": "vignette_uncertainty_results.json",
    "gamma0": "check_gamma0_vignette_results.json",
    "backtest": "check_operator_backtest_results.json",
    "cohort_scope": "check_cohort_scope_results.json",
    "depth": "check_cohort_depth_sensitivity_results.json",
    "earned": "check_earned_basis_sensitivity_results.json",
    "bucket": "check_bucket_share_sensitivity_results.json",
    "least_certain": "check_low_confidence_sensitivity_results.json",
    "donors": "check_donor_influence_results.json",
}
KIND_CREDIBLE = "credible interval (Bayesian bootstrap over syndicates, one joint posterior draw per replicate)"
KIND_CONDITIONAL = ("conditional resampling interval (cluster bootstrap by syndicate, one posterior draw per replicate), "
                    "from a record that holds no posterior interval")
BAND_TITLES = {
    "parameter_and_donor_weights": "Parameter and donor-weight uncertainty",
    "measurement_definition": "Measurement definition",
    "influential_donors": "Influential donors",
    "model_alternatives": "Model alternatives",
}
#: the letters the manuscript's caption and text give the four bands, drawn before each band's heading
BAND_LETTERS = {
    "parameter_and_donor_weights": "(a)",
    "measurement_definition": "(b)",
    "influential_donors": "(c)",
    "model_alternatives": "(d)",
}
#: the figure's row labels in mathtext where the record's plain-text label carries an inequality; the record keeps its
#: label as written
ROW_LABEL_MATH = {"u <= t-3": r"$u\leq t-3$"}
NOT_SUMMED = ("The four sources are shown separately and are not added together: they differ in population, model and "
              "estimator, and no combined interval is computed.")


def load_sources(results_dir=RESULTS):
    out = {}
    for key, fname in SOURCES.items():
        path = Path(results_dir) / fname
        if not path.exists():
            raise SystemExit("%s is absent: run the step that writes it first" % path)
        with io.open(str(path), encoding="utf-8") as fh:
            out[key] = json.load(fh)
    return out


def sha256_of(path):
    """SHA-256 of a result record in reproduce.py's canonical form (the volatile keys, runtime_seconds among them,
    removed): the hash --verify compares, so a second pass on the same inputs records the same one."""
    sys.path.insert(0, str(SD))
    import reproduce
    with open(str(path), "rb") as fh:
        return reproduce.canonical_json_sha256(fh.read())


def reserve_size(src):
    """The vignette's opening reserves (GBP m), from the backtest's recorded Vignette 1 target."""
    return float(src["backtest"]["vignette_figures"]["targets"]["V1"][0])


def headline_centres(src):
    """{where: the size-only V1 VaR99.5 centre} as each file records it."""
    return {
        "vignette_uncertainty": src["vignette_uncertainty"]["centres_full_pool_posterior_mean"]["V1_adj"]["v995"],
        "gamma0_size_only": src["gamma0"]["size_only"]["centre"]["V1_v995"],
        "backtest_operator": src["backtest"]["vignette_figures"]["operator_size_only"]["V1"]["v995"],
        "cohort_scope_headline": src["cohort_scope"]["vignettes"]["headline"]["centre"]["V1_v995"],
        "depth_primary": src["depth"]["primary"]["vignette_centre"]["V1_v995"],
        "earned_primary": src["earned"]["vignettes"]["primary_centre"]["V1_v995"],
        "bucket_primary": src["bucket"]["vignettes"]["primary_centre"]["V1_v995"],
        "least_certain_primary": src["least_certain"]["vignettes"]["primary_centre"]["V1_v995"],
        "donors_with": src["donors"]["fits"]["with"]["V1_VaR995"]["centre"]}


def check_consistency(src):
    """Stop unless every file's headline centre is the same figure, and the overlay's two records agree."""
    cen = headline_centres(src)
    ref = cen["vignette_uncertainty"]
    off = {k: v for k, v in cen.items() if abs(v - ref) > TOL}
    if off:
        raise SystemExit("the headline centre differs between the result files (vignette_uncertainty %.15g): %s"
                         % (ref, {k: float(v) for k, v in off.items()}))
    ov = src["vignette_uncertainty"]["overlay_sensitivity"]["centres_full_pool_posterior_mean"]["V1_adj"]["v995"]
    ov0 = src["gamma0"]["overlay"]["centre"]["V1_v995"]
    if abs(ov - ov0) > TOL:
        raise SystemExit("the overlay's centre differs between vignette_uncertainty (%.15g) and the gamma = 0 vignette "
                         "record (%.15g)" % (ov, ov0))
    return {"headline_centre": float(ref), "centres_read": {k: float(v) for k, v in cen.items()},
            "overlay_centre_vignette_uncertainty": float(ov), "overlay_centre_gamma0_record": float(ov0)}


def row(rid, label, point, interval, kind, source, detail=None):
    return {"id": rid, "label": label, "point": float(point),
            "interval": None if interval is None else [float(interval[0]), float(interval[1])],
            "interval_kind": None if interval is None else kind, "source": source, "detail": detail}


def build_bands(src):
    """The four bands' rows, each from the file that holds it (reserve fractions of the GBP 500m book)."""
    vu = src["vignette_uncertainty"]
    head = vu["vignette1"]["adjusted"]["var995"]
    f = "results/%s"
    bands = {
        "parameter_and_donor_weights": [
            row("headline", "Headline: draws and donor weights",
                vu["centres_full_pool_posterior_mean"]["V1_adj"]["v995"], (head["lo"], head["hi"]), KIND_CREDIBLE,
                f % SOURCES["vignette_uncertainty"],
                "centre at the posterior means on the full pool; interval from the 4,000 replicates")],
    }
    cs = src["cohort_scope"]["vignettes"]
    bands["measurement_definition"] = [
        row("construction_672", "672-record construction", cs["precedence_672"]["centre"]["V1_v995"],
            (cs["posterior_intervals"]["precedence_672"]["V1_v995"]["lo"],
             cs["posterior_intervals"]["precedence_672"]["V1_v995"]["hi"]), KIND_CREDIBLE,
            f % SOURCES["cohort_scope"], "the extraction's precedence construction, refitted on its own donors"),
    ]
    for rid, label, key, detail in (
            ("depth_t_minus_3", "Cohort depth u <= t-3", None,
             "the records that have a figure at u <= t-3, refitted at that outcome"),
            ("earned_basis", "Earned-basis records out", "earned",
             "the records whose filings say the t-2 cohort was still earning, left out and the fit redone"),
            ("older_years_bucket", "Large older-years bucket out", "bucket",
             "the records whose 'X and prior' bucket holds more than 30% of the gross reserves, left out"),
            ("least_certain", "Least-certain records out", "least_certain",
             "the records the filing readings could not settle, left out and the fit redone")):
        block = (src["depth"]["cohort_depth_t_minus_3"]["vignettes"] if key is None else src[key]["vignettes"])
        iv = block["intervals"]["V1_v995"]
        name = SOURCES["depth"] if key is None else SOURCES[key]
        bands["measurement_definition"].append(
            row(rid, label, block["centre"]["V1_v995"], (iv["lo"], iv["hi"]), KIND_CONDITIONAL, f % name, detail))
    d = src["donors"]["fits"]["without"]["V1_VaR995"]
    bands["influential_donors"] = [
        row("most_adverse_donor_out", "Most adverse donor out", d["centre"], (d["lo"], d["hi"]), KIND_CREDIBLE,
            f % SOURCES["donors"],
            "the donor %s, refitted and re-pooled without it" % src["donors"]["donor"]["key"])]
    ov = vu["overlay_sensitivity"]
    ovi = ov["vignette1"]["adjusted"]["var995"]
    vf = src["backtest"]["vignette_figures"]
    bands["model_alternatives"] = [
        row("concentration_overlay", "Concentration overlay (exploratory)",
            ov["centres_full_pool_posterior_mean"]["V1_adj"]["v995"], (ovi["lo"], ovi["hi"]), KIND_CREDIBLE,
            f % SOURCES["vignette_uncertainty"], "the gamma-free fit's fitted concentration exponent; exploratory"),
        row("square_root_scaling", "Square-root scaling, no floor", vf["sqrt_R"]["V1"]["v995"], None, None,
            f % SOURCES["backtest"], "each donor scaled by the square root of the reserve ratio; no interval recorded"),
        row("raw_pool", "Raw pool, no transfer", vf["raw_pool"]["v995"], None, None, f % SOURCES["backtest"],
            "the donors' own severities; no interval recorded")]
    return bands


def axis_limits(bands, headline):
    """(lo, hi) of the x axis: from zero to just beyond the largest interval end or point other than the raw pool, so a
    pool that is far off scale does not flatten the rest."""
    top = max([headline] + [r["point"] for b in bands.values() for r in b if r["id"] != "raw_pool"]
              + [r["interval"][1] for b in bands.values() for r in b if r["interval"]])
    return 0.0, float(np.ceil(top * 1.08 / 0.05) * 0.05)


def values_record(src, bands, reserve, consistency, xlim):
    out_bands = []
    for bid, rows in bands.items():
        out_rows = []
        for r in rows:
            o = dict(r)
            o["point_gbp_m"] = r["point"] * reserve
            o["interval_gbp_m"] = None if r["interval"] is None else [x * reserve for x in r["interval"]]
            o["off_scale"] = bool(r["point"] > xlim[1])
            out_rows.append(o)
        out_bands.append({"id": bid, "title": BAND_TITLES[bid], "rows": out_rows})
    return {
        **stamp(HEADLINE),
        "figure": "paper_pack/%s.pdf and .png" % NAME,
        "vignette": "Vignette 1",
        "statistic": "VaR at 99.5% of the transferred pool, as a fraction of the book's opening reserves",
        "reserve_size_gbp_m": reserve,
        "headline_centre": consistency["headline_centre"],
        "headline_centre_gbp_m": consistency["headline_centre"] * reserve,
        "consistency": consistency,
        "x_axis_reserve_fraction": [float(xlim[0]), float(xlim[1])],
        "bands": out_bands,
        "reading": NOT_SUMMED,
        "interval_kinds": {"credible": KIND_CREDIBLE, "conditional_resampling": KIND_CONDITIONAL},
        "inputs": {k: {"file": "results/%s" % v, "sha256": sha256_of(RESULTS / v) if (RESULTS / v).exists() else None}
                   for k, v in SOURCES.items()},
    }


def row_label_text(label):
    """The row label as the figure prints it: the record's label with its ASCII inequality set in mathtext."""
    for plain, math in ROW_LABEL_MATH.items():
        label = label.replace(plain, math)
    return label


def band_heading(band_id):
    """The band's heading as the figure prints it: its letter, then its title."""
    return "%s %s" % (BAND_LETTERS[band_id], BAND_TITLES[band_id])


def build_figure(values):
    """The figure for a values record: four bands sharing the x axis, rows labelled at the left."""
    rows_per = [len(b["rows"]) for b in values["bands"]]
    fig = plt.figure(figsize=(DRAWN_WIDTH_IN, 0.27 * (sum(rows_per) + 1) + 1.65))
    gs = fig.add_gridspec(len(rows_per), 1, height_ratios=[n + 0.9 for n in rows_per], hspace=0.62)
    xlo, xhi = values["x_axis_reserve_fraction"]
    headline = values["headline_centre"]
    reserve = values["reserve_size_gbp_m"]
    axes = []
    colours = {"parameter_and_donor_weights": "#1b4f8a", "measurement_definition": "#b2182b",
               "influential_donors": "#7a4f01", "model_alternatives": "#1b7837"}
    for gi, band in enumerate(values["bands"]):
        ax = fig.add_subplot(gs[gi], sharex=axes[0] if axes else None)
        axes.append(ax)
        col = colours[band["id"]]
        n = len(band["rows"])
        ys = np.arange(n)[::-1]
        for y, r in zip(ys, band["rows"]):
            if r["interval"] is not None:
                credible = r["interval_kind"] == KIND_CREDIBLE
                ax.hlines(y, r["interval"][0], r["interval"][1], color=col, lw=2.4 if credible else 1.6,
                          ls="-" if credible else "--", zorder=2)
            if r["off_scale"]:
                # the row's own label (at the left) names it, so the note gives only the figures, on two lines (one
                # line ran back across the headline line), a little above the row's centre to clear the axis
                ax.annotate("%.3f →\nGBP %.0fm" % (r["point"], r["point_gbp_m"]),
                            xy=(xhi, y), xytext=(xhi - 0.012 * (xhi - xlo), y + 0.12), ha="right", va="center",
                            fontsize=PFS.SMALL_PT, color=col, linespacing=1.1)
                continue
            marker = "o" if r["interval"] is not None else "s"
            ax.plot(r["point"], y, marker, color=col, ms=5.5, zorder=3)
        ax.axvline(headline, color="#333333", lw=0.9, ls=":", zorder=1)
        ax.set_yticks(ys)
        ax.set_yticklabels([row_label_text(r["label"]) for r in band["rows"]], fontsize=PFS.SMALL_PT)
        ax.set_ylim(-0.7, n - 0.3)
        ax.set_xlim(xlo, xhi)
        ax.set_title(band_heading(band["id"]), loc="left", fontsize=9.0)
        ax.tick_params(axis="x", labelsize=PFS.SMALL_PT, labelbottom=(gi == len(values["bands"]) - 1))
        ax.grid(True, axis="x", alpha=0.2)
        for side in ("top", "right"):
            ax.spines[side].set_visible(False)
        if gi == 0:
            sec = ax.secondary_xaxis("top", functions=(lambda x: x * reserve, lambda x: x / reserve))
            sec.set_xlabel("GBP m", fontsize=PFS.SMALL_PT)
            sec.tick_params(labelsize=PFS.SMALL_PT)
    axes[-1].set_xlabel("VaR 99.5%% as a fraction of GBP %.0fm reserves" % reserve)
    legend_items = [Line2D([], [], color="#444444", lw=2.4, marker="o", ms=5.5,
                                            label="centre and credible interval"),
                    Line2D([], [], color="#444444", lw=1.6, ls="--", marker="o", ms=5.5,
                                            label="centre and conditional resampling interval"),
                    Line2D([], [], color="#444444", lw=0, marker="s", ms=5.5,
                                            label="point only"),
                    Line2D([], [], color="#333333", lw=0.9, ls=":", label="headline centre")]
    fig.legend(handles=legend_items, loc="lower center", ncol=2, frameon=False, fontsize=PFS.SMALL_PT,
               bbox_to_anchor=(0.5, -0.005))
    # the left margin holds the longest row label, so the saved (cropped) page is no wider than the printed width and
    # the 8 pt text prints at 8 pt or more (the figure is drawn at its printed width, as paper_figure_style does)
    fig.subplots_adjust(left=0.445, right=0.985, top=0.90, bottom=0.17)
    return fig


def save_figure(fig, png_path=OUT_PNG, pdf_path=OUT_PDF):
    """Both files, the PDF without its creation date so that two runs give the same bytes."""
    fig.savefig(png_path, dpi=150, bbox_inches="tight")
    fig.savefig(pdf_path, bbox_inches="tight", metadata={"CreationDate": None})


def compute(src):
    """(values record, figure's rows) from the loaded sources."""
    consistency = check_consistency(src)
    bands = build_bands(src)
    reserve = reserve_size(src)
    xlim = axis_limits(bands, consistency["headline_centre"])
    return values_record(src, bands, reserve, consistency, xlim)


def main(argv=None):
    src = load_sources()
    values = compute(src)
    with PFS.style():
        fig = build_figure(values)
        save_figure(fig)
    plt.close(fig)
    with io.open(str(OUT_JSON), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(values, indent=1) + "\n")
    print("Wrote %s, %s and %s" % (OUT_PNG, OUT_PDF, OUT_JSON))
    for b in values["bands"]:
        for r in b["rows"]:
            iv = "" if r["interval"] is None else " [%.4f, %.4f]" % tuple(r["interval"])
            print("  %-28s %.4f%s%s" % (r["label"], r["point"], iv, "  (off scale)" if r["off_scale"] else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
