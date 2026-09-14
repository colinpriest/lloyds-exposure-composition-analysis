r"""Stage the extraction error-rate study for its cited home, results/extraction_error_rate/ in the analysis repository.

Copies every file the study's results rest on, from this scratchpad, into a staging folder laid out as the
analysis repository will hold it. Writes MANIFEST.json (each file's source, size and SHA-256) and README.md,
whose counts, intervals, run identifiers, batch sizes and register entries are read from the study's own files
and from the repositories' committed registers, not typed. Nothing is written to the analysis repository.

Layout
  protocol/          error-rate-protocol.md (fixed 11 September 2026; its amendments, clarification and
                     implementation notes are dated)
  first-sample/      the draw of 60 from the working sample of 707, everything read and scored on it
  second-sample/     the draw of 60 from the rebuilt working sample of 698 (fourth amendment), and the same
  superseded/        the draw withdrawn before any reading (second amendment), its packs, and the draw script
                     first written for the protocol, never run (amendment, point 2)
  checks/            each rebuilt working sample against the prediction written before it (third and fourth
                     amendments), with the working samples they compare
  tail/              the tail stratum, computed after the final refit
  census/            the census of the second sample's two error mechanisms (fifth amendment, point 1)
  takeon-census/     the RITC-regime records whose adopted figure could be the take-on itself (sixth amendment)
  found-in-passing/  the records the mapping of the extraction code named (seventh amendment, point 2)
  repairs/           the errors confirmed before repair, the mechanism scans and the offline replays that
                     measured the repairs (fifth amendment, point 2; seventh amendment)
  third-sample/      the draw of 110 after the repairs (fifth amendment, point 3), everything read and scored on
                     it, and the first briefs set aside before any reading (implementation note 2)
  third-sample/findings/  what the third sample's readings found, and the read-only scans that sized each
                     mechanism before the eighth amendment
  eighth-census/     the census of the third sample's mechanisms (eighth amendment): its dry runs, briefs,
                     readings, result and repair drafts
  propagation/       the errors' effect on Vignette 1's VaR99.5 (fifth amendment, point 5), and the smoke run on
                     the refit before the repairs with placeholder rates
  scripts/           the scripts that drew, briefed, merged, verified, scored, scanned and propagated
It refuses to run if an expected file is missing, if a batch count does not match the records read afresh, or if
the propagation was computed on an analysis tree with uncommitted changes.

    python stage_extraction_error_rate.py
"""
import hashlib
import io
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

SCR = Path(__file__).resolve().parent
OUT = SCR / "extraction_error_rate_staging"
EXT = Path(r"D:/dev/lloyds_reserve_stress_testing")
AN = Path(r"D:/dev/IME-Lloyds-exposure-composition")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

FIRST_BATCHES = range(1, 7)
AFTER_BATCHES = range(1, 6)
FILES = {
    "protocol": ["error-rate-protocol.md"],
    "first-sample": (["error-rate-sample.json", "error-rate-primary-stems.json", "error-rate-html-stems.json",
                      "error-rate-briefs.json", "packs-error-rate.log"]
                     + ["error-rate-briefs-batch-%d.json" % i for i in FIRST_BATCHES]
                     + ["reader-prompt-batch-%d.txt" % i for i in FIRST_BATCHES]
                     + ["error-rate-verdicts-batch-%d.json" % i for i in FIRST_BATCHES]
                     + ["error-rate-verdicts.json", "fallback-routes-pre-r208.json",
                        "error-rate-verification-set.json", "error-rate-verification.json", "error-rate-result.json"]),
    "second-sample": (["error-rate-sample-after.json", "error-rate-carry-over.json", "error-rate-fresh-stems.json",
                       "error-rate-briefs-after.json", "packs-error-rate-after.log"]
                      + ["error-rate-briefs-after-batch-%d.json" % i for i in AFTER_BATCHES]
                      + ["reader-prompt-after-batch-%d.txt" % i for i in AFTER_BATCHES]
                      + ["error-rate-verdicts-after-batch-%d.json" % i for i in AFTER_BATCHES]
                      + ["error-rate-after-check.txt", "error-rate-after-merge.txt", "error-rate-verdicts-after.json",
                         "error-rate-verification-set-after.json", "error-rate-verification-after.json",
                         "error-rate-result-after-rerun.json"]),
    "superseded": ["error-rate-sample-superseded-1.json", "error-rate-primary-stems-superseded-1.json",
                   "draw_error_rate_sample.py"],
    "checks": ["compare_working_sample.py", "route-correction-probe.json", "r208-exposure-results-before.json",
               "compare_r209_r210.py", "r209-verified.json", "r210-rule-comparison.json",
               "r209-exposure-results-before.json", "compare-r209-r210.txt"],
    "scripts": ["draw_error_rate_primary.py", "draw_error_rate_after.py", "draw_error_rate_tail.py",
                "make_adjudication_briefs.py", "make_adjudication_briefs_after.py", "make_reader_prompts_after.py",
                "find_reader_prompt.py", "filing_pages.py", "second_read.py", "record_second_read.py",
                "show_vset.py", "show_vset_after.py", "score_error_rate.py", "score_error_rate_after_rerun.py",
                "test_score_clarified.py", "mutate_score_error_rate.py", "measure_fallback_routes.py"],
}
PACK_DIRS = {"first-sample/packs": "packs-error-rate", "second-sample/packs": "packs-error-rate-after",
             "superseded/packs": "packs-error-rate-superseded-1"}
# the tail stratum, computed after the refit: its batch files and packs exist only for records read afresh
FILES["tail"] = ["error-rate-tail.json", "error-rate-briefs-tail.json", "error-rate-carry-over-tail.json",
                 "error-rate-fresh-stems-tail.json", "error-rate-verdicts-tail.json",
                 "error-rate-verification-set-tail.json", "error-rate-verification-tail.json",
                 "error-rate-tail-result.json"]
FILES["scripts"] += ["check_refit_population.py", "make_adjudication_briefs_tail.py", "make_reader_prompts_tail.py",
                     "score_error_rate_tail.py"]
TAIL_BATCH_GLOBS = ("error-rate-briefs-tail-batch-*.json", "reader-prompt-tail-batch-*.txt",
                    "error-rate-verdicts-tail-batch-*.json")

