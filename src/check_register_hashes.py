"""PC check: the registers' source hashes match the filings, and their quotes are on the pages they cite.

The evidence registers record, per entry, the filing the pages were read in (source_file, relative to the filings
folder) and its SHA-256, and a quote. The filings are not in this repository, so no test compares the registers with
them (a test that skipped without them would be no test); this script does, on the PC. It is not in the manifest: run it
by hand after editing a register, or before a recorded pass.

  * Hashes: every source_file in data/composition_page_readings.json, data/eligibility_from_filing.json and the
    extraction's run-off registers (pdf_extraction/audit/runoff_corpus_register.json and runoff_register.json) hashes to
    its source_sha256.
  * Quotes: every single-quoted fragment of a quote in the first two registers occurs in the text of the pages the
    entry cites (the whole text for an HTML filing), after normalising case, whitespace, quotes, dashes and
    punctuation. A fragment is split at an ellipsis, and one too short to be a quote is not checked. A cited page with
    no text layer is read from the extraction's OCR page cache (pdf_extraction/ocr_page_cache), then by local Tesseract
    if it is installed. A fragment found only there is reported "ok_ocr"; one not found there "not_found_ocr" (to be
    confirmed by eye, and not a failure); one not found on a text-layer page "not_found" (a failure).
  * No register string holds U+FFFD (a damaged character).

It exits 0 if nothing failed, and 1 on a hash mismatch, a missing file, a fragment not found on a text-layer page, or a
U+FFFD. The filings folder is the first argument, else the LLOYDS_FILINGS_DIR environment variable, else
D:/dev/lloyds_reserve_stress_testing.

Run:  python src/check_register_hashes.py [filings_folder]
"""
import hashlib
import html as htmllib
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

SD = Path(__file__).resolve().parent.parent
REGISTERS = (SD / "data" / "composition_page_readings.json", SD / "data" / "eligibility_from_filing.json")
AUDIT_REGISTERS = (SD / "pdf_extraction" / "audit" / "runoff_corpus_register.json",
                   SD / "pdf_extraction" / "audit" / "runoff_register.json")
DEFAULT_FILINGS = "D:/dev/lloyds_reserve_stress_testing"
TESSERACT = ("C:/Program Files/Tesseract-OCR/tesseract.exe", "C:/Program Files/tesseract-OCR/tesseract.exe")
#: a fragment shorter than this (after normalising) is a label, not a quote worth finding
MIN_FRAGMENT = 8
#: a page whose text layer is shorter than this is read as an image
MIN_TEXT = 40


def _items(raw):
    """(key, entry) pairs of a register in either container: keyed by SYND_YEAR, or {"records": [...]} keyed by stem."""
    if isinstance(raw, dict) and isinstance(raw.get("records"), list):
        return [(str(e.get("stem", i)), e) for i, e in enumerate(raw["records"]) if isinstance(e, dict)]
    return [(k, v) for k, v in raw.items() if not k.startswith("_") and isinstance(v, dict)]


def entries(path):
    """{key: entry} of a register's entries that name a source file (keys starting "_" are notes)."""
    with open(path, encoding="utf-8") as fh:
        raw = json.load(fh)
    return {k: v for k, v in _items(raw) if "source_file" in v}


