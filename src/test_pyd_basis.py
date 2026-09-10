"""The development figure's basis is explicit, enforced and machine-readable.

Round 51 of the paper review found working-sample observations dividing a
net-of-reinsurance development figure by gross opening reserves (2999/2015 and
2999/2017 from a net claims triangle, 958/2014 from net year-of-account profit
contributions), while run_analysis.py marked reliability from field availability
alone. Every observation now carries `pyd_basis` and `pyd_basis_source`; only
`gross` enters the working sample.

Round 53 found the gross default reaching past evidence the record already held:
1206/2019, 780/2017 and 457/2016 carried net development into the gross sample
because nothing read what the models said about the figure they recorded. The rule
now consults those declarations (`pyd_basis_rule`), and all six donors are planted
below.

These tests plant the records, exercise each face of the rule on synthetic records,
and read the committed output.

Run:  python -m pytest src/test_pyd_basis.py -q
"""
import io
import json
import os

import pytest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(HERE, "src")
import sys  # noqa: E402
sys.path.insert(0, SRC)
import run_analysis as ra  # noqa: E402

PLANTED = ("2999_2015", "2999_2017", "958_2014")
#: the 7 September 2026 review's three, each audited against the filing itself
PLANTED_R53 = ("1206_2019", "780_2017", "457_2016")


@pytest.fixture(scope="module")
def register():
    return ra.load_pyd_basis_register()


def _block(key):
    d = json.load(io.open(os.path.join(HERE, "pdf_extraction", "syndicate_%s.json" % key),
                          encoding="utf-8"))
    models = d["models"]
    cands = [(mk, m.get("prior_year_movement_confidence", 0) or 0)
             for mk, m in models.items() if m.get("prior_year_development_pct") is not None]
    ck = cands[0][0] if len(cands) == 1 else max(cands, key=lambda x: x[1])[0]
    return models[ck]


@pytest.mark.parametrize("key", PLANTED)
def test_the_planted_records_are_net(register, key):
    basis, source, _ = ra.pyd_basis(_block(key), key, register)
    assert basis == "net", (key, basis, source)


def test_a_pipeline_override_carries_the_triangle_basis(register):
    gross = {"prior_year_development_gbp_m": 62.437, "_rag_triangle": {"type": "gross"},
             "data_quality_notes": "flagged as NET of reinsurance ... [RAG OVERRIDE: Model said "
                                   "PYD=-1.1, RAG triangle computed 62.437. Using RAG value.]"}
    assert ra.pyd_basis(gross, "x_2016", register) == ("gross", "triangle-override:gross", "")
    net = dict(gross, _rag_triangle={"type": "net"})
    assert ra.pyd_basis(net, "x_2016", register)[0] == "net"


def test_an_override_that_did_not_take_falls_through(register):
    cm = {"prior_year_development_gbp_m": -1.1, "_rag_triangle": {"type": "gross"},
          "_claims_triangle": {"type": "net"},
          "data_quality_notes": "[RAG OVERRIDE: Model said PYD=-1.1, RAG triangle computed "
                                "62.437. Using RAG value.]"}
    assert ra.pyd_basis(cm, "x_2016", register) == ("net", "net-triangle", "")


def test_a_net_claims_triangle_is_net_unless_the_register_says_otherwise(register):
    cm = {"prior_year_development_gbp_m": 8.277, "_claims_triangle": {"type": "net"},
          "data_quality_notes": ""}
    assert ra.pyd_basis(cm, "x_2016", register) == ("net", "net-triangle", "")
    assert ra.pyd_basis(cm, "1110_2016", register)[0] == "gross"


def test_a_plain_record_is_gross_stated(register):
    cm = {"prior_year_development_gbp_m": 5.0, "_claims_triangle": {"type": "gross"},
          "data_quality_notes": "Gross figure from the technical provisions note."}
    assert ra.pyd_basis(cm, "x_2016", register) == ("gross", "prompt-default-gross", "")


def test_the_register_quotes_its_evidence(register):
    for key, entry in register.items():
        assert entry["basis"] in ("gross", "net", "unknown"), key
        assert entry["source"] and len(entry["evidence"]) >= 20, key
        assert os.path.exists(os.path.join(HERE, "pdf_extraction", "syndicate_%s.json" % key)), key


