"""Implementation note 4: 2003/2018's brief for the sixth amendment's question, as the eighth census's takeon_triangle
part asks it. The ninth census's brief, unchanged except that its census part and reasons name takeon_triangle.

    python make_brief_2003_sixth.py
"""
import io
import json
from pathlib import Path

SCR = Path(__file__).resolve().parent
STEM = "syndicate_2003_2018"
briefs = {b["stem"]: b for b in json.load(io.open(str(SCR / "error-rate-briefs-ninth.json"), encoding="utf-8"))}
b = dict(briefs[STEM])
reasons = (b.get("census_reasons") or {}).get("takeon_base") or []
if not reasons:
    raise SystemExit("%s: the ninth census brief has no take-on reasons" % STEM)
b["census_parts"] = ["takeon_triangle"]
b["census_reasons"] = {"takeon_triangle": reasons}
out = SCR / "error-rate-briefs-ninth-sixth-2003.json"
io.open(str(out), "w", encoding="utf-8", newline="").write(json.dumps([b], indent=1, ensure_ascii=False) + "\n")
print("written %s: %s, parts %s, %d reasons" % (out.name, b["stem"], b["census_parts"], len(reasons)))