# fifth to seventh amendments: the census of the two mechanisms, the take-on census, the records found in passing,
# the repairs, the third sample and the propagation
FILES["census"] = ["error-rate-census.json", "cohort-manifestations.json", "error-rate-briefs-census.json",
                   "error-rate-briefs-census-batch-1.json", "error-rate-carry-over-census.json",
                   "error-rate-fresh-stems-census.json", "reader-prompt-census-batch-1.txt",
                   "error-rate-verdicts-census-batch-1.json", "error-rate-verdicts-census.json",
                   "error-rate-verification-set-census.json", "error-rate-verification-census.json",
                   "error-rate-census-result.json"]
FILES["takeon-census"] = ["error-rate-census-takeon.json", "error-rate-briefs-takeon.json",
                          "error-rate-briefs-takeon-batch-1.json", "error-rate-briefs-takeon-batch-2.json",
                          "error-rate-fresh-stems-takeon.json", "reader-prompt-takeon-batch-1.txt",
                          "reader-prompt-takeon-batch-2.txt", "error-rate-verdicts-takeon-batch-1.json",
                          "error-rate-verdicts-takeon-batch-2.json", "error-rate-verdicts-takeon.json",
                          "error-rate-verification-takeon.json", "error-rate-takeon-result.json",
                          "takeon-register-draft.json"]
FILES["found-in-passing"] = ["error-rate-census-passing.json", "error-rate-briefs-passing.json",
                             "error-rate-briefs-passing-batch-1.json", "error-rate-fresh-stems-passing.json",
                             "reader-prompt-passing-batch-1.txt", "error-rate-verdicts-passing-batch-1.json",
                             "error-rate-verdicts-passing.json", "error-rate-verification-passing.json",
                             "error-rate-passing-result.json"]
FILES["repairs"] = ["error-rate-confirmed-errors.json", "persisting-first-sample-errors.json",
                    "register-additions.json", "mechanism-variants-scan.json", "replay-r213-stems.json",
                    "replay-r213-before.json", "replay-r213-full.log", "replay-r213b-stems.json", "replay-r213b.log"]
FILES["third-sample"] = ["error-rate-population-698.json", "error-rate-sample-third.json",
                         "error-rate-briefs-third.json", "error-rate-carry-over-third.json",
                         "error-rate-fresh-stems-third.json", "packs-third.log", "error-rate-verdicts-third.json",
                         "error-rate-verification-set-third.json", "error-rate-verification-third.json",
                         "error-rate-result-third.json"]
FILES["propagation"] = ["error-rate-propagation.json", "error-rate-propagation-SMOKE-refit1-placeholder-rate.json",
                        "propagation-smoke.log"]
FILES["scripts"] += ["census_error_mechanisms.py", "inspect_census_sources.py", "scan_cohort_manifestations.py",
                     "make_adjudication_briefs_census.py", "make_reader_prompts_census.py", "score_error_rate_census.py",
                     "make_adjudication_briefs_takeon.py", "make_reader_prompts_takeon.py", "score_error_rate_takeon.py",
                     "make_adjudication_briefs_passing.py", "make_reader_prompts_passing.py",
                     "score_error_rate_passing.py", "persisting_first_sample_errors.py", "build_confirmed_errors.py",
                     "scan_mechanism_variants.py", "check_m1_applied.py", "scan_m3_tags.py", "render_page.py",
                     "replay_r213_isolation.py", "replay_r213_parallel.py", "update_offline_unservable.py",
                     "validate_replayed_records.py", "diff_replayed_vs_head.py", "sync_records_to_analysis.py",
                     "save_population_698.py", "predict_refit2_population.py", "guard_then_draw_third.py",
                     "draw_error_rate_third.py", "make_adjudication_briefs_third.py", "make_reader_prompts_third.py",
                     "fix_reader_prompts_third_confirmed.py", "fix_figure_source_confirmed.py",
                     "supersede_third_briefs.py", "score_error_rate_third.py", "error_rate_propagation.py",
                     "amend_protocol_fifth.py", "amend_protocol_fifth_correction.py",
                     "amend_protocol_fifth_correction2.py", "amend_protocol_sixth.py", "amend_protocol_seventh.py",
                     "amend_protocol_seventh_addendum.py", "fix_amendment_times.py", "note_protocol_loader_figure.py"]
# single files staged under another name
EXTRA = [("renders/syndicate_623_2014_p45.png", "found-in-passing/syndicate_623_2014_p45.png"),
         ("renders/syndicate_1991_2020_p38.png", "tail/syndicate_1991_2020_p38.png")]
FILES["scripts"] += ["record_tail_readings.py", "patch_stage_tail_readings.py"]
FILES["scripts"] += sorted(p.name for p in SCR.glob("readings_tail_part*.py"))
PACK_DIRS.update({"census/packs": "packs-error-rate-census", "takeon-census/packs": "packs-error-rate-takeon",
                  "found-in-passing/packs": "packs-error-rate-passing", "third-sample/packs": "packs-error-rate-third"})
THIRD_BATCH_GLOBS = ("error-rate-briefs-third-batch-*.json", "reader-prompt-third-batch-*.txt",
                     "error-rate-verdicts-third-batch-*.json")
# the eighth amendment: the third sample's findings, the census of its mechanisms, the repairs and refit 3
FILES["third-sample/findings"] = ["summarise-third-findings.txt", "scan-incremental-triangles.txt",
                                  "scan-loss-ratio-figures.txt", "scan-transposed-note-lines.txt",
                                  "check-third-confirmed-figures.txt", "tally-opening-reserves.txt"]
FILES["eighth-census"] = ["error-rate-census-eighth.json", "census-eighth-dryrun.log", "census-eighth-dryrun2.log",
                          "census-eighth-dryrun3.log", "census-eighth.log", "probe-census-rules.txt",
                          "error-rate-briefs-eighth.json", "error-rate-carry-over-eighth.json",
                          "error-rate-fresh-stems-eighth.json", "packs-eighth.log", "error-rate-verdicts-eighth.json",
                          "error-rate-verification-eighth.json", "error-rate-census-eighth-result.json",
                          "eighth-repairs-draft.json"]