def sha256_of(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def check(filings, registers=None):
    """[(register name, key, status, detail)] for every entry; status is "ok", "mismatch" or "missing"."""
    out = []
    for reg in (REGISTERS if registers is None else registers):
        for key, e in sorted(entries(reg).items()):
            f = Path(filings) / e["source_file"]
            if not f.is_file():
                out.append((Path(reg).name, key, "missing", str(f)))
                continue
            got, want = sha256_of(f), e.get("source_sha256")
            out.append((Path(reg).name, key, "ok" if got == want else "mismatch",
                        "%s: file %s, register %s" % (e["source_file"], got, want)))
    return out


# ---- the quotes ------------------------------------------------------------------------------------------------------
#: some filings embed a font that maps the digits to U+0D61..U+0D6A (Malayalam letters) and the full stop to U+0011, so
#: the text layer of the page prints "Reinsurance acceptances ൩൥.ൡ" for 84.0 (6117/2021 p24; "2021" in its header reads
#: U+0D63 U+0D61 U+0D63 U+0D62 the same way). The text is decoded before comparing.
DIGIT_FONT = {0x0D61 + d: str(d) for d in range(10)}
DIGIT_FONT[0x11] = "."


def norm(s):
    """Case, quotes, dashes, whitespace and punctuation removed: what is left is the words and numbers."""
    return re.sub(r"[^0-9a-z]", "", s.translate(DIGIT_FONT).lower())


#: a single-quoted fragment: an apostrophe inside a word (Lloyd's) opens or closes nothing
QUOTED = re.compile(r"(?<![A-Za-z0-9])'(.+?)'(?![A-Za-z0-9])", re.S)
#: a page citation: "PDF p6", "PDF p5 and p47", "PDF p11-12", "PDF p6 (printed 4)", with any brackets
CITATION = re.compile(r"\(?\bPDF p\d+(?:\s*(?:,|and|-|\u2013)\s*p?\d+)*(?:\s*\(printed \d+\))?\)?", re.I)


def _plain(quote):
    """The quote with curly apostrophes made straight and the units $'000 and GBP'000 made words, not quotes."""
    s = quote.replace("\u2019", "'").replace("\u2018", "'")
    return s.replace("$'000", "$ thousand").replace("\u00a3'000", "\u00a3 thousand")


def fragments(quote):
    """The single-quoted fragments of a quote, split at ellipses, with those too short to be a quote dropped."""
    out = []
    for m in QUOTED.finditer(_plain(quote)):
        for part in re.split(r"\.\.\.|\u2026", m.group(1)):
            if len(norm(part)) >= MIN_FRAGMENT:
                out.append(part.strip())
    return out


def remainder(quote):
    """What a quote holds besides quoted page text and page citations: its labels, units and annotations.

    A register entry may say verbatim_quote true only if this is empty (punctuation and spaces do not count)."""
    s = CITATION.sub(" ", QUOTED.sub(" ", _plain(quote)))
    return re.sub(r"[\W_]+", " ", s).strip()


def html_text(path):
    raw = Path(path).read_bytes().decode("utf-8", "replace")
    raw = re.sub(r"(?is)<(script|style).*?</\1>", " ", raw)
    return htmllib.unescape(re.sub(r"(?s)<[^>]+>", " ", raw))


def ocr_cache(filings, e, page):
    """The extraction's OCR text of a page, or None if the extraction did not OCR it."""
    cache = Path(filings) / "pdf_extraction" / "ocr_page_cache" / (Path(e["source_file"]).stem + ".json")
    if cache.is_file():
        for rec in json.loads(cache.read_text(encoding="utf-8")):
            if str(rec.get("page")) == str(page) and (rec.get("text") or "").strip():
                return rec["text"]
    return None


def ocr_tesseract(doc, page):
    """Local Tesseract's text of a page, or None if it is not installed or reads nothing."""
    exe = next((t for t in TESSERACT if os.path.exists(t)), None)
    if exe:
        with tempfile.TemporaryDirectory() as tmp:
            png = os.path.join(tmp, "page.png")
            doc[page - 1].get_pixmap(dpi=200).save(png)
            r = subprocess.run([exe, png, "stdout"], capture_output=True, text=True, timeout=300)
            if r.stdout.strip():
                return r.stdout
    return None


def check_quotes(filings, registers=None):
    """[(register, key, fragment, status)] for every fragment of every quote: "ok", "ok_ocr", "not_found",
    "not_found_ocr" (every cited page read only as an image) or "no_text" (no cited page could be read)."""
    out = []
    for reg in (REGISTERS if registers is None else registers):
        for key, e in sorted(entries(reg).items()):
            frags = fragments(e.get("quote", ""))
            if not frags:
                continue
            path = Path(filings) / e["source_file"]
            texts, ocr = [], []
            if not path.is_file():
                pass
            elif path.suffix.lower() in (".html", ".htm"):
                texts.append(norm(html_text(path)))
            else:
                import fitz
                doc = fitz.open(str(path))
                for p in (p for p in e.get("pages", []) if isinstance(p, int) and 1 <= p <= doc.page_count):
                    layer = doc[p - 1].get_text()
                    cached = ocr_cache(filings, e, p)
                    if cached is None and len(layer.strip()) >= MIN_TEXT:
                        texts.append(norm(layer))  # a page with a text layer: a fragment not in it is a failure
                        continue
                    # an image page (the extraction OCR-read it, or its layer is empty): its text layer, if any, is a
                    # header only, so the fragment is looked for in the OCR text as well
                    t = cached if cached is not None else ocr_tesseract(doc, p)
                    if layer.strip():
                        ocr.append(norm(layer))
                    if t:
                        ocr.append(norm(t))
                doc.close()
            for f in frags:
                n = norm(f)
                if any(n in t for t in texts):
                    status = "ok"
                elif any(n in t for t in ocr):
                    status = "ok_ocr"
                elif texts:
                    status = "not_found"
                elif ocr:
                    status = "not_found_ocr"
                else:
                    status = "no_text"
                out.append((Path(reg).name, key, f, status))
    return out


def damaged(registers=None):
    """[(register name, key, field)] for every entry with a string holding U+FFFD."""
    out = []
    for reg in (REGISTERS if registers is None else registers):
        with open(reg, encoding="utf-8") as fh:
            raw = json.load(fh)
        for key, v in raw.items():
            for field, val in (v if isinstance(v, dict) else {"": v}).items():
                if "\ufffd" in json.dumps(val, ensure_ascii=False):
                    out.append((Path(reg).name, key, field))
    return out


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    filings = argv[0] if argv else os.environ.get("LLOYDS_FILINGS_DIR", DEFAULT_FILINGS)
    rows = check(filings) + check(filings, AUDIT_REGISTERS)
    bad = [r for r in rows if r[2] != "ok"]
    for name, key, status, detail in bad:
        print("%s %s: %s (%s)" % (name, key, status.upper(), detail))
    print("%d source files checked in %s: %d ok, %d mismatched or missing"
          % (len(rows), filings, len(rows) - len(bad), len(bad)))
    quotes = check_quotes(filings)
    failed = [q for q in quotes if q[3] in ("not_found", "no_text")]
    for name, key, frag, status in failed + [q for q in quotes if q[3] in ("ok_ocr", "not_found_ocr")]:
        print("%s %s: %s: '%s'" % (name, key, status.upper(), frag[:100]))
    counts = {s: sum(1 for q in quotes if q[3] == s) for s in ("ok", "ok_ocr", "not_found_ocr", "not_found", "no_text")}
    print("%d quote fragments: %s" % (len(quotes), ", ".join("%d %s" % (n, s) for s, n in counts.items())))
    dmg = damaged()
    for name, key, field in dmg:
        print("%s %s: U+FFFD in %s" % (name, key, field or "the entry"))
    print("%d damaged characters (U+FFFD)" % len(dmg))
    return 1 if bad or not rows or failed or dmg else 0


if __name__ == "__main__":
    sys.exit(main())
