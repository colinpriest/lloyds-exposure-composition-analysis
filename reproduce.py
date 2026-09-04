#!/usr/bin/env python3
"""Regenerate the analysis behind the manuscript, in order, from a clean checkout.

    python reproduce.py --list      what would run, and roughly how long
    python reproduce.py --check     environment and inputs only, no fitting
    python reproduce.py             run everything
    python reproduce.py --only calibration
    python reproduce.py --only checks

Why this exists. The cover letter said a clean checkout reproduces the figures and
tables. It could not: requirements.txt named numpy, matplotlib and openpyxl while the
headline calibration needs PyMC, ArviZ, PyTensor and SciPy, and the README documented a
few individual commands with no end-to-end route. The claim was made about a repository
nobody had tried to reproduce from scratch.

What it does NOT do. It does not re-run the PDF extraction: that needs the source
reports and paid LLM API access, and its output is committed as
model/exposure_results.json. Everything downstream of that file is RE-RUNNABLE from
this checkout through the manifest below; what has been DEMONSTRATED is the recorded
clean run, which is deliberately partial (--verify prints its exact coverage), and
the remaining stages have not been run end to end in one pass.

Verification. --verify validates the committed run report against HISTORY (dirty
recorded runs rejected; every recorded hash checked against the blob at the recorded
commit), and additionally, when a local run stamp exists, compares that run's declared
outputs with HEAD. It reports only on a run actually recorded, and says
whether that run was partial. It used to compare the working tree with HEAD and nothing
else, which on a clean checkout meant it reported success without regenerating anything.

Determinism, stated accurately. Every fitting script sets its own seed, and the fitted
quantities reproduce exactly: calibrate_dispersion_ritc.py reproduces
model/dispersion_calibration_ritc.json and its 6,000-draw npz byte for byte. Two
outputs also record `runtime_seconds`, which is wall-clock and obviously varies, so a
plain `git status` after a run shows them as modified even though every number in them
is identical. --verify compares the outputs ignoring that field, so the check reports
what actually matters rather than sending a reader chasing a timing difference.
"""
import argparse
import importlib
import io
import json
import os
import re
import shlex
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "src")

REQUIRED = ("numpy", "scipy", "matplotlib", "openpyxl", "pymc", "arviz",
            "pytensor", "numba")
SUPPORTED_PYTHON = "3.12.6"
INPUTS = ("model/exposure_results.json", "pdf_extraction/ritc_scan.json",
          "distortion_tool.html", "vignettes/vignette-2/target_transition.json")

# (script, stage, rough minutes). The calibration must precede the checks: several read
# model/dispersion_calibration_ritc.json as the published posterior to compare against.
STEPS = [
    # inputs: producers of the committed model/ inputs. fetch_h10_rates needs network
    # access to the Federal Reserve H.10 service; everything else is offline.
    ("fetch_h10_rates.py", "inputs", 1),
    ("build_maturity_share.py", "inputs", 2),

    ("calibrate_dispersion.py", "calibration", 2),
    ("calibrate_dispersion_ritc.py", "calibration", 2),
    ("calibrate_dispersion_systemic.py", "calibration", 3),
    ("calibrate_dispersion_hetscale.py", "calibration", 3),
    ("calibrate_dispersion_sizeloaded.py", "calibration", 3),

    ("check_k_unconstrained.py", "checks", 2),
    ("check_syndicate_random_effect.py", "checks", 4),
    ("check_mean_concentration_bayes.py", "checks", 12),
    ("check_ritc_scale_term.py", "checks", 4),
    ("check_vignette2_sign.py", "checks", 1),
    ("check_operator_properties.py", "checks", 1),
    ("check_fx_timing.py", "checks", 3),
    ("check_size_maturity.py", "checks", 4),
    ("check_maturity_denominator.py", "checks", 3),
    ("check_missingness_sensitivity.py", "checks", 3),
    ("check_currency_entanglement.py", "checks", 4),
    ("check_pooling_cv_extended.py", "checks", 25),
    ("check_bayes_model_compare.py", "checks", 8),
    ("check_cv_clustered_se.py", "checks", 20),
    ("check_floor_large_syndicates.py", "checks", 8),
    ("check_large_book_slope_conditional.py", "checks", 5),
    ("check_pyd_temporal_correlation.py", "checks", 1),
    ("check_systemic_share.py", "checks", 1),
    ("check_tail_support_syndicate.py", "checks", 2),

    # producers previously ABSENT from the manifest although their committed outputs
    # are cited by the manuscript -- a review found six of these; a full scan of
    # src/ write-targets found twenty-five
    ("missingness_check.py", "checks", 1),
    ("systemic_correlation_check.py", "checks", 2),
    ("systemic_ppc.py", "checks", 4),
    ("donor_review.py", "checks", 1),
    ("check_pooling_cv.py", "checks", 25),
    ("check_gamma0_vignette.py", "checks", 3),
    ("check_large_book_flattening.py", "checks", 4),
    ("check_large_book_slope.py", "checks", 3),
    ("check_large_book_slope_bayes.py", "checks", 6),
    ("check_mean_zero_boundary.py", "checks", 3),
    ("check_size_concentration_assoc.py", "checks", 1),
    ("pooling_compare.py", "checks", 12),
    ("oos_validation.py", "checks", 20),
    ("oos_size_only.py", "checks", 8),
    ("ritc_robustness.py", "checks", 10),
    ("ritc_shape_invariance.py", "checks", 5),
    ("ritc_tail_shape.py", "checks", 3),
    ("ritc_treatments.py", "checks", 8),
    ("fx_sensitivity.py", "checks", 8),
    ("proxy_stress.py", "checks", 6),
    ("worked_example_donor.py", "checks", 1),
    ("compose_robust.py", "checks", 1),
    ("proxy_stress_bayes.py", "checks", 30),

    # tail analyses: these produce paper results and were missing from the manifest,
    # so a "complete" run did not in fact regenerate the GPD table
    ("vignette_uncertainty.py", "tails", 6),
    ("vignette1_diagnostics.py", "tails", 2),
    ("gpd_var_uncertainty.py", "tails", 4),
    ("bayesian_gpd.py", "tails", 3),

    ("appendix_c_tail_comparison.py", "outputs", 2),
    ("run_analysis.py", "outputs", 5),
    # the four paper figures are generated from the fitted results, so a run that
    # leaves them as committed has not reproduced what the manuscript shows
    ("make_paper_figures.py", "outputs", 1),
    # the current-results document is generated, so it is part of the route
    ("build_current_results.py", "outputs", 1),
]


