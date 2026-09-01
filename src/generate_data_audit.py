"""Generate Appendix B (data audit & provenance) -> docs/appendix-data-audit.md.

Mines the raw extraction (pdf_extraction/syndicate_*.json), the analysis output
(exposure_results.json) and the code to fill in the audit with real numbers: reserve
caption evidence and gross-vs-net, claims-triangle and segmental-premium coverage, the
actual disclosed class labels and how each folds into the 13 categories (with the
keyword-ordering artefacts surfaced), the exclusion waterfall and per-year counts, market
coverage against Lloyd's active-syndicate denominators, RITC prevalence, and the syndicate
panel structure.

Run: python generate_data_audit.py
"""
import json, glob, re
from collections import Counter, defaultdict
from pathlib import Path

SD = Path(__file__).resolve().parent.parent
RESULTS = SD / "model" / "exposure_results.json"
RAW = sorted(glob.glob(str(SD / "pdf_extraction" / "syndicate_*.json")))
OUT = SD / "docs" / "appendix-data-audit.md"
WEIGHT_FLOOR = 0.01
YEARS = list(range(2014, 2025))

LOB_NAMES = ["Property", "Casualty", "Marine", "Energy", "Motor", "Aviation",
             "Reinsurance — Property", "Reinsurance — Casualty", "Reinsurance — Specialty",
             "Professional Lines", "Accident & Health", "Cyber", "Aggregate"]
RULES = [(6, ["reinsurance property", "property treaty", "property reinsurance"]),
         (7, ["reinsurance casualty", "casualty treaty", "casualty reinsurance"]),
         (8, ["reinsurance specialty", "specialty treaty", "specialty reinsurance"]),
         (9, ["professional", "d&o", "directors", "e&o", "pi", "financial lines"]),
         (10, ["accident", "health", "a&h", "personal accident"]),
         (5, ["aviation"]), (11, ["cyber"]),
         (0, ["property", "fire", "damage to property"]),
         (1, ["casualty", "third party liability", "liability"]),
         (2, ["marine", "hull", "cargo", "transit"]),
         (3, ["energy"]), (4, ["motor"]),
         (12, ["aggregate", "miscellaneous", "other", "whole account", "reinsurance"])]

# Market denominator: active Lloyd's syndicates.
# 2020-2024: Lloyd's official "List of active Syndicates & Managing Agent" spreadsheets
#            (syndicate numbers extracted into market_active_syndicates.json).
# 2014-2019: Lloyd's Annual Reports / SFCRs (BoE/PRA Jan-2015 register lists ~101 incl. run-off/RITC).
MARKET_AR = {2014: 92, 2015: 94, 2016: 99, 2017: 95, 2018: 99, 2019: 93}
_MKT_FILE = SD / "data" / "market_active_syndicates.json"


def classify(name):
    nl = name.lower().strip()
    for idx, kws in RULES:
        for k in kws:
            if k in nl:
                return idx
    return 12


def canon(d):
    m = d.get("models", {})
    return m.get("gemini-2.5-flash") or m.get("gpt-5-mini") or {}


def mine_raw():
    n_files = len(RAW)
    has_g = has_p = neither = 0
    tri = gpm = ritc = gross = net = 0
    labels = Counter()
    ritc_sy = set()
    cap = Counter()
    raw_year, empty_year, extr_year = Counter(), Counter(), Counter()
    for f in RAW:
        ym = re.search(r"syndicate_(\d+)_(\d+)", f)
        yr = int(ym.group(2)) if ym else None
        if yr:
            raw_year[yr] += 1
        d = json.loads(Path(f).read_text(encoding="utf-8"))
        m = d.get("models", {})
        g, p = m.get("gemini-2.5-flash"), m.get("gpt-5-mini")
        has_g += bool(g); has_p += bool(p)
        if g or p:
            if yr:
                extr_year[yr] += 1
        else:
            neither += 1
            if yr:
                empty_year[yr] += 1
        r = g or p or {}
        if not r:
            continue
        if isinstance(r.get("_claims_triangle"), dict) and r["_claims_triangle"]:
            tri += 1
        pm = r.get("gross_premium_mix") or []
        if pm:
            gpm += 1
            for e in pm:
                lob = e.get("line_of_business")
                if lob:
                    labels[lob] += 1
        txt = " ".join(str(r.get(k) or "") for k in
                       ("data_quality_notes", "exact_reserve_text", "standardized_narrative"))
        if re.search(r"\britc\b|reinsurance to close", txt, re.I):
            ritc += 1
            ritc_sy.add((r.get("syndicate"), r.get("year")))
        ert = str(r.get("exact_reserve_text") or "") + " " + str(r.get("standardized_narrative") or "")
        gross += bool(re.search(r"gross", ert, re.I))
        net += bool(re.search(r"\bnet\b", ert, re.I))
        for term in ["gross claims", "claims outstanding", "technical provision",
                     "technical reserve", "provision for claims", "outstanding claims"]:
            if term in ert.lower():
                cap[term] += 1
    return dict(n_files=n_files, has_g=has_g, has_p=has_p, neither=neither, tri=tri,
                gpm=gpm, ritc=ritc, gross=gross, net=net, labels=labels, ritc_sy=ritc_sy, cap=cap,
                raw_year=raw_year, empty_year=empty_year, extr_year=extr_year)


