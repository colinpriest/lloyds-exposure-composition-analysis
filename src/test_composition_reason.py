"""Every record left without a composition records why (the review of 2 October 2026, M-4; test gap 3).

build_weight_vector gives no weights for a record with no mix, a mix that does not reconcile with a premium total
another reader gave, or a mix whose whole weight lands in Aggregate, which it called "likely a misparse". The
review found most of the 90 such records were correct readings the taxonomy maps wholly to Aggregate: books whose
mix names only a contract form ("Reinsurance") or only distribution channels, and life books. The loader now
records the reason beside weight_source (which stays "none"), and the disposition ledger makes the books with no
line of business and the life books scope exclusions (D3-1, 4 October 2026); every other record stays
composition-unavailable with its reason.

Run:  python -m pytest src/test_composition_reason.py -q
"""
import os
import sys

import pytest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(HERE, "src"))
import missingness_check as MC  # noqa: E402
import run_analysis as ra  # noqa: E402


def mix(*pairs):
    return [{"line_of_business": label, "amount_gbp_m": amount} for label, amount in pairs]


# the review's examples (REPORT.md M-4 and scratch/R5/agg_kinds_out.txt), with the reason each must record
CASES = [
    ("6104/2018", mix(("Reinsurance", 47.6)), "contract_form_only"),
    ("6117/2020", mix(("Reinsurance acceptances", 81.9)), "contract_form_only"),
    ("2357/2019", mix(("MGA Insurance", 158.976), ("Reinsurance", 314.68)), "channel_only"),
    ("3002/2019", mix(("Long-term insurance business", 50.033)), "life"),
    ("life with inwards", mix(("Life", 3.0), ("Reinsurance acceptances", 1.0)), "life"),
    ("life by channel", mix(("Binder business written", 1.0), ("Group business written", 2.0),
                            ("Individual business written", 3.0), ("Scheme", 4.0)), "life"),
    ("1892/2021", mix(("Medical Malpractice", 14.822)), "line_not_in_taxonomy"),
    ("medical malpractice with inwards", mix(("Direct insurance: Medical Malpractice", 5.0), ("Reinsurance:", 1.0)),
     "line_not_in_taxonomy"),
    ("3002/2021", mix(("EU countries", 1.02), ("US", 0.96), ("Latin America", 10.55), ("Other Worldwide", 2.313)),
     "misparse_geographic"),
    ("1910/2021", mix(("UK", 33.0), ("Canada", 7.9), ("US", 101.9), ("Rest of Europe", 10.4), ("Other", 102.7)),
     "misparse_geographic"),
    ("6123/2018", mix(("Eastern Seaboard", 5.074), ("Florida", 9.157), ("Gulf Coast", 4.009), ("Earthquake", 7.681)),
     "misparse_geographic"),
    ("1910/2020", mix(("Fire and other damage to property", -2.8), ("Other", 10.1),
                      ("Reinsurance acceptances", 248.6)), "other_labels"),
    ("no mix", [], "no_mix"),
    ("only a total and a negative class", mix(("Total", 10.0), ("Marine", -1.0)), "no_mix"),
    ("727/2019", mix(("Accident and health", 7.912), ("Fire and other damage to property", 21.455),
                     ("Reinsurance inwards", 17.427)), "unreconciled"),
]


@pytest.mark.parametrize("name,gpm,reason", CASES, ids=[c[0] for c in CASES])
def test_each_mix_records_the_reason_its_labels_give(name, gpm, reason):
    assert ra.composition_unavailable_reason(gpm) == reason


def test_the_weight_vector_is_unchanged_for_a_mix_with_no_line_of_business():
    """weight_source stays "none" and build_weight_vector keeps its two return values: the reason is a separate
    field, so the dozen places that test weight_source and the tests that unpack the pair are untouched."""
    weights, source = ra.build_weight_vector(mix(("Reinsurance", 47.6)), 47.6)
    assert source == "none" and weights.sum() == 0


