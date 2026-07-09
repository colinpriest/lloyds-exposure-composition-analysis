"""Report-currency extraction with provenance for every syndicate report.

For each pdf_extraction/syndicate_<synd>_<year>.json, opens the source PDF
(d:/dev/lloyds_reserve_stress_testing/syndicate_reports/pdfs/) and determines the
currency the report's monetary amounts are PRESENTED in, recording PROVENANCE:
the page number, the nearest section heading, and a verbatim quote of the sentence
that establishes the currency.

The relevant concept is the PRESENTATIONAL currency (the currency of the published
amounts), not the functional currency: a syndicate can have a USD functional
currency while presenting its accounts in sterling (e.g. syndicate 1861 in 2014).

Evidence hierarchy (strongest first):
  1. presentational_statement — an explicit statement of the presentation currency
     ("the syndicate's functional and presentational currency is US dollars",
     "these annual accounts are presented in US dollars", "the Syndicate's
     Sterling presentational currency"). The currency token is searched after the
     anchor phrase first, then before it (sentence-bounded).
  2. unit_headers — dominance of monetary unit headers in the actual statements
     ("US$'000" vs "£'000"; >=3 hits and >=3x dominance). This is direct evidence
     of the presentation currency of the tables.
  3. functional_statement — a functional-currency statement only (no
     presentational statement and no unit-header dominance found). Flagged: the
     presentational currency usually, but not always, equals the functional one.
  4. llm_field — the dual-LLM extraction's `currency` field ("Reporting currency
     of the financial statements"), used when the PDF has no usable text layer or
     nothing matched. Flagged.

Every classification is cross-checked against (a) the LLM field and (b) the
unit-header tally; conflicts are flagged for manual review. Currencies other than
GBP/USD are classified OTHER:<CODE> and listed for manual instruction.

Writes pdf_extraction/currency_scan.json.
Usage:  python currency_scan.py
"""
import glob, io, json, re, sys, time
from pathlib import Path
import fitz  # PyMuPDF

SCRIPT_DIR = Path(__file__).resolve().parent
DATA_DIR = SCRIPT_DIR / "pdf_extraction"
PDF_DIR = Path(r"d:/dev/lloyds_reserve_stress_testing/syndicate_reports/pdfs")
OUT = DATA_DIR / "currency_scan.json"
MAX_PAGES = 100          # statement + unit search window
MIN_TEXT_CHARS = 2000    # below this the PDF is treated as scanned (no text layer)

# anchor phrases that assert the PRESENTATION currency, most direct first
PRESENTATIONAL_ANCHORS = [
    ("accounts_presented_in",
     r"(?:financial statements|annual accounts|syndicate accounts|underwriting "
     r"accounts|these accounts|the accounts)[^.;]{0,140}?"
     r"(?<!previously )(?<!formerly )"
     r"(?:presented|prepared|expressed|stated|shown|reported)\s+in\b"),
    ("functional_and_presentational",
     r"functional (?:currency )?and presentation(?:al)? currenc\w*"),
    ("presentational_currency", r"presentation(?:al)?\s+currenc\w*"),
    ("expressed_in_thousands",
     r"(?:presented|expressed|stated|shown)\s+in\s+(?:thousands|millions)\s+of\b"),
]
FUNCTIONAL_ANCHOR = ("functional_currency", r"functional\s+currenc\w*")

USD_TOKENS = [r"us\s?dollars?", r"u\.s\.\s?dollars?", r"united states dollars?",
              r"\busd\b", r"us\s?\$"]
GBP_TOKENS = [r"sterling", r"pounds?\s+sterling", r"gb\s?pounds?", r"\bgbp\b", r"£",
              r"\bpounds?\b"]
OTHER_TOKENS = {
    "EUR": [r"\beuros?\b", r"\beur\b"], "CAD": [r"canadian dollars?", r"\bcad\b"],
    "AUD": [r"australian dollars?", r"\baud\b"], "JPY": [r"\byen\b", r"\bjpy\b"],
    "CHF": [r"swiss francs?", r"\bchf\b"], "CNY": [r"renminbi", r"\byuan\b", r"\bcny\b"],
    "NZD": [r"new zealand dollars?"], "SGD": [r"singapore dollars?"],
    "HKD": [r"hong kong dollars?"], "ZAR": [r"\bzar\b"],
}

