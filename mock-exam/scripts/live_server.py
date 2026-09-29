"""Serve dashboards that update while a run is in progress.

Every run under runs/ is listed at http://localhost:<port>/. A run's page polls
/api/<exam>/<run_id> every few seconds and redraws as students hand in, grades
arrive and the analysis finishes. Listens on localhost only and serves run data
only, never exam or solution files.

Usage:
    python3 scripts/live_server.py [--port 8131]
"""

import argparse
import json
import re
from datetime import datetime
from html import escape
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from build_dashboard import build_data, render_html
from examlib import ROOT

RUNS = ROOT / "runs"
NAME = re.compile(r"[\w.-]+")

INDEX = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><meta http-equiv="refresh" content="5">
<title>mock-exam · runs</title><style>
body {{ margin: 0; background: #0a0a0f; color: #ececf2; font: 15px/1.55 -apple-system, BlinkMacSystemFont, "Inter", system-ui, sans-serif; }}
main {{ max-width: 900px; margin: 0 auto; padding: 48px 16px; }}
h1 {{ letter-spacing: -.02em; }} .muted {{ color: #9090a4; }}
a.run {{ display: grid; grid-template-columns: 1fr auto; gap: 4px 16px; padding: 16px 18px; margin-top: 12px; border: 1px solid #262633;
  border-radius: 14px; background: #12121a; color: inherit; text-decoration: none; }}
a.run:hover {{ border-color: #ff5c93; }}
.mono {{ font-family: ui-monospace, "SF Mono", Menlo, monospace; font-size: 13px; }}
.live {{ color: #ff5c93; }} .done {{ color: #5fd49a; }}
</style></head><body><main><h1>Runs</h1><p class="muted">Newest first. Open a run to follow it live.</p>{rows}</main></body></html>"""


def list_runs():
    rows = []
    for manifest in sorted(RUNS.glob("*/*/manifest.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        d = manifest.parent
        m = json.loads(manifest.read_text())
        graded = len(list((d / "grades").glob("S*.json")))
        done = (d / "dashboard.html").exists()
        status = '<span class="done">finished</span>' if done else f'<span class="live">● live</span> · {graded}/{len(m["students"])} graded'
        rows.append(f'<a class="run" href="/run/{d.parent.name}/{d.name}"><b>{escape(m["exam"]["title"])}</b>'
                    f'<span class="mono">{status}</span><span class="mono muted">{d.parent.name}/{d.name}</span>'
                    f'<span class="muted">{len(m["students"])} students · {escape(m["created"])}</span></a>')
    return INDEX.format(rows="".join(rows) or '<p class="muted">No runs yet.</p>')


def run_dir(exam, run_id):
    if not (NAME.fullmatch(exam) and NAME.fullmatch(run_id)):
        return None
    d = RUNS / exam / run_id
    return d if (d / "manifest.json").exists() else None


class Handler(BaseHTTPRequestHandler):
    def send(self, status, body, content_type):
        data = body.encode()
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        parts = [p for p in self.path.split("?")[0].split("/") if p]
        if not parts:
            return self.send(200, list_runs(), "text/html; charset=utf-8")
        if len(parts) == 3 and parts[0] in ("run", "api") and (d := run_dir(parts[1], parts[2])):
            data = build_data(d)
            if parts[0] == "api":
                return self.send(200, json.dumps(data, ensure_ascii=False), "application/json")
            return self.send(200, render_html(data, live_api=f"/api/{parts[1]}/{parts[2]}"), "text/html; charset=utf-8")
        self.send(404, "Not found", "text/plain")

    def log_message(self, *args):
        pass


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--port", type=int, default=8131)
    args = ap.parse_args()
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print(f"Live dashboards at http://localhost:{args.port}/  ({datetime.now():%H:%M:%S}, Ctrl+C to stop)", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
