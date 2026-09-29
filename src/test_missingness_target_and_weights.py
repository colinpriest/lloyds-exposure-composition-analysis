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


def test_dispositions_separate_structural_and_unresolved_cases():
    rows = _ledger()
    counts = {name: sum(row["category"] == name for row in rows) for name in {
        "structural_no_eligible_outcome", "eligibility_unresolved",
        "scientific_exclusion", "eligible_outcome_unavailable",
        "eligible_observed_composition_unavailable", "working_sample",
    }}
    assert len(rows) == 1065
    # round 62 (the records at extraction d9f2bdee; was 69, 58, 143, 12, 97, 686): 13 unresolved filings were read,
    # 1985/2024 became a first-year stub, and the run-off year 2468/2022 is a scientific exclusion
    assert counts == {
        "structural_no_eligible_outcome": 70,
        "eligibility_unresolved": 45,
        "scientific_exclusion": 145,
        "eligible_outcome_unavailable": 12,
        "eligible_observed_composition_unavailable": 98,
        "working_sample": 695,
    }
    unresolved = [row for row in rows if row["category"] == "eligibility_unresolved"]
    assert all(row["economic_eligibility"] == "unresolved" for row in unresolved)
    assert all(row["in_supported_target_population"] == "False" for row in unresolved)
    assert all(row["in_broader_potential_target"] == "True" for row in unresolved)


def test_source_audited_skips_carry_substantive_evidence():
    rows = _ledger()
    skipped = [row for row in rows if row["category"] == "structural_no_eligible_outcome"]
    assert len(skipped) == 70
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


def test_generated_sensitivity_discloses_caps_and_broader_target():
    result = _sensitivity()
    prop = result["propensity_model"]
    assert prop["primary_probability_floor"] == 0.15
    assert prop["primary_diagnostics"]["n_below_cap"] == 6
    assert prop["primary_diagnostics"]["kish_effective_sample_size"] > 500
    # round 62: the uncapped diagnostic's ESS is 135 on the records at extraction d9f2bdee (it was below 100); the
    # pin is the value the generated sentence prints, and capping must still leave the larger effective sample
    assert round(prop["uncapped_diagnostic_not_fitted"]["kish_effective_sample_size"]) == 135
    assert (prop["uncapped_diagnostic_not_fitted"]["kish_effective_sample_size"]
            < prop["primary_diagnostics"]["kish_effective_sample_size"])
    assert {"ipw_cap_0.10", "ipw_cap_0.15", "ipw_cap_0.20"} <= set(result["fits"])
    broad = result["eligibility_unresolved_stress"]
    assert broad["n_pseudo"] == 57
    assert broad["n_known_eligible_unavailable"] == 12
    assert broad["n_eligibility_unresolved"] == 45
    assert result["n_broader_potential_target_if_all_unresolved_eligible"] == 850


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
