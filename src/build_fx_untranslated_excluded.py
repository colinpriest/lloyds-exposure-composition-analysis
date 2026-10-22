r"""Build data/fx_untranslated_excluded.json: the records the primary sample leaves for the exchange-rate rule.

The author's decision of 22 October 2026 (rule B). A record leaves the PRIMARY sample when

  (a) its development table is not retranslated between the year t-1 and year t reports across a sterling/dollar move
      of 5% or more (the cells for years before t-1 are the same in the year-t report as in the year t-1 report, so
      the step from the t-1 diagonal to the t diagonal carries the translation of the foreign-currency part of the
      book), AND
  (b) the filing's own gross claims-outstanding roll-forward prints an exchange line of at least 5% of the opening
      gross claims outstanding R.

The population screened is the 13 candidates of results/extraction_error_rate/mature-cohort/fx-translation/
fx_translation.json (written by fx-translation/measure_fx_translation.py: the primary sample's 653 records, 37 with a table not retranslated, 18
of those in a year sterling moved 5% or more against the dollar, and of those 3 with a placed exchange line of 5% or
more and 10 with no placed line), each read twice, independently, from the filing (readers F1 and F2). Both readers
agree on every record. The register holds the four records both conditions hold for ("excluded") and the nine that
were read and kept ("read_and_kept"), each with both readings' pages, quotes, figures and percentage.

The readings are archived verbatim in results/extraction_error_rate/mature-cohort/fx-translation/readings/F1.json
and F2.json (their parts 2 and 3, the aggregated column of 1945 and the outward transfers of 2689/2022 and
1492/2023, are used by build_mature_cohort_figures.py and by data/outbound_transfer_retained_base.json).

Usage:
  python src/build_fx_untranslated_excluded.py            # check the register against a rebuild; exit 1 on a difference
  python src/build_fx_untranslated_excluded.py --write    # rebuild and write the register
"""
import io
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
REGISTER = HERE / "data" / "fx_untranslated_excluded.json"
READINGS = HERE / "results" / "extraction_error_rate" / "mature-cohort" / "fx-translation" / "readings"
READERS = ("F1", "F2")
THRESHOLD_PCT = 5.0

#: the records read and the author's verdict on each (the rule applied to both readers' figures)
EXCLUDED = ("1897_2016", "2468_2016", "5151_2016", "5151_2017")
KEPT = ("218_2017", "1301_2023", "1686_2018", "1971_2023", "2468_2017", "4242_2016", "4242_2017", "4242_2018",
        "5151_2018")

#: the five records the script placed an exchange line for, under 5% (fx-translation/measure_fx_translation.py; a pattern placement,
#: not a reading, and not read twice)
SCREENED_UNDER_5 = {"1686_2023": 2.03, "2019_2023": 0.03, "2689_2022": 0.26, "4242_2022": 0.14, "4242_2023": 0.30}

RULE = (
    "The author's decision of 22 October 2026 (rule B). A record leaves the PRIMARY sample (outcome 'mature_cohort') "
    "when (a) its development table is not retranslated between the year t-1 and year t reports across a "
    "sterling/dollar move of 5% or more, so that the step from the t-1 diagonal to the t diagonal carries the "
    "translation of the foreign-currency part of the book, AND (b) the filing's own gross claims-outstanding "
    "roll-forward prints an exchange line of at least 5% of the opening gross claims outstanding R (absolute value). "
    "A record for which either condition fails stays. The loader (run_analysis.py) removes an 'excluded' entry's "
    "record from the primary at the unusable-severity step with the tag FX_UNTRANSLATED_TABLE and counts it "
    "(fx_untranslated_excluded); under outcome 'precedence_672' the register is not read and nothing changes. An entry "
    "is applied only with two independent readings of the filing (F1, F2) that give the same opening gross claims "
    "outstanding and the same exchange line, a table not retranslated, a line of at least 5% of R, and the pages and "
    "quotes. 'read_and_kept' entries record the candidates both readers found to fail a condition; the loader "
    "validates them and applies nothing for them. Built by src/build_fx_untranslated_excluded.py from the archived "
    "readings.")

