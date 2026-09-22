r"""The study README follows the tenth amendment: its counts of amendments and notes, a section on the tenth census,
the tenth census's propagation beside the ninth amendment's, who read its records, and its folder.

Every number is read from the study's own files (the protocol's headings, tenth-census/census-tenth-result.json,
tenth-census/partial-premium/partial-premium-after-repairs.json, tenth-census/tail-entrants-tenth.json and
propagation/error-rate-propagation-tenth.json), not typed. It refuses to run twice.

    python results/extraction_error_rate/scripts/write_readme_tenth.py [--dry-run]
"""
import io
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
STUDY = os.path.abspath(os.path.join(HERE, ".."))
README = os.path.join(STUDY, "README.md")
DRY = "--dry-run" in sys.argv
ORD = {"Second": 2, "Third": 3, "Fourth": 4, "Fifth": 5, "Sixth": 6, "Seventh": 7, "Eighth": 8, "Ninth": 9,
       "Tenth": 10, "Eleventh": 11, "Twelfth": 12}


def load(rel):
    return json.load(io.open(os.path.join(STUDY, *rel.split("/")), encoding="utf-8"))


def pct(x):
    return "%.1f%%" % (100.0 * x)


def counts():
    heads = [l for l in io.open(os.path.join(STUDY, "protocol", "error-rate-protocol.md"), encoding="utf-8")
             if l.startswith("## ")]
    amend = [h for h in heads if re.match(r"## (?:\w+ )?[Aa]mendment,", h)]
    notes = [h for h in heads if h.startswith("## Implementation note")]
    return len(amend), len(notes)


