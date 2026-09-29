"""Where a run is right now: pipeline phases, each student's stage, each agent's last action.

Two sources: the files agents have written into the run folder (answers, feedback,
grades, analysis) and runs/activity.jsonl, which .claude/hooks/log_activity.py appends
to on every tool call of a pipeline agent. Agents are matched to students by what
they touch: a student reads its own persona card first, a grader reads one answer sheet.
"""

import json
import re
import time
from datetime import datetime
from pathlib import Path

from examlib import ROOT

ACTIVITY = ROOT / "runs" / "activity.jsonl"
STAGES = ["waiting", "studying", "sitting", "feedback", "handed in", "grading", "graded"]


def load_activity(since):
    """Activity events from `since` (epoch seconds) on."""
    if not ACTIVITY.exists():
        return []
    events = []
    for line in ACTIVITY.read_text().splitlines():
        try:
            e = json.loads(line)
        except json.JSONDecodeError:
            continue
        if e.get("t", 0) >= since:
            events.append(e)
    return events


def mtime(path):
    return path.stat().st_mtime if path.exists() else None


def describe(e):
    """'Read 07 - Stackelberg games.tex' from an activity event."""
    target = e.get("target", "")
    if e.get("tool") in ("Read", "Write", "Edit"):
        target = Path(target).name
    action = f"{e.get('tool', '')} {target}".strip()
    return f"blocked: {action}" if e.get("blocked") else action


def compute_progress(run, events, final=False):
    m = run["manifest"]
    run_dir = m["run_dir"]
    d = run["dir"]
    started = datetime.fromisoformat(m["created"]).timestamp()
    persona_to_sid = {s["persona_id"]: s["sid"] for s in m["students"]}
    exam_file = m["exam"]["student_file"]

    # Match each agent to a student (or to this run, for analysts) by the files it touches.
    owner = {}
    for e in events:
        aid, target = e.get("agent_id"), e.get("target", "")
        if not aid or aid in owner:
            continue
        if e["agent_type"] == "student":
            hit = re.search(r"personas/([\w-]+)\.toml", target)
            if hit and hit.group(1) in persona_to_sid:
                owner[aid] = ("student", persona_to_sid[hit.group(1)])
            elif hit := re.search(re.escape(run_dir) + r"/(?:answers|feedback)/(S\d+)\.json", target):
                owner[aid] = ("student", hit.group(1))
        elif e["agent_type"] == "grader":
            if hit := re.search(re.escape(run_dir) + r"/(?:answers|grades)/(S\d+)\.json", target):
                owner[aid] = ("grader", hit.group(1))
        elif run_dir in target:
            owner[aid] = (e["agent_type"], None)

    by_role = {}
    for e in events:
        if e.get("agent_id") in owner:
            by_role.setdefault(owner[e["agent_id"]], []).append(e)

    stats_done = mtime(d / "analysis" / "stats.json")
    students = []
    for s in m["students"]:
        sid = s["sid"]
        answered = mtime(d / "answers" / f"{sid}.json")
        handed_in = mtime(d / "feedback" / f"{sid}.json")
        graded = mtime(d / "grades" / f"{sid}.json")
        own = by_role.get(("student", sid), [])
        grading = by_role.get(("grader", sid), [])
        if graded:
            stage = "graded"
        elif grading:
            stage = "grading"
        elif handed_in:
            stage = "handed in"
        elif answered:
            stage = "feedback"
        elif any(e.get("target", "").endswith(exam_file) and not e.get("blocked") for e in own):
            stage = "sitting"
        elif own:
            stage = "studying"
        else:
            stage = "waiting"
        if stage != "graded" and (stats_done or final):
            stage = "no result"  # the analysis has started without this student
        last = max(own + grading, key=lambda e: e["t"], default=None)
        grades = run["grades"][sid] or {}
        students.append({
            "sid": sid,
            "persona_id": s["persona_id"],
            "stage": stage,
            "started": min((e["t"] for e in own), default=None),
            "handed_in": handed_in,
            "graded": graded,
            "total": sum(float(q.get("points") or 0) for q in grades.get("questions", [])) if grades else None,
            "calls": len(own) + len(grading),
            "last": {"t": last["t"], "who": owner[last["agent_id"]][0], "action": describe(last)} if last else None,
        })

    n = len(students)
    n_in = sum(1 for s in students if s["handed_in"])
    n_graded = sum(1 for s in students if s["graded"])
    report_done = mtime(d / "dashboard.html")
    analysts = []
    for key, label, path in (("stats", "Statistics", d / "analysis" / "stats.json"),
                             ("feedback-analyst", "Feedback analyst", d / "analysis" / "feedback.json"),
                             ("exam-reviewer", "Exam reviewer", d / "analysis" / "recommendations.json"),
                             ("report", "Dashboard", d / "dashboard.html")):
        mine = by_role.get((key, None), [])
        done = mtime(path) or (final and key == "report")
        last = max(mine, key=lambda e: e["t"], default=None)
        analysts.append({
            "key": key, "label": label,
            "state": "done" if done else "active" if mine else "waiting",
            "finished": mtime(path),
            "last": {"t": last["t"], "action": describe(last)} if last else None,
        })

    complete = final or bool(report_done)
    any_started = any(s["stage"] != "waiting" for s in students)

    def state(done, total, active):
        return "done" if total and done >= total else "active" if active else "pending"

    analysis_steps = sum(1 for a in analysts[:3] if a["state"] == "done")
    phases = [
        {"key": "prepare", "label": "Prepare", "state": "done", "detail": f"{n} students"},
        {"key": "sit", "label": "Sit", "state": state(n_in, n, any_started), "done": n_in, "total": n},
        {"key": "grade", "label": "Grade", "state": state(n_graded, n, n_in > 0 or n_graded > 0), "done": n_graded, "total": n},
        {"key": "analyze", "label": "Analyze", "state": state(analysis_steps, 3, analysis_steps > 0 or any(a["state"] == "active" for a in analysts[:3])),
         "done": analysis_steps, "total": 3},
        {"key": "report", "label": "Report", "state": "done" if complete else "pending"},
    ]
    if complete:
        for p in phases:
            p["state"] = "done" if p["state"] != "pending" or p["key"] == "report" else p["state"]
    outputs = [p.stat().st_mtime for sub in ("answers", "feedback", "grades", "analysis") for p in (d / sub).glob("*.json")]
    finished = (max(outputs, default=None) or time.time()) if complete else None
    return {
        "started": started,
        "now": time.time(),
        "complete": complete,
        "finished": finished,
        "phases": phases,
        "students": students,
        "analysts": analysts,
        "stages": STAGES,
    }