UNIT_USD = [r"us\s?\$\s?'?0{3}", r"us\s?\$\s?'?m\b", r"usd\s?'?0{3}", r"us\s?\$\s?million",
            r"\$\s?'?0{3}", r"\$\s?m\b", r"\$\s?million"]
UNIT_GBP = [r"£\s?'?0{3}", r"£\s?'?m\b", r"gbp\s?'?0{3}", r"£\s?million"]

HEADING_HINTS = ["accounting policies", "basis of preparation", "basis of presentation",
                 "foreign currenc", "notes to the", "statement of accounting",
                 "principal accounting"]


def classify_tokens(text):
    """Set of currency codes mentioned in text (lowercased input)."""
    found = set()
    if any(re.search(p, text) for p in USD_TOKENS):
        found.add("USD")
    if any(re.search(p, text) for p in GBP_TOKENS):
        found.add("GBP")
    for code, pats in OTHER_TOKENS.items():
        if any(re.search(p, text) for p in pats):
            found.add(code)
    return found


ALL_TOKEN_PATS = ([(p, "USD") for p in USD_TOKENS] + [(p, "GBP") for p in GBP_TOKENS]
                  + [(p, code) for code, pats in OTHER_TOKENS.items() for p in pats])

# a statement about a FUTURE currency change does not describe this report's amounts
FUTURE_CHANGE = re.compile(r"will\s+(?:be\s+)?chang|will\s+be\s+presented|"
                           r"(?:change[ds]?|changing)[^.;]{0,60}?"
                           r"(?:effective|with effect)\s+from[^.;]{0,30}?(20\d\d)|"
                           r"change\s+to[^.;]{0,50}?\bin\s+(20\d\d)")


def is_future_change(sentence, report_year):
    """True if the sentence announces a currency change taking effect AFTER the
    reporting year (so the current report is still in the old currency)."""
    m = FUTURE_CHANGE.search(sentence)
    if not m:
        return False
    yrs = [int(g) for g in m.groups() if g]
    if yrs:
        return max(yrs) > report_year
    return True  # "will change" with no year: future by construction


CURRENCY_KEYWORDS = [("functional", r"functional"),
                     ("presentational", r"presentation(?:al)?|reporting")]


def currency_near_anchor(flat_low, start, end, direct_object=False):
    """Resolve the currency a presentational anchor at [start:end) asserts.

    direct_object=True ("presented in X" style): first token after the anchor.
    Otherwise ("presentational currency" style): nearest token in the sentence
    whose own nearest currency-type keyword is NOT 'functional' (so 'the
    functional currency is USD and the presentation currency is sterling'
    resolves to sterling); falls back to the overall nearest token.
    Parentheticals like '(previously GBP)' are masked first."""
    s0 = max(0, start - 160)
    sent_start = max([flat_low.rfind(c, s0, start) for c in ".;"] + [s0 - 1]) + 1
    sent_start = max(sent_start, s0)
    e_lim = end + 260
    ends = [flat_low.find(c, end, e_lim) for c in ".;"]
    ends = [e for e in ends if e != -1]
    sent_end = min(ends) if ends else e_lim
    sent = flat_low[sent_start:sent_end]
    sent = re.sub(r"\((?:previously|formerly)[^)]{0,60}\)", lambda m: " " * len(m.group()),
                  sent)
    a_start, a_end = start - sent_start, end - sent_start

    if direct_object:
        window = sent[a_end:a_end + 70]
        hits = [(m.start(), code) for pat, code in ALL_TOKEN_PATS
                for m in re.finditer(pat, window)]
        return min(hits)[1] if hits else None

    kws = [(m.start(), kind) for kind, pat in CURRENCY_KEYWORDS
           for m in re.finditer(pat, sent)]
    toks = []
    for pat, code in ALL_TOKEN_PATS:
        for m in re.finditer(pat, sent):
            pos, pos_end = m.start(), m.end()
            if pos >= a_end:
                dist, after = pos - a_end, 0
            elif pos_end <= a_start:
                dist, after = a_start - pos_end, 1
            else:
                dist, after = 0, 0
            near_kw = min(kws, key=lambda k: abs(k[0] - pos), default=None)
            assoc = near_kw[1] if near_kw and abs(near_kw[0] - pos) <= 90 else None
            toks.append((dist, after, code, assoc))
    if not toks:
        return None
    non_functional = [t for t in toks if t[3] != "functional"]
    pool = non_functional if non_functional else toks
    return min(pool, key=lambda t: (t[0], t[1]))[2]


