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
    assert 'within-syndicate dependence may miscalibrate' in output
    assert '***' not in output and 'SHAPE DIFFERS' not in output


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
    monkeypatch.setattr(ritc, 'anderson_ksample_shape', lambda *a: {'stat': 2., 'p': sign})
    monkeypatch.setattr(ritc.stats, 'fisher_exact', lambda *a: (2., .01))
    store = {}
    ritc.analyse('example', rows(), {f'{i}_2016' for i in range(20)}, set(), cal(), np.random.default_rng(7), store)
    output = capsys.readouterr().out
    assert output.count(f'sign2={sign:.3f}') == 7
    assert 'not an established null-calibrated p-value' in output
    assert 'within-syndicate dependence may miscalibrate' in output
    assert 'SHAPE DIFFERS' not in output and ' -> DIFFERS' not in output
    assert 'Fisher p=0.010  ***' in output
    assert all(a['fisher_p'] == .01 and a['odds_ratio'] == 2. for a in store['example']['tail']['levels'].values())
    assert all('***' not in line for line in output.splitlines() if 'sign2=' in line)


def test_legacy_axis_summary_does_not_claim_a_nonzero_slope_proves_drift(monkeypatch, capsys):
    monkeypatch.setattr(shape, 'build_population', lambda: [])
    monkeypatch.setattr(shape, 'run_for', lambda *args: None)
    shape.main()
    output = capsys.readouterr().out
    assert 'may be miscalibrated under panel dependence' in output
    assert 'do not establish invariance or the direction of tail error' in output
    assert 'shape is NOT invariant' not in output


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
    assert 'may be miscalibrated under within-syndicate dependence' in output


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
