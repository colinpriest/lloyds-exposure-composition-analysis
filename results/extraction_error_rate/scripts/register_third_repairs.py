r"""The eighth amendment's point 2: the repairs the owner decided on 14 September 2026, written into the analysis
repository's registers from the readings themselves.

  data/pyd_confirmed_figures.json      382/2015, 382/2016, 382/2018, 382/2019, 2010/2018, 3010/2019: the printed gross
                                       triangle's figure (triangle, gross); 1880/2014: the net table's -13.6 (triangle,
                                       net); 623/2014: no figure, unknown basis
  data/takeon_not_development.json     1274/2018 (the Motor RITC, 317.39), 1980/2018 (the portfolio transfer, 163.213)
  data/opening_reserves_confirmed.json 2003/2018 (5,344.064), a new register

Each entry carries the pages its readings cited, a quote from the filing and a summary of each reading. The script
refuses if the protocol has no eighth amendment, if an entry exists already, or if the readings do not say what the
entry claims (both errors, the same figure; the take-on and the opening named in both).

    python register_third_repairs.py
"""
import io
import json
from pathlib import Path

SCR = Path(__file__).resolve().parent
AN = Path(r"D:/dev/IME-Lloyds-exposure-composition")
CONFIRMED = AN / "data" / "pyd_confirmed_figures.json"
TAKEON = AN / "data" / "takeon_not_development.json"
OPENING = AN / "data" / "opening_reserves_confirmed.json"
SOURCE = "extraction error-rate study, third sample, repaired under the eighth amendment (results/extraction_error_rate/)"
DECISION = "owner's decision, 14 September 2026 (error-rate protocol, eighth amendment)"


def load(p):
    return json.load(io.open(str(p), encoding="utf-8"))


def save(p, obj):
    io.open(str(p), "w", encoding="utf-8", newline="").write(json.dumps(obj, indent=1, ensure_ascii=False) + "\n")


if "## Eighth amendment" not in io.open(str(SCR / "error-rate-protocol.md"), encoding="utf-8").read():
    raise SystemExit("the protocol has no eighth amendment: no repair before it")
first = {v["stem"]: v for v in load(SCR / "error-rate-verdicts-third.json")}
second = {v["stem"]: v for v in load(SCR / "error-rate-verification-third.json")}
passing_first = {v["stem"]: v for v in load(SCR / "error-rate-verdicts-passing.json")}
passing_second = {v["stem"]: v for v in load(SCR / "error-rate-verification-passing.json")}


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


def readings_of(f, s, label, first_text=None, second_text=None):
    return ["%s, first reading (%s): %s%s; %s" % (label, f.get("first_reader"), f.get("clarified_verdict") or f.get("verdict"),
                                                 ", " + f["error_kind"] if f.get("error_kind") else "",
                                                 short(first_text or f.get("arithmetic") or f.get("reasoning"))),
            "%s, second reading (editor, %s): %s%s; %s" % (label, s.get("recorded"), s.get("verdict"),
                                                          ", " + s["error_kind"] if s.get("error_kind") else "",
                                                          short(second_text or s.get("why")))]


def need(cond, why):
    if not cond:
        raise SystemExit(why)


confirmed, takeons = load(CONFIRMED), load(TAKEON)
openings = load(OPENING) if OPENING.exists() else None
KEYS = ["382_2015", "382_2016", "382_2018", "382_2019", "2010_2018", "3010_2019", "1880_2014", "623_2014"]
need(not set(KEYS) & set(confirmed), "confirmed-figure entries exist already: %s" % sorted(set(KEYS) & set(confirmed)))
need(not {"1274_2018", "1980_2018"} & set(takeons), "take-on entries exist already")
need(openings is None, "data/opening_reserves_confirmed.json exists already")

# the six confirmed figures
FIGURES = {"382_2015": 2.626, "382_2016": -14.328, "382_2018": 24.988, "382_2019": 12.549,
           "2010_2018": -15.755, "3010_2019": -1.925}
for key, fig in FIGURES.items():
    f, s = first["syndicate_" + key], second["syndicate_" + key]
    need(f.get("clarified_verdict") == "error" and s.get("verdict") == "error", "%s: both readings must be errors" % key)
    need(all(x is not None and abs(float(x) - fig) < 1e-9 for x in (f.get("filing_figure_m"), s.get("filing_figure_m"))),
         "%s: the readings' figures are not %s" % (key, fig))
    confirmed[key] = {"figure_m": fig, "figure_kind": "triangle", "basis": "gross", "pages": pages(s, f),
                      "quote": s["quote"], "readings": readings_of(f, s, "third sample"), "source": SOURCE}

# 1880/2014: the net table's figure, net
f, s = first["syndicate_1880_2014"], second["syndicate_1880_2014"]
need(f.get("clarified_verdict") == "error" and s.get("verdict") == "error", "1880/2014: both readings must be errors")
need("-13.6" in (f.get("arithmetic") or "") and "net table" in (s.get("why") or ""), "1880/2014: both readings must name the net table's -13.6")
confirmed["1880_2014"] = {"figure_m": -13.6, "figure_kind": "triangle", "basis": "net", "pages": pages(s, f),
                          "quote": s["quote"], "readings": readings_of(f, s, "third sample"), "source": SOURCE}

