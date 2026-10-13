r"""The fourth random draw of the extraction error-rate study (protocol/error-rate-protocol-fourth.md).

A fresh simple random sample of the FINAL extraction, drawn before any of its records is read. Two steps, each
writing one file once and refusing to overwrite it:

    python draw_error_rate_fourth.py frame
        Writes fourth-sample/error-rate-frame-fourth.json from the committed tree, before the seed exists:
          - W, the working sample: the stems adopted_model.load_sample retains from model/exposure_results.json;
          - R, the records the study has read: every syndicate_NNNN_YYYY string in the two files
            src/error_rate_propagation.py reads as its read set (propagation/error-rate-read-stems.json and
            tenth-census/error-rate-read-stems-tenth.json), the same rule (stems_in) and so the same set;
          - F = W - R, the frame, sorted lexicographically: the records no sample or census has read. It is exactly
            the set the propagation calls unread;
          - C, a census stratum: the records of W & R whose final figures no earlier verdict checked (protocol,
            "Population", point 5). Each rule is in census_reason() below.

    python draw_error_rate_fourth.py draw --timestamp "<the output of: date '+%Y-%m-%dT%H:%M:%S%z'>"
        Refuses unless the frame file and this script are committed and unchanged, and unless the timestamp is
        later than the commit that holds them. The seed is int(SHA-256(timestamp as ASCII), 16), the whole
        256-bit digest; anyone can recompute it with: printf '%s' "<timestamp>" | sha256sum.
        numpy.random.default_rng(seed).choice(len(F), size=N, replace=False) picks N = 100 records of F; their
        draw order assigns reading batches 1-4 of 25 (draw positions 1-25, 26-50, 51-75, 76-100), so the
        allocation of records to readers is random too. Every record of C is listed for reading as batch 5.
        Writes fourth-sample/error-rate-sample-fourth.json: the seed and its derivation, the frame's hash, and
        per record the brief a reader needs (the adopted figure and opening reserves in the report's currency,
        the route, the figure's source, the cited pages, the record and filing paths). Each brief's figures are
        checked against model/exposure_results.json's observation, converted as the loader converts them.

Read-only over the records and the filings: it checks that a filing's file exists and opens none.
Run with PYTHONDONTWRITEBYTECODE=1 so no __pycache__ lands in the archive.
"""
import argparse
import copy
import datetime
import hashlib
import io
import json
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

import numpy as np

SCR = Path(__file__).resolve().parent
STUDY = SCR.parent
AN = STUDY.parent.parent
OUT_DIR = STUDY / "fourth-sample"
FRAME = OUT_DIR / "error-rate-frame-fourth.json"
SAMPLE = OUT_DIR / "error-rate-sample-fourth.json"
EXTRACTION = Path(r"D:/dev/lloyds_reserve_stress_testing")
PDFS = EXTRACTION / "syndicate_reports" / "pdfs"
CONVERTED = EXTRACTION / "pdf_extraction" / "html_converted"
READ_FILES = (STUDY / "propagation" / "error-rate-read-stems.json",
              STUDY / "tenth-census" / "error-rate-read-stems-tenth.json")
N = 100
BATCH = 25
EXPECTED_W = 674
ADOPTED = "adopted_prior_year_development_m_report_currency"
OPENING = "adopted_opening_reserves_m_report_currency"
TS_FORMAT = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}[+-]\d{4}$")

sys.path.insert(0, str(AN / "src"))
sys.path.insert(0, str(SCR))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import adopted_model  # noqa: E402
import run_analysis as ra  # noqa: E402
import score_error_rate as ser  # noqa: E402


def load(p):
    return json.load(io.open(str(p), encoding="utf-8"))


def write_once(path, obj):
    if path.exists():
        raise SystemExit("%s exists; it is written once" % path.name)
    path.parent.mkdir(parents=True, exist_ok=True)
    io.open(str(path), "w", encoding="utf-8", newline="\n").write(json.dumps(obj, indent=1, ensure_ascii=False) + "\n")