def section():
    t = load("tenth-census/census-tenth-result.json")
    after = load("tenth-census/partial-premium/partial-premium-after-repairs.json")
    tail = load("tenth-census/tail-entrants-tenth.json")
    fy = [r for r in t["first_year"]]
    pm = [r for r in t["provision_movement"]]
    tb = [r for r in t["transfer_blamed_blanks"] if r["in_working_sample"]]
    esc = [r["stem"].replace("_", "/") for r in tb if not r["in_regime_before"]]
    pp = t["partial_premium"]
    rows = "\n".join("| %s | %s | %s | %s | %s |" % (
        r["stem"].replace("_", "/"), "%+.3fm" % r["adopted_m"],
        ("%+.3fm" % r["filing_figure_m"]) if r["filing_figure_m"] is not None else "none",
        r["verdict"], r["repair"]) for r in t["found_in_passing"])
    ent = tail["entrants"]
    el = load("tenth-census/entrants/entrants-result.json")

    def figs(r):
        return "; ".join("%s %s%s" % (k, v["verdict"], "" if v["figure_m"] is None else " (%+.3fm)" % v["figure_m"])
                         for k, v in sorted(r["readings"].items()))
    el_rows = "\n".join("| %s | %s | %+.3fm | %s | %s |" % (
        r["stem"].replace("_", "/"), r["why"], r["adopted_m"], figs(r),
        r["outcome"] + ("" if r["figure_m"] is None or r["outcome"] == "stands" else " to %+.3fm" % r["figure_m"]))
        for r in el["records"])
    ent_txt = ", ".join("%s (rank %d%s)" % (r["stem"][len("syndicate_"):].replace("_", "/"), r["rank"],
                                           "" if r["read"] else ", unread") for r in ent) or "none"
    twelfth = [r for r in el["records"] if "twelfth amendment" in r["why"]]
    if len(twelfth) != 1:
        raise SystemExit("entrants-result.json has %d twelfth-amendment records" % len(twelfth))
    tw = twelfth[0]
    tw_txt = ("After those repairs the refit brought one more unread donor into Vignette 1's top 20, %s, and the twelfth "
              "amendment had it read twice the same way (`entrants/readings/reader-F.txt`, `reader-G.txt`, with each "
              "reader's instruction): the table's last row." % tw["stem"].replace("_", "/"))
    return """### The tenth census (`tenth-census/`)

A frozen external review of the submission (21 September 2026) found three mechanisms the samples and censuses had
not reached (tenth amendment). Each was counted across the corpus by a script written before any of its records was
read (`scripts/make_census_tenth.py`), on the records and results of analysis commit %s, before the repairs
(`census-tenth-result.json`):

- A figure that is not development, adopted from one model. The no-mature-cohort rule flags %d records (%d in the
  working sample) and the provision-movement rule %d (%d); the working-sample record is 1884/2016 under both. The
  loader now counts the first with the skipped first-year reports and gives the second no severity, and the
  extraction writes 1884/2016 as a first-year stub.
- An inward transfer described without a transaction noun. %d working-sample records carry a figure a route filled
  after both models blamed a transfer; %d of them were outside the RITC regime (%s). The transfer scan now reads such
  a sentence (`transfer-scan/`), and every confirmed take-on is a regime source.
- A premium table read in part. %d records' classes sum to under 80%% of a premium total two independent readings
  agree on, %d of them in the working sample (`partial-premium/`). After the repairs and the extraction's replay the
  same rule finds %d in the working sample of %d, and none more than 2%% (or 0.2m) from every such total; %d records
  have no such pair, because their tables print the total with a currency sign the parser does not read
  (`partial-premium/partial-premium-after-repairs.json`, implementation note 8).

The records found in passing were each read twice, by two agents reading independently of each other
(`readings/reader-A.md`, `readings/reader-B.md`, with the instruction each was given):

| Record | Adopted | Filing's figure | Verdict | Repair |
|---|---|---|---|---|
%s

Implementation notes 6, 7 and 10 record how 1856/2018, 1856/2020 and 3334/2018 were decided. On 22 September 2026 the
owner excluded 1856/2020, as note 7 had registered it, and chose 3334/2018's retained opening reserves, 78.791m (the
printed 116.773m less the 37.982m of run-off reserves transferred out; `data/opening_reserves_confirmed.json`). The
repair column above gives the plan as the census recorded it on 21 September.

The tail stratum was drawn from refit 3 and is reported as drawn. After the repairs, %d donors enter Vignette 1's top
20: %s (`tail-entrants-tenth.json`).

The repairs brought five records into the working sample that no sample or census had read, and the refit after them
put one of them, 3010/2022, first in Vignette 1's pool. The eleventh amendment had them and 1969/2018, the one unread
donor in the refit's top 20, read twice by two readers reading independently (`entrants/readings/`, with each reader's
instruction), and one record the second reader found in passing read by a third (implementation note 9;
`entrants/entrants-result.json`):

| Record | Why read | Adopted | Readings | Outcome |
|---|---|---|---|---|
%s

The two readings of 3010/2022 agree on every number and on the figure the paper's rule gives; they differ on the
score, which no rate uses (implementation note 9, point 3).

%s

""" % (t["analysis_commit"][:7], len(fy), sum(r["in_working_sample"] for r in fy), len(pm),
       sum(r["in_working_sample"] for r in pm), len(tb), len(esc), " and ".join(esc), pp["total"],
       pp["total_in_working_sample"], after["partial_n"], after["working_sample_n"], after["no_agreed_total_n"],
       rows, len(ent), ent_txt, el_rows, tw_txt)


def propagation():
    p = load("propagation/error-rate-propagation-tenth.json")
    h, post, fixed = p["headline"], p["p_from_posterior"], p["p_at_posterior_97_5"]
    a, b = p["rate_posterior"]["alpha"], p["rate_posterior"]["beta"]

    def cell(block, m):
        r = block[m]["relative_change"]
        return "%s [%s, %s] | %.3f" % (pct(r["median"]), pct(r["p2_5"]), pct(r["p97_5"]),
                                       block[m]["P_abs_relative_change_gt_5pct"])
    table = "\n".join("| %s | %s | %s |" % (m, cell(post, m), cell(fixed, m)) for m in ("sign", "replace", "shift"))
    return """The tenth census's repairs, computed on analysis commit %s%s with both fits read by the inverse CDF
(`before-refit3-inverse-cdf.json`, `error-rate-propagation-tenth.json`): VaR99.5 moved from %.4f to %.4f (%+.1f%%).
For errors not yet found on the final fit, %d replicates (seed %d) drew an error rate from the posterior
Beta(%.1f, %.1f), a count among the %d working-sample records no sample or census read, and changed each chosen
record's severity under the same three error models, the shifts drawn from %d confirmed errors
(`../tenth-census/error-rate-confirmed-errors-tenth.json`).

| Error model | Relative change, rate from the posterior: median [2.5%%, 97.5%%] | P(abs > 5%%) | Rate at the posterior's 97.5%% point (%.3f): median [2.5%%, 97.5%%] | P(abs > 5%%) |
|---|---|---|---|---|
%s

""" % (p["analysis_commit"], " (tree with uncommitted changes)" if p["analysis_tree_dirty"] else "",
       h["V1_VaR995_before_repairs"], h["V1_VaR995_after_repairs"], 100.0 * h["relative_change_from_repairs"],
       p["replicates"], p["seed"], a, b, p["unread_working_sample_records"], len(p["confirmed_error_shifts"]),
       p["rate_posterior"]["p97_5"], table)