def check_readme_counts():
    """The README must not restate the manifest; --list is the authority.

    "the 22 scripts" and "~2.5 hours" were typed once and drifted to 27 scripts and
    ~170 minutes. Prose duplicating a computed number goes stale silently, so this
    fails on any stated script count or run duration that disagrees with the manifest.
    """
    try:
        text = io.open(os.path.join(HERE, "README.md"), encoding="utf-8").read()
    except Exception:
        return []
    bad = []
    total_min = sum(m for _, _, m in STEPS)
    # "55 manifest scripts" and "fifty-five scripts" both slipped past the first
    # version of this check, which required digits immediately before the noun. A
    # count gate that only counts one spelling is not a count gate.
    words = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
             "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11,
             "twelve": 12, "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50,
             "sixty": 60}

    def _spelled(tok):
        parts = re.split(r"[- ]", tok.lower())
        if not parts or any(p not in words for p in parts):
            return None
        return sum(words[p] for p in parts)

    pattern = r"([\d]+|[A-Za-z]+(?:[- ][A-Za-z]+)?)\s+(?:\w+\s+)?scripts\b"
    for m in re.finditer(pattern, text):
        tok = m.group(1)
        n = int(tok) if tok.isdigit() else _spelled(tok)
        if n is None:
            continue
        if n != len(STEPS):
            bad.append("says %s scripts; the manifest holds %d" % (tok, len(STEPS)))
    for m in re.finditer(r"~\s*([\d.]+)\s*hours?\b", text):
        stated = float(m.group(1)) * 60.0
        if abs(stated - total_min) > 0.25 * total_min:
            bad.append("says ~%s hours; the manifest totals ~%d minutes"
                       % (m.group(1), total_min))
    return bad


TESTS_RECORD = "tests-run-report.json"


def check_test_counts():
    """A stated test count must come from the committed record, and the record must
    still describe this suite.

    "121 passed, 14 skipped" was typed into the README and the manuscript checklist
    after a run; a test added the same day made it 122 before either was read. So the
    count is stamped by src/record_tests.py, and two things are checked here: that
    nothing states a different number, and that the suite has not changed size since
    the record was written. The second half matters more -- a record nothing revalidates
    goes stale exactly the way the prose did."""
    path = os.path.join(HERE, TESTS_RECORD)
    try:
        rec = json.load(io.open(path, encoding="utf-8"))
    except Exception:
        return ["%s is missing or unreadable; run python src/record_tests.py"
                % TESTS_RECORD]
    bad = []
    if rec.get("failed"):
        bad.append("the recorded run had %d failing test(s)" % rec["failed"])
    try:
        text = io.open(os.path.join(HERE, "README.md"), encoding="utf-8").read()
    except Exception:
        text = ""
    for m in re.finditer(r"(\d+) passed, (\d+) skipped", text):
        if (int(m.group(1)), int(m.group(2))) != (rec.get("passed"), rec.get("skipped")):
            bad.append("README says %s but the record holds %s passed, %s skipped"
                       % (m.group(0), rec.get("passed"), rec.get("skipped")))
    r = subprocess.run([sys.executable, "-m", "pytest", "--collect-only", "-q"],
                       cwd=HERE, capture_output=True, text=True)
    m = re.search(r"(\d+)\s+tests? collected", (r.stdout or "") + (r.stderr or ""))
    if not m:
        bad.append("could not collect the suite to check the record is current")
    elif int(m.group(1)) != rec.get("collected"):
        bad.append("the suite now collects %s test(s); the record was written at %s "
                   "-- rerun python src/record_tests.py"
                   % (m.group(1), rec.get("collected")))
    return bad


MANUAL_ASSETS = ("figures/project-infographic.png",)


