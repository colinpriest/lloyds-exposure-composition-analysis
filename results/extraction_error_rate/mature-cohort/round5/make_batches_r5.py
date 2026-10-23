"""Round-5 batches: every record the rebase screen asks to read (except 2689_2023, already read twice), to two arms
P1..P8 and Q1..Q8, each record once per arm, the arms chunked differently."""
import io
import json
import os

S = r"D:/tmp/r62/oc/rebase/rebase_screen.json"
with io.open(S, encoding="utf-8") as fh:
    d = json.load(fh)
rn = d["reading_needed"]
groups = list(rn.items()) + [("D_alignment_uncertain", [x if isinstance(x, str) else x.get("key")
                                                        for x in d.get("alignment_uncertain", [])]),
                             ("D_no_identity_evidence", [x if isinstance(x, str) else x.get("key")
                                                         for x in d.get("no_identity_evidence", [])])]
seen, recs = set(), []
KEEP = ("key", "verdict", "status", "report_currency", "t_page", "p_page", "t_units", "p_units", "t_currency",
        "p_currency", "t_years", "p_years", "t_aggregated_anchor", "p_aggregated_anchor", "shift", "lag_t", "lag_p",
        "alignment_uncertain", "units_differ", "v1_top_donor_rank", "s_raw_a", "source")
for g, keys in groups:
    for k in keys:
        if not k or k in seen or k == "2689_2023":
            continue
        seen.add(k)
        r = d["records"].get(k, {"key": k})
        e = {f: r.get(f) for f in KEEP if f in r}
        e["key"] = k
        e["screen_group"] = g
        for f in ("factor", "factor_rule", "size_vs_R", "size_vs_M", "flag_tier", "confidence", "flag_reasons",
                  "units_note", "opening_reserves_m", "M_m"):
            if f in r:
                e[f] = r[f]
        e["years"] = [{kk: y.get(kk) for kk in ("u", "oldest_col", "in_M_years", "cell_t", "cell_p", "age_t",
                                                 "ratio", "flagged")} for y in r.get("years", [])]
        e["filing_t"] = "syndicate_%s" % k
        syn, yr = k.split("_")
        e["filing_prev"] = "syndicate_%s_%d" % (syn, int(yr) - 1)
        recs.append(e)
print("records:", len(recs))
x = [recs[i::8] for i in range(8)]
rot = recs[len(recs) // 2:] + recs[:len(recs) // 2]
y = [rot[i::8][::-1] for i in range(8)]
for arm, parts in (("P", x), ("Q", y)):
    for i, part in enumerate(parts):
        out = os.path.join(r"D:/tmp/r62/oc/readings", "%s%d" % (arm, i + 1))
        os.makedirs(out, exist_ok=True)
        with io.open(os.path.join(out, "batch.json"), "w", encoding="utf-8", newline="") as fh:
            fh.write(json.dumps(part, indent=1) + "\n")
print("P sizes", [len(p) for p in x], "Q sizes", [len(p) for p in y])
assert {r["key"] for p in x for r in p} == {r["key"] for p in y for r in p}
