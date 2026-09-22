"""No pool VaR is read any way but pool_quantile.var_q (frozen review of 21 September 2026, M04).

The Bayesian-bootstrap replicates interpolated between weighted plotting positions and the point
estimates used numpy's type 7; neither is a quantile of the scenario distribution the manuscript
states. Both now go through pool_quantile.var_q, and so does every other pool VaR. This test parses
every producer and fails on a numpy percentile or quantile taken at a VaR level (99, 99.5, 0.99,
0.995, an alpha, or a probability times 100), so a new script cannot quietly read a VaR by another
rule. An exception names its file, its enclosing function and the call, with the reason it is not a
VaR of a scenario pool; a text-only key would hide the same call anywhere else in the file.
"""
import ast
import io
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))

FUNCS = {"percentile", "quantile", "nanpercentile", "nanquantile"}
VAR_LEVEL = re.compile(r"(?<![\d.])(?:99(?:\.5)?|0?\.99(?:5)?)(?![\d])|\balpha\b|\bALPHA\b|\bALPHAS\b"
                       r"|\*\s*100(?:\.0)?\b|\b100(?:\.0)?\s*\*")

#: (file, enclosing function, call) -> why it is not a pool VaR
ALLOWED = {
    ("run_analysis.py", "weighted_quantile", "np.percentile(values, tau * 100)"):
        "a kernel-weighted conditional quantile for the smoothing bands, not a VaR of a scenario pool",
}


def offenders(name, text, allowed=None):
    """(file, function, call) for every numpy percentile or quantile taken at a VaR level."""
    allowed = ALLOWED if allowed is None else allowed
    tree = ast.parse(text)
    out = []

    def visit(node, where):
        for child in ast.iter_child_nodes(node):
            inner = child.name if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)) else where
            if (isinstance(child, ast.Call) and isinstance(child.func, ast.Attribute)
                    and child.func.attr in FUNCS and len(child.args) > 1):
                level = ast.get_source_segment(text, child.args[1]) or ""
                call = ast.get_source_segment(text, child) or ""
                if VAR_LEVEL.search(level) and (name, where, call) not in allowed:
                    out.append((name, where, call))
            visit(child, inner)

    visit(tree, "<module>")
    return out


def _sources():
    for fn in sorted(os.listdir(HERE)):
        if fn.endswith(".py") and not fn.startswith("test_") and fn != "pool_quantile.py":
            yield fn, io.open(os.path.join(HERE, fn), encoding="utf-8").read()


def test_the_scan_sees_the_forms_a_var_was_read_in():
    planted = ("np.percentile(x, 99.5)\n"
               "np.percentile(z * sig_q, 100.0 * alpha, method='linear')\n"
               "np.quantile(samp, ALPHA)\n"
               "float(np.percentile(Sadj[keep], 99.0))\n"
               "def var(a, p):\n    return float(np.percentile(a, 100 * p, method=Q))\n")
    assert len(offenders("planted.py", planted)) == 5


def test_an_exception_covers_one_function_only():
    planted = "def elsewhere(values, tau):\n    return np.percentile(values, tau * 100)\n"
    assert offenders("run_analysis.py", planted) == [
        ("run_analysis.py", "elsewhere", "np.percentile(values, tau * 100)")]


def test_the_scan_leaves_thresholds_and_draw_summaries_alone():
    fine = ("np.percentile(draws, [2.5, 97.5])\n"
            "np.percentile(sample, uq, method='linear')\n"
            "np.percentile(arr, 75)\n"
            "np.percentile(R, np.linspace(0, 100, 21))\n")
    assert offenders("fine.py", fine) == []


def test_no_producer_reads_a_var_by_another_rule():
    found = [o for fn, text in _sources() for o in offenders(fn, text)]
    assert found == [], found


def test_every_exception_is_still_there():
    """An exception that no longer matches anything is stale and would hide the next one."""
    texts = dict(_sources())
    for (fn, func, call), why in ALLOWED.items():
        assert (fn, func, call) in offenders(fn, texts.get(fn, ""), allowed={}), (fn, func, call, why)
