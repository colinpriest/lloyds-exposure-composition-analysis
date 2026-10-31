"""Exercise the retained dashboard against its historical inception cache."""

import json
from pathlib import Path
import shutil
import subprocess

import pytest


ROOT = Path(__file__).resolve().parent.parent


def test_unverified_2357_age_is_not_displayed():
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not available")
    html = (ROOT / "pdf_extraction" / "progress_report.html").read_text(encoding="utf-8")
    age_function = html.split("function getUwFlag(", 1)[1].split("async function readInceptionYears", 1)[0]
    analysis = html.split("function analyzeData(", 1)[1].split("// ─── Formatting", 1)[0]
    render = html.split("function renderTable(", 1)[1].split("// ─── Refresh loop", 1)[0]
    record = json.loads((ROOT / "pdf_extraction" / "syndicate_2357_2014.json").read_text(encoding="utf-8"))
    cache = json.loads((ROOT / "data" / "syndicate_inception_years.json").read_text(encoding="utf-8"))
    assert cache["2357"] == 2013
    js = """
const fs = require('fs');
const input = JSON.parse(fs.readFileSync(0, 'utf8'));
function getUwFlag(%s
function analyzeData(%s
function renderTable(%s
const tbody = {innerHTML: ''};
const document = {getElementById: () => tbody};
const records = [
  {name: 'syndicate_2357_2014.json', data: input.record},
  {name: 'syndicate_2014_2015.json', data: {syndicate: 2014, year: 2015, first_year_syndicate: true}}
];
const stats = analyzeData(records, 2, input.cache);
renderTable(stats.completed);
process.stdout.write(JSON.stringify({flags: stats.completed.map(r => r.uwFlag), html: tbody.innerHTML}));
""" % (age_function, analysis, render)
    output = subprocess.run([node, "-e", js], input=json.dumps({"record": record, "cache": cache}),
                            text=True, capture_output=True, check=True)
    result = json.loads(output.stdout)
    assert result["flags"] == [None, 2]
    first, second = result["html"].split("</tr>")[:2]
    assert "2357" in first and "yr UW" not in first and "Skipped" in first
    assert "2014" in second and "2nd yr UW" in second
