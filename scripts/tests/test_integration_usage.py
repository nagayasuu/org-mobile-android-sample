"""Exercise phase attribution with synthetic Codex sessions and timing ledgers."""

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "integration_timing.py"


def utc(second):
    return f"2026-11-21T00:00:{second:02d}Z"


def response(second, identity, amount, thread="author"):
    return dict(timestamp=utc(second), type="token_usage_record", payload=dict(
        thread_id=thread, response_id=identity,
        usage=dict(input_tokens=amount, cached_input_tokens=amount // 2, output_tokens=1)))


class IntegrationUsageTest(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.identity = dict(repo="example/project", head="a" * 40)
        self.write("journal.json", dict(self.identity, done={"wait": 10, "artifacts": 10}))
        attempts = [dict(step=step, status="completed", started_utc=utc(start),
                         ended_utc=utc(start + 10), elapsed_seconds=10)
                    for step, start in (("wait", 10), ("artifacts", 20))]
        self.write("journal.json.timing.json", dict(self.identity, attempts=attempts))
        self.manifest = dict(self.identity, actors_complete=True,
                             actors=[dict(id="primary", events="session.jsonl")])

    def write(self, name, data):
        (self.root / name).write_text(json.dumps(data), encoding="utf-8")

    def session(self, *events, thread="author", filename="session.jsonl"):
        metadata = dict(timestamp=utc(0), type="session_meta", payload=dict(id=thread))
        tail = dict(timestamp=utc(40), type="event_msg", payload=dict(secret="PRIVATE TEXT"))
        (self.root / filename).write_text(
            "".join(json.dumps(event) + "\n" for event in (metadata, *events, tail)), encoding="utf-8")

    def run_report(self, output="json"):
        self.write("manifest.json", self.manifest)
        return subprocess.run([sys.executable, SCRIPT, "--state", self.root / "journal.json",
                               "--usage-manifest", self.root / "manifest.json", "--format", output],
                              text=True, capture_output=True, check=False)

    def read_report(self):
        result = self.run_report()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("PRIVATE TEXT", result.stdout)
        self.assertNotIn("session.jsonl", result.stdout)
        return json.loads(result.stdout)

    def test_default_command_windows_count_unique_responses_once(self):
        self.session(response(10, "before", 50), response(16, "one", 12),
                     response(20, "boundary", 8), response(21, "one", 12),
                     response(22, "child", 80, thread="child"), response(25, "two", 7))
        report = self.read_report()
        rows = {row["step"]: row["usage"] for row in report["rows"]}
        self.assertIsNone(rows["prepare"])
        self.assertEqual(rows["wait"]["observed"], dict(responses=2, input_tokens=20,
                         cached_input_tokens=10, output_tokens=2, uncached_input_tokens=10, total_tokens=22))
        self.assertEqual(rows["artifacts"]["observed"]["total_tokens"], 8)
        self.assertIsNone(rows["wait"]["total"])
        self.assertIsNone(report["usage"]["unassigned"])
        self.assertIn("| wait #1 | command | 0/1 | 2 | 20 | 10 | 2 | 22 | — |", self.run_report("markdown").stdout)

    def test_explicit_phase_reports_zero_or_partial_without_inventing_a_total(self):
        self.session(response(4, "outside", 11))
        row = next(row for row in self.read_report()["rows"] if row["step"] == "wait")
        self.assertEqual(row["usage"]["observed"]["total_tokens"], 0)
        self.assertIsNone(row["usage"]["total"])
        self.manifest["windows"] = [dict(step="wait", attempt=1, start=utc(5), end=utc(20),
                                         complete_actors=["primary"])]
        row = next(row for row in self.read_report()["rows"] if row["step"] == "wait")
        self.assertEqual(row["usage"]["total"]["total_tokens"], 0)
        self.manifest["actors"].append(dict(id="approval", events=None))
        row = next(row for row in self.read_report()["rows"] if row["step"] == "wait")
        self.assertEqual(row["usage"]["complete_actors"], 1)
        self.assertEqual(row["usage"]["expected_actors"], 2)
        self.assertEqual(row["usage"]["actors"][1]["missing_reason"], "missing-log")
        self.assertIsNone(row["usage"]["total"])

    def test_overlapping_windows_put_usage_in_unassigned(self):
        self.session(response(21, "overlap", 10))
        self.manifest["windows"] = [dict(step="wait", attempt=1, start=utc(5), end=utc(23),
                                         complete_actors=["primary"])]
        report = self.read_report()
        self.assertEqual(report["usage"]["unassigned"]["total_tokens"], 11)
        self.assertTrue(all(row["usage"] is None or row["usage"]["total"] is None for row in report["rows"]))

    def test_conflicting_usage_is_rejected_without_log_contents(self):
        self.session(response(12, "private-id", 11), response(13, "private-id", 9))
        result = self.run_report()
        self.assertEqual(result.returncode, 2)
        self.assertFalse(result.stdout)
        self.assertNotIn("private-id", result.stderr)
        self.assertNotIn("session.jsonl", result.stderr)

    def test_sub_microsecond_event_is_rejected_instead_of_changing_its_window(self):
        event = response(20, "just-after-the-boundary", 10)
        event["timestamp"] = "2026-11-21T00:00:20.000000001Z"
        self.session(event)
        result = self.run_report()
        self.assertEqual(result.returncode, 2)
        self.assertFalse(result.stdout)

    def test_multiple_threads_are_added_once_and_must_have_distinct_responses(self):
        self.session(response(15, "shared", 10))
        self.manifest["actors"].append(dict(id="review", events="second.jsonl"))
        self.manifest["windows"] = [dict(step="wait", attempt=1, start=utc(5), end=utc(20),
                                         complete_actors=["primary", "review"])]
        self.session(response(15, "second-response", 3, thread="second"), thread="second", filename="second.jsonl")
        row = next(row for row in self.read_report()["rows"] if row["step"] == "wait")
        self.assertEqual(row["usage"]["total"]["total_tokens"], 15)
        self.session(response(15, "shared", 10, thread="second"), thread="second", filename="second.jsonl")
        self.assertEqual(self.run_report().returncode, 2)
