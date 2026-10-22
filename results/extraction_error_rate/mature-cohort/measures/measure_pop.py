"""Whole-population measures for the adjudication (read only; writes pop_measures.json beside this script).

For every record of the proposed primary population (the 571 triangle records of the 672 and the 86 restored or
entering records), from the 13 October triangle-table census (571) and the design's scan of the restored grids (86):
  - the census class, CO_g, the used table's latest diagonal less paid (where placed), and the share of CO_g the used
    table's own reserves leave uncovered (the reserves of years the table does not develop: an "X and prior" bucket or
    omitted older years);
  - the lines on the used table's page(s) that name an older-years bucket ("2010 and prior", "pre-2011", "all prior
    years", "provision in respect of prior years", ...);
  - the lines on the used table's page(s), and the page before, that use the word "earned" about claims, ultimates or
    the development (an earned-basis table), for hand classification.
Offline; no API.
"""
import io, json, re, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCR = Path(r"D:/tmp/r62/pub4/results/extraction_error_rate/scripts")
sys.path.insert(0, str(SCR))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import scan_triangle_tables as stt  # noqa: E402

CENSUS = Path(r"D:/tmp/r62/pub4/results/extraction_error_rate/triangle-table-scan/triangle-table-scan.json")
RESTORED = Path(r"D:/tmp/r62/oc/design/scan_restored.json")
sets = json.load(io.open(HERE / "sets.json", encoding="utf-8"))

PRIOR_RE = re.compile(r"(?:19|20)\d\d\s*(?:&|and|\+)\s*(?:prior|earlier|before|pr\b)|\bpre[- ]?(?:19|20)\d\d\b|"
                      r"\bbefore\s+(?:19|20)\d\d\b|all\s+prior\s+years|in\s+respect\s+of\s+prior\s+years|"
                      r"prior\s+years?\s+(?:provision|reserve)|\bPY\s+provision|\bearlier\b|(?:19|20)\d\d\s*ae\b|"
                      r"(?:19|20)\d\d\s*&\s*P\b", re.I)
EARNED_RE = re.compile(r"earned", re.I)
EARNED_CTX = re.compile(r"claim|ultimate|loss|development|pure\s+year|basis|exposure|to\s+date", re.I)

census = {r["stem"].replace("syndicate_", ""): r for r in json.load(io.open(CENSUS, encoding="utf-8"))["records"]}
restored = {r["stem"].replace("syndicate_", ""): r for r in json.load(io.open(RESTORED, encoding="utf-8"))}

out = {}
keys = sets["the571"] + sets["the86"]
for n, key in enumerate(keys):
    src = "census" if key in sets["the571"] else "restored"
    r = (census if src == "census" else restored).get(key)
    row = {"key": key, "group": "571" if src == "census" else "86", "in_scan": r is not None}
    if r is None:
        out[key] = row
        continue
    loc = r.get("locate") or {}
    pages = loc.get("pages") or [p for p in (r.get("route_triangle_page"), r.get("grid_source_page")) if p]
    pages = sorted(set(int(p) for p in pages if p))
    row.update({"class": r.get("class"), "reason": r.get("reason"), "co_g": r.get("co_g"), "co_n": r.get("co_n"),
                "i_g": r.get("i_g"), "d_less_paid": r.get("d_less_paid"), "located": bool(loc.get("pages")),
                "pages": pages, "grid_type": r.get("grid_type"), "route": r.get("route"),
                "eye_note": ((r.get("eye") or {}).get("note") or "")[:600]})
    co_g, dlp = r.get("co_g"), r.get("d_less_paid")
    if co_g and dlp is not None and co_g > 0:
        row["uncovered_share"] = round((co_g - dlp) / co_g, 4)
    try:
        f = stt.Filing("syndicate_" + key)
    except Exception as exc:  # pragma: no cover
        row["text_error"] = str(exc)
        out[key] = row
        continue
    look = sorted(set(pages + [p + 1 for p in pages] + [p - 1 for p in pages if p > 1]))
    prior_lines, earned_lines = [], []
    for p in look:
        for ln in f.pages.get(p, []):
            t = ln.text
            if p in pages or p == max(pages, default=0) + 1:
                if PRIOR_RE.search(t):
                    prior_lines.append("p%d: %s" % (p, t[:200]))
            if EARNED_RE.search(t) and EARNED_CTX.search(t):
                earned_lines.append("p%d: %s" % (p, t[:220]))
    row["text_how"] = sorted(set(f.how.get(p, "?") for p in pages))
    row["prior_lines"] = prior_lines[:12]
    row["earned_lines"] = earned_lines[:12]
    out[key] = row
    if n % 50 == 0:
        print(n, key, flush=True)

with io.open(HERE / "pop_measures.json", "w", encoding="utf-8", newline="") as fh:
    json.dump(out, fh, indent=1, ensure_ascii=False)
print("written", len(out))
