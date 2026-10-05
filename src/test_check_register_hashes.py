"""src/check_register_hashes.py: the PC check that every source_file a register names hashes to its source_sha256, and
that every quote a register holds is on the page it cites.

The filings are not in this repository, so no test compares the committed registers with them (a test that skipped
without them would be no test); this holds the check's own logic, on synthetic files and a synthetic PDF, that it covers
the evidence registers and the run-off registers, that no register string holds U+FFFD, and that it is not in the
manifest.

Run:  python -m pytest src/test_check_register_hashes.py -q
"""
import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(HERE, "src"))
sys.path.insert(0, HERE)
import check_register_hashes as CH  # noqa: E402


def _register(tmp_path, name, source, sha):
    path = tmp_path / name
    path.write_text(json.dumps({"_purpose": "x", "1_2020": {"source_file": source, "source_sha256": sha},
                                "2_2020": {"quote": "an entry without a source is not checked"}}), encoding="utf-8")
    return path


def test_a_matching_file_is_ok_and_a_wrong_hash_or_a_missing_file_is_named(tmp_path):
    (tmp_path / "f").mkdir()
    good = tmp_path / "f" / "a.pdf"
    good.write_bytes(b"filing a")
    sha = hashlib.sha256(b"filing a").hexdigest()
    ok = _register(tmp_path, "ok.json", "a.pdf", sha)
    assert CH.check(tmp_path / "f", [ok]) == [("ok.json", "1_2020", "ok", CH.check(tmp_path / "f", [ok])[0][3])]
    bad = _register(tmp_path, "bad.json", "a.pdf", "0" * 64)
    assert CH.check(tmp_path / "f", [bad])[0][2] == "mismatch"
    gone = _register(tmp_path, "gone.json", "b.pdf", sha)
    row = CH.check(tmp_path / "f", [gone])[0]
    assert row[2] == "missing" and "b.pdf" in row[3]


def test_main_exits_nonzero_on_a_mismatch_or_a_missing_file_and_zero_otherwise(tmp_path, monkeypatch, capsys):
    (tmp_path / "f").mkdir()
    (tmp_path / "f" / "a.pdf").write_bytes(b"filing a")
    sha = hashlib.sha256(b"filing a").hexdigest()
    good = _register(tmp_path, "good.json", "a.pdf", sha)
    monkeypatch.setattr(CH, "AUDIT_REGISTERS", ())
    monkeypatch.setattr(CH, "REGISTERS", (good,))
    assert CH.main([str(tmp_path / "f")]) == 0
    assert "1 source files checked" in capsys.readouterr().out
    monkeypatch.setattr(CH, "REGISTERS", (_register(tmp_path, "bad.json", "a.pdf", "1" * 64),))
    assert CH.main([str(tmp_path / "f")]) == 1 and "MISMATCH" in capsys.readouterr().out
    monkeypatch.setattr(CH, "REGISTERS", (_register(tmp_path, "gone.json", "zzz.pdf", sha),))
    assert CH.main([str(tmp_path / "f")]) == 1 and "MISSING" in capsys.readouterr().out
    monkeypatch.setattr(CH, "REGISTERS", ())
    assert CH.main([str(tmp_path / "f")]) == 1, "no entries checked is not a pass"


def test_it_covers_the_evidence_registers_and_the_run_off_registers_and_is_not_in_the_manifest():
    names = {p.name for p in CH.REGISTERS}
    assert names == {"composition_page_readings.json", "eligibility_from_filing.json"}
    counts = {p.name: len(CH.entries(p)) for p in CH.REGISTERS}
    assert counts == {"composition_page_readings.json": 76, "eligibility_from_filing.json": 3}
    # the extraction's run-off registers keep their entries in a "records" list: every record is covered
    counts = {p.name: len(CH.entries(p)) for p in CH.AUDIT_REGISTERS}
    assert counts == {"runoff_corpus_register.json": 111, "runoff_register.json": 8}
    for p in CH.AUDIT_REGISTERS:
        with open(p, encoding="utf-8") as fh:
            records = json.load(fh)["records"]
        assert len(CH.entries(p)) == len(records), p.name
        assert all(len(e["source_sha256"]) == 64 for e in CH.entries(p).values()), p.name
    import reproduce
    assert "check_register_hashes.py" not in [s for s, _stage, _m in reproduce.STEPS]


