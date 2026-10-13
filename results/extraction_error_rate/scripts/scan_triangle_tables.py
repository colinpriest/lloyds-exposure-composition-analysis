r"""The triangle-table census (protocol/error-rate-protocol-table-scan.md, the fourteenth amendment). Read-only.

For every record of the working sample whose adopted figure is triangle-sourced, locate in the filing the table the
figure was computed from (the used table), place its own printed totals and the filing's gross and net claims
outstanding at the report date, reconcile them within 2%, and classify the record:

    A  a used-table total reconciles to the gross figure          (pass)
    B  a used-table total reconciles to the net figure only       (net-table candidate)
    C  totals placed but none reconciles, or the filing's own gross latest-estimate total does not reconcile to the
       gross table's latest diagonal                               (faulty or unreconciled)
    D  cannot be checked, with the reason

    python scan_triangle_tables.py                 # the whole population; writes triangle-table-scan/triangle-table-scan.json
    python scan_triangle_tables.py --stems syndicate_1274_2023 syndicate_4472_2022 --print   # some records; writes nothing

Offline: it reads the analysis copies of the records, the filings (text layer; the extraction's OCR page cache for a
page without one), and the next report's record; it calls no API and writes only its own output. Eye placements
(triangle-table-scan/eye-placements.json) override or add totals a reader placed by reading the page, and every record
so placed is marked. Run with PYTHONDONTWRITEBYTECODE=1 and LLOYDS_EXTRACTION_OFFLINE=1.
"""
import argparse
import copy
import datetime
import io
import json
import os
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

SCR = Path(__file__).resolve().parent
STUDY = SCR.parent
AN = STUDY.parent.parent
OUT_DIR = STUDY / "triangle-table-scan"
OUT = OUT_DIR / "triangle-table-scan.json"
EYE = OUT_DIR / "eye-placements.json"
EXTRACTION = Path(r"D:/dev/lloyds_reserve_stress_testing")
OCR_CACHE = EXTRACTION / "pdf_extraction" / "ocr_page_cache"
FOURTH = STUDY / "fourth-sample"

TOL = 0.02            # the protocol's opening-reserves tolerance: |x - y| <= 0.02 |y|
INDISTINCT = 0.04     # gross and net indistinguishable when they differ by 4% of gross or less
ANCHOR_TOL = 0.01     # a printed figure carries the adopted opening reserves (or the next report's) within 1%
TRIPLE_TOL = 0.003    # gross less reinsurers' share is net, within rounding
MIN_CELL = 10.0       # grid cells smaller than this are not used to locate a table (they match anywhere)
SCALES = (1000.0, 1.0, 1e6)
UNITS = {"thousands": 1000.0, "millions": 1.0, "units": 1e6, "ones": 1e6}

sys.path.insert(0, str(SCR))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

MONTHS = r"(?:January|February|March|April|May|June|July|August|September|October|November|December)"
DATE_RE = re.compile(r"\b\d{1,2}(?:st|nd|rd|th)?\s+" + MONTHS + r"(?:\s*,?\s*(?:19|20)\d\d)?\b|\b" + MONTHS
                     + r"\s+(?:19|20)\d\d\b", re.I)
YEAR_RE = re.compile(r"^(?:19[89]\d|20[0-3]\d)$")
NUM_RE = re.compile(r"^\(?[-\u2013\u2212]?\(?\d{1,3}(?:,\d{3})+(?:\.\d+)?\)?$|^\(?[-\u2013\u2212]?\(?\d+(?:\.\d+)?\)?$")
TOTAL_KW = re.compile(r"reserve|outstanding|balance|liabilit|provision|total|recogni[sz]ed|ibnr|estimated|sheet"
                      r"|financial\s+position", re.I)
NOTE_HEAD = re.compile(r"^\s*\d{1,2}\s*[.)]\s+[A-Za-z]")
PAID_KW = re.compile(r"\bpaid\b|payment|settle", re.I)
BASIS_KW = re.compile(r"\b(gross|net)\b|reinsurance", re.I)
DEVSTART = re.compile(r"^\W*(?:at\s+)?(?:the\s+)?end\s+of\s+(?:the\s+)?(?:first\s+|underwriting\s+|accident\s+|reporting\s+)?"
                      r"(?:underwriting\s+)?year|^\W*(?:1|one|first)\s+year\b|^\W*year\s*1\b|^\W*12\s+months", re.I)
AGE_HEAD = re.compile(r"\b\d+\s+(?:years?|months)\b", re.I)
CLOSE_KW = re.compile(r"31\s*December|end\s+of\s+(?:the\s+)?(?:financial\s+)?(?:year|period)|closing|carried\s+forward"
                      r"|balance\s+at\s+end|at\s+31", re.I)
CO_LABEL = re.compile(r"claims\s+outstanding|outstanding\s+claims|claims\s+reserves?\b|insurance\s+(?:contract\s+)?"
                      r"liabilit|provisions?\s+for\s+(?:outstanding\s+)?claims|gross\s+(?:claims|provision)|"
                      r"technical\s+provisions", re.I)
RI_CO = re.compile(r"claims\s+outstanding|outstanding\s+claims", re.I)
RI_NOT = re.compile(r"change|paid|movement|incurred|gross", re.I)
RI_KW = re.compile(r"reinsurer|re-insurer|reinsurance\s+share|share\s+of", re.I)
OPEN_KW = re.compile(r"1\s*January|beginning\s+of|opening|brought\s+forward|at\s+1\b", re.I)