def test_the_committed_output_carries_the_basis_and_admits_only_gross():
    d = json.load(io.open(os.path.join(HERE, "model", "exposure_results.json"), encoding="utf-8"))
    obs = d["observations"]
    assert all("pyd_basis" in o and "pyd_basis_source" in o for o in obs)
    working = [o for o in obs if o.get("s_raw_a") is not None and o.get("opening_reserves_gbp_m")
               and o.get("hhi") is not None]
    assert all(o["pyd_basis"] == "gross" for o in working)
    keys = {"%s_%s" % (o["syndicate"], o["year"]) for o in working}
    for key in PLANTED:
        assert key not in keys, key
    excluded = [o for o in obs if o["data_quality_tag"] in ("NET_BASIS", "UNKNOWN_BASIS")]
    assert excluded, "no basis exclusions recorded"
    assert all(o["s_raw_a"] is None for o in excluded)


# --- round 53: the record's own declaration ----------------------------------


def _record(key):
    return json.load(io.open(os.path.join(HERE, "pdf_extraction", "syndicate_%s.json" % key),
                             encoding="utf-8"))


@pytest.mark.parametrize("key", PLANTED_R53)
def test_the_audited_donors_do_not_reach_the_gross_sample(register, key):
    """1206/2019 and 780/2017 are declared net; 457/2016's basis is not established."""
    d = _record(key)
    basis, source, evidence = ra.pyd_basis(_block(key), key, register, d["models"])
    assert basis in ("net", "unknown"), (key, basis, source)
    assert source.startswith("declared-"), (key, source)
    assert evidence, key


def test_a_declaration_naming_a_different_amount_does_not_make_the_figure_net(register):
    """3000/2022 records 112.626 under a note about a net release of 25.4m: the note
    describes another number, so the basis is unknown rather than net."""
    cm = {"prior_year_development_gbp_m": 112.626,
          "data_quality_notes": "The prior year development figure is reported as a net "
                                "release of GBP 25.4m."}
    basis, source, _ = ra.pyd_basis(cm, "x_2016", register, {"m": cm})
    assert basis == "unknown", (basis, source)
    assert "inconsistent" in source


def test_a_contrasting_mention_of_a_net_figure_stays_gross(register):
    """The recorded value is the gross triangle one; the net figure is named to
    explain what was NOT used."""
    cm = {"prior_year_development_gbp_m": 20.057,
          "data_quality_notes": "The gross prior year development calculated from the claims "
                                "development triangle (+GBP 20.057m strengthening) differs from "
                                "the net prior year release of GBP 1.4m stated in the narrative."}
    assert ra.pyd_basis(cm, "x_2016", register, {"m": cm})[0] == "gross"


def test_the_arithmetic_net_idiom_is_not_a_reinsurance_basis(register):
    cm = {"prior_year_development_gbp_m": 48.491,
          "data_quality_notes": "The prior year development is a net effect of both adverse and "
                                "positive developments across different classes."}
    assert ra.pyd_basis(cm, "x_2016", register, {"m": cm})[0] == "gross"


def test_the_second_model_can_settle_the_basis(register):
    """457/2016's canonical block prioritises an explicit narrative figure; only the
    other block records that the filing does not label it."""
    models = {
        "a": {"prior_year_development_gbp_m": -40.3,
              "data_quality_notes": "The narrative figure has been prioritized due to its "
                                    "explicit nature."},
        "b": {"prior_year_development_gbp_m": -40.3,
              "data_quality_notes": "The report explicitly states 'GBP 40.3m of releases' but "
                                    "does not unambiguously label this amount as gross or net."},
    }
    basis, source, evidence = ra.pyd_basis(models["a"], "x_2016", register, models)
    assert basis == "unknown", (basis, source)
    assert "unstated" in source and "unambiguously" in evidence


def test_a_block_reporting_another_value_is_not_read(register):
    """A second model that recorded a different figure describes a different number."""
    models = {
        "a": {"prior_year_development_gbp_m": 30.0, "data_quality_notes": ""},
        "b": {"prior_year_development_gbp_m": -2.0,
              "data_quality_notes": "Prior year development figure is net of reinsurance."},
    }
    assert ra.pyd_basis(models["a"], "x_2016", register, models)[0] == "gross"


