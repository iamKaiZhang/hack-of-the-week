"""Tests for the deterministic parts of the pipeline: run preparation, statistics,
the student guard hook and the dashboard build. The agents themselves are not tested
here; tests/fixtures/demo-run stands in for their output (hand-written, synthetic)."""

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from analyze_run import compute_stats  # noqa: E402
from examlib import load_personas, load_run  # noqa: E402
from prepare_run import materials_for  # noqa: E402

FIXTURE = "tests/fixtures/demo-run"
GUARD = ROOT / ".claude" / "hooks" / "guard_student.py"


def sweep_test_runs():
    """Remove empty run folders the tests left behind. The iCloud-synced Desktop sometimes
    restores a just-deleted folder's empty subfolders; without a manifest they are debris."""
    for d in ROOT.glob("runs/*/*_unittest*"):
        if not (d / "manifest.json").exists() and not any(p.is_file() for p in d.rglob("*")):
            shutil.rmtree(d, ignore_errors=True)


setUpModule = tearDownModule = sweep_test_runs


class PersonaCardsTest(unittest.TestCase):
    def test_cards_are_complete(self):
        for pid, card in load_personas().items():
            with self.subTest(persona=pid):
                self.assertEqual(card.get("id"), pid)
                for key in ("name", "age", "program", "level", "background", "focus", "ability", "languages", "interests"):
                    self.assertIn(key, card)
                self.assertIn(card["level"], ("bachelor", "master", "phd"))
                self.assertIn(card.get("ability"), ("top 10%", "above median", "median", "below median", "bottom quarter"))
                self.assertTrue(0 <= card["preparation"]["coverage"] <= 1)
                self.assertIn(card["preparation"]["exercises"], ("none", "some", "all"))
                self.assertIn(card["exam_behavior"]["speed"], ("slow", "average", "fast"))


class MaterialsTest(unittest.TestCase):
    MATERIALS = [{"path": "w1", "week": 1}, {"path": "w2", "week": 2}, {"path": "w3", "week": 3}, {"path": "formulas"}]

    def pick(self, coverage):
        return materials_for({"preparation": {"coverage": coverage}}, self.MATERIALS)

    def test_coverage_cuts_by_week(self):
        self.assertEqual(self.pick(1.0), ["w1", "w2", "w3", "formulas"])
        self.assertEqual(self.pick(0.75), ["w1", "w2", "formulas"])
        self.assertEqual(self.pick(0.6), ["w1", "formulas"])

    def test_unweeked_materials_always_given(self):
        self.assertEqual(self.pick(0.0), ["formulas"])


class PrepareRunTest(unittest.TestCase):
    def test_creates_run_with_anonymous_ids(self):
        out = subprocess.run(
            [sys.executable, "scripts/prepare_run.py", "--exam", "example", "--personas", "lena,sofia,luca", "--label", "unittest"],
            cwd=ROOT, capture_output=True, text=True, check=True,
        )
        manifest = json.loads(out.stdout)
        run_dir = ROOT / manifest["run_dir"]
        try:
            self.assertEqual([s["sid"] for s in manifest["students"]], ["S01", "S02", "S03"])
            self.assertEqual({s["persona_id"] for s in manifest["students"]}, {"lena", "sofia", "luca"})
            sofia = next(s for s in manifest["students"] if s["persona_id"] == "sofia")
            self.assertEqual(len(sofia["materials"]), 1)  # coverage 0.6 of a 3-week course
            for sub in ("answers", "feedback", "grades", "analysis"):
                self.assertTrue((run_dir / sub).is_dir())
            self.assertTrue((run_dir / "manifest.json").exists())
        finally:
            shutil.rmtree(run_dir)

    def test_unknown_persona_fails(self):
        out = subprocess.run([sys.executable, "scripts/prepare_run.py", "--exam", "example", "--personas", "nobody"],
                             cwd=ROOT, capture_output=True, text=True)
        self.assertNotEqual(out.returncode, 0)
        self.assertIn("Unknown persona", out.stderr)


class StatsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.stats = compute_stats(load_run(FIXTURE))
        cls.q = {q["qid"]: q for q in cls.stats["questions"]}

    def test_overall(self):
        o = self.stats["overall"]
        self.assertEqual(o["n_graded"], 8)
        self.assertAlmostEqual(o["mean_pct"], 128 / 8 / 25)  # totals in the fixture sum to 128
        self.assertEqual(o["share_ran_out"], 0.5)
        self.assertEqual(o["median_minutes"], 29.5)

    def test_points_capped_at_config_maximum(self):
        for st in self.stats["students"]:
            for qid, pts in st["q_pts"].items():
                self.assertLessEqual(pts, self.q[qid]["points"])

    def test_time_ignores_blank_answers(self):
        # Q3 was attempted by 6 students: 8 + 7 + 8 + 7 + 9 + 6 minutes.
        self.assertAlmostEqual(self.q["Q3"]["mean_minutes"], 45 / 6)
        self.assertEqual(self.q["Q3"]["status_counts"].get("blank"), 2)

    def test_ambiguity_flags(self):
        self.assertEqual(len(self.q["Q2c"]["ambiguity_flags"]), 4)
        self.assertEqual(len(self.q["Q1"]["ambiguity_flags"]), 2)