# --- text --------------------------------------------------------------------------------------------------------------

def amount(tok):
    """A printed amount, signed (brackets or a minus are negative), or None. Bare years are not amounts."""
    t = tok.strip().strip("£$€").replace("\u2019", "").rstrip(".,;:*")
    t = t.lstrip("£$€")
    if not t or t in ("-", "\u2013", "\u2014", "nil", "Nil"):
        return None
    if YEAR_RE.match(t):
        return None
    if not NUM_RE.match(t):
        return None
    neg = t.startswith("(") or t.endswith(")") or t.lstrip("(").startswith(("-", "\u2013", "\u2212"))
    v = float(re.sub(r"[^\d.]", "", t))
    return -v if neg else v


def amounts_of(text):
    clean = DATE_RE.sub(" ", text)
    return [a for a in (amount(t) for t in clean.split()) if a is not None]


def label_of(text):
    """The words before the line's first amount."""
    out = []
    for tok in DATE_RE.sub(" DATE ", text).split():
        if amount(tok) is not None:
            break
        out.append(tok)
    return " ".join(out)


def years_in(text):
    return [t for t in text.replace("&", " ").split() if YEAR_RE.match(t.strip(".,"))]


class Line:
    __slots__ = ("page", "idx", "text", "amts", "label")

    def __init__(self, page, idx, text):
        self.page, self.idx, self.text = page, idx, text
        self.amts = amounts_of(text)
        self.label = label_of(text)

    def __repr__(self):
        return "p%d#%d %s" % (self.page, self.idx, self.text[:100])


def fitz_rows(page, ytol=2.5):
    words = page.get_text("words")
    words.sort(key=lambda w: ((w[1] + w[3]) / 2, w[0]))
    rows = []
    for w in words:
        yc = (w[1] + w[3]) / 2
        if rows and abs(rows[-1][0] - yc) <= ytol:
            rows[-1][1].append(w)
        else:
            rows.append([yc, [w]])
    return [" ".join(w[4] for w in sorted(ws, key=lambda w: w[0])) for _y, ws in rows]


class Filing:
    """A filing's pages as lines: the text layer, or the OCR page cache for a page without one."""

    def __init__(self, stem):
        import fitz
        import filing_pages
        self.stem = stem
        path, what = filing_pages.filing_path(stem)
        self.path, self.kind = path, what
        self.pages, self.how = {}, {}
        if path is None:
            return
        ocr = {}
        cache = OCR_CACHE / ("%s.json" % stem)
        if cache.exists():
            for pg in json.load(io.open(str(cache), encoding="utf-8")):
                ocr[int(pg["page"])] = pg.get("text") or ""
        doc = fitz.open(str(path))
        try:
            for i in range(doc.page_count):
                p = i + 1
                if len((doc[i].get_text() or "").strip()) >= 40:
                    texts, how = fitz_rows(doc[i]), "text layer"
                elif ocr.get(p, "").strip():
                    texts, how = [t for t in ocr[p].splitlines() if t.strip()], "OCR page cache"
                else:
                    texts, how = [], "image page without OCR text"
                self.pages[p] = [Line(p, k, t) for k, t in enumerate(texts)]
                self.how[p] = how
        finally:
            doc.close()

    def lines(self):
        for p in sorted(self.pages):
            for ln in self.pages[p]:
                yield ln


# --- the used table ----------------------------------------------------------------------------------------------------

def latest_cells(grid):
    """Per underwriting-year column: (year, latest non-empty cell, the one before it)."""
    rows = grid.get("development_rows") or []
    years = grid.get("underwriting_years") or []
    out = []
    for j, y in enumerate(years):
        col = [r[j] for r in rows if j < len(r) and r[j] is not None]
        if col:
            out.append((y, col[-1], col[-2] if len(col) > 1 else None))
    return out


def grid_scale(grid, report_year, adopted):
    """The divisor that takes the grid's cells to millions: the stated units' unless another of 1, 1,000, 1,000,000
    (or 1/1,000) is the one at which the grid reproduces the adopted figure (the estimator reads a document's unit
    hint where a grid's own units label is wrong). Returns (scale, how)."""
    stated = UNITS.get(str(grid.get("units") or "").lower())
    raw = recompute(grid, report_year, 1.0)

    def ok(s):
        return raw is not None and adopted is not None and abs(raw / s - adopted) <= max(0.5, 0.05 * abs(adopted))
    if stated and (ok(stated) or raw is None or adopted is None):
        return stated, "stated units"
    for s in (1000.0, 1.0, 1e6, 0.001):
        if ok(s) and abs(raw) / s > 0.0:
            return s, "inferred: the grid reproduces the adopted figure at this scale (stated %r)" % grid.get("units")
    return stated, "stated units (the grid reproduces the adopted figure at no scale)"


def recompute(grid, report_year, scale=None):
    """The adopted figure recomputed from the grid: latest less previous over underwriting years up to t-2, to
    millions. (A check that the grid is the figure's source, not the estimator; it may differ where the estimator
    cleans a grid.)"""
    scale = scale or UNITS.get(str(grid.get("units") or "").lower())
    if not scale:
        return None
    tot, n = 0.0, 0
    for y, last, prev in latest_cells(grid):
        try:
            yi = int(str(y)[:4])
        except ValueError:
            continue
        if yi <= report_year - 2 and prev is not None:
            tot += last - prev
            n += 1
    return round(tot / scale, 3) if n else None


