"""The paper's figures are drawn at the width they print at, so their text prints at its drawn size.

The manuscript's figure-text gate (paper/audit_numbers.py, gate CC; review of 29 September 2026) measured the
text of all six paper figures printing at 3.4-4.8 pt: each was drawn 6.9-10.9 inches wide with 7-10 pt text and
\\includegraphics shrank it to 4.2-5.0 inches. Cambridge asks for about 9 pt at final size. So each figure is now
drawn at its printed width -- the fraction of \\linewidth the manuscript gives it, times the article's text width
-- with 9 pt labels and titles and 8 pt ticks, legends and annotations, and src/test_figure_layout.py renders
every one and measures its text as the gate does: size in the file times printed width over file width, and
none below MIN_PRINTED_PT.
"""
import matplotlib.pyplot as plt

#: the article's text width in points, measured from the built manuscript (paper/main.pdf and supplement.pdf,
#: 29 September 2026: 402.6-403.1 pt across builds; the smallest is used, so the text never prints smaller)
TEXT_WIDTH_PT = 402.6
#: each paper figure's printed width as a fraction of \linewidth, as the manuscript includes it
PRINTED_FRACTION = {
    "fig_size_dispersion": 0.75,
    "fig_hhi_dispersion": 0.75,
    "fig_goodness_of_fit": 0.90,
    "fig_v1_ritc_survivor": 0.85,
    "fig_corpus_coverage": 0.85,
    "systemic_correlation_profile": 0.80,
}
#: no text may print smaller than this (the manuscript's gate fails below 6 pt; Cambridge asks about 9 pt)
MIN_PRINTED_PT = 7.0
#: drawn sizes: labels and titles at 9 pt, the small furniture at 8 pt
RC = {"font.size": 9.0, "axes.titlesize": 9.0, "axes.labelsize": 9.0, "figure.titlesize": 9.0,
      "xtick.labelsize": 8.0, "ytick.labelsize": 8.0, "legend.fontsize": 8.0}
SMALL_PT = 8.0


def width_in(name):
    """The printed width of figure `name` in inches."""
    return PRINTED_FRACTION[name] * TEXT_WIDTH_PT / 72.0


def figure(name, height_in, **kw):
    """plt.subplots at the printed width of figure `name` (call inside style())."""
    return plt.subplots(figsize=(width_in(name), height_in), **kw)


def style():
    """A context in which a paper figure is drawn: the sizes above, restored afterwards."""
    return plt.rc_context(RC)


def plain_log_ticks(ax):
    """Plain-number tick labels (0.01, 100) on every log-scaled axis of `ax`, and none on minor ticks: a
    mathtext 10^k label prints its exponent at 70% of the tick size, below the floor at any legible size."""
    from matplotlib.ticker import FuncFormatter, NullFormatter
    for axis, scale in ((ax.xaxis, ax.get_xscale()), (ax.yaxis, ax.get_yscale())):
        if scale == "log":
            axis.set_major_formatter(FuncFormatter(lambda v, _pos: "%g" % v))
            axis.set_minor_formatter(NullFormatter())


def printed_text_sizes(pdf_path, name):
    """Every text span's printed size in points, sorted: its size in the PDF times the printed width over the
    PDF's page width -- the arithmetic of the manuscript's gate."""
    import fitz
    with fitz.open(str(pdf_path)) as doc:
        page = doc[0]
        scale = width_in(name) * 72.0 / page.rect.width
        return sorted(s["size"] * scale for b in page.get_text("dict")["blocks"] for ln in b.get("lines", [])
                      for s in ln["spans"] if s["text"].strip())
