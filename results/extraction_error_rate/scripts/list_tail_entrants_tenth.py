r"""The tenth amendment's point 5: donors that enter Vignette 1's top 20 in the refit after its repairs, each with
whether a sample or census read it.

The top 20 is computed exactly as draw_error_rate_tail.py computed the tail stratum: every donor of the pool
(distortion_tool.html) transferred to Vignette 1's target by the de-RITC transfer under the headline calibration's
posterior means (model/dispersion_calibration_ritc.json), as src/donor_review.py ranks them. The stratum itself is
reported as drawn (tail/error-rate-tail.json); this lists the donors that enter and leave the top 20. A record counts
as read when propagation/error-rate-read-stems.json lists it (the draws, the censuses and the stratum) or the tenth
census read it (tenth-census/error-rate-read-stems-tenth.json: 1884/2016, the records found in passing and the eleventh amendment's). Writes
tenth-census/tail-entrants-tenth.json with the hashes of the calibration and the pool it used.

    python results/extraction_error_rate/scripts/list_tail_entrants_tenth.py
"""
import datetime
import hashlib
import io
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
STUDY = os.path.join(ROOT, "results", "extraction_error_rate")
OUT = os.path.join(STUDY, "tenth-census", "tail-entrants-tenth.json")
N_TAIL = 20
sys.path.insert(0, os.path.join(ROOT, "src"))

import donor_review as dr  # noqa: E402
from dispersion_mle import sigma, deritc_z  # noqa: E402
from vignette_uncertainty import load_pool, load_ritc  # noqa: E402


def sha(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


def main():
    cal_path = os.path.join(ROOT, "model", "dispersion_calibration_ritc.json")
    pool_path = os.path.join(ROOT, "distortion_tool.html")
    cal = json.load(io.open(cal_path, encoding="utf-8"))
    mp = {k: cal[k] for k in ("k", "gamma", "sd_undiv", "sd_div", "nu_clean", "nu_ritc")}
    S, R, H, synd, year = load_pool()
    ritc = load_ritc(synd, year)
    V1 = dr.V1
    sig_i = sigma(R, H, mp["k"], mp["gamma"], mp["sd_undiv"], mp["sd_div"])
    sig_q = sigma(V1[0], V1[1], mp["k"], mp["gamma"], mp["sd_undiv"], mp["sd_div"])
    z = deritc_z(S / sig_i, ritc.astype(float), mp["nu_clean"], mp["nu_ritc"])
    s_adj = z * sig_q
    order = np.argsort(-s_adj)[:N_TAIL]
    top = ["syndicate_%s_%s" % (synd[i], year[i]) for i in order]

    stratum = json.load(io.open(os.path.join(STUDY, "tail", "error-rate-tail.json"), encoding="utf-8"))["tail"]["stems"]
    read = set(json.load(io.open(os.path.join(STUDY, "propagation", "error-rate-read-stems.json"),
                                 encoding="utf-8"))["stems"])
    # the tenth census's readings and the eleventh amendment's (write_propagation_inputs_tenth.py lists both)
    read_tenth = set(json.load(io.open(os.path.join(STUDY, "tenth-census", "error-rate-read-stems-tenth.json"),
                                       encoding="utf-8"))["stems"])
    entrants = [s for s in top if s not in stratum]
    rows = [{"stem": s, "rank": top.index(s) + 1, "transferred_severity": float(s_adj[order[top.index(s)]]),
             "assumed_business_regime": bool(ritc[order[top.index(s)]]),
             "read": s in read or s in read_tenth,
             "read_by": sorted((["an earlier sample, census or the stratum"] if s in read else [])
                               + (["the tenth census or the eleventh amendment"] if s in read_tenth else []))} for s in entrants]
    out = {"_about": ("the tenth amendment's point 5: the donors entering Vignette 1's top 20 in the refit after its "
                      "repairs (results/extraction_error_rate/scripts/list_tail_entrants_tenth.py)"),
           "generated": datetime.datetime.now().astimezone().isoformat(timespec="minutes"),
           "calibration": {"file": "model/dispersion_calibration_ritc.json", "sha256": sha(cal_path), "parameters": mp},
           "donor_pool": {"file": "distortion_tool.html", "n": int(len(S)), "sha256": sha(pool_path)},
           "top_20": [{"stem": s, "transferred_severity": float(s_adj[i]), "assumed_business_regime": bool(ritc[i])}
                      for s, i in zip(top, order)],
           "entrants": rows, "left_the_top_20": [s for s in stratum if s not in top],
           "entrants_unread": [r["stem"] for r in rows if not r["read"]]}
    with io.open(OUT, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(out, indent=1, ensure_ascii=False) + "\n")
    print("pool %d; entrants %d (unread %d): %s; left: %s"
          % (len(S), len(rows), len(out["entrants_unread"]), [r["stem"] for r in rows], out["left_the_top_20"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