def grid_values(grid):
    return {round(abs(float(v)), 1) for r in (grid.get("development_rows") or []) for v in r
            if v is not None and abs(float(v)) >= MIN_CELL}


def locate(filing, grid):
    """The page(s) holding the most of the grid's distinct cells, and the used table's line cluster there."""
    vals = grid_values(grid)
    if len(vals) < 3:
        return {"located": False, "why": "the grid has fewer than three distinct cells of %g or more" % MIN_CELL}
    hits = {}
    for p, lines in filing.pages.items():
        hits[p] = {round(abs(a), 1) for ln in lines for a in ln.amts} & vals
    if not hits:
        return {"located": False, "why": "no filing text"}
    need = max(3, (len(vals) + 1) // 2)
    best = max(sorted(hits), key=lambda p: (len(hits[p]), -p))
    pages = [best]
    if len(hits[best]) < need:
        pair = max(((p, p + 1) for p in hits if p + 1 in hits), key=lambda q: len(hits[q[0]] | hits[q[1]]),
                   default=None)
        if pair and len(hits[pair[0]] | hits[pair[1]]) >= need:
            pages = list(pair)
    found = set().union(*(hits[p] for p in pages))
    if len(found) < need:
        how = Counter(filing.how.values())
        return {"located": False, "matched": len(found), "distinct_cells": len(vals), "best_page": best,
                "why": "the grid's cells are not in the filing's text (best page %d holds %d of %d; pages: %s)"
                       % (best, len(found), len(vals), dict(how))}
    # the cluster of table lines on the last page that holds the table
    last_page = pages[-1]
    lines = filing.pages[last_page]
    is_tab = []
    for ln in lines:
        m = sum(1 for a in ln.amts if round(abs(a), 1) in vals)
        is_tab.append(m >= 1 and m * 2 >= len(ln.amts))
    # a cluster is broken by a gap of more than six lines, or by a separator between two table lines: a year-header
    # line, or a gross / net heading with no amounts (two tables stacked close, sharing some cells)
    def separator(ln):
        return (len(set(years_in(ln.text))) >= 3 and len(ln.amts) <= 1) or \
            (not ln.amts and BASIS_KW.search(ln.text) and not PAID_KW.search(ln.text))
    clusters, cur = [], []
    for k, t in enumerate(is_tab):
        if t:
            if cur and (k - cur[-1] > 6 or any(separator(lines[i]) for i in range(cur[-1] + 1, k))):
                clusters.append(cur)
                cur = []
            cur.append(k)
    if cur:
        clusters.append(cur)
    if not clusters:
        return {"located": False, "why": "no table lines on page %d" % last_page}

    def weight(c):
        return len({round(abs(a), 1) for k in c for a in lines[k].amts} & vals)
    cl = max(clusters, key=weight)
    return {"located": True, "pages": pages, "matched": len(found), "distinct_cells": len(vals),
            "page_text": [filing.how[p] for p in pages], "first_line": cl[0], "last_line": cl[-1]}


def block_lines(filing, loc):
    """The lines after the used table's development rows, up to the next table's start: a year-header line, or a new
    development table's first row that does not follow a paid marker. Runs on to the next page when the table ends its
    page with no next table on it."""
    out = []
    page = loc["pages"][-1]
    start = loc["last_line"] + 1
    for p in (page, page + 1):
        if p not in filing.pages:
            break
        lines = filing.pages[p]
        in_paid = False
        k0 = start if p == page else 0
        stopped = False
        for k in range(k0, len(lines)):
            ln = lines[k]
            if PAID_KW.search(ln.label or ln.text):
                in_paid = True
            elif ln.amts and TOTAL_KW.search(ln.label):
                in_paid = False
            yh = len(set(years_in(ln.text))) >= 3 and len(ln.amts) <= 1
            ds = bool(DEVSTART.search(ln.label or "")) and not in_paid
            ah = len(AGE_HEAD.findall(ln.text)) >= 3
            # a gross / net heading with no amounts starts the next table when a table heading follows it within
            # three lines with no amounts between (a heading followed by amounts is a wrapped label, not a table's)
            nxt = []
            for x in lines[k + 1:k + 4]:
                nxt.append(x)
                if x.amts:
                    break
            bh = (not ln.amts and BASIS_KW.search(ln.text) and not PAID_KW.search(ln.text)
                  and any(len(set(years_in(x.text))) >= 3 or len(AGE_HEAD.findall(x.text)) >= 3
                          or DEVSTART.search(x.label or "") for x in nxt)
                  and not any(x.amts and not (len(set(years_in(x.text))) >= 3 and len(x.amts) <= 1)
                              and not DEVSTART.search(x.label or "") for x in nxt))
            if yh or ds or ah or bh:
                stopped = True
                break
            if p != page and NOTE_HEAD.search(ln.text) and not re.search(r"continued", ln.text, re.I):
                stopped = True
                break
            out.append(ln)
            if p != page and len(out) > 30:
                stopped = True
                break
        if stopped:
            break
    return out


def candidates(block):
    """The used table's own totals: each total-like line's last amount, and the sum of its amounts when it prints three
    or more of one sign and no total column (its last amount is not the sum of the others). A line is total-like when
    its label (with the label words wrapped onto the lines just above it) names a reserve, outstanding, balance,
    liability, provision, financial position or total, or, with no label at all (an OCR page prints labels apart), when
    it is a single amount or a row of amounts. Each candidate carries all the line's amounts, so that a line printing
    both bases (gross, reinsurers' share, net) can be bound to neither."""
    out = []
    for k, ln in enumerate(block):
        if not ln.amts:
            continue
        ctx = [ln.label]
        for prev in reversed(block[max(0, k - 4):k]):
            if prev.amts:
                break
            ctx.insert(0, prev.text)
        bare = not re.search(r"[A-Za-z]", ln.label) and not any(re.search(r"[A-Za-z]", c) for c in ctx[:-1])
        if PAID_KW.search(ln.label):
            continue          # a paid row is never a reserve total
        # a label wrapped around its amounts runs on to the line below ("Gross claims / <amounts> / reserve"), for a
        # line that has no label of its own
        if not re.search(r"[A-Za-z]", ln.label) and k + 1 < len(block) and not block[k + 1].amts \
                and len(block[k + 1].text.split()) <= 4:
            ctx.append(block[k + 1].text)
        labelled = bool(TOTAL_KW.search(" ".join(ctx)))
        if years_in(ln.label) and not re.search(r"[A-Za-z]", ln.label) and not labelled:
            continue          # an underwriting year's row of a table, not a total
        if not (labelled or bare):
            continue
        a = ln.amts
        vals = [("last", a[-1])]
        if len(a) >= 3 and (all(x > 0 for x in a) or all(x < 0 for x in a)) \
                and not near(abs(a[-1]), abs(sum(a[:-1])), 0.002):
            vals.append(("sum", sum(a)))
        for how, v in vals:
            if abs(v) > 0:
                out.append({"value": abs(v), "how": how, "labelled": labelled, "line": ln.text[:160], "page": ln.page,
                            "line_no": ln.idx, "single": len(a) == 1, "line_values": [abs(x) for x in a]})
    return out


def paid_total(filing, loc, block, grid):
    """The used table's latest cumulative paid, summed (grid units), so that its latest diagonal less paid is its
    reserve: (a) a paid amount printed at the end of each underwriting year's row (bracketed, after the row's latest
    cell), one for each of the grid's underwriting years, or (b) the first paid / payments line in the block with
    exactly one amount per underwriting year of the grid (and perhaps their total), all of one sign. A paid line that
    covers other years than the grid (a prior-years column the grid does not store) is not used.
    Returns (paid, how, line) or None."""
    latest = {round(abs(c[1]), 1) for c in latest_cells(grid)}
    n_years = len(latest_cells(grid))
    lines = filing.pages[loc["pages"][-1]][loc["first_line"]:loc["last_line"] + 1]
    row_paid = []
    for ln in lines:
        a = ln.amts
        if len(a) >= 2 and a[-1] < 0 and round(abs(a[-2]), 1) in latest:
            row_paid.append(abs(a[-1]))
    if n_years >= 3 and len(row_paid) == n_years:
        return sum(row_paid), "a paid amount at the end of each underwriting year's row (%d rows)" % len(row_paid), None
    for k, ln in enumerate(block):
        ctx = " ".join([x.text for x in block[max(0, k - 2):k] if not x.amts] + [ln.label])
        a = ln.amts
        if PAID_KW.search(ctx) and n_years >= 3 and len(a) >= n_years \
                and (all(x > 0 for x in a) or all(x < 0 for x in a)):
            vals = a[:-1] if (len(a) == n_years + 1 and near(abs(a[-1]), abs(sum(a[:-1])), 0.002)) else a
            if len(vals) != n_years:
                return None   # the paid line covers other years (a prior-years column) than the grid
            return sum(abs(x) for x in vals), "the block's paid line", ln.text[:160]
    return None


def both_bases_lines(block):
    """Lines of the block printing gross, reinsurers' share (bracketed) and net, gross less the share being net:
    (gross, net, line)."""
    out = []
    for ln in block:
        for a, b, c in triples(ln):
            if b < 0:
                out.append((a, c, ln.text[:160]))
                break
    return out


# --- the filing's claims outstanding -----------------------------------------------------------------------------------

def near(x, y, tol):
    return y is not None and x is not None and abs(x - y) <= tol * abs(y)


def consistent_triple(a, b, c):
    return a > 0 and c >= 0 and abs(b) <= a and abs(a - abs(b) - c) <= TRIPLE_TOL * a + 1.0


def triples(ln):
    a = ln.amts
    return [(a[i], a[i + 1], a[i + 2]) for i in range(len(a) - 2) if consistent_triple(a[i], a[i + 1], a[i + 2])]


def scale_for(x, anchors):
    """The scale s at which the printed amount x, divided by s, is one of the anchors (millions)."""
    for s in SCALES:
        for v in anchors:
            if v and near(abs(x) / s, v, ANCHOR_TOL):
                return s, v
    return None, None


def place_claims_outstanding(filing, opening, next_opening, report_year):
    """CO_g and CO_n at 31 December of the report year (millions), each with where it was read."""
    gross, net = [], []
    all_lines = list(filing.lines())
    by_page = filing.pages
    for ln in all_lines:
        # (1) a movement table's opening line (gross, reinsurers' share, net) carrying the opening reserves; its closing
        #     line follows within 15 lines
        for a, b, c in triples(ln):
            s, _v = scale_for(a, opening)
            if s and not (CLOSE_KW.search(ln.text) and not OPEN_KW.search(ln.text)):
                # (a closing line carrying the opening reserves is the comparative year's, not an opening line)
                follow = by_page[ln.page][ln.idx + 1:ln.idx + 16]
                if len(follow) < 15 and ln.page + 1 in by_page:
                    follow = follow + by_page[ln.page + 1][:15 - len(follow)]
                for f in follow:
                    if OPEN_KW.search(f.text) and not CLOSE_KW.search(f.text):
                        break
                    ts = triples(f)
                    if ts and CLOSE_KW.search(f.text):
                        x, y, z = ts[0]
                        if not near(x / s, a / s, 1e-6):
                            gross.append((x / s, "movement closing line, opening anchored", f))
                            net.append((z / s, "movement closing line, opening anchored", f))
                        break
            # (2) a closing triple carrying the next report's opening reserves
            s2, _v2 = scale_for(a, next_opening)
            if s2:
                gross.append((a / s2, "gross / reinsurers' share / net line carrying the next report's opening", ln))
                net.append((c / s2, "gross / reinsurers' share / net line carrying the next report's opening", ln))
        # (3) a two-column statement line (this year, last year) whose last-year column is the opening reserves
        if CO_LABEL.search(ln.label) and not RI_KW.search(ln.label) and not re.search(r"\bnet\b", ln.label, re.I):
            a = ln.amts
            for j in range(1, len(a)):
                s, _v = scale_for(a[j], opening)
                if s and a[j - 1] > 0 and a[j - 1] / s > 0.2 * (a[j] / s) and not near(a[j - 1], a[j], 1e-9):
                    gross.append((a[j - 1] / s, "claims outstanding line, last-year column is the opening reserves", ln))
                    break
            for j in range(len(a)):
                s, _v = scale_for(a[j], next_opening)
                if s and a[j] > 0:
                    gross.append((a[j] / s, "claims outstanding line carrying the next report's opening", ln))
                    break
    g = consensus(gross)
    n = None
    if g:
        # the net printed on the same line as the agreed gross
        n = consensus([x for x in net if any(x[2] is ln for ln in g["lines"])])
        if n is None:
            n = place_net_from_parts(all_lines, g["value"], opening)
    return g, n


def place_net_from_parts(all_lines, co_g, opening):
    """Net = gross less the reinsurers' share of claims outstanding, from (a) a gross / reinsurers' share / net triple
    whose gross is CO_g, (b) a vertical gross, reinsurers' share, net layout, or (c) the balance sheet's reinsurers'
    share of claims outstanding (its last-year column below the opening reserves)."""
    found = []
    for ln in all_lines:
        for a, b, c in triples(ln):
            for s in SCALES:
                if near(a / s, co_g, 0.002):
                    found.append((c / s, "gross / reinsurers' share / net line whose gross is CO_g", ln))
    if found:
        return consensus(found)
    pages = {}
    for ln in all_lines:
        pages.setdefault(ln.page, []).append(ln)
    for p, lines in pages.items():
        for k, ln in enumerate(lines):
            if not ln.amts:
                continue
            for s in SCALES:
                if not near(ln.amts[0] / s, co_g, 0.002):
                    continue
                nxt = [x for x in lines[k + 1:k + 6] if x.amts]
                for i in range(len(nxt)):
                    for j in range(i + 1, len(nxt)):
                        r, c = nxt[i].amts[0], nxt[j].amts[0]
                        if RI_KW.search(nxt[i].text) and abs(ln.amts[0] - abs(r) - c) <= TRIPLE_TOL * ln.amts[0] + 1:
                            found.append((c / s, "gross, reinsurers' share, net printed one under another", nxt[j]))
    if found:
        return consensus(found)
    for p, lines in pages.items():
        for k, ln in enumerate(lines):
            if not (RI_CO.search(ln.label) and not RI_NOT.search(ln.label) and len(ln.amts) >= 2):
                continue
            above = " ".join(x.text for x in lines[max(0, k - 6):k + 1])
            if not RI_KW.search(above):
                continue
            a = ln.amts
            for j in range(1, len(a)):
                for s in SCALES:
                    r_t, r_prev = abs(a[j - 1]) / s, abs(a[j]) / s
                    if (0 < r_t < co_g and not near(r_t, co_g, TOL) and any(o and r_prev < o and not near(r_prev, o, TOL)
                                                                           for o in opening)
                            and 0.02 * co_g < r_t < 0.98 * co_g and r_prev > 0.02 * max(o for o in opening if o)):
                        if s == SCALES[0] or r_t > 1:
                            found.append((co_g - r_t, "balance sheet: CO_g less the reinsurers' share of claims "
                                                      "outstanding", ln))
                            break
                else:
                    continue
                break
    return consensus(found) if found else None


def consensus(cands):
    """The value most sources agree on (within 0.5%); ties go to the first found."""
    if not cands:
        return None
    groups = []
    for v, why, ln in cands:
        for g in groups:
            if near(v, g["value"], 0.005):
                g["n"] += 1
                g["sources"].append("%s (p%d: %s)" % (why, ln.page, ln.text[:120]))
                g["lines"].append(ln)
                break
        else:
            groups.append({"value": v, "n": 1, "sources": ["%s (p%d: %s)" % (why, ln.page, ln.text[:120])],
                           "lines": [ln]})
    groups.sort(key=lambda g: -g["n"])
    best = groups[0]
    return {"value": round(best["value"], 4), "n_sources": best["n"], "sources": best["sources"][:4],
            "lines": best["lines"], "alternatives": [round(g["value"], 4) for g in groups[1:4]]}


def place_latest_totals(filing, co_g, co_n):
    """I_g and I_n: a filing's own total of gross and net latest estimates, printed in a summary whose claims
    liabilities line carries CO_g and CO_n (e.g. 4020/2017 p42 'Total claims 1,935,876 1,596,671'), checked by
    the summary's paid line (total less paid is the liability)."""
    if co_g is None or co_n is None:
        return None
    for p, lines in filing.pages.items():
        for k, ln in enumerate(lines):
            a = ln.amts
            for s in SCALES:
                pos = [i for i in range(len(a) - 1) if near(abs(a[i]) / s, co_g, 0.002) and near(abs(a[i + 1]) / s, co_n, 0.002)]
                if not pos:
                    continue
                i = pos[0]
                above = lines[max(0, k - 4):k]
                paid = [x for x in above if PAID_KW.search(x.text) and len(x.amts) >= i + 2]
                for x in above:
                    if PAID_KW.search(x.text) or len(x.amts) < i + 2:
                        continue
                    tg, tn = abs(x.amts[i]) / s, abs(x.amts[i + 1]) / s
                    for pl in paid:
                        pg, pn = abs(pl.amts[i]) / s, abs(pl.amts[i + 1]) / s
                        if near(tg - pg, co_g, 0.005) and near(tn - pn, co_n, 0.005):
                            return {"I_g": round(tg, 4), "I_n": round(tn, 4), "page": p,
                                    "lines": [x.text[:160], pl.text[:160], ln.text[:160]]}
    return None


# --- the rule ------------------------------------------------------------------------------------------------------------

def reconcile(x, own, other):
    """x reconciles to own: within 2% of it and nearer it than the other basis's figure."""
    if own is None or not near(x, own, TOL):
        return False
    return other is None or abs(x - own) < abs(x - other)


def classify(t):
    """The class from placed totals (millions): t has located, co_g, co_n, cands (list of {value, labelled, line}),
    d_used, i_g, i_n. Returns (class, reason, detail)."""
    if not t.get("located"):
        return "D", "the used table is not located: %s" % t.get("locate_why", ""), {}
    co_g, co_n, i_g, i_n, d = t.get("co_g"), t.get("co_n"), t.get("i_g"), t.get("i_n"), t.get("d_used")
    cands = t.get("cands") or []
    if co_g is None and i_g is None:
        return "D", "the filing's gross claims outstanding at the report date is not placed", {}
    g_hits = [c for c in cands if reconcile(c["value"], co_g, co_n)]
    n_hits = [c for c in cands if co_n is not None and reconcile(c["value"], co_n, co_g)]
    # a line printing both bases (a summary under one table, or gross / reinsurers' share / net) binds to neither
    both_lines = {c["line"] for c in g_hits} & {c["line"] for c in n_hits}
    for c in cands:
        lv = c.get("line_values") or []
        if co_g is not None and co_n is not None and any(near(v, co_g, TOL) for v in lv) and any(near(v, co_n, TOL) for v in lv):
            both_lines.add(c["line"])
    g_hits = [c for c in g_hits if c["line"] not in both_lines]
    n_hits = [c for c in n_hits if c["line"] not in both_lines]
    d_g = d is not None and i_g is not None and reconcile(d, i_g, i_n)
    d_n = d is not None and i_n is not None and reconcile(d, i_n, i_g)
    # the latest diagonal less the latest paid is the table's reserve: against CO_g / CO_n, and against the gross and
    # net columns of a gross / reinsurers' share / net line printed under the table
    r = t.get("d_less_paid")
    pairs = [(co_g, co_n)] + [(p["gross"], p["net"]) for p in t.get("both_bases_lines") or []]
    r_g = r is not None and any(g is not None and reconcile(r, g, n) for g, n in pairs)
    r_n = r is not None and any(n is not None and reconcile(r, n, g) for g, n in pairs)
    gross = bool(g_hits) or d_g or r_g
    netb = bool(n_hits) or d_n or r_n
    detail = {"gross_hits": g_hits[:3], "net_hits": n_hits[:3], "diagonal_to_I_g": d_g, "diagonal_to_I_n": d_n,
              "diagonal_less_paid_to_gross": r_g, "diagonal_less_paid_to_net": r_n}
    indist = co_g is not None and co_n is not None and abs(co_g - co_n) <= INDISTINCT * abs(co_g)
    if indist and (gross or netb or any(near(c["value"], co_g, TOL) or near(c["value"], co_n, TOL) for c in cands)):
        return "A", "gross and net claims outstanding are indistinguishable (within 4%), and the table reconciles to them", detail
    if gross and netb:
        return "D", "a total reconciles to gross and another to net within the used table's block", detail
    if gross:
        if i_g is not None and d is not None and not d_g:
            return ("C", "the table reconciles to gross claims outstanding, but its latest diagonal %.3f does not "
                         "reconcile to the filing's own gross total of latest estimates %.3f" % (d, i_g), detail)
        return "A", ("the used table's total reconciles to gross" if g_hits else
                     "the used table's latest diagonal reconciles to the filing's gross total of latest estimates"
                     if d_g else "the used table's latest diagonal less its paid reconciles to gross"), detail
    if netb:
        return "B", ("the used table's total reconciles to net claims outstanding, not gross" if n_hits else
                     "the used table's latest diagonal reconciles to the filing's net total of latest estimates, "
                     "not gross" if d_n else "the used table's latest diagonal less its paid reconciles to net, not "
                     "gross"), detail
    printed = [c for c in cands if c["labelled"] or c.get("single")] + ([r] if r is not None else [])
    if i_g is not None and d is not None:
        return ("C", "the used table's latest diagonal %.3f reconciles to neither the filing's gross (%.3f) nor its "
                     "net (%s) total of latest estimates" % (d, i_g, i_n), detail)
    if not printed:
        return "D", "the used table prints no total in its block, and the filing prints no total of latest estimates", detail
    if co_n is None:
        return ("D", "the used table's totals do not reconcile to gross claims outstanding, and the net claims "
                     "outstanding is not placed (net or faulty cannot be told)", detail)
    return ("C", "the used table's totals reconcile to neither gross (%.3f) nor net (%.3f) claims outstanding"
            % (co_g, co_n), detail)


# --- the population and each record ---------------------------------------------------------------------------------

def load(p):
    return json.load(io.open(str(p), encoding="utf-8"))


def used_grid(data, ck, route_source):
    m = data["models"][ck]
    if route_source == "code_triangle":
        return m.get("_claims_triangle") or m.get("_rag_triangle"), "_claims_triangle"
    if m.get("_rag_triangle"):
        return m["_rag_triangle"], "_rag_triangle"
    for k in sorted(data["models"]):
        if data["models"][k].get("_rag_triangle"):
            return data["models"][k]["_rag_triangle"], "_rag_triangle (model %s)" % k
    return m.get("_claims_triangle"), "_claims_triangle"


def openings(data, brief):
    vals = [brief.get("adopted_opening_reserves_m_report_currency")]
    for m in (data.get("models") or {}).values():
        vals.append(m.get("opening_reserves_gbp_m"))
    return sorted({round(float(v), 4) for v in vals if v})


def next_openings(stem):
    syn, yr = stem.replace("syndicate_", "").split("_")
    nxt = "syndicate_%s_%d" % (syn, int(yr) + 1)
    for d in (AN / "pdf_extraction", EXTRACTION / "pdf_extraction"):
        p = d / ("%s.json" % nxt)
        if p.exists():
            data = load(p)
            return nxt, sorted({round(float(m.get("opening_reserves_gbp_m")), 4)
                                for m in (data.get("models") or {}).values() if m.get("opening_reserves_gbp_m")})
    return None, []


def read_status():
    frame = load(FOURTH / "error-rate-frame-fourth.json")
    sample = load(FOURTH / "error-rate-sample-fourth.json")
    status = {}
    for s in frame["F_frame"]["stems"]:
        status[s] = "unread (draw four's frame, not drawn)"
    for r in frame["K_checked"]["records"]:
        status[r["stem"]] = "read earlier (latest figure verdict: %s)" % r["latest_figure_verdict"]
    for r in frame["C_census"]["records"]:
        status[r["stem"]] = "read earlier, final figure unchecked (draw four's census stratum)"
    census = {r["stem"] for r in frame["C_census"]["records"]}
    for r in sample["records"]:
        s = r["stem"]
        status[s] = ("draw four, census stratum (two readings)" if s in census else "draw four, random sample")
    return status


def scan_record(stem, brief, loader_route, eye=None):
    data = load(AN / "pdf_extraction" / ("%s.json" % stem))
    import draw_error_rate_fourth as d4
    ck = d4.canonical(data)
    grid, grid_field = used_grid(data, ck, loader_route)
    t = {"stem": stem, "route": loader_route, "canonical_model": ck, "grid_field": grid_field,
         "adopted_m": brief.get("adopted_prior_year_development_m_report_currency"),
         "opening_m": brief.get("adopted_opening_reserves_m_report_currency"),
         "report_currency": brief.get("report_currency"), "route_triangle_page": (brief.get("route") or {}).get(
             "triangle_source_page"), "grid_source_page": (grid or {}).get("source_page"),
         "grid_type": (grid or {}).get("type"), "grid_units": (grid or {}).get("units")}
    year = int(stem.split("_")[2])
    if loader_route == "confirmed_figure":
        reg = d4.ra.load_pyd_confirmed_figures().get(stem.replace("syndicate_", "")) or {}
        t["register_pages"] = reg.get("pages")
    filing = Filing(stem)
    t["filing"] = None if filing.path is None else str(filing.path).replace("\\", "/")
    t["filing_kind"] = filing.kind
    if grid:
        scale, t["grid_scale_how"] = grid_scale(grid, year, t["adopted_m"])
        t["grid_scale"] = scale
        t["recomputed_m"] = recompute(grid, year, scale)
        tol = max(0.5, 0.05 * abs(t["adopted_m"] or 0))
        t["grid_reproduces_adopted"] = (t["recomputed_m"] is not None and t["adopted_m"] is not None
                                        and abs(t["recomputed_m"] - t["adopted_m"]) <= tol)
        lc = latest_cells(grid)
        t["d_used"] = round(sum(c[1] for c in lc) / scale, 4) if scale and lc else None
    else:
        t["recomputed_m"], t["grid_reproduces_adopted"], t["d_used"], scale = None, False, None, None
    if filing.path is None:
        t.update(located=False, locate_why="no filing on disk")
    elif not grid:
        t.update(located=False, locate_why="no stored grid")
    else:
        loc = locate(filing, grid)
        t["located"] = loc["located"]
        t["locate"] = {k: v for k, v in loc.items() if k != "located"}
        if not loc["located"]:
            t["locate_why"] = loc["why"]
        elif scale:
            blk = block_lines(filing, loc)
            cs = candidates(blk)
            for c in cs:
                c["value"] = round(c["value"] / scale, 4)
                c["line_values"] = [round(v / scale, 4) for v in c["line_values"]]
            t["cands"] = cs
            t["block_pages"] = sorted({ln.page for ln in blk}) or loc["pages"]
            pt = paid_total(filing, loc, blk, grid)
            if pt and t.get("d_used") is not None:
                t["paid_m"], t["paid_how"], t["paid_line"] = round(pt[0] / scale, 4), pt[1], pt[2]
                t["d_less_paid"] = round(t["d_used"] - pt[0] / scale, 4)
            t["both_bases_lines"] = [{"gross": round(g / scale, 4), "net": round(n / scale, 4), "line": l}
                                     for g, n, l in both_bases_lines(blk)]
        else:
            t["located"], t["locate_why"] = False, "the grid's units are not stated (%r)" % grid.get("units")
    op = openings(data, brief)
    nxt, nop = next_openings(stem)
    t["opening_anchors_m"], t["next_report"], t["next_opening_anchors_m"] = op, nxt, nop
    if filing.path is not None:
        g, n = place_claims_outstanding(filing, op, nop, year)
        t["co_g"] = g["value"] if g else None
        t["co_n"] = n["value"] if n else None
        t["co_g_where"] = None if not g else {k: v for k, v in g.items() if k != "lines"}
        t["co_n_where"] = None if not n else {k: v for k, v in n.items() if k != "lines"}
        lt = place_latest_totals(filing, t["co_g"], t["co_n"])
        t["i_g"], t["i_n"] = (lt["I_g"], lt["I_n"]) if lt else (None, None)
        t["latest_totals_where"] = lt
    t["placed_by_eye"] = False
    if eye:
        t["placed_by_eye"] = True
        t["eye"] = eye
        for k in ("co_g", "co_n", "i_g", "i_n", "d_used"):
            if k in eye:
                t[k] = eye[k]
        if "cands" in eye:
            t["cands"] = [dict(c, labelled=True, single=True, line=c.get("line", "placed by eye"))
                          for c in eye["cands"]]
        if "located" in eye:
            t["located"] = eye["located"]
            if eye["located"]:
                t.pop("locate_why", None)
            else:
                t["locate_why"] = eye.get("locate_why", "placed by eye: not located")
    cls, why, detail = classify(t)
    t["class"], t["reason"], t["detail"] = cls, why, detail
    t["page_text_kinds"] = dict(Counter(filing.how.values())) if filing.path is not None else {}
    return t


def population():
    import draw_error_rate_fourth as d4
    loader = d4.Loader()
    W = d4.working_sample()
    overruled = d4.ser.overruled_stems()
    pop = []
    for s in W:
        b = loader.brief(s)
        src, why = d4.figure_source(b, overruled)
        if src == "triangle":
            pop.append((s, b, (b["route"] or {}).get("source")))
    return W, pop


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--stems", nargs="*")
    ap.add_argument("--print", action="store_true")
    a = ap.parse_args(argv)
    if os.environ.get("LLOYDS_EXTRACTION_OFFLINE") != "1":
        raise SystemExit("set LLOYDS_EXTRACTION_OFFLINE=1")
    W, pop = population()
    eye = load(EYE) if EYE.exists() else {}
    eye = {k: v for k, v in eye.items() if not k.startswith("_")}
    status = read_status()
    todo = [p for p in pop if not a.stems or p[0] in a.stems]
    rows = []
    for i, (s, b, route) in enumerate(todo):
        t = scan_record(s, b, route, eye.get(s))
        t["reading_status"] = status.get(s, "not in draw four's frame files")
        rows.append(t)
        if a.print:
            print("%-22s %s  %s | adopted %s recomputed %s | D %s | CO_g %s CO_n %s | I %s %s | pages %s"
                  % (s, t["class"], t["reason"][:150], t["adopted_m"], t.get("recomputed_m"), t.get("d_used"),
                     t.get("co_g"), t.get("co_n"), t.get("i_g"), t.get("i_n"),
                     (t.get("locate") or {}).get("pages")))
        elif (i + 1) % 50 == 0:
            print("%d of %d" % (i + 1, len(todo)), flush=True)
    if a.stems:
        return rows
    out = {
        "protocol": "protocol/error-rate-protocol-table-scan.md (the fourteenth amendment)",
        "computed": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
        "analysis_commit": subprocess.run(["git", "-C", str(AN), "rev-parse", "HEAD"], capture_output=True,
                                          text=True).stdout.strip(),
        "extraction_commit": subprocess.run(["git", "-C", str(EXTRACTION), "rev-parse", "HEAD"], capture_output=True,
                                            text=True).stdout.strip(),
        "working_sample": len(W),
        "population": {"n": len(pop), "by_route": dict(Counter(p[2] for p in pop))},
        "tolerance": TOL, "indistinguishable_within": INDISTINCT,
        "counts": dict(sorted(Counter(t["class"] for t in rows).items())),
        "counts_placed_by_eye": dict(sorted(Counter(t["class"] for t in rows if t["placed_by_eye"]).items())),
        "counts_by_reading_status": {c: dict(Counter(t["reading_status"].split(" (")[0] for t in rows if t["class"] == c))
                                     for c in "ABCD"},
        "records": rows,
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    io.open(str(OUT), "w", encoding="utf-8", newline="\n").write(json.dumps(out, indent=1, ensure_ascii=False) + "\n")
    print("population %d: %s -> %s" % (len(rows), out["counts"], OUT.relative_to(AN)))
    return rows


if __name__ == "__main__":
    main()
