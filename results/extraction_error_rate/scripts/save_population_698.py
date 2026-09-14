r"""Save the second sample's population before the repairs overwrite it (error-rate-protocol.md, fifth amendment,
point 3 needs it to separate the records that stay from those that enter).

The population is the stems adopted_model.load_sample retains from the refit's model/exposure_results.json, which
check_refit_population.py found to be run 59da1151 with the committed seed-42 draw reproduced. This repeats both
checks before writing, and refuses to overwrite.

    python save_population_698.py
"""
import datetime
import io
import json
import sys
from pathlib import Path

import numpy as np

AN = Path(r"D:/dev/IME-Lloyds-exposure-composition")
SCR = Path(__file__).resolve().parent
sys.path.insert(0, str(AN / "src"))
import adopted_model  # noqa: E402

OUT = SCR / "error-rate-population-698.json"
if OUT.exists():
    raise SystemExit("%s exists" % OUT.name)
after = json.load(io.open(str(SCR / "error-rate-sample-after.json"), encoding="utf-8"))
cur = json.load(io.open(str(AN / "model" / "exposure_results.json"), encoding="utf-8"))
S, R, H, yr, syn, ritc = adopted_model.load_sample()
stems = sorted("syndicate_%s_%s" % (s, y) for s, y in zip(syn, yr))
if len(stems) != after["population"]["n"]:
    raise SystemExit("load_sample retains %d; the second sample's population held %d" % (len(stems), after["population"]["n"]))
idx = np.random.default_rng(after["seed"]).choice(len(stems), size=after["primary"]["n"], replace=False)
if [stems[int(i)] for i in sorted(idx)] != after["primary"]["stems"]:
    raise SystemExit("the seed-%d redraw is not the committed second sample: this is not its population" % after["seed"])
io.open(str(OUT), "w", encoding="utf-8", newline="").write(json.dumps({
    "what": "the second sample's population: the stems adopted_model.load_sample retains, sorted lexicographically",
    "exposure_results_run_id": cur.get("analysis_run_id"),
    "n": len(stems),
    "checked": "the seed-%d redraw of %d equals error-rate-sample-after.json's primary stems" % (after["seed"], after["primary"]["n"]),
    "saved": datetime.datetime.now().isoformat(timespec="seconds"),
    "stems": stems}, indent=1) + "\n")
print("%s: %d stems, run %s, redraw checked" % (OUT.name, len(stems), cur.get("analysis_run_id")))
