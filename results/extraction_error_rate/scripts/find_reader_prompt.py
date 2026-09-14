r"""Recover the error-rate first readers' prompts from this session's transcript. Read-only.

Writes reader-prompt-batch-<n>.txt for every "Error-rate first reading" agent call found, so a later
re-reading can use the same instruction word for word.

    python find_reader_prompt.py
"""
import io
import json
import re
from pathlib import Path

SCR = Path(__file__).resolve().parent
TRANSCRIPT = Path(r"C:\Users\colin\.claude\projects\D--Latex-projects-BAJ---Lloyds-reserves-rescaling--claude-worktrees-fixed-effects-syndicate-repeats-fff692\9e91ee54-a3fb-43e4-ae67-a88d2e6ac499.jsonl")

found = {}
with io.open(str(TRANSCRIPT), encoding="utf-8", errors="replace") as fh:
    for line in fh:
        if "Error-rate first reading" not in line:
            continue
        try:
            d = json.loads(line)
        except ValueError:
            continue
        for block in ((d.get("message") or {}).get("content") or []):
            if not (isinstance(block, dict) and block.get("type") == "tool_use" and block.get("name") == "Agent"):
                continue
            inp = block.get("input") or {}
            desc = str(inp.get("description") or "")
            m = re.search(r"Error-rate first reading, batch (\d+)", desc)
            if m:
                found[int(m.group(1))] = inp.get("prompt") or ""
for n in sorted(found):
    p = SCR / ("reader-prompt-batch-%d.txt" % n)
    io.open(str(p), "w", encoding="utf-8").write(found[n])
    print("batch %d: %d characters -> %s" % (n, len(found[n]), p.name))
if not found:
    print("no first-reader prompt found in the transcript")
