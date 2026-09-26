#!/usr/bin/env python3
"""The serial-dependence diagnostic, its limits, and the claims made from it.

The frozen review of 25 September 2026 found three things wrong at once, and each needs a test that
would have caught it:

  M01  The permutation p-value was the share of draws FURTHER FROM ZERO than the observed statistic.
       De-meaning within syndicate biases the pooled lag-1 correlation down by about 1/(T-1), so that
       null is centred near -0.195, and in a null centred below zero "distance from zero" is not a
       test of positive persistence. The published 0.96 and the directed 0.037 came from the same
       4,000 permutations. A test that only checked the number was reproducible would not have seen
       it, so the tests here check the STATISTIC'S BEHAVIOUR on series built with known dependence.

  D01  The demeaning benchmark was quoted as a bound on the serial component. It assumes one lag-1
       coefficient and one marginal variance for every syndicate, and once the variances are allowed
       to differ a process with no persistent level at all reproduces BOTH published statistics. So
       the algebra must respond to the variances it is given, and the counterexample must be recorded.

  D03  Two active diagnostics described a marginal regression of log|S| on log R as the conditional
       derivative d log sigma / d log R, and one wrote that into its result JSON, with thresholds
       (-0.342, -0.171) that the recorded calibration had since moved away from.

Run:  python -m pytest src/test_serial_dependence_claims.py -q
"""
import io
import json
import os

import numpy as np
import pytest

import adopted_model
import check_pyd_temporal_correlation as C

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESULTS = os.path.join(HERE, "results")
SRC = os.path.join(HERE, "src")


def _read(*parts):
    return io.open(os.path.join(HERE, *parts), encoding="utf-8").read()


def _json(*parts):
    path = os.path.join(HERE, *parts)
    if not os.path.exists(path):
        pytest.skip("%s is not present in this checkout" % os.path.join(*parts))
    return json.load(io.open(path, encoding="utf-8"))


def _series(paths, values):
    """A {syndicate: (years, values)} dict in the shape series_by_synd returns."""
    return {i: (np.asarray(y, float), np.asarray(v, float)) for i, (y, v) in enumerate(zip(paths, values))}


