r"""The ninth amendment's point 1: the eighth census's repairs, written into the analysis repository's registers from
the readings themselves (eighth amendment, point 5, and the owner's decision of 14 September 2026 on 2010/2015).

  data/pyd_confirmed_figures.json      2791/2015 -2.131, 3010/2018 -4.140, 382/2017 +7.401 (triangle, gross);
                                       5678/2015 -8.135 (stated, gross); 2010/2015 -9.646 (stated, gross; the owner's
                                       decision); 510/2014: the net table's -48.4 (triangle, net)
  data/opening_reserves_confirmed.json 1225/2018 595.8, 609/2023 1,171.381

Each entry carries the pages its readings cited, the second reading's quote from the filing and a summary of each
reading. The script refuses if the protocol has no ninth amendment, if an entry exists already, or if the readings do
not say what the entry claims: both errors with the same figure; for 2010/2015 both errors with the figures the
decision names; for 510/2014 both errors and a net table found by both; for the opening reserves an opening found by
both with the same gross figure.

    python register_eighth_repairs.py
"""
import io
import json
from pathlib import Path

SCR = Path(__file__).resolve().parent
AN = Path(r"D:/dev/IME-Lloyds-exposure-composition")
CONFIRMED = AN / "data" / "pyd_confirmed_figures.json"
OPENING = AN / "data" / "opening_reserves_confirmed.json"
SOURCE = "extraction error-rate study, eighth census, repaired under the ninth amendment (results/extraction_error_rate/)"
DECISION = "owner's decision, 14 September 2026 (error-rate protocol, ninth amendment)"


def load(p):
    return json.load(io.open(str(p), encoding="utf-8"))


def save(p, obj):
    io.open(str(p), "w", encoding="utf-8", newline="").write(json.dumps(obj, indent=1, ensure_ascii=False) + "\n")


def need(cond, why):
    if not cond:
        raise SystemExit(why)


need("## Ninth amendment" in io.open(str(SCR / "error-rate-protocol.md"), encoding="utf-8").read(),
     "the protocol has no ninth amendment: no repair before it")
first = {v["stem"]: v for v in load(SCR / "error-rate-verdicts-eighth.json")}
second = {v["stem"]: v for v in load(SCR / "error-rate-verification-eighth.json")}


def short(text, n=480):
    text = " ".join(str(text or "").split())
    return text if len(text) <= n else text[:n].rsplit(" ", 1)[0] + " ..."


def pages(*readings):
    out = []
    for r in readings:
        for p in r.get("pages") or []:
            if isinstance(p, int) and not isinstance(p, bool) and p > 0 and p not in out:
                out.append(p)
    return out


def readings_of(f, s):
    return ["eighth census, first reading (%s): %s%s; %s" % (f.get("first_reader"), f.get("clarified_verdict") or f.get("verdict"),
                                                            ", " + f["error_kind"] if f.get("error_kind") else "",
                                                            short(f.get("reasoning") or f.get("arithmetic"))),
            "eighth census, second reading (editor, %s): %s%s; %s" % (s.get("recorded"), s.get("verdict"),
                                                                     ", " + s["error_kind"] if s.get("error_kind") else "",
                                                                     short(s.get("why")))]


def same(x, y):
    return x is not None and y is not None and abs(float(x) - float(y)) < 1e-9


def part(reading, name):
    return ((reading.get("census_check") or {}).get(name) or {})


def both(key):
    s = "syndicate_" + key
    need(s in first and s in second, "%s: the census holds no two readings of it" % key)
    need((AN / "pdf_extraction" / ("%s.json" % s)).exists(), "%s: no extraction record" % key)
    return first[s], second[s]


confirmed, openings = load(CONFIRMED), load(OPENING)
FIGURES = {"2791_2015": (-2.131, "triangle"), "3010_2018": (-4.14, "triangle"), "382_2017": (7.401, "triangle"),
           "5678_2015": (-8.135, "stated")}
CKEYS = sorted(FIGURES) + ["2010_2015", "510_2014"]
OKEYS = ["1225_2018", "609_2023"]
need(not set(CKEYS) & set(confirmed), "confirmed-figure entries exist already: %s" % sorted(set(CKEYS) & set(confirmed)))
need(not set(OKEYS) & set(openings), "opening entries exist already: %s" % sorted(set(OKEYS) & set(openings)))