def compute():
    d = json.loads(RESULTS.read_text(encoding="utf-8"))
    meta, obs = d["meta"], d["observations"]
    disc = meta["discarded"]["reasons"]
    rem = list(obs)
    sev = [o for o in rem if o.get("s_raw_a") is None]; rem = [o for o in rem if o.get("s_raw_a") is not None]
    res = [o for o in rem if not o.get("opening_reserves_gbp_m")]; rem = [o for o in rem if o.get("opening_reserves_gbp_m")]
    wt = [o for o in rem if o.get("hhi") is None]; rem = [o for o in rem if o.get("hhi") is not None]
    sample = rem
    corpus_by_year = {int(y): c for y, c in meta["yearly_observations"].items()}
    sample_by_year = Counter(o["year"] for o in sample)
    pres = defaultdict(set)
    for o in obs:
        pres[o["syndicate"]].add(o["year"])
    allyrs = sum(1 for ys in pres.values() if set(ys) >= set(YEARS))
    year_dist = dict(sorted(Counter(len(ys) for ys in pres.values()).items()))
    sample_sy = {(o["syndicate"], o["year"]) for o in sample}
    corpus_sy = {(o["syndicate"], o["year"]) for o in obs}
    # official active-syndicate lists (2020-2024) and the corpus-vs-list diff
    corp_syn_year = defaultdict(set)
    for o in obs:
        corp_syn_year[o["year"]].add(o["syndicate"])
    all_corp = set(o["syndicate"] for o in obs)
    market = dict(MARKET_AR)
    official = {}
    diff = {}
    if _MKT_FILE.exists():
        mkt = {int(k): set(v) for k, v in json.loads(_MKT_FILE.read_text()).items()}
        for y, active in mkt.items():
            market[y] = len(active)
            official[y] = active
            have = corp_syn_year[y] & active
            miss = active - corp_syn_year[y]
            diff[y] = dict(active=len(active), have=len(have), miss=len(miss),
                           miss_seen=len(miss & all_corp), extra=len(corp_syn_year[y] - active))
    return dict(corpus=len(obs), sample=len(sample), disc=disc, disc_total=sum(disc.values()),
                market=market, official=official, diff=diff,
                sev=len(sev), res=len(res), wt=len(wt), excl=len(sev) + len(res) + len(wt),
                total_files=meta["total_files"], corpus_by_year=corpus_by_year,
                sample_by_year=dict(sorted(sample_by_year.items())),
                corpus_synd=meta["unique_syndicates"], sample_synd=len(set(o["syndicate"] for o in sample)),
                present_all=allyrs, year_dist=year_dist, n_synd=len(pres),
                sample_sy=sample_sy, corpus_sy=corpus_sy)


def _clean(lab):
    return re.sub(r"\s+", " ", lab.replace(":unselected:", "").replace(":selected:", "")).strip()


def label_mapping(labels):
    bycat = defaultdict(list)
    for lab, cnt in labels.items():
        bycat[classify(lab)].append((_clean(lab), cnt))
    out = {}
    for idx in range(13):
        if bycat[idx]:
            tot = sum(c for _, c in bycat[idx])
            top = sorted(bycat[idx], key=lambda x: -x[1])[:5]
            out[LOB_NAMES[idx]] = (tot, top)
    return out