def test_the_default_still_applies_without_contrary_evidence(register):
    cm = {"prior_year_development_gbp_m": 5.0,
          "data_quality_notes": "Opening reserves taken from the balance sheet."}
    assert ra.pyd_basis(cm, "x_2016", register, {"m": cm}) == ("gross", "prompt-default-gross", "")


# --- the adversarial sentences from the round-53 code review ------------------------

def test_an_unstated_declaration_is_read_as_a_wording_not_the_audited_quote(register):
    """457/2016's quote is one wording of "the filing does not say gross or net";
    the rule must read the others the corpus uses."""
    for note in ("The filing does not clearly state whether the amount is gross or net.",
                 "The note does not explicitly label this figure as gross or net of reinsurance.",
                 "The report does not distinguish gross from net for this movement."):
        cm = {"prior_year_development_gbp_m": 5.0, "data_quality_notes": note}
        basis, source, _ = ra.pyd_basis(cm, "x_2016", register, {"m": cm})
        assert (basis, source.split(":")[0]) == ("unknown", "declared-unstated"), (note, basis, source)


def test_a_rejected_net_figure_is_still_not_a_net_declaration(register):
    """2488/2015 records the gross figure and says the net one was not used."""
    cm = {"prior_year_development_gbp_m": -57.087,
          "data_quality_notes": "Net PYD = -49.609 (release) per note 5 but was not used as "
                                "the primary PYD field because it is net of reinsurance."}
    assert ra.pyd_basis(cm, "x_2015", register, {"m": cm})[0] == "gross"


def test_the_rejection_veto_governs_the_net_figure_only(register):
    """A net declaration that mentions some other value not being used is net."""
    cm = {"prior_year_development_gbp_m": -3.0,
          "data_quality_notes": "The prior year development is reported as a net figure "
                                "because a gross value was not used in the underlying ledger."}
    basis, source, _ = ra.pyd_basis(cm, "x_2016", register, {"m": cm})
    assert basis == "net", (basis, source)


def test_a_same_sentence_gross_provenance_settles_an_unlabelled_narrative(register):
    """2012/2016: the narrative figure is unlabelled, the recorded figure is the gross
    triangle calculation named in the same sentence."""
    cm = {"prior_year_development_gbp_m": 9.38,
          "data_quality_notes": "The Managing Agent narrative quotes an adverse prior year "
                                "development of GBP 10.3m but does not explicitly state whether "
                                "that is gross or net; the prior_year_development_gbp_m is "
                                "calculated from the gross claims development triangle and "
                                "yields GBP 9.38m."}
    assert ra.pyd_basis(cm, "x_2016", register, {"m": cm})[0] == "gross"


def test_an_unlabelled_figure_that_is_not_the_recorded_one_is_inconsistent(register):
    """609/2016: the note describes -40.5m as unlabelled; the record carries -47.547."""
    cm = {"prior_year_development_gbp_m": -47.547,
          "data_quality_notes": "Prior year development figure (-GBP 40.5m) taken from the "
                                "narrative, which is explicit but does not specify reinsurance "
                                "gross/net."}
    basis, source, _ = ra.pyd_basis(cm, "x_2016", register, {"m": cm})
    assert (basis, source.split(":")[0]) == ("unknown", "declared-inconsistent"), (basis, source)


# --- the recall pass (round 53, second review): wordings the corpus scan found ------


def _one(register, value, notes, key="x_2016"):
    cm = {"prior_year_development_gbp_m": value, "data_quality_notes": notes}
    basis, source, _ = ra.pyd_basis(cm, key, register, {"m": cm})
    return basis, source.split(":")[0]


def test_a_qualified_subject_is_still_the_subject(register):
    """5151/2020: 'Prior year development figure of GBP 5.2m is assumed to be net'."""
    assert _one(register, -5.2, "Prior year development figure of GBP 5.2m is assumed to be "
                "net of reinsurance as the report does not explicitly state 'gross' for this "
                "figure.") == ("net", "declared-net")


