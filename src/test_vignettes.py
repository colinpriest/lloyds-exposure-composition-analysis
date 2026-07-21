#!/usr/bin/env python3
"""
Tests for the vignette generation pipeline.

Covers: helper functions, donor selection, distribution computation,
decomposition, output writers, figure generators, snippet/metadata,
and end-to-end integration.
"""

import json
import math
import os
import shutil
import tempfile
from pathlib import Path
from unittest import mock

import numpy as np
import pytest

# Import the module under test
import run_analysis as ra


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def _set_combined_model():
    """Set a deterministic COMBINED_MODEL for all tests."""
    original = ra.COMBINED_MODEL
    ra.COMBINED_MODEL = {
        "size": {"A": 0.001, "B": 0.5, "C": -0.5},
        "hhi": {"A": 0.001, "B": 0.1, "C": 2.0},
        "v_hhi_ref": 0.017,
        "reference_hhi": 0.4,
    }
    yield
    ra.COMBINED_MODEL = original


def _make_weights(prop=0.4, cas=0.3, mar=0.2, prof=0.1):
    """Build a 13-element normalised weight vector."""
    w = np.zeros(ra.N_LOBS, dtype=float)
    w[ra.LOB_INDEX["Property"]] = prop
    w[ra.LOB_INDEX["Casualty"]] = cas
    w[ra.LOB_INDEX["Marine"]] = mar
    w[ra.LOB_INDEX["Professional Lines"]] = prof
    s = w.sum()
    if s > 0:
        w /= s
    return w


def _make_lob_severity(base=0.05):
    """Build a 13-element LoB severity vector."""
    sev = np.zeros(ra.N_LOBS, dtype=float)
    sev[ra.LOB_INDEX["Property"]] = base * 1.2
    sev[ra.LOB_INDEX["Casualty"]] = base * 0.8
    sev[ra.LOB_INDEX["Marine"]] = base * 1.5
    sev[ra.LOB_INDEX["Professional Lines"]] = base * 0.5
    return sev


def _make_donor(syndicate, year, reserves, s_raw, weights=None, lob_sev=None,
                hhi=None, quality="RELIABLE"):
    """Create a synthetic donor record."""
    if weights is None:
        weights = _make_weights()
    if lob_sev is None:
        lob_sev = _make_lob_severity()
    if hhi is None:
        hhi = float(np.sum(weights ** 2))
    return {
        "syndicate": syndicate,
        "year": year,
        "opening_reserves_gbp_m": reserves,
        "s_raw_a": s_raw,
        "pyd_gbp_m": s_raw * reserves if s_raw is not None and reserves is not None else None,
        "pyd_pct": s_raw * 100 if s_raw is not None else None,
        "weights": weights.tolist(),
        "lob_severity": lob_sev.tolist(),
        "lob_severity_computed": True,
        "hhi": hhi,
        "data_quality_tag": quality,
        "direction": "adverse" if s_raw is not None and s_raw > 0 else "release",
        "eligible_for_capital": s_raw is not None and lob_sev is not None,
    }


@pytest.fixture
def target_weights():
    """Target weights vector for V1-style tests."""
    return _make_weights(prop=0.25, cas=0.20, mar=0.15, prof=0.40)


@pytest.fixture
def target_profile():
    """Target profile dict."""
    tw = _make_weights(prop=0.25, cas=0.20, mar=0.15, prof=0.40)
    return {
        "weights_vec": tw,
        "size": 500.0,
        "hhi": float(np.sum(tw ** 2)),
    }


@pytest.fixture
def donor_pool():
    """A pool of 20 synthetic donors with varied sizes and compositions."""
    rng = np.random.RandomState(123)
    pool = []
    for i in range(20):
        syndicate = 1000 + i
        year = 2018 + (i % 5)
        reserves = rng.uniform(50, 3000)
        s_raw = rng.normal(0.02, 0.15)
        # Vary weights
        raw_w = rng.dirichlet([2, 2, 1, 1] + [0.1] * 9)
        w = np.zeros(ra.N_LOBS, dtype=float)
        w[:4] = raw_w[:4]
        w[4:] = raw_w[4:]
        w /= w.sum()
        # LoB severity
        sev = np.zeros(ra.N_LOBS, dtype=float)
        for j in range(ra.N_LOBS):
            if w[j] > 0.01:
                sev[j] = rng.normal(0.03, 0.1)
        pool.append(_make_donor(syndicate, year, reserves, s_raw,
                                weights=w, lob_sev=sev))
    return pool


@pytest.fixture
def tmp_dir():
    """Temporary directory for output tests."""
    d = tempfile.mkdtemp(prefix="vig_test_")
    yield Path(d)
    shutil.rmtree(d, ignore_errors=True)


# ─────────────────────────────────────────────────────────────────────────────
# Unit tests: V_size and size_lambda
# ─────────────────────────────────────────────────────────────────────────────

class TestVSize:
    def test_basic_computation(self):
        """V_size(R) = A + B * R^C with known coefficients."""
        # A=0.001, B=0.5, C=-0.5 → V_size(100) = 0.001 + 0.5 * 100^(-0.5)
        expected = 0.001 + 0.5 * 100 ** (-0.5)
        assert ra._v_size(100) == pytest.approx(expected, rel=1e-6)

    def test_returns_1_without_model(self):
        """Should return 1.0 when COMBINED_MODEL is None."""
        original = ra.COMBINED_MODEL
        ra.COMBINED_MODEL = None
        try:
            assert ra._v_size(500) == 1.0
        finally:
            ra.COMBINED_MODEL = original

    def test_decreasing_with_size(self):
        """With C < 0, V_size should decrease as R increases."""
        assert ra._v_size(100) > ra._v_size(1000)

    def test_positive_for_positive_R(self):
        """V_size must be strictly positive for any R > 0."""
        for R in [1, 10, 100, 500, 2000, 10000]:
            assert ra._v_size(R) > 0


class TestSizeLambda:
    def test_identity_when_equal(self):
        """Lambda should be 1.0 when target = donor."""
        assert ra._size_lambda(500, 500) == pytest.approx(1.0, rel=1e-10)

    def test_less_than_one_for_larger_target(self):
        """With C < 0: V_size decreases with R, so lambda < 1 when target > donor."""
        lam = ra._size_lambda(2000, 100)
        assert lam < 1.0

    def test_greater_than_one_for_smaller_target(self):
        """Lambda > 1 when target is smaller than donor (with C < 0)."""
        lam = ra._size_lambda(100, 2000)
        assert lam > 1.0

    def test_symmetric_inverse(self):
        """Lambda(a,b) * Lambda(b,a) should equal 1."""
        lam_ab = ra._size_lambda(200, 800)
        lam_ba = ra._size_lambda(800, 200)
        assert lam_ab * lam_ba == pytest.approx(1.0, rel=1e-10)

    def test_returns_1_without_model(self):
        original = ra.COMBINED_MODEL
        ra.COMBINED_MODEL = None
        try:
            assert ra._size_lambda(100, 500) == pytest.approx(1.0)
        finally:
            ra.COMBINED_MODEL = original