# the four figures both readings agree on
for key, (fig, kind) in FIGURES.items():
    f, s = both(key)
    need(f.get("clarified_verdict") == "error" and s.get("verdict") == "error", "%s: both readings must be errors" % key)
    need(same(f.get("filing_figure_m"), fig) and same(s.get("filing_figure_m"), fig), "%s: the readings' figures are not %s" % (key, fig))
    confirmed[key] = {"figure_m": fig, "figure_kind": kind, "basis": "gross", "pages": pages(s, f),
                      "quote": s["quote"], "readings": readings_of(f, s), "source": SOURCE}
f, s = both("382_2017")
need(part(f, "net_table").get("finding") is True and part(s, "net_table").get("finding") is True,
     "382/2017: both readings must find the net table the route read")
confirmed["382_2017"]["decision"] = (
    "ninth amendment, point 1: both readings also find the net table the route read (p48); the readings agree on the "
    "gross table's figure, which the eighth amendment's point 5 repairs, so the record keeps a gross basis")

# 2010/2015: both readings find a sign error; the owner decided the figure
f, s = both("2010_2015")
need(f.get("clarified_verdict") == "error" and s.get("verdict") == "error", "2010/2015: both readings must be errors")
need(same(f.get("filing_figure_m"), -41.232) and same(s.get("filing_figure_m"), -9.646),
     "2010/2015: the readings' figures are not the -41.232 and -9.646 the decision names")
need("(9,646)" in (s.get("quote") or "") and "-9.646" in (f.get("reasoning") or ""),
     "2010/2015: both readings must quote the note's gross prior-year line (9,646)")
confirmed["2010_2015"] = {
    "figure_m": -9.646, "figure_kind": "stated", "basis": "gross", "pages": pages(s, f), "quote": s["quote"],
    "readings": readings_of(f, s),
    "decision": DECISION + ": repaired by -9.646m, the note's gross 'Claims incurred in prior underwriting year' that rule 2 "
                "checks a stated route against and both readings quote; the first reading recorded the 2013 and prior "
                "accounts' -41.232m (p13) as its figure",
    "source": SOURCE}

# 510/2014: the net table's figure, net
f, s = both("510_2014")
need(f.get("clarified_verdict") == "error" and s.get("verdict") == "error", "510/2014: both readings must be errors")
need(part(f, "net_table").get("finding") is True and part(s, "net_table").get("finding") is True,
     "510/2014: both readings must find the net table")
need("48.4" in (f.get("reasoning") or "") + (f.get("arithmetic") or "") and "-48.4m" in (s.get("why") or ""),
     "510/2014: both readings must name the net table's -48.4")
confirmed["510_2014"] = {"figure_m": -48.4, "figure_kind": "triangle", "basis": "net", "pages": pages(s, f),
                         "quote": s["quote"], "readings": readings_of(f, s),
                         "decision": "eighth amendment, point 5: both readings find the table 'after reinsurance "
                                     "recoveries' and no gross figure in the filing; recorded and excluded as a "
                                     "net-basis record, as 1880/2014",
                         "source": SOURCE}

# the two opening reserves
for key, gross in (("1225_2018", 595.8), ("609_2023", 1171.381)):
    f, s = both(key)
    fo, so = part(f, "opening"), part(s, "opening")
    need(fo.get("finding") is True and so.get("finding") is True, "%s: both readings must find another line" % key)
    need(same(fo.get("gross_opening_m"), gross) and same(so.get("gross_opening_m"), gross),
         "%s: the readings' gross opening reserves are not %s" % (key, gross))
    adopted = (f.get("opening_reserves") or {}).get("adopted_m")
    openings[key] = {"opening_reserves_m": gross, "pages": pages(s, f), "quote": s["quote"],
                     "readings": ["eighth census, first reading (%s): opening reserves adopted %s, gross %s; %s"
                                  % (f.get("first_reader"), adopted, fo.get("gross_opening_m"), short(fo.get("evidence"), 360)),
                                  "eighth census, second reading (editor, %s): %s"
                                  % (s.get("recorded"), short(s.get("why"), 480))],
                     "decision": "eighth amendment, point 5: both readings find the adopted opening reserves to be the "
                                 "reinsurers' share and agree on the gross claims outstanding at 1 January",
                     "source": SOURCE}

save(CONFIRMED, confirmed)
save(OPENING, openings)
print("registered: confirmed figures %s; opening reserves %s" % (CKEYS, OKEYS))
for key in CKEYS:
    e = confirmed[key]
    print("  %-10s figure %-8s kind %-8s basis %-6s pages %s" % (key, e["figure_m"], e["figure_kind"], e["basis"], e["pages"]))
for key in OKEYS:
    print("  %-10s opening %s pages %s" % (key, openings[key]["opening_reserves_m"], openings[key]["pages"]))