def test_the_net_figure_used_as_a_fallback_is_net(register):
    """2007/2014 and 3000/2014: the model says which figure it recorded."""
    assert _one(register, -26.8, "No gross figure was found. Therefore "
                "prior_year_development_gbp_m uses the NET figure as a fallback and is "
                "flagged accordingly.")[0] == "net"
    assert _one(register, -33.6, "Therefore the prior_year_development_gbp_m value is the "
                "narrated NET release (negative=release).")[0] == "net"


def test_a_hedged_net_reading_of_the_recorded_figure_is_net(register):
    """3623/2020 'appears to be a net figure', 457/2018 'implying it is a net figure'."""
    assert _one(register, -8.8, "Prior year development amount ($8.8m) is taken from narrative "
                "text and appears to be a net figure.")[0] == "net"
    assert _one(register, -27.0, "Prior year development figure is stated as a component of "
                "the 'net technical result', implying it is a net figure after "
                "reinsurance.")[0] == "net"


def test_an_anaphoric_declaration_needs_the_recorded_amount(register):
    """557/2020: the quoted 0.4m is the recorded figure, so 'this is stated as a net
    figure' is about it; with another amount it is about another number."""
    notes = ("The narrative mentions a 'favourable reserve release on prior years, which "
             "contributed GBP 0.4 million to the closing year result', but this is stated "
             "as a net figure.")
    assert _one(register, -0.4, notes)[0] == "net"
    assert _one(register, -12.0, notes)[0] == "gross"


def test_a_net_table_source_is_net(register):
    """1910/2016: the development table is presented on a net basis."""
    assert _one(register, -8.28, "The claims development table included in the notes is "
                "presented on a NET basis (cumulative net claims) in the document, so a "
                "reliable aggregated gross prior-year development number could not be "
                "produced.")[0] == "net"


def test_a_subject_inside_a_net_noun_phrase_is_the_narrative_figure(register):
    """382/2022: 'a small net favourable prior year development (GBP 0.2m) - this is NET
    of reinsurance' describes the narrative figure; the record carries the triangle."""
    assert _one(register, 34.169, "The syndicate narrative reports a small net favourable "
                "prior year development (GBP 0.2m) - this is NET of reinsurance and "
                "reconciles with the triangle.")[0] == "gross"


def test_the_amount_beside_gross_settles_a_contrast_sentence(register):
    """780/2016: net $23.3m in the narrative, gross $15.6m in the table; 15.6 recorded."""
    notes = ("The narrative text describes a net prior year reserve release of $23.3m, "
             "while the detailed claims reserve movement table on page 13 shows a gross "
             "prior year release of $15.6m.")
    assert _one(register, -15.6, notes)[0] == "gross"
    assert _one(register, -23.3, notes)[0] == "net"


def test_a_verified_gross_declaration_outranks_another_blocks_inconsistency(register):
    """780/2016 across blocks: the second block says it used a net $17.1m it did not
    record; the first block's amount-verified gross reading settles the record."""
    a = {"prior_year_development_gbp_m": -15.6,
         "data_quality_notes": "The narrative text describes a net prior year reserve release "
                               "of $23.3m, while the table shows a gross prior year release of "
                               "$15.6m."}
    b = {"prior_year_development_gbp_m": -15.6,
         "data_quality_notes": "No clear gross figure was identifiable; therefore a net "
                               "prior-year release of $17.1m has been used as a fallback."}
    basis, source, _ = ra.pyd_basis(a, "x_2016", register, {"a": a, "b": b})
    assert basis == "gross", (basis, source)


def test_a_class_breakdown_sentence_is_not_about_the_recorded_figure(register):
    """2008/2016: 'the LOB movements for prior year development are presented as net'
    is about lob_movements."""
    assert _one(register, -12.896, "The LOB movements for prior year development are "
                "presented as net of reinsurance in the source document.")[0] == "gross"


def test_net_of_something_other_than_reinsurance_is_arithmetic(register):
    """1084/2014: 'assumed to be net of this effect' (an RITC), not net of reinsurance."""
    assert _one(register, -77.4, "This transaction impacts the comparability of opening and "
                "closing reserve figures but the stated prior year development figure is "
                "assumed to be net of this effect.")[0] == "gross"


