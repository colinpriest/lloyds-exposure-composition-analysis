"""Every reason this suite may skip a test, declared, and the rule a recorded run is held to.

A skipping test is not a test. Until the review of 29 September 2026 (A-7) nothing here said so:
37 of the transfer tool's tests skipped silently wherever Node.js was absent, the README never
mentioned Node, and the recorded "1110 passed, 14 skipped" was quietly a statement about the
author's machine. Fourteen more skips were permanent (tests of code removed with the superseded
least-squares projection) and are now replaced by current-model tests.

So:

  * every skip reason the suite can produce is declared below, with the environment that
    produces it. A skip whose reason matches no declaration FAILS the suite (the root
    conftest.py), so a new skip has to be argued for here before it can hide anything;
  * a RECORDED run -- the one src/record_tests.py writes into tests-run-report.json and stamps
    into the README -- may carry none of them: each declared reason is a missing input, a
    missing tool (Node.js) or a missing output, and the recorded run is the one made with all of
    them present. src/record_tests.py refuses to record or stamp a run that skipped anything.

A reader's clone may legitimately lack Node.js, the manuscript checkout or the generated outputs;
there the declared skips are allowed and say what is missing.
"""
import re

#: (id, regular expression matched against the skip reason, why the environment can lack it)
DECLARED = (
    ("node", r"^node is not available$",
     "Node.js is not on PATH: the transfer tool's JavaScript cannot run (README, Setup)"),
    ("generated_output_absent",
     r"(not generated in this checkout|not present in this checkout|results? not present|"
     r"artefact not generated|outputs not generated|not written yet \(rerun pending\)|"
     r"predates the disposition ledger \(rerun pending\)|^sign check not run$|"
     r"is not present in this checkout|^.+ absent$)",
     "a generated output the test reads has not been produced in this checkout"),
    ("run_report_absent_or_pending",
     r"(no committed run report yet|no manifest run report in this tree|"
     r"report predates schema 4|committed run report is from a dirty source tree|"
     r"^no binary outputs in report$)",
     "the manifest's run report is absent, older, or from a dirty tree"),
    ("provenance_document_absent", r"^no (provenance document|correction block) in this tree$",
     "the generated provenance note or its correction block is absent"),
    ("manuscript_absent", r"^no manuscript at .+ cross-repository check does not run$",
     "the manuscript checkout this cross-repository test reads is absent (LLOYDS_PAPER_REPO)"),
    ("git_history_absent", r"^(pre-fix commit not available|git check-attr is not available here)",
     "git, or the history a test replays, is absent (a shallow or exported copy)"),
    ("python_package_absent", r"^(could not import '[A-Za-z_]+'|openpyxl not installed)",
     "an optional Python package is not installed"),
    ("module_unimportable", r"^vignette1_diagnostics(\.[A-Za-z_]+ is gone| is not importable)",
     "a module under test cannot be imported in this environment"),
)


def classify(reason):
    """The declaration a skip reason falls under, or None."""
    text = (reason or "").strip()
    if text.startswith("Skipped: "):
        text = text[len("Skipped: "):]
    for ident, pattern, _why in DECLARED:
        if re.search(pattern, text):
            return ident
    return None


def undeclared(reasons):
    """The skip reasons no declaration covers."""
    return sorted({r for r in reasons if classify(r) is None})


def recorded_run_problems(skip_reasons):
    """Why a run with these skips ({reason: count}) may not be recorded: each skip, declared or not."""
    out = []
    for reason, n in sorted((skip_reasons or {}).items()):
        ident = classify(reason)
        if ident is None:
            out.append("%d skip(s) with an undeclared reason: %s" % (n, reason))
        else:
            out.append("%d skip(s) [%s] in a run that is to be recorded: %s" % (n, ident, reason))
    return out
