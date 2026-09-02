#!/usr/bin/env python3
"""The currency scanner takes its PDF directory from configuration and fails safe.

Round 44 of the paper review found src/currency_scan.py hard-coding the author's
local drive as the source-PDF directory and, when that directory was absent,
marking every report `pdf_missing`, substituting the dual-LLM `currency` field for
all 1,065 of them, and overwriting the canonical pdf_extraction/currency_scan.json
-- so a reader following the documented command would silently replace
PDF-derived provenance with an all-fallback scan.

These tests exercise the behaviour, not the wording:

  * the directory comes from --pdf-dir or the documented environment variable,
    and its absence stops the run before anything is read or written;
  * a run whose source PDFs are missing stops before writing unless the LLM
    substitution is asked for explicitly, and even then writes to a separately
    named file unless canonical replacement is expressly requested;
  * a failed run leaves the committed output byte-identical;
  * the documents that describe the scanner name the same mechanism.

Run:  python -m pytest src/test_currency_scan_config.py -q
"""
import io
import json
import os

import pytest

import currency_scan as cs

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SENTINEL = '{"sentinel": "committed output must not be touched"}'


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    """A fake pdf_extraction/ with two reports, a canonical output sentinel, and a
    scan_pdf stub so no real PDF is opened."""
    data = tmp_path / "pdf_extraction"
    data.mkdir()
    for key in ("1001_2019", "1002_2020"):
        (data / ("syndicate_%s.json" % key)).write_text(
            json.dumps({"models": {"a": {"currency": "USD"}}}), encoding="utf-8")
    canonical = data / "currency_scan.json"
    canonical.write_text(SENTINEL, encoding="utf-8")
    monkeypatch.setattr(cs, "DATA_DIR", data)
    monkeypatch.setattr(cs, "DEFAULT_OUT", canonical)
    monkeypatch.setattr(cs, "FALLBACK_OUT", data / "currency_scan_llm_fallback.json")
    monkeypatch.setattr(cs, "scan_pdf", lambda path, year: (
        "GBP", {"method": "presentational_statement", "page": 3,
                "section_heading": None, "quote": "presented in sterling",
                "unit_headers": {"usd_hits": 0, "gbp_hits": 9},
                "evidence_conflict": False}))
    monkeypatch.delenv(cs.ENV_VAR, raising=False)
    return data, canonical


def _pdf_dir(tmp_path, keys):
    d = tmp_path / "pdfs"
    d.mkdir(exist_ok=True)
    for key in keys:
        (d / ("syndicate_%s.pdf" % key)).write_bytes(b"%PDF-stub")
    return d


def test_no_directory_configured_stops_before_anything_is_written(workspace):
    data, canonical = workspace
    with pytest.raises(SystemExit):
        cs.main([])
    assert canonical.read_text(encoding="utf-8") == SENTINEL
    assert not (data / "currency_scan_llm_fallback.json").exists()


def test_absent_directory_stops_before_anything_is_written(workspace, tmp_path):
    data, canonical = workspace
    with pytest.raises(SystemExit):
        cs.main(["--pdf-dir", str(tmp_path / "nowhere")])
    assert canonical.read_text(encoding="utf-8") == SENTINEL


def test_environment_variable_supplies_the_directory(workspace, tmp_path, monkeypatch):
    data, canonical = workspace
    monkeypatch.setenv(cs.ENV_VAR, str(_pdf_dir(tmp_path, ["1001_2019", "1002_2020"])))
    assert cs.main([]) == 0
    out = json.loads(canonical.read_text(encoding="utf-8"))
    assert out["n_reports"] == 2 and out["pdf_missing"] == 0
    assert out["method_counts"] == {"presentational_statement": 2}


def test_complete_source_coverage_writes_the_canonical_output(workspace, tmp_path):
    data, canonical = workspace
    pdfs = _pdf_dir(tmp_path, ["1001_2019", "1002_2020"])
    assert cs.main(["--pdf-dir", str(pdfs)]) == 0
    out = json.loads(canonical.read_text(encoding="utf-8"))
    assert out["pdf_dir"] == str(pdfs.resolve())
    assert out["counts"] == {"GBP": 2}
    assert out["fallback_mode"] is False