def check_manifest_completeness():
    """Every tracked artifact under model/, results/ and figures/ must have a
    manifest producer, and every manifest step must declare its outputs. Six absent
    producers were reported in review; a full scan found twenty-five."""
    bad = []
    for sc, _, _ in STEPS:
        if sc not in OUTPUTS:
            bad.append("step %s declares no outputs" % sc)
    produced = {rel for outs in OUTPUTS.values() for rel in outs}
    r = subprocess.run(["git", "-C", HERE, "ls-files", "model", "results",
                        "figures"], capture_output=True, text=True)
    for rel in r.stdout.split():
        rel = rel.replace("\\", "/")
        if rel in MANUAL_ASSETS or rel.endswith(".xlsx"):
            continue
        if rel not in produced:
            bad.append("tracked artifact %s has no manifest producer" % rel)
    return bad


def _direct_reference_error(requirement, distribution):
    """Return an error when an installed direct reference differs from the lock."""
    try:
        direct = json.loads(distribution.read_text("direct_url.json") or "{}")
    except (TypeError, ValueError):
        direct = {}
    if not direct:
        return "installed distribution has no direct_url.json provenance"

    expected = requirement.url
    if expected.startswith("git+"):
        vcs, expected_ref = expected.split("+", 1)
        expected_url, separator, revision = expected_ref.rpartition("@")
        if not separator:
            expected_url, revision = expected_ref, ""
        vcs_info = direct.get("vcs_info", {})
        if vcs_info.get("vcs") != vcs:
            return "expected %s VCS provenance, got %s" % (
                vcs, vcs_info.get("vcs", "none"))
        if direct.get("url", "").rstrip("/") != expected_url.rstrip("/"):
            return "direct VCS URL differs from lock"
        installed_revision = (vcs_info.get("commit_id") or
                              vcs_info.get("requested_revision") or "")
        if revision and installed_revision != revision:
            return "VCS revision %s differs from locked %s" % (
                installed_revision or "unknown", revision)
        return None

    from urllib.parse import urldefrag
    expected_url, fragment = urldefrag(expected)
    if direct.get("url", "").rstrip("/") != expected_url.rstrip("/"):
        return "direct URL differs from lock"
    if fragment:
        algorithm, separator, digest = fragment.partition("=")
        hashes = direct.get("archive_info", {}).get("hashes", {})
        installed_digest = hashes.get(algorithm)
        if separator and installed_digest != digest:
            return "direct URL %s hash differs from lock" % algorithm
    return None


def _extra_errors(requirement, distribution, distribution_getter):
    """Validate requested extras and the dependencies activated by each extra."""
    from packaging.requirements import InvalidRequirement, Requirement
    from packaging.utils import canonicalize_name

    errors = []
    provided = {canonicalize_name(extra) for extra in
                (distribution.metadata.get_all("Provides-Extra") or [])}
    for extra in requirement.extras:
        if canonicalize_name(extra) not in provided:
            errors.append("requested extra %s is not provided" % extra)
            continue
        for dependency_text in distribution.requires or []:
            try:
                dependency = Requirement(dependency_text)
            except InvalidRequirement as exc:
                errors.append("extra %s has invalid dependency metadata: %s" %
                              (extra, exc))
                continue
            if (not dependency.marker or
                    not dependency.marker.evaluate({"extra": extra})):
                continue
            try:
                installed = distribution_getter(dependency.name)
            except Exception:
                errors.append("extra %s requires %s, which is not installed" %
                              (extra, dependency.name))
                continue
            if dependency.url:
                error = _direct_reference_error(dependency, installed)
                if error:
                    errors.append("extra %s dependency %s: %s" %
                                  (extra, dependency.name, error))
            elif installed.version not in dependency.specifier:
                errors.append("extra %s requires %s%s but %s is installed" %
                              (extra, dependency.name, dependency.specifier,
                               installed.version))
    return errors


