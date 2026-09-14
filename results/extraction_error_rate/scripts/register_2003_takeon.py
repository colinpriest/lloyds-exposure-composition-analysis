r"""Implementation note 4: 2003/2018 as a take-on in the analysis repository's data/takeon_not_development.json.

Run only after both readings find the take-on dominating the triangle figure and the owner has decided. Refuses unless
the protocol has implementation note 4; the reader's file holds one reading of 2003/2018 whose census_check.takeon_triangle
finding is true, with pages, a quote and a transferred amount; the editor's census reading in
error-rate-verification-ninth.json finds the take-on dominating the figure, with its amount; the two amounts agree within
2%; and the register has no 2003_2018 entry. --owner-decision carries the owner's answer, verbatim.

    python register_2003_takeon.py --owner-decision "<the owner's answer>"
"""
import argparse
import io
import json
from pathlib import Path

SCR = Path(__file__).resolve().parent
AN = Path(r"D:/dev/IME-Lloyds-exposure-composition")
REGISTER = AN / "data" / "takeon_not_development.json"
STEM, KEY = "syndicate_2003_2018", "2003_2018"
SOURCE = "extraction error-rate study, take-on base census, implementation note 4 (results/extraction_error_rate/)"
QUOTE = ("p44 note 12, gross claims outstanding ($000): 'As at 1 January 2018 5,344,064'; 'Movement in the provision "
         "253,539'; 'RITC from S1209 532,922'; 'Foreign exchange movements (208,828)'; 'As at 31 December 2018 5,921,697'. "
         "p45 note 13 'Gross claims development' ($m), end-2017 and end-2018 diagonals: 2012 1,376 / 1,435; 2013 1,319 / "
         "1,375; 2014 1,574 / 1,691; 2015 1,594 / 1,641; 2016 1,984 / 2,124. p39 note 5: 'An unfavorable run-off deviation "
         "(prior accident years' deterioration) of $92m for Syndicate 2003 was experienced during the year'. "
         "syndicate_2003_2017, 'Gross claims development', end-2017 diagonal: 2012 1,391; 2013 1,334; 2014 1,587; "
         "2015 1,606; 2016 1,984")


def load(p):
    return json.load(io.open(str(p), encoding="utf-8"))


def need(cond, why):
    if not cond:
        raise SystemExit(why)


def short(text, n=480):
    text = " ".join(str(text or "").split())
    return text if len(text) <= n else text[:n].rsplit(" ", 1)[0] + " ..."


ap = argparse.ArgumentParser()
ap.add_argument("--owner-decision", required=True)
a = ap.parse_args()
need(a.owner_decision.strip(), "--owner-decision is empty")
need("## Implementation note 4" in io.open(str(SCR / "error-rate-protocol.md"), encoding="utf-8").read(),
     "the protocol has no implementation note 4")

readers = [v for v in load(SCR / "error-rate-verdicts-ninth-sixth-2003.json") if v.get("stem") == STEM]
need(len(readers) == 1, "the reader's file must hold exactly one reading of %s" % STEM)
r = readers[0]
t = (r.get("census_check") or {}).get("takeon_triangle") or {}
need(t.get("finding") is True, "the reader does not find the take-on dominating the figure (finding %s)" % t.get("finding"))
need(str(r.get("quote") or "").strip() and r.get("pages"), "the reader's reading has no quote or pages")
r_amt = t.get("takeon_amount_m")

editors = [v for v in load(SCR / "error-rate-verification-ninth.json") if v.get("stem") == STEM]
need(len(editors) == 1, "no editor's census reading of %s" % STEM)
e = editors[0]
need("so it dominates it" in (e.get("why") or ""), "the editor's census reading does not find the take-on dominating the figure")
e_amt = ((e.get("census_check") or {}).get("takeon_base") or {}).get("takeon_amount_m")
need(all(isinstance(x, (int, float)) and not isinstance(x, bool) for x in (r_amt, e_amt)),
     "both readings must give the transferred amount (%s, %s)" % (r_amt, e_amt))
need(abs(r_amt - e_amt) <= 0.02 * max(abs(r_amt), abs(e_amt)), "the readings' amounts %s and %s differ by more than 2%%" % (r_amt, e_amt))

register = load(REGISTER)
need(KEY not in register, "%s is registered already" % KEY)
pages = []
for p in list(e.get("pages") or []) + list(t.get("pages") or []) + list(r.get("pages") or []):
    if isinstance(p, int) and not isinstance(p, bool) and p > 0 and p not in pages:
        pages.append(p)
register[KEY] = {
    "takeon_amount_m": float(e_amt),
    "pages": pages,
    "quote": QUOTE,
    "readings": [
        "take-on base census, editor's reading (%s): the take-on dominates the figure; %s" % (e.get("recorded"), short(e.get("why"))),
        "implementation note 4, reading: takeon_triangle %s; %s" % (t.get("finding"), short(t.get("evidence") or r.get("reasoning"))),
    ],
    "decision": "owner's decision, 14 September 2026 (error-rate protocol, implementation note 4): %s" % a.owner_decision.strip(),
    "source": SOURCE,
}
io.open(str(REGISTER), "w", encoding="utf-8", newline="").write(json.dumps(register, indent=1, ensure_ascii=False) + "\n")
print("registered %s: take-on %s, pages %s" % (KEY, e_amt, pages))
