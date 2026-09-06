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


def _mentioned_paths(script):
    src = io.open(os.path.join(HERE, script), encoding="utf-8").read()
    found = set(PATH_RE.findall(src))
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
