"""Committed sensitivity result is tied to its data, producer and run evidence."""
import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RESULT = ROOT / "results/source_numerator_sensitivity_results.json"
PROVENANCE = ROOT / "results/source_numerator_sensitivity_provenance.json"


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_result_matches_targeted_run_and_normalized_producer():
    result = read(RESULT)
    provenance = read(PROVENANCE)
    assert hashlib.sha256(RESULT.read_bytes().replace(b'\r\n', b'\n')).hexdigest() == provenance["result_sha256"]
    script = ROOT / "src/check_source_numerator_sensitivity.py"
    blob = subprocess.check_output(["git", "-C", str(ROOT), "hash-object", str(script)], text=True).strip()
    assert blob == provenance["producer"]["normalized_git_blob"]
    assert result["code_commit"] == provenance["run_code_commit"]
    assert result["working_tree_dirty"]
    assert not provenance["old_full_reproduction_report_applies_to_this_targeted_run"]


def test_baseline_and_recorded_scenarios_are_consistent():
    result = read(RESULT)
    baseline = read(ROOT / "results/check_gamma0_vignette_results.json")["size_only"]["centre"]
    assert result["baseline_centre"] == baseline
    assert result["baseline_exactly_reproduces_published_centre"]
    assert result["baseline_n"] == 632
    cases = result["cases"]
    assert set(cases) == {"exclude_3330_2017", "exclude_1274_2016", "exclude_both",
                          "printed_2016_table", "prior_cell_without_retranslation"}
    for name, n in (("exclude_3330_2017", 631), ("exclude_1274_2016", 631),
                    ("exclude_both", 630), ("printed_2016_table", 632),
                    ("prior_cell_without_retranslation", 632)):
        case = cases[name]
        assert case["n_fit_and_donors"] == n
        assert case["diagnostics"]["divergences"] == 0
        assert case["diagnostics"]["max_rhat"] <= 1.01
        for q, relative in case["relative_to_baseline"].items():
            assert abs(relative - (case["refit_and_rebuilt_pool"][q] / baseline[q] - 1.0)) < 1e-12
