r"""make_census_eighth.py: three rules tightened after the dry run, before the amendment is written or any record read.

The dry run flagged 83 records for net_table, 44 for opening and 104 for takeon_triangle. Reading the hits
(census-eighth-dryrun.log) and the probe (probe_census_rules.py) shows why:
  net_table        the sentence test caught narrative about net claims beside gross tables (510, 2999, 4000) and table
                   text with no sentence breaks; 1880/2014's page has no gross heading at all, while every page with a
                   gross and a net table has one. The rule becomes a page test on headings.
  opening          a year's jump against one neighbour is common (new syndicates, RITC take-ons); 2003/2018's value is
                   under half of two neighbours that agree with each other. The rule becomes that isolated dip or spike.
  takeon_triangle  the 800-character window caught management changes, group structure and year-of-account accounts.
                   The RITC scan's own decision (inward, in the report year) finds 1274/2018; 2003/2018's Syndicate
                   1209 is a roll-forward row ("RITC from S1209") and a sentence ("reinsurered to close into the
                   Syndicate on 1 January 2018"). The rule becomes the scan's decision, a sentence-bounded passage with
                   an inward word, or an RITC row naming another syndicate.

Each block and its docstring rule is replaced between fixed markers; each marker must occur once.

    python fix_census_eighth_rules.py
"""
import io
from pathlib import Path

P = Path(__file__).resolve().parent / "make_census_eighth.py"

DOC = {
    ("  net_table        ", "  provisions_row   "): r'''  net_table        A net table taken for gross. Every working-sample record whose adopted figure is a triangle figure
                   (score_error_rate.figure_source) and whose triangle page names a net table ("net of reinsurance",
                   "after reinsurance", "net claims", "incurred net", "ultimate net", "cumulative net", "net basis")
                   and has no gross heading ("gross of reinsurance", "gross claims", "incurred gross", "ultimate gross",
                   "cumulative gross", "gross basis", "before reinsurance", "gross ultimate", or a line reading Gross).
''',
    ("  opening          ", "  takeon_triangle  "): r'''  opening          An opening-reserves misreading. Every working-sample record whose adopted opening reserves are under
                   half or over twice both neighbouring years' (t-1 and t+1), where the two neighbours are within a
                   factor of two of each other.
''',
    ("  takeon_triangle  ", "\nRecords already decided"): r'''  takeon_triangle  A take-on inside a triangle figure. Every working-sample record whose adopted figure is a triangle
                   figure and whose filing records a transfer in from outside the syndicate: the RITC scan decides an
                   inward RITC in the report year; or a passage (its sentence, at most 300 characters either side)
                   names reinsurance to close, RITC or a portfolio transfer, an inward word (accept, into the
                   syndicate, take-on, transferred to, from Syndicate N), the report year, and another syndicate's
                   number or a portfolio transfer, and is not about a managing agent taking on or novating the
                   management of syndicates; or a roll-forward row reads "RITC (accepted) from" another syndicate.
''',
}

NET_TABLE = r'''# --- net_table --------------------------------------------------------------------------------------------------------
NET_HEAD = re.compile(r"net of reinsurance|after reinsurance|net claims|incurred net|ultimate net|cumulative net|net basis", re.I)
GROSS_HEAD = re.compile(r"gross of reinsurance|gross claims|incurred gross|ultimate gross|cumulative gross|gross basis|"
                        r"before reinsurance|gross ultimate|gross of reinsurers|^\s*gross\s*$", re.I | re.M)
page_cache = {}


def page_text(stem, page):
    k = (stem, page)
    if k not in page_cache:
        if not briefs[stem]["filing_pdf"]:
            page_cache[k] = ""
        else:
            doc = fitz.open(briefs[stem]["filing_pdf"])
            page_cache[k] = doc[page - 1].get_text() if 1 <= page <= len(doc) else ""
            doc.close()
    return page_cache[k]


no_page = []
for s in WS:
    if source[s] != "triangle":
        continue
    cm = records[s]["models"][briefs[s]["canonical_model"]]
    page = briefs[s]["route"].get("triangle_source_page") or (cm.get("_rag_triangle") or {}).get("source_page")
    if not isinstance(page, int):
        no_page.append(s)
        continue
    raw = page_text(s, page)
    m = NET_HEAD.search(raw)
    if m and not GROSS_HEAD.search(raw):
        flag("net_table", s, "p%d: '%s' and no gross heading: ...%s..."
             % (page, m.group(0), re.sub(r"\s+", " ", raw[max(0, m.start() - 150): m.end() + 150])))

'''