# the loader's prediction after A4a was not kept under its own name; the predictions after A4b, A4c and A4d are staged
FILES["checks"] += ["predict-refit3-known-repairs.txt"]
FILES["scripts"] += ["summarise_third_findings.py", "check_third_confirmed_figures.py", "scan_incremental_triangles.py",
                     "scan_loss_ratio_figures.py", "scan_transposed_note_lines.py", "tally_opening_reserves.py",
                     "readings_of.py", "third_verification_status.py", "probe_census_rules.py", "make_census_eighth.py",
                     "fix_census_eighth_rules.py", "fix_census_eighth_rules2.py", "make_reader_prompts_eighth.py",
                     "patch_second_read_eighth.py", "score_error_rate_eighth.py", "register_third_repairs.py",
                     "patch_run_analysis_openings.py", "mutate_openings_and_bases.py", "snapshot_refit2_outputs.py",
                     "predict_refit3_population.py", "amend_protocol_eighth.py", "patch_tail_after_eighth.py",
                     "fix_third_log_blocks.py", "fix_third_log_blocks_recursion.py"]
PACK_DIRS["eighth-census/packs"] = "packs-error-rate-eighth"
EIGHTH_BATCH_GLOBS = ("error-rate-briefs-eighth-batch-*.json", "reader-prompt-eighth-batch-*.txt",
                      "error-rate-verdicts-eighth-batch-*.json")
# batch 12 of the eighth census stopped on the spend limit after one record; batch 12b read the other two
EIGHTH_RERUN = ("error-rate-briefs-eighth-batch-12b.json", "reader-prompt-eighth-batch-12b.txt",
                "error-rate-verdicts-eighth-batch-12b.json")
# the ninth amendment: the eighth census's repairs, the take-on base, its census and refit 3
FILES["ninth-census"] = ["error-rate-census-ninth.json", "census-ninth-dryrun.log", "census-ninth-dryrun2.log",
                         "census-ninth-dryrun3.log", "census-ninth.log", "probe-census-ninth-rows.txt",
                         "error-rate-briefs-ninth.json", "error-rate-carry-over-ninth-skeleton.json",
                         "error-rate-carry-over-ninth.json", "error-rate-fresh-stems-ninth.json", "packs-ninth.log",
                         "error-rate-verdicts-ninth.json", "error-rate-verification-ninth.json",
                         "error-rate-census-ninth-result.json", "ninth-repairs-draft.json",
                         "error-rate-briefs-ninth-sixth-2003.json", "reader-prompt-ninth-sixth-2003.txt",
                         "error-rate-verdicts-ninth-sixth-2003.json"]
FILES["checks"] += ["predict-refit3-a4b.txt", "mutate-takeon-base.txt"]
# refit 3: the loader's predictions after A4c and A4d, and the population check (its dry run on refit 2 must fail)
FILES["checks"] += ["predict-refit3-a4c.txt", "predict-refit3-a4d.txt", "check-refit3-dryrun-on-refit2.txt",
                    "check-refit3.txt"]
FILES["propagation"] += ["error-rate-read-stems.json"]
FILES["scripts"] += ["check_refit3_population.py", "build_read_stems.py", "run_propagation.py",
                     "first_draw_errors_now.py", "basis_net_in_a.py", "inspect_results.py",
                     "patch_stage_refit3_inputs.py"]
FILES["scripts"] += ["make_batch_12b.py", "record_eighth_readings.py", "register_eighth_repairs.py",
                     "patch_run_analysis_takeon_base.py", "mutate_takeon_base.py", "make_census_ninth.py",
                     "probe_census_ninth_rows.py", "carry_view_ninth.py", "carry_decisions_ninth.py",
                     "record_carry_ninth.py", "make_reader_prompts_ninth.py", "patch_second_read_ninth.py",
                     "score_error_rate_ninth.py", "register_ninth_takeon_base.py", "record_ninth_state.py",
                     "patch_stage_ninth.py", "list_ninth_outcomes.py", "view_ninth_remaining.py",
                     "view_json_stem.py", "make_brief_2003_sixth.py", "register_2003_takeon.py",
                     "patch_stage_note4.py"]
FILES["scripts"] += sorted(p.name for p in SCR.glob("readings_eighth_part*.py"))
FILES["scripts"] += sorted(p.name for p in SCR.glob("readings_ninth_part*.py"))
PACK_DIRS["ninth-census/packs"] = "packs-error-rate-ninth"
# the scripts that write this directory's README and manifest, copy it into the analysis repository and check
# the committed blobs (R213, A5)
FILES["scripts"] += ["stage_extraction_error_rate.py", "patch_stage_readme_wording.py",
                     "patch_stage_gitattributes.py", "copy_stage_to_analysis.py", "verify_a5_blobs.py"]
NINTH_BATCH_GLOBS = ("error-rate-briefs-ninth-batch-*.json", "reader-prompt-ninth-batch-*.txt",
                     "error-rate-verdicts-ninth-batch-*.json")


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def load(name):
    return json.load(io.open(str(SCR / name), encoding="utf-8"))


def committed_json(repo, path):
    out = subprocess.run(["git", "-C", str(repo), "show", "HEAD:" + path], capture_output=True, check=True).stdout
    head = subprocess.run(["git", "-C", str(repo), "rev-parse", "--short", "HEAD"], capture_output=True, text=True,
                          check=True).stdout.strip()
    return json.loads(out.decode("utf-8")), head


missing = [name for names in FILES.values() for name in names if not (SCR / name).is_file()]
missing += [src for src, _dst in EXTRA if not (SCR / src).is_file()]
missing += [src for src in PACK_DIRS.values() if not (SCR / src).is_dir()]
set_aside = sorted(SCR.glob("superseded-before-reading-*"))
if len(set_aside) != 1:
    missing.append("exactly one superseded-before-reading-* folder (found %d)" % len(set_aside))
if missing:
    raise SystemExit("missing, not staging: %s" % missing)
PACK_DIRS["third-sample/superseded-before-reading"] = set_aside[0].name


def batches_match(fresh_file, globs, label, size=10, extra=()):
    n_fresh = len(load(fresh_file))
    n_batches = (n_fresh + size - 1) // size
    absent = [name for name in extra if not (SCR / name).is_file()]
    if absent:
        raise SystemExit("%s: the extra batch files it allows are missing: %s" % (label, absent))
    for pattern in globs:
        found = len([p for p in SCR.glob(pattern) if p.name not in extra])
        if found != n_batches:
            raise SystemExit("%s: %s holds %d file(s), but %d record(s) read afresh make %d batch(es)"
                             % (label, pattern, found, n_fresh, n_batches))
    return n_fresh, n_batches