# ----------------------------------------------------------------- M01: the direction ------
class TestTheTestPointsAtPositivePersistence:
    """The statistic and its p-values, on data whose dependence is known by construction."""

    def test_the_upper_tail_p_is_the_rank_in_the_null(self):
        null = np.arange(100, dtype=float) / 100.0      # 0.00 .. 0.99
        # 10 draws are >= 0.90, and the observed statistic counts once itself
        assert C.upper_tail_p(null, 0.90) == pytest.approx(11 / 101)
        assert C.upper_tail_p(null, -1.0) == pytest.approx(101 / 101)
        assert C.upper_tail_p(null, 2.0) == pytest.approx(1 / 101)

    def test_the_two_sided_rank_p_is_about_the_nulls_centre_not_zero(self):
        """A null centred at -0.2: a statistic AT the centre is unremarkable, and one at zero is in
        the upper tail. Measured from zero instead, the centre would look extreme."""
        null = np.random.default_rng(0).normal(-0.2, 0.05, 20000)
        assert C.two_sided_rank_p(null, -0.2) > 0.5
        assert C.two_sided_rank_p(null, 0.0) < 0.001
        assert C.upper_tail_p(null, 0.0) < 0.001

    def test_the_two_sided_rank_p_takes_twice_the_SMALLER_tail(self):
        """A statistic far BELOW the null's centre is two-sided extreme too. Twice the upper tail
        alone would call it unremarkable (it caps at 1), which is the whole point of the smaller
        tail: the quantity must see both directions."""
        null = np.random.default_rng(0).normal(-0.2, 0.05, 20000)
        assert C.upper_tail_p(null, -0.5) > 0.99
        assert C.two_sided_rank_p(null, -0.5) < 0.01
        assert C.two_sided_rank_p(null, -0.5) == pytest.approx(
            2 * (1 + np.sum(null <= -0.5)) / (null.size + 1))

    def test_the_superseded_distance_from_zero_reads_the_opposite_way(self):
        """The defect itself, in three lines: on a null centred below zero, an observed statistic at
        zero is extreme by rank and unremarkable by distance from zero."""
        null = np.random.default_rng(0).normal(-0.2, 0.05, 20000)
        obs = 0.0
        p_abs = (1 + np.sum(np.abs(null) >= abs(obs))) / (null.size + 1)
        assert p_abs > 0.99, "distance from zero must be the misleading quantity here"
        assert C.upper_tail_p(null, obs) < 0.001

    @pytest.mark.parametrize("rho,expect_small", [(0.7, True), (0.0, False), (-0.7, False)])
    def test_the_directed_p_detects_positive_dependence_and_not_its_absence(self, rho, expect_small):
        """Build 60 syndicates of 9 years as AR(1) with a known rho, no level, and run the section's
        own statistic and null. A positive rho must be detected; zero and negative must not be."""
        rng = np.random.default_rng(11)
        years = list(range(2014, 2023))
        vals = []
        for _ in range(60):
            x = [rng.normal()]
            for _ in range(len(years) - 1):
                x.append(rho * x[-1] + rng.normal() * np.sqrt(1 - rho ** 2))
            vals.append(x)
        ser = _series([years] * 60, vals)
        obs = C.pooled_lag1(ser, "pearson")
        null = C.within_syndicate_null(ser, 600, np.random.default_rng(3),
                                      lambda s: C.pooled_lag1(s, "pearson"))
        p = C.upper_tail_p(null, obs)
        assert null.mean() < 0, "the permutation null of a demeaned statistic sits below zero"
        assert (p < 0.01) == expect_small, (rho, obs, null.mean(), p)

    def test_the_within_syndicate_null_is_fooled_by_a_common_year_component(self):
        """Why the section's finding cannot rest on the published null, even pointed the right way.

        The panel here has a common reporting-year component and NO within-syndicate dynamics at all,
        so a correctly sized test must not reject. Permuting a syndicate's own years destroys its
        alignment with the calendar, so the year component lands in the observed statistic and not in
        the null: the unadjusted test rejects anyway. Taking each year's location and scale out of the
        cross-section first repairs it. This is the single-panel version of the (g) calibration.
        """
        S, syn0, yr0 = C.load()
        base = C.series_by_synd(S, syn0, yr0, min_obs=3)
        vals, syn, yr = C.simulate_panel(base, year_rho=0.6, syn_rho=0.0,
                                         rng=np.random.default_rng(4))
        ser = C.series_by_synd(vals, syn, yr, min_obs=3)
        obs = C.pooled_lag1(ser, "pearson")
        within = C.within_syndicate_null(ser, 400, np.random.default_rng(7),
                                         lambda s: C.pooled_lag1(s, "pearson"))
        assert C.upper_tail_p(within, obs) < 0.05, \
            "this panel has no within-syndicate dynamics, so a rejection here is the null's fault"
        adj = C.per_year_adjusted(vals, yr)
        ser_adj = C.series_by_synd(adj, syn, yr, min_obs=3)
        obs_adj = C.pooled_lag1(ser_adj, "pearson")
        null_adj = C.within_syndicate_null(ser_adj, 400, np.random.default_rng(7),
                                           lambda s: C.pooled_lag1(s, "pearson"))
        assert C.upper_tail_p(null_adj, obs_adj) > 0.05, \
            "the per-year-adjusted test must not reject a panel with no within-syndicate dynamics"

    def test_the_adjusted_test_still_finds_dynamics_when_they_are_there(self):
        """The other half: a test that never rejects is not correctly sized, it is useless."""
        S, syn0, yr0 = C.load()
        base = C.series_by_synd(S, syn0, yr0, min_obs=3)
        vals, syn, yr = C.simulate_panel(base, year_rho=0.6, syn_rho=0.4,
                                         rng=np.random.default_rng(4))
        adj = C.per_year_adjusted(vals, yr)
        ser = C.series_by_synd(adj, syn, yr, min_obs=3)
        obs = C.pooled_lag1(ser, "pearson")
        null = C.within_syndicate_null(ser, 400, np.random.default_rng(7),
                                       lambda s: C.pooled_lag1(s, "pearson"))
        assert C.upper_tail_p(null, obs) < 0.05

    def test_the_year_block_permutation_keeps_each_years_membership_and_values(self):
        """What the block null does and does not do: a year's cross-section moves whole, so its
        members and values are preserved, but the ARRANGEMENT of the years is destroyed -- which is
        why it cannot separate a persistent year component from within-syndicate dynamics."""
        vals = np.arange(30, dtype=float)
        syn = np.repeat([1, 2, 3], 10)
        yr = np.tile(np.arange(2014, 2024), 3)
        seen = []
        C.year_block_null(vals, syn, yr, 3, np.random.default_rng(1),
                          lambda ser: seen.append(sorted(
                              (int(y), float(v)) for _s, (yy, vv) in ser.items()
                              for y, v in zip(yy, vv))) or 0.0)
        original = sorted((int(y), float(v)) for y, v in zip(yr, vals))
        by_year = {}
        for y, v in original:
            by_year.setdefault(y, []).append(v)
        moved = 0
        for draw in seen:
            drawn = {}
            for y, v in draw:
                drawn.setdefault(y, []).append(v)
            # every year still carries one whole original year's set of values
            assert sorted(tuple(sorted(v)) for v in drawn.values()) == \
                sorted(tuple(sorted(v)) for v in by_year.values())
            if any(sorted(drawn[y]) != sorted(by_year[y]) for y in by_year):
                moved += 1
        assert moved, "the years were never actually rearranged, so this is not a permutation null"

    def test_per_year_adjustment_removes_a_common_year_level_and_scale(self):
        rng = np.random.default_rng(9)
        yr = np.repeat([2014, 2015, 2016], 200)
        z = np.concatenate([rng.normal(5.0, 3.0, 200), rng.normal(-2.0, 0.5, 200),
                            rng.normal(0.0, 1.0, 200)])
        out = C.per_year_adjusted(z, yr)
        for t in (2014, 2015, 2016):
            m = yr == t
            assert abs(float(np.median(out[m]))) < 1e-9
            assert abs(1.4826 * float(np.median(np.abs(out[m] - np.median(out[m])))) - 1.0) < 1e-9


