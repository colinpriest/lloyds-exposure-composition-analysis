"""The share of a record's gross reserves held outside the years its triangle develops: an "X and prior" bucket printed
as a reserve with no development of its own, or older years the table leaves out (the adjudication of 22 October 2026,
Q5; results/extraction_error_rate/mature-cohort/adjudication.md).

Equation (1) sums the movement over every underwriting year u <= t-2, and its denominator R holds every year's reserves.
A bucket printed as a reserve without development is inside R and outside the movement, so it pulls |S| towards zero by
up to its share. The share measured here is

    share = 1 - (gross reserves of the years the stored grid develops) / CO_g,

with CO_g the filing's gross claims outstanding as the triangle-table census placed it. It is a script measure, not a
reading. Every method reads only stored data (the census and its eye placements, the stored grid, the adjudication's
population measures), and none calls an API. A record's share is the first of these, in this order (PRECEDENCE), that
measures it; the others that also measure it are kept beside it, as a cross-check:

  reading            a reader's share among the 86 restored and entering records, as the adjudication lists it (Q5);
  developed_column   the stored grid itself develops an older-years column ("2010 and prior", ...): share 0;
  design_dlp         the design's measure (measures/measure_pop.py, pop_measures.json): the table's latest diagonal less its
                     payments, against CO_g, kept where a reader placed the diagonal less paid, or where the census's
                     paid line is a gross payments line with one cell for each of the grid's years (design_dlp_basis),
                     and the result lies in [-2%, 100%]. Where it and the reserve line both measure and disagree, they
                     are reconciled year by year (reconcile_by_year): an older-years amount folded into the oldest
                     cell keeps it, a disagreement on another year drops it;
  eye_bucket         the census's eye placement writes the table's total as "total X + ... prior years Y": share
                     Y / (X + Y);
  reserve_line       a reserve line printed by underwriting year (the census's reconciling gross line, or its "paid"
                     line where that line is in fact a reserve line), aligned with the stored grid's years: the cells
                     beyond the grid's years are outside it. The line's cells are read from its own text (dashes are
                     empty cells), oldest first or newest first, whichever ordering keeps every developed year's reserve
                     within its latest incurred estimate; where both do and disagree, the reserve-to-incurred pattern
                     decides or nothing does (reserve_line_share);
  bucket_line        a line naming the older years ("2010 and prior", "provision in respect of prior years") labelled as a
                     reserve, with one amount in the table's units: share amount / CO_g.

A share in [-2%, 0) is read as 0 (the census's own 2% reconciliation tolerance). A record no method measures is listed
with its reasons (REASONS). measure_all() returns one row per record and distribution() the counts.
"""
import io
import json
import re

import numpy as np

#: the readers' shares among the 86 the adjudication names (Q5: "780/2016 65%, 3000/2016 29%, ..."); the 13 it gives
#: only as "under 5%" are not listed by record there, so are not used
READER_SHARES = {"780_2016": 0.65, "3000_2016": 0.29, "2003_2016": 0.28, "1084_2015": 0.17, "2001_2016": 0.15,
                 "2525_2016": 0.13, "1221_2023": 0.09, "2010_2020": 0.07, "2987_2021": 0.06, "2010_2023": 0.055,
                 "2987_2023": 0.054, "1084_2024": 0.053}
TOL = 0.02
#: an older-years label in a grid's underwriting-year list (measures/classify_pop.py's GROUP)
GROUP = re.compile(r"\b(?:prior|pre|earlier|older|before|ae)\b|&\s*P\b", re.I)
#: a line's words saying it is a reserve line, not a payments line
RESERVE_WORDS = re.compile(r"reserve|provision|outstanding|balance to pay|liabilit|claims at|unpaid", re.I)
PAID_WORDS = re.compile(r"paid|payment", re.I)
NET = re.compile(r"\bnet\b", re.I)
#: the eye placements' bracketed decomposition: "[= <...> total X + <...> prior years Y]"
EYE_BUCKET = re.compile(r"\[\s*=.*?total\s*\(?([\d,]+(?:\.\d+)?)\)?\s*\+.*?(?:prior|earlier|pre-?\d{4}).*?"
                        r"\(?([\d,]+(?:\.\d+)?)\)?\s*\]", re.I)