OPENING = r'''# --- opening ----------------------------------------------------------------------------------------------------------
panel = {}
for p in glob.glob(str(AN / "pdf_extraction" / "syndicate_*_*.json")):
    parts = Path(p).stem.split("_")
    if len(parts) != 3 or not parts[2].isdigit():
        continue
    data = records.get(Path(p).stem) or load(p)
    if not data.get("models"):
        continue
    try:
        v = data["models"][canonical(data)].get("opening_reserves_gbp_m")
    except (ValueError, KeyError):
        continue
    if isinstance(v, (int, float)) and v > 0:
        panel[(parts[1], int(parts[2]))] = v
for s in WS:
    syn, year = s.split("_")[1], int(s.split("_")[2])
    v = briefs[s][OPENING]
    if not isinstance(v, (int, float)) or v <= 0:
        continue
    nb = [panel[(syn, y)] for y in (year - 1, year + 1) if (syn, y) in panel]
    if len(nb) != 2 or max(nb) > 2 * min(nb):
        continue
    if all(v < 0.5 * n for n in nb) or all(v > 2 * n for n in nb):
        others = ["%s says %s" % (model, md.get("opening_reserves_gbp_m"))
                  for model, md in sorted((records[s].get("models") or {}).items())
                  if model != briefs[s]["canonical_model"] and md.get("opening_reserves_gbp_m") != v]
        flag("opening", s, "opening %s against neighbouring years %s%s"
             % (v, nb, ("; " + "; ".join(others)) if others else ""))

'''

TAKEON = r'''# --- takeon_triangle --------------------------------------------------------------------------------------------------
scan = load(EX / "pdf_extraction" / "ritc_scan.json")
no_filing = []
TRANSFER = re.compile(r"reinsur\w*\s+to\s+close|\bRITC\b|portfolio\s+transfer", re.I)
INWARD = re.compile(r"accept|into (?:the|this) syndicate|take-on|taken on|transferred (?:in)?to|"
                    r"\bfrom (?:syndicate\s*|s)\d{3,4}", re.I)
SYND = re.compile(r"(?:\b[Ss]yndicates?\s+|\bS)(\d{3,4})\b")
ROW = re.compile(r"\bRITC\s+(?:accepted\s+)?from\s+(?:[Ss]yndicate\s+|S)(\d{3,4})\b")
MANAGEMENT = re.compile(r"management of|took on (?:the )?management|novat", re.I)
for s in WS:
    if source[s] != "triangle":
        continue
    key, syn, year = s.replace("syndicate_", ""), s.split("_")[1], int(s.split("_")[2])
    top = scan.get(key) or {}
    if top.get("ritc_occurred") is True and top.get("direction") == "inward" and top.get("event_year") == year:
        flag("takeon_triangle", s, "RITC scan: an inward RITC in %d: %s"
             % (year, re.sub(r"\s+", " ", top.get("evidence") or "")[:240]))
    if not briefs[s]["filing_pdf"]:
        no_filing.append(s)
        continue
    doc = fitz.open(briefs[s]["filing_pdf"])
    text = re.sub(r"\s+", " ", " ".join(pg.get_text() for pg in doc))
    doc.close()
    for m in TRANSFER.finditer(text):
        a = text.rfind(". ", 0, m.start())
        b = text.find(". ", m.end())
        w = text[max(a + 2 if a >= 0 else 0, m.start() - 300): min(b + 1 if b >= 0 else len(text), m.end() + 300)]
        if (INWARD.search(w) and re.search(r"\b%d\b" % year, w) and not MANAGEMENT.search(w)
                and ([n for n in SYND.findall(w) if n != syn] or re.search(r"portfolio\s+transfer", w, re.I))):
            flag("takeon_triangle", s, "text: ...%s..." % w[:500])
            break
    r = next((x for x in ROW.finditer(text) if x.group(1) != syn), None)
    if r:
        flag("takeon_triangle", s, "row: ...%s..." % text[max(0, r.start() - 120): r.end() + 160])

'''

BLOCKS = [("# --- net_table ", "# --- provisions_row ", NET_TABLE),
          ("# --- opening ", "# --- takeon_triangle ", OPENING),
          ("# --- takeon_triangle ", "# --- definers, decided records, carry-over ", TAKEON)]

raw = io.open(str(P), encoding="utf-8", newline="").read()
crlf = "\r\n" in raw
t = raw.replace("\r\n", "\n")
if "GROSS_HEAD" in t:
    raise SystemExit("already tightened")
for (start, end), new in DOC.items():
    if t.count(start) != 1 or t.count(end) != 1:
        raise SystemExit("docstring markers %r %r found %d, %d times" % (start, end, t.count(start), t.count(end)))
    i, j = t.index(start), t.index(end)
    t = t[:i] + new + t[j:]
for start, end, new in BLOCKS:
    if t.count(start) != 1 or t.count(end) != 1:
        raise SystemExit("code markers %r %r found %d, %d times" % (start, end, t.count(start), t.count(end)))
    i, j = t.index(start), t.index(end)
    t = t[:i] + new + t[j:]
io.open(str(P), "w", encoding="utf-8", newline="").write(t.replace("\n", "\r\n") if crlf else t)
print("make_census_eighth.py: net_table, opening and takeon_triangle rules tightened (docstring and code)")