def test_a_run_off_register_hash_mismatch_makes_main_fail(tmp_path, monkeypatch, capsys):
    """main() checks the run-off registers' hashes too (a register of {"records": [...]})."""
    (tmp_path / "f").mkdir()
    (tmp_path / "f" / "a.pdf").write_bytes(b"filing a")
    sha = hashlib.sha256(b"filing a").hexdigest()
    ev = _register(tmp_path, "ev.json", "a.pdf", sha)

    def runoff(sha_):
        p = tmp_path / "runoff.json"
        p.write_text(json.dumps({"records": [{"stem": "syndicate_1_2020", "source_file": "a.pdf",
                                              "source_sha256": sha_}]}), encoding="utf-8")
        return p

    monkeypatch.setattr(CH, "REGISTERS", (ev,))
    monkeypatch.setattr(CH, "AUDIT_REGISTERS", (runoff(sha),))
    assert CH.main([str(tmp_path / "f")]) == 0 and "2 source files checked" in capsys.readouterr().out
    monkeypatch.setattr(CH, "AUDIT_REGISTERS", (runoff("2" * 64),))
    assert CH.main([str(tmp_path / "f")]) == 1 and "runoff.json syndicate_1_2020: MISMATCH" in capsys.readouterr().out


def test_fragments_and_the_remainder_of_a_quote():
    q = "PDF p6 (printed 4): 'The principal activity is life business at Lloyd's.' 2017 $'000: 'MGA Insurance 126,610'; total 330,544"
    assert CH.fragments(q) == ["The principal activity is life business at Lloyd's.", "MGA Insurance 126,610"]
    assert CH.fragments("'a ... much longer fragment of the page'; 'ab'") == ["much longer fragment of the page"]
    # citations and quoted page text only: nothing left
    assert CH.remainder("PDF p25: 'First page text here.'; 'Second.' PDF p149 and p150: 'Third.'") == ""
    assert CH.remainder("(PDF p11-12) 'Technical account'") == ""
    # any label, unit or annotation of the reading's own is left over, and so is a bare figure
    assert CH.remainder(q) == "2017 thousand total 330 544"
    assert CH.remainder("Income statement 'Technical account' (PDF p10)") == "Income statement"
    assert CH.remainder("PDF p5: 'text of the page' only") == "only"


def _pdf(path, pages):
    import fitz
    d = fitz.open()
    for text in pages:
        pg = d.new_page()
        if text:
            pg.insert_text((72, 100), text, fontsize=11)
    d.save(str(path))
    d.close()


def _entry(source, pages, quote):
    return {"source_file": source, "source_sha256": "0" * 64, "pages": pages, "quote": quote}


def test_a_quote_is_found_only_on_the_page_it_cites_after_normalising(tmp_path):
    """A text-layer page: found (whatever the case, spacing or dashes) is ok; a sentence that is on another page is a
    failure, so a quote cannot cite a page that does not hold it."""
    (tmp_path / "f").mkdir()
    _pdf(tmp_path / "f" / "a.pdf", ["Cover page of the report with its title and the year", "Life insurance 92 % Life reinsurance 8 % Total 100 %"])
    reg = tmp_path / "r.json"

    def run(pages, quote):
        reg.write_text(json.dumps({"1_2020": _entry("a.pdf", pages, quote)}), encoding="utf-8")
        return [s for _r, _k, _f, s in CH.check_quotes(tmp_path / "f", [reg])]

    assert run([2], "PDF p2: 'Life insurance 92%'; 'Life reinsurance 8%'") == ["ok", "ok"]
    assert run([2], "'LIFE  insurance - 92 %'") == ["ok"]
    assert run([1], "'Life insurance 92%'") == ["not_found"], "the figure is on page 2, not on the cited page 1"
    assert run([2], "'Life insurance 99%'") == ["not_found"]
    assert run([2], "'Gross premiums written by underwriting team'") == ["not_found"]
    assert run([2], "no quoted text at all") == []


def test_a_quote_on_an_html_filing_is_looked_for_in_its_text(tmp_path):
    (tmp_path / "f").mkdir()
    (tmp_path / "f" / "a.html").write_text("<html><body><p>The principal activity of the <b>Syndicate</b> is "
                                           "life&nbsp;business.</p><script>var x = 'hidden script text';</script></body></html>",
                                           encoding="utf-8")
    reg = tmp_path / "r.json"
    reg.write_text(json.dumps({"1_2020": _entry("a.html", [], "'The principal activity of the Syndicate is life business.'; "
                                                               "'hidden script text'; 'some other sentence here'")}), encoding="utf-8")
    assert [s for _r, _k, _f, s in CH.check_quotes(tmp_path / "f", [reg])] == ["ok", "not_found", "not_found"]


