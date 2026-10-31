import importlib
import numpy as np
import pytest

shape = importlib.import_module('test_shape_invariance')
ritc = importlib.import_module('ritc_shape_invariance')
tail = importlib.import_module('ritc_tail_shape')


def rows():
    return [{'s_raw_a': float(np.sin(i/3) + i/100), 'opening_reserves_gbp_m': 20.,
             'hhi': 0.5, 'syndicate': str(i), 'year': 2016} for i in range(40)]


def cal():
    return {'k': .5, 'gamma': 0., 'sd_undiv': 1., 'sd_div': 1., 'reference_size': 20.}


@pytest.mark.parametrize("sign", [.01, .5])
def test_axis_bootstrap_sign_is_not_a_p_value_or_significance_verdict(monkeypatch, capsys, sign):
    monkeypatch.setattr(shape, 'anderson_ksample_shape', lambda *args: {'stat': 2., 'p': sign})
    monkeypatch.setattr(shape, 'cluster_bootstrap_diff', lambda *args, **kwargs: {'point': .2, 'ci': (.1, .3), 'p': sign})
    monkeypatch.setattr(shape, 'cluster_bootstrap_slope', lambda *args, **kwargs: {'slope': .2, 'ci': (.1, .3), 'p': sign})
    x = np.arange(40.)
    shape.analyse_axis('example', x, np.sin(x), x, np.random.default_rng(7))
    output = capsys.readouterr().out
    assert output.count(f'sign2={sign:.3f}') == 6
    assert 'not an established null-calibrated p-value' in output
    assert 'panel dependence' in output and 'medians/IQRs can also alter' in output
    assert 'mixture of conditional scales' in output
    assert '***' not in output and 'SHAPE DIFFERS' not in output
    assert 'Linear slope across deciles' in output and 'Monotone trend' not in output
    assert 'Kruskal-Wallis on group ranks' in output and 'medians equal?' not in output


@pytest.mark.parametrize("sign", [.01, .5])
def test_tail_sign_is_descriptive(monkeypatch, capsys, sign):
    def contrast(*args, **kwargs):
        result = {'clean': 1., 'ritc': 2., 'obs': 1., 'ci': (.1, 2.), 'p': sign, 'n_boot': 20}
        if kwargs.get('bound_fn'):
            result.update(ritc_at_bound=None, clean_at_bound=None, n_boot_at_bound=0)
        return result
    monkeypatch.setattr(tail, 'cluster_contrast', contrast)
    store = {}
    tail.run('example', rows(), {f'{i}_2016' for i in range(20)}, set(), cal(), np.random.default_rng(7), store)
    output = capsys.readouterr().out
    assert 'sign2' in output and 'not an established null-calibrated p-value' in output
    assert '***' not in output
    gpd_line = next(line for line in output.splitlines() if 'GPD xi' in line)
    assert 'pooled threshold; scale-sensitive' in gpd_line
    assert all(x['p'] == sign for x in store['example']['tests'].values())


@pytest.mark.parametrize("sign", [.01, .5])
def test_ritc_sign_is_descriptive_and_fisher_test_remains_distinct(monkeypatch, capsys, sign):
    monkeypatch.setattr(ritc, 'cluster_bootstrap_ratio', lambda *a, **kw: {'ratio': 1.1, 'ci': (1., 1.2), 'p': sign})
    monkeypatch.setattr(ritc, 'cluster_bootstrap_diff', lambda *a, **kw: {'point': .2, 'ci': (.1, .3), 'p': sign})
    monkeypatch.setattr(ritc, 'anderson_ksample_shape',
                        lambda values, groups: {'stat': 2., 'p': sign, 'k': len(np.unique(groups))})
    monkeypatch.setattr(ritc.stats, 'fisher_exact', lambda *a: (2., .01))
    store = {}
    ritc.analyse('example', rows(), {f'{i}_2016' for i in range(20)}, set(), cal(), np.random.default_rng(7), store)
    output = capsys.readouterr().out
    assert output.count(f'sign2={sign:.3f}') == 7
    assert 'not an established null-calibrated p-value' in output
    assert 'panel dependence' in output and 'medians/IQRs can also alter' in output
    assert 'mixture of conditional scales' in output
    assert 'SHAPE DIFFERS' not in output and ' -> DIFFERS' not in output
    assert 'SHAPE COMPARISONS on raw s' in output
    assert 'raw severity s' in store['example']['meta']['shape_section_input']
    assert 'scale mix' in store['example']['meta']['group_shape_note']
    assert 'estimated group median/IQR' in store['example']['meta']['row_test_note']
    assert store['example']['shape']['ad_three_way'] is None
    assert store['example']['shape']['ad_available_groups']['groups'] == ['clean', 'strong']
    assert 'Three-way clean/weak/strong Anderson-Darling comparison unavailable' in output
    assert 'Fisher p=0.010  ***' in output
    assert all(a['fisher_p'] == .01 and a['odds_ratio'] == 2. for a in store['example']['tail']['levels'].values())
    assert all('***' not in line for line in output.splitlines() if 'sign2=' in line)


def test_legacy_axis_summary_does_not_claim_a_nonzero_slope_proves_drift(monkeypatch, capsys):
    monkeypatch.setattr(shape, 'build_population', lambda: [])
    monkeypatch.setattr(shape, 'run_for', lambda *args: None)
    shape.main()
    output = capsys.readouterr().out
    assert 'Panel dependence and estimated medians/IQRs' in output
    assert 'within-group scale mix' in output
    assert 'do not establish invariance or the direction of tail error' in output
    assert 'shape is NOT invariant' not in output
    assert 'positive affine rescaling' in output


