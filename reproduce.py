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
this checkout through the manifest below; what has been DEMONSTRATED is whatever the
committed run report records, no more: --verify prints that run's exact coverage and
says whether it was partial or complete.

Verification. --verify validates the committed run report against HISTORY (dirty
recorded runs rejected; every recorded hash checked against the blob at the recorded
commit; the whole tree's inputs attested clean before the run and unchanged after it, and
their digest recomputed from the recorded commit), and additionally, when a local run stamp exists, compares that run's declared
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
import shutil
import subprocess
import sys
import tempfile
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
    # the loader pass: the calibrations read model/exposure_results.json, so the
    # sample must be rebuilt from the current records BEFORE they run; run_analysis.py
    # in the outputs stage refreshes the calibration-dependent blocks afterwards
    ("build_working_sample.py", "inputs", 1),

    ("calibrate_dispersion.py", "calibration", 2),
    ("calibrate_dispersion_ritc.py", "calibration", 2),
    ("calibrate_dispersion_systemic.py", "calibration", 3),
    ("calibrate_dispersion_hetscale.py", "calibration", 3),
    ("calibrate_dispersion_sizeloaded.py", "calibration", 3),

    ("check_syndicate_random_effect.py", "checks", 4),
    ("check_mean_concentration_bayes.py", "checks", 12),
    ("check_ritc_scale_term.py", "checks", 4),
    ("check_vignette2_sign.py", "checks", 1),
    ("check_operator_properties.py", "checks", 1),
    ("check_fx_timing.py", "checks", 3),
    ("check_size_maturity.py", "checks", 4),
    ("check_maturity_denominator.py", "checks", 3),
    ("check_cohort_scope.py", "checks", 4),
    ("audit_pyd_basis.py", "checks", 1),
    ("check_missingness_sensitivity.py", "checks", 3),
    ("check_currency_entanglement.py", "checks", 4),
    ("check_pooling_cv_extended.py", "checks", 20),
    ("check_bayes_model_compare.py", "checks", 8),
    ("check_cv_clustered_se.py", "checks", 20),
    ("check_floor_large_syndicates.py", "checks", 8),
    ("check_large_book_slope_conditional.py", "checks", 5),
    # two minutes, not one: the nulls' own size and power are measured on these year sets rather
    # than assumed, which is 40 simulated panels of permutations on top of the diagnostic
    ("check_pyd_temporal_correlation.py", "checks", 2),
    # the consequence of what the line above finds: eight short refits of the adopted model on
    # subsamples, which is why it costs minutes where the diagnostic itself costs two
    ("check_serial_sensitivity.py", "checks", 13),
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
    ("check_k_half_sensitivity.py", "checks", 4),
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
    ("check_long_tail_share.py", "checks", 15),
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
    # the Vignette 1 survivor figure (manuscript Figure 5) is generated from the
    # fitted operator too; it was outside the manifest until round 52, and shipped stale
    ("make_v1_ritc_survivor.py", "outputs", 1),
    # the current-results document is generated, so it is part of the route
    ("build_current_results.py", "outputs", 1),
    # so is the data-audit appendix: it quotes the loader's counts and the published
    # calibration, and outside the manifest a refit left it quoting the previous beta_RITC.
    # Its text names documents build_current_results.py writes, so it runs after that step
    ("generate_data_audit.py", "outputs", 1),
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

# Evidence archives: a study's record, not a pipeline output. results/extraction_error_rate/
# holds the extraction error-rate study (PLAN R163 and R213): its protocol, draws, readings,
# evidence packs, censuses, repairs and the scripts that ran, placed there by the owner's
# decision. No manifest step produces it. check_manifest_completeness therefore exempts a
# tracked file under an archive only if the archive's own MANIFEST.json lists it (or it is
# that manifest, its README or its .gitattributes), and check_evidence_archives requires
# every listed file to be tracked and to hold the bytes the manifest hashes, so the
# exemption cannot hide a file the archive does not account for.
EVIDENCE_ARCHIVES = ("results/extraction_error_rate/",)
ARCHIVE_OWN_FILES = ("MANIFEST.json", "README.md", ".gitattributes")


