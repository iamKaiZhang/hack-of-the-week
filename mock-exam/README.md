# mock-exam

Pilot a new exam on a class of simulated students before real students see it.

Each student is an agent playing a persona: a background, a level, how much of the course they studied, their strengths, weaknesses and misconceptions, and how they behave under time pressure. They read the course materials they studied, sit the exam against a clock, and fill in a feedback survey. Blind graders mark every script against your solution, two analysts turn the results into concrete edits, and a script builds a dashboard.

**What to trust.** LLM students are stronger than their personas intend, so the grade distribution is not a forecast. The useful signals are about the exam itself: wording that allows two readings, questions that take far longer than their points, errors, and scope mismatches. The dashboard leads with those.

## Quick start

1. Open Claude Code in this folder and accept the trust prompt. The trust is needed for the hook that keeps students away from the solutions.
2. Preview the dashboard on synthetic demo data (hand-written, no agents involved):
   ```bash
   python3 scripts/build_dashboard.py tests/fixtures/demo-run --output runs/demo-dashboard.html && open runs/demo-dashboard.html
   ```
3. Smoke-test the real pipeline on the example exam with three students by asking Claude:
   ```text
   Run /mock-exam on the example exam with lena, sofia and tobias.
   ```
   (`/mock-exam example` runs every persona card in `personas/`.) Watch it with `/workflows`. The example exam contains two planted flaws (Q1 says “dominated” without strict or weak; Q2c asks for “the equilibrium payoff” of a game with three equilibria), so a working run should flag both.
4. Open `runs/example/<run_id>/dashboard.html`.

## Follow a run live

From the `mock-exam` folder (or from anywhere, with the script's full path):

```bash
python3 scripts/live_server.py
```

Then open http://localhost:8131 and pick the run. If the port is taken, add `--port 8132`. The page, styled after the Claude Code docs explorer, refreshes every few seconds:

- **Progress:** each pipeline stage with its counts, plus one row per student showing their current step (studying, sitting the exam, writing feedback, being graded) and their last action.
- **Explorer:** a sidebar of students (by level) and questions (by exercise), with a panel for whichever you pick. A student's panel shows their profile, score and every answer, with the grader's note and any ambiguity flag. A question's panel shows its statistics, issues, the suggested change and all students' answers.
- **Filling in:** the heatmap, recommendations and quotes fill in as grades and analysis arrive.

The server only listens on your own machine and serves run data only, never exam or solution files. Agent actions come from `runs/activity.jsonl`, which a hook appends to on every file read or write by a student, grader or analyst.

## Your own exam

1. Copy `exams/example/` to `exams/<exam-id>/`. Put the compiled exam (without solutions) and the solution or rubric there.
2. Put the course materials in `materials/<course>/`.
3. Edit `exams/<exam-id>/exam.toml`: duration, aids, questions with points, solution files, and materials in lecture order with a `week` each. The week lets a persona who studied 60% of the course get only the first 60% of the materials.
4. Run `/mock-exam <exam-id>`. With no persona list it uses every card in `personas/`.

**What students can see is set in `exam.toml`.** A student can read only three things:

- its own persona card;
- the `materials` its coverage reaches (entries without a `week` go to everyone);
- the exam, and only after it has read all of those materials. Once the exam is open, the materials are put away, unless the exam sets `open_book = true`.

To hand out exercise sheets, a formula sheet or old exams, add them to `materials`. A hook enforces all of this, and it also stops students from writing anything except their own answer sheet and feedback.

Exams, materials and runs are gitignored (only the example is tracked), so an unreleased exam does not end up on GitHub by accident. The agents do send what they read to the model provider, so check your institution's rules for unreleased exams.

## How it works

```
prepare_run.py ─► student ×N ─► grader ×N ─► analyze_run.py ─► feedback-analyst ─► exam-reviewer ─► build_dashboard.py
  run folder,      answers/       grades/      stats.json        feedback.json       recommendations.json   dashboard.html
  anonymous ids    feedback/
```

- `.claude/workflows/mock-exam.js` orchestrates everything. Each student's script goes to a grader as soon as it is handed in; the analysis waits for the whole class.
- `.claude/agents/`: `student` (in character, Read and Write only, no CLAUDE.md), `grader` (blind, rubric-bound, flags ambiguous wording), `feedback-analyst` (clusters feedback into issues with evidence), `exam-reviewer` (turns issues into concrete edits).
- `.claude/hooks/guard_student.py` blocks the student agent from reading solutions, rubrics, other students' files or anything outside the project.
- `scripts/`: run preparation, statistics (score, time against the per-question budget, clarity, discrimination) and the dashboard (`dashboard_template.html`, one self-contained file with no server needed).

## Personas

Cards live in `personas/<id>.toml`. Copy one and edit it. The fields that shape behavior most:

- `ability`: where the student stands in the class (top 10%, above median, median, below median, bottom quarter). The student agent performs at that level; set the exam's `typical_score` (median share of points) to anchor it.
- `background` and `focus`: home discipline and main interest (e.g. mathematics, markets). They set the prior knowledge a student brings beyond the course.
- `preparation.coverage`: share of the course studied, in lecture order. Decides which materials the student gets.
- `profile.misconceptions`: beliefs the student applies without flagging them. This is where realistic mistakes come from.
- `exam_behavior.speed` and `strategy`: drive the simulated clock and the order of questions.
- `model` (optional): e.g. `"haiku"` for a weaker student. The default comes from the exam's `student_model` (`sonnet`).

## Cost

Every student reads their materials in full, so tokens grow with materials × students. Start with three students. Graders and analysts run on Opus; change `model:` in `.claude/agents/*.md` to trade quality for cost.

## Tests

```bash
python3 -m unittest discover tests
```

These cover the deterministic parts: materials selection, run preparation, statistics, the guard hook and the dashboard build.