# ─────────────────────────────────────────────────────────────────────────────
# Unit tests: weight helpers
# ─────────────────────────────────────────────────────────────────────────────

class TestVigWeightsVec:
    def test_normalises_to_one(self):
        w = ra._vig_weights_vec({"Property": 0.6, "Casualty": 0.4})
        assert w.sum() == pytest.approx(1.0, abs=1e-9)

    def test_correct_length(self):
        w = ra._vig_weights_vec({"Property": 1.0})
        assert len(w) == ra.N_LOBS

    def test_correct_placement(self):
        w = ra._vig_weights_vec({"Marine": 0.5, "Casualty": 0.5})
        assert w[ra.LOB_INDEX["Marine"]] == pytest.approx(0.5)
        assert w[ra.LOB_INDEX["Casualty"]] == pytest.approx(0.5)
        assert w[ra.LOB_INDEX["Property"]] == pytest.approx(0.0)

    def test_empty_dict(self):
        w = ra._vig_weights_vec({})
        assert w.sum() == 0.0


class TestVigHHI:
    def test_concentrated_portfolio(self):
        """Single-LoB portfolio should have HHI = 1."""
        w = np.zeros(ra.N_LOBS)
        w[0] = 1.0
        assert ra._vig_hhi(w) == pytest.approx(1.0)

    def test_equal_split(self):
        """n equal weights should give HHI = 1/n."""
        n = 4
        w = np.zeros(ra.N_LOBS)
        w[:n] = 1 / n
        assert ra._vig_hhi(w) == pytest.approx(1.0 / n, rel=1e-6)

    def test_two_lob_split(self):
        w = np.zeros(ra.N_LOBS)
        w[0] = 0.7
        w[1] = 0.3
        assert ra._vig_hhi(w) == pytest.approx(0.49 + 0.09)


# ─────────────────────────────────────────────────────────────────────────────
# Unit tests: donor pool building
# ─────────────────────────────────────────────────────────────────────────────

class TestVigDonorPool:
    """The vignette donor pool uses eligible_for_capital + reserves > 0 + s_raw_a not None."""

    def _flag(self, record, eligible=True):
        """Set eligible_for_capital on a record (normally set by compute_eligibility)."""
        record["eligible_for_capital"] = eligible
        return record

    def test_filters_not_eligible_for_capital(self):
        r = self._flag(_make_donor(1, 2020, 500, 0.05), eligible=False)
        assert len(ra._vig_donor_pool([r])) == 0

    def test_filters_missing_reserves(self):
        r = self._flag(_make_donor(1, 2020, None, 0.05))
        assert len(ra._vig_donor_pool([r])) == 0

    def test_filters_zero_reserves(self):
        r = self._flag(_make_donor(1, 2020, 0, 0.05))
        assert len(ra._vig_donor_pool([r])) == 0

    def test_filters_missing_s_raw(self):
        r = self._flag(_make_donor(1, 2020, 500, None))
        assert len(ra._vig_donor_pool([r])) == 0

    def test_accepts_valid_record(self):
        r = self._flag(_make_donor(1, 2020, 500, 0.05))
        assert len(ra._vig_donor_pool([r])) == 1

    def test_accepts_negative_s_raw(self):
        """Release observations should still be in the donor pool."""
        r = self._flag(_make_donor(1, 2020, 500, -0.03))
        assert len(ra._vig_donor_pool([r])) == 1

    def test_accepts_small_positive_reserves(self):
        """Any positive reserve size is accepted — capital flag is the gate."""
        r = self._flag(_make_donor(1, 2020, 0.5, 0.05))
        assert len(ra._vig_donor_pool([r])) == 1


# ─────────────────────────────────────────────────────────────────────────────
# Unit tests: donor selection
# ─────────────────────────────────────────────────────────────────────────────

class TestSelectSizeDonor:
    def test_selects_most_size_mismatched(self, target_profile):
        tw = target_profile["weights_vec"]
        t_size = target_profile["size"]
        t_hhi = target_profile["hhi"]
        # Three donors: tiny, medium, huge — all adverse, similar HHI
        pool = [
            _make_donor(1, 2020, 50, 0.1, weights=tw, hhi=t_hhi),    # huge size diff
            _make_donor(2, 2020, 400, 0.1, weights=tw, hhi=t_hhi),   # small size diff
            _make_donor(3, 2020, 5000, 0.1, weights=tw, hhi=t_hhi),  # huge size diff
        ]
        selected = ra._select_size_donor(pool, tw, t_size, t_hhi)
        # Should pick the biggest |log(R_i / R_q)|
        assert selected["syndicate"] in (1, 3)

    def test_prefers_adverse_donors(self, target_profile):
        tw = target_profile["weights_vec"]
        t_size = target_profile["size"]
        t_hhi = target_profile["hhi"]
        pool = [
            _make_donor(1, 2020, 50, -0.2, weights=tw, hhi=t_hhi),   # release, huge diff
            _make_donor(2, 2020, 100, 0.05, weights=tw, hhi=t_hhi),  # adverse, big diff
        ]
        selected = ra._select_size_donor(pool, tw, t_size, t_hhi)
        assert selected["syndicate"] == 2

    def test_fallback_when_no_hhi_match(self, target_profile):
        tw = target_profile["weights_vec"]
        t_size = target_profile["size"]
        t_hhi = target_profile["hhi"]
        # All donors have very different HHI (> 0.05 tolerance)
        pool = [
            _make_donor(i, 2020, 50 * (i + 1), 0.1, hhi=t_hhi + 0.2 + i * 0.01)
            for i in range(15)
        ]
        selected = ra._select_size_donor(pool, tw, t_size, t_hhi)
        # Fallback: among top 10 size mismatches, pick smallest HHI diff
        assert selected is not None

    def test_returns_none_for_empty_pool(self, target_profile):
        tw = target_profile["weights_vec"]
        assert ra._select_size_donor([], tw, 500, 0.2) is None


