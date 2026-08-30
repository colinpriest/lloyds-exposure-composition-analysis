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
model/exposure_results.json. Everything downstream of that file is reproducible here.

Verification. --verify reports only on a run recorded in this checkout, and says
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
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "src")

REQUIRED = ("numpy", "scipy", "matplotlib", "openpyxl", "pymc", "arviz", "pytensor")
INPUTS = ("model/exposure_results.json", "pdf_extraction/ritc_scan.json",
          "distortion_tool.html", "vignettes/vignette-2/target_transition.json")

# (script, stage, rough minutes). The calibration must precede the checks: several read
# model/dispersion_calibration_ritc.json as the published posterior to compare against.
STEPS = [
    ("calibrate_dispersion.py", "calibration", 2),
    ("calibrate_dispersion_ritc.py", "calibration", 2),
    ("calibrate_dispersion_systemic.py", "calibration", 3),
    ("calibrate_dispersion_hetscale.py", "calibration", 3),
    ("calibrate_dispersion_sizeloaded.py", "calibration", 3),

    ("check_k_unconstrained.py", "checks", 2),
    ("check_syndicate_random_effect.py", "checks", 4),
    ("check_mean_concentration_bayes.py", "checks", 12),
    ("check_ritc_scale_term.py", "checks", 4),
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
    ("check_tail_support_syndicate.py", "checks", 2),
    ("proxy_stress_bayes.py", "checks", 30),

    # tail analyses: these produce paper results and were missing from the manifest,
    # so a "complete" run did not in fact regenerate the GPD table
    ("vignette_uncertainty.py", "tails", 6),
    ("gpd_var_uncertainty.py", "tails", 4),
    ("bayesian_gpd.py", "tails", 3),

    ("run_analysis.py", "outputs", 5),
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
    for m in re.finditer(r"(\d+)\s+scripts\b", text):
        if int(m.group(1)) != len(STEPS):
            bad.append("says %s scripts; the manifest holds %d"
                       % (m.group(1), len(STEPS)))
    for m in re.finditer(r"~\s*([\d.]+)\s*hours?\b", text):
        stated = float(m.group(1)) * 60.0
        if abs(stated - total_min) > 0.25 * total_min:
            bad.append("says ~%s hours; the manifest totals ~%d minutes"
                       % (m.group(1), total_min))
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
        print("\ninstall the environment first:  pip install -r requirements.txt")
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


VOLATILE = ("runtime_seconds",)
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


def verify():
    """Compare regenerated outputs with the committed ones, ignoring wall-clock fields.

    Two guards, both learned the hard way.

    First, this cannot conclude anything unless a run actually happened. Comparing the
    working tree with HEAD on a clean checkout is trivially equal, so an earlier version
    printed "byte-identical" and exited zero having regenerated nothing at all -- a
    green light for doing nothing.

    Second, `git status` alone answers the wrong question anyway: two calibration files
    record how long the fit took, so they show as modified while every fitted number in
    them is identical. Strip the volatile keys and compare the rest.
    """
    stamp = read_stamp()
    if not stamp:
        print("\nverify: nothing to verify -- no run has been recorded in this "
              "checkout.\n         Run `python reproduce.py` (or --only <stage>) "
              "first; comparing an\n         untouched tree with HEAD proves only "
              "that nothing was regenerated.")
        return False
    ran, total = len(stamp.get("ran", [])), stamp.get("manifest_size", len(STEPS))
    print("\nverify: %d of %d manifest scripts were run in this checkout" % (ran, total))
    if stamp.get("failed"):
        print("verify: %d script(s) failed in that run: %s"
              % (len(stamp["failed"]), ", ".join(stamp["failed"])))
    if ran < total:
        print("verify: this is a PARTIAL run; unrun scripts' outputs are the committed "
              "ones and\n        are not evidence of reproduction")
    r = subprocess.run(["git", "-C", HERE, "diff", "--name-only", "--", "model", "results"],
                       capture_output=True, text=True)
    changed = [f for f in r.stdout.split() if f.endswith(".json")]
    if not changed:
        print("\nverify: every regenerated output is byte-identical to the "
              "committed one")
        return True
    substantive = []
    for rel in changed:
        old = subprocess.run(["git", "-C", HERE, "show", "HEAD:" + rel],
                             capture_output=True, text=True).stdout
        try:
            a = json.loads(old)
            b = json.load(io.open(os.path.join(HERE, rel), encoding="utf-8"))
        except Exception:
            substantive.append((rel, "unparseable"))
            continue
        for k in VOLATILE:
            a.pop(k, None)
            b.pop(k, None)
        if a != b:
            substantive.append((rel, "differs"))
    print("\nverify: %d file(s) differ from the committed copy" % len(changed))
    for rel in changed:
        note = dict(substantive).get(rel, "wall-clock timing only")
        print("   %-52s %s" % (rel, note))
    if substantive:
        print("verify: *** substantive differences above -- the run did NOT reproduce")
        return False
    print("verify: all differences are recorded timings; the results reproduced")
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--only", choices=("calibration", "checks", "tails", "outputs"))
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
    for msg in check_readme_counts():
        print("  README *** %s" % msg)
        ok = False
    if a.check:
        return 0 if ok else 1
    if not ok:
        return 1

    print()
    failed = run(steps)
    write_stamp([sc for sc, _, _ in steps if sc not in failed], failed)
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