def _archive_manifest(prefix):
    """The file entries an evidence archive's MANIFEST.json lists, or None when the
    manifest cannot be read or its count disagrees with its list."""
    path = os.path.join(HERE, *prefix.strip("/").split("/"), "MANIFEST.json")
    try:
        manifest = json.load(io.open(path, encoding="utf-8"))
        files = manifest["files"]
        if manifest["count"] != len(files):
            return None
        return [dict(f, path=f["path"]) for f in files]
    except (OSError, ValueError, KeyError, TypeError):
        return None


def check_evidence_archives():
    """Every file an evidence archive's MANIFEST.json lists is tracked and holds the
    bytes the manifest hashes."""
    import hashlib
    bad = []
    for prefix in EVIDENCE_ARCHIVES:
        files = _archive_manifest(prefix)
        if files is None:
            bad.append("evidence archive %s has no readable MANIFEST.json" % prefix)
            continue
        r = subprocess.run(["git", "-C", HERE, "ls-files", prefix],
                           capture_output=True, text=True)
        tracked = {rel.replace("\\", "/") for rel in r.stdout.splitlines()}
        for f in files:
            rel = prefix + f["path"]
            if rel not in tracked:
                bad.append("%s is listed in %sMANIFEST.json but not tracked" % (rel, prefix))
                continue
            with open(os.path.join(HERE, *rel.split("/")), "rb") as fh:
                data = fh.read()
            if (len(data) != f.get("bytes")
                    or hashlib.sha256(data).hexdigest() != f.get("sha256")):
                bad.append("%s does not hold the bytes %sMANIFEST.json hashes"
                           % (rel, prefix))
    return bad