def git(*args):
    return subprocess.run(["git", "-C", str(AN)] + list(args), capture_output=True, text=True).stdout.strip()


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def stems_in(obj):
    """Every syndicate_NNNN_YYYY string anywhere in a JSON document (src/error_rate_propagation.stems_in)."""
    out = set()
    if isinstance(obj, str):
        if obj.startswith("syndicate_"):
            out.add(obj)
    elif isinstance(obj, list):
        for x in obj:
            out |= stems_in(x)
    elif isinstance(obj, dict):
        for x in obj.values():
            out |= stems_in(x)
    return out


def canonical(data):
    """The canonical model, as run_analysis.load_and_classify resolves it."""
    models = data.get("models") or {}
    keys = sorted(models)
    if (data.get("validation") or {}).get("passed") is True:
        return keys[0]
    cands = [(k, models[k].get("prior_year_movement_confidence", 0) or 0) for k in keys
             if models[k].get("prior_year_development_pct") is not None]
    return cands[0][0] if len(cands) == 1 else max(cands, key=lambda x: x[1])[0]


def figure_source(brief, overruled):
    """score_error_rate.figure_source, with the one route name the extraction added after it was written: a
    "code_triangle" route is the deterministic triangle's code override (round 58 names it; refinement 3 read the
    same figure from an empty route and its CODE OVERRIDE note), so its figure is a triangle's."""
    if (brief.get("route") or {}).get("source") == "code_triangle":
        return "triangle", "a code_triangle route: the code override computed the adopted figure from a triangle"
    return ser.figure_source(brief, overruled)


class Loader:
    """The figure and the opening reserves the loader adopts, its registers applied as load_and_classify applies them
    (the confirmed figure, the confirmed opening reserves, the take-on base), in the report's currency."""

    def __init__(self):
        self.cur = load(AN / "model" / "exposure_results.json")
        self.obs = {"syndicate_%s_%s" % (o["syndicate"], o["year"]): o for o in self.cur["observations"]}
        self.confirmed = ra.load_pyd_confirmed_figures()
        self.openings = ra.load_opening_reserves_confirmed()
        self.base = ra.load_takeon_base()

    def brief(self, stem):
        key = stem.replace("syndicate_", "")
        record = AN / "pdf_extraction" / ("%s.json" % stem)
        data = load(record)
        ck = canonical(data)
        cm = copy.deepcopy(data["models"][ck])
        registers = []
        if key in self.confirmed:
            cm = ra.apply_confirmed_figure(cm, self.confirmed[key])
            registers.append("data/pyd_confirmed_figures.json")
        if key in self.openings:
            cm = ra.apply_confirmed_opening(cm, self.openings[key])
            registers.append("data/opening_reserves_confirmed.json")
        if key in self.base:
            cm = ra.apply_takeon_base(cm, self.base[key])
            registers.append("data/opening_reserves_takeon_base.json")
        route = cm.get("_pyd_route") or {}
        o = self.obs[stem]
        notes = cm.get("data_quality_notes") or ""
        notes = notes if isinstance(notes, str) else " ".join(map(str, notes))
        filing = next((d / ("%s.pdf" % stem) for d in (PDFS, CONVERTED) if (d / ("%s.pdf" % stem)).exists()), None)
        return {
            "stem": stem,
            "syndicate": key.split("_")[0],
            "report_year": int(key.split("_")[1]),
            "record_path_analysis": "pdf_extraction/%s.json" % stem,
            "record_path_extraction": str(EXTRACTION / "pdf_extraction" / ("%s.json" % stem)).replace("\\", "/"),
            "filing_pdf": str(filing).replace("\\", "/") if filing else None,
            "filing_kind": (None if filing is None else "filed PDF" if filing.parent == PDFS
                            else "HTML report, read from the extraction's PDF conversion"),
            "report_currency": ra.FX_CURRENCIES.get(key, "UNDETERMINED"),
            "canonical_model": ck,
            ADOPTED: cm.get("prior_year_development_gbp_m"),
            OPENING: cm.get("opening_reserves_gbp_m"),
            "sign_convention": "positive = deterioration (strengthening), negative = release",
            "route": dict({k: route.get(k) for k in ("source", "value", "model_value", "triangle_type",
                                                      "triangle_units", "triangle_source_page", "note")},
                          **({k: route.get(k) for k in ("figure_kind", "basis", "register")}
                             if route.get("source") == ra.CONFIRMED_FIGURE_SOURCE else {})),
            "registers_applied": registers,
            "cited_pages": {"prior_year_movement": cm.get("prior_year_movement_page"),
                            "opening_reserves": cm.get("opening_reserves_page"),
                            "triangle": route.get("triangle_source_page")},
            "loader_basis": [o.get("pyd_basis"), o.get("pyd_basis_source")],
            "loader_cohort_scope": [o.get("pyd_cohort_scope"), o.get("pyd_cohort_route")],
            "observation_gbp_m": {"prior_year_development": o.get("pyd_gbp_m"),
                                  "opening_reserves": o.get("opening_reserves_gbp_m"),
                                  "fx_applied": o.get("fx_applied"), "fx_rate_usd_per_gbp": o.get("fx_rate_usd_per_gbp")},
            "model_notes": notes[:1500],
        }

    def check(self, b):
        """The brief's figures, converted as the loader converts them, are the observation's."""
        o = self.obs[b["stem"]]
        rate = o.get("fx_rate_usd_per_gbp") if o.get("fx_applied") else 1.0
        bad = []
        for field, obs_field in ((ADOPTED, "pyd_gbp_m"), (OPENING, "opening_reserves_gbp_m")):
            v = b[field]
            if v is None or o.get(obs_field) is None or abs(v / rate - o[obs_field]) > 1e-6 * max(1.0, abs(o[obs_field])):
                bad.append("%s %s: %s / %s is not the observation's %s" % (b["stem"], field, v, rate, o.get(obs_field)))
        if b["report_currency"] != o.get("report_currency"):
            bad.append("%s currency %s, observation %s" % (b["stem"], b["report_currency"], o.get("report_currency")))
        return bad


