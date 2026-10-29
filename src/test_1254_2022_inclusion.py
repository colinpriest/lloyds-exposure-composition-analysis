"""Source-backed conditional 1254/2022 scenario does not alter the headline."""
import copy
import json

import pytest

import adopted_model as am
import assumed_business
import run_analysis as ra
from check_1254_2022_inclusion import FIXTURE, KEY, scenario_from_fixture


def fixture():
    return json.loads(FIXTURE.read_text(encoding='utf-8'))


def test_gross_bridge_movement_and_source_weight_mapping():
    f = fixture()
    s = scenario_from_fixture(f, ra.build_weight_vector)
    assert s['reserve_base_gbp_m'] == pytest.approx(75.257)
    assert s['gross_movement_gbp_m'] == pytest.approx(-4.733)
    assert s['severity'] == pytest.approx(-4.733 / 75.257)
    assert s['hhi'] == pytest.approx((1571**2 + 503**2 + 230**2 + 191**2 + 12**2) / 2507**2)
    assert s['closing_triangle_difference_gbp_m'] == pytest.approx(0.298)
    assert sum(s['weights']) == pytest.approx(1.0)
    assert f['gross_written_premiums_gbp_m'] == pytest.approx(2.507)
    assert len(f['assumptions']) == 4


def test_scenario_refuses_broken_bridge_cohort_or_mix():
    original = fixture()
    broken = copy.deepcopy(original); broken['gross_foreign_exchange_change_gbp_m'] += 1
    with pytest.raises(ValueError, match='bridge'):
        scenario_from_fixture(broken, ra.build_weight_vector)
    broken = copy.deepcopy(original); broken['ritc_years_of_account'] = [2017, 2018, 2019, 2022]
    with pytest.raises(ValueError, match='cohort'):
        scenario_from_fixture(broken, ra.build_weight_vector)
    broken = copy.deepcopy(original); broken['gross_premium_mix'][0]['amount_gbp_m'] += 1
    with pytest.raises(ValueError, match='premium mix'):
        scenario_from_fixture(broken, ra.build_weight_vector)


def test_record_is_excluded_from_headline_and_is_strong_ritc():
    S, R, H, year, synd, ritc = am.load_sample()
    keys = ['%s_%s' % (s, y) for s, y in zip(synd, year)]
    assert len(keys) == 632 and KEY not in keys
    assert '1254_2023' in keys and KEY in assumed_business.keys()
    scan = json.loads((FIXTURE.parent.parent / 'pdf_extraction/ritc_scan.json').read_text(encoding='utf-8'))
    assert scan[KEY]['ritc_occurred'] and scan[KEY]['confidence'] == 'strong'


def test_recorded_result_preserves_provenance_and_scenario():
    import hashlib
    import subprocess
    from pathlib import Path

    root = FIXTURE.parent.parent
    summary_path = root / 'results/conditional_1254_2022_inclusion_results.json'
    prov_path = root / 'results/conditional_1254_2022_inclusion_provenance.json'
    summary = json.loads(summary_path.read_text(encoding='utf-8'))
    prov = json.loads(prov_path.read_text(encoding='utf-8'))
    canonical = summary_path.read_bytes().replace(b'\r\n', b'\n')
    assert hashlib.sha256(canonical).hexdigest() == prov['result_sha256_normalized_lf']
    assert summary['code_commit'] == prov['run_code_commit']
    assert summary['working_tree_dirty'] and prov['run_working_tree_dirty']
    assert not prov['old_full_reproduction_report_applies_to_this_targeted_run']
    for name, info in prov['new_inputs'].items():
        blob = subprocess.check_output(['git', '-C', str(root), 'hash-object', name], text=True).strip()
        assert blob == info['normalized_git_blob']
    assert summary['scenario_source'] == fixture()
    assert summary['scenario'] == scenario_from_fixture(fixture(), ra.build_weight_vector)
    assert summary['source_report_sha256'] == prov['source_report_sha256']
    assert summary['baseline_n'] == 632 and summary['conditional_n'] == 633
    assert summary['baseline_n_syndicates'] == summary['conditional_n_syndicates'] == 117
    assert summary['ritc_assumed_business']
    assert summary['diagnostics']['divergences'] == 0
    assert summary['diagnostics']['max_rhat'] <= 1.01
    baseline = json.loads((root / 'results/check_gamma0_vignette_results.json').read_text(encoding='utf-8'))
    assert summary['baseline_centre'] == baseline['size_only']['centre']
    for key, relative in summary['relative_to_baseline'].items():
        assert relative == pytest.approx(summary['refit_and_rebuilt_pool'][key] / summary['baseline_centre'][key] - 1)
    assert summary['pool_only']['V1_v995'] == summary['baseline_centre']['V1_v995']