POPULATION = {
    "screen": ("results/extraction_error_rate/mature-cohort/fx-translation/fx_translation.json (measure_fx_translation"
               ".py), over the primary sample's 653 records at bed49ee"),
    "records": 653,
    "table_not_retranslated": 37,
    "of_those_in_a_year_sterling_moved_5pct_or_more": 18,
    "of_those_with_a_placed_exchange_line_of_5pct_or_more": ["2468_2016", "5151_2016", "5151_2017"],
    "of_those_with_a_placed_line_under_5pct_not_read_twice": SCREENED_UNDER_5,
    "of_those_with_no_placed_line_candidates_read_twice": ["218_2017", "1301_2023", "1686_2018", "1897_2016",
                                                           "1971_2023", "2468_2017", "4242_2016", "4242_2017",
                                                           "4242_2018", "5151_2018"],
    "candidates_read_twice": 13,
    "candidates_read_twice_are": sorted(EXCLUDED + KEPT, key=lambda k: tuple(int(p) for p in k.split("_"))),
    "readers": "F1 and F2, each reading the filings independently (the readings archived under readings/)",
    "note": ("The five records with a placed line under 5% are the script's pattern placement of the roll-forward's "
             "first exchange amount as a share of R, shown here as the script printed it; they were not read twice. "
             "A pattern placement is not a reading, but its figure is under half the threshold in each case."),
}

#: the decisions that are the Claude analysis session's own, on top of the author's rule
SESSION_NOTE = {
    "1897_2016": (
        "decision of the Claude analysis session, 22 October 2026: the line is labelled 'Effect of FX and other "
        "movements', not an exchange line alone, and it is treated as exchange, because retranslating R at the "
        "filing's printed year-end rates (USD 1.47 to 1.24, p22) gives about 14.3m of the 13.8m line (both readers "
        "make the same calculation: 77.314 x (1.47/1.24 - 1))"),
    "5151_2016": (
        "the functional currency changed to US dollars on 1 January 2016 (p20, p25) and the 2016 report amends the "
        "t-1 diagonal (p44); both readers record this beside the verdict, and both point the same way as the "
        "exclusion"),
}


def load_reader(rid):
    with io.open(READINGS / ("%s.json" % rid), encoding="utf-8") as fh:
        return json.load(fh)


def _pick(e, *names):
    for n in names:
        if n in e:
            return e[n]
    return None


def year_pages(key, pages):
    """The year-t filing's pages (ints), and the other filing's, from a reader's `pages` (a dict keyed by filing, or a
    list for the record's own filing)."""
    if isinstance(pages, dict):
        own = [p for p in pages.get(key, []) if isinstance(p, int)]
        other = {k: [p for p in v if isinstance(p, int)] for k, v in pages.items() if k != key}
        return own, {k: v for k, v in other.items() if v}
    return [p for p in pages if isinstance(p, int)], {}


def reading(rid, key, e):
    """One reader's reading of a candidate, normalised across the two readers' field names."""
    own, other = year_pages(key, e["pages"])
    r_open = _pick(e, "opening_gross_claims_outstanding_R", "opening_R")
    line = _pick(e, "fx_line_gross", "fx_line")
    out = {
        "reader": rid,
        "pages": own,
        "pages_of_the_earlier_report": other,
        "read_by": e["read_by"],
        "report_currency": e["report_currency"],
        "functional_currency": e["functional_currency"],
        "opening_gross_claims_outstanding": {k: r_open[k] for k in ("value_m", "page", "quote")},
        "fx_line_gross": ({k: line.get(k) for k in ("value_m", "page", "quote")} if isinstance(line, dict)
                          else {"value_m": None, "page": None, "quote": line}),
        "fx_line_pct_of_opening": _pick(e, "fx_line_pct_of_R"),
        "table_retranslated": e["retranslated"],
        "cells_compared": _pick(e, "cell_comparison", "cells_compared"),
        "table_exchange_basis": e["table_exchange_basis"],
        "rate_move": e["rate_move"],
        "verdict": e["verdict"],
        "note": e["note"],
    }
    return out


def pct_of(line_m, opening_m):
    return None if line_m is None else round(100.0 * line_m / opening_m, 2)