# --- the census stratum: read records whose final figures no earlier verdict checked -------------------------------

# every scored reading of a record's figure, latest first: (name, briefs, merged verdicts)
SCORED = (("tail stratum", "tail/error-rate-briefs-tail.json", "tail/error-rate-verdicts-tail.json",
           "tail/error-rate-verification-tail.json"),
          ("eighth census", "eighth-census/error-rate-briefs-eighth.json", "eighth-census/error-rate-verdicts-eighth.json",
           "eighth-census/error-rate-verification-eighth.json"),
          ("third sample", "third-sample/error-rate-briefs-third.json", "third-sample/error-rate-verdicts-third.json",
           "third-sample/error-rate-verification-third.json"),
          ("take-on census", "takeon-census/error-rate-briefs-takeon.json", "takeon-census/error-rate-verdicts-takeon.json",
           "takeon-census/error-rate-verification-takeon.json"),
          ("found in passing", "found-in-passing/error-rate-briefs-passing.json",
           "found-in-passing/error-rate-verdicts-passing.json", "found-in-passing/error-rate-verification-passing.json"),
          ("census", "census/error-rate-briefs-census.json", "census/error-rate-verdicts-census.json",
           "census/error-rate-verification-census.json"),
          ("second sample", "second-sample/error-rate-briefs-after.json", "second-sample/error-rate-verdicts-after.json",
           "second-sample/error-rate-verification-after.json"),
          ("first sample", "first-sample/error-rate-briefs.json", "first-sample/error-rate-verdicts.json",
           "first-sample/error-rate-verification.json"))


def later_figure_verdicts():
    """The tenth census's and the eleventh and twelfth amendments' two-reader verdicts on a record's FIGURE (later than
    every set in SCORED): stem -> (name, the adopted figure they read). A reading on another question only (a
    transfer's genuineness, a take-on's share) is not a figure verdict."""
    out = {}
    for r in load(STUDY / "tenth-census" / "entrants" / "entrants-result.json")["records"]:
        verdicts = [str(v.get("verdict", "")) for v in (r.get("readings") or {}).values()]
        if verdicts and all(v.startswith(("correct", "error")) for v in verdicts):
            out["syndicate_" + r["stem"]] = ("tenth census, entrants (eleventh and twelfth amendments)", r["adopted_m"])
    for r in load(STUDY / "tenth-census" / "census-tenth-result.json")["found_in_passing"]:
        if r.get("verdict") in ("correct", "error"):
            out.setdefault("syndicate_" + r["stem"], ("tenth census, found in passing", r["adopted_m"]))
    return out


