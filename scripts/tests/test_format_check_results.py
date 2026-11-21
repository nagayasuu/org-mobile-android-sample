import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "format_check_results.py"
HEAD, BASE, MERGE = "a" * 40, "b" * 40, "c" * 40


class FormatCheckResultsTest(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)

    def write(self, name, data):
        path = self.root / name
        path.write_text(json.dumps(data), encoding="utf-8")
        return str(path)

    def cli(self, *args):
        return subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True,
                              text=True, encoding="utf-8", timeout=10)

    def test_review_shows_unconfirmed_and_omits_private_fields(self):
        report = self.write("summary.json", {
            "status": "unconfirmed", "revision": {"head": HEAD, "tracked_diff_sha256": "e" * 64},
            "command_exit_code": 0,
            "wall_seconds": 0.25, "command": ["private-arg"], "log": "private-log",
            "report_errors": [{"kind": "junit", "reason": "private-path"}],
            "lint": {"severities": {"Warning": 2}},
        })
        result = self.cli("--format", "review", "--check", "V1", report)
        self.assertEqual(result.returncode, 0, result.stderr)
        for value in ("| V1 |", HEAD, "e" * 64, "未確認", "JUnit レポート未確認", "Warning 2"):
            self.assertIn(value, result.stdout)
        self.assertNotIn("private-", result.stdout)
        self.assertNotIn(report, result.stdout)

    def test_rejects_local_pass_that_conflicts_with_report_counts(self):
        report = self.write("summary.json", {
            "status": "passed", "revision": {"head": HEAD}, "command_exit_code": 0,
            "wall_seconds": 1, "report_errors": [],
            "junit": {"tests": 1, "failures": 1, "errors": 0, "skipped": 0},
        })
        result = self.cli("--format", "pr", "--check", "V1", report)
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, "")

    def test_pr_uses_recorded_ci_attempt_and_verified_counts(self):
        counts = dict(tests=10, failures=0, errors=0, skipped=1)
        evidence = dict(schema_version=1, tested_sha=MERGE, parents=[BASE, HEAD],
                        apk_sha256="d" * 64, tests={"Debug": counts, "Release": counts},
                        lint={}, coverage={"LINE": [8, 10], "BRANCH": [0, 0]}, regression="passed")
        data = dict(repo="example/project", head=HEAD, base=BASE, pr=7, run=42, attempt=2,
                    done={"wait": 1.2, "artifacts": 2.1}, evidence=evidence)
        journal = self.write("journal.json", data)
        result = self.cli("--format", "pr", "--ci", "V2", journal)
        self.assertEqual(result.returncode, 0, result.stderr)
        for value in ("attempt 2", "https://github.com/example/project/actions/runs/42",
                      "Debug JUnit", "LINE 8/10", "d" * 64):
            self.assertIn(value, result.stdout)
        data["done"].pop("artifacts")
        result = self.cli("--format", "pr", "--ci", "V2", self.write("incomplete.json", data))
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, "")