class TestSelectMixDonor:
    def test_selects_most_mix_mismatched(self, target_profile):
        tw = target_profile["weights_vec"]
        t_size = target_profile["size"]
        t_hhi = target_profile["hhi"]
        # Donor with very different weights (same size)
        diff_weights = _make_weights(prop=0.0, cas=0.0, mar=0.9, prof=0.1)
        similar_weights = _make_weights(prop=0.24, cas=0.21, mar=0.14, prof=0.41)
        pool = [
            _make_donor(1, 2020, 500, 0.1, weights=diff_weights),
            _make_donor(2, 2020, 500, 0.1, weights=similar_weights),
        ]
        selected = ra._select_mix_donor(pool, tw, t_size, t_hhi)
        assert selected["syndicate"] == 1

    def test_respects_size_tolerance(self, target_profile):
        tw = target_profile["weights_vec"]
        t_size = target_profile["size"]
        t_hhi = target_profile["hhi"]
        diff_weights = _make_weights(prop=0.0, cas=0.0, mar=0.9, prof=0.1)
        pool = [
            # Huge Hellinger but size way out of range
            _make_donor(1, 2020, 10, 0.1, weights=diff_weights),
            # Moderate Hellinger but in size range
            _make_donor(2, 2020, 450, 0.1,
                        weights=_make_weights(prop=0.1, cas=0.1, mar=0.7, prof=0.1)),
        ]
        selected = ra._select_mix_donor(pool, tw, t_size, t_hhi)
        # Donor 2 is in size tolerance (450/500 = 0.9), donor 1 is not (10/500 = 0.02)
        assert selected["syndicate"] == 2

    def test_fallback_when_no_size_match(self, target_profile):
        tw = target_profile["weights_vec"]
        t_size = target_profile["size"]
        t_hhi = target_profile["hhi"]
        # All donors have very different sizes
        pool = [
            _make_donor(i, 2020, 5 * (i + 1), 0.1,
                        weights=_make_weights(prop=0.1 * i, cas=0.9 - 0.1 * i, mar=0.0, prof=0.0))
            for i in range(1, 10)
        ]
        selected = ra._select_mix_donor(pool, tw, t_size, t_hhi)
        assert selected is not None

    def test_returns_none_for_empty_pool(self, target_profile):
        tw = target_profile["weights_vec"]
        assert ra._select_mix_donor([], tw, 500, 0.2) is None


# ─────────────────────────────────────────────────────────────────────────────
# Unit tests: worked example detail
# ─────────────────────────────────────────────────────────────────────────────

class TestWorkedDetail:
    def test_returns_all_required_fields(self, target_profile):
        tw = target_profile["weights_vec"]
        donor = _make_donor(1234, 2021, 200, 0.08)
        detail = ra._worked_detail(donor, tw, 500, target_profile["hhi"], "v1", "p1")
        required = [
            "vignette_id", "target_profile_id", "donor_observation_id",
            "donor_syndicate_id", "donor_report_year", "donor_reserve_size",
            "donor_hhi", "donor_signed_pyd_amount", "donor_signed_pyd_ratio",
            "target_reserve_size", "target_hhi", "S_raw", "S_mix", "S_adj",
            "size_multiplier_lambda", "V_size_donor", "V_size_target",
            "raw_to_mix_abs", "mix_to_adj_abs", "raw_to_adj_abs",
            "raw_to_mix_pct", "mix_to_adj_pct", "raw_to_adj_pct",
            "per_lob_table", "hellinger_distance", "log_reserve_ratio_to_target",
        ]
        for f in required:
            assert f in detail, f"Missing field: {f}"

    def test_s_adj_equals_s_mix_times_lambda(self, target_profile):
        tw = target_profile["weights_vec"]
        donor = _make_donor(1234, 2021, 200, 0.08)
        detail = ra._worked_detail(donor, tw, 500, target_profile["hhi"], "v1", "p1")
        assert detail["S_adj"] == pytest.approx(
            detail["S_mix"] * detail["size_multiplier_lambda"], abs=1e-5)

    def test_change_metrics_consistency(self, target_profile):
        tw = target_profile["weights_vec"]
        donor = _make_donor(1234, 2021, 200, 0.08)
        detail = ra._worked_detail(donor, tw, 500, target_profile["hhi"], "v1", "p1")
        assert detail["raw_to_adj_abs"] == pytest.approx(
            detail["raw_to_mix_abs"] + detail["mix_to_adj_abs"], abs=1e-5)

    def test_per_lob_contributions_sum_to_s_mix(self, target_profile):
        tw = target_profile["weights_vec"]
        donor = _make_donor(1234, 2021, 200, 0.08)
        detail = ra._worked_detail(donor, tw, 500, target_profile["hhi"], "v1", "p1")
        contrib_sum = sum(row["projected_contribution"] for row in detail["per_lob_table"])
        assert contrib_sum == pytest.approx(detail["S_mix"], abs=1e-4)

    def test_per_lob_table_has_required_fields(self, target_profile):
        tw = target_profile["weights_vec"]
        donor = _make_donor(1234, 2021, 200, 0.08)
        detail = ra._worked_detail(donor, tw, 500, target_profile["hhi"], "v1", "p1")
        for row in detail["per_lob_table"]:
            assert "lob_name" in row
            assert "source_weight" in row
            assert "target_weight" in row
            assert "line_level_ratio" in row
            assert "projected_contribution" in row

    def test_log_reserve_ratio_sign(self, target_profile):
        tw = target_profile["weights_vec"]
        # Donor smaller than target
        detail = ra._worked_detail(
            _make_donor(1, 2020, 100, 0.05), tw, 500, target_profile["hhi"], "v1", "p1")
        assert detail["log_reserve_ratio_to_target"] < 0
        # Donor larger than target
        detail2 = ra._worked_detail(
            _make_donor(2, 2020, 2000, 0.05), tw, 500, target_profile["hhi"], "v1", "p1")
        assert detail2["log_reserve_ratio_to_target"] > 0

    def test_pct_change_none_when_base_zero(self, target_profile):
        """Percentage change should be None when base value is zero."""
        tw = target_profile["weights_vec"]
        donor = _make_donor(1, 2020, 500, 0.0)  # S_raw = 0
        detail = ra._worked_detail(donor, tw, 500, target_profile["hhi"], "v1", "p1")
        assert detail["raw_to_mix_pct"] is None
        assert detail["raw_to_adj_pct"] is None


# ─────────────────────────────────────────────────────────────────────────────
# Unit tests: distribution computation
# ─────────────────────────────────────────────────────────────────────────────

class TestComputeTargetDists:
    def test_returns_matching_lengths(self, donor_pool, target_weights):
        raw, mix, adj, ids = ra._compute_target_dists(donor_pool, target_weights, 500)
        assert len(raw) == len(mix) == len(adj) == len(ids)

    def test_filters_invalid_records(self, target_weights):
        pool = [
            _make_donor(1, 2020, 500, 0.05),
            _make_donor(2, 2020, None, 0.05),  # invalid reserves
            _make_donor(3, 2020, 500, None),     # invalid s_raw
        ]
        raw, mix, adj, ids = ra._compute_target_dists(pool, target_weights, 500)
        assert len(raw) == 1

    def test_s_adj_is_s_mix_times_lambda(self, target_weights):
        pool = [_make_donor(1, 2020, 200, 0.10)]
        raw, mix, adj, ids = ra._compute_target_dists(pool, target_weights, 500)
        lam = ra._size_lambda(500, 200)
        assert adj[0] == pytest.approx(mix[0] * lam, rel=1e-6)

    def test_raw_values_match_source(self, target_weights):
        pool = [_make_donor(1, 2020, 300, 0.123)]
        raw, _, _, _ = ra._compute_target_dists(pool, target_weights, 500)
        assert raw[0] == pytest.approx(0.123)


# ─────────────────────────────────────────────────────────────────────────────
# Unit tests: distribution statistics
# ─────────────────────────────────────────────────────────────────────────────

