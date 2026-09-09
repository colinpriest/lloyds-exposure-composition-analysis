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


SKIP_LINE = re.compile(r"^SKIPPED \[(\d+)\] (\S+?):\d+: (.*)$")


def skip_reasons(text):
    """{reason: count} from pytest's -rs summary, so a rise in skips is itemised."""
    out = {}
    for line in text.splitlines():
        m = SKIP_LINE.match(line.strip())
        if m:
            reason = m.group(3).strip()
            out[reason] = out.get(reason, 0) + int(m.group(1))
    return dict(sorted(out.items()))


def run_suite():
    r = subprocess.run([sys.executable, "-m", "pytest", "-q", "-rs"], cwd=HERE,
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
            "skip_reasons": skip_reasons(tail),
            "summary_line": line.strip()}


def collect_only():
    r = subprocess.run([sys.executable, "-m", "pytest", "--collect-only", "-q"],
                       cwd=HERE, capture_output=True, text=True)
    n = collected_count((r.stdout or "") + (r.stderr or ""))
    if n is None:
        raise SystemExit("could not read the collected-test count")
    return n


REPORT = os.path.join(HERE, "reproduce-run-report.json")
CALIBRATION = os.path.join(HERE, "model", "dispersion_calibration_ritc.json")
SCALE_TERM = os.path.join(HERE, "results", "check_ritc_scale_term_results.json")


def stamped_readme_text(text, rec):
    """The README with every stated number that has a record rewritten from it: the
    suite counts (this record), the full-manifest run date (the run report), the
    headline fit (the calibration) and the operator's RITC scale-term cost (the
    scale-term check). Round 54, review D01-D03: the run date said 7 September after
    a 9 September run, and the headline numbers were typed."""
    text = re.sub(r"\(\d+ passed, \d+ skipped\)",
                  "(%d passed, %d skipped)" % (rec["passed"], rec["skipped"]), text)
    if os.path.exists(REPORT):
        rep = json.load(io.open(REPORT, encoding="utf-8"))
        d = datetime.datetime.strptime(rep["finished_utc"][:10], "%Y-%m-%d")
        text = re.sub(r"was made on\s+\d{1,2} \w+ \d{4} on a source tree",
                      "was made on\n%d %s %d on a source tree" % (d.day, d.strftime("%B"), d.year), text)
    if os.path.exists(CALIBRATION):
        cal = json.load(io.open(CALIBRATION, encoding="utf-8"))
        p = cal["params"]
        head = ("`k ≈ %.2f`, `gamma ≈ %.2f`,\n`sigma_undiv ≈ %.3f`, `nu_clean ≈ %.2f`, `nu_ritc ≈ %.2f`, "
                "`P(nu_ritc < nu_clean) = %.2f`."
                % (p["k"]["mean"], p["gamma"]["mean"], p["sd_undiv"]["mean"], p["nu_clean"]["mean"],
                   p["nu_ritc"]["mean"], cal["posterior_prob"]["nu_ritc_lt_nu_clean"]))
        text = re.sub(r"`k ≈ [0-9.]+`, `gamma ≈ [0-9.]+`,\s*`sigma_undiv ≈ [0-9.]+`, `nu_clean ≈ [0-9.]+`, "
                      r"`nu_ritc ≈ [0-9.]+`, `P\(nu_ritc < nu_clean\) = [0-9.]+`\.", head, text)
        text = re.sub(r"Headline fit \(n=\d+ gross-basis", "Headline fit (n=%d gross-basis" % cal["n"], text)
    if os.path.exists(SCALE_TERM):
        sens = json.load(io.open(SCALE_TERM, encoding="utf-8"))["operator_sensitivity"]["V1_VaR995"]
        pct = 100 * sens["difference"]["mean"] / sens["as_published"]["mean"]
        text = re.sub(r"worth about [0-9.]+% of the vignette stresses", "worth about %.1f%% of the vignette stresses" % pct, text)
    return text


RANEF = os.path.join(HERE, "results", "check_syndicate_random_effect_results.json")
PROVENANCE = os.path.join(HERE, "docs", "data-provenance.md")


def stamp_provenance_note():
    """docs/data-provenance.md: the random-intercept floor change, from the record
    (round 54, review D05: the note said 2.1% to 1.3% for a fit at 2.3% to 1.4%)."""
    if not (os.path.exists(RANEF) and os.path.exists(PROVENANCE)):
        return False
    fits = json.load(io.open(RANEF, encoding="utf-8"))["fits"]
    a = 100 * fits["mu0_adopted"]["sd_undiv"]["mean"]
    b = 100 * fits["random_intercept"]["sd_undiv"]["mean"]
    text = io.open(PROVENANCE, encoding="utf-8").read()
    new = re.sub(r"the floor moves from about [0-9.]+% to\s+[0-9.]+% when partially pooled syndicate intercepts are added",
                 "the floor moves from about %.1f%% to\n%.1f%% when partially pooled syndicate intercepts are added" % (a, b), text)
    if new != text:
        io.open(PROVENANCE, "w", encoding="utf-8", newline="\n").write(new)
        return True
    return False


def stamp_readme(rec):
    """Rewrite every stated, recorded number in the README (see stamped_readme_text),
    and the provenance note's recorded figures."""
    stamp_provenance_note()
    text = io.open(README, encoding="utf-8").read()
    stamped = stamped_readme_text(text, rec)
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
            "failed": result["failed"],
            "skip_reasons": result.get("skip_reasons", {})}


def write_record(rec):
    io.open(RECORD, "w", encoding="utf-8", newline="\n").write(
        json.dumps(rec, indent=2) + "\n")


def stamp_only():
    """Stamp the README from the existing record and result files, without running
    the suite (python src/record_tests.py --stamp)."""
    rec = json.load(io.open(RECORD, encoding="utf-8"))
    changed = stamp_readme(rec)
    print("README %s" % ("stamped" if changed else "already agrees with the records"))
    return 0


def main():
    if "--stamp" in sys.argv:
        return stamp_only()
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
