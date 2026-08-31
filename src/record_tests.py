#!/usr/bin/env python3
"""Run the test suite, record the result, and stamp the README from that record.

Why this exists. The README and the manuscript's submission checklist both stated
"121 passed, 14 skipped". The suite passed 122. The number had been typed by hand
after a run, and a test added the same day made it stale before anyone read it -- the
same failure as the "22 scripts" and "~2.5 hours" that `reproduce.py --check` already
polices, and the same failure as a page count typed into a checklist.

So no test count is typed anywhere any more. This script runs the suite, writes
`tests-run-report.json` (counts, commit, dirty flag, environment), and rewrites the
README's stated numbers from what it just observed. `reproduce.py --check` then fails
if a stated count disagrees with the record, OR if the suite has changed size since
the record was written -- because a record can go stale exactly the way prose does,
and a stale record that nothing checks is worse than a typed number.

Run:  python src/record_tests.py
"""
import datetime
import io
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RECORD = os.path.join(HERE, "tests-run-report.json")
README = os.path.join(HERE, "README.md")

SUMMARY = re.compile(
    r"(?:(?P<failed>\d+) failed[, ]+)?(?P<passed>\d+) passed"
    r"(?:[, ]+(?P<skipped>\d+) skipped)?")


def collected_count(text):
    m = re.search(r"(\d+)\s+tests? collected", text)
    return int(m.group(1)) if m else None


def run_suite():
    r = subprocess.run([sys.executable, "-m", "pytest", "-q"], cwd=HERE,
                       capture_output=True, text=True)
    tail = (r.stdout or "") + (r.stderr or "")
    line = ""
    for candidate in reversed(tail.splitlines()):
        if "passed" in candidate or "failed" in candidate or "error" in candidate:
            line = candidate
            break
    m = SUMMARY.search(line)
    if not m:
        raise SystemExit("could not parse the pytest summary line: %r" % line[:200])
    return {"passed": int(m.group("passed")),
            "skipped": int(m.group("skipped") or 0),
            "failed": int(m.group("failed") or 0),
            "summary_line": line.strip()}


def collect_only():
    r = subprocess.run([sys.executable, "-m", "pytest", "--collect-only", "-q"],
                       cwd=HERE, capture_output=True, text=True)
    n = collected_count((r.stdout or "") + (r.stderr or ""))
    if n is None:
        raise SystemExit("could not read the collected-test count")
    return n


def stamp_readme(rec):
    """Rewrite every stated suite result in the README from the record."""
    text = io.open(README, encoding="utf-8").read()
    stamped = re.sub(r"\(\d+ passed, \d+ skipped\)",
                     "(%d passed, %d skipped)" % (rec["passed"], rec["skipped"]),
                     text)
    if stamped != text:
        io.open(README, "w", encoding="utf-8", newline="\n").write(stamped)
        return True
    return False


def build_record(result):
    dirty = subprocess.run(["git", "-C", HERE, "status", "--porcelain", "--",
                            "src", "reproduce.py"],
                           capture_output=True, text=True).stdout.strip()
    commit = subprocess.run(["git", "-C", HERE, "rev-parse", "HEAD"],
                            capture_output=True, text=True).stdout.strip()
    import platform as _pf
    return {"schema": 1,
            "commit": commit,
            "worktree_dirty_src": bool(dirty),
            "python": sys.version.split()[0],
            "platform": _pf.platform(),
            "finished_utc": datetime.datetime.now(datetime.timezone.utc)
                            .strftime("%Y-%m-%dT%H:%M:%SZ"),
            "collected": collect_only(),
            "passed": result["passed"],
            "skipped": result["skipped"],
            "failed": result["failed"]}


def write_record(rec):
    io.open(RECORD, "w", encoding="utf-8", newline="\n").write(
        json.dumps(rec, indent=2) + "\n")


def main():
    for attempt in range(1, 4):
        result = run_suite()
        # The candidate describes the run that will VERIFY it, not the one that
        # produced the counts: recording this run's failures would guarantee the next
        # run fails for the same reason, since one of the tests reads this file.
        rec = build_record(dict(result, failed=0))
        write_record(rec)
        stamped = stamp_readme(rec)
        # The suite reads this record, so it is a function of what was just written:
        # re-run and require the second pass to be green AND to agree.
        check = run_suite()
        agrees = (check["failed"] == 0
                  and (check["passed"], check["skipped"])
                  == (rec["passed"], rec["skipped"]))
        print("pass %d: recorded %d passed, %d skipped (%d collected); re-run gives "
              "%d passed, %d skipped, %d failed%s"
              % (attempt, rec["passed"], rec["skipped"], rec["collected"],
                 check["passed"], check["skipped"], check["failed"],
                 " [README stamped]" if stamped else ""))
        if agrees:
            print("settled at %s%s" % (rec["commit"][:12],
                                       " [DIRTY src]" if rec["worktree_dirty_src"]
                                       else ""))
            return 0

    # not a bookkeeping problem: the suite is failing for a reason the record cannot
    # cure. Write what was actually observed and refuse.
    write_record(build_record(check))
    raise SystemExit("the suite did not settle against its own record; the last run "
                     "reported %d failing test(s), now recorded. Fix the suite."
                     % check["failed"])


if __name__ == "__main__":
    raise SystemExit(main())
