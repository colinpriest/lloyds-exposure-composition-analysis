"""Classify the source formats recorded in per-filing extraction JSON.

The source documents are not committed here. Counts describe source_file metadata,
not a fresh scan of the inaccessible source documents.
"""
from collections import Counter
import json
from pathlib import PurePosixPath, Path


def source_format(source_file):
    if not isinstance(source_file, str) or not source_file.strip():
        return "unknown"
    suffix = PurePosixPath(source_file.replace("\\", "/")).suffix.lower()
    if suffix == ".pdf":
        return "PDF"
    if suffix in (".html", ".htm"):
        return "HTML"
    return "unknown"


def count_sources(paths):
    counts = Counter()
    for path in paths:
        record = json.loads(Path(path).read_text(encoding="utf-8"))
        counts[source_format(record.get("source_file"))] += 1
    return counts


def format_counts(counts):
    """A deterministic, complete breakdown, including any unrecognised source."""
    labels = [("PDF", "PDF"), ("HTML", "HTML"), ("unknown", "unknown format")]
    entries = ["{:,} {}".format(counts[k], label) for k, label in labels if counts.get(k, 0)]
    if not entries:
        return "no source-format records"
    if len(entries) == 1:
        return entries[0]
    return ", ".join(entries[:-1]) + " and " + entries[-1]
