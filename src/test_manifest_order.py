"""The manifest must be ordered by its data dependencies.

Round 52: the calibrations read model/exposure_results.json, which run_analysis.py
produced at step 55 of 58, so a rerun after the extraction records changed fitted
every model on the previous sample.  The check is general: every artefact path a
step's source mentions that some manifest step declares as an output must be
declared by that step itself or by an earlier one.  Reading a later step's output is
a dependency inversion whatever the file.
"""
import io
import os
import re
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
import reproduce  # noqa: E402

PATH_RE = re.compile(r"(?:model|results|paper_pack|figures|vignettes|docs)/[A-Za-z0-9_./-]+\.(?:json|csv|npz|tex|pdf|png|md|html)")
# a filename mentioned as a plain literal (e.g. SCRIPT_DIR / "model" / "x.json")
PARTS_RE = re.compile(r'"(model|results|paper_pack|figures|vignettes|docs)"\s*/\s*"([A-Za-z0-9_.-]+)"(?:\s*/\s*"([A-Za-z0-9_.-]+)")?')


#: the declared outputs that sit at the repository's top level (no directory in their path)
_ALL_OUTPUTS = [rel for outs in reproduce.OUTPUTS.values() for rel in outs]
#: ... and whose file name no other declared output shares (README.md is the repository's and each vignette folder's, so a
#: mention of it names no one file)
ROOT_OUTPUTS = sorted({rel for rel in _ALL_OUTPUTS if "/" not in rel
                       and sum(1 for o in _ALL_OUTPUTS if os.path.basename(o) == rel) == 1})


def _mentioned_paths(script):
    with io.open(os.path.join(HERE, script), encoding="utf-8") as _fh:
        src = _fh.read()
    found = set(PATH_RE.findall(src))
    # an output at the repository's top level (distortion_tool.html) is named without a directory: a step that mentions it
    # reads or writes it, and the same rule applies. It was the hole through which four steps read the shipped tool before
    # run_analysis.py rewrote it (the verification of 26 October 2026, R1)
    for name in ROOT_OUTPUTS:
        if re.search(r"(?<![\w./-])" + re.escape(name) + r"(?![\w-])", src):
            found.add(name)
    for m in PARTS_RE.finditer(src):
        parts = [p for p in m.groups() if p]
        found.add("/".join(parts))
    return found


def _order():
    return [sc for sc, _, _ in reproduce.STEPS]


@pytest.mark.parametrize("script", _order())
def test_step_reads_only_earlier_outputs(script):
    order = _order()
    idx = order.index(script)
    producers = {}
    for sc, outs in reproduce.OUTPUTS.items():
        for rel in outs:
            producers.setdefault(rel, []).append(sc)
    later = []
    for rel in sorted(_mentioned_paths(script)):
        if rel not in producers or rel in reproduce.OUTPUTS.get(script, ()):
            continue
        if not any(order.index(p) < idx for p in producers[rel] if p in order):
            later.append("%s (produced by %s)" % (rel, ", ".join(producers[rel])))
    assert not later, "%s reads outputs of later steps: %s" % (script, "; ".join(later))


def test_loader_pass_precedes_every_calibration():
    order = _order()
    assert "build_working_sample.py" in order
    first = order.index("build_working_sample.py")
    for sc, stage, _ in reproduce.STEPS:
        if stage == "calibration":
            assert order.index(sc) > first, sc
    assert order.index("run_analysis.py") > max(order.index(sc) for sc, st, _ in reproduce.STEPS if st == "calibration")


def test_the_gamma_free_fit_follows_the_headline_calibration():
    """Option B (10 October 2026): calibrate_dispersion_ritc.py writes the gamma = 0 headline and the next step writes the
    gamma-free fit the overlay reads, both in the calibration stage, before any check reads either; the sensitivity that
    sets them side by side runs after the vignette record it checks against."""
    order = _order()
    stage = {sc: st for sc, st, _ in reproduce.STEPS}
    head, free = order.index("calibrate_dispersion_ritc.py"), order.index("calibrate_dispersion_ritc_gamma_free.py")
    assert free == head + 1 and stage["calibrate_dispersion_ritc_gamma_free.py"] == "calibration"
    assert reproduce.OUTPUTS["calibrate_dispersion_ritc_gamma_free.py"] == (
        "model/dispersion_calibration_ritc_gamma_free.json", "model/dispersion_posterior_draws_ritc_gamma_free.npz")
    assert order.index("check_gamma_free_fit.py") > order.index("check_gamma0_vignette.py")
    assert "check_gamma0_refit.py" not in order and "check_gamma0_refit.py" not in reproduce.OUTPUTS


def test_the_root_level_outputs_are_found_and_the_scan_sees_them():
    assert "distortion_tool.html" in ROOT_OUTPUTS
    assert ROOT_OUTPUTS, "no root-level output: the scan has lost its subject"


def test_a_step_that_names_a_later_steps_root_output_is_caught(tmp_path, monkeypatch):
    """The hole: the path regexes need a directory, so a top-level file like distortion_tool.html was invisible. A synthetic
    step that reads it before run_analysis.py writes it is now a dependency inversion."""
    fake = tmp_path / "fake_step.py"
    fake.write_text('html = (SCRIPT_DIR / "distortion_tool.html").read_text()\n', encoding="utf-8")
    monkeypatch.setattr(sys.modules[__name__], "HERE", str(tmp_path))
    assert "distortion_tool.html" in _mentioned_paths("fake_step.py")
    fake.write_text("x = 1  # nothing named here\n", encoding="utf-8")
    assert "distortion_tool.html" not in _mentioned_paths("fake_step.py")


def test_a_committed_input_that_a_later_step_writes_is_read_by_no_earlier_step():
    """reproduce.INPUTS are the files a clean checkout must hold. One that a step also writes (model/exposure_results.json,
    the loader step's output) is fine for a reader after that step, and for none before it."""
    order = _order()
    for rel in reproduce.INPUTS:
        writers = [sc for sc, outs in reproduce.OUTPUTS.items() if rel in outs and sc in order]
        if not writers:
            continue
        first = min(order.index(w) for w in writers)
        early = [sc for sc in order[:first] if rel in _mentioned_paths(sc) and sc not in writers]
        assert not early, "%s is written by %s but read earlier by %s" % (rel, writers, early)