def main():
    raw = io.open(README, encoding="utf-8", newline="").read()
    crlf = "\r\n" in raw
    t = raw.replace("\r\n", "\n")
    if "### The tenth census (`tenth-census/`)" in t:
        raise SystemExit("the README already has the tenth census")
    n_amend, n_notes = counts()
    head = re.search(r"Its \d+\s+amendments, its clarification and its \d+ implementation notes", t)
    if not head:
        raise SystemExit("the README's count sentence has changed")
    t = t[:head.start()] + ("Its %d\namendments, its clarification and its %d implementation notes" % (n_amend, n_notes)
                            if "\n" in head.group(0) else
                            "Its %d amendments, its clarification and its %d implementation notes" % (n_amend, n_notes)
                            ) + t[head.end():]
    edits = [
        ("### The effect on Vignette 1's VaR99.5 (`propagation/`)\n\nComputed on analysis commit 2d0df44. The repairs",
         section() + "### The effect on Vignette 1's VaR99.5 (`propagation/`)\n\nThe repairs to the ninth amendment, "
         "under the quantile rule then in use (numpy type 7), computed on analysis commit 2d0df44. The repairs"),
        ("`error-rate-propagation-SMOKE-refit1-placeholder-rate.json` is a smoke run",
         propagation() + "`error-rate-propagation-SMOKE-refit1-placeholder-rate.json` is a smoke run"),
        ("its route field, and a seeded random fifth of the remaining corrects. It read every record of each census and\n"
         "  every record found in passing.\n",
         "its route field, and a seeded random fifth of the remaining corrects. It read every record of each census and\n"
         "  every record found in passing, except the tenth census's and the eleventh and twelfth amendments': those were\n"
         "  read by Claude Code agents running Claude Opus 5, two to a record, each without the other's reading\n"
         "  (`tenth-census/readings/`, `tenth-census/entrants/readings/`).\n"),
        ("- `superseded/`: the draw of 13 September",
         "- `tenth-census/`: the tenth amendment's census (`census-tenth-result.json`), the premium census's files and its\n"
         "  run after the repairs (`partial-premium/`), the transfer scan's new flags (`transfer-scan/`), the two readings\n"
         "  of the records found in passing with the instruction each reader was given (`readings/`), the tenth\n"
         "  amendment's propagation inputs (`error-rate-read-stems-tenth.json`, `error-rate-confirmed-errors-tenth.json`),\n"
         "  the donors entering Vignette 1's top 20 after the repairs (`tail-entrants-tenth.json`), and the eleventh and\n"
         "  twelfth amendments' readings of the records the repairs brought in, with each reader's instruction and the\n"
         "  outcomes (`entrants/`).\n"
         "- `superseded/`: the draw of 13 September"),
    ]
    for old, new in edits:
        if t.count(old) != 1:
            raise SystemExit("README anchor occurs %d times: %r" % (t.count(old), old[:70]))
        t = t.replace(old, new, 1)
    if DRY:
        print("ready: %d amendments, %d implementation notes" % (n_amend, n_notes))
        return 0
    io.open(README, "w", encoding="utf-8", newline="").write(t.replace("\n", "\r\n") if crlf else t)
    print("README.md: written (%d amendments, %d implementation notes)" % (n_amend, n_notes))
    return 0


if __name__ == "__main__":
    sys.exit(main())
