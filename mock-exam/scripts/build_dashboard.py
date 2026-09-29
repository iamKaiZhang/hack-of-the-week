"""Build a self-contained HTML dashboard for a run.

Reads everything in the run folder, recomputes the statistics and the progress, and
embeds it all as JSON in scripts/dashboard_template.html. The output opens from
file:// with no server; math in answers renders when KaTeX can load from the CDN.
For a dashboard that updates while a run is in progress, use scripts/live_server.py.

Usage:
    python3 scripts/build_dashboard.py runs/<exam>/<run_id> [--output path.html]
"""

import argparse
import json
from datetime import datetime
from html import escape
from pathlib import Path

from analyze_run import compute_stats
from examlib import load_personas, load_run
from progress import compute_progress, load_activity

TEMPLATE = Path(__file__).with_name("dashboard_template.html")


def build_data(run_dir, final=False):
    """Everything the dashboard shows. `final` marks a finished run (the static build)."""
    run = load_run(run_dir)
    m = run["manifest"]
    cards = load_personas()
    started = datetime.fromisoformat(m["created"]).timestamp()
    return {
        "exam": m["exam"],
        "run": {"id": m["run_id"], "created": m["created"], "dir": m["run_dir"]},
        "students": [
            {
                "sid": s["sid"],
                "persona_id": s["persona_id"],
                "persona": cards.get(s["persona_id"], {"name": s["persona_id"]}),
                "answers": run["answers"][s["sid"]],
                "feedback": run["feedback"][s["sid"]],
                "grades": run["grades"][s["sid"]],
            }
            for s in m["students"]
        ],
        "stats": compute_stats(run),
        "issues": run["issues"],
        "recommendations": run["recommendations"],
        "progress": compute_progress(run, load_activity(started - 5), final=final),
        "generated": datetime.now().isoformat(timespec="seconds"),
    }


def render_html(data, live_api=None):
    """The template with the data embedded, or, with `live_api`, set up to poll that URL."""
    # "</" would end the <script> block early; "<\/" is the same string in JSON.
    payload = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    live = json.dumps({"api": live_api}) if live_api else "null"
    return (TEMPLATE.read_text()
            .replace("__TITLE__", escape(data["exam"]["title"]))
            .replace("__LIVE__", live)
            .replace("__DASHBOARD_DATA__", payload))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("run_dir")
    ap.add_argument("--output", help="default: <run_dir>/dashboard.html")
    args = ap.parse_args()

    data = build_data(args.run_dir, final=True)
    out = Path(args.output) if args.output else load_run(args.run_dir)["dir"] / "dashboard.html"
    out.write_text(render_html(data))
    print(out)


if __name__ == "__main__":
    main()