# 623/2014: no figure, unknown basis
f, s = passing_first["syndicate_623_2014"], passing_second["syndicate_623_2014"]
need(s.get("verdict") == "error" and "loss-ratio" in (s.get("error_kind") or ""), "623/2014: the second reading must find loss-ratio points")
confirmed["623_2014"] = {"figure_m": None, "figure_kind": None, "basis": "unknown", "pages": pages(s, f),
                         "quote": s["quote"], "readings": readings_of(f, s, "found in passing"),
                         "decision": DECISION + ": excluded, its adopted -17.3 is a sum of loss-ratio points, not an amount",
                         "source": "extraction error-rate study, records found in passing (seventh amendment, point 2); "
                                   "excluded under the eighth amendment"}
confirmed["_purpose"] = confirmed["_purpose"].rstrip() + (
    " An entry may instead record a basis the readings established: a net figure with basis 'net' (1880/2014, whose "
    "table is 'after reinsurance recoveries'), or no figure (figure_m and figure_kind null) with basis 'unknown' when the "
    "adopted figure is not an amount and the filing gives none to put in its place (623/2014). The loader keeps the "
    "adopted figure for an entry without one, and either entry is recorded and excluded like any net or unknown-basis record.")

# the two take-ons
f, s = first["syndicate_1274_2018"], second["syndicate_1274_2018"]
need("317,390" in (f.get("basis_check") or "") + (f.get("reasoning") or "") and "317.4m" in (s.get("why") or ""),
     "1274/2018: both readings must name the Motor RITC")
takeons["1274_2018"] = {"takeon_amount_m": 317.39, "pages": pages(s, f),
                        "quote": s["quote"] + " | first reading, p37: 'Motor RITC accepted on 1/1/18: gross 317,390, reinsurance 303,482, net 13,908' (the reader's transcription of the roll-forward row)",
                        "readings": readings_of(f, s, "third sample", first_text=f.get("reasoning")),
                        "decision": DECISION + ": excluded, the triangle figure's 2016 step is almost all the Motor RITC",
                        "source": SOURCE}
f, s = first["syndicate_1980_2018"], second["syndicate_1980_2018"]
need("163,213" in (f.get("arithmetic") or "") + (f.get("reasoning") or "") and "163.2m" in (s.get("why") or ""),
     "1980/2018: both readings must name the portfolio transferred")
takeons["1980_2018"] = {"takeon_amount_m": 163.213, "pages": pages(s, f), "quote": s["quote"],
                        "readings": readings_of(f, s, "third sample"),
                        "decision": DECISION + ": excluded, the adopted figure is the loss portfolio transfer class's premium",
                        "source": SOURCE}
takeons["_purpose"] = takeons["_purpose"].rstrip() + (
    " A triangle figure whose latest step the filing shows to be dominated by a take-on is a take-on in the same sense "
    "(1274/2018: the Motor RITC accepted on 1 January 2018), and so is the premium of a loss portfolio transfer adopted "
    "as development (1980/2018).")

# 2003/2018's opening reserves
f, s = first["syndicate_2003_2018"], second["syndicate_2003_2018"]
fo = f.get("opening_reserves") or {}
need(fo.get("within_2pct") is False and abs(float(fo.get("filing_m")) - 5344.064) < 1e-9, "2003/2018: the first reading must find 5,344.064")
need("5,344.064" in (s.get("why") or "") and "reinsurers' share" in (s.get("why") or ""), "2003/2018: the second reading must find the reinsurers' share")
openings = {
    "_purpose": "Opening reserves confirmed by two readings of the filing, for records whose adopted opening reserves the "
                "extraction error-rate study (PLAN R213, eighth amendment) found to be another line of the filing. "
                "run_analysis.py (load_and_classify, apply_confirmed_opening) adopts the register's opening reserves for "
                "these records only, before the FX conversion, recomputes the development percentage on them, and "
                "discloses the correction in the record's data_quality_notes; the development figure and its route are "
                "left as they are. opening_reserves_m is in millions of the report's own currency. The loader refuses an "
                "entry without two readings, its pages and a quote; an entry marked _to_complete is skipped, not applied, "
                "until it carries them.",
    "2003_2018": {"opening_reserves_m": 5344.064, "pages": sorted(set([44] + pages(s, f))),
                  "quote": "p44 (USD000; provision for unearned premium, claims outstanding): 'Gross Technical Provisions "
                           "As at 1 January 2018 1,545,443 5,344,064'; 'Reinsurers' share of technical provisions As at 1 "
                           "January 2018 448,171 1,659,705'",
                  "readings": ["third sample, first reading (%s): opening reserves adopted %s, filing %s (p%s), outside 2%%; %s"
                               % (f.get("first_reader"), fo.get("adopted_m"), fo.get("filing_m"), fo.get("page"),
                                  short(f.get("reasoning"), 300)),
                               "third sample, second reading (editor, %s): %s" % (s.get("recorded"),
                                   short([x for x in (s.get("why") or "").split(". ") if "pening" in x][0], 400))],
                  "decision": DECISION + ": the confirmed opening reserves replace the adopted ones",
                  "source": SOURCE}}

save(CONFIRMED, confirmed)
save(TAKEON, takeons)
save(OPENING, openings)
print("registered: confirmed figures %s; take-ons 1274_2018, 1980_2018; opening reserves 2003_2018" % KEYS)
for key in KEYS:
    e = confirmed[key]
    print("  %-10s figure %-8s kind %-8s basis %-7s pages %s" % (key, e["figure_m"], e["figure_kind"], e["basis"], e["pages"]))
for key in ("1274_2018", "1980_2018"):
    print("  %-10s take-on %s pages %s quote %s" % (key, takeons[key]["takeon_amount_m"], takeons[key]["pages"], takeons[key]["quote"][:200]))
print("  2003_2018  opening %s pages %s" % (openings["2003_2018"]["opening_reserves_m"], openings["2003_2018"]["pages"]))