def test_an_image_page_is_read_from_the_ocr_cache_and_a_miss_there_is_for_the_eye(tmp_path):
    """A page the extraction OCR-read is an image page: a fragment found in the OCR text is ok_ocr, one not found is
    not_found_ocr (reported to be read by eye, not a failure); a text-layer page's miss stays a failure."""
    (tmp_path / "f" / "pdf_extraction" / "ocr_page_cache").mkdir(parents=True)
    _pdf(tmp_path / "f" / "a.pdf", ["Header only of the page, not the body text"])
    (tmp_path / "f" / "pdf_extraction" / "ocr_page_cache" / "a.json").write_text(
        json.dumps([{"page": "1", "text": "Report of the directors\nThe Syndicate wrote 78.2m of premium during 2016."}]),
        encoding="utf-8")
    reg = tmp_path / "r.json"
    reg.write_text(json.dumps({"1_2020": _entry("a.pdf", [1], "'The Syndicate wrote 78.2m of premium during 2016.'; "
                                                               "'Header only of the page'; 'a sentence the page lacks'")}),
                   encoding="utf-8")
    assert [s for _r, _k, _f, s in CH.check_quotes(tmp_path / "f", [reg])] == ["ok_ocr", "ok_ocr", "not_found_ocr"]


def test_the_digit_font_of_some_filings_is_decoded():
    """6117/2021 p24 prints 84.0 as U+0D69 U+0D65 U+0011 U+0D61 (a font that maps digits to Malayalam letters)."""
    garbled = "Reinsurance acceptances \n" + chr(0x0D69) + chr(0x0D65) + "\x11" + chr(0x0D61)
    assert CH.norm(garbled) == CH.norm("Reinsurance acceptances 84.0")


def test_a_damaged_character_in_a_register_fails_the_check(tmp_path, monkeypatch, capsys):
    (tmp_path / "f").mkdir()
    (tmp_path / "f" / "a.pdf").write_bytes(b"filing a")
    sha = hashlib.sha256(b"filing a").hexdigest()
    good = _register(tmp_path, "good.json", "a.pdf", sha)
    dmg = tmp_path / "dmg.json"
    dmg.write_text(json.dumps({"1_2020": {"source_file": "a.pdf", "source_sha256": sha,
                                          "quote": "'gross written premium of \ufffd28.4m'"}}), encoding="utf-8")
    assert CH.damaged([good]) == [] and CH.damaged([dmg]) == [("dmg.json", "1_2020", "quote")]
    monkeypatch.setattr(CH, "AUDIT_REGISTERS", ())
    monkeypatch.setattr(CH, "REGISTERS", (dmg,))
    monkeypatch.setattr(CH, "check_quotes", lambda *a, **k: [])
    assert CH.main([str(tmp_path / "f")]) == 1 and "U+FFFD in quote" in capsys.readouterr().out


def test_no_committed_register_or_result_file_holds_a_damaged_character():
    """U+FFFD is what a bad decode leaves where a pound sign was (6118/2016's quotes were reported to hold it). The
    committed registers, the data files and the audit registers must decode as UTF-8 and hold none."""
    import glob
    paths = (glob.glob(os.path.join(HERE, "data", "*.json")) + glob.glob(os.path.join(HERE, "pdf_extraction", "audit", "*.json"))
             + [str(p) for p in CH.REGISTERS])
    assert len(paths) > 5
    for path in paths:
        with open(path, "rb") as fh:
            text = fh.read().decode("utf-8")
        assert "\ufffd" not in text, path
    # and the pound sign is there where the page prints one
    with open(os.path.join(HERE, "data", "composition_page_readings.json"), encoding="utf-8") as fh:
        reg = json.load(fh)
    assert "\u00a328.4m" in reg["6118_2016"]["quote"] and "\u00a378.2m" in reg["6118_2016"]["quote"]


def test_main_fails_on_a_quote_not_found_on_a_text_layer_page_but_not_on_one_for_the_eye(tmp_path, monkeypatch, capsys):
    (tmp_path / "f").mkdir()
    (tmp_path / "f" / "a.pdf").write_bytes(b"filing a")
    sha = hashlib.sha256(b"filing a").hexdigest()
    monkeypatch.setattr(CH, "AUDIT_REGISTERS", ())
    monkeypatch.setattr(CH, "REGISTERS", (_register(tmp_path, "good.json", "a.pdf", sha),))
    for status, code in (("ok", 0), ("ok_ocr", 0), ("not_found_ocr", 0), ("not_found", 1), ("no_text", 1)):
        monkeypatch.setattr(CH, "check_quotes", lambda *a, _s=status, **k: [("good.json", "1_2020", "a fragment", _s)])
        assert CH.main([str(tmp_path / "f")]) == code, status
        out = capsys.readouterr().out
        assert "1 quote fragments" in out
        assert ("NOT_FOUND_OCR" in out or "OK_OCR" in out) == (status in ("ok_ocr", "not_found_ocr")), status
