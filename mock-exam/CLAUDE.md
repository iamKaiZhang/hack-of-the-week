# mock-exam

Pilot a newly written exam on a class of simulated students before real students see it. Persona agents sit the exam, blind graders mark it, analysts turn results and feedback into proposed edits, and a script builds an HTML dashboard.

## Pipeline

`/mock-exam <exam-id>` (`.claude/workflows/mock-exam.js`) runs:

1. **Prepare**: `scripts/prepare_run.py` creates `runs/<exam>/<run_id>/`, shuffles personas into anonymous ids (S01, ...), and picks each student's materials from their `coverage`.
2. **Sit**: one `student` agent per persona (`.claude/agents/student.md`) writes `answers/Sxx.json` and `feedback/Sxx.json`.
3. **Grade**: one `grader` per sheet writes `grades/Sxx.json`. Pipelined, so grading starts as soon as a sheet is in.
4. **Analyze**: `scripts/analyze_run.py` writes `analysis/stats.json`; `feedback-analyst` writes `analysis/feedback.json`; `exam-reviewer` writes `analysis/recommendations.json`.
5. **Report**: `scripts/build_dashboard.py` writes `dashboard.html` (self-contained, opens from file://).

Live view: `scripts/live_server.py` serves the same template in polling mode (`/run/<exam>/<run_id>`, data at `/api/...`). `scripts/progress.py` infers each student's stage from which files exist plus `runs/activity.jsonl`, which `.claude/hooks/log_activity.py` (PreToolUse, never blocks) appends to for the four pipeline agents. Agents are matched to students by the first file they touch: a student's persona card, a grader's answer sheet.

Optional args: `{exam, personas: [...], label}`. The JSON formats each agent writes are defined in its agent file; `scripts/analyze_run.py` and `scripts/dashboard_template.html` read them, so change all three together.

## Conventions

- Configs are TOML (stdlib `tomllib`, no dependencies): `exams/<id>/exam.toml`, `personas/<id>.toml`. Copy `exams/example/` for a new exam. Keep `exams/example/` and `materials/example/`: the tests run on them.
- The student-facing exam file must not contain solutions. Solution files are listed in `solution_files` and should have `solution` or `rubric` in the name.
- `.claude/hooks/guard_student.py` (PreToolUse, in `.claude/settings.json`) is an allowlist for the `student` agent. Reading its persona card seats the agent in the newest run where that persona has not handed in (state in `runs/.agents/<agent_id>.json`). From then on it may read only its persona card, its assigned materials (the exam config's `materials`, cut by coverage) and the exam, the exam only after all its materials, and the materials no longer once the exam is open (unless `open_book = true` in `exam.toml`); and it may write only its own answers and feedback. A student agent outside any run falls back to a blocklist (no solutions or rubrics, no `runs/`, nothing outside the project). What students can see is therefore set in `exam.toml`. It keys on `agent_type == "student"`; keep the agent's name in sync. The hook command finds the script via `$CLAUDE_PROJECT_DIR`, else by walking up from the working directory, and lets the call through if neither works (a missing script would otherwise exit 2 and block every agent's file access).
- Students run without CLAUDE.md (`omitClaudeMd`), so nothing here leaks into their context.
- Real exams and course materials are gitignored (only `example/` is tracked), and so is `runs/`.

## Commands

- Tests: `python3 -m unittest discover tests`
- Live dashboards: `python3 scripts/live_server.py` → http://localhost:8131
- Rebuild a dashboard after editing the template: `python3 scripts/build_dashboard.py runs/<exam>/<run_id>`
- Preview the synthetic demo: `python3 scripts/build_dashboard.py tests/fixtures/demo-run --output runs/demo-dashboard.html`