BUCKET_LINE = re.compile(r"(?:prior|earlier)", re.I)
NUM = re.compile(r"^\(?-?[\d,]*\d(?:\.\d+)?\)?$")
DASH = re.compile(r"^[-–—]$")
#: the order in which the methods decide a record's share
PRECEDENCE = ("reading", "developed_column", "design_dlp", "eye_bucket", "reserve_line", "bucket_line")
#: why a record is not measured, by code
REASONS = {
    "not_in_census": "not in the census or the design's scan of the restored grids",
    "no_co_g": "no gross claims outstanding placed",
    "line_text": "the reserve line's text does not end with the census's amounts",
    "fewer_cells": "the reserve line has fewer year cells than the stored grid has years",
    "no_ordering": "neither ordering of the reserve line keeps every developed year within its latest incurred estimate",
    "ambiguous_ordering": "both orderings of the reserve line fit and give different shares, and neither is clearer",
    "line_out_of_range": "the reserve line gives a share outside [-2%, 100%]",
    "dlp_not_payments": ("the design's diagonal-less-paid measure was not placed by a reader and rests on a line that is "
                         "not a gross payments line of the grid's years, or falls outside [-2%, 100%]"),
    "dlp_years_disagree": ("the design's diagonal-less-paid measure and the reserve line disagree on a year other than "
                           "the oldest: the payments line or the grid is misread there"),
    "bucket_unplaced": "an older-years line is printed but carries no single reserve amount the script can place",
    "single_total": "the table's reconciling total is a single amount: the reserves by year were not placed",
    "no_total": "the census placed no reconciling gross total for the table",
}
#: how much clearer one ordering's reserve-to-incurred pattern must be than the other's to decide between them
ORDER_MARGIN = 0.5


def _num(tok):
    t = tok.replace(",", "")
    neg = t.startswith("(") and t.endswith(")")
    t = t.strip("()")
    v = float(t)
    return -v if neg else v


def line_cells(line, values):
    """The line's trailing cells, in order: each a number in millions or None for a dash, ending with the census's
    `values` (its parsed amounts, in millions). Returns (cells, scale), or (None, None) when the text does not end with
    those amounts at one scale."""
    toks = line.replace("–", " – ").split()
    want = [float(v) for v in values]
    if not want:
        return None, None
    cells, scale, j = [], None, len(want) - 1
    for tok in reversed(toks):
        if DASH.match(tok):
            cells.append(None)
            continue
        if not NUM.match(tok) or j < 0:
            break
        raw = abs(_num(tok))
        target = abs(want[j])
        if target == 0:
            if raw != 0:
                break
        else:
            s = raw / target
            if scale is None:
                scale = s
            if abs(s - scale) > 1e-6 * max(1.0, scale):
                break
        cells.append(want[j])
        j -= 1
    if j >= 0:
        return None, None
    cells.reverse()
    while cells and cells[0] is None:
        cells.pop(0)
    return cells, scale


def grid_years(rec_json, model, field):
    """(the stored grid's underwriting years, its latest incurred estimate by year in millions, whether a year is an
    older-years group), from one extraction record's model block."""
    blk = ((rec_json.get("models") or {}).get(model) or {}).get(field or "_rag_triangle") or {}
    years = blk.get("underwriting_years") or []
    rows = blk.get("development_rows") or []
    units = str(blk.get("units") or "").lower()
    scale = {"thousands": 1000.0, "millions": 1.0, "units": 1e6, "billions": 1e-3}.get(units)
    latest = []
    for c in range(len(years)):
        col = [r[c] for r in rows if c < len(r) and r[c] is not None]
        latest.append(col[-1] / scale if (col and scale) else None)
    group = any(GROUP.search(str(y)) for y in years) or bool(blk.get("aggregated_cohort"))
    return years, latest, group


