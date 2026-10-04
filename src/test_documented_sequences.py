"""Every documented sequence of analysis scripts runs in the manifest's order (the review of 2 October 2026, A-3).

The provenance note's fresh-clone recipe ran run_analysis.py once, before the calibration, so the tool, the paper
pack and the vignettes it wrote embedded the previous calibration; reproduce.py runs the loader before the fits and
again after them. Each code block or list item in the README and docs/ that names two or more `python src/<script>.py`
steps must name them in an order the manifest runs them. The loader pass before the fits is build_working_sample.py,
which runs run_analysis.py, so run_analysis.py may come both before and after the calibrations.

Run:  python -m pytest src/test_documented_sequences.py -q
"""
import glob
import io
import os
import re
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
import reproduce  # noqa: E402

STEP = re.compile(r"python src/([A-Za-z0-9_]+\.py)")


def manifest_order():
    order = []
    for script, _stage, _minutes in reproduce.STEPS:
        order += ["run_analysis.py"] if script == "build_working_sample.py" else []
        order.append(script)
    return order


def follows_manifest(seq, order=None):
    """Whether `seq` (scripts the manifest runs) is a subsequence of the manifest's order."""
    order = order or manifest_order()
    i = 0
    for script in seq:
        while i < len(order) and order[i] != script:
            i += 1
        if i == len(order):
            return False
        i += 1
    return True


def rebuilds_after_calibration(seq):
    """Whether a sequence that refits and then runs an outputs-stage script runs the loader after the last fit:
    the tool, the paper pack and the vignettes run_analysis.py writes embed the calibration present when it runs."""
    stage = {script: st for script, st, _m in reproduce.STEPS}
    fits = [i for i, s in enumerate(seq) if stage.get(s) == "calibration"]
    later = [i for i, s in enumerate(seq) if stage.get(s) == "outputs" and s != "run_analysis.py"]
    if not fits or not any(i > fits[-1] for i in later):
        return True
    return any(s == "run_analysis.py" and i > fits[-1] for i, s in enumerate(seq))


def documented_sequences():
    """(file, scripts) for each fenced code block, and each numbered list, naming two or more manifest scripts."""
    known = set(manifest_order())
    out = []
    for path in [os.path.join(HERE, "README.md")] + sorted(glob.glob(os.path.join(HERE, "docs", "*.md"))):
        text = io.open(path, encoding="utf-8").read()
        blocks = re.findall(r"```.*?```", text, re.S)
        blocks += re.findall(r"(?:^\d+\. .*\n(?:(?!\d+\. ).*\S.*\n)*)+", text, re.M)
        for block in blocks:
            seq = [s for s in STEP.findall(block) if s in known]
            if len(seq) >= 2:
                out.append((os.path.relpath(path, HERE), seq))
    return out


def test_the_manifest_order_check_refuses_a_calibration_after_its_only_loader_pass():
    assert follows_manifest(["run_analysis.py", "calibrate_dispersion_ritc.py", "run_analysis.py"])
    assert not follows_manifest(["calibrate_dispersion_ritc.py", "build_working_sample.py"])
    assert not follows_manifest(["generate_data_audit.py", "build_current_results.py"])


def test_a_refit_followed_by_outputs_without_a_second_loader_pass_is_refused():
    """The recipe the review found: the loader once, before the fit, then the tails and the data audit."""
    old = ["run_analysis.py", "calibrate_dispersion_ritc.py", "vignette_uncertainty.py", "gpd_var_uncertainty.py",
           "bayesian_gpd.py", "generate_data_audit.py"]
    assert follows_manifest(old) and not rebuilds_after_calibration(old)
    assert rebuilds_after_calibration(old[:5] + ["run_analysis.py", "generate_data_audit.py"])


def test_every_documented_sequence_runs_in_the_manifests_order():
    seqs = documented_sequences()
    assert len(seqs) >= 3, seqs
    wrong = [(f, s) for f, s in seqs if not (follows_manifest(s) and rebuilds_after_calibration(s))]
    assert wrong == []


def test_the_fresh_clone_recipe_runs_the_manifest():
    doc = io.open(os.path.join(HERE, "docs", "data-provenance.md"), encoding="utf-8").read()
    recipe = doc[doc.index("## 5. Reproducing from a fresh clone"):]
    assert "`python reproduce.py`" in recipe
    assert "python src/calibrate_dispersion_ritc.py" not in recipe


def test_the_readme_puts_the_reproducibility_boundary_at_the_records():
    """The review of 2 October 2026, A-8: the README called model/exposure_results.json the extraction's committed
    output; it is run_analysis.py's, from the record files the extraction wrote."""
    readme = " ".join(io.open(os.path.join(HERE, "README.md"), encoding="utf-8").read().split())
    assert "its output is committed as `model/exposure_results.json`" not in readme
    assert "its output is committed as the record files `pdf_extraction/syndicate_*.json`" in readme
    assert "model/exposure_results.json" in dict(reproduce.OUTPUTS)["run_analysis.py"]