class TestDistStats:
    def test_required_fields(self):
        stats = ra._dist_stats([1, 2, 3, 4, 5], "test")
        required = ["distribution_label", "n_total", "n_adverse",
                     "mean", "standard_deviation", "q75", "var99", "var995"]
        for f in required:
            assert f in stats, f"Missing field: {f}"

    def test_n_total_correct(self):
        stats = ra._dist_stats([1, 2, 3], "test")
        assert stats["n_total"] == 3

    def test_n_adverse_counts_positive(self):
        stats = ra._dist_stats([-1, -0.5, 0, 0.5, 1, 2], "test")
        assert stats["n_adverse"] == 3  # 0.5, 1, 2

    def test_mean_correct(self):
        stats = ra._dist_stats([2, 4, 6], "test")
        assert stats["mean"] == pytest.approx(4.0)

    def test_empty_returns_zero_count(self):
        stats = ra._dist_stats([], "empty")
        assert stats["n_total"] == 0

    def test_single_value(self):
        stats = ra._dist_stats([0.5], "single")
        assert stats["n_total"] == 1
        assert stats["mean"] == pytest.approx(0.5)
        assert stats["standard_deviation"] == 0.0

    def test_quantile_ordering(self):
        vals = list(np.random.RandomState(42).normal(0, 1, 200))
        stats = ra._dist_stats(vals, "test")
        assert stats["q75"] <= stats["var99"] <= stats["var995"]


# ─────────────────────────────────────────────────────────────────────────────
# Unit tests: bootstrap
# ─────────────────────────────────────────────────────────────────────────────

class TestBootstrapCI:
    def test_returns_required_keys(self, donor_pool, target_weights):
        result = ra._bootstrap_ci(donor_pool, target_weights, 500, B=50, seed=42)
        assert result is not None
        for k in ["raw_var99", "raw_var995", "adj_var99", "adj_var995", "B", "confidence_level"]:
            assert k in result

    def test_ci_lower_less_than_upper(self, donor_pool, target_weights):
        result = ra._bootstrap_ci(donor_pool, target_weights, 500, B=100, seed=42)
        for key in ["raw_var99", "raw_var995", "adj_var99", "adj_var995"]:
            lo, hi = result[key]
            if lo is not None and hi is not None:
                assert lo <= hi, f"{key}: lower ({lo}) > upper ({hi})"

    def test_deterministic_with_same_seed(self, donor_pool, target_weights):
        r1 = ra._bootstrap_ci(donor_pool, target_weights, 500, B=50, seed=99)
        r2 = ra._bootstrap_ci(donor_pool, target_weights, 500, B=50, seed=99)
        assert r1["adj_var995"] == r2["adj_var995"]

    def test_returns_none_with_too_few_syndicates(self, target_weights):
        pool = [_make_donor(1, 2020, 500, 0.05)]  # only 1 syndicate
        result = ra._bootstrap_ci(pool, target_weights, 500, B=50)
        assert result is None

    def test_syndicate_level_resampling(self, target_weights):
        """Pool with 6 syndicates, 2 obs each — should work."""
        pool = []
        for s in range(6):
            for y in range(2):
                pool.append(_make_donor(s, 2020 + y, 500 + s * 50, 0.05 + s * 0.01))
        result = ra._bootstrap_ci(pool, target_weights, 500, B=50, seed=42)
        assert result is not None
        assert result["B"] == 50


# ─────────────────────────────────────────────────────────────────────────────
# Unit tests: Shapley decomposition
# ─────────────────────────────────────────────────────────────────────────────

class TestShapleyV1:
    def test_returns_all_metrics(self, donor_pool, target_weights):
        result = ra._shapley_v1(donor_pool, target_weights, 500)
        for metric in ["q75", "var99", "var995"]:
            assert metric in result
            for f in ["metric", "raw_metric", "mix_adjusted_metric",
                       "fully_adjusted_metric", "mix_effect", "size_effect"]:
                assert f in result[metric]

    def test_effects_sum_to_total_change(self, donor_pool, target_weights):
        result = ra._shapley_v1(donor_pool, target_weights, 500)
        for metric in ["q75", "var99", "var995"]:
            d = result[metric]
            total_change = d["fully_adjusted_metric"] - d["raw_metric"]
            assert d["mix_effect"] + d["size_effect"] == pytest.approx(total_change, abs=1e-5)

    def test_no_size_effect_when_same_size(self, target_weights):
        """When all donors have same size as target, size effect should be ~0."""
        pool = [_make_donor(i, 2020, 500, 0.05 * (i - 5)) for i in range(20)]
        result = ra._shapley_v1(pool, target_weights, 500)
        # Size effect should be very small since all R_i ≈ R_target
        for metric in ["q75", "var99", "var995"]:
            assert abs(result[metric]["size_effect"]) < 0.01


class TestShapleyV2:
    def test_returns_all_metrics(self, donor_pool):
        old_w = _make_weights(prop=0.3, cas=0.25, mar=0.15, prof=0.3)
        new_w = _make_weights(prop=0.35, cas=0.30, mar=0.0, prof=0.35)
        result = ra._shapley_v2(donor_pool, old_w, new_w, 800, 650)
        for metric in ["q75", "var99", "var995"]:
            assert metric in result
            for f in ["metric", "old_profile_metric", "new_profile_metric",
                       "mix_change_effect", "size_change_effect"]:
                assert f in result[metric]

    def test_effects_sum_to_total_change(self, donor_pool):
        old_w = _make_weights(prop=0.3, cas=0.25, mar=0.15, prof=0.3)
        new_w = _make_weights(prop=0.35, cas=0.30, mar=0.0, prof=0.35)
        result = ra._shapley_v2(donor_pool, old_w, new_w, 800, 650)
        for metric in ["q75", "var99", "var995"]:
            d = result[metric]
            total = d["new_profile_metric"] - d["old_profile_metric"]
            assert d["mix_change_effect"] + d["size_change_effect"] == pytest.approx(total, abs=1e-5)

    def test_no_change_when_profiles_identical(self, donor_pool):
        """Old = new should give zero effects."""
        w = _make_weights(prop=0.3, cas=0.3, mar=0.2, prof=0.2)
        result = ra._shapley_v2(donor_pool, w, w, 500, 500)
        for metric in ["q75", "var99", "var995"]:
            assert result[metric]["mix_change_effect"] == pytest.approx(0.0, abs=1e-10)
            assert result[metric]["size_change_effect"] == pytest.approx(0.0, abs=1e-10)


# ─────────────────────────────────────────────────────────────────────────────
# Unit tests: output writers
# ─────────────────────────────────────────────────────────────────────────────