def _rank_corr(x):
    """Spearman's correlation of x with its position, or 0 for fewer than three values or a constant x."""
    x = np.asarray(x, float)
    if x.size < 3 or np.all(x == x[0]):
        return 0.0
    rx = np.argsort(np.argsort(x))
    return float(np.corrcoef(rx, np.arange(x.size))[0, 1])


def reserve_line_share(cells, co_g, latest):
    """(share, how, developed cells in the grid's year order) from a reserve line's year cells against the grid's
    years, or (None, reason code, None).

    The developed years are the grid's; the line's other cells (its oldest, whichever end that is) are outside them.
    An ordering must keep each developed year's reserve within its latest incurred estimate (2% and 0.05m of slack).
    Where both orderings do and they disagree, the one whose reserve-to-incurred ratio rises more clearly from the
    oldest year to the newest (older years being further paid) decides, by ORDER_MARGIN in rank correlation; otherwise
    none does."""
    ng = len(latest)
    if ng == 0:
        return None, "fewer_cells", None
    vals = [0.0 if c is None else c for c in cells]
    # a total at the end: the last cell equals the sum of the others (to the printed rounding), or it is CO_g itself
    # (within the census's 2%) and more than the others' sum (a total that includes an older-years amount the line does
    # not print by year)
    if len(vals) >= 2 and (abs(vals[-1] - sum(vals[:-1])) <= max(0.002 * abs(vals[-1]), 0.0015)
                           or (abs(vals[-1] - co_g) <= TOL * co_g and vals[-1] > sum(vals[:-1]))):
        vals = vals[:-1]
    n = len(vals)
    if n < ng:
        return None, "fewer_cells", None
    fits = {}
    for order in ("oldest_first", "newest_first"):
        dev = vals[n - ng:] if order == "oldest_first" else vals[:ng][::-1]
        if all(l is None or d <= l * 1.02 + 0.05 for d, l in zip(dev, latest)):
            ratio = [d / l for d, l in zip(dev, latest) if l]
            fits[order] = (1.0 - sum(dev) / co_g, _rank_corr(ratio), dev)
    if not fits:
        return None, "no_ordering", None
    if len(fits) == 2 and abs(fits["oldest_first"][0] - fits["newest_first"][0]) > 1e-6:
        c_old, c_new = fits["oldest_first"][1], fits["newest_first"][1]
        if abs(c_old - c_new) < ORDER_MARGIN:
            return None, "ambiguous_ordering", None
        order = "oldest_first" if c_old > c_new else "newest_first"
        how = ("%d year cells against the grid's %d years (%s, by the reserve-to-incurred pattern: rank correlation "
               "%.2f against %.2f)" % (n, ng, order, max(c_old, c_new), min(c_old, c_new)))
    else:
        order = "oldest_first" if "oldest_first" in fits else "newest_first"
        how = "%d year cells against the grid's %d years (%s)" % (n, ng, order)
    return fits[order][0], how, list(fits[order][2])


def reconcile_by_year(latest, paid, developed, scale_tol=0.01, abs_tol=0.02):
    """Compare each grid year's latest diagonal less its payments with the reserve line's cell for that year. Returns
    ("folded", excess) when only the oldest year disagrees and its reserve cell is the larger (an older-years amount
    folded into the oldest cell, which the reserve line cannot see and the payments measure counts outside), ("paid",
    years) when another year disagrees (the payments line or the grid is misread there), or ("agree", None)."""
    bad = []
    for i, (l, p, d) in enumerate(zip(latest, paid, developed)):
        if l is None:
            continue
        if abs((l - p) - d) > max(scale_tol * abs(d), abs_tol):
            bad.append(i)
    if not bad:
        return "agree", None
    if bad == [0] and developed[0] > latest[0] - paid[0]:
        return "folded", developed[0] - (latest[0] - paid[0])
    return "paid", bad


