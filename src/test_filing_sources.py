"""Filing format provenance includes HTML and is generated from extraction metadata."""
import json
from pathlib import Path
import re

import pytest

import build_current_results as bcr
import filing_sources
import generate_data_audit as audit

ROOT = Path(__file__).resolve().parent.parent


def test_metadata_classification_and_unknown_are_explicit(tmp_path):
    source_values = [r"syndicate_reports\\pdfs\\a.PDF", "a.html", "folder/b.HTM", "report.xml", None]
    paths = []
    for i, value in enumerate(source_values):
        path = tmp_path / (str(i) + ".json")
        path.write_text(json.dumps({"source_file": value}), encoding="utf-8")
        paths.append(path)
    counts = filing_sources.count_sources(paths)
    assert counts == {"PDF": 1, "HTML": 2, "unknown": 2}
    assert filing_sources.format_counts(counts) == "1 PDF, 2 HTML and 2 unknown format"
    row = bcr.source_format_row(paths)
    assert "5 records: 1 PDF, 2 HTML and 2 unknown format" in row
    with pytest.raises(ValueError, match="no extraction records"):
        bcr.source_format_row([])
    with pytest.raises(ValueError, match="exactly one"):
        bcr.source_format_text("no row", paths)
    with pytest.raises(ValueError, match="exactly one"):
        bcr.source_format_text(row + "\n" + row, paths)


def test_current_records_and_generated_documents_agree():
    paths = sorted((ROOT / "pdf_extraction").glob("syndicate_*_[0-9][0-9][0-9][0-9].json"))
    counts = filing_sources.count_sources(paths)
    assert len(paths) == 1065
    assert counts == {"PDF": 970, "HTML": 95}
    assert audit.mine_raw()["source_formats"] == counts
    appendix = (ROOT / "docs/appendix-data-audit.md").read_text(encoding="utf-8")
    provenance = (ROOT / "docs/data-provenance.md").read_text(encoding="utf-8")
    assert "1,065 records: 970 PDF and 95 HTML" in bcr.source_format_row(paths)
    assert bcr.source_format_row(paths) in provenance
    assert "970 PDF and 95 HTML source documents" in appendix
    assert "The 2024 HTML accounts use inline XBRL" in appendix
    assert "Raw PDFs retrieved" not in appendix
    assert "retrieved PDFs;" not in appendix
    assert not re.search(r"\b(?:1065|1,065)\s+(?:retrieved\s+)?PDFs\b", appendix + provenance)
