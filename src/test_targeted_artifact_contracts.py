"""Behavioural checks for the separate targeted-producer and historical-evidence contracts."""
import hashlib
import json
import subprocess
import sys
import types
from pathlib import Path

import pytest
import reproduce as rp
import targeted_maturity_refit as maturity


def test_variants_are_independent_and_refuse_missing_457():
    primary = {'records': {'457_2015': {'phi_delta_1': .4}, 'other': {'phi_delta_1': .8}}}
    out = maturity.candidate(primary, 'exclude-457')
    assert '457_2015' not in out['records']
    assert '457_2015' in primary['records']
    with pytest.raises(ValueError, match='missing'):
        maturity.candidate(out, 'exclude-457')


def test_maturity_refit_routes_seven_summaries_to_new_directory(tmp_path, monkeypatch):
    root = tmp_path / 'repo'
    (root / 'model').mkdir(parents=True)
    rows = {'records': {'457_2015': {f'phi_delta_{t}': .8 for t in maturity.TAGS}}}
    (root / 'model/maturity_share.json').write_text(json.dumps(rows))
    exposure = {'observations': [{'syndicate': 457, 'year': 2015, 's_raw_a': .1,
                                  'opening_reserves_gbp_m': 10, 'hhi': .3}]}
    (root / 'model/exposure_results.json').write_text(json.dumps(exposure))
    class Table:
        index = ['k']
        columns = ['mean']
        class Loc:
            def __getitem__(self, key): return .62
        loc = Loc()
    fake = types.ModuleType('check_maturity_denominator')
    fake.az = types.SimpleNamespace(summary=lambda *args, **kw: Table())
    def fake_main():
        proxy = json.loads(fake.MAT.read_text())
        assert '457_2015' not in proxy['records']
        for _ in range(7): fake.az.summary()
        fake.OUT.write_text('{"fitted": true}')
    fake.main = fake_main
    monkeypatch.setattr(maturity, 'ROOT', root)
    monkeypatch.setitem(sys.modules, 'check_maturity_denominator', fake)
    monkeypatch.setitem(sys.modules, 'build_maturity_group_sensitivity', types.SimpleNamespace(build=None))
    target = tmp_path / 'fresh'
    maturity.run('exclude-457', target)
    assert json.loads((target / 'results.json').read_text())['fitted']
    assert len(json.loads((target / 'diagnostics.json').read_text())['fit_summaries']) == 7
    assert json.loads((target / 'inputs.json').read_text())['candidate']['n_refit'] == 0
    assert json.loads((root / 'model/maturity_share.json').read_text()) == rows
    with pytest.raises(FileExistsError): maturity.run('exclude-457', target)


def test_targeted_contracts_reject_untracked_producer_and_altered_history(tmp_path, monkeypatch):
    subprocess.run(['git', 'init', '-q', str(tmp_path)], check=True)
    (tmp_path / 'src').mkdir(); (tmp_path / 'results').mkdir()
    producer = tmp_path / 'src/producer.py'; producer.write_text('print(1)\n')
    record = tmp_path / 'results/history.json'; record.write_bytes(b'{"actual": 1}\n')
    (tmp_path / 'results/refit.json').write_text('{}')
    subprocess.run(['git', '-C', str(tmp_path), 'add', 'src/producer.py', 'results/history.json', 'results/refit.json'], check=True)
    digest = hashlib.sha256(record.read_bytes()).hexdigest()
    monkeypatch.setattr(rp, 'HERE', str(tmp_path))
    monkeypatch.setattr(rp, 'TARGETED_PRODUCERS', {'results/refit.json': ('src/producer.py', '--output-dir PATH; results.json')})
    monkeypatch.setattr(rp, 'TARGETED_RUN_EVIDENCE', {'results/history.json': digest})
    assert rp.check_targeted_contracts() == []
    record.write_bytes(b'{"actual": 2}\n')
    assert any('differs from its recorded hash' in err for err in rp.check_targeted_contracts())
    record.write_bytes(b'{"actual": 1}\n')
    subprocess.run(['git', '-C', str(tmp_path), 'rm', '--cached', '-q', 'src/producer.py'], check=True)
    assert any('no tracked producer' in err for err in rp.check_targeted_contracts())
    subprocess.run(['git', '-C', str(tmp_path), 'rm', '--cached', '-q', 'results/history.json'], check=True)
    assert any('historical evidence' in err and 'not tracked' in err for err in rp.check_targeted_contracts())


def test_real_contracts_cover_thirteen_new_records():
    assert len(rp.TARGETED_PRODUCERS) == 6
    assert len(rp.TARGETED_RUN_EVIDENCE) == 7
    assert set(rp.TARGETED_PRODUCERS).isdisjoint(rp.TARGETED_RUN_EVIDENCE)
    assert rp.check_targeted_contracts() == []
    assert rp.check_manifest_completeness() == []
