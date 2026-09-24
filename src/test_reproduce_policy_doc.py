r"""What README.md promises about reproduction is what reproduce.py does (frozen review of 24 September 2026, D01).

The README said the verifier excludes "the three documented volatile fields" and compares every binary "byte for
byte". It excludes five -- the vignette metadata also records the run's own commit and time -- and a workbook is
compared on its members' names and contents in name order, without docProps/core.xml and without the zip entries'
own metadata. Nothing bound the sentences to the code, so the promise stayed at three keys through two rounds that
added two.

These tests read the README's own words and the verifier's own behaviour: a field added to VOLATILE, or a count
left at "three", fails here rather than in a reader's hands. The workbook cases are behavioural, not textual: two
workbooks that differ only in when they were written, or in the order their members are stored, hash alike, and one
whose cell changed does not.

Run:  python -m pytest src/test_reproduce_policy_doc.py -q
"""
import io
import os
import re
import sys
import zipfile

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
import reproduce  # noqa: E402

README = os.path.join(HERE, "README.md")
NUMBER_WORD = {1: "one", 2: "two", 3: "three", 4: "four", 5: "five", 6: "six", 7: "seven", 8: "eight"}


def _readme(path=README):
    with io.open(path, encoding="utf-8") as fh:
        return " ".join(fh.read().split())


def test_the_readme_names_every_volatile_field_and_counts_them(path=README):
    """The listing sentence: the count word and the backticked names are the VOLATILE tuple."""
    text = _readme(path)
    word = NUMBER_WORD[len(reproduce.VOLATILE)]
    m = re.search(r"as canonical JSON after excluding the (\w+) documented volatile fields \(([^)]*)\)", text)
    assert m, "the README no longer states the volatile-field policy where the verifier is described"
    assert m.group(1) == word, "the README says %r volatile fields; reproduce.py excludes %d" % (m.group(1),
                                                                                                len(reproduce.VOLATILE))
    named = set(re.findall(r"`([A-Za-z_]+)`", m.group(2)))
    assert named == set(reproduce.VOLATILE), "the README lists %s; VOLATILE is %s" % (sorted(named),
                                                                                      sorted(reproduce.VOLATILE))


def test_the_readme_repeats_the_same_count_where_it_explains_git_status(path=README):
    text = _readme(path)
    word = NUMBER_WORD[len(reproduce.VOLATILE)]
    assert ("`--verify` excludes exactly those %s fields" % word) in text, \
        "the second passage does not say %r fields" % word
    for field in reproduce.VOLATILE:
        assert ("`%s`" % field) in text, "the README never names `%s`" % field


def test_the_readme_describes_the_workbook_comparison_where_it_promises_byte_comparison(path=README):
    """"Byte for byte" is not true of a workbook, and the sentence that says so must say which members are read."""
    text = _readme(path)
    assert "except the vignette workbooks" in text
    assert "members' names and contents, in name order" in text
    assert "docProps/core.xml" in text
    assert "without the zip entries' own metadata" in text


def _workbook(members, when=(2026, 9, 24, 12, 0, 0)):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for name, data in members:
            z.writestr(zipfile.ZipInfo(name, date_time=when), data)
    return buf.getvalue()


CELLS = ("xl/worksheets/sheet1.xml", b"<sheetData><row><c><v>1</v></c></row></sheetData>")
OTHER = ("xl/workbook.xml", b"<workbook/>")


def test_a_workbook_hashes_alike_when_only_its_write_time_or_member_order_differs():
    a = _workbook([("docProps/core.xml", b"<created>2026-09-24T12:00:00Z</created>"), CELLS, OTHER])
    b = _workbook([OTHER, CELLS, ("docProps/core.xml", b"<created>2026-09-25T23:59:59Z</created>")],
                  when=(2026, 9, 25, 23, 59, 58))
    assert a != b
    assert reproduce.output_bytes_for_hash("vignettes/v/workings.xlsx", a) == \
           reproduce.output_bytes_for_hash("vignettes/v/workings.xlsx", b)


def test_a_workbook_whose_cell_changed_does_not_hash_alike():
    a = _workbook([("docProps/core.xml", b"<created>2026-09-24T12:00:00Z</created>"), CELLS, OTHER])
    b = _workbook([("docProps/core.xml", b"<created>2026-09-24T12:00:00Z</created>"),
                   (CELLS[0], b"<sheetData><row><c><v>2</v></c></row></sheetData>"), OTHER])
    assert reproduce.output_bytes_for_hash("vignettes/v/workings.xlsx", a) != \
           reproduce.output_bytes_for_hash("vignettes/v/workings.xlsx", b)


def test_a_binary_that_is_not_a_workbook_is_still_compared_byte_for_byte():
    data = b"\x93NUMPY\x01\x00 some bytes"
    assert reproduce.output_bytes_for_hash("model/draws.npz", data) == data
    assert reproduce.output_bytes_for_hash("figures/f.pdf", data) == data