def eye_bucket_share(texts):
    """(share, how) from an eye placement's "[= ... total X + ... prior years Y]", or (None, None)."""
    for t in texts:
        m = EYE_BUCKET.search(t or "")
        if m:
            tot, bucket = _num(m.group(1)), _num(m.group(2))
            if tot + bucket > 0:
                return bucket / (tot + bucket), "eye placement: %s" % m.group(0)[:160]
    return None, None


#: a table row whose label is a gross older-years reserve: "Provision in respect of prior years", "Gross ... reserve for
#: 2010 and prior years", "Prior years reserve"; the label ends at the first amount
BUCKET_ROW = re.compile(r"^(?:gross\s+)?(?:(?:ultimate\s+)?claims?\s+)?(?:provision|reserves?)\s+(?:in\s+respect\s+of\s+|"
                        r"for\s+)(?:(?:19|20)\d\d\s*(?:&|and)\s*)?prior(?:\s+years?)?\b|^prior\s+years?\s+(?:provision|"
                        r"reserves?)\b|^gross\s+ultimate\s+claims\s+reserve\s+for\s+(?:19|20)\d\d\s*(?:&|and)\s*prior",
                        re.I)
#: a row that is not a reserve balance although it names the older years and a provision
NOT_A_BALANCE = re.compile(r"\bnet\b|change|movement|release|surplus|deficit|development|paid|payment|earned", re.I)
#: an amount as a table prints it: thousands grouped in threes, or a plain decimal
AMOUNT = re.compile(r"^\(?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?\)?$")


def bucket_line_share(lines, co_g, scale):
    """(share, how) from the first amount on a gross older-years reserve row (BUCKET_ROW, and nothing in NOT_A_BALANCE),
    in the table's units (`scale` per million), or (None, None). An amount must be printed whole (AMOUNT): an OCR line
    that cuts it short ("160,76") is not read."""
    if not scale:
        return None, None
    for ln in lines:
        text = re.sub(r"^p\d+:\s*", "", ln).strip()
        if not BUCKET_ROW.search(text) or NOT_A_BALANCE.search(text):
            continue
        rest = BUCKET_ROW.split(text, maxsplit=1)[-1] if BUCKET_ROW.search(text) else text
        toks = rest.split()
        if not toks or not AMOUNT.match(toks[0]):
            continue
        return abs(_num(toks[0])) / scale / co_g, "bucket line: %s" % ln[:160]
    return None, None


def amounts(text):
    """The amounts on a line, in order: numbers (bracketed negatives as negatives) and None for a dash cell. A last token
    that is not printed whole (an OCR line cut short, "2,343,42") is dropped."""
    toks = re.findall(r"\(\s*[\d,]+(?:\.\d+)?\s*\)|[\d,]*\d(?:\.\d+)?|(?<![\w-])[-\u2013\u2014](?![\w-])", text)
    if toks and not DASH.match(toks[-1]) and not AMOUNT.match(toks[-1].replace(" ", "")):
        toks = toks[:-1]
    return [None if DASH.match(t) else _num(t.replace(" ", "")) for t in toks]