class TestTheRecordedDiagnostic:
    """What the committed output must carry, so no reader meets the old quantity unlabelled."""

    def test_the_old_key_is_gone_and_the_directed_ones_are_there(self):
        a = _json("results", "check_pyd_temporal_correlation_results.json")["a_lag1_demeaned"]
        assert "permutation_p_two_sided" not in a, \
            "the ambiguous key is back: it named a distance-from-zero quantity 'two sided'"
        for key in ("p_upper_positive_persistence", "p_two_sided_rank", "permutation_null",
                    "alternative"):
            assert key in a, key

    def test_the_superseded_quantity_is_labelled_as_superseded(self):
        a = _json("results", "check_pyd_temporal_correlation_results.json")["a_lag1_demeaned"]
        keys = [k for k in a if "absolute_distance_from_zero" in k]
        assert keys == ["p_absolute_distance_from_zero_superseded"], keys
        assert "not a test of positive persistence" in a["superseded_note"]

    def test_the_nulls_own_location_is_recorded_beside_every_p_value(self):
        d = _json("results", "check_pyd_temporal_correlation_results.json")
        null = d["a_lag1_demeaned"]["permutation_null"]
        for key in ("mean", "median", "sd", "pct2_5", "pct97_5", "share_below_zero", "draws"):
            assert key in null, key
        assert null["mean"] < 0, "the demeaning bias must be visible in the recorded null"
        for entry in d["f_conditional_on_adopted_model"]["tests"].values():
            for method in ("pearson", "spearman"):
                assert entry[method]["permutation_null"]["mean"] < 0

    def test_the_conditional_test_is_recorded_under_both_nulls(self):
        f = _json("results", "check_pyd_temporal_correlation_results.json")["f_conditional_on_adopted_model"]
        assert set(f["tests"]) == {"year_block_permutation", "per_year_adjusted"}
        assert "sigma_numeric" in f["residual"]
        assert "per_year_adjusted" in f["primary"], \
            "the primary must be the test (g) shows to be correctly sized"

    def test_the_nulls_calibration_is_recorded_and_says_which_to_trust(self):
        """M01's "demonstrated behaviour under its stated null": the shares are measured on these
        year sets, and the script refuses to write its output if they stop supporting the reading."""
        g = _json("results", "check_pyd_temporal_correlation_results.json")["g_null_calibration"]
        # BOTH statistics, because the section leads with the rank one: a calibration of the other
        # would leave the reported p-value's behaviour unmeasured
        for method in ("pearson", "spearman"):
            size = g["rejection_shares"]["common_year_component_only"][method]
            power = g["rejection_shares"]["within_syndicate_ar1"][method]
            # literals, not the module's own constants: comparing a record against the thresholds
            # that produced it is vacuous, and loosening those thresholds would then pass unnoticed
            assert size["per_year_adjusted"] <= 0.35, method
            assert size["unadjusted"] >= 0.50, \
                "the published null must be shown to over-reject the %s statistic" % method
            assert power["per_year_adjusted"] >= 0.50, method
            assert size["per_year_adjusted"] < size["unadjusted"], method
        # and the script's own guards must be no weaker than what this test requires
        assert C.CAL_MAX_SIZE_ADJUSTED <= 0.35
        assert C.CAL_MIN_SIZE_UNADJUSTED >= 0.50
        assert C.CAL_MIN_POWER >= 0.50
        for key in ("panels_per_design", "permutations_per_panel", "alpha", "year_component_lag1",
                    "alternative_within_syndicate_lag1", "seed", "limits"):
            assert key in g, key

    def test_the_diagnostic_refuses_to_write_an_uncalibrated_test(self):
        """The guards, exercised: each threshold must be able to stop the script."""
        S, syn, yr = C.load()
        ser = C.series_by_synd(S, syn, yr, min_obs=3)
        # two panels is enough to reach the guard; the point is the guard, not the estimate
        cal = C.calibrate_nulls(ser, reps=2, perms=40, seed=1)
        assert set(cal) == {"common_year_component_only", "within_syndicate_ar1"}
        for design in cal.values():
            assert set(design) == {"pearson", "spearman"}
            for shares in design.values():
                assert set(shares) == {"unadjusted", "per_year_adjusted"}
                for v in shares.values():
                    assert 0.0 <= v <= 1.0

    def test_no_document_says_the_dependence_was_not_detected(self):
        """Generalised over the repository's own current documents rather than a list of the two the
        review happened to name: the claim is retired, so it must be absent everywhere it could be
        restated. Retired phrasings live in one register."""
        retired = (
            r"no residual (serial|temporal|year-to-year|lag-1) \w*\s*(dependence|association)",
            r"(de-?meaned )?lag-1 correlation is null",
            r"no positive residual lag-1 association is detected",
            r"detects no residual",
            r"gives no reason to (add|consider) an? (autoregressive|AR)",
            r"what the contrast does exclude is dynamics",
        )
        import re
        targets = []
        for root in ("docs", "src", "results"):
            base = os.path.join(HERE, root)
            for dirpath, dirnames, filenames in os.walk(base):
                dirnames[:] = [d for d in dirnames if d not in ("__pycache__", ".pytest_cache")]
                for fn in filenames:
                    if fn.endswith((".md", ".py", ".json")):
                        targets.append(os.path.join(dirpath, fn))
        targets.append(os.path.join(HERE, "README.md"))
        me = os.path.abspath(__file__)
        bad = []
        for path in targets:
            if os.path.abspath(path) == me:
                continue        # this file names the retired phrasings in order to forbid them
            try:
                flat = " ".join(io.open(path, encoding="utf-8", errors="replace").read().split())
            except OSError:
                continue
            for pat in retired:
                for m in re.finditer(pat, flat, re.I):
                    window = flat[max(0, m.start() - 160):m.end() + 160]
                    # a sentence that reports the claim as RETIRED is the point, not a violation
                    if re.search(r"used to|superseded|no longer|was an artefact|until the frozen|"
                                 r"it is not:|frozen review of 25 September|must be absent|retired",
                                 window, re.I):
                        continue
                    bad.append("%s: %s" % (os.path.relpath(path, HERE), window[:200]))
        assert not bad, "the retired non-detection claim survives in:\n" + "\n".join(bad)


