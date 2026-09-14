r"""Print a filing's pages as text, the same way for every adjudicator. Read-only.

    python filing_pages.py syndicate_1183_2017 18 19 34
    python filing_pages.py syndicate_780_2017 31 --rotate 180
    python filing_pages.py syndicate_1183_2017 --find "prior year"     (pages whose text matches)

Page numbers are the PDF's own page order, counted from 1, as the adjudication packs use them.
A report filed as HTML is read from the PDF the extraction driver converted it to
(pdf_extraction/html_converted/<stem>.pdf), because that is the document whose pages the packs and
the records cite; the tool says which file it read. A page with a text layer is printed from it. A
page without one (a scanned filing) is OCR'd with Tesseract at 240 dpi; --rotate turns the image
first, for a page printed sideways or upside down (the page's /Rotate attribute is printed so the
reader can tell). Nothing is written.
"""
import argparse
import re
import sys
from pathlib import Path

import fitz

ROOT = Path(r"D:/dev/lloyds_reserve_stress_testing")
PDFS = ROOT / "syndicate_reports" / "pdfs"
CONVERTED = ROOT / "pdf_extraction" / "html_converted"
sys.path.insert(0, str(ROOT))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

_ocr_ready = None


def _ocr(page, rotate):
    global _ocr_ready
    if _ocr_ready is None:
        try:
            import test_gemini  # noqa: F401  -- sets pytesseract's Tesseract path
            import pytesseract  # noqa: F401
            from PIL import Image  # noqa: F401
            _ocr_ready = True
        except Exception as exc:
            print("(OCR unavailable: %s)" % exc)
            _ocr_ready = False
    if not _ocr_ready:
        return None
    import pytesseract
    from PIL import Image
    pix = page.get_pixmap(dpi=240)
    img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
    if rotate:
        img = img.rotate(rotate, expand=True)
    return pytesseract.image_to_string(img)


def page_text(doc, pno, rotate=0):
    page = doc[pno - 1]
    text = page.get_text() or ""
    if len(text.strip()) >= 40 and not rotate:
        return "text layer", page.rotation, text
    got = _ocr(page, rotate)
    return ("OCR%s" % (" rotated %d" % rotate if rotate else "")), page.rotation, (got or "")


def filing_path(stem):
    """The PDF a pack's page numbers refer to: the filed PDF, else the HTML report's conversion."""
    pdf = PDFS / ("%s.pdf" % stem)
    if pdf.exists():
        return pdf, "filed PDF"
    conv = CONVERTED / ("%s.pdf" % stem)
    if conv.exists():
        html = [p.name for p in PDFS.glob("%s.htm*" % stem)]
        return conv, "PDF converted from the HTML report %s" % (html[0] if html else "(HTML not found)")
    return None, None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("stem")
    ap.add_argument("pages", nargs="*", type=int)
    ap.add_argument("--rotate", type=int, default=0)
    ap.add_argument("--find", default=None, help="print only pages whose text matches this regex")
    a = ap.parse_args()
    path, what = filing_path(a.stem)
    if path is None:
        raise SystemExit("no filing for %s in %s or %s" % (a.stem, PDFS, CONVERTED))
    doc = fitz.open(str(path))
    try:
        pages = a.pages or list(range(1, doc.page_count + 1))
        print("%s: %d pages (%s: %s)" % (a.stem, doc.page_count, what, path.name))
        for p in pages:
            if not 1 <= p <= doc.page_count:
                print("(page %d does not exist)" % p)
                continue
            how, rot, text = page_text(doc, p, a.rotate)
            if a.find and not re.search(a.find, text, re.I):
                continue
            print("=" * 25, "page %d (%s; /Rotate %s)" % (p, how, rot), "=" * 25)
            print("\n".join(ln.rstrip() for ln in text.splitlines() if ln.strip()))
    finally:
        doc.close()


if __name__ == "__main__":
    main()