class GuardTest(unittest.TestCase):
    def run_guard(self, agent_type, tool, path):
        event = {"agent_type": agent_type, "tool_name": tool, "tool_input": {"file_path": path}, "cwd": str(ROOT)}
        return subprocess.run([sys.executable, str(GUARD)], input=json.dumps(event), capture_output=True, text=True).returncode

    def test_student_reads(self):
        self.assertEqual(self.run_guard("student", "Read", "exams/example/exam.pdf"), 0)
        self.assertEqual(self.run_guard("student", "Read", "materials/example/week1-strategic-games.md"), 0)
        self.assertEqual(self.run_guard("student", "Read", "exams/example/solution.tex"), 2)
        self.assertEqual(self.run_guard("student", "Read", str(ROOT / "exams/example/Rubric-final.pdf")), 2)
        self.assertEqual(self.run_guard("student", "Read", "runs/example/r1/answers/S02.json"), 2)
        self.assertEqual(self.run_guard("student", "Read", "/etc/hosts"), 2)

    def test_student_writes(self):
        self.assertEqual(self.run_guard("student", "Write", "runs/example/r1/answers/S01.json"), 0)
        self.assertEqual(self.run_guard("student", "Write", "runs/example/r1/feedback/S01.json"), 0)
        self.assertEqual(self.run_guard("student", "Write", "runs/example/r1/grades/S01.json"), 2)
        self.assertEqual(self.run_guard("student", "Edit", "exams/example/exam.tex"), 2)

    def test_other_agents_untouched(self):
        self.assertEqual(self.run_guard("grader", "Read", "exams/example/solution.tex"), 0)
        self.assertEqual(self.run_guard(None, "Read", "exams/example/solution.tex"), 0)


class SeatedGuardTest(unittest.TestCase):
    """A student seated in a run may read only its card, its materials, and then the exam."""

    AGENT = "unittest-guard-agent"

    @classmethod
    def setUpClass(cls):
        out = subprocess.run([sys.executable, "scripts/prepare_run.py", "--exam", "example", "--personas", "lena,luca", "--label", "unittest-guard"],
                             cwd=ROOT, capture_output=True, text=True, check=True)
        cls.m = json.loads(out.stdout)
        cls.lena = next(s for s in cls.m["students"] if s["persona_id"] == "lena")
        cls.luca = next(s for s in cls.m["students"] if s["persona_id"] == "luca")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(ROOT / cls.m["run_dir"])
        (ROOT / "runs" / ".agents" / f"{cls.AGENT}.json").unlink(missing_ok=True)
        log = ROOT / "runs" / "activity.jsonl"
        if log.exists():
            log.write_text("".join(l for l in log.read_text().splitlines(keepends=True) if cls.AGENT not in l))

    def run_guard(self, tool, path):
        event = {"agent_type": "student", "agent_id": self.AGENT, "tool_name": tool, "tool_input": {"file_path": path}, "cwd": str(ROOT)}
        return subprocess.run([sys.executable, str(GUARD)], input=json.dumps(event), capture_output=True, text=True).returncode

    def test_study_before_the_exam(self):
        run_dir, sid = self.m["run_dir"], self.lena["sid"]
        self.assertEqual(self.run_guard("Read", "personas/lena.toml"), 0)                         # seats the agent
        self.assertEqual(self.run_guard("Read", "exams/example/exam.pdf"), 2)                     # has not studied yet
        self.assertEqual(self.run_guard("Read", "materials/example/week3-mixed-strategies.md"), 2)  # beyond coverage 0.75
        self.assertEqual(self.run_guard("Read", "personas/luca.toml"), 2)
        self.assertEqual(self.run_guard("Read", "exams/example/solution.tex"), 2)
        for path in self.lena["materials"]:
            self.assertEqual(self.run_guard("Read", path), 0)
        self.assertEqual(self.run_guard("Read", "exams/example/exam.pdf"), 0)                     # studied: exam handed out
        self.assertEqual(self.run_guard("Read", self.lena["materials"][-1]), 2)                  # closed book: materials put away
        self.assertEqual(self.run_guard("Read", "exams/example/exam.toml"), 2)
        self.assertEqual(self.run_guard("Write", f"{run_dir}/answers/{sid}.json"), 0)
        self.assertEqual(self.run_guard("Write", f"{run_dir}/answers/{self.luca['sid']}.json"), 2)  # another student's sheet


