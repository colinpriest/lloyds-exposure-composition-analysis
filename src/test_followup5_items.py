"""The deferred analysis items 6 to 8 of FOLLOWUP5 (recorded 1 October 2026, done in stage 3 of the fix cycle).

6. check_outbound_transfer_sensitivity.py's docstring named one confirmed record outside the sample; four are.
7. The provenance note typed "~90-95 PDFs retrieved per year vs ~91-99 active syndicates"; it is generated now, and
   7b, the lowest non-2014 coverage was truncated (2021's 57.6% printed as 57%) and is rounded.
8. The round-55 block's "What it did to the counts" compared the pinned commit with today, which mixes in every
   later rule and import; the lead-in now says what it compares.

Items 9 and 10 are tested in src/test_no_mature_cohort.py.

Run:  python -m pytest src/test_followup5_items.py -q
"""
import csv
import io
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(HERE, "src"))
import build_current_results as bcr  # noqa: E402
import check_outbound_transfer_sensitivity as cots  # noqa: E402


def _exposure():
    return json.load(io.open(os.path.join(HERE, "model", "exposure_results.json"), encoding="utf-8"))


def test_the_outbound_docstring_names_every_confirmed_record_outside_the_sample():
    with io.open(os.path.join(HERE, "data", "outbound_transfer_retained_base.json"), encoding="utf-8") as fh:
        confirmed = json.load(fh)["confirmed"]
    with io.open(os.path.join(HERE, "results", "disposition_ledger.csv"), encoding="utf-8") as fh:
        disp = {r["file"]: r["disposition"] for r in csv.DictReader(fh)}
    outside = sorted((k for k in confirmed if not disp["syndicate_%s.json" % k].startswith("CORPUS:")),
                     key=lambda k: tuple(int(x) for x in k.split("_")))
    doc = " ".join(cots.__doc__.split())
    assert "Four of the six confirmed records are outside it" in doc and len(outside) == 4 and len(confirmed) == 6
    for key in outside:
        assert key.replace("_", "/") in doc, key


def test_the_coverage_lines_generate_the_retrieval_range_and_round_the_rates():
    ex = _exposure()
    text = " ".join(bcr.coverage_lines(ex))
    assert "~" not in text[text.index("The 2020\u20132024 retrieval"):]     # "~47 %" is the old dataset's
    got, active = bcr._retrieved_by_year(), bcr._active_by_year()
    recent = range(2020, 2025)
    assert ("%d–%d PDFs retrieved per year in 2020–2024 vs %d–%d active syndicates"
            % (min(got[y] for y in recent), max(got[y] for y in recent),
               min(active[y] for y in recent), max(active[y] for y in recent))) in text
    samp = bcr._sample_by_year(ex)
    rates = {y: 100.0 * samp[y] / active[y] for y in samp}
    worst = min(rates, key=rates.get)
    mid = [r for y, r in rates.items() if y != worst]
    assert "every other year between %d %% and %d %%" % (round(min(mid)), round(max(mid))) in text
    assert sum(got.values()) == 1065


def test_the_data_audit_generates_its_retrieval_range():
    src = io.open(os.path.join(HERE, "src", "generate_data_audit.py"), encoding="utf-8").read()
    assert "~90" not in src and "~91" not in src
    assert re.search(r"\{min\(raw_years\)\}.\{max\(raw_years\)\} PDFs/year throughout", src)


def test_the_round_55_table_says_what_it_compares():
    text = " ".join(bcr.correction_lines(_exposure()))
    assert "What it did to the counts" not in text
    assert "The change is not the correction's alone" in text