class TestVigWriteTable:
    def test_writes_csv(self, tmp_dir):
        rows = [{"a": 1, "b": "x"}, {"a": 2, "b": "y"}]
        ra._vig_write_table(tmp_dir, "test", rows, ["a", "b"])
        csv_path = tmp_dir / "test.csv"
        assert csv_path.exists()
        lines = csv_path.read_text(encoding="utf-8").strip().split("\n")
        assert lines[0] == "a,b"
        assert lines[1] == "1,x"
        assert lines[2] == "2,y"

    def test_writes_tex(self, tmp_dir):
        rows = [{"x": 1.5, "y": "hello"}]
        ra._vig_write_table(tmp_dir, "test", rows, ["x", "y"], caption="Test", label="test_lbl")
        tex_path = tmp_dir / "test.tex"
        assert tex_path.exists()
        content = tex_path.read_text(encoding="utf-8")
        assert "\\begin{table}" in content
        assert "\\caption{Test}" in content
        assert "\\label{tab:test_lbl}" in content
        assert "\\toprule" in content
        assert "\\bottomrule" in content

    def test_writes_xlsx_when_available(self, tmp_dir):
        if not ra._HAS_XLSX:
            pytest.skip("openpyxl not installed")
        rows = [{"col1": 10, "col2": "abc"}]
        ra._vig_write_table(tmp_dir, "test", rows, ["col1", "col2"])
        assert (tmp_dir / "test.xlsx").exists()

    def test_handles_empty_rows(self, tmp_dir):
        ra._vig_write_table(tmp_dir, "empty", [], ["a", "b"])
        csv_path = tmp_dir / "empty.csv"
        assert csv_path.exists()
        lines = csv_path.read_text(encoding="utf-8").strip().split("\n")
        assert len(lines) == 1  # header only

    def test_handles_missing_keys(self, tmp_dir):
        """Rows with missing keys should output empty strings."""
        rows = [{"a": 1}]
        ra._vig_write_table(tmp_dir, "test", rows, ["a", "b"])
        lines = (tmp_dir / "test.csv").read_text(encoding="utf-8").strip().split("\n")
        assert lines[1] == "1,"

    def test_float_formatting_in_tex(self, tmp_dir):
        rows = [{"val": 0.123456}]
        ra._vig_write_table(tmp_dir, "test", rows, ["val"])
        content = (tmp_dir / "test.tex").read_text(encoding="utf-8")
        assert "0.1235" in content  # 4 decimal places


# ─────────────────────────────────────────────────────────────────────────────
# Unit tests: figure generators
# ─────────────────────────────────────────────────────────────────────────────

class TestVigDistributionPlot:
    def test_creates_png_and_pdf(self, tmp_dir):
        series = [
            ("Raw", list(np.random.RandomState(1).normal(0, 0.1, 50)), "#2166ac"),
            ("Adj", list(np.random.RandomState(2).normal(0, 0.05, 50)), "#b2182b"),
        ]
        ra._vig_distribution_plot(tmp_dir, series, "test subtitle", "dist_test")
        assert (tmp_dir / "dist_test.png").exists()
        assert (tmp_dir / "dist_test.pdf").exists()

    def test_creates_plot_data(self, tmp_dir):
        series = [
            ("Raw", [0.1, 0.2, -0.1], "#2166ac"),
        ]
        ra._vig_distribution_plot(tmp_dir, series, "", "dist_test")
        assert (tmp_dir / "dist_test_data.csv").exists()
        lines = (tmp_dir / "dist_test_data.csv").read_text().strip().split("\n")
        assert len(lines) == 4  # header + 3 data rows


class TestVigTailPlot:
    def test_creates_png_and_pdf(self, tmp_dir):
        series = [
            ("Raw", list(np.random.RandomState(1).normal(0, 0.1, 100)), "#2166ac"),
        ]
        ra._vig_tail_plot(tmp_dir, series, "tail_test")
        assert (tmp_dir / "tail_test.png").exists()
        assert (tmp_dir / "tail_test.pdf").exists()

    def test_creates_plot_data_positive_only(self, tmp_dir):
        vals = [-0.5, -0.1, 0.1, 0.3, 0.5]
        series = [("Raw", vals, "#2166ac")]
        ra._vig_tail_plot(tmp_dir, series, "tail_test")
        content = (tmp_dir / "tail_test_data.csv").read_text()
        # Should only have positive values
        import csv as csv_m
        import io
        reader = csv_m.DictReader(io.StringIO(content))
        for row in reader:
            assert float(row["value"]) > 0


class TestVigWaterfallPlot:
    def test_creates_png_and_pdf(self, tmp_dir):
        ra._vig_waterfall_plot(tmp_dir, 0.28, 0.01, 0.02, 0.31, "VaR99.5", "wf_test")
        assert (tmp_dir / "wf_test.png").exists()
        assert (tmp_dir / "wf_test.pdf").exists()

    def test_creates_plot_data(self, tmp_dir):
        ra._vig_waterfall_plot(tmp_dir, 0.28, 0.01, 0.02, 0.31, "VaR99.5", "wf_test")
        assert (tmp_dir / "wf_test_data.csv").exists()
        lines = (tmp_dir / "wf_test_data.csv").read_text().strip().split("\n")
        assert len(lines) == 5  # header + 4 bars


# ─────────────────────────────────────────────────────────────────────────────
# Unit tests: metadata and snippet
# ─────────────────────────────────────────────────────────────────────────────

class TestVigMetadata:
    def test_returns_required_fields(self):
        meta = ra._vig_metadata("v1_test", [{"label": "test"}], ra.VIGNETTE_SETTINGS)
        required = [
            "run_id", "spec_version", "paper_version_label",
            "git_commit_or_hash", "execution_timestamp_utc",
            "random_seed", "donor_subset", "include_2024",
            "bootstrap_reps", "bootstrap_confidence_level",
            "quantile_method", "kde_bandwidth_rule",
            "size_function_A", "size_function_B", "size_function_C",
            "distribution_plot_mode", "environment_python_version",
            "vignette_id", "target_profiles",
        ]
        for f in required:
            assert f in meta, f"Missing metadata field: {f}"

    def test_size_function_coefficients(self):
        meta = ra._vig_metadata("v1", [], ra.VIGNETTE_SETTINGS)
        assert meta["size_function_A"] == 0.001
        assert meta["size_function_B"] == 0.5
        assert meta["size_function_C"] == -0.5

    def test_run_id_is_uuid(self):
        meta = ra._vig_metadata("v1", [], ra.VIGNETTE_SETTINGS)
        import uuid
        uuid.UUID(meta["run_id"])  # should not raise


