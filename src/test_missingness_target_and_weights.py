"""Regression tests for the supported target, unresolved cases and bounded IPW."""
import csv
import io
import json
from pathlib import Path

import numpy as np
import pytest

import check_missingness_sensitivity as cms


ROOT = Path(__file__).resolve().parent.parent


def _ledger():
    with io.open(ROOT / "results" / "inferential_disposition_ledger.csv",
                 encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def _sensitivity():
    return json.load(io.open(
        ROOT / "results" / "check_missingness_sensitivity_results.json",
        encoding="utf-8",
    ))


@pytest.fixture(scope="module")
def sources():
    """What the records and the filing-page audit say, read without the loader: the unresolved filings (the records
    left unread and the audit's unresolved stubs), the audit's decisions, and the record files."""
    import missingness_check as MC
    return {"unresolved": MC.unresolved_filings_from_sources(), "audit": MC._structural_decisions(),
            "m01": MC.no_mature_cohort_records(),
            "records": sorted(p.name for p in (ROOT / "pdf_extraction").glob("syndicate_*.json"))}


def test_dispositions_separate_structural_and_unresolved_cases(sources):
    rows = _ledger()
    counts = {name: sum(row["category"] == name for row in rows) for name in {
        "structural_no_eligible_outcome", "eligibility_unresolved",
        "scientific_exclusion", "eligible_outcome_unavailable",
        "eligible_observed_composition_unavailable", "working_sample",
    }}
    assert [row["file"] for row in rows] == sources["records"]
    # generated from the records and the audit, not typed (FIX3 A4): the author's decision D2 (30 September 2026)
    # moves read records from the unresolved filings to the structural ones
    assert {row["file"] for row in rows if row["category"] == "eligibility_unresolved"} == sources["unresolved"]
    # the structural filings are the audit's ineligible stubs and the records the loader's rule M01 skips (the
    # decision of 1 October 2026), each with its entry in data/no_mature_cohort_records.json
    assert {row["file"] for row in rows if row["category"] == "structural_no_eligible_outcome"} == {
        name for name, decision in sources["audit"].items() if decision["economic_eligibility"] == "ineligible"
    } | set(sources["m01"])
    # the loader's decisions on the corpus, as measured. The author's decision D1 (30 September 2026) made six
    # negative-premium years whose filings state run-off scientific exclusions: four had been composition-unavailable
    # (145 -> 149, 98 -> 94) and two were net-basis exclusions already. The decision of 1 October 2026 (option A),
    # on the extraction's corpus-wide register as imported at 2ee4007e (the import before 57b4b14d), made 20
    # whole-year run-off years outside the RITC regime scientific exclusions: 16 from the working sample, 3
    # composition-unavailable and 1 net-basis (149 -> 168, 94 -> 91, 695 -> 679). The same day's extension of rule M01
    # to every route moved 11 records to the structural filings: 5 from the working sample, 5 scientific exclusions
    # (4 net or unstated basis, 1 take-on) and 1 composition-unavailable (168 -> 163, 91 -> 90, 679 -> 674).
    # Measured from the loader on the records imported at 57b4b14d (4 October 2026), against the earlier ledger: the
    # scope rule of D3-1 moves 72 composition-unavailable records to scientific exclusions (50 whose extracted mix names
    # no line of business, 22 life) and leaves 4 others, where another model reads a line, as composition-unavailable;
    # the import and the eight confirmed-figure entries of 4 October 2026 move 1400/2014 from the run-off exclusions to
    # the unresolved filings (-1), 1967/2014 and 2010/2014 from the working sample to the basis exclusions (+2),
    # 382/2020 back from the basis exclusions into the working sample (-1) and 4020/2019 from composition-unavailable
    # into it (163 + 72 - 1 + 2 - 1 = 235; 90 - 72 - 1 = 17)
    assert (counts["scientific_exclusion"], counts["eligible_outcome_unavailable"],
            counts["eligible_observed_composition_unavailable"], counts["working_sample"]) == (235, 12, 17, 674)
    unresolved = [row for row in rows if row["category"] == "eligibility_unresolved"]
    assert all(row["economic_eligibility"] == "unresolved" for row in unresolved)
    assert all(row["in_supported_target_population"] == "False" for row in unresolved)
    assert all(row["in_broader_potential_target"] == "True" for row in unresolved)


def test_source_audited_skips_carry_substantive_evidence(sources):
    rows = _ledger()
    skipped = [row for row in rows if row["category"] == "structural_no_eligible_outcome"]
    assert len(skipped) == (sum(d["economic_eligibility"] == "ineligible" for d in sources["audit"].values())
                            + len(sources["m01"]))
    assert all(row["economic_eligibility"] == "ineligible" for row in skipped)
    assert all("year" in row["classification_evidence"].lower()
               or "cohort" in row["classification_evidence"].lower()
               for row in skipped)


def test_weight_formula_and_overlap_diagnostics_are_exact():
    phat = np.array([0.01, 0.10, 0.50, 1.00])
    weights, diag = cms.propensity_weights(phat, 0.15)
    expected = 1.0 / np.maximum(phat, 0.15)
    expected /= expected.mean()
    assert np.allclose(weights, expected)
    assert diag["n_below_cap"] == 2
    assert abs(diag["kish_effective_sample_size"]
               - weights.sum() ** 2 / np.sum(weights ** 2)) < 1e-12


def test_generated_sensitivity_discloses_caps_and_broader_target(sources):
    result = _sensitivity()
    prop = result["propensity_model"]
    assert prop["primary_probability_floor"] == 0.15
    # the decision of 1 October 2026 (option A, on the extraction's register as imported at 2ee4007e, the import
    # before 57b4b14d: 801 -> 782) and the same day's extension of rule M01 (782 -> 776) took 25 records out of the
    # target: 6 -> 4 below the cap
    assert prop["primary_diagnostics"]["n_below_cap"] == 4
    assert prop["primary_diagnostics"]["kish_effective_sample_size"] > 500
    # round 62: the uncapped diagnostic's ESS was 135 on the records at extraction d9f2bdee (it was below 100). The
    # author's decision D1 (30 September 2026) took four composition-unavailable filings out of the target (805 ->
    # 801): the propensity's log R coefficient rose from 0.880 to 0.904 and the ESS fell to 110. The decisions of
    # 1 October (option A on the final register and the extension of rule M01, 801 -> 776) moved the coefficient to
    # 1.051 and the ESS to 39. The pin is the value the generated sentence prints, and capping must still leave the
    # larger effective sample
    assert round(prop["uncapped_diagnostic_not_fitted"]["kish_effective_sample_size"]) == 39
    assert (prop["uncapped_diagnostic_not_fitted"]["kish_effective_sample_size"]
            < prop["primary_diagnostics"]["kish_effective_sample_size"])
    assert {"ipw_cap_0.10", "ipw_cap_0.15", "ipw_cap_0.20"} <= set(result["fits"])
    # the stress's populations are the partition's, and its unresolved filings the records' (FIX3 A4: they were
    # typed as 57 = 45 + 12 and 850)
    rows = _ledger()
    unavailable = sum(row["category"] == "eligible_outcome_unavailable" for row in rows)
    target = sum(row["in_supported_target_population"] == "True" for row in rows)
    broad = result["eligibility_unresolved_stress"]
    assert broad["n_eligibility_unresolved"] == len(sources["unresolved"])
    assert broad["n_known_eligible_unavailable"] == unavailable
    assert broad["n_pseudo"] == len(sources["unresolved"]) + unavailable
    assert result["n_broader_potential_target_if_all_unresolved_eligible"] == target + len(sources["unresolved"])


def _dispositions(n_working, unresolved):
    return ([{"file": "syndicate_%d_2020.json" % i, "category": "working_sample"} for i in range(n_working)]
            + [{"file": name, "category": "eligibility_unresolved"} for name in unresolved])


def test_the_sensitivity_checks_its_populations_against_a_second_count(monkeypatch):
    """The sensitivity's populations were typed (695, 805, 12, 45) and retyped at every data change; they are now
    checked against a second count of the same filings: the model sample against the partition's working sample,
    the unresolved filings against the records left unread and the audit's unresolved stubs (FIX3 A4)."""
    unread = {"syndicate_1_2014.json", "syndicate_2_2015.json"}
    monkeypatch.setattr(cms, "unresolved_filings_from_sources", lambda: set(unread))
    rows = _dispositions(3, sorted(unread))
    unresolved = [r for r in rows if r["category"] == "eligibility_unresolved"]
    cms.check_populations(np.zeros(3), rows, unresolved)
    with pytest.raises(AssertionError, match="loads 4 records and the partition's working sample holds 3"):
        cms.check_populations(np.zeros(4), rows, unresolved)
    with pytest.raises(AssertionError, match="0 extra .* 1 missing"):
        cms.check_populations(np.zeros(3), rows, unresolved[:1])
    extra = unresolved + [{"file": "syndicate_3_2016.json", "category": "eligibility_unresolved"}]
    with pytest.raises(AssertionError, match="1 extra .* 0 missing"):
        cms.check_populations(np.zeros(3), rows, extra)


def test_the_unresolved_filings_are_read_from_the_records_and_the_audit(tmp_path, monkeypatch):
    import missingness_check as MC
    (tmp_path / "pdf_extraction").mkdir()
    for name, record in (("syndicate_1_2014.json", {"status": "no_deterministic_reading", "excluded": True}),
                         ("syndicate_2_2015.json", {"first_year_syndicate": True}),
                         ("syndicate_3_2016.json", {"models": {}})):
        (tmp_path / "pdf_extraction" / name).write_text(json.dumps(record), encoding="utf-8")
    monkeypatch.setattr(MC, "SD", tmp_path)
    monkeypatch.setattr(MC, "_structural_decisions", lambda: {
        "syndicate_2_2015.json": {"economic_eligibility": "unresolved"},
        "syndicate_4_2017.json": {"economic_eligibility": "ineligible"}})
    assert MC.unresolved_filings_from_sources() == {"syndicate_1_2014.json", "syndicate_2_2015.json"}


def test_mature_nil_cohort_with_positive_reserve_enters_the_model_sample():
    rows = _ledger()
    row = next(r for r in rows if r["file"] == "syndicate_1840_2022.json")
    assert row["category"] == "working_sample"
    assert row["economic_eligibility"] == "eligible"
    assert row["in_model_sample"] == "True"
    exposure = json.load(io.open(ROOT / "model" / "exposure_results.json", encoding="utf-8"))
    observation = next(o for o in exposure["observations"]
                       if o["syndicate"] == 1840 and o["year"] == 2022)
    assert observation["pyd_pct"] == 0.0
    assert observation["opening_reserves_gbp_m"] == pytest.approx(0.279)


def test_the_fit_summary_is_stored_unrounded():
    """Round 62's verification (N-V-A-2): ArviZ's default rounding stored the stress fit's nu_clean mean as 3.655,
    a tie at the 2 dp the documents print. The stored mean is now the draws' own mean, unrounded."""
    import arviz as az
    rng = np.random.default_rng(7)
    draws = {name: rng.normal(3.6553217, 0.37, size=(4, 250)) for name in cms.VARIABLES}
    idata = az.from_dict(posterior=draws, sample_stats={"diverging": np.zeros((4, 250), bool)})
    out = cms.summarise(idata)
    for name in cms.VARIABLES:
        assert out[name]["mean"] == pytest.approx(float(draws[name].mean()), abs=1e-12), name
        assert out[name]["hdi_2.5"] < out[name]["mean"] < out[name]["hdi_97.5"]
    assert out["_diag"]["divergences"] == 0


def _stored_means(result):
    fits = dict(result["fits"])
    for stress in ("eligible_outcome_stress", "eligibility_unresolved_stress"):
        for c, fit in result[stress]["by_c"].items():
            fits["%s x%s" % (stress, c)] = fit
    return {(tag, name): fit[name]["mean"] for tag, fit in fits.items() for name in cms.VARIABLES if name in fit}


def test_the_recorded_fits_are_stored_unrounded():
    """Every stored posterior mean carries more than 3 decimals: none is a rounded copy (a draws' mean that lands
    exactly on a 3-dp number has probability zero)."""
    means = _stored_means(_sensitivity())
    assert len(means) >= 7 * 12
    rounded = sorted(key for key, v in means.items() if abs(v * 1000 - round(v * 1000)) < 1e-9)
    assert not rounded, "rounded means stored: %s" % rounded[:5]
