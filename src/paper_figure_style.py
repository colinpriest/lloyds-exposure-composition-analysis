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
import numpy as np

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
#: NOTE for the redesign (26 October 2026): paper_pack/fig_uncertainty_sources (make_uncertainty_figure.py) is not listed
#: below because the manuscript does not include it yet, and src/test_figure_layout.py compares this dict with the
#: manuscript's includes. When the redesigned paper includes it (Figure 3), add "fig_uncertainty_sources": 0.95 here, the
#: fraction the figure is drawn for (make_uncertainty_figure.PRINTED_FRACTION), and extend the two figure tests' builders
#: (test_figure_layout.py, test_figure_presentation.py) to render it.
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


def data_under_legend(fig, ax, legend, pad_pt=0.0):
    """The labels of what `ax` plots that the legend's box, grown by `pad_pt` points on every side, touches: a line of any style that
    passes through the box (a connected series crossing it between its vertices as much as one with a vertex in it), a
    scatter point, a bar and a filled band (fill_between). An empty list is a clear legend. A line or band drawn in a
    blended transform (axhline, axvline) is a reference mark and not counted.

    The 23 October 2026 check that found the supplement's profile: its legend, inside the axes upper left, was crossed
    by the observed series' first segment and its marker, which a count of scatter points and marker-only lines
    (make_paper_figures.points_under_legend) never sees, because the series is a connected line."""
    from matplotlib.collections import PathCollection, PolyCollection
    from matplotlib.path import Path as MplPath
    from matplotlib.transforms import Bbox
    fig.canvas.draw()
    # only the part of the legend inside the axes can cover anything: what the axes plots outside its limits is clipped
    # (a legend below the axes, as Figures 2, 3 and 6 have, is over nothing)
    pad = pad_pt * fig.dpi / 72.0
    ext = legend.get_window_extent(fig.canvas.get_renderer())
    box = Bbox.intersection(Bbox.from_extents(ext.x0 - pad, ext.y0 - pad, ext.x1 + pad, ext.y1 + pad), ax.bbox)
    if box is None:
        return []
    hits = []
    for ln in ax.lines:
        # `==` on a blended transform and transData is not reliable (an axhline's compares equal): ask both axes
        if not all(ln.get_transform().contains_branch_seperately(ax.transData)) or not len(ln.get_xdata()):
            continue
        xy = np.asarray(ln.get_xydata(), float)
        with np.errstate(divide="ignore", invalid="ignore"):
            disp = ax.transData.transform(xy)
        disp = disp[np.isfinite(disp).all(axis=1)]
        if not len(disp):
            continue
        inside = ((disp[:, 0] >= box.x0) & (disp[:, 0] <= box.x1) & (disp[:, 1] >= box.y0)
                  & (disp[:, 1] <= box.y1)).any()
        joined = ln.get_linestyle() not in ("None", "none", " ", "") and len(disp) > 1
        if inside or (joined and MplPath(disp).intersects_bbox(box, filled=False)):
            hits.append(ln.get_label())
    for c in ax.collections:
        if isinstance(c, PolyCollection):                   # fill_between: its paths are in data coordinates
            for p in c.get_paths():
                if len(p.vertices) > 2 and MplPath(ax.transData.transform(p.vertices), p.codes).intersects_bbox(
                        box, filled=True):
                    hits.append(c.get_label())
                    break
        elif isinstance(c, PathCollection) and len(c.get_offsets()):          # scatter
            with np.errstate(divide="ignore", invalid="ignore"):
                disp = ax.transData.transform(np.asarray(c.get_offsets(), float))
            disp = disp[np.isfinite(disp).all(axis=1)]
            if ((disp[:, 0] >= box.x0) & (disp[:, 0] <= box.x1) & (disp[:, 1] >= box.y0)
                    & (disp[:, 1] <= box.y1)).any():
                hits.append(c.get_label())
    hits += [p.get_label() for p in ax.patches if box.overlaps(p.get_window_extent())]
    return hits


def printed_text_sizes(pdf_path, name):
    """Every text span's printed size in points, sorted: its size in the PDF times the printed width over the
    PDF's page width -- the arithmetic of the manuscript's gate."""
    import fitz
    with fitz.open(str(pdf_path)) as doc:
        page = doc[0]
        scale = printed_width_pt(name) / page.rect.width
        return sorted(s["size"] * scale for b in page.get_text("dict")["blocks"] for ln in b.get("lines", [])
                      for s in ln["spans"] if s["text"].strip())
