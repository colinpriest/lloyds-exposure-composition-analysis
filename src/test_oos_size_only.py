"""Round 55 (T01): the size-only comparison is computed from the same-run benchmark
record, never from embedded constants. Changing the benchmark inputs changes the
differences; a benchmark from a different sample, fold count or seed is refused.

Run:  python -m pytest src/test_oos_size_only.py -q
"""
import io
import json
import os
import re
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import oos_size_only as oso  # noqa: E402


def test_differences_follow_the_benchmark_inputs():
    a = oso.comparison(500.0, {"held_out_ELPD_model": 550.0, "held_out_ELPD_naive": 495.0})
    assert a["size_only_minus_composition_model"] == pytest.approx(-50.0)
    assert a["size_only_minus_naive_pool"] == pytest.approx(5.0)
    b = oso.comparison(500.0, {"held_out_ELPD_model": 540.0, "held_out_ELPD_naive": 510.0})
    assert b["size_only_minus_composition_model"] == pytest.approx(-40.0)
    assert b["size_only_minus_naive_pool"] == pytest.approx(-10.0)
    assert a["held_out_ELPD_composition_model"] == 550.0 and b["held_out_ELPD_naive_pool"] == 510.0


def test_a_benchmark_from_another_run_is_refused(monkeypatch):
    ref = json.load(io.open(os.path.join(ROOT, "results", "oos_validation_results.json"), encoding="utf-8"))
    with pytest.raises(SystemExit):
        oso.load_reference(ref["n"] + 1, ref["folds"], ref["seed"])
    with pytest.raises(SystemExit):
        oso.load_reference(ref["n"], ref["folds"], ref["seed"] + 1)
    assert oso.load_reference(ref["n"], ref["folds"], ref["seed"]) is not None


def test_no_embedded_benchmark_survives_in_the_script():
    src = io.open(os.path.join(HERE, "oos_size_only.py"), encoding="utf-8").read()
    assert not re.search(r"\b(598\.66|530\.71)\b", src)
    assert "vs_full_" not in src and "vs_naive_" not in src


def test_the_committed_result_carries_the_computed_keys():
    p = os.path.join(ROOT, "results", "oos_size_only_results.json")
    out = json.load(io.open(p, encoding="utf-8"))
    ref = json.load(io.open(os.path.join(ROOT, "results", "oos_validation_results.json"), encoding="utf-8"))
    for k in ("held_out_ELPD_composition_model", "held_out_ELPD_naive_pool",
              "size_only_minus_composition_model", "size_only_minus_naive_pool"):
        assert k in out, "%s not in the committed result: rerun src/oos_size_only.py" % k
    assert out["held_out_ELPD_composition_model"] == pytest.approx(ref["held_out_ELPD_model"])
    assert out["size_only_minus_composition_model"] == pytest.approx(out["held_out_ELPD"] - ref["held_out_ELPD_model"])
    assert out["size_only_minus_naive_pool"] == pytest.approx(out["held_out_ELPD"] - ref["held_out_ELPD_naive"])