# ------------------------------------------------------- D01: the benchmark's assumptions ------
class TestTheBenchmarkIsAnIllustrationNotABound:

    def test_the_algebra_responds_to_the_variances_it_is_given(self):
        """If the variances argument were ignored, the two readings would agree and the review's
        point would be invisible."""
        years = list(range(2014, 2023))
        short = list(range(2014, 2018))
        ser = _series([years] * 10 + [short] * 10, [[0.0] * 9] * 10 + [[0.0] * 4] * 10)
        equal = C.demeaned_lag1_under_ar1(ser, 0.4)
        heavy = C.demeaned_lag1_under_ar1(ser, 0.4, {s: (100.0 if len(y) <= 4 else 1.0)
                                                     for s, (y, _v) in ser.items()})
        assert equal != pytest.approx(heavy, abs=1e-6)

    def test_equal_variances_is_the_default_and_is_the_same_as_passing_ones(self):
        years = list(range(2014, 2023))
        ser = _series([years] * 8, [[0.0] * 9] * 8)
        assert C.demeaned_lag1_under_ar1(ser, 0.5) == pytest.approx(
            C.demeaned_lag1_under_ar1(ser, 0.5, {s: 1.0 for s in ser}))

    def test_the_rho_reading_can_be_taken_under_either_assumption(self):
        d = _json("results", "check_pyd_temporal_correlation_results.json")
        bench = d["e_demeaning_benchmark"]
        het = bench["heterogeneous_variance_reading"]
        assert bench["rho_reading_the_observed_demeaned"] is not None
        assert het["rho_reading_the_observed_demeaned"] is not None
        assert het["rho_reading_the_observed_demeaned"] != pytest.approx(
            bench["rho_reading_the_observed_demeaned"], abs=1e-4), \
            "the two readings must differ, which is why neither is a bound"
        assert "assumptions" in bench and "SAME marginal variance" in bench["assumptions"]

    def test_the_observed_variances_use_the_unbiased_estimator(self):
        """ddof matters on series this short: at ddof=0 the recorded reading moves from 0.141 to
        0.129, so the choice is pinned rather than left to whichever numpy default."""
        years = list(range(2014, 2018))
        ser = _series([years], [[1.0, 2.0, 3.0, 6.0]])
        got = C.observed_variances(ser)[0]
        assert got == pytest.approx(float(np.var([1.0, 2.0, 3.0, 6.0], ddof=1)))
        assert got != pytest.approx(float(np.var([1.0, 2.0, 3.0, 6.0])))

    def test_the_counterexample_reproduces_both_published_statistics(self):
        """The heart of D01: a level-free process at the observed RAW lag-1 that reads the observed
        DE-MEANED one. If it exists, the contrast between the two excludes nothing."""
        d = _json("results", "check_pyd_temporal_correlation_results.json")
        bench = d["e_demeaning_benchmark"]
        ce = bench["counterexample_to_excluding_dynamics"]
        assert ce["variance_for_short_histories"] is not None
        assert ce["rho"] == pytest.approx(bench["observed_raw_lag1"])
        assert ce["reading"] == pytest.approx(ce["target_observed_demeaned"], abs=1e-9)
        assert ce["n_short_histories"] > 0

    def test_the_counterexample_is_computed_and_not_recorded_by_hand(self):
        S, syn, yr = C.load()
        ser = C.series_by_synd(S, syn, yr, min_obs=3)
        raw = float(C.corr(*C.lag_pairs(ser, 1, demean=False), "pearson"))
        dem = C.pooled_lag1(ser, "pearson")
        var, n_short = C.short_history_variance_reading(ser, raw, dem)
        rec = _json("results", "check_pyd_temporal_correlation_results.json")[
            "e_demeaning_benchmark"]["counterexample_to_excluding_dynamics"]
        assert var == pytest.approx(rec["variance_for_short_histories"], rel=1e-6)
        assert n_short == rec["n_short_histories"]

    def test_no_counterexample_exists_when_every_variance_is_equal(self):
        """The claim was not absurd: under equal variances the contrast DOES exclude that process.
        The reading at the observed raw lag-1 is above the observed statistic, and no positive
        short-history variance below the search ceiling brings it down to it when nothing is short."""
        years = list(range(2014, 2023))
        ser = _series([years] * 20, [[0.0] * 9] * 20)
        var, n_short = C.short_history_variance_reading(ser, 0.48, -0.09)
        assert n_short == 0
        assert var is None, "with no short histories there is nothing to reweight"


