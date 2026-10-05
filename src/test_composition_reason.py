"""Every record left without a composition records why (the review of 2 October 2026, M-4; test gap 3).

build_weight_vector gives no weights for a record with no mix, a mix that does not reconcile with a premium total
another reader gave, or a mix whose whole weight lands in Aggregate, which it called "likely a misparse". The
review found most of the 90 such records were correct readings the taxonomy maps wholly to Aggregate: books whose
mix names only a contract form ("Reinsurance") or only distribution channels, and life books. The loader now
records the reason beside weight_source (which stays "none"), and the disposition ledger makes the books with no
line of business and the life books scope exclusions (D3-1, 4 October 2026); every other record stays
composition-unavailable with its reason.

The stage-3 review (4 October 2026, finding 4) found the scope rule looked at the adopted block's mix alone: 6107/2024
and 6118/2016 were scope exclusions although another model read a real split by line of business, and 1910/2022's
other rows were negative direct lines. The rule is general: a record is a scope exclusion only if no other model in
the record reads a line of business, and is "readers_disagree" otherwise.

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


LINES = mix(("Property", 5.0), ("Marine", 3.0))
NEGATIVE_LINES = mix(("Fire and other damage to property", -2.8), ("Motor", -1.1))


@pytest.mark.parametrize("gpm,scope", [
    (mix(("Reinsurance", 47.6)), "contract_form_only"),
    (mix(("MGA Insurance", 1.0), ("Reinsurance", 3.0)), "channel_only"),
    (mix(("Long-term insurance business", 50.0)), "life"),
])
def test_a_scope_mix_is_a_disagreement_when_another_model_reads_a_line_of_business(gpm, scope):
    """The rule is on the record's other readers, whatever the adopted mix's labels: contract form, channel and
    life alike. A negative amount still reads a line (1910/2022's other rows)."""
    assert ra.composition_unavailable_reason(gpm) == scope
    assert ra.composition_unavailable_reason(gpm, []) == scope
    assert ra.composition_unavailable_reason(gpm, [None, []]) == scope
    for other in (LINES, NEGATIVE_LINES, mix(("Reinsurance", 1.0), ("Marine", 2.0))):
        assert ra.composition_unavailable_reason(gpm, [other]) == "readers_disagree"
        assert ra.composition_unavailable_reason(gpm, [mix(("Reinsurance", 9.0)), other]) == "readers_disagree"


@pytest.mark.parametrize("other", [
    mix(("Reinsurance", 47.6)), mix(("MGA Insurance", 1.0)), mix(("Life", 3.0)),
    mix(("Total", 10.0), ("Marine", None)), mix(("Total gross premiums", 10.0)), [],
])
def test_another_model_that_also_names_no_line_leaves_the_scope_exclusion(other):
    assert ra.composition_unavailable_reason(mix(("Reinsurance", 47.6)), [other]) == "contract_form_only"


@pytest.mark.parametrize("gpm,reason", [
    (mix(("Medical Malpractice", 14.8)), "line_not_in_taxonomy"),
    (mix(("UK", 33.0), ("US", 101.9), ("Other", 102.7)), "misparse_geographic"),
    (mix(("Reinsurance", 4.0), ("Other", 2.0)), "other_labels"),
    ([], "no_mix"),
])
def test_only_a_would_be_scope_exclusion_becomes_a_disagreement(gpm, reason):
    """The other readers change a scope outcome and nothing else: the other reasons are their own."""
    assert ra.composition_unavailable_reason(gpm, [LINES]) == reason


def test_a_line_read_by_another_model_is_a_line():
    assert ra.mix_reads_a_line_of_business(LINES) and ra.mix_reads_a_line_of_business(NEGATIVE_LINES)
    assert not ra.mix_reads_a_line_of_business(mix(("Reinsurance", 1.0), ("Life", 2.0), ("MGA Insurance", 3.0)))
    assert not ra.mix_reads_a_line_of_business(mix(("Marine", None)))
    assert not ra.mix_reads_a_line_of_business(None)


def test_the_reasons_and_the_ledgers_words_and_details_agree():
    assert set(MC.COMPOSITION_REASON_WORDS) == set(ra.COMPOSITION_REASONS)
    assert "readers_disagree" in ra.COMPOSITION_REASONS
    assert set(MC.COMPOSITION_SCOPE_DETAIL) == set(ra.COMPOSITION_REASONS_OUT_OF_SCOPE) == {
        "contract_form_only", "channel_only", "life"}
    assert len(set(ra.COMPOSITION_REASONS)) == len(ra.COMPOSITION_REASONS)


@pytest.mark.parametrize("reason,category,detail", [
    ("contract_form_only", "scientific_exclusion", "mix_names_no_line_of_business"),
    ("channel_only", "scientific_exclusion", "mix_names_no_line_of_business"),
    ("life", "scientific_exclusion", "life_book"),
    ("readers_disagree", "eligible_observed_composition_unavailable", "missing_lob_composition"),
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


def test_the_stage_3_reviews_disagreements_are_not_scope_exclusions(loaded):
    """The stage-3 review's records: another model read a real split by line of business (6107/2024, 6118/2016) or the
    other rows were negative direct lines (1910/2022); a fourth, 3002/2024 (life), moved with the general rule."""
    records, _ = loaded
    by_key = {(r["syndicate"], r["year"]): r["composition_unavailable_reason"] for r in records}
    for key in ((6107, 2024), (6118, 2016), (1910, 2022), (3002, 2024)):
        assert by_key[key] == "readers_disagree", key


def _other_readers_mixes(record):
    import glob
    import json
    path = os.path.join(str(ra.DATA_DIR), "syndicate_%s_%s.json" % (record["syndicate"], record["year"]))
    with open(path, encoding="utf-8") as fh:
        models = json.load(fh)["models"]
    return [(m or {}).get("gross_premium_mix") for m in models.values()]


def test_on_the_committed_records_no_scope_exclusion_has_a_reader_that_reads_a_line(loaded):
    """The rule on fixed inputs, read from the record files: every scope exclusion has no model reading a line of
    business, and every disagreement has at least one reading one besides the adopted block's own (so that rule and
    records cannot drift apart). The four records that moved when the rule became general are named."""
    records, _ = loaded
    scope = [r for r in records if r["composition_unavailable_reason"] in ra.COMPOSITION_REASONS_OUT_OF_SCOPE]
    assert len(scope) > 50
    for r in scope:
        assert not any(ra.mix_reads_a_line_of_business(m) for m in _other_readers_mixes(r)), (
            r["syndicate"], r["year"])
    disagree = {(r["syndicate"], r["year"]) for r in records
                if r["composition_unavailable_reason"] == "readers_disagree"}
    assert disagree == {(1910, 2022), (3002, 2024), (6107, 2024), (6118, 2016)}
    for r in records:
        if (r["syndicate"], r["year"]) in disagree:
            assert any(ra.mix_reads_a_line_of_business(m) for m in _other_readers_mixes(r))


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