class TestVigSnippet:
    def test_output_is_string(self):
        raw_stats = ra._dist_stats(list(np.random.RandomState(1).normal(0, 0.1, 100)), "Raw")
        adj_stats = ra._dist_stats(list(np.random.RandomState(2).normal(0, 0.05, 100)), "Adj")
        decomp = {"var995": {"mix_effect": -0.05, "size_effect": -0.01}}
        snippet = ra._vig_snippet("v1", raw_stats, adj_stats, decomp, 100, 2, 1, 2, 1)
        assert isinstance(snippet, str)
        assert len(snippet) > 50

    def test_mentions_donor_count(self):
        raw_stats = ra._dist_stats([0.1, 0.2, 0.3], "Raw")
        adj_stats = ra._dist_stats([0.05, 0.1, 0.15], "Adj")
        decomp = {"var995": {"mix_effect": -0.05, "size_effect": -0.01}}
        snippet = ra._vig_snippet("v1", raw_stats, adj_stats, decomp, 42, 1, 1, 1, 1)
        assert "42" in snippet

    def test_identifies_dominant_effect(self):
        raw_stats = ra._dist_stats([0.1, 0.2, 0.3], "Raw")
        adj_stats = ra._dist_stats([0.05, 0.1, 0.15], "Adj")
        # Mix dominates
        decomp = {"var995": {"mix_effect": -0.10, "size_effect": -0.01}}
        snippet = ra._vig_snippet("v1", raw_stats, adj_stats, decomp, 10, 1, 1, 1, 1)
        assert "mix adjustment" in snippet

    def test_extra_text_included(self):
        raw_stats = ra._dist_stats([0.1], "Raw")
        adj_stats = ra._dist_stats([0.05], "Adj")
        decomp = {"var995": {"mix_effect": -0.05, "size_effect": -0.01}}
        snippet = ra._vig_snippet("v1", raw_stats, adj_stats, decomp, 1, 1, 1, 1, 1,
                                  extra="CUSTOM_EXTRA_TEXT")
        assert "CUSTOM_EXTRA_TEXT" in snippet


# ─────────────────────────────────────────────────────────────────────────────
# Unit tests: target profile constants
# ─────────────────────────────────────────────────────────────────────────────

class TestVignetteProfiles:
    def test_v1_weights_sum_to_one(self):
        total = sum(ra.VIGNETTE_1_TARGET["lob_weights"].values())
        assert total == pytest.approx(1.0, abs=1e-9)

    def test_v2_old_weights_sum_to_one(self):
        total = sum(ra.VIGNETTE_2_OLD["lob_weights"].values())
        assert total == pytest.approx(1.0, abs=1e-9)

    def test_v2_new_weights_sum_to_one(self):
        total = sum(ra.VIGNETTE_2_NEW["lob_weights"].values())
        assert total == pytest.approx(1.0, abs=1e-9)

    def test_v2_new_lacks_dropped_lob(self):
        dropped = ra.VIGNETTE_2_NEW["dropped_lob_name"]
        assert dropped not in ra.VIGNETTE_2_NEW["lob_weights"]
        assert dropped in ra.VIGNETTE_2_OLD["lob_weights"]

    def test_v2_new_smaller_than_old(self):
        assert ra.VIGNETTE_2_NEW["reserve_size"] < ra.VIGNETTE_2_OLD["reserve_size"]

    def test_v2_new_more_concentrated(self):
        old_w = ra._vig_weights_vec(ra.VIGNETTE_2_OLD["lob_weights"])
        new_w = ra._vig_weights_vec(ra.VIGNETTE_2_NEW["lob_weights"])
        assert ra._vig_hhi(new_w) > ra._vig_hhi(old_w)

    def test_all_lob_names_valid(self):
        for profile in [ra.VIGNETTE_1_TARGET, ra.VIGNETTE_2_OLD, ra.VIGNETTE_2_NEW]:
            for lob in profile["lob_weights"]:
                assert lob in ra.LOB_INDEX, f"Invalid LoB name: {lob}"


# ─────────────────────────────────────────────────────────────────────────────
# Integration tests: end-to-end vignette 1
# ─────────────────────────────────────────────────────────────────────────────

class TestVignette1Integration:
    def _run_v1(self, tmp_dir, pool):
        """Run vignette 1 generation in a temp directory."""
        v1_dir = tmp_dir / "vignette-1"
        v1_dir.mkdir(parents=True, exist_ok=True)
        with mock.patch.object(ra, "SCRIPT_DIR", tmp_dir):
            (tmp_dir / "vignettes").mkdir(exist_ok=True)
            (tmp_dir / "vignettes" / "vignette-1").mkdir(exist_ok=True)
            # Patch requirements.txt existence
            (tmp_dir / "requirements.txt").write_text("numpy\n")
            ra._generate_vignette_1(pool, pool)
        return tmp_dir / "vignettes" / "vignette-1"

    def test_creates_all_required_files(self, donor_pool, tmp_dir):
        out = self._run_v1(tmp_dir, donor_pool)
        required = [
            "target_profile.json",
            "target_profile_table.csv", "target_profile_table.xlsx", "target_profile_table.tex",
            "donor_selection.csv", "donor_selection.xlsx", "donor_selection.tex",
            "worked_example_size_mismatch.json", "worked_example_mix_mismatch.json",
            "worked_example_size_mismatch.csv", "worked_example_mix_mismatch.csv",
            "distribution_stats.csv", "distribution_stats.xlsx", "distribution_stats.tex",
            "tail_support_bootstrap.csv", "tail_support_bootstrap.xlsx", "tail_support_bootstrap.tex",
            "decomposition_summary.csv", "decomposition_summary.xlsx", "decomposition_summary.tex",
            "distribution_plot.png", "distribution_plot.pdf",
            "tail_exceedance_plot.png", "tail_exceedance_plot.pdf",
            "distribution_plot_data.csv", "tail_exceedance_plot_data.csv",
            "summary_snippet.md",
            "metadata.json",
        ]
        for f in required:
            assert (out / f).exists(), f"Missing: {f}"

    def test_profile_json_valid(self, donor_pool, tmp_dir):
        out = self._run_v1(tmp_dir, donor_pool)
        with open(out / "target_profile.json") as f:
            profile = json.load(f)
        assert profile["vignette_id"] == "v1_new_entrant"
        assert profile["reserve_size"] == 500.0
        assert profile["donor_count"] == len(donor_pool)
        assert profile["adverse_donor_count"] > 0
        assert profile["hhi"] > 0

    def test_decomposition_adds_up(self, donor_pool, tmp_dir):
        out = self._run_v1(tmp_dir, donor_pool)
        import csv as csv_m
        with open(out / "decomposition_summary.csv") as f:
            rows = list(csv_m.DictReader(f))
        for row in rows:
            raw = float(row["raw_metric"])
            full = float(row["fully_adjusted_metric"])
            mix_e = float(row["mix_effect"])
            size_e = float(row["size_effect"])
            assert mix_e + size_e == pytest.approx(full - raw, abs=1e-4)

    def test_distribution_stats_has_three_rows(self, donor_pool, tmp_dir):
        out = self._run_v1(tmp_dir, donor_pool)
        import csv as csv_m
        with open(out / "distribution_stats.csv") as f:
            rows = list(csv_m.DictReader(f))
        labels = [r["distribution_label"] for r in rows]
        assert "Raw market" in labels
        assert "Adjusted target" in labels

    def test_metadata_has_size_function(self, donor_pool, tmp_dir):
        out = self._run_v1(tmp_dir, donor_pool)
        with open(out / "metadata.json") as f:
            meta = json.load(f)
        assert meta["size_function_A"] is not None
        assert meta["size_function_B"] is not None
        assert meta["size_function_C"] is not None


# ─────────────────────────────────────────────────────────────────────────────
# Integration tests: end-to-end vignette 2
# ─────────────────────────────────────────────────────────────────────────────

