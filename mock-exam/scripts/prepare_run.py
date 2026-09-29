"""Create a run folder for an exam and print its manifest as JSON.

Students get anonymous ids (S01, S02, ...) in a shuffled order, so graders cannot
infer the persona from the id. Each student gets the materials their persona's
`coverage` reaches.

Usage:
    python3 scripts/prepare_run.py --exam example [--personas lena,arjun] [--label pilot]
"""

import argparse
import json
import math
import random
from datetime import datetime

from examlib import ROOT, load_exam, load_personas, write_json


def materials_for(card, materials):
    """Materials up to the week the persona's coverage reaches; unweeked materials always."""
    weeks = [m["week"] for m in materials if "week" in m]
    if not weeks:
        return [m["path"] for m in materials]
    cutoff = math.floor(card["preparation"]["coverage"] * max(weeks) + 1e-9)
    return [m["path"] for m in materials if m.get("week", 0) <= cutoff]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--exam", required=True, help="folder name under exams/")
    ap.add_argument("--personas", help="comma-separated persona ids (default: exam config, else all)")
    ap.add_argument("--label", help="suffix for the run id, e.g. pilot")
    args = ap.parse_args()

    exam = load_exam(args.exam)
    ids = args.personas.split(",") if args.personas else exam.get("personas")
    cards = load_personas(ids)
    if not cards:
        raise SystemExit("No persona cards found in personas/")

    materials = exam.get("materials", [])
    paths = [exam["student_file"], *exam["solution_files"], *(m["path"] for m in materials)]
    missing = [p for p in paths if not (ROOT / p).exists()]
    if missing:
        raise SystemExit(f"Missing files referenced by exams/{args.exam}/exam.toml: {', '.join(missing)}")

    run_id = datetime.now().strftime("%Y-%m-%d_%H%M%S") + (f"_{args.label}" if args.label else "")
    run_dir = ROOT / "runs" / args.exam / run_id
    for sub in ("answers", "feedback", "grades", "analysis"):
        (run_dir / sub).mkdir(parents=True, exist_ok=True)

    order = list(cards)
    random.Random(run_id).shuffle(order)
    students = [
        {
            "sid": f"S{i:02d}",
            "persona_id": pid,
            "persona_file": f"personas/{pid}.toml",
            "model": cards[pid].get("model", exam.get("student_model", "sonnet")),
            "materials": materials_for(cards[pid], materials),
        }
        for i, pid in enumerate(order, start=1)
    ]

    keys = ("id", "title", "course", "duration_min", "language", "aids", "pass_fraction", "typical_score", "open_book",
            "student_file", "solution_files", "total_points", "questions")
    manifest = {
        "exam_id": args.exam,
        "run_id": run_id,
        "run_dir": str(run_dir.relative_to(ROOT)),
        "created": datetime.now().isoformat(timespec="seconds"),
        "exam": {k: exam[k] for k in keys if k in exam},
        "students": students,
    }
    write_json(run_dir / "manifest.json", manifest)
    print(json.dumps(manifest, ensure_ascii=False))


if __name__ == "__main__":
    main()
