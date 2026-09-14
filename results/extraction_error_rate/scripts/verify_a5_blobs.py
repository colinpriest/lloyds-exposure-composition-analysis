"""After commit A5: every file of results/extraction_error_rate/ at a commit, read from git's blobs, against MANIFEST.json
at that commit; the tree's tracked files against the manifest's list; and git's attributes for them (text must be
unset, so no checkout converts a line ending and the blob bytes are the bytes a clone holds).

    python verify_a5_blobs.py [commit]
"""
import hashlib
import json
import subprocess
import sys

ANALYSIS = r"D:\dev\IME-Lloyds-exposure-composition"
PREFIX = "results/extraction_error_rate/"
commit = sys.argv[1] if len(sys.argv) > 1 else "HEAD"


def git(*args, data=None):
    return subprocess.run(["git", "-C", ANALYSIS] + list(args), input=data, capture_output=True, check=True).stdout


manifest = json.loads(git("show", "%s:%sMANIFEST.json" % (commit, PREFIX)).decode("utf-8"))
files = manifest["files"]
request = "".join("%s:%s%s\n" % (commit, PREFIX, f["path"]) for f in files).encode("utf-8")
out = git("cat-file", "--batch", data=request)
pos, missing, mismatched = 0, [], []
for f in files:
    nl = out.index(b"\n", pos)
    header = out[pos:nl].decode("utf-8").split()
    if len(header) != 3 or header[1] != "blob":
        missing.append(f["path"])
        pos = nl + 1
        continue
    size = int(header[2])
    blob = out[nl + 1:nl + 1 + size]
    pos = nl + 1 + size + 1
    if size != f["bytes"] or hashlib.sha256(blob).hexdigest() != f["sha256"]:
        mismatched.append(f["path"])

tracked = set(git("ls-tree", "-r", "--name-only", commit, "--", PREFIX).decode("utf-8").splitlines())
expected = {PREFIX + f["path"] for f in files} | {PREFIX + x for x in ("MANIFEST.json", "README.md", ".gitattributes")}
unlisted, untracked = sorted(tracked - expected), sorted(expected - tracked)

# the paths go on stdin: 810 of them on one command line exceed Windows' limit (WinError 206)
attr_lines = git("check-attr", "--stdin", "text",
                 data=("\n".join(sorted(expected)) + "\n").encode("utf-8")).decode("utf-8").splitlines()
not_unset = [line for line in attr_lines if not line.endswith(": text: unset")
             and not line.startswith(PREFIX + ".gitattributes")]
eol = git("ls-files", "--eol", "--", PREFIX + "protocol/error-rate-protocol.md", PREFIX + "README.md").decode("utf-8")

print("commit %s: %d manifest files; blobs missing %d; hash or size mismatches %d; tracked but not listed %d; "
      "listed but not tracked %d; files whose text attribute is not unset %d"
      % (git("rev-parse", "--short", commit).decode().strip(), len(files), len(missing), len(mismatched),
         len(unlisted), len(untracked), len(not_unset)))
print(eol.rstrip())
for p in (missing + mismatched + unlisted + untracked + not_unset)[:12]:
    print("   ", p)
sys.exit(1 if (missing or mismatched or unlisted or untracked or not_unset) else 0)