def entry_for(key, reads):
    r1, r2 = reads
    open_m = r1["opening_gross_claims_outstanding"]["value_m"]
    line_m = r1["fx_line_gross"]["value_m"]
    for r in reads:
        if r["opening_gross_claims_outstanding"]["value_m"] != open_m or r["fx_line_gross"]["value_m"] != line_m:
            raise SystemExit("%s: the readers disagree on R or the exchange line" % key)
        if r["verdict"] != reads[0]["verdict"]:
            raise SystemExit("%s: the readers disagree on the verdict" % key)
    verdict = r1["verdict"]
    if (key in EXCLUDED) != (verdict == "exclude"):
        raise SystemExit("%s: the readers' verdict %r does not match the register's list" % (key, verdict))
    pct = pct_of(line_m, open_m)
    if (verdict == "exclude") != (pct is not None and abs(pct) >= THRESHOLD_PCT):
        raise SystemExit("%s: verdict %s against a line of %s%% of R" % (key, verdict, pct))
    pages = sorted({p for r in reads for p in r["pages"]})
    quote = " | ".join("reader %s, p%s: %s" % (r["reader"], r["opening_gross_claims_outstanding"]["page"],
                                                r["opening_gross_claims_outstanding"]["quote"]) for r in reads)
    quote += " || " + " | ".join(
        "reader %s, p%s: %s" % (r["reader"], r["fx_line_gross"]["page"], r["fx_line_gross"]["quote"]) for r in reads)
    e = {
        "report_currency": r1["report_currency"],
        "opening_gross_claims_outstanding_m": open_m,
        "fx_line_gross_m": line_m,
        "fx_line_pct_of_opening": pct,
        "pages": pages,
        "quote": quote,
        "readings": [r1, r2],
    }
    if verdict == "exclude":
        e["table_retranslated"] = False
        e["decision"] = (
            "the author's rule B (decision of 22 October 2026), applied to two independent readings of the filing "
            "(F1, F2): the development table is not retranslated across a sterling/dollar move of 5%% or more, and "
            "the gross claims-outstanding roll-forward prints an exchange line of %s%% of the opening gross claims "
            "outstanding (absolute value at least 5%%), so the record leaves the primary sample; the 672 "
            "sensitivity keeps it" % ("%.1f" % (100.0 * line_m / open_m)))
        if key in SESSION_NOTE:
            e["session_decision"] = SESSION_NOTE[key]
    else:
        e["reason"] = "no_fx_line_printed" if line_m is None else "fx_line_under_5pct"
        e["decision"] = (
            "read twice (F1, F2) and kept in the primary sample under the author's rule B (decision of 22 October "
            "2026): %s" % (
                "the gross claims-outstanding roll-forward prints no exchange line, so condition (b) fails"
                if line_m is None else
                "the gross exchange line is %.2f%% of the opening gross claims outstanding (absolute value under "
                "5%%), so condition (b) fails" % pct))
    return e


def build():
    data = {rid: load_reader(rid) for rid in READERS}
    out = {"_rule": RULE, "_population": POPULATION, "excluded": {}, "read_and_kept": {}}
    for bucket, keys in (("excluded", EXCLUDED), ("read_and_kept", KEPT)):
        for key in sorted(keys, key=lambda k: tuple(int(p) for p in k.split("_"))):
            reads = [reading(rid, key, data[rid][key]) for rid in READERS]
            out[bucket][key] = entry_for(key, reads)
    return out


def dumps(reg):
    return json.dumps(reg, indent=1, ensure_ascii=False) + "\n"


def main(argv):
    text = dumps(build())
    if "--write" in argv:
        with io.open(REGISTER, "w", encoding="utf-8", newline="") as fh:
            fh.write(text)
        print("wrote %s" % REGISTER.relative_to(HERE))
        return 0
    with io.open(REGISTER, encoding="utf-8", newline="") as fh:
        committed = fh.read()
    if committed != text:
        print("data/fx_untranslated_excluded.json differs from its rebuild: run with --write and read the diff")
        return 1
    print("data/fx_untranslated_excluded.json equals its rebuild")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