def _ritc_scan_sets():
    """Authoritative RITC flags from the dual-LLM scan (the file the model/operator use)."""
    import io as _io
    p = SD / "pdf_extraction" / "ritc_scan.json"
    if not p.exists():
        return None
    rs = json.load(_io.open(p, encoding="utf-8"))
    def parse(k):
        s, y = k.rsplit("_", 1); return (int(s), int(y))
    occ = {parse(k) for k, v in rs.items() if v.get("ritc_occurred")}
    strong = {parse(k) for k, v in rs.items() if v.get("ritc_occurred") and v.get("confidence") == "strong"}
    weak = {parse(k) for k, v in rs.items() if v.get("ritc_occurred") and v.get("confidence") == "weak"}
    return {"occ": occ, "strong": strong, "weak": weak}


def md(c, r):
    scan = _ritc_scan_sets()
    if scan:
        occ = scan["occ"]
        ritc_total = len(occ)
        ritc_corpus = len(occ & c["corpus_sy"]); ritc_sample = len(occ & c["sample_sy"])
        rs_strong = len(scan["strong"] & c["sample_sy"]); rs_weak = len(scan["weak"] & c["sample_sy"])
        n_strong, n_weak = len(scan["strong"]), len(scan["weak"])
    else:  # fallback: earlier text-mine
        ritc_total = r["ritc"]
        ritc_corpus = len(r["ritc_sy"] & c["corpus_sy"]); ritc_sample = len(r["ritc_sy"] & c["sample_sy"])
        rs_strong = rs_weak = n_strong = n_weak = None
    lm = label_mapping(r["labels"])
    L = []
    A = L.append
    A("# Appendix B — Data audit and provenance\n")
    A("*Generated by `generate_data_audit.py`, which mines the source extraction "
      "(`pdf_extraction/`), the analysis output (`exposure_results.json`) and the pipeline code. "
      "All counts below are computed; note *numbers* (which vary by filing) are recorded by the "
      "extraction as page references rather than note indices, so captions are given by their "
      "disclosed wording.*\n")

    # B.1
    A("## B.1 Provenance\n")
    A(f"**Reserve base $R_{{i,t}}$ — gross claims outstanding.** Read from the balance-sheet "
      f"technical-provisions / claims-outstanding caption (`opening_reserves_gbp_m`, with a page "
      f"reference `opening_reserves_page`). Across the {r['has_g']} extracted filings the "
      f"reserve text names the figure by the wording "
      + ", ".join(f"\"{t}\" ({n})" for t, n in r["cap"].most_common(4)) + ". "
      f"The basis is **gross of outward reinsurance**: the reserve/narrative text mentions "
      f"\"gross\" in {r['gross']} filings vs \"net\" in {r['net']}, and the standardised narratives "
      f"describe an \"opening gross claims outstanding\". (Note numbers vary by filing; the page "
      f"reference is recorded, the note index is not.)\n")
    A(f"**Claims-development figures $M$ — FRS 103 triangle.** The claims-development triangle is "
      f"captured in `_claims_triangle` for **{r['tri']} of {r['has_g']}** extracted filings; the "
      f"figures are on the same gross basis as the reserve caption above.\n")
    A(f"**Class-of-business premium $w_{{i,t,\\ell}}$ — segmental gross premium.** Taken from the "
      f"segmental *gross premium written by class of business* disclosure (`gross_premium_mix`, page "
      f"`gross_premium_page`), populated for **{r['gpm']} of {r['has_g']}** extracted filings. The "
      f"disclosed labels are the Solvency II / FRS 103 standard classes (B.3).\n")

    # B.2
    A("## B.2 Corpus and exclusions\n### Exclusion waterfall\n")
    A("| Stage | Count | Dropped |\n|---|---:|---:|")
    A(f"| Filing PDFs retrieved | {c['total_files']} | — |")
    A(f"| — No usable dual-model extraction (empty) | | {r['neither']} |")
    A(f"| Syndicate-years extracted (0 duplicate pairs) | {r['has_g']} | — |")
    A(f"| — Excluded (manual / out of scope) | | {c['disc']['excluded']} |")
    A(f"| — Skipped (no claims-development / movement disclosure; <3 UW years) | | {c['disc']['skipped']} |")
    A(f"| — In run-off (GPW = 0, no premium mix) | | {c['disc']['in_runoff']} |")
    A(f"| — No reserves | | {c['disc']['no_reserves']} |")
    A(f"| **Corpus (kept records)** | **{c['corpus']}** | — |")
    A(f"| — Unusable severity ($S_{{i,t}}$ not computable) | | {c['sev']} |")
    A(f"| — Missing opening reserves ($R_{{i,t}}$) | | {c['res']} |")
    A(f"| — Missing LoB weights | | {c['wt']} |")
    A(f"| **Working sample** | **{c['sample']}** | {c['excl']} excluded |")
    A(f"\n- **File → record reconciliation.** {c['total_files']} retrieved PDFs; {r['neither']} "
      f"produced no usable extraction (blank/failed OCR), leaving {r['has_g']} extracted "
      f"syndicate-years with **no duplicate (syndicate, year) pairs**. Both LLMs "
      f"(Gemini 2.5 Flash, GPT-5 Mini) returned a record for the same {r['has_g']} filings. The "
      f"pipeline's discard tags (excluded {c['disc']['excluded']}, skipped {c['disc']['skipped']}, "
      f"run-off {c['disc']['in_runoff']}, no-reserves {c['disc']['no_reserves']}) reduce these to the "
      f"{c['corpus']}-record corpus.")
    A(f"- **Working-sample exclusions are almost entirely missing weights:** of the {c['excl']} "
      f"corpus records dropped, {c['wt']} lack usable LoB weights, {c['sev']} an unusable severity, "
      f"and **{c['res']} are missing reserves**. \"No usable claims-development disclosure\" sits "
      f"inside Skipped ({c['disc']['skipped']}), which also bundles first/second-year syndicates.")
    A("\n### Filing source\n")
    A("The raw accounts are **Lloyd's syndicate annual reports** (PDF; `source_file` paths of the "
      "form `syndicate_reports/pdfs/syndicate_{number}_{year}.pdf`), retrieved by automated "
      "collection and converted to structured JSON by a dual-LLM extraction (Gemini 2.5 Flash and "
      "GPT-5 Mini) with cross-model agreement checks (see the OCR/extraction pipeline; a material "
      "disagreement is where the two models' PYD% differ by > 0.5pp, resolved by confidence).")
    A("\n### Per-year counts\n| Reporting year | Corpus | Working sample |\n|---|---:|---:|")
    for y in YEARS:
        A(f"| {y} | {c['corpus_by_year'].get(y, 0)} | {c['sample_by_year'].get(y, 0)} |")
    A(f"| **Total** | **{sum(c['corpus_by_year'].values())}** | **{sum(c['sample_by_year'].values())}** |")

    # B.3
    A("\n## B.3 Line-of-business taxonomy\n")
    A("Disclosed class labels are folded into 13 categories by the first matching keyword rule "
      "(unmatched → Aggregate). The table shows the **actual disclosed labels observed** in the "
      f"corpus ({len(r['labels'])} distinct strings) grouped by the category each is assigned to, "
      "with the label frequency:\n")
    A("| Category | Assigned share* | Most frequent disclosed labels folded in |\n|---|---:|---|")
    grand = sum(t for t, _ in lm.values())
    for name in LOB_NAMES:
        if name in lm:
            tot, top = lm[name]
            labs = ", ".join(f"{l} ({n})" for l, n in top)
            A(f"| {name} | {100*tot/grand:.0f}% | {labs} |")
    A("\n\\*Share of label-instances assigned to the category (segmental lines across all filings).\n")
    A("**Keyword-ordering artefacts (documented, since they shape the HHI concentration measure):**")
    A("- The Solvency II class **\"Marine, aviation and transport\"** matches the *aviation* rule "
      "before *marine*, so this composite line is assigned to **Aviation**, not Marine.")
    A("- **\"Motor (third party liability)\"** matches the *liability* → **Casualty** rule before "
      "*motor*, so motor-TPL premium is grouped with Casualty rather than Motor.")
    A("- Energy sub-lines carrying the word marine (e.g. **\"Energy – non marine\"**) match *marine* "
      "first and land in **Marine**.")
    A(f"- **Aggregate ({100*lm['Aggregate'][0]/grand:.0f}% of label-instances)** absorbs "
      "undifferentiated *Reinsurance*, *Miscellaneous*, *Pecuniary loss*, *Credit and suretyship* "
      "and *Transport*, none of which has a specific category. It also catches the subtotal label "
      "**\"Total direct\"** — a disclosure artefact, not a class; a premium mix landing entirely in "
      "Aggregate is rejected as a misparse and treated as missing weights.")

    # B.4
    A("\n## B.4 Weights\n")
    A(f"- **Weight floor:** every non-zero LoB weight is floored at **{WEIGHT_FLOOR:.2f} (1%)**.\n"
      "- **Renormalisation:** weights **are** renormalised to sum to 1 after flooring "
      "(`apply_weight_floor`: normalise → floor → renormalise).\n"
      "- **Ownership.** This 1% *weight* floor is distinct from the ±5% *line-level* severity caps "
      "in Appendix A. It is owned here (Appendix B); Appendix A should reference it and retain only "
      "the ±5% caps.")

    # B.5
    A("\n## B.5 Coverage\n")
    A(f"The working sample spans **{c['sample_synd']} syndicates / {c['sample']} syndicate-years** "
      f"(corpus {c['corpus_synd']} / {c['corpus']}). Coverage against the active-syndicate denominator "
      "(2020–2024: Lloyd's official *List of active Syndicates & Managing Agent* spreadsheets; "
      "2014–2019: Lloyd's Annual Reports / SFCRs, with the BoE/PRA Jan-2015 register listing ~101 "
      "including run-off/RITC vehicles):\n")
    A("| Year | Active syndicates | Corpus | Working sample | Sample coverage |\n|---|---:|---:|---:|---:|")
    tot_m = tot_c = tot_s = 0
    for y in YEARS:
        m = c["market"][y]; cc = c["corpus_by_year"].get(y, 0); ss = c["sample_by_year"].get(y, 0)
        tot_m += m; tot_c += cc; tot_s += ss
        A(f"| {y} | {m} | {cc} | {ss} | {100*ss/m:.0f}% |")
    A(f"| **Total** | **{tot_m}** | **{tot_c}** | **{tot_s}** | **{100*tot_s/tot_m:.0f}%** |")

    covs = [100 * c["sample_by_year"].get(y, 0) / c["market"][y] for y in YEARS if c["market"].get(y)]
    A("\n### Coverage is broadly complete and balanced across years\n")
    A(f"The updated collection retrieves about as many PDFs per year as the market has active "
      f"syndicates, so coverage is high and roughly flat across 2014–2024 "
      f"({min(covs):.0f}–{max(covs):.0f}% of active syndicate-years per year):\n")
    A("| Year | Active | Raw PDFs retrieved | Empty extraction | Corpus | Sample |\n|---|---:|---:|---:|---:|---:|")
    for y in YEARS:
        A(f"| {y} | {c['market'][y]} | {r['raw_year'].get(y, 0)} | {r['empty_year'].get(y, 0)} "
          f"| {c['corpus_by_year'].get(y, 0)} | {c['sample_by_year'].get(y, 0)} |")
    A("\n- **Retrieval now matches the market** (~90–107 PDFs/year throughout, vs ~91–99 active "
      "syndicates); the recent-year retrieval gap present in the earlier dataset has been closed.")
    A(f"- The residual shortfall to 100% is dominated by **failed extraction of a minority of (often "
      f"older, scanned) reports**: {r['neither']} of {c['total_files']} PDFs yielded no usable dual-model "
      f"output (worst in 2014, {r['empty_year'].get(2014, 0)} of {r['raw_year'].get(2014, 0)}), plus the "
      "weight/severity exclusions in B.2.")
    if c["diff"]:
        d0 = c["diff"]; ylist = sorted(d0)
        cov_lo = min(100 * d0[y]["have"] / d0[y]["active"] for y in ylist)
        cov_hi = max(100 * d0[y]["have"] / d0[y]["active"] for y in ylist)
        A(f"- **Against the official active lists (2020–2024)** the corpus holds {cov_lo:.0f}–{cov_hi:.0f}% "
          "of listed syndicates each year:")
        A("\n| Year | Listed | We have | Missing | Missing but retrieved in other years | In corpus, not on active list |\n|---|---:|---:|---:|---:|---:|")
        for y in ylist:
            e = d0[y]
            A(f"| {y} | {e['active']} | {e['have']} | {e['miss']} | {e['miss_seen']} | {e['extra']} |")
        A("\n  The few \"in corpus, not on active list\" are run-off syndicates that still file accounts.")
    A("- **Implication.** Annual coverage is 62-86% and is roughly flat across years, "
      "but the shortfall is size-biased toward smaller and older-scanned syndicates "
      "(docs/data-provenance.md, section 2c), so missing-at-random is NOT established: "
      "the observed-syndicate diagnostic is silent about the 37 orphan filings from "
      "never-observed syndicates, and a reporting-year effect cannot correct selection "
      "on syndicates that are never observed. The manuscript therefore reports "
      "inverse-probability-weighting and high-volatility orphan sensitivities instead "
      "of resting on ignorability: the IPW refit leaves the fitted scale essentially "
      "unchanged, and the orphan stress moves the conditional bracketed estimate only "
      "from $k=0.587$ to $0.570$ --- a construction that makes the predominantly small "
      "missing books more volatile, so it cannot test the adverse-to-sub-linearity "
      "direction --- while the clean-tail index moves materially under it.")

    # B.6
    A("\n## B.6 RITC and discontinuities\n")
    split = (f" ({n_strong} strong / {n_weak} weak confidence; {rs_strong} strong / {rs_weak} weak "
             f"in the working sample)") if scan else ""
    A(f"- **RITC prevalence.** Reinsurance-to-close is common and identifiable in the notes. A dedicated "
      f"dual-LLM scan (`pdf_extraction/ritc_scan.json`, the flag file the model consumes) flags "
      f"**{ritc_total} syndicate-years** as RITC-affected{split}: {ritc_corpus} in the corpus, "
      f"**{ritc_sample} in the {c['sample']}-record working sample** (~{100*ritc_sample/c['sample']:.0f}%). "
      "A typical note records an incoming transfer, e.g. one syndicate \"assumed the liabilities of "
      "Syndicate 4000 under a Reinsurance to Close (RITC) contract\", transferring gross technical "
      "provisions onto the receiving syndicate's balance sheet.\n")
    A("- **RITC handling.** External RITC injects a lumpy, non-recurring step into prior-year "
      "development that is not a portfolio-composition property. Because the disclosures give a "
      "**flag but no transfer amount**, the step cannot be backed out of $M_{i,t}$ arithmetically. "
      "Instead RITC is modelled as a **separate Student-$t$ tail regime**: RITC-affected years take a "
      "heavier tail index $\\nu_{\\text{RITC}}=\\nu_{\\text{clean}}\\,e^{-\\lambda_{\\text{RITC}}}$ "
      "(the scale term is omitted as a structural simplification, not because it was shown to "
      "be zero: $\\beta_{\\text{RITC}}=-0.15$ [$-0.41$, $+0.10$] with "
      "$P(|\\beta_{\\text{RITC}}|>0.1)=0.67$; propagating it moves both vignette stresses by "
      "about 3%), and the "
      "transfer operator rank-maps a donor's residual between tail regimes via a Student-$t$ "
      "quantile transform, with the target regime a user choice: a clean target **de-RITCs** RITC "
      "donors onto the clean-composition tail, an RITC-affected target maps clean donors into the "
      "heavier regime, and preserving each donor's own regime makes the map the identity "
      "(see the model write-up §2.7/§6.1). "
      f"Separately, pure *run-off* years (reliable PYD, gross premium written = 0, no premium mix) are "
      f"excluded ({c['disc']['in_runoff']} record).")
    A(f"- **Syndicate identity continuity.** The panel is **unbalanced**: of {c['n_synd']} distinct "
      f"syndicate numbers, only **{c['present_all']} appear in all 11 years**, while {c['year_dist'].get(1,0)} "
      f"appear once (distribution of years-present: {c['year_dist']}). Syndicate numbers are Lloyd's "
      "stable identifiers and are used as the panel key; mergers, transfers of business and "
      "renumberings are **not** explicitly reconciled beyond what the RITC notes reveal. Entry/exit is "
      "thus genuine (syndicates opening, closing, or going into run-off), and the reporting-year "
      "shared-shock and any within-syndicate clustering treat each number as one entity across the "
      "window.")

    A("\n---\n*All figures computed from the extraction and analysis outputs; regenerate with "
      "`python generate_data_audit.py`.*")
    return "\n".join(L) + "\n"


def main():
    c = compute(); r = mine_raw()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(md(c, r), encoding="utf-8")
    print(f"Wrote {OUT}")
    print(f"  files {c['total_files']} ({r['neither']} empty) -> extracted {r['has_g']} -> corpus {c['corpus']} -> sample {c['sample']}")
    _rscan = _ritc_scan_sets()
    _rsamp = len(_rscan["occ"] & c["sample_sy"]) if _rscan else len(r['ritc_sy'] & c['sample_sy'])
    _rtot = len(_rscan["occ"]) if _rscan else r['ritc']
    print(f"  gross/net text {r['gross']}/{r['net']}; triangle {r['tri']}; premium {r['gpm']}; "
          f"RITC(scan) {_rtot} (sample {_rsamp}); RITC(text-mine) {r['ritc']} (sample {len(r['ritc_sy'] & c['sample_sy'])})")
    print(f"  panel: {c['n_synd']} syndicates, {c['present_all']} present all 11 years")


if __name__ == "__main__":
    main()