def test_working_axis_summary_names_its_threshold_as_diagnostic(monkeypatch, tmp_path, capsys):
    import check_shape_invariance as working

    result = {'n': 40, 'n_syndicates': 20, 'no_drift_on_either_axis': True,
              'axes': {'size': {'shape_anderson_darling': {'p': .25}, 'no_drift': True}}}
    monkeypatch.setattr(working, 'load_sample', lambda: (None,) * 6)
    monkeypatch.setattr(working, 'run', lambda *args: result)
    monkeypatch.setattr(working, 'OUT', tmp_path / 'result.json')
    working.main()
    output = capsys.readouterr().out
    assert 'diagnostic threshold flag on both axes: True' in output
    assert 'does not prove invariance' in output
    assert 'Panel dependence and estimated medians/IQRs' in output
    assert 'within-group scale mix' in output


def test_tail_summary_distinguishes_fixed_threshold_gpd_from_shape(monkeypatch, tmp_path, capsys):
    import json

    calibration = tmp_path / 'calibration.json'
    calibration.write_text(json.dumps(cal()), encoding='utf-8')
    monkeypatch.setattr(tail, 'CAL', calibration)
    monkeypatch.setattr(tail, 'OUT', tmp_path / 'tail.json')
    monkeypatch.setattr(tail.assumed_business, 'strong_weak', lambda: (set(), set()))
    monkeypatch.setattr(tail, 'load_calib_population', lambda: [])
    monkeypatch.setattr(tail, 'build_population', lambda: [])
    monkeypatch.setattr(tail, 'select', lambda records, mode: [])
    monkeypatch.setattr(tail, 'run', lambda *args: None)
    tail.main()
    output = capsys.readouterr().out
    assert 'GPD xi uses a fixed pooled threshold' in output
    assert 'can change under group rescaling' in output
    assert 'its contrast alone does not establish a shape change' in output
    assert 'Hill index' in output and 'q95/q99 ratios describe magnitudes' in output


def test_ritc_summary_reports_where_direction_is_recorded(monkeypatch, tmp_path, capsys):
    import json

    calibration = tmp_path / 'calibration.json'
    calibration.write_text(json.dumps(cal()), encoding='utf-8')
    monkeypatch.setattr(ritc, 'CAL', calibration)
    monkeypatch.setattr(ritc, 'OUT', tmp_path / 'shape.json')
    monkeypatch.setattr(ritc.assumed_business, 'strong_weak', lambda: (set(), set()))
    monkeypatch.setattr(ritc, 'load_calib_population', lambda: [])
    monkeypatch.setattr(ritc, 'build_population', lambda: [])
    monkeypatch.setattr(ritc, 'select', lambda records, mode: [])
    monkeypatch.setattr(ritc, 'analyse', lambda *args: None)
    ritc.main()
    output = capsys.readouterr().out
    assert "direction is recorded with its ratio in the result file" in output
    assert "direction is printed with its ratio above" not in output


@pytest.mark.parametrize("weak_mode", ['absent', 'sparse', 'flat', 'valid'])
def test_ritc_subgroup_ad_reports_only_eligible_groups(monkeypatch, capsys, weak_mode):
    # A nonempty weak group is ineligible when it has fewer than eight rows or zero IQR.
    monkeypatch.setattr(ritc, 'cluster_bootstrap_ratio', lambda *a, **kw: None)
    monkeypatch.setattr(ritc, 'cluster_bootstrap_diff', lambda *a, **kw: None)
    sample = rows()
    strong = {f'{i}_2016' for i in range(10)}
    weak_count = {'absent': 0, 'sparse': 7, 'flat': 10, 'valid': 10}[weak_mode]
    weak = {f'{i}_2016' for i in range(10, 10 + weak_count)}
    if weak_mode == 'flat':
        for i in range(10, 20):
            sample[i]['s_raw_a'] = .1
    store = {}
    ritc.analyse('example', sample, strong, weak, cal(), np.random.default_rng(7), store)
    output = capsys.readouterr().out
    record = store['example']['shape']
    expected = ['clean', 'weak', 'strong'] if weak_mode == 'valid' else ['clean', 'strong']
    assert record['ad_available_groups']['groups'] == expected
    assert record['ad_available_groups']['result']['k'] == len(expected)
    assert (record['ad_three_way'] is not None) == (weak_mode == 'valid')
    assert ('Three-way clean/weak/strong Anderson-Darling comparison unavailable' in output) == (weak_mode != 'valid')


def test_ritc_binary_ad_unavailable_when_a_group_has_zero_iqr(monkeypatch, capsys):
    monkeypatch.setattr(ritc, 'cluster_bootstrap_ratio', lambda *a, **kw: None)
    monkeypatch.setattr(ritc, 'cluster_bootstrap_diff', lambda *a, **kw: None)
    sample = rows()
    for i in range(10):
        sample[i]['s_raw_a'] = .1
    strong = {f'{i}_2016' for i in range(10)}
    store = {}
    ritc.analyse('example', sample, strong, set(), cal(), np.random.default_rng(7), store)
    output = capsys.readouterr().out
    assert store['example']['shape']['ad_clean_vs_ritc'] is None
    assert store['example']['shape']['ad_available_groups'] == {'groups': ['clean'], 'result': None}
    assert store['example']['shape']['ad_three_way'] is None
    assert 'clean vs RITC comparison unavailable' in output