def check_manifest_completeness():
    """Every tracked artifact under model/, results/ and figures/ must have a
    manifest producer, and every manifest step must declare its outputs. Six absent
    producers were reported in review; a full scan found twenty-five. A file under an
    evidence archive needs no producer, but its archive's MANIFEST.json must list it
    (EVIDENCE_ARCHIVES)."""
    bad = []
    for sc, _, _ in STEPS:
        if sc not in OUTPUTS:
            bad.append("step %s declares no outputs" % sc)
    produced = {rel for outs in OUTPUTS.values() for rel in outs}
    archived = {}
    for prefix in EVIDENCE_ARCHIVES:
        files = _archive_manifest(prefix)
        archived[prefix] = (None if files is None
                            else {f["path"] for f in files} | set(ARCHIVE_OWN_FILES))
    r = subprocess.run(["git", "-C", HERE, "ls-files", "model", "results",
                        "figures"], capture_output=True, text=True)
    for rel in r.stdout.split():
        rel = rel.replace("\\", "/")
        prefix = next((p for p in EVIDENCE_ARCHIVES if rel.startswith(p)), None)
        if prefix is not None:
            if archived[prefix] is None or rel[len(prefix):] not in archived[prefix]:
                bad.append("tracked file %s is not listed in %sMANIFEST.json"
                           % (rel, prefix))
            continue
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
    toolchain = shutil.which("g++") or shutil.which("cl")
    if toolchain:
        # The committed outputs were produced with NO C++ toolchain: PyTensor runs the
        # scripts' pinned NUMBA backend and falls back to Python for the rest. With a
        # toolchain present PyTensor compiles those ops instead, and on the reference
        # machine that changed every posterior draw from the first (the posterior
        # means moved by about a fiftieth of a posterior SD). So a toolchain does not
        # break the manifest, but it does mean --verify will report the fitted
        # outputs as differing. Hide the compiler from PATH to reproduce bit for bit.
        print("\nC++ toolchain detected at %s: the committed results were produced "
              "without one, and with it the draws differ (means move by roughly a "
              "fiftieth of a posterior SD). Remove it from PATH to reproduce them "
              "bit for bit." % toolchain)
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
        # PyTensor's NUMBA backend writes about a thousand temporary source files per
        # compiled fit and never removes them; a %TEMP% that has collected them for
        # months creates files slowly (round 53: 1.49 million entries, 40 ms per file,
        # a fivefold slowdown of every fit). Each step gets its own directory, removed
        # when the step ends, so nothing accumulates anywhere.
        with tempfile.TemporaryDirectory(prefix="reproduce-") as step_tmp:
            env = dict(os.environ, TEMP=step_tmp, TMP=step_tmp, TMPDIR=step_tmp)
            r = subprocess.run([sys.executable, script], cwd=SRC, env=env,
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
VOLATILE = ("runtime_seconds", "analysis_timestamp", "retrieved_utc",
            # R221: the vignette metadata's record of the run that wrote it (run_analysis.py); no other output
            # carries either key
            "execution_timestamp_utc", "git_commit_or_hash")
# Text outputs are compared with line endings normalised: the same content written
# on Windows carries CRLF while the committed blob is LF, and that is not a
# reproduction failure.
TEXT_OUTPUT_SUFFIXES = (".tex", ".csv", ".md", ".html", ".txt")


def _xlsx_canonical(data):
    """A workbook's content for hashing: its members in name order, without docProps/core.xml, which records when the
    workbook was written. Measured on the 21 vignette workbooks of 22 September 2026, it is the only member that
    differs between two runs on the same inputs (the zip entries' own times differ too, and are not read)."""
    import zipfile
    try:
        z = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile:
        return data
    parts = []
    for name in sorted(z.namelist()):
        if name == "docProps/core.xml":
            continue
        parts.append(name.encode("utf-8") + b"\0" + z.read(name) + b"\0")
    return b"".join(parts)


def output_bytes_for_hash(rel, data):
    if rel.endswith(TEXT_OUTPUT_SUFFIXES):
        return data.replace(b"\r\n", b"\n")
    if rel.endswith(".xlsx"):
        return _xlsx_canonical(data)
    return data

# R221 (the frozen review of 21 September 2026, T01): run_analysis.py writes its vignette workings and the
# paper pack's tables and figures on every run, and build_working_sample.py runs it whole before any
# calibration. The whole-tree input attestation reads every tracked file no step declares as an output as an
# input, so the recorded pass of 22 September 2026 found them changed after it began (a workbook records when
# it was written, a vignette's metadata the run's commit and time) and could not be accepted. Every tracked
# file under vignettes/vignette-1/, vignettes/vignette-2/ and paper_pack/ that no other step declares is
# declared here by name; src/test_reproduce_report.py::test_the_manifest_writes_are_declared keeps it whole.
RUN_ANALYSIS_WRITES = (
    "paper_pack/fig2_p95_trends.png",
    "paper_pack/fig3_mean_excess.png",
    "paper_pack/fig4_size_severity_loglog.png",
    "paper_pack/fig5_var_decomposition.png",
    "paper_pack/fig6_lob_elasticities_NOTE.txt",
    "paper_pack/fig_boxplot_hhi.png",
    "paper_pack/fig_boxplot_reserves.png",
    "paper_pack/fig_boxplot_year.png",
    "paper_pack/fig_capital_decomposition.png",
    "paper_pack/fig_diversification_abs_pyd.png",
    "paper_pack/fig_diversification_reserves.png",
    "paper_pack/fig_hhi_adjusted_size.png",
    "paper_pack/fig_hhi_severity.png",
    "paper_pack/fig_persona_overlay_diversified.png",
    "paper_pack/fig_persona_overlay_large.png",
    "paper_pack/fig_persona_overlay_small.png",
    "paper_pack/fig_persona_overlay_typical.png",
    "paper_pack/fig_persona_overlay_undiversified.png",
    "paper_pack/fig_power_law_hhi.png",
    "paper_pack/fig_power_law_size.png",
    "paper_pack/fig_pyd_distribution.png",
    "paper_pack/fig_size_abs_pyd.png",
    "paper_pack/fig_size_adjusted_hhi.png",
    "paper_pack/fig_size_pyd.png",
    "paper_pack/fig_yearly_observations.png",
    "paper_pack/table10_data_quality.tex",
    "paper_pack/table11_reserves_distribution.tex",
    "paper_pack/table12_decile_tests.tex",
    "paper_pack/table13_primary_re_gls.tex",
    "paper_pack/table14_dispersion_models.tex",
    "paper_pack/table15_direction_test.tex",
    "paper_pack/table16_power_law_hhi.tex",
    "paper_pack/table17_correlation.tex",
    "paper_pack/table18_variance_attribution.tex",
    "paper_pack/table19_hhi_dispersion_adjusted.tex",
    "paper_pack/table1_corpus_coverage.tex",
    "paper_pack/table20_combined_model.tex",
    "paper_pack/table21_test_portfolios.tex",
    "paper_pack/table22_univariate_comparison.tex",
    "paper_pack/table23_variance_attribution_hhi_first.tex",
    "paper_pack/table24_ordering_comparison.tex",
    "paper_pack/table25_local_donor_cas-heavy_500m.tex",
    "paper_pack/table25_local_donor_prop-heavy_500m.tex",
    "paper_pack/table26_tail_sample_support.tex",
    "paper_pack/table27_tail_capital_sensitivity.tex",
    "paper_pack/table28_bootstrap_var.tex",
    "paper_pack/table29_reserve_source_audit.tex",
    "paper_pack/table2_sampling_sensitivity.tex",
    "paper_pack/table30_lob_weight_source_audit.tex",
    "paper_pack/table31_pyd_source_audit.tex",
    "paper_pack/table32_dual_model_workflow.tex",
    "paper_pack/table33_exclusions_by_year.tex",
    "paper_pack/table34_subset_comparison.tex",
    "paper_pack/table35_dispersion_robustness.tex",
    "paper_pack/table36_event_groups.tex",
    "paper_pack/table37_event_group_definitions.tex",
    "paper_pack/table38_dispersion_calibration.tex",
    "paper_pack/table3_size_severity.tex",
    "paper_pack/table4_var_decomposition.tex",
    "paper_pack/table4b_var_decomposition_personas.tex",
    "paper_pack/table5_worked_example_event.tex",
    "paper_pack/table6_worked_example_summary.tex",
    "paper_pack/table7_persona_pyd_stats_raw.tex",
    "paper_pack/table7_persona_pyd_stats_standardised.tex",
    "paper_pack/table8_persona_tail_diagnostics.tex",
    "paper_pack/table9_corpus_summary.tex",
    "vignettes/vignette-1/README.md",
    "vignettes/vignette-1/decomposition_summary.csv",
    "vignettes/vignette-1/decomposition_summary.tex",
    "vignettes/vignette-1/decomposition_summary.xlsx",
    "vignettes/vignette-1/distribution_plot.pdf",
    "vignettes/vignette-1/distribution_plot.png",
    "vignettes/vignette-1/distribution_plot_data.csv",
    "vignettes/vignette-1/distribution_plot_data.tex",
    "vignettes/vignette-1/distribution_plot_data.xlsx",
    "vignettes/vignette-1/distribution_stats.csv",
    "vignettes/vignette-1/distribution_stats.tex",
    "vignettes/vignette-1/distribution_stats.xlsx",
    "vignettes/vignette-1/donor_selection.csv",
    "vignettes/vignette-1/donor_selection.tex",
    "vignettes/vignette-1/donor_selection.xlsx",
    "vignettes/vignette-1/metadata.json",
    "vignettes/vignette-1/summary_snippet.md",
    "vignettes/vignette-1/tail_exceedance_plot.pdf",
    "vignettes/vignette-1/tail_exceedance_plot.png",
    "vignettes/vignette-1/tail_exceedance_plot_data.csv",
    "vignettes/vignette-1/tail_exceedance_plot_data.tex",
    "vignettes/vignette-1/tail_exceedance_plot_data.xlsx",
    "vignettes/vignette-1/tail_support_bootstrap.csv",
    "vignettes/vignette-1/tail_support_bootstrap.tex",
    "vignettes/vignette-1/tail_support_bootstrap.xlsx",
    "vignettes/vignette-1/target_profile.json",
    "vignettes/vignette-1/target_profile_table.csv",
    "vignettes/vignette-1/target_profile_table.tex",
    "vignettes/vignette-1/target_profile_table.xlsx",
    "vignettes/vignette-1/worked_example_mix_mismatch.csv",
    "vignettes/vignette-1/worked_example_mix_mismatch.json",
    "vignettes/vignette-1/worked_example_mix_mismatch.tex",
    "vignettes/vignette-1/worked_example_mix_mismatch.xlsx",
    "vignettes/vignette-1/worked_example_size_mismatch.csv",
    "vignettes/vignette-1/worked_example_size_mismatch.json",
    "vignettes/vignette-1/worked_example_size_mismatch.tex",
    "vignettes/vignette-1/worked_example_size_mismatch.xlsx",
    "vignettes/vignette-2/README.md",
    "vignettes/vignette-2/decomposition_summary.csv",
    "vignettes/vignette-2/decomposition_summary.tex",
    "vignettes/vignette-2/decomposition_summary.xlsx",
    "vignettes/vignette-2/distribution_plot.pdf",
    "vignettes/vignette-2/distribution_plot.png",
    "vignettes/vignette-2/distribution_plot_data.csv",
    "vignettes/vignette-2/distribution_plot_data.tex",
    "vignettes/vignette-2/distribution_plot_data.xlsx",
    "vignettes/vignette-2/distribution_stats.csv",
    "vignettes/vignette-2/distribution_stats.tex",
    "vignettes/vignette-2/distribution_stats.xlsx",
    "vignettes/vignette-2/donor_selection.csv",
    "vignettes/vignette-2/donor_selection.tex",
    "vignettes/vignette-2/donor_selection.xlsx",
    "vignettes/vignette-2/metadata.json",
    "vignettes/vignette-2/old_to_new_change_decomposition.csv",
    "vignettes/vignette-2/old_to_new_change_decomposition.tex",
    "vignettes/vignette-2/old_to_new_change_decomposition.xlsx",
    "vignettes/vignette-2/old_to_new_waterfall.pdf",
    "vignettes/vignette-2/old_to_new_waterfall.png",
    "vignettes/vignette-2/old_to_new_waterfall_data.csv",
    "vignettes/vignette-2/old_to_new_waterfall_data.tex",
    "vignettes/vignette-2/old_to_new_waterfall_data.xlsx",
    "vignettes/vignette-2/profile_transition_distribution.csv",
    "vignettes/vignette-2/profile_transition_distribution.tex",
    "vignettes/vignette-2/profile_transition_distribution.xlsx",
    "vignettes/vignette-2/summary_snippet.md",
    "vignettes/vignette-2/tail_exceedance_plot.pdf",
    "vignettes/vignette-2/tail_exceedance_plot.png",
    "vignettes/vignette-2/tail_exceedance_plot_data.csv",
    "vignettes/vignette-2/tail_exceedance_plot_data.tex",
    "vignettes/vignette-2/tail_exceedance_plot_data.xlsx",
    "vignettes/vignette-2/tail_support_bootstrap.csv",
    "vignettes/vignette-2/tail_support_bootstrap.tex",
    "vignettes/vignette-2/tail_support_bootstrap.xlsx",
    "vignettes/vignette-2/target_transition.json",
    "vignettes/vignette-2/target_transition_table.csv",
    "vignettes/vignette-2/target_transition_table.tex",
    "vignettes/vignette-2/target_transition_table.xlsx",
    "vignettes/vignette-2/worked_example_mix_mismatch.csv",
    "vignettes/vignette-2/worked_example_mix_mismatch.json",
    "vignettes/vignette-2/worked_example_mix_mismatch.tex",
    "vignettes/vignette-2/worked_example_mix_mismatch.xlsx",
    "vignettes/vignette-2/worked_example_size_mismatch.csv",
    "vignettes/vignette-2/worked_example_size_mismatch.json",
    "vignettes/vignette-2/worked_example_size_mismatch.tex",
    "vignettes/vignette-2/worked_example_size_mismatch.xlsx",
)

# Every manifest step's outputs, declared. --verify compares each declared output with
# the committed version: canonical JSON (only the documented VOLATILE fields excluded)
# for .json, byte-for-byte for anything else. The old verifier filtered `git diff` to
# .json, so a changed .npz was invisible -- while the cover letter claimed the
# 6,000-draw NPZ byte-identical. A claim the tooling cannot check is not a claim.
# run_analysis.py's vignette workings and paper pack are declared (RUN_ANALYSIS_WRITES, R221); a workbook is
# compared without the member that records when it was written.
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
    "check_cohort_scope.py": (
        "results/check_cohort_scope_results.json",),
    "audit_pyd_basis.py": (
        "results/pyd_basis_declarations.json", "results/pyd_basis_declarations.md"),
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
    "check_serial_sensitivity.py": ("results/check_serial_sensitivity_results.json",),
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
    "build_working_sample.py": ("model/exposure_results.json",) + RUN_ANALYSIS_WRITES,
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
    "check_k_half_sensitivity.py": ("results/check_k_half_sensitivity_results.json",),
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
    "check_long_tail_share.py": ("results/check_long_tail_share_results.json",),
    "appendix_c_tail_comparison.py": ("figures/appendix_c_tail_comparison.tex",
                                      "figures/appendix_c_tail_comparison.pdf",
                                      "figures/appendix_c_tail_comparison.png"),
    # run_analysis also writes its vignette workings and the paper pack's tables and figures
    # (RUN_ANALYSIS_WRITES, R221)
    "run_analysis.py": ("model/exposure_results.json", "distortion_tool.html",
                        "results/disposition_ledger.csv", "paper_pack/table39_reconciliation.tex")
                       + RUN_ANALYSIS_WRITES,
    "make_v1_ritc_survivor.py": ("paper_pack/fig_v1_ritc_survivor.pdf", "paper_pack/fig_v1_ritc_survivor.png"),
    "make_paper_figures.py": ("paper_pack/fig_corpus_coverage.pdf", "paper_pack/fig_size_dispersion.pdf",
                              "paper_pack/fig_hhi_dispersion.pdf", "paper_pack/fig_goodness_of_fit.pdf",
                              "results/goodness_of_fit_results.json",
                              # R221: the PNG beside each PDF
                              "paper_pack/fig_corpus_coverage.png", "paper_pack/fig_goodness_of_fit.png",
                              "paper_pack/fig_hhi_dispersion.png", "paper_pack/fig_size_dispersion.png"),
    "build_current_results.py": ("docs/current-results.md", "docs/data-provenance.md",
                                 "docs/referee-checks.md"),
    "generate_data_audit.py": ("docs/appendix-data-audit.md",),
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
    raw_equal = cur == blob
    cur, blob = output_bytes_for_hash(rel, cur), output_bytes_for_hash(rel, blob)
    if cur == blob:
        if rel.endswith(".xlsx") and not raw_equal:
            return "identical-excluding-volatile", "docProps/core.xml"
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



# --- the whole-tree input attestation ------------------------------------------------------
# The first report checked `src` and reproduce.py only, and only after the scripts had run, so an
# extraction record, a repair register, a template or the lock file could change -- before or
# during a run -- and the report still said the tree was clean (frozen review of 21 September
# 2026, T01). This is taken BEFORE the scripts run and checked AFTER. Every tracked file that no
# manifest script declares as an output is an input. The tree must be clean when the run begins,
# HEAD must not move, and no input may differ from HEAD afterwards. The inputs' blob ids at the
# starting commit are hashed into one digest, which --verify recomputes from the recorded commit,
# using the output set the report itself records.
ALWAYS_WRITTEN = ("reproduce-run-report.json",)


def _git(root, *args):
    return subprocess.run(["git", "-C", root] + list(args), capture_output=True, text=True,
                          encoding="utf-8", errors="replace")


def declared_outputs():
    """Every path a manifest script declares it writes, and the report itself."""
    return sorted({rel.replace("\\", "/") for rels in OUTPUTS.values() for rel in rels}
                  | set(ALWAYS_WRITTEN))


def changed_paths(root):
    """Every path git reports as modified, staged, deleted or untracked (both ends of a rename)."""
    toks = _git(root, "status", "--porcelain=v1", "-z", "--untracked-files=all").stdout.split("\0")
    paths, i = [], 0
    while i < len(toks):
        tok = toks[i]
        i += 1
        if not tok:
            continue
        code, path = tok[:2], tok[3:]
        paths.append(path)
        if "R" in code or "C" in code:
            if i < len(toks) and toks[i]:
                paths.append(toks[i])
            i += 1
    return paths


def inputs_digest(root, commit, excluded):
    """(sha256, count) over "path blob-id" of every file at `commit` not in `excluded`."""
    import hashlib
    listing = _git(root, "ls-tree", "-r", "--full-tree", commit).stdout.splitlines()
    skip = set(excluded)
    pairs = sorted("%s %s" % (path, meta.split()[2])
                   for meta, path in (line.split("\t", 1) for line in listing if "\t" in line)
                   if path not in skip)
    return hashlib.sha256("\n".join(pairs).encode("utf-8")).hexdigest(), len(pairs)


def capture_inputs(root=None, excluded=None):
    """The state of the tree when a run begins."""
    root = root or HERE
    excluded = declared_outputs() if excluded is None else sorted(excluded)
    head = _git(root, "rev-parse", "HEAD").stdout.strip()
    dirty = changed_paths(root)
    digest, n = inputs_digest(root, head, excluded)
    return {"head_before": head, "clean_before": not dirty, "dirty_before": dirty[:50],
            "inputs_sha256": digest, "n_inputs": n, "outputs_excluded": excluded}


def check_inputs_after(before, root=None):
    """The same attestation after the run: HEAD unchanged and no input differing from it."""
    root = root or HERE
    head = _git(root, "rev-parse", "HEAD").stdout.strip()
    skip = set(before["outputs_excluded"])
    problems = []
    if head != before["head_before"]:
        problems.append("HEAD moved during the run: %s -> %s"
                        % (before["head_before"][:12], head[:12]))
    problems += ["input differs from HEAD after the run: %s" % p
                 for p in changed_paths(root) if p not in skip]
    return dict(before, unchanged_after=not problems, changed_after=problems[:50])


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
    if rep.get("schema", 1) < 4:
        return False, ["report schema %s predates the whole-tree input attestation; rerun the "
                       "recorded pass" % rep.get("schema")]
    if rep.get("worktree_dirty_src") is not False:
        return False, ["recorded run had a DIRTY source tree; a dirty run "
                       "establishes nothing about the committed code -- rerun from "
                       "a clean checkout"]
    inp = rep.get("inputs")
    if not isinstance(inp, dict):
        return False, ["report carries no input attestation; rerun the recorded pass"]
    if inp.get("clean_before") is not True:
        return False, ["the tree was not clean when the recorded run began (%s); a run on "
                       "changed inputs establishes nothing about the committed ones"
                       % ", ".join(inp.get("dirty_before") or ["unrecorded"])[:200]]
    if inp.get("unchanged_after") is not True:
        return False, ["an input or HEAD changed during the recorded run (%s)"
                       % "; ".join(inp.get("changed_after") or ["unrecorded"])[:200]]
    ok = True
    if inp.get("head_before") != rep.get("commit"):
        ok = False
        msgs.append("the run began at %s but records commit %s"
                    % (str(inp.get("head_before"))[:12], str(rep.get("commit"))[:12]))
    if not isinstance(inp.get("outputs_excluded"), list):
        ok = False
        msgs.append("the input attestation does not record the output set it excluded")
    else:
        digest, n = inputs_digest(HERE, rep.get("commit", ""), inp["outputs_excluded"])
        if digest != inp.get("inputs_sha256") or n != inp.get("n_inputs"):
            ok = False
            msgs.append("the recorded inputs digest (%s, %s files) is not the recorded "
                        "commit's (%s, %d files)" % (str(inp.get("inputs_sha256"))[:12],
                                                    inp.get("n_inputs"), digest[:12], n))
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
    # the input attestation is taken BEFORE any script runs, and checked again after
    tree_before = capture_inputs()
    failed = run(steps)
    tree_state = check_inputs_after(tree_before)
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
        "schema": 4,
        "environment": env,
        "commit": rc.stdout.strip(),
        "worktree_dirty_src": bool(dirty),
        "inputs": tree_state,
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
