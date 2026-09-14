r"""Facts to set three census rules on, before the eighth amendment is written (read-only; no record is read for a verdict).

1. 1880/2014 p26: every place "gross" and a net marker appear.
2. 2003/2018: every passage naming Syndicate 1209.
3. The RITC scan's top-level decision for records its events flag inward in the report year.
4. Gross and net heading markers on pages the loose net_table rule flagged.

    python probe_census_rules.py
"""
import io
import json
import re
import sys

import fitz

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
EX = "D:/dev/lloyds_reserve_stress_testing"


def pdf(stem):
    return fitz.open("%s/syndicate_reports/pdfs/%s.pdf" % (EX, stem))


def around(text, m, n=120):
    return re.sub(r"\s+", " ", text[max(0, m.start() - n): m.end() + n])


print("1. 1880/2014 p26")
t = pdf("syndicate_1880_2014")[25].get_text()
for m in re.finditer(r"gross", t, re.I):
    print("  gross: ...%s..." % around(t, m))
for m in re.finditer(r"after reinsurance|net of reinsurance|net claims", t, re.I):
    print("  net:   ...%s..." % around(t, m))

print("2. 2003/2018: Syndicate 1209")
doc = pdf("syndicate_2003_2018")
for i, pg in enumerate(doc):
    tx = pg.get_text()
    for m in re.finditer(r"1209", tx):
        print("  p%d: ...%s..." % (i + 1, around(tx, m, 260)))

print("3. RITC scan top level")
scan = json.load(io.open(EX + "/pdf_extraction/ritc_scan.json", encoding="utf-8"))
for k in ("2791_2015", "2791_2017", "1110_2020", "3000_2017", "435_2018", "1254_2023", "510_2014", "1969_2022",
          "2008_2023", "3500_2019", "4444_2023", "1884_2021", "3330_2017", "1274_2018", "2488_2019"):
    v = scan.get(k, {})
    print("  %-10s occurred %-5s direction %-8s year %-5s %s" % (k, v.get("ritc_occurred"), v.get("direction"),
                                                              v.get("event_year"), (v.get("evidence") or "")[:160]))

print("4. heading markers")
GROSS = re.compile(r"gross of reinsurance|gross claims|incurred gross|ultimate gross|cumulative gross|gross basis|"
                   r"before reinsurance|gross ultimate|gross of reinsurers|\bgross\s*\n", re.I)
NET = re.compile(r"net of reinsurance|after reinsurance|net claims|incurred net|ultimate net|cumulative net|net basis", re.I)
for stem, page in (("syndicate_1880_2014", 26), ("syndicate_510_2020", 35), ("syndicate_1967_2015", 49),
                   ("syndicate_609_2016", 34), ("syndicate_318_2015", 54), ("syndicate_1861_2016", 40),
                   ("syndicate_4000_2017", 34), ("syndicate_1910_2018", 36), ("syndicate_6118_2017", 36),
                   ("syndicate_1955_2015", 48), ("syndicate_1856_2018", 38), ("syndicate_5820_2016", 42)):
    tx = pdf(stem)[page - 1].get_text()
    g = [around(tx, m, 30) for m in GROSS.finditer(tx)]
    n = [around(tx, m, 30) for m in NET.finditer(tx)]
    print("  %-22s p%-3d gross %d %s | net %d %s" % (stem, page, len(g), g[:2], len(n), n[:2]))
