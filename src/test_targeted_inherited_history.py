"""Behavioural tests for the conditional inherited-history stress."""
import numpy as np
import pytest
from scipy import stats
import targeted_inherited_history as s


def rec(name, category='structural_no_eligible_outcome', year=2018, size=1):
    return {'file': name, 'category': category, 'year': year, 'size_proxy': size,
            'size_proxy_source': 'filing', 'syndicate': int(name.split('_')[1]),
            'observation': None}


def test_selection_uses_source_positive_and_conversion_not_zero():
    positive = rec('syndicate_1200_2018.json')
    zero = rec('syndicate_1201_2018.json')
    m01 = rec('syndicate_3902_2018.json', size=30.3)
    a = {positive['file']: {'opening_gross_reserve_gbp_m': 20, 'opening_gross_reserve_currency': 'USD',
                             'opening_gross_reserve_page': 7, 'source_sha256': 'a'},
         zero['file']: {'opening_gross_reserve_gbp_m': 0, 'opening_gross_reserve_currency': 'GBP',
                        'source_sha256': 'b'}}
    result = s.select_positive_screened([positive, zero, m01], a, {m01['file']: {'source_sha256': 'c'}}, {2018: 1.25})
    assert [r['file'] for r in result] == [positive['file'], m01['file']]
    assert result[0]['size_proxy'] == 16
    assert result[0]['sensitivity_source']['source_page'] == 7
    assert result[1]['size_proxy'] == 30.259
    assert result[1]['size_proxy_source'] == 'exact_source_opening_replaces_rounded_model'
    assert positive['size_proxy'] == 1  # do not mutate the shared disposition ledger
    a[positive['file']]['opening_gross_reserve_currency'] = 'EUR'
    with pytest.raises(ValueError, match='unsupported currency'):
        s.select_positive_screened([positive], a, {}, {2018: 1.25})


def test_quantile_placement_is_a_reproducible_permutation():
    for n in (34, 86):
        original = s.assigned_quantiles(n, 'original')
        shuffled = s.assigned_quantiles(n, 'permuted')
        np.testing.assert_array_equal(np.sort(shuffled), original)
        np.testing.assert_array_equal(shuffled, s.assigned_quantiles(n, 'permuted'))
        assert not np.array_equal(original, shuffled)
        assert np.mean(original) == pytest.approx(.5)
    with pytest.raises(ValueError):
        s.assigned_quantiles(34, 'unknown')


def test_pseudo_values_keep_case_specific_sizes_and_change_only_placement(monkeypatch):
    unavailable = [rec('syndicate_1200_2018.json', 'eligible_outcome_unavailable', size=100)]
    unresolved = [rec('syndicate_1201_2018.json', 'eligibility_unresolved', size=500)]
    selected = [rec('syndicate_1202_2018.json', size=1000)]
    rows = unavailable + unresolved + selected
    monkeypatch.setattr(s.original, 'ritc_flag', lambda names: np.array([False] * len(names)))
    calibration = {'nu_clean': 4, 'gamma': 0, 'k': .6, 'sd_undiv': .03, 'sd_div': .04}
    a = s.pseudo_inputs(rows, unavailable, unresolved, selected, np.array([10., 500.]), np.array([.4,.4]), calibration, 'original')
    b = s.pseudo_inputs(rows, unavailable, unresolved, selected, np.array([10., 500.]), np.array([.4,.4]), calibration, 'permuted')
    np.testing.assert_array_equal(a[1], [100,500,1000])
    np.testing.assert_array_equal(a[1], b[1])
    np.testing.assert_allclose(np.sort(a[5]), np.sort(b[5]))
    np.testing.assert_allclose(a[5], stats.t.ppf(a[4], df=4))
    assert a[6][0] > a[6][-1]  # independently implied by k<1 with a positive floor


def test_committed_draw_archives_match_result_hashes():
    """The recorded draws must be the exact archives that produced the result."""
    import hashlib
    import json
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    result = json.loads((root / "results/check_inherited_history_sensitivity_results.json").read_text(encoding="utf-8"))
    hashes = result["posterior_draw_hashes"]
    assert len(hashes) == 6
    for name, expected in hashes.items():
        archive = root / "results/inherited_history_draws" / name
        assert hashlib.sha256(archive.read_bytes()).hexdigest() == expected
        with np.load(archive, allow_pickle=False) as arrays:
            assert arrays.files
            for value in arrays.values():
                assert value.size > 0
                assert np.isfinite(value).all()


