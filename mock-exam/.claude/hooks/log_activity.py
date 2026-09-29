#!/usr/bin/env python3
"""PostToolUse logger: appends what the exam agents did to runs/activity.jsonl.

PostToolUse fires only for calls that ran, so a call the student guard blocked never
appears here; the guard logs its blocks itself, marked "blocked".

The live dashboard (scripts/live_server.py) reads this log to show each agent's last
action. Only the pipeline's own agents are logged, never the main session. The hook
must never get in the way, so any failure is swallowed and it always exits 0.
"""

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LOG = ROOT / "runs" / "activity.jsonl"
TRACKED = {"student", "grader", "feedback-analyst", "exam-reviewer"}


def target_of(tool, tool_input):
    if tool in ("Read", "Write", "Edit"):
        return tool_input.get("file_path", "")
    if tool in ("Glob", "Grep"):
        return " ".join(x for x in (tool_input.get("pattern", ""), tool_input.get("path", "")) if x)
    if tool == "Bash":
        return tool_input.get("command", "")[:200]
    return ""


def main():
    try:
        event = json.load(sys.stdin)
        if event.get("agent_type") not in TRACKED:
            return
        tool = event.get("tool_name", "")
        target = target_of(tool, event.get("tool_input") or {})
        if target.startswith(str(ROOT) + "/"):
            target = target[len(str(ROOT)) + 1:]
        line = {"t": round(time.time(), 2), "agent_id": event.get("agent_id"), "agent_type": event["agent_type"],
                "tool": tool, "target": target}
        LOG.parent.mkdir(exist_ok=True)
        with open(LOG, "a") as f:
            f.write(json.dumps(line, ensure_ascii=False) + "\n")
    except Exception:
        pass


if __name__ == "__main__":
    main()
