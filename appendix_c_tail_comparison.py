"""Appendix C: consolidated VaR99.5 tail-estimate comparison (three methods).

Reads the three result files and emits (i) a LaTeX table and (ii) a forest-plot figure
comparing the empirical, frequentist-EVT (POT bootstrap) and Bayesian-EVT (POT MCMC) VaR99.5
for the two vignette tail distributions, each as a point with a 95% interval.

Run: python appendix_c_tail_comparison.py
"""
import json
from pathlib import Path
import numpy as np
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt

SCRIPT_DIR = Path(__file__).resolve().parent


def load():
    vu = json.loads((SCRIPT_DIR / "vignette_uncertainty_results.json").read_text())
    gp = json.loads((SCRIPT_DIR / "gpd_var_uncertainty_results.json").read_text())
    bg = json.loads((SCRIPT_DIR / "bayesian_gpd_results.json").read_text())
    cen = vu["centres_full_pool_posterior_mean"]
    rows = {
        "V1 (adjusted)": {
            "Empirical": (cen["V1_adj"]["v995"], vu["vignette1"]["adjusted"]["var995"]["lo"], vu["vignette1"]["adjusted"]["var995"]["hi"]),
            "EVT - frequentist POT": (gp["distributions"]["V1_adjusted"]["point_var995"], gp["distributions"]["V1_adjusted"]["band_lo_2.5"], gp["distributions"]["V1_adjusted"]["band_hi_97.5"]),
            "EVT - Bayesian POT": (bg["distributions"]["V1_adjusted"]["var995_median"], bg["distributions"]["V1_adjusted"]["var995_2.5"], bg["distributions"]["V1_adjusted"]["var995_97.5"]),
            "xi": bg["distributions"]["V1_adjusted"]["xi_median"],
        },
        "V2 (new profile)": {
            "Empirical": (cen["V2_new"]["v995"], vu["vignette2"]["adjusted_new"]["var995"]["lo"], vu["vignette2"]["adjusted_new"]["var995"]["hi"]),
            "EVT - frequentist POT": (gp["distributions"]["V2_new"]["point_var995"], gp["distributions"]["V2_new"]["band_lo_2.5"], gp["distributions"]["V2_new"]["band_hi_97.5"]),
            "EVT - Bayesian POT": (bg["distributions"]["V2_new"]["var995_median"], bg["distributions"]["V2_new"]["var995_2.5"], bg["distributions"]["V2_new"]["var995_97.5"]),
            "xi": bg["distributions"]["V2_new"]["xi_median"],
        },
    }
    return rows


def latex(rows):
    def cell(t): return f"{t[0]:.3f} [{t[1]:.3f}, {t[2]:.3f}]"
    methods = ["Empirical", "EVT - frequentist POT", "EVT - Bayesian POT"]
    body = "\\textbf{Method} & \\textbf{V1 (adjusted)} & \\textbf{V2 (new profile)} \\\\\n\\midrule\n"
    for m in methods:
        ml = m.replace("EVT - ", "EVT, ")
        body += f"{ml} & {cell(rows['V1 (adjusted)'][m])} & {cell(rows['V2 (new profile)'][m])} \\\\\n"
    xi1, xi2 = rows["V1 (adjusted)"]["xi"], rows["V2 (new profile)"]["xi"]
    tex = (
        "\\begin{table}[htbp]\n\\centering\n"
        "\\caption{Tail-estimate comparison for VaR$_{99.5\\%}$ of the transferred-severity "
        "distributions: empirical, frequentist extreme-value (peaks-over-threshold, POT) and "
        "Bayesian POT. Point estimate with 95\\% interval; POT threshold at the 90th percentile "
        "($N_u\\approx49$ exceedances).}\n"
        "\\label{tab:tail_comparison}\n\\begin{tabular}{lcc}\n\\toprule\n"
        + body +
        "\\bottomrule\n\\end{tabular}\n\\vspace{2pt}\n"
        f"{{\\footnotesize The three estimates are mutually consistent: each point lies inside the "
        f"other methods' intervals, and both EVT intervals contain the empirical point. The fitted "
        f"tail shape is credibly heavy ($\\hat\\xi\\approx{xi1:.2f}$ for V1, ${xi2:.2f}$ for V2; "
        f"95\\% credible interval excludes zero), which is why the upper limits are wide. Intervals: "
        f"empirical and frequentist-POT from a cluster (by-syndicate) bootstrap $\\times$ posterior "
        f"draws ($B=4000$); Bayesian-POT from the GPD posterior.}}\n\\end{{table}}\n"
    )
    (SCRIPT_DIR / "appendix_c_tail_comparison.tex").write_text(tex, encoding="utf-8")


def figure(rows):
    methods = ["Empirical", "EVT - frequentist POT", "EVT - Bayesian POT"]
    colors = {"Empirical": "#2166ac", "EVT - frequentist POT": "#b2182b", "EVT - Bayesian POT": "#1b7837"}
    fig, axes = plt.subplots(1, 2, figsize=(11, 3.6), sharex=True)
    for ax, (vname, data) in zip(axes, rows.items()):
        emp = data["Empirical"][0]
        ax.axvline(emp, color="#2166ac", ls="--", lw=1, alpha=0.6, zorder=0)
        for i, m in enumerate(methods):
            pt, lo, hi = data[m]
            y = len(methods) - 1 - i
            ax.plot([lo, hi], [y, y], color=colors[m], lw=2.5, solid_capstyle="round")
            ax.plot([lo, hi], [y, y], "|", color=colors[m], markersize=10, mew=2)
            ax.plot(pt, y, "o", color=colors[m], markersize=8, zorder=3)
            ax.text(hi + 0.02, y, f"{pt:.3f} [{lo:.2f}, {hi:.2f}]", va="center", fontsize=8)
        ax.set_yticks(range(len(methods)))
        ax.set_yticklabels([m.replace("EVT - ", "EVT: ") for m in reversed(methods)], fontsize=9)
        ax.set_ylim(-0.6, len(methods) - 0.4)
        ax.set_title(f"{vname}   ($\\hat\\xi\\approx{data['xi']:.2f}$)", fontsize=10)
        ax.set_xlabel("VaR$_{99.5\\%}$ (signed PYD ratio)")
        ax.grid(True, axis="x", alpha=0.25)
        ax.set_xlim(0.2, 1.25)
    fig.suptitle("VaR$_{99.5\\%}$ tail estimates: empirical vs frequentist EVT vs Bayesian EVT "
                 "(point + 95% interval; dashed line = empirical point)", fontsize=10)
    fig.tight_layout(rect=[0, 0, 1, 0.96])
    fig.savefig(SCRIPT_DIR / "appendix_c_tail_comparison.png", dpi=150, bbox_inches="tight")
    fig.savefig(SCRIPT_DIR / "appendix_c_tail_comparison.pdf", bbox_inches="tight")
    plt.close(fig)


def main():
    rows = load()
    latex(rows); figure(rows)
    for v, data in rows.items():
        print(f"{v}:")
        for m in ["Empirical", "EVT - frequentist POT", "EVT - Bayesian POT"]:
            pt, lo, hi = data[m]
            print(f"  {m:24s} {pt:.3f} [{lo:.3f}, {hi:.3f}]")
    print("\nWrote appendix_c_tail_comparison.tex, .png, .pdf")


if __name__ == "__main__":
    main()
