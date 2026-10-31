"""Ensure current inputs and connected published outputs carry one run identity."""
import glob
import json
import re
from pathlib import Path

import run_analysis as ra

ROOT = Path(__file__).resolve().parent.parent


def _load(path):
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def test_loaded_input_fingerprints_match_every_connected_output():
    """A current source/input tree must not ship identifiers from an older run."""
    files = sorted(glob.glob(str(ra.DATA_DIR / "syndicate_*.json")))
    assert files, "cannot validate the run ID without its extraction inputs"
    code = ra.hash_script()
    full_data = ra.run_source_hash(files, [ra.calibration_file(), ra.overlay_calibration_file()])
    bare_data = ra.run_source_hash(files, ())
    full_id = ra.derive_run_id(full_data, code)
    bare_id = ra.derive_run_id(bare_data, code)

    exposure = _load("model/exposure_results.json")
    assert exposure["analysis_code_hash"] == code
    assert exposure["source_data_hash"] == full_data
    assert exposure["analysis_run_id"] == full_id
    assert exposure["analysis_run_id_without_calibration"] == bare_id
    for vignette in ("vignette-1", "vignette-2"):
        assert _load(f"vignettes/{vignette}/metadata.json")["run_id"] == full_id

    html = (ROOT / "distortion_tool.html").read_text(encoding="utf-8")
    match = re.search(r"const EMBEDDED_DATA = (\{.*?\});\s*\n", html)
    assert match, "the interactive tool must embed the data it displays"
    assert json.loads(match.group(1))["run_id"] == full_id

    assert _load("results/check_small_book_diagnosis_results.json")["inputs"][
        "loader_run_id_without_calibration"] == bare_id
    assert _load("results/check_exclusion_influence_results.json")[
        "loader_run_id_without_calibration"] == bare_id
    error = _load("results/error_rate_propagation_results.json")
    assert error["fit"]["loader_run_id_without_calibration"] == bare_id
    assert error["rate_population"]["current"]["exposure_results_run_id_without_calibration"] == bare_id
    assert error["pooled_rate_sensitivity"]["rate_population"]["current"][
        "exposure_results_run_id_without_calibration"] == bare_id