def same(x, y):
    return x is not None and y is not None and abs(float(x) - float(y)) <= 1e-9


def census_reason(stem, now, prior, later, loader, overruled):
    """None when an earlier verdict checked the record's final figures; otherwise why it is in C.

    Checked means (the fourth amendment's rule, point 3, with each field read for what the check uses):
      - the figure: the latest figure verdict read the adopted figure the record now carries; or the record now
        carries a figure two readings confirmed (data/pyd_confirmed_figures.json, after those readings); or the first
        and the second reading of that verdict both give the figure it now carries (the extraction has since moved
        the figure to the readings' own, as for 1225/2022, 218/2020 and 5000/2017);
      - the opening reserves: the latest scored verdict read the opening reserves the record now carries, or they
        come from a register two readings confirmed (data/opening_reserves_confirmed.json,
        data/opening_reserves_takeon_base.json);
      - the figure's source (triangle or stated): unchanged, unless the record now carries a confirmed figure;
      - the basis: unchanged;
      - the cohort scope: unchanged, for a stated figure only. A triangle figure is checked against the triangle over
        underwriting years up to t-2 whatever the scope label says (clarification, rule 1); refinement 2 reads the
        scope of a stated figure.
    """
    key = stem.replace("syndicate_", "")
    confirmed_now = (now["route"] or {}).get("source") == ra.CONFIRMED_FIGURE_SOURCE
    opening_register = key in loader.openings or key in loader.base
    if stem in later:
        name, read_figure = later[stem]
        if not (same(read_figure, now[ADOPTED]) or confirmed_now):
            return "the %s read adopted %s; it now carries %s" % (name, read_figure, now[ADOPTED])
        return None
    held = next((p for p in prior if stem in p[1] and stem in p[2]), None)
    if held is None:
        return "no scored verdict on its figure: read only on another question"
    name, briefs, merged, second = held
    old, row = briefs[stem], merged[stem]
    # a figure the extraction has since moved to the readings' own: both readings give the figure it now carries
    both_readings_give_it = (stem in second and same(row.get("filing_figure_m"), now[ADOPTED])
                             and same(second[stem].get("filing_figure_m"), now[ADOPTED]))
    why = []
    if not (same(old[ADOPTED], now[ADOPTED]) or confirmed_now or both_readings_give_it):
        why.append("adopted figure %s -> %s" % (old[ADOPTED], now[ADOPTED]))
    if not (same(old[OPENING], now[OPENING]) or opening_register):
        why.append("opening reserves %s -> %s" % (old[OPENING], now[OPENING]))
    src_old = row.get("figure_source") or figure_source(old, overruled)[0]
    src_now = figure_source(now, overruled)[0]
    if src_old != src_now and not confirmed_now:
        why.append("figure source %s -> %s" % (src_old, src_now))
    if (old.get("loader_basis") or [None])[0] != now["loader_basis"][0]:
        why.append("basis %s -> %s" % ((old.get("loader_basis") or [None])[0], now["loader_basis"][0]))
    if src_now == "stated" and not confirmed_now \
            and (old.get("loader_cohort_scope") or [None])[0] != now["loader_cohort_scope"][0]:
        why.append("stated figure's cohort scope %s -> %s"
                   % ((old.get("loader_cohort_scope") or [None])[0], now["loader_cohort_scope"][0]))
    return ("latest verdict in the %s; since then: %s" % (name, "; ".join(why))) if why else None


def working_sample():
    _S, _R, _H, yr, syn, _ritc = adopted_model.load_sample()
    return sorted("syndicate_%s_%s" % (s, y) for s, y in zip(syn, yr))