def nearest_heading(page_text_lines, quote_head):
    """Best-effort nearest preceding heading above the quote within the page."""
    idx = None
    for i, line in enumerate(page_text_lines):
        if quote_head[:30].strip() and quote_head[:30].strip()[:20] in line:
            idx = i
            break
    search = page_text_lines[:idx] if idx is not None else page_text_lines
    for line in reversed(search):
        t = line.strip()
        if not t or len(t) > 90:
            continue
        low = t.lower()
        if any(h in low for h in HEADING_HINTS):
            return t
        if re.match(r"^\d{1,2}\.?\s+[A-Z][A-Za-z]", t) and len(t) < 70:
            return t
    return None


def unit_tally(pages):
    all_text = " ".join(p.replace("\n", " ") for p in pages).lower()
    n_usd = sum(len(re.findall(p, all_text)) for p in UNIT_USD)
    n_gbp = sum(len(re.findall(p, all_text)) for p in UNIT_GBP)
    return n_usd, n_gbp


def find_statement(pages, anchors, report_year):
    """First anchor match (pattern priority, then page order) with a resolvable
    currency; statements announcing a post-reporting-year currency change are
    skipped. Returns (currency, page_no, quote, pattern_name, heading) or None."""
    for pname, pat in anchors:
        for pno, ptxt in enumerate(pages):
            flat = ptxt.replace("\n", " ")
            flat_low = flat.lower()
            for m in re.finditer(pat, flat_low):
                window = flat_low[max(0, m.start() - 160):m.end() + 260]
                if is_future_change(window, report_year):
                    continue
                direct = pname in ("accounts_presented_in", "expressed_in_thousands")
                cur = currency_near_anchor(flat_low, m.start(), m.end(),
                                           direct_object=direct)
                if cur:
                    q0 = max(0, m.start() - 120)
                    quote = flat[q0:m.end() + 240]
                    quote = quote[quote.find(". ") + 2 if ". " in quote[:120] else 0:]
                    heading = nearest_heading(ptxt.split("\n"), flat[m.start():m.end()])
                    return cur, pno + 1, quote[:400].strip(), pname, heading
    return None


def scan_pdf(pdf_path, report_year):
    """Classify presentation currency of one PDF.
    Returns (currency|None, provenance/diag dict)."""
    doc = fitz.open(pdf_path)
    n_pages = min(len(doc), MAX_PAGES)
    pages = [doc[i].get_text("text") for i in range(n_pages)]
    doc.close()
    total_chars = sum(len(p) for p in pages)
    if total_chars < MIN_TEXT_CHARS:
        return None, {"reason": "no_text_layer", "chars": total_chars}

    n_usd, n_gbp = unit_tally(pages)
    units = {"usd_hits": n_usd, "gbp_hits": n_gbp}
    unit_verdict = ("USD" if (n_usd >= 3 and n_usd >= 3 * max(n_gbp, 1)) else
                    "GBP" if (n_gbp >= 3 and n_gbp >= 3 * max(n_usd, 1)) else None)

    # 1) explicit presentational statement
    hit = find_statement(pages, PRESENTATIONAL_ANCHORS, report_year)
    if hit:
        cur, page, quote, pname, heading = hit
        return cur, {"method": "presentational_statement", "pattern": pname,
                     "page": page, "section_heading": heading, "quote": quote,
                     "unit_headers": units,
                     "evidence_conflict": bool(unit_verdict and unit_verdict != cur)}
    # 2) unit-header dominance
    if unit_verdict:
        return unit_verdict, {
            "method": "unit_headers", "page": None, "section_heading": None,
            "quote": (f"monetary unit headers across first {n_pages} pages: "
                      f"US$'000-style x{n_usd}, £'000-style x{n_gbp}"),
            "unit_headers": units, "evidence_conflict": False}
    # 3) functional-currency statement only
    hit = find_statement(pages, [FUNCTIONAL_ANCHOR], report_year)
    if hit:
        cur, page, quote, pname, heading = hit
        return cur, {"method": "functional_statement", "pattern": pname,
                     "page": page, "section_heading": heading, "quote": quote,
                     "unit_headers": units,
                     "note": ("presentational currency not explicitly stated and no "
                              "unit-header dominance; functional currency used"),
                     "evidence_conflict": False}
    return None, {"reason": "no_pattern_matched", "chars": total_chars,
                  "unit_headers": units}


