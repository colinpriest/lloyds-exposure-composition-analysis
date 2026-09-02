#!/usr/bin/env python3
"""Every documented `python <path>.py` command must name a file that exists.

Round 44 of the paper review found the public reproduction instructions still
telling a reader to run run_analysis.py, generate_data_audit.py and four more
scripts from the repository root, when d2f2796 had moved every analysis script
into src/ on 21 July 2026. The generated data audit repeated the stale command
from its generator, and fifty-odd `Run:` / `Usage:` docstrings under src/ kept
the old form. Each instruction was correct when written and became false when
the files moved, and nothing checked that a documented command still resolved.

This test parses every `python <path>.py` command in the current-facing
documents, the root script and every src/ docstring, and asserts that the target
exists relative to the repository root -- the working directory the README says
every command is run from. Declared superseded archives (a `Status: superseded`
header) are out of scope, as are placeholders such as `python src/<script>.py`.
This file exempts itself from the scan: its planted examples are the defect.

Run:  python -m pytest src/test_documented_commands.py -q
"""
import glob
import io
import os
import re

import pytest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SELF = os.path.abspath(__file__)

COMMAND = re.compile(
    r"python(?:3(?:\.\d+)?)?\s+(?:-m\s+\S+\s+)?([A-Za-z0-9_./\\-]*\.py)\b")
SUPERSEDED = re.compile(r"^>?\s*\*\*Status:\s*superseded", re.I | re.M)


def _read(path):
    return io.open(path, encoding="utf-8").read()


def documented_commands(text):
    """Every script path a `python ...` command in `text` names, in order."""
    return [m.group(1) for m in COMMAND.finditer(text) if "<" not in m.group(1)]


def missing_targets(text):
    """The documented targets that do not exist relative to the repository root."""
    return [t for t in documented_commands(text)
            if not os.path.exists(os.path.join(HERE, t.replace("\\", "/")))]


def current_facing_documents():
    docs = [os.path.join(HERE, "README.md"), os.path.join(HERE, "reproduce.py")]
    for path in sorted(glob.glob(os.path.join(HERE, "docs", "*.md"))):
        head = "\n".join(_read(path).splitlines()[:8])
        if not SUPERSEDED.search(head):
            docs.append(path)
    docs += [p for p in sorted(glob.glob(os.path.join(HERE, "src", "*.py")))
             if os.path.abspath(p) != SELF]
    return docs


@pytest.mark.parametrize("path", current_facing_documents(),
                         ids=lambda p: os.path.relpath(p, HERE).replace("\\", "/"))
def test_every_documented_command_names_an_existing_file(path):
    assert missing_targets(_read(path)) == [], (
        "%s documents a command whose target does not exist from the repository "
        "root" % os.path.relpath(path, HERE))


def test_src_docstrings_use_the_src_prefix():
    """A `Run:`/`Usage:` line naming a src/ script must say src/ -- the existence
    check above already fails on the bare form, this states the convention."""
    bad = []
    for path in sorted(glob.glob(os.path.join(HERE, "src", "*.py"))):
        if os.path.abspath(path) == SELF:
            continue
        for line in _read(path).splitlines():
            if re.match(r"\s*(Run|Usage):", line):
                for target in documented_commands(line):
                    name = os.path.basename(target)
                    if os.path.exists(os.path.join(HERE, "src", name)) \
                            and not target.replace("\\", "/").startswith("src/"):
                        bad.append((os.path.basename(path), line.strip()))
    assert bad == []


# the historical wordings, assembled so that no rewrite of this file can "fix" them
ROOT_FORM_PROVENANCE = "2. `" + "python " + "run_analysis.py` -> exposure_results.json"
ROOT_FORM_AUDIT = "*regenerate with `" + "python " + "generate_data_audit.py`.*"


def test_helper_fires_on_the_historical_root_form_command():
    """The planted defect: the exact instructions the public documents carried."""
    assert missing_targets(ROOT_FORM_PROVENANCE) == ["run_analysis.py"]
    assert missing_targets(ROOT_FORM_AUDIT) == ["generate_data_audit.py"]


def test_helper_accepts_the_root_script_and_placeholders():
    assert missing_targets("python reproduce.py --check") == []
    assert missing_targets("run as `python src/<script>.py`") == []
    assert missing_targets("python -m pytest src/test_distortion_tool.py -q") == []
