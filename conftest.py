"""Suite-wide rule: a skip must have a declared reason (src/skip_budget.py), or the run fails.

A skip that nothing accounts for reads as green. The declarations say which environments may
skip what; a reason outside them is either a new skip that has not been argued for or a test
that has stopped running for a reason nobody chose, and either way the run should say so.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))
import skip_budget  # noqa: E402


def skip_reason_of(report):
    """The reason text of a skipped test report (pytest keeps it in longrepr's third field)."""
    rep = getattr(report, "longrepr", None)
    if isinstance(rep, tuple) and len(rep) == 3:
        return str(rep[2])
    return str(rep or "")


def undeclared_skips(reports):
    return skip_budget.undeclared(skip_reason_of(r) for r in reports)


def pytest_sessionfinish(session, exitstatus):
    tr = session.config.pluginmanager.get_plugin("terminalreporter")
    if tr is None:
        return
    bad = undeclared_skips(tr.stats.get("skipped", []))
    if bad:
        tr.write_line("")
        tr.write_line("UNDECLARED SKIP REASON(S) -- declare them in src/skip_budget.py or make the test run:",
                      red=True)
        for reason in bad:
            tr.write_line("  " + reason, red=True)
        if session.exitstatus == 0:
            session.exitstatus = 1