def payments_cells(paid_line, scale, n_years):
    """The payments line's year cells in millions, in the order printed, when it has exactly the grid's number of years
    (a trailing total, and trailing dashes beyond the grid's count, dropped); else None. Label numbers before the cells
    (a day of the month, a year) are dropped only when that leaves exactly `n_years` cells."""
    vals = amounts(paid_line or "")
    nums = [abs(v) / scale for v in vals if v is not None]
    if len(vals) >= 2 and vals[-1] is not None and len(nums) >= 2 and abs(nums[-1] - sum(nums[:-1])) <= max(
            0.002 * nums[-1], 0.0015):
        vals = vals[:-1]
    while len(vals) > n_years and vals and vals[-1] is None:
        vals = vals[:-1]
    while len(vals) > n_years and vals and vals[0] is not None and (abs(vals[0]) <= 31 or 1900 <= abs(vals[0]) <= 2100):
        vals = vals[1:]
    if n_years == 0 or len(vals) != n_years:
        return None
    return [0.0 if v is None else abs(v) / scale for v in vals]


def design_dlp_basis(census_rec, paid):
    """Why the design's diagonal-less-paid measure can be used for this record, or None: a reader placed the table's
    diagonal less paid (the census's eye placement), or the census's paid line is a payments line of the grid's years
    and not a reserve line (`paid`, payments_cells' result)."""
    if census_rec.get("class") == "B":
        return None
    eye = ((census_rec.get("eye") or {}).get("placements") or {})
    if eye.get("d_less_paid") is not None:
        return "a reader placed the table's diagonal less paid (the census's eye placement)"
    line = census_rec.get("paid_line") or ""
    if paid is not None and not NET.search(line) and (PAID_WORDS.search(line) or not RESERVE_WORDS.search(line)):
        return "the census's payments line, one cell for each of the grid's years"
    return None


def candidates(key, census_rec, pop_row, pop_class, rec_json):
    """({method: (share, detail)}, [reason codes]): every method that measures the record, and why the others do not."""
    found, why = {}, []
    if key in READER_SHARES:
        found["reading"] = (READER_SHARES[key], "the adjudication's Q5 list of readers' shares")
    if census_rec is None:
        if not found:
            why.append("not_in_census")
        return found, why
    co_g = census_rec.get("co_g")
    _years, latest, group = grid_years(rec_json or {}, census_rec.get("canonical_model"), census_rec.get("grid_field"))
    if group or (pop_class or {}).get("grid_group_column"):
        found["developed_column"] = (0.0, "the stored grid develops an older-years column")
    if not co_g or co_g <= 0:
        why.append("no_co_g")
        return found, why
    paid_line = census_rec.get("paid_line") or ""
    unc = (pop_row or {}).get("uncovered_share")
    paid = payments_cells(paid_line, census_rec.get("grid_scale") or 1.0, len(latest)) if paid_line else None
    if unc is not None:
        basis = design_dlp_basis(census_rec, paid)
        if basis and -TOL <= unc <= 1.0:
            found["design_dlp"] = (unc, "the table's latest diagonal less its payments against CO_g (measures/measure_pop.py): "
                                        + basis)
        else:
            why.append("dlp_not_payments")
    hits = (census_rec.get("detail") or {}).get("gross_hits") or []
    share, how = eye_bucket_share([h.get("line") for h in hits] + [((census_rec.get("eye") or {}).get("note") or "")])
    if share is not None:
        found["eye_bucket"] = (share, how)
    aligned = None
    lines = [(h.get("line"), h.get("line_values")) for h in hits if not h.get("single") and h.get("line_values")]
    if paid_line and RESERVE_WORDS.search(paid_line) and not PAID_WORDS.search(paid_line):
        sc = census_rec.get("grid_scale") or 1.0
        lines.append((paid_line, [_num(x) / sc for x in paid_line.split() if NUM.match(x)]))
    for text, values in lines:
        cells, _scale = line_cells(text or "", values)
        if cells is None:
            why.append("line_text")
            continue
        share, how, developed = reserve_line_share(cells, co_g, latest)
        if share is None:
            why.append(how)
        elif -TOL <= share <= 1.0:
            if "reserve_line" not in found:
                found["reserve_line"] = (share, "%s: %s" % (how, (text or "")[:160]))
                aligned = developed
        else:
            why.append("line_out_of_range")
    if "design_dlp" in found and "reserve_line" in found and abs(found["design_dlp"][0] - found["reserve_line"][0]) > TOL:
        # the two disagree: reconcile them year by year (reconcile_by_year)
        verdict, what = reconcile_by_year(latest, paid, aligned)
        if verdict == "paid":
            del found["design_dlp"]
            why.append("dlp_years_disagree")
        elif verdict == "folded":
            found["design_dlp"] = (found["design_dlp"][0], found["design_dlp"][1] + "; the reserve line's oldest cell "
                                   "holds %.3fm more than its year's diagonal less payments (an older-years amount "
                                   "folded into it)" % what)
    share, how = bucket_line_share((pop_row or {}).get("prior_lines") or [], co_g, census_rec.get("grid_scale"))
    if share is not None and 0.0 <= share <= 1.0:
        found["bucket_line"] = (share, how)
    elif (pop_row or {}).get("prior_lines"):
        why.append("bucket_unplaced")
    if not hits:
        why.append("no_total")
    elif all(h.get("single") for h in hits):
        why.append("single_total")
    return found, list(dict.fromkeys(why))