def check_environment_lock():
    """Enforce Python and every PEP 508 requirement in requirements.lock."""
    import importlib.metadata as _md
    from packaging.requirements import InvalidRequirement, Requirement

    lock = os.path.join(HERE, "requirements.lock")
    if not os.path.exists(lock):
        return ["requirements.lock missing"]
    bad = []
    running_python = ".".join(str(v) for v in sys.version_info[:3])
    if running_python != SUPPORTED_PYTHON:
        bad.append("Python locked at %s but %s is running" %
                   (SUPPORTED_PYTHON, running_python))
    for line_number, line in enumerate(io.open(lock, encoding="utf-8"), 1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        try:
            requirement = Requirement(line)
        except InvalidRequirement as exc:
            bad.append("requirements.lock:%d is invalid: %s" % (line_number, exc))
            continue
        if requirement.marker and not requirement.marker.evaluate():
            continue
        try:
            distribution = _md.distribution(requirement.name)
        except Exception:
            bad.append("%s is locked but not installed" % requirement.name)
            continue
        for error in _extra_errors(requirement, distribution, _md.distribution):
            bad.append("%s: %s" % (requirement.name, error))
        if requirement.url:
            error = _direct_reference_error(requirement, distribution)
            if error:
                bad.append("%s: %s" % (requirement.name, error))
        elif distribution.version not in requirement.specifier:
            bad.append("%s locked at %s but %s installed" %
                       (requirement.name, requirement.specifier, distribution.version))
    return bad


def check_environment():
    missing = []
    for mod in REQUIRED:
        try:
            importlib.import_module(mod)
        except Exception:
            missing.append(mod)
    absent = [p for p in INPUTS if not os.path.exists(os.path.join(HERE, p))]
    for mod in REQUIRED:
        mark = "missing" if mod in missing else "ok"
        print("  %-12s %s" % (mod, mark))
    for p in INPUTS:
        print("  %-46s %s" % (p, "missing" if p in absent else "ok"))
    if missing:
        print("\ninstall the locked environment first:  "
              "python -m pip install -r requirements.lock")
    if absent:
        print("\ninputs missing; these are committed, so the checkout is incomplete")
    return not (missing or absent)


def run(steps):
    total = sum(m for _, _, m in steps)
    print("%d script(s), roughly %d minutes on a machine without a C++ toolchain\n"
          % (len(steps), total))
    failed = []
    for i, (script, stage, mins) in enumerate(steps, 1):
        path = os.path.join(SRC, script)
        if not os.path.exists(path):
            print("[%2d/%2d] %-42s SKIP (not present)" % (i, len(steps), script))
            continue
        t0 = time.time()
        r = subprocess.run([sys.executable, script], cwd=SRC,
                           stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                           text=True)
        took = time.time() - t0
        if r.returncode == 0:
            print("[%2d/%2d] %-42s ok    %5.1f min" % (i, len(steps), script, took / 60))
        else:
            failed.append(script)
            tail = (r.stderr or "").strip().splitlines()[-1:] or [""]
            print("[%2d/%2d] %-42s FAIL  %s" % (i, len(steps), script, tail[0][:70]))
    return failed


# Fields a rerun legitimately changes: wall-clock durations, the run timestamp and
# the retrieval time of the H.10 rates (copied into the exposure file). Nothing
# fitted is on this list.
VOLATILE = ("runtime_seconds", "analysis_timestamp", "retrieved_utc")
# Text outputs are compared with line endings normalised: the same content written
# on Windows carries CRLF while the committed blob is LF, and that is not a
# reproduction failure.
TEXT_OUTPUT_SUFFIXES = (".tex", ".csv", ".md", ".html", ".txt")


def output_bytes_for_hash(rel, data):
    if rel.endswith(TEXT_OUTPUT_SUFFIXES):
        return data.replace(b"\r\n", b"\n")
    return data

# Every manifest step's outputs, declared. --verify compares each declared output with
# the committed version: canonical JSON (only the documented VOLATILE fields excluded)
# for .json, byte-for-byte for anything else. The old verifier filtered `git diff` to
# .json, so a changed .npz was invisible -- while the cover letter claimed the
# 6,000-draw NPZ byte-identical. A claim the tooling cannot check is not a claim.
# run_analysis.py also writes figures and distortion_tool.html outside model|results;
# those are documented as outside this verification's scope.
OUTPUTS = {
    "calibrate_dispersion.py": ("model/dispersion_calibration.json",
                                "model/dispersion_posterior_draws.npz"),
    "calibrate_dispersion_ritc.py": ("model/dispersion_calibration_ritc.json",
                                     "model/dispersion_posterior_draws_ritc.npz"),
    "calibrate_dispersion_systemic.py": (
        "model/dispersion_calibration_systemic.json",
        "model/dispersion_posterior_draws_systemic.npz"),
    "calibrate_dispersion_hetscale.py": ("model/dispersion_calibration_hetscale.json",),
    "calibrate_dispersion_sizeloaded.py": (
        "model/dispersion_calibration_sizeloaded.json",),
    "check_k_unconstrained.py": ("results/check_k_unconstrained_results.json",),
    "check_syndicate_random_effect.py": (
        "results/check_syndicate_random_effect_results.json",),
    "check_mean_concentration_bayes.py": (
        "results/check_mean_concentration_bayes_results.json",),
    "check_ritc_scale_term.py": ("results/check_ritc_scale_term_results.json",),
    "check_vignette2_sign.py": ("results/check_vignette2_sign_results.json",),
    "check_operator_properties.py": ("results/check_operator_properties_results.json",),
    "check_fx_timing.py": ("results/check_fx_timing_results.json",),
    "check_size_maturity.py": ("results/check_size_maturity_results.json",),
    "check_maturity_denominator.py": (
        "results/check_maturity_denominator_results.json",),
    "check_missingness_sensitivity.py": (
        "results/check_missingness_sensitivity_results.json",),
    "check_currency_entanglement.py": (
        "results/check_currency_entanglement_results.json",),
    "check_pooling_cv_extended.py": ("results/check_pooling_cv_extended_results.json",),
    "check_bayes_model_compare.py": ("results/check_bayes_model_compare_results.json",),
    "check_cv_clustered_se.py": ("results/check_cv_clustered_se_results.json",),
    "check_floor_large_syndicates.py": (
        "results/check_floor_large_syndicates_results.json",),
    "check_large_book_slope_conditional.py": (
        "results/check_large_book_slope_conditional_results.json",),
    "check_pyd_temporal_correlation.py": (
        "results/check_pyd_temporal_correlation_results.json",),
    "check_systemic_share.py": ("results/check_systemic_share_results.json",),
    "check_tail_support_syndicate.py": (
        "results/check_tail_support_syndicate_results.json",),
    "proxy_stress_bayes.py": ("results/proxy_stress_results.json",),
    "vignette_uncertainty.py": ("results/vignette_uncertainty_results.json",),
    "vignette1_diagnostics.py": ("results/vignette1_diagnostics_results.json",),
    "gpd_var_uncertainty.py": ("results/gpd_var_uncertainty_results.json",),
    "bayesian_gpd.py": ("results/bayesian_gpd_results.json",),
    "fetch_h10_rates.py": ("model/fx_rates_h10.json",),
    "build_maturity_share.py": ("model/maturity_share.json",),
    "missingness_check.py": ("results/missingness_check_results.json",
                             "results/missing_filings_worklist.csv"),
    "systemic_correlation_check.py": (
        "results/systemic_correlation_check_results.json",),
    "systemic_ppc.py": ("results/systemic_ppc_results.json",
                        "figures/systemic_correlation_profile.pdf",
                        "figures/systemic_correlation_profile.png"),
    "donor_review.py": ("results/donor_review_results.json",),
    "check_pooling_cv.py": ("results/check_pooling_cv_results.json",),
    "check_gamma0_vignette.py": ("results/check_gamma0_vignette_results.json",),
    "check_large_book_flattening.py": (
        "results/check_large_book_flattening_results.json",),
    "check_large_book_slope.py": ("results/check_large_book_slope_results.json",),
    "check_large_book_slope_bayes.py": (
        "results/check_large_book_slope_bayes_results.json",),
    "check_mean_zero_boundary.py": (
        "results/check_mean_zero_boundary_results.json",),
    "check_size_concentration_assoc.py": (
        "results/check_size_concentration_assoc_results.json",),
    "pooling_compare.py": ("results/pooling_compare_results.json",),
    "oos_validation.py": ("results/oos_validation_results.json",),
    "oos_size_only.py": ("results/oos_size_only_results.json",),
    "ritc_robustness.py": ("results/ritc_robustness_results.json",),
    "ritc_shape_invariance.py": ("results/ritc_shape_invariance_results.json",),
    "ritc_tail_shape.py": ("results/ritc_tail_shape_results.json",),
    "ritc_treatments.py": ("results/ritc_treatments_results.json",),
    "fx_sensitivity.py": ("results/fx_sensitivity_results.json",),
    "proxy_stress.py": ("results/proxy_stress_mle_results.json",),
    "worked_example_donor.py": ("results/worked_example_donors.json",),
    "compose_robust.py": ("results/compose_robust_results.json",),
    "appendix_c_tail_comparison.py": ("figures/appendix_c_tail_comparison.tex",
                                      "figures/appendix_c_tail_comparison.pdf",
                                      "figures/appendix_c_tail_comparison.png"),
    # run_analysis also writes per-run figure packs and vignette workings outside the
    # tracked model/results/figures trees; its TRACKED artifacts are these two
    "run_analysis.py": ("model/exposure_results.json", "distortion_tool.html"),
    "make_paper_figures.py": ("paper_pack/fig_corpus_coverage.pdf", "paper_pack/fig_size_dispersion.pdf",
                              "paper_pack/fig_hhi_dispersion.pdf", "paper_pack/fig_goodness_of_fit.pdf",
                              "results/goodness_of_fit_results.json"),
    "build_current_results.py": ("docs/current-results.md",),
}
REPORT = os.path.join(HERE, "reproduce-run-report.json")


def sha256_file(path, rel=None):
    """SHA-256 of the file; text outputs (by rel suffix) with line endings normalised."""
    import hashlib
    with open(path, "rb") as fh:
        data = fh.read()
    if rel is not None:
        data = output_bytes_for_hash(rel, data)
    return hashlib.sha256(data).hexdigest()


def canonical_json_sha256(raw_bytes):
    """SHA-256 of the JSON content with the documented volatile fields removed and
    keys sorted -- the hash of what --verify actually compares for .json outputs."""
    import hashlib
    obj = _strip_volatile(json.loads(raw_bytes.decode("utf-8")))
    canon = json.dumps(obj, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(canon).hexdigest()


def committed_bytes(rel):
    """The committed version of rel, or None if not tracked at HEAD."""
    r = subprocess.run(["git", "-C", HERE, "show", "HEAD:" + rel],
                       capture_output=True)
    return r.stdout if r.returncode == 0 else None


def _strip_volatile(obj):
    if isinstance(obj, dict):
        return {k: _strip_volatile(v) for k, v in obj.items() if k not in VOLATILE}
    if isinstance(obj, list):
        return [_strip_volatile(v) for v in obj]
    return obj


def output_matches(rel):
    """(status, detail) for one declared output against its committed version.

    status: 'byte-identical' | 'identical-excluding-volatile' | 'MISSING'
            | 'UNTRACKED' | 'DIFFERS'
    """
    path = os.path.join(HERE, rel)
    if not os.path.exists(path):
        return "MISSING", "declared output not on disk"
    blob = committed_bytes(rel)
    if blob is None:
        return "UNTRACKED", "declared output not committed at HEAD"
    with open(path, "rb") as fh:
        cur = fh.read()
    cur, blob = output_bytes_for_hash(rel, cur), output_bytes_for_hash(rel, blob)
    if cur == blob:
        return "byte-identical", ""
    if rel.endswith(".json"):
        try:
            a = _strip_volatile(json.loads(cur.decode("utf-8")))
            b = _strip_volatile(json.loads(blob.decode("utf-8")))
        except Exception as e:
            return "DIFFERS", "unparseable JSON (%s)" % e
        if a == b:
            return "identical-excluding-volatile", ",".join(VOLATILE)
        return "DIFFERS", "fitted content differs after excluding volatile fields"
    return "DIFFERS", "binary content differs"


STAMP = os.path.join(HERE, ".reproduce-run.json")


def write_stamp(ran, failed):
    """Record which scripts actually ran, so --verify cannot report on nothing."""
    io.open(STAMP, "w", encoding="utf-8").write(json.dumps(
        {"ran": ran, "failed": failed, "manifest_size": len(STEPS)}, indent=2))


def read_stamp():
    try:
        return json.load(io.open(STAMP, encoding="utf-8"))
    except Exception:
        return None


def validate_report(rep):
    """Check the committed run report AGAINST HISTORY, not the worktree against
    itself. Returns (ok, messages).

    The first report was recorded and then never read for anything but script names:
    its commit, dirty flag and hashes made no difference to --verify, so a clean
    clone 'verified' by comparing its own untouched outputs with its own HEAD. Every
    recorded fact is consequential: command determines scripts, scripts determine the
    exact output set, and each output hash must match the blob at the recorded commit.
    """
    msgs = []
    if rep.get("schema", 1) < 3:
        return False, ["report schema %s predates complete relationship checks; rerun the "
                       "recorded pass" % rep.get("schema")]
    if rep.get("worktree_dirty_src") is not False:
        return False, ["recorded run had a DIRTY source tree; a dirty run "
                       "establishes nothing about the committed code -- rerun from "
                       "a clean checkout"]
    ok = True
    if rep.get("manifest_size") != len(STEPS):
        ok = False
        msgs.append("manifest_size is %r, expected %d" %
                    (rep.get("manifest_size"), len(STEPS)))

    command = rep.get("command")
    expected_scripts = None
    if not isinstance(command, str):
        ok = False
        msgs.append("command is missing or is not text")
    else:
        try:
            command_parts = shlex.split(command, posix=False)
        except ValueError as exc:
            command_parts = []
            ok = False
            msgs.append("command is invalid: %s" % exc)
        if command_parts and os.path.basename(command_parts[0]).lower() == "reproduce.py":
            arguments = command_parts[1:]
            if not arguments:
                expected_scripts = [script for script, _, _ in STEPS]
            elif (len(arguments) == 2 and arguments[0] == "--only" and
                  arguments[1] in {stage for _, stage, _ in STEPS}):
                expected_scripts = [script for script, stage, _ in STEPS
                                    if stage == arguments[1]]
            else:
                ok = False
                msgs.append("command does not describe a full or --only stage run")
        elif command_parts:
            ok = False
            msgs.append("command must start with reproduce.py")

    scripts = rep.get("scripts")
    if not isinstance(scripts, dict):
        ok = False
        msgs.append("scripts must be an object")
        scripts = {}
    known_scripts = {script for script, _, _ in STEPS}
    unknown_scripts = set(scripts) - known_scripts
    if unknown_scripts:
        ok = False
        msgs.append("unknown script(s): %s" % ", ".join(sorted(unknown_scripts)))
    if expected_scripts is not None and set(scripts) != set(expected_scripts):
        ok = False
        missing = set(expected_scripts) - set(scripts)
        extra = set(scripts) - set(expected_scripts)
        msgs.append("script set disagrees with command (missing: %s; extra: %s)" %
                    (", ".join(sorted(missing)) or "none",
                     ", ".join(sorted(extra)) or "none"))
    failed_scripts = [script for script, meta in scripts.items()
                      if not isinstance(meta, dict) or meta.get("status") != "ok"]
    if failed_scripts:
        ok = False
        msgs.append("script(s) not recorded successful: %s" %
                    ", ".join(sorted(failed_scripts)))

    expected_outputs = {rel for script in scripts for rel in OUTPUTS.get(script, ())}
    outputs = rep.get("outputs")
    if not isinstance(outputs, dict):
        ok = False
        msgs.append("outputs must be an object")
        outputs = {}
    if set(outputs) != expected_outputs:
        ok = False
        missing = expected_outputs - set(outputs)
        extra = set(outputs) - expected_outputs
        msgs.append("output set disagrees with scripts (missing: %s; extra: %s)" %
                    (", ".join(sorted(missing)) or "none",
                     ", ".join(sorted(extra)) or "none"))

    expected_partial = len(scripts) < len(STEPS)
    if rep.get("partial") is not expected_partial:
        ok = False
        msgs.append("partial is %r, expected %r from the script set" %
                    (rep.get("partial"), expected_partial))

    environment = rep.get("environment")
    if not isinstance(environment, dict):
        ok = False
        msgs.append("environment must be an object")
        environment = {}
    if rep.get("python") != SUPPORTED_PYTHON:
        ok = False
        msgs.append("top-level Python is %r, expected %s" %
                    (rep.get("python"), SUPPORTED_PYTHON))
    if environment.get("python") != rep.get("python"):
        ok = False
        msgs.append("environment Python disagrees with top-level Python")
    missing_environment = [name for name in REQUIRED
                           if environment.get(name) in (None, "absent")]
    if missing_environment:
        ok = False
        msgs.append("environment omits material package(s): %s" %
                    ", ".join(missing_environment))
    if not isinstance(rep.get("platform"), str) or not rep.get("platform"):
        ok = False
        msgs.append("platform is missing")
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z",
                        rep.get("finished_utc", "")):
        ok = False
        msgs.append("finished_utc is missing or malformed")
    if rep.get("volatile_json_fields_excluded_by_verify") != list(VOLATILE):
        ok = False
        msgs.append("volatile JSON field declaration disagrees with verifier")

    commit = rep.get("commit", "")
    r = subprocess.run(["git", "-C", HERE, "cat-file", "-e", commit + "^{commit}"],
                       capture_output=True)
    if r.returncode != 0:
        return False, ["recorded commit %s does not resolve" % commit[:12]]
    import hashlib
    for rel, meta in outputs.items():
        b = subprocess.run(["git", "-C", HERE, "show", "%s:%s" % (commit, rel)],
                           capture_output=True)
        if b.returncode != 0:
            ok = False
            msgs.append("%s: not present at recorded commit" % rel)
            continue
        if rel.endswith(".json"):
            want = meta.get("canonical_sha256")
            got = canonical_json_sha256(b.stdout)
            if want != got:
                ok = False
                msgs.append("%s: canonical content differs from the recorded run"
                            % rel)
        else:
            if hashlib.sha256(output_bytes_for_hash(rel, b.stdout)).hexdigest() != meta.get("sha256"):
                ok = False
                msgs.append("%s: bytes differ from the recorded run" % rel)
    if ok:
        msgs.append("report valid: clean-tree run at %s; %d output hash(es) match "
                    "the blobs at that commit" % (commit[:12],
                                                   len(outputs)))
    return ok, msgs


def verify():
    """Compare every output DECLARED by the recorded run against the committed tree.

    Fails on: no recorded run; a declared output missing, untracked, or differing
    (canonical JSON with only VOLATILE fields excluded; byte comparison otherwise);
    or any OTHER tracked file under model/ or results/ changed without a ran script
    declaring it. The old verifier filtered to .json and could not see a changed
    .npz; this one checks exactly what the manifest declares, and nothing passes by
    being outside the filter.
    """
    stamp = read_stamp()
    report = None
    try:
        report = json.load(io.open(REPORT, encoding="utf-8"))
    except Exception:
        pass
    if not stamp and not report:
        print("\nverify: nothing to verify -- no run is recorded in this checkout"
              " (no local stamp and no committed reproduce-run-report.json).\n"
              "         Run `python reproduce.py` (or --only <stage>) first.")
        return False
    report_ok = True
    if report:
        report_ok, rmsgs = validate_report(report)
        print("\nverify: committed run report:")
        for m in rmsgs:
            print("verify:   %s%s" % ("" if report_ok else "*** ", m))
    # The coverage census is printed on BOTH paths, before any verdict. The
    # clean-clone path used to print "verdict rests on the committed report alone"
    # and then PASS: a reader was told the report was valid without being told it
    # covers five scripts of fifty-five, while the README claimed --verify
    # "identifies it as partial". A verdict without its coverage is the same
    # over-claim as a reproduction claim without its scope.
    total = len(STEPS)
    if stamp:
        ran = stamp.get("ran") or []
        src_of = "local stamp"
    else:
        ran = sorted((report or {}).get("scripts") or {})
        src_of = "committed run report"
    partial = len(ran) < total
    print("\nverify: %d of %d manifest scripts recorded as run (%s)"
          % (len(ran), total, src_of))
    if partial:
        print("verify: PARTIAL. The outputs of the other %d script(s) are the "
              "committed ones\n        and are not evidence of reproduction."
              % (total - len(ran)))

    if not stamp:
        # a clean clone: the ONLY evidence is the report, validated against history
        # above. Comparing this untouched tree with its own HEAD would prove nothing,
        # so no output comparison is run here.
        print("verify: no local run in this checkout; verdict rests on the "
              "committed report alone")
        print("verify: %s%s" % ("PASS" if report_ok else "FAIL",
                                " (PARTIAL run)" if partial else ""))
        return report_ok

    ok = True
    n_byte, n_canon = 0, 0
    declared = set()
    for sc in ran:
        for rel in OUTPUTS.get(sc, ()):
            declared.add(rel)
            status, detail = output_matches(rel)
            if status == "byte-identical":
                n_byte += 1
            elif status == "identical-excluding-volatile":
                n_canon += 1
                print("verify: %-52s identical excluding %s" % (rel, detail))
            else:
                ok = False
                print("verify: *** %-48s %s (%s)" % (rel, status, detail))
    print("verify: %d output(s) byte-identical; %d identical after excluding the "
          "documented\n        volatile field(s)" % (n_byte, n_canon))

    r = subprocess.run(["git", "-C", HERE, "status", "--porcelain", "--",
                        "model", "results"], capture_output=True, text=True)
    for line in r.stdout.splitlines():
        rel = line[3:].strip().replace("\\", "/")
        if rel and rel not in declared:
            ok = False
            print("verify: *** %-48s changed but not declared by any ran script"
                  % rel)
    ok = ok and report_ok
    print("verify: %s%s" % ("PASS" if ok else "FAIL",
                            " (PARTIAL run)" if partial else ""))
    return ok


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--only", choices=("inputs", "calibration", "checks", "tails", "outputs"))
    ap.add_argument("--verify", action="store_true",
                    help="compare regenerated outputs against the committed ones, "
                         "ignoring recorded wall-clock timings")
    a = ap.parse_args()

    steps = [s for s in STEPS if not a.only or s[1] == a.only]

    if a.list:
        for script, stage, mins in steps:
            print("  %-10s %-42s ~%2d min" % (stage, script, mins))
        print("\n  total ~%d minutes" % sum(m for _, _, m in steps))
        return 0

    if a.verify:
        # verify what is already on disk; do NOT re-run the pipeline. Without this the
        # flag triggered a 2.5-hour run before reporting, which is not what "verify"
        # means to anyone reading the help text.
        return 0 if verify() else 1

    print("environment and inputs:")
    ok = check_environment()
    for msg in check_manifest_completeness():
        print("  manifest *** %s" % msg)
        ok = False
    for msg in check_environment_lock():
        print("  lock *** %s" % msg)
        ok = False
    for msg in check_readme_counts():
        print("  README *** %s" % msg)
        ok = False
    # The test-count record is evidence for a documentation claim, not an input to
    # reproduction. Under --check it is fatal like everything else; in a run it is a
    # note, because otherwise a stale record blocks the very run whose report the
    # record depends on -- a deadlock this hit the moment the manifest gained a step.
    for msg in check_test_counts():
        print("  tests %s %s" % ("***" if a.check else "note:", msg))
        if a.check:
            ok = False
    if a.check:
        return 0 if ok else 1
    if not ok:
        return 1

    print()
    failed = run(steps)
    ran_ok = [sc for sc, _, _ in steps if sc not in failed]
    write_stamp(ran_ok, failed)
    # the durable, COMMITTED record of this pass: the gitignored stamp cannot be
    # audited from a clean clone, so the claim it supported was unfalsifiable there
    import datetime
    import platform as _pf
    rc = subprocess.run(["git", "-C", HERE, "rev-parse", "HEAD"],
                        capture_output=True, text=True)
    dirty = subprocess.run(["git", "-C", HERE, "status", "--porcelain",
                            "--", "src", "reproduce.py"],
                           capture_output=True, text=True).stdout.strip()
    outs = {}
    for sc in ran_ok:
        for rel in OUTPUTS.get(sc, ()):
            p = os.path.join(HERE, rel)
            if os.path.exists(p):
                entry = {"sha256": sha256_file(p, rel), "bytes": os.path.getsize(p)}
                if rel.endswith(".json"):
                    with open(p, "rb") as fh:
                        entry["canonical_sha256"] = canonical_json_sha256(fh.read())
                outs[rel] = entry
    import importlib.metadata as _md
    env = {"python": sys.version.split()[0]}
    for pkg in REQUIRED:
        try:
            env[pkg] = _md.version(pkg)
        except Exception:
            env[pkg] = "absent"
    io.open(REPORT, "w", encoding="utf-8", newline="\n").write(json.dumps({
        "schema": 3,
        "environment": env,
        "commit": rc.stdout.strip(),
        "worktree_dirty_src": bool(dirty),
        "command": " ".join(sys.argv),
        "finished_utc": datetime.datetime.now(datetime.timezone.utc)
                        .strftime("%Y-%m-%dT%H:%M:%SZ"),
        "platform": _pf.platform(),
        "python": sys.version.split()[0],
        "manifest_size": len(STEPS),
        "partial": len(steps) < len(STEPS),
        "scripts": {sc: {"status": "failed" if sc in failed else "ok"}
                    for sc, _, _ in steps},
        "outputs": outs,
        "volatile_json_fields_excluded_by_verify": list(VOLATILE),
    }, indent=2) + "\n")
    print("\nrun report written to reproduce-run-report.json (commit this file: it "
          "is the\ndurable record --verify and the cover letter refer to)")
    n_json = len([f for f in os.listdir(os.path.join(HERE, "results"))
                  if f.endswith(".json")])
    print("\nresults/*.json now present: %d" % n_json)
    if failed:
        print("failed: %s" % ", ".join(failed))
        return 1
    if verify() and not failed:
        print("done. Outputs match the committed files.")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
