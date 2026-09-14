r"""Bring the analysis repository's copies of the extraction records and audit files to the extraction's HEAD.

The analysis commits a copy of every extraction record it reads (pdf_extraction/syndicate_*.json) and of the audit
files beside them. This copies each file whose content differs from the extraction's committed blob, then checks
that every copy's blob id (git hash-object, with the analysis repo's filters) equals the extraction HEAD's. It
refuses when any of those extraction paths has uncommitted changes, so the copies always match a commit.

    python sync_records_to_analysis.py --dry-run
    python sync_records_to_analysis.py
"""
import re
import shutil
import subprocess
import sys
from pathlib import Path

EXT = Path(r"D:/dev/lloyds_reserve_stress_testing")
ANA = Path(r"D:/dev/IME-Lloyds-exposure-composition")
AUDIT = ["pdf_extraction/audit/" + n for n in ("run_manifest.json", "disagreement_log.json", "rejection_log.json",
                                              "portfolio_transfer_adjudication.json",
                                              "triangle_figures_confirmed_by_hand.json")]
DRY = "--dry-run" in sys.argv


def git(repo, *args, stdin=None):
    r = subprocess.run(["git", "-C", str(repo)] + list(args), input=stdin, capture_output=True, text=True)
    if r.returncode:
        raise SystemExit("git %s failed in %s: %s" % (" ".join(args), repo, r.stderr.strip()))
    return r.stdout


# a record is syndicate_<number>_<year>.json: the extraction directory also holds syndicate_inception_years.json and
# syndicate_1176_2022_azure.json, which the analysis never copied and its loader's glob would count as records
RECORD = re.compile(r"pdf_extraction/syndicate_\d+_\d{4}\.json")
head_blobs = {}
for line in git(EXT, "ls-tree", "-r", "HEAD", "--", "pdf_extraction/").splitlines():
    meta, path = line.split("\t", 1)
    if RECORD.fullmatch(path) or path in AUDIT:
        head_blobs[path] = meta.split()[2]
missing = [p for p in AUDIT if p not in head_blobs]
if missing:
    raise SystemExit("not committed in the extraction repo: %s" % missing)
dirty = [line for line in git(EXT, "status", "--porcelain", "--", "pdf_extraction/").splitlines()
         if line[3:].strip().strip('"') in head_blobs]
if dirty:
    raise SystemExit("the extraction working tree differs from HEAD for these paths; commit first:\n"
                     + "\n".join(dirty[:20]))


def analysis_blobs(paths):
    present = [p for p in paths if (ANA / p).exists()]
    out = git(ANA, "hash-object", "--stdin-paths", stdin="\n".join(present) + "\n").split()
    return dict(zip(present, out))


paths = sorted(head_blobs)
before = analysis_blobs(paths)
to_copy = [p for p in paths if before.get(p) != head_blobs[p]]
new = [p for p in to_copy if p not in before]
extra = sorted(str(q.relative_to(ANA)).replace("\\", "/") for q in (ANA / "pdf_extraction").glob("syndicate_*.json")
               if str(q.relative_to(ANA)).replace("\\", "/") not in head_blobs)
print("extraction HEAD %s: %d files (%d records, %d audit files); analysis copies differing %d (new %d)"
      % (git(EXT, "rev-parse", "--short", "HEAD").strip(), len(paths), len(paths) - len(AUDIT), len(AUDIT),
         len(to_copy), len(new)))
print("analysis records with no extraction counterpart: %d %s" % (len(extra), extra[:10]))
for p in to_copy[:12]:
    print("   ", p)
if DRY:
    sys.exit(0)
for p in to_copy:
    (ANA / p).parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(str(EXT / p), str(ANA / p))
after = analysis_blobs(paths)
bad = [p for p in paths if after.get(p) != head_blobs[p]]
if bad:
    raise SystemExit("after copying, %d blobs still differ: %s" % (len(bad), bad[:10]))
print("copied %d; every one of the %d analysis copies now has the extraction HEAD blob" % (len(to_copy), len(paths)))