def test_all_free_diagnostics_record_each_element_and_missing_nonfinite(monkeypatch):
    import arviz as az
    import xarray as xr
    rng = np.random.default_rng(17)
    idata = az.from_dict(posterior={"theta": rng.normal(size=(4, 120)),
                                    "z_s": rng.normal(size=(4, 120, 2))},
                         sample_stats={"diverging": np.zeros((4, 120), dtype=bool)})
    years = np.array([2017, 2019])
    actual = s.all_parameter_diagnostics(idata, ["theta", "z_s"], years)
    assert actual["element_count"] == 3
    assert [x["reporting_year"] for x in actual["elements"]] == [None, 2017, 2019]
    assert all(x["missing_or_nonfinite"] == 0 for x in actual["metric_counts"].values())
    assert actual["extrema"]["rhat"]["parameter"] in ("theta", "z_s")
    monkeypatch.setattr(s.arviz, "rhat", lambda data, var_names: xr.Dataset({
        var_names[0]: ([], float("nan")) if var_names[0] == "theta"
        else (["z_s_dim_0"], [1.03, 1.01])}))
    impaired = s.all_parameter_diagnostics(idata, ["theta", "z_s", "missing"], years)
    assert impaired["element_count"] == 4
    assert impaired["metric_counts"]["rhat"] == {"finite": 2, "missing_or_nonfinite": 2}
    assert impaired["metric_counts"]["ess_bulk"]["missing_or_nonfinite"] == 1
    assert impaired["extrema"]["rhat"]["reporting_year"] == 2017
    assert impaired["extrema"]["rhat"]["rhat"] == pytest.approx(1.03)
    assert impaired["errors"] and "missing posterior variable" in impaired["errors"][0]


def test_recorded_all_free_diagnostics_match_draws_and_historical_results():
    import hashlib
    import json
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    result = json.loads((root / "results/check_inherited_history_allfree_diagnostics_results.json").read_text(encoding="utf-8"))
    previous = json.loads((root / "results/check_inherited_history_sensitivity_results.json").read_text(encoding="utf-8"))
    historic = json.loads((root / "results/check_missingness_sensitivity_results.json").read_text(encoding="utf-8"))["eligibility_unresolved_stress"]
    assert len(result["scenarios"]) == 4
    for scenario, current in result["scenarios"].items():
        old = historic if scenario == "690_original_clean" else previous["scenarios"][scenario]
        if scenario != "690_original_clean":
            for key in ("pseudo_inputs", "imputation", "allocation", "n_fit", "n_pseudo"):
                assert current[key] == old[key]
        for c, fit in current["by_c"].items():
            for key in ("k", "sd_undiv", "sd_div", "nu_clean", "nu_ritc", "tau_s", "_diag"):
                assert fit[key] == old["by_c"][c][key]
            diag = fit["_diag_all_free"]
            assert diag["free_parameters"] == ["theta", "log_tot", "f", "tau_s", "z_s", "nu_clean", "lambda_ritc", "beta_ritc"]
            assert diag["element_count"] == len(diag["elements"]) == 18
            assert len([x for x in diag["elements"] if x["parameter"] == "z_s" and x["reporting_year"] is not None]) == 11
            assert diag["divergences"] == 0 and not diag["errors"]
            for metric, select in (("rhat", max), ("ess_bulk", min), ("ess_tail", min)):
                assert diag["metric_counts"][metric] == {"finite": 18, "missing_or_nonfinite": 0}
                extreme = select(diag["elements"], key=lambda x: x[metric])
                assert diag["extrema"][metric] == {k: extreme[k] for k in ("parameter", "index", "reporting_year", metric)}
            name = f"{scenario}-c{float(c):g}-draws.npz"
            digest = hashlib.sha256((root / "results/inherited_history_draws" / name).read_bytes()).hexdigest()
            assert digest == result["posterior_draw_hashes"][name]
            if scenario != "690_original_clean":
                assert digest == previous["posterior_draw_hashes"][name]
