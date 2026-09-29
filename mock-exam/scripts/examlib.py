"""Shared loaders for exam configs, persona cards and run folders."""

import json
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def load_toml(path):
    with open(path, "rb") as f:
        return tomllib.load(f)


def load_exam(exam_id):
    path = ROOT / "exams" / exam_id / "exam.toml"
    if not path.exists():
        raise SystemExit(f"No exam config at {path.relative_to(ROOT)}")
    exam = load_toml(path)
    required = ("title", "duration_min", "student_file", "solution_files", "questions")
    missing = [k for k in required if k not in exam]
    if missing:
        raise SystemExit(f"{path.relative_to(ROOT)} is missing: {', '.join(missing)}")
    exam["id"] = exam_id
    exam["total_points"] = sum(q["points"] for q in exam["questions"])
    return exam


def load_personas(ids=None):
    """Persona cards keyed by file stem (personas/<id>.toml)."""
    cards = {p.stem: load_toml(p) for p in sorted((ROOT / "personas").glob("*.toml"))}
    if ids:
        unknown = [i for i in ids if i not in cards]
        if unknown:
            raise SystemExit(f"Unknown persona(s): {', '.join(unknown)}. Available: {', '.join(cards)}")
        cards = {i: cards[i] for i in ids}
    return cards


def read_json(path):
    path = Path(path)
    return json.loads(path.read_text()) if path.exists() else None


def write_json(path, data):
    Path(path).write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")


def load_run(run_dir):
    """Everything the agents and scripts wrote into a run folder. Missing files come back as None."""
    run_dir = Path(run_dir)
    if not run_dir.is_absolute():
        run_dir = ROOT / run_dir
    manifest = read_json(run_dir / "manifest.json")
    if manifest is None:
        raise SystemExit(f"No manifest.json in {run_dir}")
    sids = [s["sid"] for s in manifest["students"]]
    return {
        "dir": run_dir,
        "manifest": manifest,
        "answers": {sid: read_json(run_dir / "answers" / f"{sid}.json") for sid in sids},
        "feedback": {sid: read_json(run_dir / "feedback" / f"{sid}.json") for sid in sids},
        "grades": {sid: read_json(run_dir / "grades" / f"{sid}.json") for sid in sids},
        "issues": read_json(run_dir / "analysis" / "feedback.json"),
        "recommendations": read_json(run_dir / "analysis" / "recommendations.json"),
    }
