r"""Every file a run hashes is kept byte for byte on every checkout (R221, the review of the whole-tree attestation).

run_analysis.py hashes the record files and the loader's registers as stored (hash_file_contents reads raw bytes) into
source_data_hash and the run identifier, and requirements.txt into each vignette's environment_package_lock_hash. The
repository had no .gitattributes, so Git for Windows' default core.autocrlf=true checked those files out with CRLF, and
a rerun of the same commit wrote a different identifier and data hash into model/exposure_results.json,
distortion_tool.html and both vignettes' metadata.json: outputs that differ from the committed ones with nothing in the
data changed. The root .gitattributes unsets `text` for them. This test reads git's own attribute resolution for every
file the run hashes, so a register added to source_files_for_hash, or a pattern narrowed in .gitattributes, fails here
and not on a reader's machine.

Run:  python -m pytest src/test_hashed_inputs_bytes.py -q
"""
import glob
import os
import subprocess
import sys

import pytest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(HERE, "src"))
sys.path.insert(0, HERE)
import run_analysis as ra  # noqa: E402


def _hashed_files():
    """The files a run hashes, as run_analysis names them, relative to the repository."""
    records = sorted(glob.glob(str(ra.DATA_DIR / "syndicate_*.json")))
    paths = list(ra.source_files_for_hash(records)) + [str(ra.SCRIPT_DIR / "requirements.txt")]
    return [os.path.relpath(p, HERE).replace(os.sep, "/") for p in paths]


def _text_attribute(rels):
    """{path: value of the text attribute}, NUL-separated both ways (a text-mode pipe on Windows would add a carriage
    return to every path it sends)."""
    r = subprocess.run(["git", "-C", HERE, "check-attr", "-z", "--stdin", "text"],
                       input=("\0".join(rels) + "\0").encode("utf-8"), capture_output=True)
    if r.returncode != 0:
        pytest.skip("git check-attr is not available here: %s" % r.stderr.decode("utf-8", "replace").strip()[:200])
    parts = r.stdout.decode("utf-8").split("\0")
    return {parts[i]: parts[i + 2] for i in range(0, len(parts) - 2, 3)}


def test_the_run_hashes_the_records_the_registers_and_the_requirements():
    rels = _hashed_files()
    assert len([p for p in rels if p.startswith("pdf_extraction/syndicate_")]) > 1000
    assert "requirements.txt" in rels and "data/pyd_basis_register.json" in rels


def test_every_hashed_file_is_kept_byte_for_byte():
    rels = _hashed_files()
    attrs = _text_attribute(rels)
    assert set(attrs) == set(rels), "git reported an attribute for every hashed file"
    loose = sorted(p for p in rels if attrs[p] != "unset")
    assert not loose, "%d hashed file(s) a checkout may convert: %s" % (len(loose), loose[:10])
