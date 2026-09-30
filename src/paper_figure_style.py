"""The paper's figures are drawn at the width they print at, so their text prints at its drawn size.

The manuscript's figure-text gate (paper/audit_numbers.py, gate CC; review of 29 September 2026) measured the
text of all six paper figures printing at 3.4-4.8 pt: each was drawn 6.9-10.9 inches wide with 7-10 pt text and
\\includegraphics shrank it to 4.2-5.0 inches. Cambridge asks for about 9 pt at final size. So each figure is now
drawn at about its printed width -- the fraction of \\linewidth the manuscript gives it -- with 9 pt labels and
titles and 8 pt ticks, legends and annotations, and src/test_figure_layout.py renders every one and measures its
text as the gate does: size in the file times printed width over file width, and none below MIN_PRINTED_PT.

The printed width is the fraction times LINE_WIDTH_PT, the layout's text width. The article's five figures are
drawn from TEXT_WIDTH_PT, 0.7% wider, and saved cropped to their contents; the supplement's profile is saved
uncropped and drawn from the line width less PRINT_MARGIN (30 September 2026: drawn from TEXT_WIDTH_PT, it printed
at 7.94 pt against the gate's 8 pt floor).
"""
import matplotlib.pyplot as plt

#: the text width both documents print at, in PDF points: cup-journal's medium layout (journal=aas) is 174 mm wide
#: with margins of 18 mm and 15 mm, so 141 mm = 399.69 pt. The built main.pdf and supplement.pdf place all six
#: figures at their fraction of 399.69-399.72 pt (measured 30 September 2026 from each figure's placement, as the
#: manuscript's gate CC reads it)
LINE_WIDTH_PT = 141.0 / 25.4 * 72.0
#: the width the article's five figures are drawn from: 402.6 pt, measured on 29 September 2026 as the widest text
#: block, which margin kerning widens (the manuscript's gate CC records the same flaw in its former measure). It is
#: 0.7% wider than the line; those figures are saved cropped to their contents, which the manuscript enlarges to
#: the line, and print at 8.08-8.14 pt. They are left as they are
TEXT_WIDTH_PT = 402.6
#: a figure saved uncropped prints its text at LINE_WIDTH_PT over the width it is drawn from; the ones named here
#: are drawn from the line width over this margin, so their 8 pt text prints at 8.16 pt
PRINT_MARGIN = 1.02
SAVED_UNCROPPED = ("systemic_correlation_profile",)
#: each paper figure's printed width as a fraction of \linewidth, as the manuscript includes it
PRINTED_FRACTION = {
    "fig_size_dispersion": 0.75,
    "fig_hhi_dispersion": 0.75,
    "fig_goodness_of_fit": 0.90,
    "fig_v1_ritc_survivor": 0.85,
    "fig_corpus_coverage": 0.85,
    "systemic_correlation_profile": 0.82,
}
#: no text may print smaller than this: the manuscript's gate CC floor (FIGURE_MIN_PRINTED_PT; Cambridge asks about
#: 9 pt)
MIN_PRINTED_PT = 8.0
#: drawn sizes: labels and titles at 9 pt, the small furniture at 8 pt
RC = {"font.size": 9.0, "axes.titlesize": 9.0, "axes.labelsize": 9.0, "figure.titlesize": 9.0,
      "xtick.labelsize": 8.0, "ytick.labelsize": 8.0, "legend.fontsize": 8.0}
SMALL_PT = 8.0


def width_in(name):
    """The width figure `name` is drawn at, in inches."""
    base = LINE_WIDTH_PT / PRINT_MARGIN if name in SAVED_UNCROPPED else TEXT_WIDTH_PT
    return PRINTED_FRACTION[name] * base / 72.0


def printed_width_pt(name):
    """The width figure `name` prints at in the manuscript, in points."""
    return PRINTED_FRACTION[name] * LINE_WIDTH_PT


def figure(name, height_in, **kw):
    """plt.subplots at the drawn width of figure `name` (call inside style())."""
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
        scale = printed_width_pt(name) / page.rect.width
        return sorted(s["size"] * scale for b in page.get_text("dict")["blocks"] for ln in b.get("lines", [])
                      for s in ln["spans"] if s["text"].strip())