n_tail_fresh, tail_batches = batches_match("error-rate-fresh-stems-tail.json", TAIL_BATCH_GLOBS, "tail")
n_third_fresh, third_batches = batches_match("error-rate-fresh-stems-third.json", THIRD_BATCH_GLOBS, "third sample")
n_eighth_fresh, eighth_batches = batches_match("error-rate-fresh-stems-eighth.json", EIGHTH_BATCH_GLOBS,
                                              "eighth census", size=5, extra=EIGHTH_RERUN)
n_ninth_fresh, ninth_batches = batches_match("error-rate-fresh-stems-ninth.json", NINTH_BATCH_GLOBS,
                                            "ninth census", size=5)
if n_tail_fresh:
    PACK_DIRS["tail/packs"] = "packs-error-rate-tail"
    if not (SCR / "packs-error-rate-tail").is_dir():
        raise SystemExit("missing, not staging: packs-error-rate-tail")
prop = load("error-rate-propagation.json")
if prop.get("analysis_tree_dirty") is not False:
    raise SystemExit("the propagation was computed on an analysis tree with uncommitted model, results or src "
                     "changes (analysis_tree_dirty=%r): rerun it on the committed refit" % prop.get("analysis_tree_dirty"))
if OUT.exists():
    shutil.rmtree(str(OUT))
manifest = []


def stage_file(src, dst_rel):
    dst = OUT / dst_rel
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(str(src), str(dst))
    manifest.append({"path": dst_rel, "source": str(Path(src).relative_to(SCR)).replace("\\", "/"),
                     "bytes": dst.stat().st_size, "sha256": sha(dst)})


for folder, names in FILES.items():
    for name in names:
        stage_file(SCR / name, "%s/%s" % (folder, name))
for src, dst_rel in EXTRA:
    stage_file(SCR / src, dst_rel)
for folder, globs in (("tail", TAIL_BATCH_GLOBS), ("third-sample", THIRD_BATCH_GLOBS),
                      ("eighth-census", EIGHTH_BATCH_GLOBS), ("ninth-census", NINTH_BATCH_GLOBS)):
    for pattern in globs:
        for p in sorted(SCR.glob(pattern)):
            stage_file(p, "%s/%s" % (folder, p.name))
for folder, src in PACK_DIRS.items():
    shutil.copytree(str(SCR / src), str(OUT / folder))
    for p in sorted(q for q in (OUT / folder).rglob("*") if q.is_file()):
        rel = str(p.relative_to(OUT / folder)).replace("\\", "/")
        manifest.append({"path": "%s/%s" % (folder, rel), "source": "%s/%s" % (src, rel),
                         "bytes": p.stat().st_size, "sha256": sha(p)})

before = load("error-rate-result.json")
after = load("error-rate-result-after-rerun.json")
first_sample = load("error-rate-sample.json")
second_sample = load("error-rate-sample-after.json")
superseded = load("error-rate-sample-superseded-1.json")
first_sizes = [len(load("error-rate-briefs-batch-%d.json" % i)) for i in FIRST_BATCHES]
after_sizes = [len(load("error-rate-briefs-after-batch-%d.json" % i)) for i in AFTER_BATCHES]
if sum(first_sizes) != before["sample_n"] or sum(after_sizes) != after["read_afresh"]:
    raise SystemExit("batch sizes do not add up: %s %s" % (first_sizes, after_sizes))
if first_sample["population"]["n"] != before["population_n"] or second_sample["population"]["n"] != after["population_n"]:
    raise SystemExit("a result's population is not its sample's")
r208_before = load("r208-exposure-results-before.json").get("analysis_run_id")
r209_before = load("r209-exposure-results-before.json").get("analysis_run_id")
protocol_text = io.open(str(SCR / "error-rate-protocol.md"), encoding="utf-8").read()
amendment_heads = re.findall(r"^## ((?:[A-Z][a-z]+ )?[Aa]mendment, .*)$", protocol_text, re.M)
note_heads = re.findall(r"^## (Implementation note.*)$", protocol_text, re.M)
clarification_heads = re.findall(r"^## (.*[Cc]larification.*)$", protocol_text, re.M)


def row(result, label):
    cells = []
    for rule in ("clarified", "first_readers_instruction"):
        r = result["rules"][rule]
        lo, hi = r["posterior"]["ci95_equal_tailed"]
        cells.append("%d / %d / %d | %.3f [%.3f, %.3f]" % (r["errors"], r["correct"], r["undeterminable"],
                                                           r["posterior"]["mean"], lo, hi))
    return "| %s | %d of %d | %s | %s |" % (label, result["sample_n"], result["population_n"], cells[0], cells[1])


tail = load("error-rate-tail-result.json")


def tail_row(result):
    cells = []
    for rule in ("clarified", "first_readers_instruction"):
        r = result["rules"][rule]
        lo, hi = r["posterior"]["ci95_equal_tailed"]
        cells.append("%d / %d / %d | %.3f [%.3f, %.3f]" % (r["errors"], r["correct"], r["undeterminable"],
                                                           r["posterior"]["mean"], lo, hi))
    return "| Tail stratum (after refit 3) | the %d largest transferred severities | %s | %s |" % (
        result["tail_n"], cells[0], cells[1])


def sizes(xs):
    if len(set(xs)) == 1:
        return "%s batches of %d" % (WORDS[len(xs)], xs[0])
    return "batches of " + ", ".join(str(x) for x in xs[:-1]) + " and " + str(xs[-1])


WORDS = {1: "one", 2: "two", 3: "three", 4: "four", 5: "five", 6: "six", 7: "seven", 8: "eight", 9: "nine",
         10: "ten", 11: "eleven", 12: "twelve"}