def measure(key, census_rec, pop_row, pop_class, rec_json):
    """One record's row: the share by the first method of PRECEDENCE that measures it (or None, with the reasons), and
    every other method's share beside it, for the cross-check."""
    found, why = candidates(key, census_rec, pop_row, pop_class, rec_json)
    row = {"record": key, "share": None, "method": None, "detail": None, "other_methods": {}, "reasons_unmeasured": []}
    for m in PRECEDENCE:
        if m in found:
            if row["method"] is None:
                row["share"], row["detail"] = found[m]
                row["method"] = m
            else:
                row["other_methods"][m] = found[m][0]
    if row["method"] is None:
        row["reasons_unmeasured"] = why or ["no_total"]
        row["detail"] = "; ".join(REASONS[c] for c in row["reasons_unmeasured"])
    if row["share"] is not None and -TOL <= row["share"] < 0:
        row["share"] = 0.0
    return row


def measure_all(keys, census, pop_measures, pop_classified, load_record):
    """{key: row} for `keys`; `census` maps a key to its census (or restored-scan) record, `load_record(key)` returns
    the stored extraction record or None."""
    return {k: measure(k, census.get(k), pop_measures.get(k), pop_classified.get(k), load_record(k)) for k in keys}


def cross_check(rows, tol=TOL):
    """Where the deciding method and another both measure a record: how often they agree within `tol`, per pair."""
    out = {}
    for r in rows.values():
        for m, s in r["other_methods"].items():
            pair = "%s__vs__%s" % (r["method"], m)
            c = out.setdefault(pair, {"n": 0, "n_agree_within_2pct": 0, "disagree": []})
            c["n"] += 1
            if abs(s - r["share"]) <= tol:
                c["n_agree_within_2pct"] += 1
            else:
                c["disagree"].append({"record": r["record"], r["method"]: r["share"], m: s})
    return out


def distribution(rows, lines=(0.02, 0.10, 0.30)):
    measured = [r["share"] for r in rows.values() if r["share"] is not None]
    out = {"n": len(rows), "n_measured": len(measured), "n_unmeasured": len(rows) - len(measured), "by_method": {},
           "reasons_unmeasured": {}}
    for r in rows.values():
        if r["method"]:
            out["by_method"][r["method"]] = out["by_method"].get(r["method"], 0) + 1
        else:
            for c in r["reasons_unmeasured"]:
                out["reasons_unmeasured"][c] = out["reasons_unmeasured"].get(c, 0) + 1
    for t in lines:
        out["n_above_%g_pct" % (100 * t)] = int(sum(s > t for s in measured))
    out["median_measured"] = float(np.median(measured)) if measured else None
    return out


def load_json(path):
    with io.open(path, encoding="utf-8") as _fh:
        return json.load(_fh)
