"""Compute per-student and per-question statistics for a run.

Writes <run_dir>/analysis/stats.json and prints a short summary. Points are taken
from the grades per question and capped at the maximum in the exam config, so a
grader's arithmetic slip in `total` cannot distort the numbers.

Usage:
    python3 scripts/analyze_run.py runs/<exam>/<run_id>
"""

import argparse
import statistics
from collections import Counter

from examlib import load_personas, load_run, write_json


def mean(xs):
    xs = [x for x in xs if x is not None]
    return statistics.fmean(xs) if xs else None


def pearson(xs, ys):
    """Correlation, or None when it is undefined (fewer than 3 students or no variance)."""
    if len(xs) < 3:
        return None
    mx, my = statistics.fmean(xs), statistics.fmean(ys)
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    sxx = sum((x - mx) ** 2 for x in xs)
    syy = sum((y - my) ** 2 for y in ys)
    return sxy / (sxx * syy) ** 0.5 if sxx > 0 and syy > 0 else None


def by_qid(entries):
    return {e["qid"]: e for e in entries or []}


def compute_stats(run):
    m = run["manifest"]
    exam = m["exam"]
    questions = exam["questions"]
    max_pts = {q["id"]: q["points"] for q in questions}
    total_max = exam["total_points"]
    duration = exam["duration_min"]
    pass_fraction = exam.get("pass_fraction", 0.5)
    cards = load_personas()

    students, missing = [], []
    for s in m["students"]:
        sid = s["sid"]
        grades = run["grades"][sid]
        if not grades:
            missing.append(sid)
            continue
        answers = run["answers"][sid] or {}
        feedback = run["feedback"][sid] or {}
        g = by_qid(grades.get("questions"))
        a = by_qid(answers.get("answers"))
        fq = by_qid(feedback.get("questions"))
        q_pts = {qid: min(max(float(g.get(qid, {}).get("points") or 0), 0), mx) for qid, mx in max_pts.items()}
        total = sum(q_pts.values())
        overall = feedback.get("overall", {})
        clarity = mean([fq[q].get("clarity") for q in fq])
        students.append({
            "sid": sid,
            "persona_id": s["persona_id"],
            "level": cards.get(s["persona_id"], {}).get("level"),
            "total": total,
            "pct": total / total_max,
            "passed": total / total_max >= pass_fraction,
            "q_pts": q_pts,
            "q_pct": {qid: q_pts[qid] / mx for qid, mx in max_pts.items()},
            "q_status": {qid: a.get(qid, {}).get("status", "blank") for qid in max_pts},
            "minutes_used": answers.get("minutes_used"),
            "ran_out_of_time": bool(answers.get("ran_out_of_time")),
            "difficulty_felt": overall.get("difficulty"),
            "length_vote": overall.get("length"),
            "fairness_felt": overall.get("fairness"),
            "clarity_felt": clarity,
        })

    per_question = []
    for q in questions:
        qid, mx = q["id"], q["points"]
        pcts = [st["q_pct"][qid] for st in students]
        rest = [(st["total"] - st["q_pts"][qid]) / (total_max - mx) for st in students] if total_max > mx else []
        # Time a question takes: average over students who attempted it, so blanks do not pull it down.
        minutes = [
            by_qid((run["answers"][st["sid"]] or {}).get("answers")).get(qid, {}).get("minutes")
            for st in students if st["q_status"][qid] != "blank"
        ]
        fq = [by_qid((run["feedback"][st["sid"]] or {}).get("questions")).get(qid, {}) for st in students]
        flags = [
            {"sid": st["sid"], "note": gq["ambiguity"]}
            for st in students
            if (gq := by_qid(run["grades"][st["sid"]].get("questions")).get(qid, {})).get("ambiguity")
        ]
        budget = duration * mx / total_max
        mean_minutes = mean(minutes)
        per_question.append({
            "qid": qid,
            "topic": q.get("topic", ""),
            "points": mx,
            "mean_pct": mean(pcts),
            "sd_pct": statistics.pstdev(pcts) if len(pcts) > 1 else None,
            "discrimination": pearson(pcts, rest) if rest else None,
            "status_counts": dict(Counter(st["q_status"][qid] for st in students)),
            "budget_minutes": budget,
            "mean_minutes": mean_minutes,
            "time_ratio": mean_minutes / budget if mean_minutes is not None and budget else None,
            "clarity_mean": mean([f.get("clarity") for f in fq]),
            "difficulty_mean": mean([f.get("difficulty") for f in fq]),
            "ambiguity_flags": flags,
        })

    pcts = [st["pct"] for st in students]
    minutes = [st["minutes_used"] for st in students if st["minutes_used"] is not None]
    levels = sorted({st["level"] for st in students if st["level"]})
    overall = {
        "n_planned": len(m["students"]),
        "n_graded": len(students),
        "missing": missing,
        "mean_pct": mean(pcts),
        "median_pct": statistics.median(pcts) if pcts else None,
        "pass_rate": mean([1.0 if st["passed"] else 0.0 for st in students]),
        "median_minutes": statistics.median(minutes) if minutes else None,
        "share_ran_out": mean([1.0 if st["ran_out_of_time"] else 0.0 for st in students]),
        "length_votes": dict(Counter(st["length_vote"] for st in students if st["length_vote"])),
        "difficulty_mean": mean([st["difficulty_felt"] for st in students]),
        "fairness_mean": mean([st["fairness_felt"] for st in students]),
        "by_level": {
            lv: {"n": len(g), "mean_pct": mean([st["pct"] for st in g])}
            for lv in levels
            if (g := [st for st in students if st["level"] == lv])
        },
    }
    return {"overall": overall, "students": students, "questions": per_question}


def fmt_pct(x):
    return "n/a" if x is None else f"{100 * x:.0f}%"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("run_dir")
    args = ap.parse_args()

    run = load_run(args.run_dir)
    stats = compute_stats(run)
    write_json(run["dir"] / "analysis" / "stats.json", stats)

    o = stats["overall"]
    print(f"Graded {o['n_graded']}/{o['n_planned']} students"
          + (f" (missing: {', '.join(o['missing'])})" if o["missing"] else ""))
    print(f"Mean {fmt_pct(o['mean_pct'])}, pass rate {fmt_pct(o['pass_rate'])}, ran out of time {fmt_pct(o['share_ran_out'])}")
    for q in stats["questions"]:
        ratio = "n/a" if q["time_ratio"] is None else f"{q['time_ratio']:.1f}x"
        print(f"  {q['qid']:>5}: mean {fmt_pct(q['mean_pct'])}, time {ratio} of budget, "
              f"{len(q['ambiguity_flags'])} ambiguity flag(s)")
    print(f"Wrote {(run['dir'] / 'analysis' / 'stats.json')}")


if __name__ == "__main__":
    main()
