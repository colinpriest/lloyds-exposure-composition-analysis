r"""The ninth amendment's point 5: the take-on base census's adjustments, written into the analysis repository's register
data/opening_reserves_takeon_base.json from the census's scored drafts.

Each entry carries the 1 January gross claims outstanding the loader holds for the record, the gross claims reserves
both readings found the adopted figure covers, the pages the readings cited, a quote from the filing and a summary of
each reading. The script refuses if the protocol has no ninth amendment, if an entry exists already, or if a draft does
not follow from the scored result: the outcome must be adjusted, the readings' amounts must agree within 2%, the amount
must be 5% or more of the opening reserves, and the draft's opening reserves must be the brief's adopted figure.

    python register_ninth_takeon_base.py
"""
import io
import json
from pathlib import Path

SCR = Path(__file__).resolve().parent
AN = Path(r"D:/dev/IME-Lloyds-exposure-composition")
REGISTER = AN / "data" / "opening_reserves_takeon_base.json"
OPENING = "adopted_opening_reserves_m_report_currency"
ADOPTED = "adopted_prior_year_development_m_report_currency"
SOURCE = "extraction error-rate study, take-on base census, adjusted under the ninth amendment (results/extraction_error_rate/)"
DECISION = ("owner's decision, 14 September 2026 (error-rate protocol, ninth amendment): the opening reserves carry the "
            "take-on the adopted development covers")


def load(p):
    return json.load(io.open(str(p), encoding="utf-8"))


def need(cond, why):
    if not cond:
        raise SystemExit(why)


need("## Ninth amendment" in io.open(str(SCR / "error-rate-protocol.md"), encoding="utf-8").read(),
     "the protocol has no ninth amendment: no repair before it")
drafts = load(SCR / "ninth-repairs-draft.json")
result = {r["stem"]: r for r in load(SCR / "error-rate-census-ninth-result.json")["table"]}
briefs = {b["stem"]: b for b in load(SCR / "error-rate-briefs-ninth.json")}
register = load(REGISTER)
keys = [d["stem"].replace("syndicate_", "") for d in drafts]
need(not set(keys) & set(register), "take-on base entries exist already: %s" % sorted(set(keys) & set(register)))

rows = []
for d in drafts:
    s, key = d["stem"], d["stem"].replace("syndicate_", "")
    r, b = result.get(s), briefs.get(s)
    need(r is not None and b is not None, "%s: not in the scored census" % s)
    need(r["outcome"] == "adjusted", "%s: the scored outcome is %s, not adjusted" % (s, r["outcome"]))
    a1, a2 = d["takeon_m_readings"]
    need(isinstance(a1, (int, float)) and isinstance(a2, (int, float)) and abs(a1 - a2) <= 0.02 * max(abs(a1), abs(a2)),
         "%s: the readings' amounts %s and %s do not agree within 2%%" % (s, a1, a2))
    opening, takeon = float(d["opening_reserves_m"]), float(d["takeon_m"])
    need(opening == float(b[OPENING]), "%s: the draft's opening reserves %s are not the brief's %s" % (s, opening, b[OPENING]))
    need(takeon >= 0.05 * opening, "%s: the take-on %s is under 5%% of the opening reserves %s" % (s, takeon, opening))
    need((AN / "pdf_extraction" / ("%s.json" % s)).exists(), "%s: no extraction record" % s)
    pages = [p for p in d["pages"] if isinstance(p, int) and not isinstance(p, bool) and p > 0]
    need(pages and str(d.get("quote") or "").strip() and len(d.get("readings") or []) >= 2, "%s: pages, a quote and two readings" % s)
    register[key] = {"opening_reserves_m": opening, "takeon_m": takeon, "pages": pages, "quote": d["quote"],
                     "readings": d["readings"], "decision": DECISION, "source": SOURCE}
    pyd = b[ADOPTED]
    rows.append((key, opening, takeon, None if pyd is None else 100.0 * pyd / opening,
                 None if pyd is None else 100.0 * pyd / (opening + takeon)))

io.open(str(REGISTER), "w", encoding="utf-8", newline="").write(json.dumps(register, indent=1, ensure_ascii=False) + "\n")
print("registered %d take-on base entr%s" % (len(rows), "y" if len(rows) == 1 else "ies"))
for key, opening, takeon, before, after in rows:
    print("  %-10s opening %-10s take-on %-10s severity %s%% -> %s%%" % (
        key, opening, takeon, None if before is None else round(before, 2), None if after is None else round(after, 2)))
