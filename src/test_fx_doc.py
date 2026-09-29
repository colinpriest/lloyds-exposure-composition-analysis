"""Round 54 (review D05, D06): the FX guide's counts are the files' counts.

The guide said 6,644 daily observations to the present after the stored series was
bounded at 2025-12-31 (6,518), and listed provenance methods 588 + 65 + 14 + 240 = 907
against a corpus of 908. Both statements are recomputed here from the committed files.

Run:  python -m pytest src/test_fx_doc.py -q
"""
import io
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)


def _load(rel):
    return json.load(io.open(os.path.join(ROOT, rel), encoding="utf-8"))


def _doc():
    return io.open(os.path.join(ROOT, "docs", "fx-conversion.md"), encoding="utf-8").read()


def test_series_bound_and_count_are_the_files():
    fx = _load("model/fx_rates_h10.json")
    doc = _doc()
    end = fx["source"].get("series_end") or max(fx["daily_series"])
    assert end in doc
    assert "{:,} daily observations".format(fx["n_daily_observations"]) in doc
    assert fx["n_daily_observations"] == len(fx["daily_series"])
    assert max(fx["daily_series"]) <= end


def test_provenance_method_counts_sum_to_the_corpus():
    scan = _load("pdf_extraction/currency_scan.json")
    res = _load("model/exposure_results.json")
    keys = ["%d_%d" % (o["syndicate"], o["year"]) for o in res["observations"]]
    methods, cur = {}, {}
    for k in keys:
        r = scan["reports"].get(k) or {}
        m = (r.get("provenance") or {}).get("method")
        methods[m] = methods.get(m, 0) + 1
        cur[r.get("currency")] = cur.get(r.get("currency"), 0) + 1
    doc = " ".join(_doc().split())
    # the guide states how many corpus records the scan left undetermined, "none" being zero (round 56:
    # four scanned filings the scan could not read entered the corpus)
    m = re.search(r"Within the (\d+)-observation analysis corpus: \*\*(\d+) GBP, (\d+) USD \((\d+)%\)\*\*, (none|\d+) undetermined\. Provenance methods: (\d+) presentational statements, (\d+) unit-header, (\d+) functional-statement, (\d+) LLM-field", doc)
    assert m, "the corpus sentence is in the guide"
    n, gbp, usd, pct = (int(x) for x in m.groups()[:4])
    undetermined = 0 if m.group(5) == "none" else int(m.group(5))
    p_s, u_h, f_s, llm = (int(x) for x in m.groups()[5:])
    assert n == len(keys)
    assert (gbp, usd, undetermined) == (cur.get("GBP", 0), cur.get("USD", 0), cur.get("UNDETERMINED", 0))
    assert pct == round(100.0 * usd / n)
    assert (p_s, u_h, f_s, llm) == tuple(methods.get(k, 0) for k in
                                         ("presentational_statement", "unit_headers", "functional_statement", "llm_field"))
    assert p_s + u_h + f_s + llm + undetermined == n


def test_an_undetermined_currency_in_the_corpus_is_one_both_models_read_as_gbp():
    """The loader applies an undetermined currency as GBP, with no conversion (run_analysis). That is safe
    only for a report presented in sterling. So every corpus record the scan left undetermined must be read
    as GBP by every extraction model (round 56: four such records entered the corpus after the scan)."""
    scan = _load("pdf_extraction/currency_scan.json")
    res = _load("model/exposure_results.json")
    keys = ["%d_%d" % (o["syndicate"], o["year"]) for o in res["observations"]]
    undetermined = [k for k in keys if (scan["reports"].get(k) or {}).get("currency") == "UNDETERMINED"]
    checked, wrong = 0, []
    for k in undetermined:
        models = _load("pdf_extraction/syndicate_%s.json" % k).get("models") or {}
        read = sorted({str((mb or {}).get("currency")) for mb in models.values()})
        checked += 1
        if read != ["GBP"]:
            wrong.append((k, read))
    assert checked == len(undetermined)
    assert not wrong, "an undetermined currency is applied as GBP to records whose models read otherwise: %s" % wrong


def _corpus_keys():
    return ["%d_%d" % (o["syndicate"], o["year"]) for o in _load("model/exposure_results.json")["observations"]]


