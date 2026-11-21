import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "run_check.py"


class RunCheckComparisonTest(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.git("init", "-q")
        (self.root / "tracked").write_text("base")
        self.git("add", "tracked")
        self.git("-c", "user.name=Test", "-c", "user.email=test@example.com",
                 "commit", "-qm", "test input")
        self.context = self.root / "conditions"
        self.context.write_text("input and environment v1")

    def git(self, *args):
        subprocess.run(["git", *args], cwd=self.root, check=True, capture_output=True)

    def check(self, code, *options):
        return subprocess.run([sys.executable, str(SCRIPT), "--context-file", str(self.context),
                               *options, "--", sys.executable, "-c", code],
                              cwd=self.root, capture_output=True, text=True, timeout=10)

    def compare(self, code, record):
        result = self.check(code, "--compare-only", record)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)["records"][0]

    def test_comparison_finds_failures_and_successes_without_running(self):
        code = "from pathlib import Path; p=Path('attempts'); p.write_text('run'); raise SystemExit(7)"
        failed = self.check(code, "--output-dir", "failed")
        self.assertEqual(failed.returncode, 7, failed.stderr)
        (self.root / "attempts").unlink()
        previous = self.compare(code, "failed/summary.json")
        self.assertEqual(previous["status"], "previous-failure")
        self.assertEqual(previous["log"], "failed/command.log")
        self.assertFalse((self.root / "attempts").exists())

        success = self.check("pass", "--output-dir", "passed")
        self.assertEqual(success.returncode, 0, success.stderr)
        self.assertEqual(self.compare("pass", "passed/summary.json")["status"], "reuse-candidate")
        self.assertEqual(self.compare("print(1)", "passed/summary.json")["status"], "different-conditions")
        self.context.write_text("input and environment v2")
        self.assertEqual(self.compare("pass", "passed/summary.json")["status"], "different-conditions")

    def test_changed_or_unrecorded_conditions_cannot_be_reused(self):
        changed = "from pathlib import Path; Path('tracked').write_text('changed')"
        result = self.check(changed, "--output-dir", "changed")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.compare(changed, "changed/summary.json")["status"], "insufficient-record")

        (self.root / "older.json").write_text(json.dumps({"status": "passed"}))
        self.assertEqual(self.compare("pass", "older.json")["status"], "insufficient-record")