readme = """# Extraction error rate

The probability that a record drawn at random from the working sample carries a materially wrong adopted
prior-year development figure, judged against the syndicate's own filing (PLAN R163). The protocol,
`protocol/error-rate-protocol.md`, was fixed on 11 September 2026, before any sample was drawn. Its %d
amendments, its clarification and its %d implementation notes are dated, and each says what prompted it.

## Results

Errors / correct / undeterminable, and the mean and 95%% equal-tailed credible interval of the Beta(1/2, 1/2)
posterior over the adjudicable records. The clarified rule is the protocol's. The first readers' instruction
is reported beside it, without second-reading corrections, which were made under the clarified rule.

| Extraction | Drawn | Clarified rule | Mean [95%% CrI] | First readers' instruction | Mean [95%% CrI] |
|---|---|---|---|---|---|
%s
%s
%s

The first sample was drawn from a working sample of %d. R208 then removed one record that was not drawn
(1947/2019), and the third amendment explains why the drawn records remain a simple random sample of the 706
that stayed. The second row is the extraction after PLAN R209 and R210. They changed the working sample after
the first result was scored, and a record entered it, so the study was re-run from step 1 with a new draw
(fourth amendment). %d records held by both samples kept their readings, because nothing their verdicts were
read against had changed, and %d were read afresh. Second readings: %d on the first sample, %d on the second.

The third row is the tail stratum: the %d largest Vignette-1 transferred severities, computed after the refit
(analysis run %s). It is purposive, so it is reported apart and never pooled with either random sample. %d
of its records kept readings from a primary sample, and %d were read afresh.
""" % (len(amendment_heads), len(note_heads), row(before, "Before R209 and R210"), row(after, "After R209 and R210"),
       tail_row(tail), before["population_n"], after["carried_over"], after["read_afresh"],
       before["second_readings"], after["second_readings"], tail["tail_n"], tail["exposure_results_run_id"],
       tail["carried_over"], tail["read_afresh"])

# --- the fifth to seventh amendments ---------------------------------------------------------------------------
census = load("error-rate-census-result.json")
takeon = load("error-rate-takeon-result.json")
passing = load("error-rate-passing-result.json")
confirmed = load("error-rate-confirmed-errors.json")
third = load("error-rate-sample-third.json")
res3 = load("error-rate-result-third.json")
carry3 = load("error-rate-carry-over-third.json")["decisions"]
ext_register, ext_head = committed_json(EXT, "pdf_extraction/audit/triangle_figures_confirmed_by_hand.json")
confirmed_register, an_head = committed_json(AN, "data/pyd_confirmed_figures.json")
takeon_register, _ = committed_json(AN, "data/takeon_not_development.json")


def key(stem):
    return stem.replace("syndicate_", "").replace("_", "/")


def stems_of(xs):
    return [x if isinstance(x, str) else x["stem"] for x in xs]


def m(v):
    return ("%+.3f" % float(v)).rstrip("0").rstrip(".") + "m"


def pct(v):
    return "%.1f%%" % (100.0 * float(v))


def listing(stems):
    names = [key(s) for s in stems]
    return ", ".join(names) if names else "none"


mech = census["by_mechanism"]
mech_lines = "\n".join("- %s: %d record(s); error %s; correct %s; undeterminable %s." % (
    name.replace("_", " "), sum(len(v[k]) for k in ("error", "correct", "undeterminable")),
    listing(v["error"]), listing(v["correct"]), listing(v["undeterminable"])) for name, v in mech.items())
leaving = stems_of(takeon["leaving"])
takeon_other_errors = [r["stem"] for r in takeon["records"]
                       if r.get("second_verdict") == "error" and not r.get("leaves_the_working_sample")]
passing_rows = passing["records"]
passing_split = [r["stem"] for r in passing_rows if r["first_verdict"] != r["second_verdict"]]
passing_undet = [r["stem"] for r in passing_rows
                 if r["first_verdict"] == r["second_verdict"] == "undeterminable"]
confirmed_lines = "\n".join("| %s | %s | %s | %s | %s |" % (key(c["stem"]), c["from"], m(c["adopted_m"]), m(c["filing_m"]),
                                                           m(c["opening_m"])) for c in confirmed)
ext_repaired = [r["stem"] for r in ext_register["records"]]
an_repaired = sorted(k for k, v in confirmed_register.items() if not k.startswith("_") and v.get("figure_m") is not None)
an_takeons = sorted(k for k in takeon_register if not k.startswith("_"))
carried3 = [d for d in carry3 if d["carry_over"]]
third_sizes = [len(load("error-rate-briefs-third-batch-%d.json" % i)) for i in range(1, third_batches + 1)]
if sum(third_sizes) != n_third_fresh:
    raise SystemExit("third-sample batch sizes %s do not add up to %d" % (third_sizes, n_third_fresh))
A, W, T, T1 = res3["A_sampled"], res3["working_sample"], res3["third_sample_alone"], res3["third_sample_first_readers_instruction"]


def rate_row(label, records, block):
    lo, hi = block["posterior"]["ci95_equal_tailed"]
    return "| %s | %s | %d / %d / %d | %.3f [%.3f, %.3f] |" % (label, records, block["errors"], block["correct"],
                                                             block["undeterminable"], block["posterior"]["mean"], lo, hi)


prop_rows = []
for model in ("sign", "replace", "shift"):
    a, b = prop["p_from_posterior"][model], prop["p_at_posterior_97_5"][model]
    prop_rows.append("| %s | %s [%s, %s] | %.3f | %s [%s, %s] | %.3f |" % (
        model, pct(a["relative_change"]["median"]), pct(a["relative_change"]["p2_5"]), pct(a["relative_change"]["p97_5"]),
        a["P_abs_relative_change_gt_5pct"], pct(b["relative_change"]["median"]), pct(b["relative_change"]["p2_5"]),
        pct(b["relative_change"]["p97_5"]), b["P_abs_relative_change_gt_5pct"]))
head = prop["headline"]

# --- the eighth amendment ------------------------------------------------------------------------------------------
census8 = load("error-rate-census-eighth-result.json")
census8_file = load("error-rate-census-eighth.json")
opening_register, _ = committed_json(AN, "data/opening_reserves_confirmed.json")
eighth_sizes = [len(load("error-rate-briefs-eighth-batch-%d.json" % i)) for i in range(1, eighth_batches + 1)]
if sum(eighth_sizes) != n_eighth_fresh:
    raise SystemExit("eighth-census batch sizes %s do not add up to %d" % (eighth_sizes, n_eighth_fresh))
# --- the ninth amendment ------------------------------------------------------------------------------------------
census9 = load("error-rate-census-ninth-result.json")
census9_file = load("error-rate-census-ninth.json")
carried9 = sum(1 for d in load("error-rate-carry-over-ninth.json")["decisions"] if d["carry"])
base_register, _ = committed_json(AN, "data/opening_reserves_takeon_base.json")
ninth_sizes = [len(load("error-rate-briefs-ninth-batch-%d.json" % i)) for i in range(1, ninth_batches + 1)]
if sum(ninth_sizes) != n_ninth_fresh:
    raise SystemExit("ninth-census batch sizes %s do not add up to %d" % (ninth_sizes, n_ninth_fresh))