def frame():
    if FRAME.exists():
        raise SystemExit("%s exists; the frame is computed once, before the seed" % FRAME.name)
    if git("status", "--porcelain", "--", "src", "model", "data", "pdf_extraction"):
        raise SystemExit("the analysis tree has uncommitted changes under src, model, data or pdf_extraction")
    loader = Loader()
    W = working_sample()
    flow = loader.cur.get("disposition_flow") or {}
    if len(W) != EXPECTED_W or len(set(W)) != len(W) or flow.get("working_sample") != len(W):
        raise SystemExit("the working sample is %d (%d distinct; disposition flow %s), not %d"
                         % (len(W), len(set(W)), flow.get("working_sample"), EXPECTED_W))
    read = set()
    for p in READ_FILES:
        read |= stems_in(load(p))
    RW = [s for s in W if s in read]
    F = [s for s in W if s not in read]
    # the 161: the records of the pooled rate's sample (A_sampled: the second sample's 60 less 2008/2021, and the third
    # sample's 110) still in W; and the first sample's, drawn from the extraction before R209 and R210
    second = set(load(STUDY / "second-sample" / "error-rate-sample-after.json")["primary"]["stems"])
    third = set(load(STUDY / "third-sample" / "error-rate-sample-third.json")["third"]["stems"])
    first = set(load(STUDY / "first-sample" / "error-rate-sample.json")["primary"]["stems"])
    random_in_w = sorted(s for s in RW if s in second | third)
    first_only_in_w = sorted(s for s in RW if s in first - second - third)
    # every brief of W is the loader's own figures (refuses otherwise)
    briefs = {s: loader.brief(s) for s in W}
    bad = [m for s in W for m in loader.check(briefs[s])]
    if bad:
        raise SystemExit("briefs disagree with the observations:\n  " + "\n  ".join(bad[:20]))
    overruled = ser.overruled_stems()
    # since R208 a rag_triangle route names a triangle only when its figure was computed from it
    no_tri = [s for s in W if (briefs[s]["route"] or {}).get("source") == "rag_triangle"
              and not ser.carries_triangle(briefs[s]["route"])]
    if no_tri:
        raise SystemExit("rag_triangle routes without their triangle: %s" % no_tri)
    prior = []
    for name, bf, vf, sf in SCORED:
        prior.append((name, {b["stem"]: b for b in load(STUDY / bf)},
                      {v["stem"]: v for v in load(STUDY / vf) if v.get("clarified_verdict")},
                      {v["stem"]: v for v in load(STUDY / sf)}))
    later = later_figure_verdicts()
    C, checked = [], []
    for s in RW:
        why = census_reason(s, briefs[s], prior, later, loader, overruled)
        if why:
            C.append({"stem": s, "why": why})
        else:
            src = later[s][0] if s in later else next(p[0] for p in prior if s in p[1] and s in p[2])
            checked.append({"stem": s, "latest_figure_verdict": src})
    # the records the study read, by where (a record may be in several)
    by_source = {}
    for p in READ_FILES:
        d = load(p)
        for k, v in (d.get("sources") or {}).items():
            by_source[k] = v
    out = {
        "protocol": "protocol/error-rate-protocol-fourth.md, committed with this file, before the seed exists",
        "computed": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
        "analysis_commit": git("rev-parse", "HEAD"),
        "exposure_results": {"path": "model/exposure_results.json",
                             "sha256": sha256(AN / "model" / "exposure_results.json"),
                             "analysis_run_id": loader.cur.get("analysis_run_id"),
                             "analysis_run_id_without_calibration": loader.cur.get("analysis_run_id_without_calibration")},
        "extraction_checkout": {"path": str(EXTRACTION).replace("\\", "/"),
                                "commit": subprocess.run(["git", "-C", str(EXTRACTION), "rev-parse", "HEAD"],
                                                         capture_output=True, text=True).stdout.strip(),
                                "working_sample_records_differing_from_analysis_copy": sorted(
                                    s for s in W if (AN / "pdf_extraction" / (s + ".json")).read_bytes().replace(b"\r\n", b"\n")
                                    != (EXTRACTION / "pdf_extraction" / (s + ".json")).read_bytes().replace(b"\r\n", b"\n"))},
        "W_working_sample": {"rule": "the stems adopted_model.load_sample retains", "n": len(W)},
        "R_read": {"rule": "every syndicate_NNNN_YYYY string in the read-set files of src/error_rate_propagation.py",
                   "files": [str(p.relative_to(STUDY)).replace("\\", "/") for p in READ_FILES],
                   "sources_as_recorded": by_source,
                   "n_read": len(read), "n_in_W": len(RW),
                   "pooled_rate_sample_in_W": {"rule": "the second and third samples' drawn stems (the pooled rate's "
                                                       "A_sampled) still in W; error_rate_propagation_results.json "
                                                       "records the same count as n_in_current_working_sample",
                                               "n": len(random_in_w), "stems": random_in_w},
                   "first_sample_only_in_W": {"rule": "the first sample's drawn stems, in neither later sample, still in W",
                                              "n": len(first_only_in_w), "stems": first_only_in_w},
                   "read_otherwise_in_W": len(RW) - len(random_in_w) - len(first_only_in_w),
                   "stems_in_W": RW},
        "F_frame": {"rule": "W - R, sorted lexicographically: the records no sample or census has read; the set "
                            "src/error_rate_propagation.py calls unread", "n": len(F), "stems": F},
        "C_census": {"rule": "records of W & R whose final figures no earlier verdict checked (census_reason in "
                             "scripts/draw_error_rate_fourth.py); each is read twice, reported apart, never pooled",
                     "n": len(C), "records": C},
        "K_checked": {"rule": "records of W & R whose final figures an earlier verdict checked", "n": len(checked),
                      "by_latest_verdict": dict(Counter(c["latest_figure_verdict"] for c in checked)),
                      "records": checked},
        "figure_source_over_W": dict(Counter(figure_source(briefs[s], overruled)[0] for s in W)),
        "figure_source_over_F": dict(Counter(figure_source(briefs[s], overruled)[0] for s in F)),
        "route_source_over_F": dict(Counter(str((briefs[s]["route"] or {}).get("source")) for s in F)),
        "year_over_F": dict(sorted(Counter(briefs[s]["report_year"] for s in F).items())),
        "currency_over_F": dict(Counter(briefs[s]["report_currency"] for s in F)),
        "filing_missing_in_F": sorted(s for s in F if briefs[s]["filing_pdf"] is None),
    }
    if len(F) + len(C) + len(checked) != len(W):
        raise SystemExit("F, C and K do not partition W")
    write_once(FRAME, out)
    print("W %d; R %d (in W %d: pooled rate's sample %d, first sample only %d, other reads %d); F %d; C %d; K %d -> %s"
          % (len(W), len(read), len(RW), len(random_in_w), len(first_only_in_w),
             len(RW) - len(random_in_w) - len(first_only_in_w), len(F), len(C), len(checked), FRAME.relative_to(AN)))
    for c in C:
        print("  C %-22s %s" % (c["stem"], c["why"]))


