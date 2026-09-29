# mock-exam

Pilot a new exam on simulated students before real students see it. Persona agents study the course materials and sit the exam, blind graders mark it against your solution, and two analysts turn the results into proposed edits to the exam.

Simulated students score higher than real ones, so read the grades as relative. The reliable signals are about the exam itself: ambiguous wording, questions that take longer than their points suggest, errors, and scope mismatches.

## Start a mock exam

Open Claude Code in this folder (`claude`) and accept the trust prompt, which the hooks need. Then ask:

```text
Run /mock-exam on the example exam with lena, sofia and tobias.
```

The students study, sit the exam, and hand in answers and feedback; graders mark each script; the analysts then report the issues they found and the edits they recommend. Claude summarizes these when the run ends. Everything is saved in `runs/<exam>/<run_id>/`, with the findings in `analysis/feedback.json` and `analysis/recommendations.json`.

More prompts:

```text
Run /mock-exam on my-exam with all personas.
```

```text
Run /mock-exam on my-exam with yusuf, hannah, lena and sofia, and label the run pilot.
```

```text
Run /mock-exam on my-exam with lena, sofia and tobias. When it finishes, list the three most important issues the analysts found.
```

The exam is a folder name under `exams/`, and the students are persona ids from `personas/`. Without a list, a run uses the exam's `personas` setting, or every card.

Start with three or four students. Every student reads all their materials, so cost grows with students × materials.

The example exam has two planted flaws, and a working run flags both:
- Q1 says "dominated" without saying strict or weak.
- Q2c asks for "the equilibrium payoff" of a game with three equilibria.

## Your own exam

1. Copy `exams/example/` to `exams/<exam-id>/`. Add the exam without solutions, and the solution or rubric with `solution` or `rubric` in its file name.
2. Put the course materials in `materials/<course>/`.
3. In `exam.toml`, set:
   - the duration and allowed aids;
   - the questions with their points;
   - the solution files;
   - the materials in lecture order, each with a `week`.

Students see only three things:
- their persona card;
- the materials their `coverage` reaches;
- the exam, once they have read those materials.

The materials are put away when the exam opens, unless `open_book = true`. A hook enforces all of this.

Exams, materials and runs are gitignored; only the example is tracked. The agents send what they read to the model provider, so check your institution's rules for unreleased exams.

## Personas

One card per student in `personas/<id>.toml`. The fields that matter most:

| Field | Effect |
|---|---|
| `ability` | top 10%, above median, median, below median or bottom quarter; the student performs at that level (anchor it with the exam's `typical_score`) |
| `background`, `focus` | prior knowledge beyond the course |
| `preparation.coverage` | share of the course studied, which decides the materials |
| `profile.misconceptions` | beliefs applied without flagging them, the source of realistic mistakes |
| `exam_behavior` | speed and question order, which drive the simulated clock |
| `model` | optional, e.g. `"haiku"` for a weaker student (default `sonnet`) |

## How it works

```
prepare_run.py → student ×N → grader ×N → analyze_run.py → feedback-analyst → exam-reviewer
```

- `.claude/workflows/mock-exam.js` runs the pipeline. Each answer sheet goes to a grader as soon as it is handed in.
- `.claude/agents/`: `student`, `grader` (blind, flags ambiguous wording), `feedback-analyst` and `exam-reviewer`. Graders and analysts run on Opus; change `model:` in their files to save cost.
- `.claude/hooks/`: `guard_student.py` controls what students may read and write, and `log_activity.py` records what the agents do.

Tests: `python3 -m unittest discover tests`

## Optional: dashboard

Each run also ends with a `dashboard.html` in its folder, for browsing students, answers and questions. To follow a run while it is in progress:

```bash
python3 scripts/live_server.py
```

Then open http://localhost:8131 (add `--port 8132` if the port is taken).
