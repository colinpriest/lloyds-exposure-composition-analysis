r"""Copy refit 2's outputs out of the analysis tree before refit 3 overwrites them (read-only on the repository).

Refit 2 ran on analysis 8addc04 (launched 21:42:10, exit 0 at 23:39:13 on 13 September 2026). Its outputs are the
files `git status --porcelain` lists as modified or untracked in the analysis repository; they are not committed,
because the eighth amendment's repairs and refit 3 follow. This copies each into refit2-8addc04-outputs/ at the same
relative path, the way refit1-db8eba4-outputs/ keeps refit 1's. It refuses if the destination exists, if HEAD is not
8addc04, if src/ or reproduce.py has changes (the outputs would not be refit 2's alone), or if a copy's bytes differ.

    python snapshot_refit2_outputs.py
"""
import filecmp
import shutil
import subprocess
import sys
from pathlib import Path

SCR = Path(__file__).resolve().parent
REPO = Path(r"D:/dev/IME-Lloyds-exposure-composition")
DEST = SCR / "refit2-8addc04-outputs"


def git(*args):
    return subprocess.run(["git", "-C", str(REPO)] + list(args), capture_output=True, text=True, check=True).stdout


if DEST.exists():
    raise SystemExit("%s exists; the snapshot is taken once" % DEST.name)
head = git("rev-parse", "--short", "HEAD").strip()
if head != "8addc04":
    raise SystemExit("analysis HEAD is %s, not 8addc04" % head)
if git("status", "--porcelain", "--", "src", "reproduce.py").strip():
    raise SystemExit("src/ or reproduce.py has changes: the tree's outputs would not be refit 2's alone")
paths = []
for line in git("status", "--porcelain", "--untracked-files=all").splitlines():
    status, rel = line[:2], line[3:]
    if " -> " in rel:
        rel = rel.split(" -> ", 1)[1]
    rel = rel.strip('"')
    if "D" in status:
        continue
    paths.append(rel)
for rel in paths:
    src = REPO / rel
    dst = DEST / rel
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(str(src), str(dst))
    if not filecmp.cmp(str(src), str(dst), shallow=False):
        raise SystemExit("copy differs: %s" % rel)
(DEST / "SNAPSHOT.txt").write_text(
    "Refit 2 outputs: analysis 8addc04, launched 2026-09-13 21:42:10, exit 0 at 23:39:13 (launch_refit.sh,\n"
    "refit-8addc04.log). %d files copied byte-identical from the working tree by snapshot_refit2_outputs.py.\n" % len(paths),
    encoding="utf-8")
print("refit 2 snapshot: %d files -> %s" % (len(paths), DEST.name))
sys.exit(0)