adjusted9 = [r for r in census9["table"] if r["outcome"] == "adjusted"]
if sorted(r["stem"].replace("syndicate_", "") for r in adjusted9) != sorted(k for k in base_register if not k.startswith("_")):
    raise SystemExit("the committed take-on base register does not hold the census's adjusted records")
base_lines = "\n".join("| %s | %s | %s | %.2f%% | %.2f%% |" % (
    key(r["stem"]), m(r["opening_m"]).lstrip("+"), m(base_register[r["stem"].replace("syndicate_", "")]["takeon_m"]).lstrip("+"),
    r["severity_pct"], r["severity_pct_adjusted"]) for r in adjusted9)
no_transfer9 = [r["stem"] for r in census9["table"] if r["outcome"] != "adjusted" and r["first"]["finding"] is False]
small9 = [r["stem"] for r in census9["table"] if r["outcome"] != "adjusted" and r["first"]["finding"] is not False
          and "under 5%" in r["reason"]]
# Both readings of 1110/2022 and 609/2014 find a covered transfer and no amount stated in the filing; the
# first reading of 1084/2014 does not decide coverage. A reason with no plain wording stops the staging.
PLAIN9 = {"a reading gives no transferred amount": "the filing states no amount for the covered transfer",
          "the readings do not both find a covered transfer": "the two readings do not both find a covered transfer"}


def plain9(reason):
    bare = re.sub(r" \((?:None|True|False|[-+0-9.e]+), (?:None|True|False|[-+0-9.e]+)\)$", "", reason)
    if bare not in PLAIN9:
        raise SystemExit("no plain wording for the ninth census reason %r" % reason)
    return PLAIN9[bare]


other9 = ["%s (%s)" % (key(r["stem"]), plain9(r["reason"])) for r in census9["table"] if r["outcome"] != "adjusted"
          and r["stem"] not in no_transfer9 and r["stem"] not in small9]
rules9 = ", ".join("%s %d" % (rule, len(v)) for rule, v in census9_file["parts"].items())
dry9 = []
for name in ("census-ninth-dryrun.log", "census-ninth-dryrun2.log", "census-ninth-dryrun3.log"):
    mm = re.search(r"^listed (\d+):", io.open(str(SCR / name), encoding="utf-8").read(), re.M)
    if not mm:
        raise SystemExit("%s: no 'listed N:' line" % name)
    dry9.append(mm.group(1))
# implementation note 4: 2003/2018 read once more on the sixth amendment's question, then excluded by the owner
note4 = load("error-rate-verdicts-ninth-sixth-2003.json")
note4_answer = ((note4[0].get("census_check") or {}).get("takeon_triangle") or {}) if len(note4) == 1 else {}
if len(note4) != 1 or note4[0].get("stem") != "syndicate_2003_2018" or note4_answer.get("finding") is not True:
    raise SystemExit("implementation note 4's reading is not the take-on finding the README describes")
if "2003_2018" not in an_takeons or "syndicate_2003_2018" not in no_transfer9:
    raise SystemExit("2003/2018 is not where the README puts it (the committed take-on register, no covered transfer)")
third_errors = sorted(s for s, v in res3["final_verdicts"]["A"].items() if v == "error" and s in third["third"]["stems"])
openings_outside, base_openings = [], []
for p in sorted(SCR.glob("error-rate-verdicts*.json")):
    if "-batch-" in p.name:
        continue
    for r in load(p.name):
        o = r.get("opening_reserves") if isinstance(r, dict) else None
        if isinstance(o, dict) and o.get("within_2pct") is False and r["stem"].replace("syndicate_", "") in base_register:
            base_openings.append("%s (brief %s, the filing's 1 January %s, p%s; %s)" % (key(r["stem"]), o.get("adopted_m"),
                                                                              o.get("filing_m"), o.get("page"), p.name))
        elif isinstance(o, dict) and o.get("within_2pct") is False:
            openings_outside.append("%s (adopted %s, filing %s, p%s; %s)" % (key(r["stem"]), o.get("adopted_m"),
                                                                        o.get("filing_m"), o.get("page"), p.name))
basis_entries = sorted("%s (%s)" % (key("syndicate_" + k), v["basis"]) for k, v in confirmed_register.items()
                       if not k.startswith("_") and v.get("basis") in ("net", "unknown"))
opening_entries = sorted("%s (%s)" % (key("syndicate_" + k), m(v["opening_reserves_m"]).lstrip("+"))
                         for k, v in opening_register.items() if not k.startswith("_"))
part_lines = "\n".join("| %s | %d | %d | %d | %s | %d | %s |" % (
    part, p["flagged"], len(p["decided"]), p["read"], listing(p["found_by_both"]), p["absent_by_both"],
    listing(p["unsettled"])) for part, p in census8["parts"].items())
openings_text = "; ".join(openings_outside) or "none"

