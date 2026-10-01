r"""The syndicate inception table's corrections (data/syndicate_inception_years.json; round 62, fourth cycle).

The table says it was populated automatically, from claims development triangles with unknown syndicates looked
up through an API service. It gave Syndicate 2014's first underwriting year as 2009, and the syndicate's own filing
says it commenced underwriting at Lloyd's on 1 January 2014 (the extraction's structural eligibility audit read
it). Every correction is recorded under _manual_overrides with the filing's words, page and file hash; the test
holds each correction to the table and to the extraction's own reading of the filing.

Run:  python -m pytest src/test_inception_years.py -q
"""
import io
import json
import os

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _load(*parts):
    return json.load(io.open(os.path.join(HERE, *parts), encoding="utf-8"))


def test_each_correction_is_the_tables_value_and_the_filings_words():
    table = _load("data", "syndicate_inception_years.json")
    audit = {r["file"]: r for r in _load("pdf_extraction", "audit", "structural_eligibility_audit.json")["records"]}
    overrides = table["_manual_overrides"]
    assert [o["syndicate"] for o in overrides] == ["2014"] and table["2014"] == 2014
    for o in overrides:
        assert table[o["syndicate"]] == o["now"] != o["was"], o["syndicate"]
        # the filing's words, page and hash are the extraction's own reading of the same file
        record = audit["syndicate_%s_%d.json" % (o["syndicate"], o["now"])]
        assert record["source_sha256"] == o["source_sha256"]
        assert any(s["page"] == o["source_page"] and s["page_printed"] == o["source_page_printed"]
                   and o["quote"] in s["quote"] for s in record["start_statements"]), o["syndicate"]
        assert str(o["now"]) in o["quote"]
