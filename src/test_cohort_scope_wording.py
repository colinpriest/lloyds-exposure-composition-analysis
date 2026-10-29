"""Check that source descriptions distinguish classification from source evidence."""

import ast
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def _source(name):
    return (ROOT / "src" / name).read_text(encoding="utf-8")


def _main_metadata():
    from check_cohort_scope import scope_notes
    return scope_notes()


def test_classification_metadata_discloses_the_roll_forward_limit():
    notes = _main_metadata()
    assert "classifications are not proof" in notes["purpose"]
    assert "3330/2017" in notes["estimand_note"]
    assert "may include current-year claims" in notes["estimand_note"]
    assert "does not establish" in notes["estimand_note"]
    assert "For the 672 construction" in notes["count_note"]
    assert "classified as triangle-sourced" in notes["count_note"]


def test_generator_qualifies_roll_forward_and_depth_descriptions():
    source = _source("build_mature_cohort_figures.py")
    tree = ast.parse(source)
    strings = [n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, str)]
    texts = [v for v in strings if "current-year claims" in v]
    assert len(texts) >= 3
    assert all("establish" in v for v in texts)
    assert "gross claims incurred is M" not in source
    assert "so this is their step" not in source


def test_pinned_record_is_classified_but_uses_a_roll_forward():
    observations = json.loads((ROOT / "model" / "exposure_results.json").read_text(encoding="utf-8"))["observations"]
    record = next(o for o in observations if str(o["syndicate"]) == "3330" and o["year"] == 2017)
    source = json.loads((ROOT / "data" / "mature_cohort_figures.json").read_text(encoding="utf-8"))["3330_2017"]
    assert record["pyd_cohort_scope"] == "mature-enforced"
    assert source["correction"]["method"] == "roll_forward"
    assert source["figure_m"] == 0.559


def test_refresh_notes_preserves_fitted_results(tmp_path, monkeypatch):
    import check_cohort_scope as scope

    result = tmp_path / "result.json"
    original = {"purpose": "old", "estimand_note": "old", "count_note": "old",
                "fit": {"mean": 0.42, "draws": [1.0, 2.0]}, "n": 672}
    result.write_text(json.dumps(original), encoding="utf-8")
    monkeypatch.setattr(scope, "OUT", result)
    scope.refresh_notes()
    refreshed = json.loads(result.read_text(encoding="utf-8"))
    assert refreshed["fit"] == original["fit"]
    assert refreshed["n"] == original["n"]
    assert {k: refreshed[k] for k in scope.scope_notes()} == scope.scope_notes()
