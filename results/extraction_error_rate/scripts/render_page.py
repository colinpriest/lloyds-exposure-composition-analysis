r"""Render filing pages to PNG for a visual check of a text-layer reading (read-only).

    python render_page.py syndicate_623_2014 45
    python render_page.py syndicate_623_2014 45 --clip 0 0.1 1 0.6 --dpi 160   fractions of the page

Writes renders/<stem>_p<page>.png in this directory and prints each path.
"""
import argparse
from pathlib import Path

import fitz

SCR = Path(__file__).resolve().parent
PDFS = Path(r"D:/dev/lloyds_reserve_stress_testing/syndicate_reports/pdfs")

ap = argparse.ArgumentParser()
ap.add_argument("stem")
ap.add_argument("pages", nargs="+", type=int)
ap.add_argument("--dpi", type=int, default=110)
ap.add_argument("--clip", nargs=4, type=float, default=None)
a = ap.parse_args()

out_dir = SCR / "renders"
out_dir.mkdir(exist_ok=True)
doc = fitz.open(str(PDFS / (a.stem + ".pdf")))
for p in a.pages:
    page = doc[p - 1]
    clip = None
    if a.clip:
        r = page.rect
        clip = fitz.Rect(r.x0 + a.clip[0] * r.width, r.y0 + a.clip[1] * r.height,
                         r.x0 + a.clip[2] * r.width, r.y0 + a.clip[3] * r.height)
    out = out_dir / ("%s_p%d.png" % (a.stem, p))
    page.get_pixmap(dpi=a.dpi, clip=clip).save(str(out))
    print(out)
