r"""The basis rule reads what the models said about the recorded figure (R210).

The error-rate study's second reading of 3623/2020 found a figure that its own model called net
("assumed to be net of reinsurance") carried on the gross default. Tracing the basis decision on the
working sample found more wordings the rule did not read, and a false gross: gross pattern 1's qualifier gap
spanned a negation, so "does not explicitly state if it is gross or net" read as a gross
declaration and outranked the unstated one.

Every case below is a sentence a model wrote on a working-sample record. The contrasts, written on
records in the same sample, name a net figure only to explain that the gross one was recorded; they
must stay gross, as must an arithmetic "net" ("a net release, but it's a result of mixed
movements across different lines of business"). An assumption of gross made because the filing gives no basis ("as no explicit 'net'
qualifier is used", "as per instructions") is an unstated basis. One made from what the table is
("as note refers to technical reserves") is not.
"""
import os
import sys

import pytest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(HERE, "src"))
import run_analysis as ra  # noqa: E402

REGISTER = {}


def verdict(value, notes, route=None):
    cm = {"prior_year_development_gbp_m": value, "data_quality_notes": notes}
    if route is not None:
        cm["_pyd_route"] = dict(route)
    basis, source, _ = ra.pyd_basis(cm, "x_2016", REGISTER, {"m": cm})
    return basis, source.split(":")[0]


NET = [
    ("3623/2020", -8.8, "Prior year development figure is from narrative text and assumed to be net of reinsurance "
                        "as no gross figure was explicitly stated or calculable from available tables."),
    ("3623/2020", -8.8, "The $8.8m appears in narrative and is likely a net (after reinsurance) release; no explicit "
                        "gross prior-year movement was found."),
    ("3623/2014", -4.6, "No explicit GROSS 'movement in prior years provision for claims outstanding' was found; the "
                        "Managing Agent's narrative sentence reporting a $4.6m release was used as a net prior-year "
                        "movement (NET of reinsurance) as a last-resort fallback."),
    ("1919/2014", 12.5, "The GBP 12.5m is the net syndicate deterioration."),
    ("3010/2017", -3.3, "Prior year development is derived from the breakdown of the calendar year result by year of "
                        "account, which is a net profit figure for prior years."),
]

UNSTATED = [
    ("3623/2014", -4.6, "The prior year development figure of $4.6m is taken from narrative text and does not "
                        "explicitly state if it is gross or net of reinsurance."),
    ("623/2015", -40.3, "Prior year development figure of $40.3m is presented as a total release by division, but its "
                        "context with 'Releases as a percentage of net earned premium' on page 4 suggests it might be "
                        "a net figure, although not explicitly stated as such."),
    ("382/2014", -0.172, "Prior-year development amount derived from Note 4 ('Material over provisions...') which "
                         "presents per-line figures; the note's wording references 'net payments and provisions' "
                         "leading to ambiguity whether the table figures are gross (insurance liabilities) or net of "
                         "reinsurance."),
    ("2623/2014", -149.6, "The statement 'release prior year reserves' is assumed to be gross, as no explicit 'net' "
                          "qualifier is used, and it aligns with the LOB breakdown."),
    ("2121/2014", -1.922, "The overall figure is used as the primary prior year development, assuming it is gross as "
                          "per instructions, despite the slight discrepancy in the breakdown."),
]

GROSS = [
    ("1084/2024", -25.8, "Per instructions the gross movement from Note 19 was used as the authoritative gross "
                         "prior-year movement; the narrative figure may represent a different aggregation or a net "
                         "amount."),
    ("1084/2014", -77.4, "Prior year movement taken from Note 'Movement in prior year's provision for claims "
                         "outstanding' which explicitly states a GBP 77.4m release (assumed gross as note refers to "
                         "technical reserves)."),
    ("1221/2024", 97.477, "The Managing Agent narrative references a prior year \"release\" on a net basis (GBP 19.7m) "
                          "which differs from the gross movement; this JSON reports the GROSS movement as required."),
    ("2001/2020", -11.5, "LOB-level prior-year reserve movements are not provided on a gross basis; the GBP 20.0m and "
                         "GBP 45.0m amounts quoted in the report are net of reinsurance and have been flagged as such "
                         "by lower confidence."),
    ("3000/2024", 136.6, "The Managing Agent's narrative also reports a net prior year release of GBP 70.2m (after "
                         "reinsurance); these two figures differ because one is gross and the other is net."),
    ("6125/2017", 3.1, "The `exact_reserve_text` refers to a net prior year development figure, while "
                       "`prior_year_development_gbp_m` is the gross figure from the technical provisions note."),
    # arithmetic, not a basis: the net of mixed movements across lines of business (382/2014)
    ("382/2014", -0.172, "The prior year development is a net release, but it's a result of mixed movements across "
                         "different lines of business."),
]


@pytest.mark.parametrize("record,value,notes", NET)
def test_a_net_declaration_about_the_recorded_figure_is_read(record, value, notes):
    assert verdict(value, notes) == ("net", "declared-net"), (record, verdict(value, notes))


@pytest.mark.parametrize("record,value,notes", UNSTATED)
def test_an_unstated_basis_is_read(record, value, notes):
    assert verdict(value, notes)[0] == "unknown", (record, verdict(value, notes))


@pytest.mark.parametrize("record,value,notes", GROSS)
def test_a_contrast_stays_gross(record, value, notes):
    assert verdict(value, notes) == ("gross", "prompt-default-gross"), (record, verdict(value, notes))


def test_an_amount_subject_that_is_another_figure_is_not_the_recorded_one():
    assert verdict(-3.0, "The GBP 12.5m is the net syndicate deterioration.")[0] == "gross"


def test_a_block_whose_figure_the_pipeline_overrode_describes_another_number():
    """A model's notes describe the figure the model read. Where the pipeline replaced that figure
    (the route says it overrode the model value), a sentence that quotes no amount is about the
    model's number, not the recorded one."""
    notes = ("Prior year development is derived from the breakdown of the calendar year result by year of "
             "account, which is a net profit figure for prior years.")
    route = {"source": "rag_provisions_text", "value": 52.141, "model_value": -3.3, "note": "overrode the model value"}
    assert verdict(52.141, notes, route) == ("gross", "prompt-default-gross")
    # on a block whose figure is the model's own, the same sentence is a declaration
    assert verdict(-3.3, notes) == ("net", "declared-net")
    # and a sentence quoting the recorded amount is about the recorded figure whoever wrote it
    quoted = "The recorded 52.141m is the net movement in the provisions note."
    assert verdict(52.141, quoted, route)[0] == "net"
