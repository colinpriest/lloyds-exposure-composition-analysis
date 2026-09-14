r"""stage_extraction_error_rate.py: the ninth amendment's files, the take-on base census, and the eighth census's batch 12b.

  - FILES["ninth-census"]: the census, its dry runs and probe, briefs, carry-over skeleton and decisions, fresh stems,
    packs log, merged first readings, second readings, result and draft; checks and scripts (the readings modules
    by glob); PACK_DIRS["ninth-census/packs"]; NINTH_BATCH_GLOBS, staged like the eighth census's.
  - batches_match takes the names of extra batch files a label allows. The eighth census allows batch 12b, whose files
    must exist: batch 12's reader stopped on its spend limit after one record, and batch 12b read the other two.
  - README: the eighth census's paragraph names batch 12b; a section on the eighth census's repairs and the take-on base
    census, with a table of the adjusted records (from the result, checked against the committed register); the ninth
    census in "Who read the filings" and "Files".

Every anchor must match exactly once; otherwise the script writes nothing.

    python patch_stage_ninth.py
"""
import io
from pathlib import Path

SCR = Path(__file__).resolve().parent
STAGE = SCR / "stage_extraction_error_rate.py"

SUBS = [
    ('EIGHTH_BATCH_GLOBS = ("error-rate-briefs-eighth-batch-*.json", "reader-prompt-eighth-batch-*.txt",\n'
     '                      "error-rate-verdicts-eighth-batch-*.json")\n',
     'EIGHTH_BATCH_GLOBS = ("error-rate-briefs-eighth-batch-*.json", "reader-prompt-eighth-batch-*.txt",\n'
     '                      "error-rate-verdicts-eighth-batch-*.json")\n'
     '# batch 12 of the eighth census stopped on the spend limit after one record; batch 12b read the other two\n'
     'EIGHTH_RERUN = ("error-rate-briefs-eighth-batch-12b.json", "reader-prompt-eighth-batch-12b.txt",\n'
     '                "error-rate-verdicts-eighth-batch-12b.json")\n'
     '# the ninth amendment: the eighth census\'s repairs, the take-on base, its census and refit 3\n'
     'FILES["ninth-census"] = ["error-rate-census-ninth.json", "census-ninth-dryrun.log", "census-ninth-dryrun2.log",\n'
     '                         "census-ninth-dryrun3.log", "census-ninth.log", "probe-census-ninth-rows.txt",\n'
     '                         "error-rate-briefs-ninth.json", "error-rate-carry-over-ninth-skeleton.json",\n'
     '                         "error-rate-carry-over-ninth.json", "error-rate-fresh-stems-ninth.json", "packs-ninth.log",\n'
     '                         "error-rate-verdicts-ninth.json", "error-rate-verification-ninth.json",\n'
     '                         "error-rate-census-ninth-result.json", "ninth-repairs-draft.json"]\n'
     'FILES["checks"] += ["predict-refit3-a4b.txt", "mutate-takeon-base.txt"]\n'
     'FILES["scripts"] += ["make_batch_12b.py", "record_eighth_readings.py", "register_eighth_repairs.py",\n'
     '                     "patch_run_analysis_takeon_base.py", "mutate_takeon_base.py", "make_census_ninth.py",\n'
     '                     "probe_census_ninth_rows.py", "carry_view_ninth.py", "carry_decisions_ninth.py",\n'
     '                     "record_carry_ninth.py", "make_reader_prompts_ninth.py", "patch_second_read_ninth.py",\n'
     '                     "score_error_rate_ninth.py", "register_ninth_takeon_base.py", "record_ninth_state.py",\n'
     '                     "patch_stage_ninth.py"]\n'
     'FILES["scripts"] += sorted(p.name for p in SCR.glob("readings_eighth_part*.py"))\n'
     'FILES["scripts"] += sorted(p.name for p in SCR.glob("readings_ninth_part*.py"))\n'
     'PACK_DIRS["ninth-census/packs"] = "packs-error-rate-ninth"\n'
     'NINTH_BATCH_GLOBS = ("error-rate-briefs-ninth-batch-*.json", "reader-prompt-ninth-batch-*.txt",\n'
     '                     "error-rate-verdicts-ninth-batch-*.json")\n'),
    ('def batches_match(fresh_file, globs, label, size=10):\n'
     '    n_fresh = len(load(fresh_file))\n'
     '    n_batches = (n_fresh + size - 1) // size\n'
     '    for pattern in globs:\n'
     '        found = len(list(SCR.glob(pattern)))\n',
     'def batches_match(fresh_file, globs, label, size=10, extra=()):\n'
     '    n_fresh = len(load(fresh_file))\n'
     '    n_batches = (n_fresh + size - 1) // size\n'
     '    absent = [name for name in extra if not (SCR / name).is_file()]\n'
     '    if absent:\n'
     '        raise SystemExit("%s: the extra batch files it allows are missing: %s" % (label, absent))\n'
     '    for pattern in globs:\n'
     '        found = len([p for p in SCR.glob(pattern) if p.name not in extra])\n'),
    ('n_eighth_fresh, eighth_batches = batches_match("error-rate-fresh-stems-eighth.json", EIGHTH_BATCH_GLOBS,\n'
     '                                              "eighth census", size=5)\n',
     'n_eighth_fresh, eighth_batches = batches_match("error-rate-fresh-stems-eighth.json", EIGHTH_BATCH_GLOBS,\n'
     '                                              "eighth census", size=5, extra=EIGHTH_RERUN)\n'
     'n_ninth_fresh, ninth_batches = batches_match("error-rate-fresh-stems-ninth.json", NINTH_BATCH_GLOBS,\n'
     '                                            "ninth census", size=5)\n'),
    ('for folder, globs in (("tail", TAIL_BATCH_GLOBS), ("third-sample", THIRD_BATCH_GLOBS),\n'
     '                      ("eighth-census", EIGHTH_BATCH_GLOBS)):\n',
     'for folder, globs in (("tail", TAIL_BATCH_GLOBS), ("third-sample", THIRD_BATCH_GLOBS),\n'
     '                      ("eighth-census", EIGHTH_BATCH_GLOBS), ("ninth-census", NINTH_BATCH_GLOBS)):\n'),
    ('if sum(eighth_sizes) != n_eighth_fresh:\n'
     '    raise SystemExit("eighth-census batch sizes %s do not add up to %d" % (eighth_sizes, n_eighth_fresh))\n',
     'if sum(eighth_sizes) != n_eighth_fresh:\n'
     '    raise SystemExit("eighth-census batch sizes %s do not add up to %d" % (eighth_sizes, n_eighth_fresh))\n'
     '# --- the ninth amendment ------------------------------------------------------------------------------------------\n'
     'census9 = load("error-rate-census-ninth-result.json")\n'
     'census9_file = load("error-rate-census-ninth.json")\n'
     'carried9 = sum(1 for d in load("error-rate-carry-over-ninth.json")["decisions"] if d["carry"])\n'
     'base_register, _ = committed_json(AN, "data/opening_reserves_takeon_base.json")\n'
     'ninth_sizes = [len(load("error-rate-briefs-ninth-batch-%d.json" % i)) for i in range(1, ninth_batches + 1)]\n'
     'if sum(ninth_sizes) != n_ninth_fresh:\n'
     '    raise SystemExit("ninth-census batch sizes %s do not add up to %d" % (ninth_sizes, n_ninth_fresh))\n'
     'adjusted9 = [r for r in census9["table"] if r["outcome"] == "adjusted"]\n'
     'if sorted(r["stem"].replace("syndicate_", "") for r in adjusted9) != sorted(k for k in base_register if not k.startswith("_")):\n'
     '    raise SystemExit("the committed take-on base register does not hold the census\'s adjusted records")\n'
     'base_lines = "\\n".join("| %s | %s | %s | %.2f%% | %.2f%% |" % (\n'
     '    key(r["stem"]), m(r["opening_m"]).lstrip("+"), m(base_register[r["stem"].replace("syndicate_", "")]["takeon_m"]).lstrip("+"),\n'
     '    r["severity_pct"], r["severity_pct_adjusted"]) for r in adjusted9)\n'
     'no_transfer9 = [r["stem"] for r in census9["table"] if r["outcome"] != "adjusted" and r["first"]["finding"] is False]\n'
     'small9 = [r["stem"] for r in census9["table"] if r["outcome"] != "adjusted" and r["first"]["finding"] is not False\n'
     '          and "under 5%" in r["reason"]]\n'
     'other9 = ["%s (%s)" % (key(r["stem"]), r["reason"]) for r in census9["table"] if r["outcome"] != "adjusted"\n'
     '          and r["stem"] not in no_transfer9 and r["stem"] not in small9]\n'
     'rules9 = ", ".join("%s %d" % (rule, len(v)) for rule, v in census9_file["parts"].items())\n'),
    ('in {sizes(eighth_sizes)}. The dry runs that tightened three rules before any reading are kept beside it.\n',
     'in {sizes(eighth_sizes)}; batch 12\'s reader stopped on its spend limit after one record, and batch 12b read the other\n'
     'two. The dry runs that tightened three rules before any reading are kept beside it.\n'),
    ('\n### The effect on Vignette 1\'s VaR99.5 (`propagation/`)\n',
     '\n### The eighth census\'s repairs and the take-on base (`ninth-census/`)\n'
     '\n'
     'The eighth census\'s confirmed errors are repaired through the same registers (ninth amendment, point 1), with the\n'
     'owner deciding 2010/2015\'s figure. The census also found a take-on base: a triangle restated to carry business\n'
     'taken on in the report year covers it on both diagonals of its step, while the opening reserves at 1 January\n'
     'exclude it, so the severity is overstated. On 14 September 2026 the owner decided to adjust the opening reserves.\n'
     '\n'
     'The take-on base census was computed and written on {census9_file["written"]}, before any of its records was read,\n'
     'from three rules over the {census9_file["working_sample_n"]} records of the working sample the loader predicted for\n'
     'refit 3 ({rules9}; a record may meet several). Two dry runs tightened the row rule before any reading.\n'
     '{len(census9_file["stems"])} records were listed: {carried9} kept both eighth-census readings, and {n_ninth_fresh} were read\n'
     'afresh, in {sizes(ninth_sizes)}. Adjusted (`data/opening_reserves_takeon_base.json`, analysis repository {an_head}):\n'
     '\n'
     '| Record | Opening reserves | Taken on and covered | Severity before | Severity after |\n'
     '|---|---|---|---|---|\n'
     '{base_lines}\n'
     '\n'
     'Not adjusted: {len(no_transfer9)} records with no transfer the adopted figure covers; {len(small9)} whose covered\n'
     'transfer is under 5% of the opening reserves; and {listing(other9)}.\n'
     '\n'
     '### The effect on Vignette 1\'s VaR99.5 (`propagation/`)\n'),
    ('  was read in %s records, the second sample\'s fresh records in %s, the third sample\'s in %s, and the eighth\n'
     '  census\'s in %s.\n',
     '  was read in %s records, the second sample\'s fresh records in %s, the third sample\'s in %s, the eighth\n'
     '  census\'s in %s (and batch 12b of two), and the take-on base census\'s in %s.\n'),
    ('""" % (sizes(first_sizes), sizes(after_sizes), sizes(third_sizes), sizes(eighth_sizes),\n',
     '""" % (sizes(first_sizes), sizes(after_sizes), sizes(third_sizes), sizes(eighth_sizes), sizes(ninth_sizes),\n'),
    ('- `third-sample/findings/` and `eighth-census/`: as described above; `eighth-census/packs/` holds the census\'s\n'
     '  evidence packs.\n',
     '- `third-sample/findings/` and `eighth-census/`: as described above; `eighth-census/packs/` holds the census\'s\n'
     '  evidence packs.\n'
     '- `ninth-census/`: the take-on base census, its dry runs and probe, briefs, carry-over skeleton and decisions,\n'
     '  reader prompts, first and second readings, result and draft; `ninth-census/packs/` holds its evidence packs.\n'),
]


def patched(path, subs):
    text = io.open(str(path), encoding="utf-8", newline="").read()
    nl = "\r\n" if "\r\n" in text else "\n"
    for old, new in subs:
        old, new = old.replace("\n", nl), new.replace("\n", nl)
        if text.count(old) != 1:
            raise SystemExit("%s: anchor found %d times, nothing written: %r" % (path.name, text.count(old), old[:90]))
        text = text.replace(old, new)
    return text


text = patched(STAGE, SUBS)
io.open(str(STAGE), "w", encoding="utf-8", newline="").write(text)
print("patched %s" % STAGE.name)