readme += f"""
## After the second sample: the error mechanisms, the repairs, a third sample and the effect on the VaR

The second sample's two errors are mechanisms, not one-off misreadings. The fifth amendment counted and repaired
them, drew a larger random sample from the repaired working sample, and measured the errors' effect on Vignette
1's VaR99.5. The sixth and seventh amendments added the take-on census, the records found in passing and the
repair by a confirmed figure. Each census and each list of records found in passing is purposive, so it is
reported on its own and never pooled with a random sample.

### The census of the two mechanisms (`census/`)

{census["census_n"]} records, each read twice ({census["second_readings"]} second readings, {len(census["second_reading_overturned"])} overturned a first reading):

{mech_lines}

### The take-on census (`takeon-census/`)

{takeon["census_n"]} working-sample records in the RITC regime take a movement the filing states as their figure. Each
was read twice for whether that figure is the take-on itself, the reserves a transfer brought in. Take-ons, which
leave the working sample: {listing(leaving)}. Other errors the same readings confirmed: {listing(takeon_other_errors)}.

### Records found in passing (`found-in-passing/`)

{len(passing_rows)} records the mapping of the extraction code named, each read twice. Confirmed errors:
{listing(passing["confirmed_errors"])}. Readings that split: {listing(passing_split)}. Undeterminable in both readings:
{listing(passing_undet)}. A record whose readings do not agree on an error and its filing figure is left as it is
(seventh amendment, point 2). `syndicate_623_2014_p45.png` is the rendered page the second reading of 623/2014 used.

### The repairs (`repairs/`)

The errors two readings confirmed before repair, in the report's currency (`error-rate-confirmed-errors.json`):

| Record | Found by | Adopted | Filing | Opening reserves |
|---|---|---|---|---|
{confirmed_lines}

- Repaired in the extraction (extraction repository {ext_head},
  `pdf_extraction/audit/triangle_figures_confirmed_by_hand.json`): the pipeline's deterministic triangle gives the
  confirmed figure, which its sign check had refused, and the register lets that figure stand for these records
  only: {listing(ext_repaired)}.
- Repaired by the analysis loader (analysis repository {an_head}, `data/pyd_confirmed_figures.json`): no extraction
  route produces the confirmed figure, so the loader adopts it and discloses the correction in the record:
  {", ".join(k.replace("_", "/") for k in an_repaired)}.
- Excluded as take-ons (`data/takeon_not_development.json`): {", ".join(k.replace("_", "/") for k in an_takeons)}.

`mechanism-variants-scan.json` records the scan of every committed extraction record for the mechanisms these
records showed. `replay-r213-full.log` is the full offline replay of {len(load("replay-r213-stems.json"))} data-carrying records
under the repaired pipeline, and `replay-r213b.log` the replay of the two records then added to the extraction's
register.

### The third sample (`third-sample/`)

Drawn on {third["drawn"]} from analysis run {third["exposure_results_run_id"]}, before any of its records was read. The rebuilt
working sample holds {third["rebuilt_working_sample_n"]} records; A, the records the second sample's population also holds,
{third["A"]["n"]}; entrants {len(third["E_entrants"]["stems"])}; left: {listing(third["left"]["stems"])}. {third["third"]["n"]} records were drawn from the
{third["frame"]["n"]} records of A that the second sample had not drawn (seed {third["seed"]}). {len(carried3)} kept readings from an
earlier sample or census, because nothing their verdicts were read against had changed; {n_third_fresh} were read afresh,
in {sizes(third_sizes)}. A second-sample record whose adopted figure a repair changed was read again:
{listing([r["stem"] for r in res3["repaired_records"]])}. Second readings: {res3["second_readings"]}. The first briefs, set aside
before any reading, are in `superseded-before-reading/` (implementation note 2).

| Rate after the repairs | Records | Errors / correct / undeterminable | Mean [95% CrI] |
|---|---|---|---|
{rate_row("A's sampled records: the second sample still in A and the third sample", A["n_records"], A)}
{rate_row("The third sample alone, clarified rule", T["errors"] + T["correct"] + T["undeterminable"], T)}
{rate_row("The third sample alone, first readers' instruction", T1["errors"] + T1["correct"] + T1["undeterminable"], T1)}

The working sample's rate, A's posterior weighted by its adjudicable share with the entrants' errors counted in
full ({W["mc_draws"]} draws, seed {W["mc_seed"]}): mean {W["mean"]:.3f}, 95% CrI [{W["ci95_equal_tailed"][0]:.3f}, {W["ci95_equal_tailed"][1]:.3f}].

### What the third sample found, and the eighth amendment (`third-sample/findings/`, `eighth-census/`)

The third sample's errors are mechanisms the earlier repairs did not reach: {listing(third_errors)}. The opening
reserves, which the protocol checks against a 2% tolerance and reports apart from the rate, fell outside it in
{len(openings_outside)} first reading(s): {openings_text}.

On 14 September 2026 the owner decided to repair them, count their mechanisms in a census and refit again
(eighth amendment). The rate above is the one the third sample measured, before those repairs. The repairs, all
by registers the analysis loader reads (analysis repository {an_head}):

- figures: every entry of `data/pyd_confirmed_figures.json` with a figure is listed under the repairs above;
- a basis the readings established, the record excluded like any net or unknown-basis record: {", ".join(basis_entries)};
- opening reserves (`data/opening_reserves_confirmed.json`): {", ".join(opening_entries)};
- take-ons (`data/takeon_not_development.json`): listed under the repairs above.

The census (`eighth-census/`) was computed and written on {census8_file["written"]}, before any of its records was
read, from six rules the amendment states; a record may sit in more than one part. {census8["census_n"]} records were
read or kept earlier readings, and {census8["decided_n"]} already decided were not read. {n_eighth_fresh} were read afresh,
in {sizes(eighth_sizes)}; batch 12's reader stopped on its spend limit after one record, and batch 12b read the other
two. The dry runs that tightened three rules before any reading are kept beside it.

| Part | Flagged | Decided | Read | Found by both readings | Absent by both | Unsettled |
|---|---|---|---|---|---|---|
{part_lines}

Errors both readings confirmed: {listing(census8["confirmed_errors"])}.

### The eighth census's repairs and the take-on base (`ninth-census/`)

The eighth census's confirmed errors are repaired through the same registers (ninth amendment, point 1), with the
owner deciding 2010/2015's figure. The census also found a take-on base: a triangle restated to carry business
taken on in the report year covers it on both diagonals of its step, while the opening reserves at 1 January
exclude it, so the severity is overstated. On 14 September 2026 the owner decided to adjust the opening reserves.

The take-on base census was computed and written on {census9_file["written"]}, before any of its records was read,
from three rules over the {census9_file["working_sample_n"]} records of the working sample the loader predicted for
refit 3 ({rules9}; a record may meet several). On dry runs that read no filing for a verdict, the row rule was
tightened twice: {dry9[0]} records listed, then {dry9[1]}, then {dry9[2]}.
{len(census9_file["stems"])} records were listed: {carried9} kept both eighth-census readings, and {n_ninth_fresh} were read
afresh, in {sizes(ninth_sizes)}. Adjusted (`data/opening_reserves_takeon_base.json`, analysis repository {an_head}):

| Record | Opening reserves | Taken on and covered | Severity before | Severity after |
|---|---|---|---|---|
{base_lines}

Not adjusted: {len(no_transfer9)} records with no transfer the adopted figure covers; {len(small9)} whose covered
transfer is under 5% of the opening reserves; and {listing(other9)}. Later first readings of an adjusted record find its
opening reserves outside the 2% check, as they must: {"; ".join(base_openings) or "none"}.

2003/2018 is one of the records with no covered transfer: both readings find Syndicate 1209's reinsurance to close
entering its triangle's step without restatement, which point 2 leaves to the sixth amendment. Under
implementation note 4 it was read once more, on that amendment's question (`error-rate-briefs-ninth-sixth-2003.json`,
`reader-prompt-ninth-sixth-2003.txt`, `error-rate-verdicts-ninth-sixth-2003.json`). That reading and the editor's
both find the take-on dominating the figure, and on the owner's decision of 14 September 2026 the record is
excluded as a take-on (`data/takeon_not_development.json`, analysis repository {an_head}).

### The effect on Vignette 1's VaR99.5 (`propagation/`)

Computed on analysis commit {prop["analysis_commit"]}. The repairs moved VaR99.5 from {head["V1_VaR995_before_repairs"]:.4f} to
{head["V1_VaR995_after_repairs"]:.4f} ({pct(head["relative_change_from_repairs"])}). For errors not yet found, {prop["replicates"]} replicates (seed
{prop["seed"]}) drew an error rate from the posterior Beta({prop["rate_posterior"]["alpha"]}, {prop["rate_posterior"]["beta"]}), a count among the
{prop["unread_working_sample_records"]} working-sample records no sample or census read, and changed each chosen record's severity under
three error models. The materiality line is a relative change of {pct(prop["materiality_line_relative"])}.

| Error model | Relative change, rate from the posterior: median [2.5%, 97.5%] | P(abs > 5%) | Rate at the posterior's 97.5% point ({prop["p_at_posterior_97_5"]["p"]:.3f}): median [2.5%, 97.5%] | P(abs > 5%) |
|---|---|---|---|---|
{chr(10).join(prop_rows)}

`error-rate-propagation-SMOKE-refit1-placeholder-rate.json` is a smoke run of the same script on the refit before
the repairs, with placeholder rate inputs, made to test the script before the refit after the repairs existed. No
estimate uses it.
"""

