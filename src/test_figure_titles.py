"""No paper figure's embedded title presents the floor as a feature of the data (the review of 2 October 2026, P-27).

Figure 2's title read "|S| decays with size toward the floor", against the paper's statement that the floor is a
structural specification, not a measured quantity (main.tex 1250-1251, 1277-1280, 1293). The titles are read from
the generator's source, every one of them, so a new figure is held to the same rule.

Run:  python -m pytest src/test_figure_titles.py -q
"""
import ast
import io
import os

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GENERATOR = os.path.join(HERE, "src", "make_paper_figures.py")


def _titles():
    tree = ast.parse(io.open(GENERATOR, encoding="utf-8").read())
    out = []
    for node in ast.walk(tree):
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "set_title"
                and node.args):
            arg = node.args[0]
            if isinstance(arg, ast.BinOp):      # "..." % values
                arg = arg.left
            if isinstance(arg, ast.JoinedStr):  # f-strings: their literal parts
                out.append("".join(v.value for v in arg.values if isinstance(v, ast.Constant)))
            elif isinstance(arg, ast.Constant):
                out.append(arg.value)
    return out


def test_every_title_is_read():
    titles = _titles()
    assert len(titles) >= 5, titles
    assert any(t.startswith("Size$-$dispersion") for t in titles)


def test_no_title_says_the_data_reach_the_floor():
    bad = [t for t in _titles() if "floor" in t.lower() or "decays" in t.lower()]
    assert bad == []
