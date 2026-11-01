"""Integrity checks for the mixed-source inherited-history evidence."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_corrected_scenarios_preserve_historical_690_and_record_full_diagnostics():
    old = json.loads((ROOT / 'results/check_inherited_history_allfree_diagnostics_results.json').read_text(encoding='utf8'))
    current = json.loads((ROOT / 'results/check_inherited_history_corrected_results.json').read_text(encoding='utf8'))
    for name in ('690_original_clean', '690_permuted'):
        assert current['scenarios'][name] == old['scenarios'][name]
        assert current['scenario_source_commits'][name] == old['run']['source_commit']
    for name in ('742_original', '742_permuted'):
        previous = old['scenarios'][name]['pseudo_inputs']
        corrected = current['scenarios'][name]['pseudo_inputs']
        assert len(previous) == len(corrected) == 86
        changes = [(a['file'], key, a.get(key), b.get(key))
                   for a, b in zip(previous, corrected)
                   for key in a.keys() | b.keys() if a.get(key) != b.get(key)]
        assert changes == [('syndicate_1980_2018.json', 'ritc_flag', False, True)]
        assert current['scenario_source_commits'][name] == current['run']['source_commit']
    for scenario in current['scenarios'].values():
        for fit in scenario['by_c'].values():
            diag = fit['_diag_all_free']
            assert diag['element_count'] == 18 and not diag['errors']
            assert diag['divergences'] == 0
            assert all(counts == {'finite': 18, 'missing_or_nonfinite': 0}
                       for counts in diag['metric_counts'].values())
    for name, expected in current['posterior_draw_hashes'].items():
        archive = ROOT / current['posterior_draw_paths'][name]
        assert hashlib.sha256(archive.read_bytes()).hexdigest() == expected


def test_historical_artifact_hash_identifies_the_committed_content_on_any_checkout():
    """The record's hash was read from a CRLF working copy (docs/inherited-history-sensitivity-20261031.md); it must
    name the committed content in its LF or its CRLF form, whichever line endings this checkout has, and no other."""
    current = json.loads((ROOT / 'results/check_inherited_history_corrected_results.json').read_text(encoding='utf8'))
    artifact = current['historical_690_artifact']
    lf = (ROOT / artifact['path']).read_bytes().replace(b'\r\n', b'\n')
    forms = {hashlib.sha256(lf).hexdigest(), hashlib.sha256(lf.replace(b'\n', b'\r\n')).hexdigest()}
    assert artifact['sha256'] in forms