readme += """
## Who read the filings

Every reading was made by Claude, reading the filing page by page under the protocol. This is a use of AI in
building the evidence, and the manuscript declares it as one. No reading was made by a person.

- First readers: Claude Code agents running Claude Opus 5 (`claude-opus-5`), one per batch. The first sample
  was read in %s records, the second sample's fresh records in %s, the third sample's in %s, the eighth
  census's in %s (and batch 12b of two), and the take-on base census's in %s, with one further reader for
  2003/2018 (implementation note 4).
  The censuses and the records found in passing were read the same way. Each reader was given the protocol's
  definitions, a brief of what the loader adopted, an adjudication pack and a page tool
  (`scripts/filing_pages.py`). The instruction each was given is kept as `reader-prompt-*.txt`.
- Second reader: the Claude Code session that ran the study (Claude Opus 5). It read the protocol's
  verification set: every clarified or first-reader error, every verdict the clarification changed, every
  undeterminable, every triangle-sourced figure without a recomputation, every figure whose source is not
  its route field, and a seeded random fifth of the remaining corrects. It read every record of each census and
  every record found in passing.

## Files

- `first-sample/`: the draw (`error-rate-sample.json`: analysis run %s, seed 42), the briefs, reader
  prompts and first readings per batch, the merged and clarified verdicts, the verification set, the second
  readings and the result. `packs/` holds the evidence pack each reader was given.
- `second-sample/`: the same for the draw from analysis run %s, with `error-rate-carry-over.json` (which
  readings carried over, decided before any new reading, and why) and the merge's check and log.
- `tail/`: the tail stratum's definition and stems (`error-rate-tail.json`, with the calibration's and donor
  pool's hashes), its briefs, carry-over decision, readings, verification and result, and `packs/` for the
  records read afresh.
- `census/`, `takeon-census/`, `found-in-passing/`: each list of records, its briefs, reader prompts, first
  readings, second readings and result, with `packs/`.
- `repairs/`, `third-sample/`, `propagation/`: as described above.
- `third-sample/findings/` and `eighth-census/`: as described above; `eighth-census/packs/` holds the census's
  evidence packs.
- `ninth-census/`: the take-on base census, its dry runs and probe, briefs, carry-over skeleton and decisions,
  reader prompts, first and second readings, result and draft, and implementation note 4's brief, prompt and
  reading of 2003/2018; `ninth-census/packs/` holds its evidence packs.
- `superseded/`: the draw of 13 September from a working sample of %d that a loader defect had made wrong
  (PLAN R205). It was withdrawn before any record was read (second amendment), and no estimate uses it. The
  draw script first written for the protocol is kept beside it: it was never run (amendment, point 2).
- `checks/`: `compare_working_sample.py` (R208: analysis run %s against its successor) and
  `compare_r209_r210.py` with `compare-r209-r210.txt` (R209 and R210: analysis run %s against run %s), each
  with the prediction it tests and the working sample it started from.
- `scripts/`: the scripts as they ran. Their paths name the working copies they ran in. The adjudication pack
  generator is `scripts/adjudication_pack.py` in the extraction repository.
- `MANIFEST.json`: every file with its SHA-256.
- `.gitattributes`: marks every file here `-text`, so git converts no line endings and a checkout on any platform
  holds the bytes MANIFEST.json hashes.
""" % (sizes(first_sizes), sizes(after_sizes), sizes(third_sizes), sizes(eighth_sizes), sizes(ninth_sizes),
       first_sample["population"]["exposure_results_run_id"], second_sample["population"]["exposure_results_run_id"],
       superseded["population"]["n"], r208_before, r209_before, second_sample["population"]["exposure_results_run_id"])

io.open(str(OUT / "README.md"), "w", encoding="utf-8", newline="\n").write(readme)
io.open(str(OUT / "MANIFEST.json"), "w", encoding="utf-8", newline="\n").write(
    json.dumps({"files": manifest, "count": len(manifest)}, indent=1) + "\n")
io.open(str(OUT / ".gitattributes"), "w", encoding="utf-8", newline="\n").write(
    "# kept byte for byte: MANIFEST.json hashes these files as staged, line endings included\n* -text\n")
total = sum(x["bytes"] for x in manifest)
print("staged %d files, %.1f MB, in %s" % (len(manifest), total / 1e6, OUT.name))
print("protocol: %d amendment headings, %d clarification heading(s), %d implementation note(s)"
      % (len(amendment_heads), len(clarification_heads), len(note_heads)))
for h in amendment_heads + clarification_heads + note_heads:
    print("   ", h[:110])
print("runs: first %s, after %s, R208 before %s, R209 before %s, superseded n %s; third %s; propagation on %s"
      % (first_sample["population"]["exposure_results_run_id"], second_sample["population"]["exposure_results_run_id"],
         r208_before, r209_before, superseded["population"]["n"], third["exposure_results_run_id"],
         prop["analysis_commit"]))