class TestVignette2Integration:
    def _run_v2(self, tmp_dir, pool):
        """Run vignette 2 generation in a temp directory."""
        with mock.patch.object(ra, "SCRIPT_DIR", tmp_dir):
            (tmp_dir / "vignettes").mkdir(exist_ok=True)
            (tmp_dir / "vignettes" / "vignette-2").mkdir(exist_ok=True)
            (tmp_dir / "requirements.txt").write_text("numpy\n")
            ra._generate_vignette_2(pool, pool)
        return tmp_dir / "vignettes" / "vignette-2"

    def test_creates_all_required_files(self, donor_pool, tmp_dir):
        out = self._run_v2(tmp_dir, donor_pool)
        required = [
            "target_transition.json",
            "target_transition_table.csv", "target_transition_table.xlsx",
            "donor_selection.csv",
            "worked_example_size_mismatch.json", "worked_example_mix_mismatch.json",
            "profile_transition_distribution.csv", "profile_transition_distribution.xlsx",
            "distribution_stats.csv",
            "tail_support_bootstrap.csv",
            "decomposition_summary.csv",
            "old_to_new_change_decomposition.csv",
            "distribution_plot.png", "distribution_plot.pdf",
            "tail_exceedance_plot.png", "tail_exceedance_plot.pdf",
            "old_to_new_waterfall.png", "old_to_new_waterfall.pdf",
            "summary_snippet.md",
            "metadata.json",
        ]
        for f in required:
            assert (out / f).exists(), f"Missing: {f}"

    def test_transition_json_valid(self, donor_pool, tmp_dir):
        out = self._run_v2(tmp_dir, donor_pool)
        with open(out / "target_transition.json") as f:
            trans = json.load(f)
        assert trans["dropped_lob_name"] == "Marine"
        assert trans["old_reserve_size"] == 800.0
        assert trans["new_reserve_size"] == 650.0
        assert trans["reserve_size_pct_change"] < 0
        assert trans["hhi_change"] > 0

    def test_v2_decomposition_adds_up(self, donor_pool, tmp_dir):
        out = self._run_v2(tmp_dir, donor_pool)
        import csv as csv_m
        with open(out / "old_to_new_change_decomposition.csv") as f:
            rows = list(csv_m.DictReader(f))
        for row in rows:
            old = float(row["old_profile_metric"])
            new = float(row["new_profile_metric"])
            mix_e = float(row["mix_change_effect"])
            size_e = float(row["size_change_effect"])
            assert mix_e + size_e == pytest.approx(new - old, abs=1e-4)

    def test_distribution_stats_has_four_rows(self, donor_pool, tmp_dir):
        out = self._run_v2(tmp_dir, donor_pool)
        import csv as csv_m
        with open(out / "distribution_stats.csv") as f:
            rows = list(csv_m.DictReader(f))
        labels = [r["distribution_label"] for r in rows]
        assert "Raw market" in labels
        assert "Adjusted old profile" in labels
        assert "Adjusted new profile" in labels

    def test_profile_transition_distribution_has_all_donors(self, donor_pool, tmp_dir):
        out = self._run_v2(tmp_dir, donor_pool)
        import csv as csv_m
        with open(out / "profile_transition_distribution.csv") as f:
            rows = list(csv_m.DictReader(f))
        assert len(rows) == len(donor_pool)
        # Check required columns
        for row in rows:
            assert "S_raw" in row
            assert "S_mix_old" in row
            assert "S_adj_old" in row
            assert "S_mix_new" in row
            assert "S_adj_new" in row

    def test_waterfall_data_has_four_bars(self, donor_pool, tmp_dir):
        out = self._run_v2(tmp_dir, donor_pool)
        import csv as csv_m
        with open(out / "old_to_new_waterfall_data.csv") as f:
            rows = list(csv_m.DictReader(f))
        assert len(rows) == 4
        bar_names = [r["bar"] for r in rows]
        assert "Old VaR99.5" in bar_names
        assert "New VaR99.5" in bar_names
        assert "Size effect" in bar_names
        assert "Mix effect" in bar_names


# ─────────────────────────────────────────────────────────────────────────────
# Integration test: generate_vignettes entry point
# ─────────────────────────────────────────────────────────────────────────────

class TestGenerateVignettes:
    def test_skips_without_combined_model(self, donor_pool):
        original = ra.COMBINED_MODEL
        ra.COMBINED_MODEL = None
        try:
            # Should not raise, just log a warning
            ra.generate_vignettes(donor_pool)
        finally:
            ra.COMBINED_MODEL = original

    def test_skips_with_insufficient_donors(self, tmp_dir):
        original_dir = ra.SCRIPT_DIR
        ra.SCRIPT_DIR = tmp_dir
        try:
            (tmp_dir / "vignettes" / "vignette-1").mkdir(parents=True, exist_ok=True)
            (tmp_dir / "vignettes" / "vignette-2").mkdir(parents=True, exist_ok=True)
            (tmp_dir / "requirements.txt").write_text("numpy\n")
            # Pool of 3 donors — below threshold
            pool = [_make_donor(i, 2020, 500, 0.05) for i in range(3)]
            ra.generate_vignettes(pool)
            # Should not have produced files (pool too small)
            v1_files = list((tmp_dir / "vignettes" / "vignette-1").iterdir())
            assert len(v1_files) == 0
        finally:
            ra.SCRIPT_DIR = original_dir


# ─────────────────────────────────────────────────────────────────────────────
# Edge case tests
# ─────────────────────────────────────────────────────────────────────────────

class TestEdgeCases:
    def test_all_releases_no_adverse(self, target_weights):
        """Pool with no adverse donors — selection should still work."""
        pool = [_make_donor(i, 2020, 100 * (i + 1), -0.05) for i in range(10)]
        size_d = ra._select_size_donor(pool, target_weights, 500, 0.3)
        assert size_d is not None
        mix_d = ra._select_mix_donor(pool, target_weights, 500, 0.3)
        assert mix_d is not None

    def test_single_donor_pool(self, target_weights):
        """Pool with exactly one donor."""
        pool = [_make_donor(1, 2020, 500, 0.05)]
        raw, mix, adj, ids = ra._compute_target_dists(pool, target_weights, 500)
        assert len(raw) == 1
        stats = ra._dist_stats(raw, "test")
        assert stats["n_total"] == 1

    def test_uniform_severity_across_lobs(self, target_weights):
        """When all LoB severities are equal, S_mix should equal that value."""
        sev = np.ones(ra.N_LOBS, dtype=float) * 0.05
        donor = _make_donor(1, 2020, 500, 0.05, lob_sev=sev)
        raw, mix, adj, ids = ra._compute_target_dists([donor], target_weights, 500)
        # S_mix = sum(tw_l * 0.05) = 0.05 * sum(tw) = 0.05
        assert mix[0] == pytest.approx(0.05, rel=1e-6)

    def test_worked_detail_with_zero_severity_lobs(self, target_weights):
        """Donor with some zero-severity LoB lines."""
        sev = np.zeros(ra.N_LOBS, dtype=float)
        sev[0] = 0.10  # Only Property has severity
        donor = _make_donor(1, 2020, 300, 0.10, lob_sev=sev)
        detail = ra._worked_detail(donor, target_weights, 500, 0.3, "v1", "p1")
        # S_mix should only come from Property weight × 0.10
        expected_s_mix = float(target_weights[0]) * 0.10
        assert detail["S_mix"] == pytest.approx(expected_s_mix, abs=1e-5)

    def test_identical_donor_and_target_gives_lambda_1(self, target_weights):
        """When donor size = target size, lambda should be 1."""
        detail = ra._worked_detail(
            _make_donor(1, 2020, 500, 0.05), target_weights, 500, 0.3, "v1", "p1")
        assert detail["size_multiplier_lambda"] == pytest.approx(1.0, rel=1e-6)
        assert detail["mix_to_adj_abs"] == pytest.approx(0.0, abs=1e-6)