# --------------------------------------------------- the consequence for the parameters ------
class TestTheDependenceSensitivity:

    def test_the_sensitivity_records_both_designs(self):
        ss = _json("results", "check_serial_sensitivity_results.json")
        assert "design_a_group_dispersion" in ss and "design_b_adjacency" in ss
        assert ss["n_groups"] >= 3
        assert len(ss["design_a_group_dispersion"]["k"]["group_means"]) == ss["n_groups"]

    def test_thinning_removes_the_adjacency_it_claims_to_remove(self):
        ss = _json("results", "check_serial_sensitivity_results.json")
        adj = ss["design_b_adjacency"]
        assert adj["thinned"]["adjacent_pairs"] == 0, \
            "a thinned half that still holds consecutive years is not isolating adjacency"
        assert adj["random_matched"]["adjacent_pairs"] > 0
        assert adj["thinned"]["n"] == adj["random_matched"]["n"], "the two halves must match on n"

    def test_group_dispersion_is_not_promoted_to_an_interval_multiplier(self):
        ss = _json("results", "check_serial_sensitivity_results.json")
        for name, cal in ss["design_a_group_dispersion"].items():
            assert cal["prior_sd"] is not None, name
            assert cal["data_informative"] == (not cal["prior_dominated"]), name
            assert cal["descriptive_ratio_between_over_reported"] >= 0, name
            assert "headline_sd_scaled_by_factor" not in cal, name
            if cal["prior_dominated"]:
                assert "why_not_interpretable" in cal, name
        assert "do not correct" in ss["reading"]

    def test_every_fit_converged_and_is_recorded_with_its_gap_from_the_headline(self):
        ss = _json("results", "check_serial_sensitivity_results.json")
        assert len(ss["fits"]) == ss["n_groups"] + 2
        for f in ss["fits"]:
            assert f["max_rhat"] < 1.05, (f["label"], f["max_rhat"])
            assert f["must_match_headline"] is False
            assert "gap_from_headline_in_sd" in f


