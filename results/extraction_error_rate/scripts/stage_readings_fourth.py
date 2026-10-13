r"""Stage draw four's first readings into fourth-sample/readings/, before the merge (implementation note 2).

Copies first-batch-1..4.json and census-reader-A/B.json from the reading directory. One file needs a mechanical
repair. Batch 4's reader rewrote its output after each record through a step that read the file as cp1252 and wrote it
as UTF-8, so every non-ASCII character of an earlier record's text was re-encoded once per later rewrite: the file grew
to 231.8 MB, and its earliest records' quotes to millions of characters. Each string field is repaired by undoing that
step, s = s.encode("cp1252").decode("utf-8"), for as many rounds as it applies, and the repair is accepted only if
re-applying the same rounds reproduces the stored string exactly (it is then lossless). Verdicts, numbers and pages
are ASCII or numeric and are untouched. Every repaired field is logged (stem, field, rounds, lengths) with the
SHA-256 of the file as the reader left it, in fourth-sample/readings/first-batch-4-encoding-repair.json. The original
file is not committed (it exceeds a git host's file limit); its hash identifies it.

Any other file with a field the repair would change is refused, not repaired. Nothing is copied over an existing file.

    python stage_readings_fourth.py [--from D:/tmp/r62/draw4/readings]
"""
import argparse
import hashlib
import io
import json
from pathlib import Path

SCR = Path(__file__).resolve().parent
DEST = SCR.parent / "fourth-sample" / "readings"
FILES = ["first-batch-%d.json" % n for n in (1, 2, 3, 4)] + ["census-reader-A.json", "census-reader-B.json"]
REPAIRED = "first-batch-4.json"
ENC = "cp1252"


def corrupt(s):
    return s.encode("utf-8").decode(ENC)


def repair(s):
    rounds = 0
    while True:
        try:
            t = s.encode(ENC).decode("utf-8")
        except (UnicodeEncodeError, UnicodeDecodeError):
            return s, rounds
        if t == s:
            return s, rounds
        s, rounds = t, rounds + 1


def repair_record(v, stem, log):
    out = {}
    for k, x in v.items():
        if isinstance(x, str):
            r, n = repair(x)
            if n:
                back = r
                for _ in range(n):
                    back = corrupt(back)
                if back != x:
                    raise SystemExit("%s %s: the repair does not round-trip; refused" % (stem, k))
                log.append({"stem": stem, "field": k, "rounds": n, "length_stored": len(x), "length_repaired": len(r)})
            out[k] = r
        elif isinstance(x, dict):
            out[k] = repair_record(x, stem, log) if x else x
        elif isinstance(x, list):
            out[k] = [repair(y)[0] if isinstance(y, str) else y for y in x]
            if any(isinstance(y, str) and repair(y)[1] for y in x):
                log.append({"stem": stem, "field": k, "rounds": "list"})
        else:
            out[k] = x
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="src", default=r"D:/tmp/r62/draw4/readings")
    a = ap.parse_args()
    src = Path(a.src)
    DEST.mkdir(parents=True, exist_ok=True)
    for name in FILES:
        target = DEST / name
        if target.exists():
            raise SystemExit("%s exists; readings are staged once" % target)
        raw = (src / name).read_bytes()
        data = json.loads(raw.decode("utf-8"))
        log = []
        fixed = [repair_record(v, v.get("stem"), log) for v in data]
        if name != REPAIRED:
            if log:
                raise SystemExit("%s: %d field(s) look re-encoded; refused, not repaired" % (name, len(log)))
            target.write_bytes(raw)
            print("%-22s copied byte for byte (%d records)" % (name, len(data)))
            continue
        for old, new in zip(data, fixed):
            for k in ("stem", "verdict", "adopted_figure_m", "filing_figure_m", "stated_movement_m", "pages",
                      "error_kind", "triangle_recomputation_m", "triangle_pages", "opening_reserves"):
                if k in old and k != "opening_reserves" and old[k] != new[k]:
                    raise SystemExit("%s %s: the repair changed a scored field" % (old.get("stem"), k))
        io.open(str(target), "w", encoding="utf-8", newline="\n").write(json.dumps(fixed, indent=1, ensure_ascii=False) + "\n")
        io.open(str(DEST / "first-batch-4-encoding-repair.json"), "w", encoding="utf-8", newline="\n").write(json.dumps({
            "what": ("batch 4's reader rewrote its output after each record through a cp1252 read and a UTF-8 write, so "
                     "each non-ASCII character of an earlier record's text was re-encoded once per later rewrite; "
                     "each field below is repaired by undoing that step its number of rounds, and re-applying them "
                     "reproduces the stored field exactly"),
            "script": "scripts/stage_readings_fourth.py",
            "stored_file": {"path": str(src / name).replace("\\", "/"), "bytes": len(raw),
                            "sha256": hashlib.sha256(raw).hexdigest()},
            "repaired_fields": log,
            "scored_fields_unchanged": ["stem", "verdict", "adopted_figure_m", "filing_figure_m", "stated_movement_m",
                                        "pages", "error_kind", "triangle_recomputation_m", "triangle_pages"],
        }, indent=1) + "\n")
        print("%-22s repaired %d field(s) in %d record(s) (%d bytes stored -> %d bytes)"
              % (name, len(log), len({e["stem"] for e in log}), len(raw), target.stat().st_size))


if __name__ == "__main__":
    main()