def test_the_outcome_counts_are_the_scans_and_the_undetermined_have_no_model_reading():
    """Round 62: the guide's outcome line stood at 743 / 280 / 42 against a scan that had not been rerun since
    July, while the records it describes had changed three times. The counts are the committed scan's, and the
    undetermined reports are the no-model files the guide says they are (none of them in the corpus)."""
    scan = _load("pdf_extraction/currency_scan.json")
    doc = " ".join(_doc().split())
    m = re.search(r"\*\*Outcome \(([0-9,]+) reports\):\*\* (\d+) GBP, (\d+) USD, (\d+) undetermined\. The (\d+) are "
                  r"no-model files \(no extraction model read them\) that never enter the analysis dataset; none is "
                  r"in the analysis corpus", doc)
    assert m, "the outcome sentence is in the guide"
    n, gbp, usd, und, und_again = int(m.group(1).replace(",", "")), *(int(x) for x in m.groups()[1:])
    counts = scan["counts"]
    assert (n, gbp, usd, und) == (scan["n_reports"], counts.get("GBP", 0), counts.get("USD", 0),
                                  counts.get("UNDETERMINED", 0))
    assert und_again == und == len(scan["undetermined"])
    read = [k for k in scan["undetermined"]
            if _load("pdf_extraction/syndicate_%s.json" % k).get("models")]
    assert not read, "undetermined reports that an extraction model did read: %s" % read
    assert not set(scan["undetermined"]) & set(_corpus_keys())


def test_the_html_only_filings_named_take_the_currency_the_guide_gives():
    """Round 62: the eight 2024 filings published only as HTML that the re-extraction read take the models'
    field, the currency the guide names for each."""
    scan = _load("pdf_extraction/currency_scan.json")["reports"]
    doc = " ".join(_doc().split())
    m = re.search(r"the scan takes the models' field: USD for ((?:\d+, )*\d+) and (\d+), GBP for ((?:\d+, )*\d+) "
                  r"and (\d+)\.", doc)
    assert m, "the sentence naming the eight filings is in the guide"
    named = {}
    for group, cur in ((m.group(1).split(", ") + [m.group(2)], "USD"), (m.group(3).split(", ") + [m.group(4)], "GBP")):
        for syn in group:
            named["%s_2024" % syn] = cur
    assert len(named) == 8
    for key, cur in named.items():
        entry = scan[key]
        assert entry["currency"] == cur, key
        assert entry["provenance"]["method"] == "llm_field", key
        assert "PDF scan unusable: pdf_missing" in entry["provenance"]["quote"], key


def test_the_llm_field_breakdown_is_the_corpus():
    """The corpus sentence splits the LLM-field count by why the scan could not decide."""
    scan = _load("pdf_extraction/currency_scan.json")["reports"]
    doc = " ".join(_doc().split())
    m = re.search(r"(\d+) LLM-field \((\d+) scanned PDFs, (\d+) filings published only as HTML, (\d+) PDFs whose text "
                  r"matched no pattern\)", doc)
    assert m, "the LLM-field breakdown is in the guide"
    total, scanned, html, nomatch = (int(x) for x in m.groups())
    why = {}
    for k in _corpus_keys():
        prov = scan[k].get("provenance") or {}
        if prov.get("method") == "llm_field":
            reason = re.search(r"PDF scan unusable: ([a-z_]+)", prov["quote"]).group(1)
            why[reason] = why.get(reason, 0) + 1
    assert (scanned, html, nomatch) == (why.get("no_text_layer", 0), why.get("pdf_missing", 0),
                                        why.get("no_pattern_matched", 0))
    assert total == scanned + html + nomatch == sum(why.values())


def test_the_usd_share_by_year_is_the_corpus():
    """The guide's first and last years' USD shares are the corpus's (43% before round 62's entrants, 44% after),
    by the currency each observation was loaded in."""
    doc = " ".join(_doc().split())
    m = re.search(r"The USD share rises from (\d+)% of observations in (\d{4}) to (\d+)% in (\d{4})\.", doc)
    assert m, "the USD-share sentence is in the guide"
    by_year = {}
    for o in _load("model/exposure_results.json")["observations"]:
        n, usd = by_year.get(int(o["year"]), (0, 0))
        by_year[int(o["year"])] = (n + 1, usd + (o["report_currency"] == "USD"))
    first, last = int(m.group(2)), int(m.group(4))
    assert (first, last) == (min(by_year), max(by_year))
    for pct, year in ((int(m.group(1)), first), (int(m.group(3)), last)):
        n, usd = by_year[year]
        assert pct == round(100.0 * usd / n), (year, pct, usd, n)
