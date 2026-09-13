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