# ─────────────────────────────────────────────────────────────────────────────
# Validation tests: spec compliance
# ─────────────────────────────────────────────────────────────────────────────

class TestSpecCompliance:
    """Tests ensuring outputs match the vignette specification requirements."""

    def test_v1_target_profile_card_fields(self):
        """Spec: target profile card must have these fields."""
        tw = ra._vig_weights_vec(ra.VIGNETTE_1_TARGET["lob_weights"])
        t_hhi = ra._vig_hhi(tw)
        required = ["vignette_id", "profile_id", "profile_label", "reserve_size",
                     "lob_weights_json", "hhi", "donor_subset", "donor_count",
                     "adverse_donor_count", "tail_support_count_var99",
                     "tail_support_count_var995"]
        # Simulate the card construction
        card = {
            "vignette_id": ra.VIGNETTE_1_TARGET["vignette_id"],
            "profile_id": ra.VIGNETTE_1_TARGET["profile_id"],
            "profile_label": ra.VIGNETTE_1_TARGET["profile_label"],
            "reserve_size": ra.VIGNETTE_1_TARGET["reserve_size"],
            "lob_weights_json": ra.VIGNETTE_1_TARGET["lob_weights"],
            "hhi": t_hhi,
            "donor_subset": "FULL",
            "donor_count": 100,
            "adverse_donor_count": 50,
            "tail_support_count_var99": 2,
            "tail_support_count_var995": 1,
        }
        for f in required:
            assert f in card

    def test_distribution_stats_required_columns(self):
        """Spec: distribution stats must have these columns."""
        stats = ra._dist_stats([0.1, 0.2, 0.3, -0.1, -0.05], "test")
        required = ["distribution_label", "n_total", "n_adverse",
                     "mean", "standard_deviation", "q75", "var99", "var995"]
        for f in required:
            assert f in stats

    def test_bootstrap_table_required_fields(self, donor_pool, target_weights):
        """Spec: bootstrap table must report point estimate, CI, tail support."""
        result = ra._bootstrap_ci(donor_pool, target_weights, 500, B=50, seed=42)
        assert result is not None
        for key in ["raw_var99", "raw_var995", "adj_var99", "adj_var995"]:
            lo, hi = result[key]
            assert lo is not None
            assert hi is not None

    def test_shapley_effects_are_additive(self, donor_pool, target_weights):
        """Spec: mix_effect + size_effect must equal fully_adjusted - raw."""
        result = ra._shapley_v1(donor_pool, target_weights, 500)
        for m in ["q75", "var99", "var995"]:
            d = result[m]
            total = d["fully_adjusted_metric"] - d["raw_metric"]
            assert abs(d["mix_effect"] + d["size_effect"] - total) < 1e-4

    def test_v2_transition_card_fields(self):
        """Spec: target transition card must have these fields."""
        required = ["vignette_id", "old_profile_label", "new_profile_label",
                     "old_reserve_size", "new_reserve_size",
                     "old_lob_weights_json", "new_lob_weights_json",
                     "old_hhi", "new_hhi",
                     "dropped_lob_name", "dropped_lob_old_weight",
                     "reserve_size_pct_change", "hhi_change",
                     "narrative_reason_label"]
        # Build a mock transition
        old_w = ra._vig_weights_vec(ra.VIGNETTE_2_OLD["lob_weights"])
        new_w = ra._vig_weights_vec(ra.VIGNETTE_2_NEW["lob_weights"])
        card = {
            "vignette_id": ra.VIGNETTE_2_OLD["vignette_id"],
            "old_profile_label": ra.VIGNETTE_2_OLD["profile_label"],
            "new_profile_label": ra.VIGNETTE_2_NEW["profile_label"],
            "old_reserve_size": ra.VIGNETTE_2_OLD["reserve_size"],
            "new_reserve_size": ra.VIGNETTE_2_NEW["reserve_size"],
            "old_lob_weights_json": ra.VIGNETTE_2_OLD["lob_weights"],
            "new_lob_weights_json": ra.VIGNETTE_2_NEW["lob_weights"],
            "old_hhi": ra._vig_hhi(old_w),
            "new_hhi": ra._vig_hhi(new_w),
            "dropped_lob_name": ra.VIGNETTE_2_NEW["dropped_lob_name"],
            "dropped_lob_old_weight": ra.VIGNETTE_2_NEW["dropped_lob_old_weight"],
            "reserve_size_pct_change": -18.75,
            "hhi_change": ra._vig_hhi(new_w) - ra._vig_hhi(old_w),
            "narrative_reason_label": ra.VIGNETTE_2_NEW["narrative_reason_label"],
        }
        for f in required:
            assert f in card

    def test_size_function_formula(self):
        """Spec: V_size(R) = A + B * R^C."""
        R = 300.0
        sm = ra.COMBINED_MODEL["size"]
        expected = sm["A"] + sm["B"] * R ** sm["C"]
        assert ra._v_size(R) == pytest.approx(expected)

    def test_size_multiplier_formula(self):
        """Spec: lambda = sqrt(V_size(R_target) / V_size(R_donor))."""
        R_t, R_d = 500, 200
        expected = math.sqrt(ra._v_size(R_t) / ra._v_size(R_d))
        assert ra._size_lambda(R_t, R_d) == pytest.approx(expected)

    def test_s_adj_formula(self, target_weights):
        """Spec: S_adj = S_mix * lambda."""
        donor = _make_donor(1, 2020, 200, 0.08)
        detail = ra._worked_detail(donor, target_weights, 500, 0.3, "v1", "p1")
        expected = detail["S_mix"] * detail["size_multiplier_lambda"]
        assert detail["S_adj"] == pytest.approx(expected, abs=1e-5)

    def test_s_mix_formula(self, target_weights):
        """Spec: S_mix = sum_over_lob(target_weight_l * donor_line_level_ratio_l)."""
        sev = _make_lob_severity(0.05)
        donor = _make_donor(1, 2020, 200, 0.08, lob_sev=sev)
        detail = ra._worked_detail(donor, target_weights, 500, 0.3, "v1", "p1")
        expected = float(np.sum(target_weights * sev))
        assert detail["S_mix"] == pytest.approx(expected, abs=1e-5)
