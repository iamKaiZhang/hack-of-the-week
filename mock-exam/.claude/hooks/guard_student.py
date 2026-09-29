#!/usr/bin/env python3
"""PreToolUse guard for the `student` agent: students see only what the exam config gives them.

A student first reads its persona card. That binds the agent to its seat in the newest
run where that persona has not handed in yet, and from then on it may read only:

- its persona card,
- the materials the run assigned to it (exams/<id>/exam.toml `materials`, cut by coverage),
- the exam file, and only after it has read every one of its materials, since real
  students study before they see the exam.

Once the exam is open, the materials are put away unless the exam config sets
`open_book = true`.

It may write only its own answer sheet and feedback. The binding is kept in
runs/.agents/<agent_id>.json, one file per agent, so parallel students never collide.

A student agent outside a run (e.g. a manual test) falls back to a blocklist: no
solutions or rubrics, nothing under runs/, nothing outside the project.
Every other agent, and the main session, passes through untouched.

Exit code 2 blocks the tool call and shows the stderr message to the agent.
"""

import json
import re
import sys
import time
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
AGENTS = ROOT / "runs" / ".agents"
SECRET_NAME = re.compile(r"solution|rubric|l(ö|oe)sung|answer[-_ ]?key|marking", re.IGNORECASE)
PERSONA = re.compile(r"personas/([\w-]+)\.toml")
CONTEXT = {}  # the call being checked, so a block can be logged for the live dashboard


def block(message):
    if CONTEXT.get("agent_id"):
        try:
            with open(ROOT / "runs" / "activity.jsonl", "a") as f:
                f.write(json.dumps({"t": round(time.time(), 2), **CONTEXT, "blocked": True}, ensure_ascii=False) + "\n")
        except OSError:
            pass
    print(message, file=sys.stderr)
    sys.exit(2)


def relative(raw, cwd):
    path = Path(raw)
    if not path.is_absolute():
        path = Path(cwd or ROOT) / path
    path = path.resolve()
    return str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else None


def bind(agent_id, persona_id):
    """Seat this agent in the newest run where the persona has not handed in yet."""
    manifests = sorted(ROOT.glob("runs/*/*/manifest.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    for path in manifests:
        m = json.loads(path.read_text())
        for s in m["students"]:
            if s["persona_id"] == persona_id and not (path.parent / "feedback" / f"{s['sid']}.json").exists():
                seat = {"run_dir": m["run_dir"], "sid": s["sid"], "persona_file": s["persona_file"],
                        "exam_file": m["exam"]["student_file"], "open_book": bool(m["exam"].get("open_book")),
                        "materials": s["materials"], "read": [], "exam_started": False}
                AGENTS.mkdir(parents=True, exist_ok=True)
                (AGENTS / f"{agent_id}.json").write_text(json.dumps(seat, indent=2))
                return seat
    return None


def configured_solution_files():
    paths = set()
    for cfg in ROOT.glob("exams/*/exam.toml"):
        try:
            data = tomllib.loads(cfg.read_text())
        except (OSError, tomllib.TOMLDecodeError):
            continue
        paths.update(str(Path(p)) for p in data.get("solution_files", []))
    return paths


def blocklist(tool, rel):
    """Rules for a student agent that is not seated in a run."""
    if tool == "Read":
        if rel is None:
            block("Students can only read files inside the exam project.")
        if SECRET_NAME.search(Path(rel).name) or rel in configured_solution_files():
            block("Students cannot read solutions or rubrics.")
        if rel.startswith("runs/"):
            block("Students cannot read run files (other students' answers or grades).")
    elif not (rel and len(Path(rel).parts) == 5 and rel.startswith("runs/") and Path(rel).parts[3] in ("answers", "feedback")):
        block("Students may only write their own answer sheet and feedback under runs/<exam>/<run>/answers|feedback/.")


def main():
    event = json.load(sys.stdin)
    if event.get("agent_type") != "student":
        return
    tool = event.get("tool_name")
    raw = (event.get("tool_input") or {}).get("file_path")
    if tool not in ("Read", "Write", "Edit") or not raw:
        return
    rel = relative(raw, event.get("cwd"))
    agent_id = event.get("agent_id") or ""
    CONTEXT.update(agent_id=agent_id, agent_type="student", tool=tool, target=rel or raw)
    state_file = AGENTS / f"{agent_id}.json"
    seat = json.loads(state_file.read_text()) if agent_id and state_file.exists() else None

    if seat is None and tool == "Read" and rel and (hit := PERSONA.fullmatch(rel)) and agent_id:
        bind(agent_id, hit.group(1))
        return  # reading one's persona card is always allowed
    if seat is None:
        return blocklist(tool, rel)

    if tool == "Read":
        if rel == seat["persona_file"]:
            return
        if rel in seat["materials"]:
            if seat.get("exam_started") and not seat.get("open_book"):
                block("The exam is closed book: your course materials are put away once the exam has started.")
            if rel not in seat["read"]:
                seat["read"].append(rel)
                state_file.write_text(json.dumps(seat, indent=2))
            return
        if rel == seat["exam_file"]:
            unread = [p for p in seat["materials"] if p not in seat["read"]]
            if unread:
                block("The exam is handed out after you have studied. Read your materials first: " + "; ".join(unread))
            if not seat.get("exam_started"):
                seat["exam_started"] = True
                state_file.write_text(json.dumps(seat, indent=2))
            return
        block("You may only read your persona card, your course materials and, once you have studied them, the exam.")
    own = (f"{seat['run_dir']}/answers/{seat['sid']}.json", f"{seat['run_dir']}/feedback/{seat['sid']}.json")
    if rel not in own:
        block(f"You may only write your own answer sheet and feedback: {own[0]} and {own[1]}.")


if __name__ == "__main__":
    main()