def test_missing_source_pdfs_stop_before_writing_unless_fallback_is_explicit(
        workspace, tmp_path):
    data, canonical = workspace
    pdfs = _pdf_dir(tmp_path, ["1001_2019"])          # 1002_2020 absent
    with pytest.raises(SystemExit):
        cs.main(["--pdf-dir", str(pdfs)])
    assert canonical.read_text(encoding="utf-8") == SENTINEL
    assert not (data / "currency_scan_llm_fallback.json").exists()


def test_explicit_fallback_writes_a_separate_file_and_keeps_the_canonical_one(
        workspace, tmp_path):
    data, canonical = workspace
    pdfs = _pdf_dir(tmp_path, ["1001_2019"])
    assert cs.main(["--pdf-dir", str(pdfs), "--allow-llm-fallback"]) == 0
    assert canonical.read_text(encoding="utf-8") == SENTINEL
    out = json.loads((data / "currency_scan_llm_fallback.json").read_text(encoding="utf-8"))
    assert out["fallback_mode"] is True and out["pdf_missing"] == 1
    assert out["reports"]["1002_2020"]["provenance"]["method"] == "llm_field"
    assert out["reports"]["1002_2020"]["currency"] == "USD"
    assert out["reports"]["1001_2019"]["provenance"]["method"] == "presentational_statement"


def test_canonical_replacement_under_fallback_must_be_expressly_requested(
        workspace, tmp_path):
    data, canonical = workspace
    pdfs = _pdf_dir(tmp_path, ["1001_2019"])
    assert cs.main(["--pdf-dir", str(pdfs), "--allow-llm-fallback",
                    "--replace-canonical"]) == 0
    out = json.loads(canonical.read_text(encoding="utf-8"))
    assert out["fallback_mode"] is True and out["pdf_missing"] == 1


def test_out_cannot_name_the_canonical_file_under_fallback(workspace, tmp_path):
    """The second door: --out pointed at the canonical file name must be refused
    under fallback unless --replace-canonical is also given."""
    data, canonical = workspace
    pdfs = _pdf_dir(tmp_path, ["1001_2019"])
    with pytest.raises(SystemExit):
        cs.main(["--pdf-dir", str(pdfs), "--allow-llm-fallback",
                 "--out", str(canonical)])
    assert canonical.read_text(encoding="utf-8") == SENTINEL
    # any other explicit path is fine, and the canonical file stays untouched
    other = tmp_path / "elsewhere.json"
    assert cs.main(["--pdf-dir", str(pdfs), "--allow-llm-fallback",
                    "--out", str(other)]) == 0
    assert other.exists() and canonical.read_text(encoding="utf-8") == SENTINEL
    # and with complete coverage --out at the canonical name is an ordinary write
    full = _pdf_dir(tmp_path, ["1001_2019", "1002_2020"])
    assert cs.main(["--pdf-dir", str(full), "--out", str(canonical)]) == 0
    assert json.loads(canonical.read_text(encoding="utf-8"))["fallback_mode"] is False


def test_no_machine_specific_path_survives_in_code_or_documents():
    for rel in ("src/currency_scan.py", "docs/fx-conversion.md",
                "docs/data-provenance.md"):
        text = io.open(os.path.join(HERE, rel), encoding="utf-8").read().lower()
        assert "d:/dev/" not in text and "d:\\dev\\" not in text, rel


def test_documents_name_the_configuration_mechanism():
    doc = io.open(os.path.join(HERE, "docs", "fx-conversion.md"), encoding="utf-8").read()
    assert "--pdf-dir" in doc and cs.ENV_VAR in doc
    assert "syndicate_reports/pdfs/" in doc
    prov = io.open(os.path.join(HERE, "docs", "data-provenance.md"), encoding="utf-8").read()
    assert "syndicate_reports/pdfs/" in prov
    assert "--pdf-dir" in cs.__doc__ and cs.ENV_VAR in cs.__doc__