class ProgressTest(unittest.TestCase):
    """Stages inferred from a half-finished copy of the demo run plus synthetic activity."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.dir = self.tmp / "run"
        shutil.copytree(ROOT / FIXTURE, self.dir)
        for f in ("grades/S02.json", "grades/S03.json", "feedback/S03.json", "grades/S04.json", "feedback/S04.json",
                  "answers/S04.json", "grades/S05.json", "feedback/S05.json", "answers/S05.json",
                  "analysis/feedback.json", "analysis/recommendations.json"):
            (self.dir / f).unlink()
        rd = FIXTURE  # the manifest's run_dir, which agents' paths contain
        self.events = [
            {"t": 1, "agent_id": "g2", "agent_type": "grader", "tool": "Read", "target": f"{rd}/answers/S02.json"},
            {"t": 2, "agent_id": "s4", "agent_type": "student", "tool": "Read", "target": "personas/jonas.toml"},
            {"t": 3, "agent_id": "s4", "agent_type": "student", "tool": "Read", "target": "exams/example/exam.pdf"},
            {"t": 4, "agent_id": "s5", "agent_type": "student", "tool": "Read", "target": "personas/mei.toml"},
            {"t": 5, "agent_id": "s5", "agent_type": "student", "tool": "Read", "target": "materials/example/week1-strategic-games.md"},
            {"t": 6, "agent_id": "s5", "agent_type": "student", "tool": "Read", "target": "exams/example/exam.pdf", "blocked": True},
        ]

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_stages_and_phases(self):
        from progress import compute_progress
        p = compute_progress(load_run(self.dir), self.events)
        stage = {s["sid"]: s["stage"] for s in p["students"]}
        self.assertEqual(stage["S01"], "graded")
        self.assertEqual(stage["S02"], "grading")    # handed in, grader has opened the sheet
        self.assertEqual(stage["S03"], "feedback")   # answers written, feedback not yet
        self.assertEqual(stage["S04"], "sitting")    # has read the exam
        self.assertEqual(stage["S05"], "studying")   # materials only; the exam attempt was blocked
        self.assertEqual(next(s for s in p["students"] if s["sid"] == "S05")["last"]["action"], "blocked: Read exam.pdf")
        phases = {ph["key"]: ph for ph in p["phases"]}
        self.assertEqual((phases["sit"]["done"], phases["sit"]["state"]), (5, "active"))
        self.assertEqual((phases["grade"]["done"], phases["grade"]["state"]), (4, "active"))
        self.assertEqual(phases["analyze"]["state"], "pending")
        self.assertFalse(p["complete"])

    def test_students_without_grades_marked_once_analysis_starts(self):
        from progress import compute_progress
        (self.dir / "analysis" / "stats.json").write_text("{}")
        p = compute_progress(load_run(self.dir), self.events)
        self.assertEqual({s["sid"]: s["stage"] for s in p["students"]}["S04"], "no result")


class LiveServerTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import threading
        from http.server import ThreadingHTTPServer
        from live_server import Handler
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        cls.base = f"http://127.0.0.1:{cls.server.server_address[1]}"
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()
        out = subprocess.run([sys.executable, "scripts/prepare_run.py", "--exam", "example", "--personas", "lena,luca", "--label", "unittest-live"],
                             cwd=ROOT, capture_output=True, text=True, check=True)
        cls.manifest = json.loads(out.stdout)

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        shutil.rmtree(ROOT / cls.manifest["run_dir"])

    def get(self, path):
        import urllib.error
        import urllib.request
        try:
            with urllib.request.urlopen(self.base + path) as r:
                return r.status, r.read().decode()
        except urllib.error.HTTPError as e:
            e.close()
            return e.code, ""

    def test_index_lists_run(self):
        status, body = self.get("/")
        self.assertEqual(status, 200)
        self.assertIn(self.manifest["run_id"], body)

    def test_api_and_live_page(self):
        path = f'example/{self.manifest["run_id"]}'
        status, body = self.get(f"/api/{path}")
        self.assertEqual(status, 200)
        data = json.loads(body)
        self.assertEqual([s["stage"] for s in data["progress"]["students"]], ["waiting", "waiting"])
        status, html = self.get(f"/run/{path}")
        self.assertEqual(status, 200)
        self.assertIn(f'window.MOCK_EXAM_LIVE = {{"api": "/api/{path}"}}', html)

    def test_rejects_unknown_and_traversal(self):
        for path in ("/api/example/nope", "/api/..%2F..%2Fexams/example", "/run/../exams", "/exams/example/solution.tex"):
            self.assertEqual(self.get(path)[0], 404, path)


class DashboardTest(unittest.TestCase):
    def test_builds_self_contained_html(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "dashboard.html"
            subprocess.run([sys.executable, "scripts/build_dashboard.py", FIXTURE, "--output", str(out)],
                           cwd=ROOT, capture_output=True, text=True, check=True)
            html = out.read_text()
        self.assertNotIn("__DASHBOARD_DATA__", html)
        data = html.split('<script id="data" type="application/json">', 1)[1].split("</script>", 1)[0]
        payload = json.loads(data)
        self.assertEqual(len(payload["students"]), 8)
        self.assertEqual(payload["stats"]["overall"]["n_graded"], 8)


if __name__ == "__main__":
    unittest.main()