def test_gross_versus_net_is_an_unstated_wording(register):
    """2623/2018 and 609/2014: 'does not unambiguously label the amount as gross vs net'."""
    assert _one(register, -110.0, "Prior year development figure of $110.0m is taken from the "
                "Managing Agent narrative but the statement does not unambiguously label the "
                "amount as gross vs net of reinsurance.") == ("unknown", "declared-unstated")
    assert _one(register, -41.2, "The note explicitly states an improvement but does not "
                "explicitly label the figure as 'gross' vs 'net' in the narrative."
                )[0] == "unknown"


def test_a_figure_that_may_be_net_is_unstated(register):
    """3623/2017: 'The narrative figure may be net of reinsurance in some disclosures'."""
    assert _one(register, 2.721, "The narrative figure may be net of reinsurance in some "
                "disclosures; no explicit gross-only prior year movement breakdown was found, "
                "so the narrative figure is used.") == ("unknown", "declared-unstated")


def test_a_reported_net_profit_is_not_a_use_statement(register):
    """1971/2022: 'A net profit of $5.0m is reported for 2021 and prior years' names a
    P&L item; the recorded figure is the triangle's."""
    assert _one(register, 25.471, "A net profit of $5.0m is reported for 2021 and prior years "
                "of account (P&L result), implying a release.")[0] == "gross"


def test_the_audit_names_the_step_that_assigned_the_basis():
    """Reviewer 2E1: a keep-out declaration that ends gross must show which loader step
    settled it (the record's own triangle route, a pipeline override read from the
    notes, or the register), in the Markdown as in the JSON."""
    md = io.open(os.path.join(HERE, "results", "pyd_basis_declarations.md"), encoding="utf-8").read()
    js = json.load(io.open(os.path.join(HERE, "results", "pyd_basis_declarations.json"), encoding="utf-8"))
    assert "| Basis source |" in md
    assert "keep_out_ending_gross_by_source" in js
    for src in js["keep_out_ending_gross_by_source"]:
        # triangle-route is the structured route recorded on the record itself;
        # triangle-override is the older reading of the notes sentence. Both name a
        # loader step, and they are counted separately because they are different
        # evidence (round 55, review B2-01).
        assert src in ("triangle-route", "triangle-override", "register"), src


# --- review round 3 (reviewer 3C) ---------------------------------------------------


def test_a_verified_gross_provenance_outranks_another_blocks_unstated_reading(register):
    """One block traces the recorded figure to the gross triangle and quotes it; the
    other says the filing does not label it. The verified provenance settles it."""
    a = {"prior_year_development_gbp_m": 9.38,
         "data_quality_notes": "The prior_year_development_gbp_m is calculated from the gross "
                               "claims development triangle and yields GBP 9.38m."}
    b = {"prior_year_development_gbp_m": 9.38,
         "data_quality_notes": "The note does not unambiguously label this amount as gross or net."}
    basis, source, _ = ra.pyd_basis(a, "x_2016", register, {"a": a, "b": b})
    assert basis == "gross", (basis, source)
    # without the quoted figure the gross reading is not verified and the doubt stands
    a2 = dict(a, data_quality_notes="The prior_year_development_gbp_m is calculated from the "
                                    "gross claims development triangle.")
    assert ra.pyd_basis(a2, "x_2016", register, {"a": a2, "b": b})[0] == "unknown"


def test_a_hedge_separated_from_whether_is_still_unstated(register):
    assert _one(register, 5.0, "It is unclear from the filing whether prior year movements are "
                "quoted gross or net of outwards reinsurance.") == ("unknown", "declared-unstated")


def test_an_anaphoric_quantified_subject_is_read_through_the_amount(register):
    notes = ("Note 8 gives the claims development on a net basis; the gross equivalent was not "
             "published, so the figure carried forward here, GBP 4.4m, is net.")
    assert _one(register, -4.4, notes)[0] == "net"
    assert _one(register, -12.0, notes)[0] == "gross"


def test_represents_is_a_declaration_verb(register):
    assert _one(register, 9.0, "The prior year development figure represents the net "
                "movement after reinsurance recoveries.")[0] == "net"