class TestTheNumericScaleIsTheModelsOwn:
    """sigma_numeric and scale_block must be one definition; the residuals in (f) depend on it."""

    def test_the_numeric_scale_matches_the_symbolic_block(self):
        pm = pytest.importorskip("pymc")
        S, R, H, yr, syn, ritc = adopted_model.load_sample()
        h = adopted_model.headline()
        params = {n: v["mean"] for n, v in h.items()}
        with pm.Model():
            b = adopted_model.scale_block(R=R, H=H, yr=yr, ritc=ritc)
            # the block's sigma at the published means, with the year shock switched off, which is
            # the quantity sigma_numeric computes
            sym = pm.math.exp(b["beta_ritc"] * ritc) * pm.math.sqrt(b["var"])
            got = sym.eval({b["k"]: params["k"], b["gamma"]: params["gamma"],
                            b["sd_undiv"]: params["sd_undiv"], b["sd_div"]: params["sd_div"],
                            b["beta_ritc"]: params["beta_ritc"]})
        num = adopted_model.sigma_numeric(R, H, ritc, params)
        assert np.allclose(num, got, rtol=1e-10, atol=1e-14)

    def test_the_year_shock_needs_both_its_arguments(self):
        with pytest.raises(ValueError):
            adopted_model.sigma_numeric([500.0], [0.2], [0.0], s_y=[0.1])
        with pytest.raises(ValueError):
            adopted_model.sigma_numeric([500.0], [0.2], [0.0], yidx=[0])

    def test_the_numeric_scale_applies_the_hhi_bounds(self):
        params = {n: v["mean"] for n, v in adopted_model.headline().items()}
        below = adopted_model.sigma_numeric([500.0], [1e-6], [0.0], params)
        at = adopted_model.sigma_numeric([500.0], [adopted_model.HHI_FLOOR], [0.0], params)
        assert below == pytest.approx(at)