def committed_unchanged(path):
    rel = str(path.relative_to(AN)).replace("\\", "/")
    if not git("ls-files", rel):
        raise SystemExit("%s is not committed" % rel)
    if git("status", "--porcelain", "--", rel):
        raise SystemExit("%s has uncommitted changes" % rel)
    return git("log", "-1", "--format=%H %cI", "--", rel).split()


def draw(timestamp):
    if SAMPLE.exists():
        raise SystemExit("%s exists; the fourth sample is drawn once" % SAMPLE.name)
    if not TS_FORMAT.match(timestamp):
        raise SystemExit("the timestamp must be date '+%Y-%m-%dT%H:%M:%S%z' output, e.g. 2026-10-13T14:05:09+1000")
    when = datetime.datetime.strptime(timestamp, "%Y-%m-%dT%H:%M:%S%z")
    protocol = STUDY / "protocol" / "error-rate-protocol-fourth.md"
    commits = [committed_unchanged(p) for p in (FRAME, Path(__file__).resolve(), protocol)]
    latest = max(datetime.datetime.fromisoformat(c[1]) for c in commits)
    if when <= latest:
        raise SystemExit("the timestamp %s is not later than the pre-registration commit (%s)" % (timestamp, latest))
    now = datetime.datetime.now().astimezone()
    if when > now + datetime.timedelta(seconds=5):
        raise SystemExit("the timestamp %s is in the future (now %s)" % (timestamp, now.isoformat(timespec="seconds")))
    fr = load(FRAME)
    loader = Loader()
    W = working_sample()
    if len(W) != fr["W_working_sample"]["n"] or sha256(AN / "model" / "exposure_results.json") != fr["exposure_results"]["sha256"]:
        raise SystemExit("model/exposure_results.json is not the file the frame was computed from")
    F = fr["F_frame"]["stems"]
    if F != sorted(F) or len(F) < N:
        raise SystemExit("the frame is not sorted, or holds fewer than %d records" % N)
    digest = hashlib.sha256(timestamp.encode("ascii")).hexdigest()
    seed = int(digest, 16)
    idx = np.random.default_rng(seed).choice(len(F), size=N, replace=False)
    drawn = [F[int(i)] for i in idx]  # in draw order
    overruled = ser.overruled_stems()
    records, bad = [], []
    for pos, s in enumerate(drawn, start=1):
        b = loader.brief(s)
        bad += loader.check(b)
        b.update({"role": "draw4", "draw_position": pos, "frame_index": int(idx[pos - 1]),
                  "batch": (pos - 1) // BATCH + 1})
        b["figure_source"], b["figure_source_why"] = figure_source(b, overruled)
        records.append(b)
    for c in fr["C_census"]["records"]:
        b = loader.brief(c["stem"])
        bad += loader.check(b)
        b.update({"role": "census4", "draw_position": None, "frame_index": None, "batch": 5, "census_why": c["why"]})
        b["figure_source"], b["figure_source_why"] = figure_source(b, overruled)
        records.append(b)
    if bad:
        raise SystemExit("briefs disagree with the observations:\n  " + "\n  ".join(bad[:20]))
    for b in records:
        b["pack"] = "D:/tmp/r62/draw4/packs/batch_%d/%s.txt" % (b["batch"], b["stem"])
    d4 = [b for b in records if b["role"] == "draw4"]
    out = {
        "protocol": "protocol/error-rate-protocol-fourth.md (committed %s at %s)" % (commits[2][0][:7], commits[2][1]),
        "frame": {"path": "fourth-sample/error-rate-frame-fourth.json", "sha256": sha256(FRAME),
                  "committed": commits[0][0], "n": len(F)},
        "drawn": now.isoformat(timespec="seconds"),
        "seed": {"timestamp": timestamp,
                 "timestamp_command": "date '+%Y-%m-%dT%H:%M:%S%z'  (Git Bash on the PC; the PC's clock is Brisbane, UTC+10)",
                 "sha256_of_timestamp_ascii": digest,
                 "seed": str(seed),
                 "derivation": "seed = int(SHA-256(timestamp as ASCII bytes), 16); check: printf '%s' '<timestamp>' | sha256sum",
                 "generator": "numpy.random.default_rng(seed).choice(len(F), size=%d, replace=False), numpy %s"
                              % (N, np.__version__)},
        "analysis_commit": git("rev-parse", "HEAD"),
        "exposure_results": fr["exposure_results"],
        "n_drawn": N,
        "batches": {"1-4": "draw positions 1-25, 26-50, 51-75 and 76-100: the draw order allocates records to readers",
                    "5": "the census stratum C, every record read twice by two independent readers"},
        "summary_draw4": {
            "by_year": dict(sorted(Counter(b["report_year"] for b in d4).items())),
            "by_route_source": dict(Counter(str(b["route"]["source"]) for b in d4)),
            "by_figure_source": dict(Counter(b["figure_source"] for b in d4)),
            "by_currency": dict(Counter(b["report_currency"] for b in d4)),
            "by_filing_kind": dict(Counter(str(b["filing_kind"]) for b in d4)),
            "with_a_register_applied": sorted(b["stem"] for b in d4 if b["registers_applied"]),
            "by_batch": dict(Counter(b["batch"] for b in d4)),
        },
        "records": records,
    }
    write_once(SAMPLE, out)
    print("seed %s (sha256 %s of %r)" % (seed, digest, timestamp))
    print("drew %d of %d; census %d -> %s" % (N, len(F), len(records) - N, SAMPLE.relative_to(AN)))
    for k, v in out["summary_draw4"].items():
        print("  %s: %s" % (k, v))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("step", choices=("frame", "draw"))
    ap.add_argument("--timestamp")
    a = ap.parse_args()
    if a.step == "frame":
        frame()
    else:
        if not a.timestamp:
            raise SystemExit("draw needs --timestamp")
        draw(a.timestamp)
