r"""The analysis run identifier derives from every input the analysis reads, not the record files alone.

run_analysis.main() names a run by a hash of its source data and of its script. The source data were the
record files, so a run whose registers or regime inputs differed kept the same identifier, although each
changes what the analysis does with the same records: the basis register, the confirmed figures and the
take-ons (read by the loader), and the RITC scan and the confirmed transfer register (read through
assumed_business for the tail regime). Found in the review of PLAN R213's loader registers.

Run:  python -m pytest src/test_run_id_inputs.py -q
"""
import io
import os
import sys

import pytest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(HERE, "src"))
import assumed_business  # noqa: E402
import run_analysis as ra  # noqa: E402

INPUTS = ((ra, "PYD_BASIS_REGISTER"), (ra, "PYD_CONFIRMED_FIGURES"), (ra, "TAKEON_REGISTER"),
          (ra, "OPENING_RESERVES_CONFIRMED"), (ra, "TAKEON_BASE_REGISTER"), (assumed_business, "RITC_SCAN"),
          (assumed_business, "TRANSFER_REGISTER"))


@pytest.fixture
def inputs(tmp_path, monkeypatch):
    paths = {}
    for module, name in INPUTS:
        p = tmp_path / ("%s.json" % name)
        p.write_text('{"_purpose": "test"}', encoding="utf-8")
        monkeypatch.setattr(module, name, p)
        paths[name] = p
    record = tmp_path / "syndicate_1_2020.json"
    record.write_text("{}", encoding="utf-8")
    return record, paths


def test_the_hashed_inputs_are_the_records_and_every_register_the_analysis_reads(inputs):
    record, paths = inputs
    files = ra.source_files_for_hash([str(record)])
    assert sorted(files) == sorted([str(record)] + [str(p) for p in paths.values()])


def test_editing_any_register_changes_the_source_hash(inputs):
    record, paths = inputs
    before = ra.hash_file_contents(ra.source_files_for_hash([str(record)]))
    for name, p in paths.items():
        p.write_text('{"_purpose": "edited %s"}' % name, encoding="utf-8")
        after = ra.hash_file_contents(ra.source_files_for_hash([str(record)]))
        assert after != before, name
        before = after


def test_the_run_is_named_from_those_inputs():
    """A helper nobody calls would pass the two tests above and leave the identifier as it was."""
    src = io.open(ra.__file__, encoding="utf-8").read()
    assert "source_hash = hash_file_contents(source_files_for_hash(file_paths))" in src
    assert "hash_file_contents(file_paths)" not in src
