r"""Rebuild results/extraction_error_rate/MANIFEST.json over every file the archive holds (R221).

Each file keeps the entry it had, with its size and SHA-256 recomputed: a file changed since (the protocol, whose
amendments are appended) is hashed as it is now. A file the manifest did not list is added with the source "written in
place" and the round that wrote it. The archive's own MANIFEST.json, README.md and .gitattributes are not listed
(reproduce.py, ARCHIVE_OWN_FILES). A listed file that no longer exists stops the run. The format is the manifest's:
json.dumps(indent=1) and a newline, {"files": [...], "count": n}.

    python results/extraction_error_rate/scripts/rebuild_manifest.py [--dry-run] [--round R221]
"""
import argparse
import hashlib
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
STUDY = os.path.abspath(os.path.join(HERE, ".."))
MANIFEST = os.path.join(STUDY, "MANIFEST.json")
OWN = {"MANIFEST.json", "README.md", ".gitattributes"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--round", default="R221")
    args = ap.parse_args()
    old = json.load(io.open(MANIFEST, encoding="utf-8"))
    entries = {f["path"]: f for f in old["files"]}
    on_disk = []
    for dirpath, dirnames, filenames in os.walk(STUDY):
        dirnames[:] = sorted(d for d in dirnames if d != "__pycache__")
        for name in sorted(filenames):
            rel = os.path.relpath(os.path.join(dirpath, name), STUDY).replace(os.sep, "/")
            if rel in OWN:
                continue
            on_disk.append(rel)
    gone = sorted(set(entries) - set(on_disk))
    if gone:
        raise SystemExit("listed but missing: %s" % gone[:10])
    files, changed, added = [], 0, []
    for f in old["files"]:
        data = open(os.path.join(STUDY, *f["path"].split("/")), "rb").read()
        new = dict(f, bytes=len(data), sha256=hashlib.sha256(data).hexdigest())
        changed += new != f
        files.append(new)
    for rel in sorted(set(on_disk) - set(entries)):
        data = open(os.path.join(STUDY, *rel.split("/")), "rb").read()
        files.append({"path": rel, "source": "written in place (%s)" % args.round, "bytes": len(data),
                      "sha256": hashlib.sha256(data).hexdigest()})
        added.append(rel)
    out = json.dumps({"files": files, "count": len(files)}, indent=1) + "\n"
    print("%d files: %d re-hashed with new bytes, %d added" % (len(files), changed, len(added)))
    for rel in added:
        print("  + %s" % rel)
    if not args.dry_run:
        io.open(MANIFEST, "w", encoding="utf-8", newline="\n").write(out)
        print("MANIFEST.json written")
    return 0


if __name__ == "__main__":
    sys.exit(main())