def test_the_reasons_and_the_ledgers_words_and_details_agree():
    assert set(MC.COMPOSITION_REASON_WORDS) == set(ra.COMPOSITION_REASONS)
    assert set(MC.COMPOSITION_SCOPE_DETAIL) == set(ra.COMPOSITION_REASONS_OUT_OF_SCOPE) == {
        "contract_form_only", "channel_only", "life"}
    assert len(set(ra.COMPOSITION_REASONS)) == len(ra.COMPOSITION_REASONS)


@pytest.mark.parametrize("reason,category,detail", [
    ("contract_form_only", "scientific_exclusion", "mix_names_no_line_of_business"),
    ("channel_only", "scientific_exclusion", "mix_names_no_line_of_business"),
    ("life", "scientific_exclusion", "life_book"),
    ("line_not_in_taxonomy", "eligible_observed_composition_unavailable", "missing_lob_composition"),
    ("misparse_geographic", "eligible_observed_composition_unavailable", "missing_lob_composition"),
    ("other_labels", "eligible_observed_composition_unavailable", "missing_lob_composition"),
    ("no_mix", "eligible_observed_composition_unavailable", "missing_lob_composition"),
    ("unreconciled", "eligible_observed_composition_unavailable", "missing_lob_composition"),
])
def test_the_ledger_applies_the_scope_rule_by_reason(reason, category, detail):
    got = MC.composition_disposition({"hhi": None, "composition_unavailable_reason": reason}, "syndicate_1_2020.json")
    assert (got[0], got[1]) == (category, detail)
    assert got[5].endswith(MC.COMPOSITION_REASON_WORDS[reason])


def test_a_record_without_a_reason_stops_the_ledger():
    with pytest.raises(AssertionError, match="no recorded reason"):
        MC.composition_disposition({"hhi": None}, "syndicate_1_2020.json")


@pytest.fixture(scope="module")
def loaded():
    records, counters, _log, _files = ra.load_and_classify()
    return records, counters


def test_every_record_without_weights_records_its_reason_and_no_other_does(loaded):
    """Every exit that leaves a record without a composition (no mix, unreconciled, all-Aggregate) is recorded, on
    the committed records."""
    records, counters = loaded
    without = [r for r in records if r["weight_source"] == "none"]
    assert len(without) > 50
    assert all(r["composition_unavailable_reason"] in ra.COMPOSITION_REASONS for r in without), [
        (r["syndicate"], r["year"]) for r in without if r["composition_unavailable_reason"] not in ra.COMPOSITION_REASONS]
    assert all(r["composition_unavailable_reason"] is None for r in records if r["weight_source"] != "none")
    assert sum(counters["composition_unavailable_reasons"].values()) == len(without)


def test_the_reviews_books_are_classified_as_it_found_them(loaded):
    """The review's verified records (REPORT.md M-4): 6104/2018 and 6117/2020 name only reinsurance, 3002/2019 is
    life business, 2357/2019 names only channels."""
    records, _ = loaded
    by_key = {(r["syndicate"], r["year"]): r["composition_unavailable_reason"] for r in records}
    assert by_key[(6104, 2018)] == "contract_form_only"
    assert by_key[(6117, 2020)] == "contract_form_only"
    assert by_key[(3002, 2019)] == "life"
    assert by_key[(2357, 2019)] == "channel_only"


def test_a_scope_exclusion_is_not_counted_at_the_unusable_severity_step():
    """The loader's flow removes a record without weights at its own step, not the unusable-severity one; the
    ledger's reconciliation of that step leaves out every composition detail, the scope exclusions' included."""
    rows = [{"file": "a", "detail": "life_book"}, {"file": "b", "detail": "mix_names_no_line_of_business"},
            {"file": "c", "detail": "missing_lob_composition"}, {"file": "d", "detail": "gross_development_unavailable"}]
    ledger = [{"file": f, "disposition": "CORPUS:INCOMPLETE"} for f in "abcd"]
    flow = {"to_working_sample": {"net_or_unstated_basis": 0, "unusable_severity": 1}}
    out = MC.basis_exclusions_reconciliation(rows, ledger, flow)
    assert out["flow_unusable_severity_step"] == 1
    assert out["unusable_severity_components"] == {"gross_development_unavailable": 1}