def llm_currency(d):
    for mk in sorted(d.get("models", {})):
        c = d["models"][mk].get("currency")
        if c:
            return c
    return None


def main():
    t0 = time.time()
    files = sorted(glob.glob(str(DATA_DIR / "syndicate_*_*.json")))
    print(f"{len(files)} reports; PDFs from {PDF_DIR}")
    results, counts, method_counts = {}, {}, {}
    disagreements, others, undetermined, conflicts = [], [], [], []
    for i, f in enumerate(files):
        key = Path(f).stem.replace("syndicate_", "")
        d = json.load(io.open(f, encoding="utf-8"))
        llm = llm_currency(d)
        pdf = PDF_DIR / f"syndicate_{key}.pdf"
        report_year = int(key.rsplit("_", 1)[1])
        cur, prov = (None, {"reason": "pdf_missing"}) if not pdf.exists() \
            else scan_pdf(str(pdf), report_year)
        if cur is None:
            if llm:
                cur = llm
                prov = {"method": "llm_field", "page": None, "section_heading": None,
                        "quote": (f"dual-LLM extraction `currency` field = {llm} "
                                  f"(PDF scan unusable: {prov.get('reason')})"),
                        "evidence_conflict": False}
            else:
                results[key] = {"currency": "UNDETERMINED", "llm_currency": llm,
                                "provenance": prov}
                undetermined.append(key)
                counts["UNDETERMINED"] = counts.get("UNDETERMINED", 0) + 1
                continue
        agrees = (llm is None) or (llm == cur)
        results[key] = {"currency": cur, "llm_currency": llm,
                        "agrees_with_llm": agrees, "provenance": prov}
        counts[cur] = counts.get(cur, 0) + 1
        m = prov.get("method")
        method_counts[m] = method_counts.get(m, 0) + 1
        if not agrees:
            disagreements.append(key)
        if prov.get("evidence_conflict"):
            conflicts.append(key)
        if cur not in ("GBP", "USD"):
            others.append(key)
        if (i + 1) % 200 == 0:
            print(f"  ... {i+1}/{len(files)}  ({time.time()-t0:.0f}s)")

    out = {
        "method": ("Presentation-currency scan of the source PDF text layer. Hierarchy: "
                   "(1) explicit presentational-currency statement (page + nearest "
                   "heading + verbatim quote recorded); (2) monetary unit-header "
                   "dominance in the statements (US$'000 vs £'000, >=3 hits and >=3x); "
                   "(3) functional-currency statement (flagged); (4) dual-LLM `currency` "
                   "field for scanned PDFs (flagged). Cross-checked against the LLM field "
                   "and the unit-header tally; conflicts flagged."),
        "pdf_dir": str(PDF_DIR), "n_reports": len(files), "counts": counts,
        "method_counts": method_counts,
        "disagreements_with_llm": disagreements,
        "evidence_conflicts": conflicts,
        "non_gbp_usd": others, "undetermined": undetermined,
        "reports": results,
    }
    OUT.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"\nWrote {OUT}  ({time.time()-t0:.0f}s)")
    print("counts:", counts)
    print("methods:", method_counts)
    print(f"LLM disagreements: {len(disagreements)}  {disagreements[:10]}")
    print(f"evidence conflicts (statement vs units): {len(conflicts)}  {conflicts[:10]}")
    print(f"non-GBP/USD: {len(others)}  {others[:10]}")
    print(f"undetermined: {len(undetermined)}  {undetermined[:10]}")


if __name__ == "__main__":
    sys.exit(main())