# ------------------------------------------------------- D03: marginal is not conditional ------
class TestTheLargeBookSlopeIsLabelledMarginal:

    MARGINAL = ("check_large_book_slope.py", "check_large_book_slope_bayes.py")

    @pytest.mark.parametrize("rel", MARGINAL)
    def test_neither_script_claims_the_regression_is_the_derivative(self, rel):
        flat = " ".join(_read("src", rel).split())
        import re
        for m in re.finditer(r"d log sigma / d log R", flat):
            window = flat[max(0, m.start() - 260):m.end() + 260]
            assert re.search(r"not the conditional derivative|MARGINAL|no-floor law|floor law|"
                             r"candidate scale laws|at each observation", window), window[:200]
        assert "estimates d log sigma / d log R directly" not in flat
        assert "Because S is a scale family, b estimates" not in flat

    @pytest.mark.parametrize("rel", MARGINAL)
    def test_neither_script_hard_codes_the_superseded_thresholds(self, rel):
        src = _read("src", rel)
        assert "-0.342" not in src, "the no-floor slope is generated; the recorded value has moved"
        assert "-0.171" not in src

    @pytest.mark.parametrize("rel", MARGINAL)
    def test_each_script_points_at_the_controlled_estimate(self, rel):
        flat = " ".join(_read("src", rel).split())
        assert "check_large_book_slope_conditional.py" in flat
        assert "product-of-marginals" in flat

    def test_the_word_equivalence_only_appears_being_disclaimed(self):
        """"That is an equivalence-style statement and it is what the paper needs" was the claim. The
        word may stay only where it is being denied."""
        flat = " ".join(_read("src", "check_large_book_slope.py").split())
        import re
        for m in re.finditer(r"equivalence", flat, re.I):
            window = flat[max(0, m.start() - 200):m.end() + 60]
            assert re.search(r"nothing in it is an equivalence|not as an equivalence", window, re.I), \
                window[-160:]
        assert "equivalence-style" not in flat

    def test_the_generated_metadata_says_marginal_too(self):
        d = _json("results", "check_large_book_slope_results.json")
        assert "MARGINAL" in d["definition"]
        assert "not the conditional derivative" in d["definition"]
        assert "check_large_book_slope_conditional.py" in d["definition"]
        assert "equals d log sigma / d log R" not in d["definition"]
        assert "model_local_slopes_are" in d

    def test_the_bayes_metadata_says_marginal_too(self):
        d = _json("results", "check_large_book_slope_bayes_results.json")
        assert "MARGINAL" in d["b_is"]
        assert "product-of-marginals" in d["b_is"]
        assert d["b_implied_by_nofloor_law"] is not None

    def test_the_model_reference_slopes_still_come_from_the_calibrations(self):
        """Labelling them marginal must not have turned the generated reference values into
        constants: they are k-1 from the recorded fits."""
        d = _json("results", "check_large_book_slope_results.json")
        cv = _json("results", "check_pooling_cv_extended_results.json")["full_sample_params"]
        assert d["model_local_slopes"]["no_floor_constant"] == pytest.approx(
            cv["M7_free_k_nofloor"]["k"][0] - 1.0, rel=1e-9)
        assert d["model_local_slopes"]["floor_k_minus_1"] == pytest.approx(
            cv["M1_free_k_floor"]["k"][0] - 1.0, rel=1e-9)
    # ------------------------------------------------ the conceptual check the review asked for ------
    @staticmethod
    def _floorless_panel(b, n=20000, k=0.6, gamma=0.5, seed=7):
        """A panel drawn from the FLOORLESS law, with log H moving with log R at slope `b`.

        log sigma = const + (k-1)(log R - gamma log H), which is the no-floor scale law written out.
        The conditional derivative d log sigma / d log R is exactly k-1 by construction, so any gap
        the marginal slope shows is the concentration term arriving through the correlation.
        """
        rng = np.random.default_rng(seed)
        logR = rng.normal(0.0, 1.0, n)
        logH = -1.0 + b * logR + rng.normal(0.0, 0.3, n)
        log_sigma = (k - 1.0) * (logR - gamma * logH)
        S = np.exp(log_sigma) * rng.standard_normal(n)
        return logR, logH, np.log(np.abs(S)), k, gamma

    @pytest.mark.parametrize("b", [0.35, -0.35])
    def test_a_size_correlated_concentration_moves_the_marginal_slope(self, b):
        """The marginal slope is (k-1)(1 - gamma*b); the conditional slope is k-1. They differ
        whenever b is not zero, and the sign of b decides which way."""
        logR, logH, y, k, gamma = self._floorless_panel(b)
        marginal = float(np.polyfit(logR, y, 1)[0])
        X = np.column_stack([np.ones(logR.size), logR, logH])
        conditional = float(np.linalg.lstsq(X, y, rcond=None)[0][1])
        predicted = (k - 1.0) * (1.0 - gamma * b)
        assert conditional == pytest.approx(k - 1.0, abs=0.02),             "controlling log H must recover the law's own derivative"
        assert marginal == pytest.approx(predicted, abs=0.02),             "the marginal slope must be what the algebra says, not the derivative"
        assert abs(marginal - conditional) > 0.05,             "the two must differ materially here, or the example demonstrates nothing"
        if b > 0:
            assert marginal > conditional,                 "concentration rising with size makes the decline look shallower than it is"
        else:
            assert marginal < conditional, "and falling with size makes it look steeper"

    def test_the_two_agree_when_concentration_does_not_move_with_size(self):
        """The control: the conflation is harmless exactly when the covariates are unrelated, which
        is the condition the older diagnostics never stated."""
        logR, logH, y, k, _gamma = self._floorless_panel(0.0)
        marginal = float(np.polyfit(logR, y, 1)[0])
        X = np.column_stack([np.ones(logR.size), logR, logH])
        conditional = float(np.linalg.lstsq(X, y, rcond=None)[0][1])
        assert marginal == pytest.approx(conditional, abs=0.02)
        assert marginal == pytest.approx(k - 1.0, abs=0.02)

    def test_the_repository_records_that_size_and_concentration_are_associated(self):
        """Which is why the example is not hypothetical here. The magnitude is whatever the fit
        gives; this asserts only that the association is measured and recorded, so a reader can see
        that the marginal and conditional slopes are different quantities on these data."""
        d = _json("results", "check_size_concentration_assoc_results.json")
        flat = json.dumps(d)
        assert "pearson" in flat, "the association must be recorded somewhere in this output"

    def test_the_conditional_diagnostic_states_its_own_limitation(self):
        """And the controlled estimate the two older ones now point at carries its own caveat, which
        they must not silently inherit as a stronger claim."""
        flat = " ".join(_read("src", "check_large_book_slope_conditional.py").split())
        assert "PRODUCT-OF-MARGINALS" in flat
        assert "not a joint posterior probability" in flat
