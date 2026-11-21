import argparse
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import ci_status
import git_preflight
import integration_timing
from integrate_pr import Integration, timing_path
from verify_local import checks_for


REPO, SHA = "example/project", "a" * 40
TIME = "2026-11-21T01:00:00Z"


class CiStatusTest(unittest.TestCase):
    def mock_response(self, *, event="pull_request", run_status="completed", conclusion="success",
                      artifacts=None, latest_attempt=2, pull_requests=None, opened=TIME):
        branch = "chore/verification" if event == "pull_request" else "main"
        run = dict(id=42, workflow_id=15, event=event, head_branch=branch, head_sha=SHA,
                   head_repository={"full_name": REPO}, run_attempt=2,
                   status=run_status, conclusion=conclusion, created_at=TIME,
                   pull_requests=pull_requests or [])
        job = dict(name="verify", id=71, conclusion=conclusion, started_at=TIME,
                   steps=[dict(name="Later", number=4, conclusion="failure"),
                          dict(name="Test", number=3, conclusion="failure")] if conclusion == "failure" else [])
        artifacts = artifacts or []
        responses = {
            "pulls/7": dict(number=7, created_at=opened, head=dict(sha=SHA, ref=branch, repo={"full_name": REPO}),
                            base=dict(ref="main", repo={"full_name": REPO})),
            ci_status.WORKFLOW: {"id": 15},
            f"{ci_status.WORKFLOW}/runs?branch=main&event=push&head_sha={SHA}&per_page=2":
                dict(total_count=1, workflow_runs=[{"id": 42}]),
            "actions/runs/42/attempts/2/jobs?per_page=100": dict(total_count=1, jobs=[job]),
            "actions/runs/42/artifacts?per_page=100": dict(total_count=len(artifacts), artifacts=artifacts),
        }
        run_reads = iter((run, {**run, "run_attempt": latest_attempt}))

        def read(repo, endpoint):
            self.assertEqual(repo, REPO)
            return next(run_reads) if endpoint == "actions/runs/42" else responses[endpoint]

        return patch("ci_status.github_api", side_effect=read)

    def test_pending_check_uses_link_and_ignores_old_attempt_artifact(self):
        old = dict(name="org-reader-debug", created_at="2026-11-21T00:59:59Z", expired=False)
        checks = json.dumps([dict(name="verify", bucket="pending",
                                  link=f"https://github.com/{REPO}/actions/runs/42/job/71")])
        with self.mock_response(run_status="in_progress", conclusion=None, artifacts=[old]), \
                patch("ci_status.subprocess.run", return_value=subprocess.CompletedProcess([], 8, checks, "")):
            result = ci_status.lookup(REPO, pr=7)
        self.assertEqual((result["status"], result["attempt"], result["apk"]), ("pending", 2, "missing"))

    def test_pr_without_checks_is_distinct_from_cli_failure(self):
        no_checks = subprocess.CompletedProcess([], 1, "", "no required checks reported on the 'test' branch\n")
        with self.mock_response(), patch("ci_status.subprocess.run", return_value=no_checks):
            self.assertEqual(ci_status.lookup(REPO, pr=7)["status"], "not-found")
        denied = subprocess.CompletedProcess([], 1, "", "HTTP 403")
        with self.mock_response(), patch("ci_status.subprocess.run", return_value=denied):
            with self.assertRaises(ValueError):
                ci_status.lookup(REPO, pr=7)

    def test_main_attempt_change_discards_older_evidence(self):
        with self.mock_response(event="push", latest_attempt=3):
            result = ci_status.lookup(REPO, sha=SHA)
        self.assertEqual(result["status"], "changed")
        self.assertNotIn("apk", result)

    def test_pr_run_for_different_or_earlier_pr_is_not_success(self):
        checks = [dict(name="verify", bucket="pass", link=f"https://github.com/{REPO}/actions/runs/42/job/71")]
        for options in (dict(pull_requests=[{"number": 8}]), dict(opened="2026-11-21T01:00:01Z")):
            with self.mock_response(**options), patch("ci_status.required_checks", return_value=checks):
                result = ci_status.lookup(REPO, pr=7)
            self.assertEqual(result["status"], "unconfirmed")
            self.assertNotIn("apk", result)

    def test_missing_and_ambiguous_run(self):
        for candidate_ids, state in (([], "not-found"), ([20, 21], "ambiguous")):
            listing = dict(total_count=len(candidate_ids), workflow_runs=[{"id": i} for i in candidate_ids])
            with patch("ci_status.github_api", return_value=listing) as api:
                self.assertEqual(ci_status.lookup(REPO, sha=SHA)["status"], state)
            api.assert_called_once()

    def test_failed_step_reports_and_log_preserve_existing_file(self):
        report = dict(name="android-reports", created_at=TIME, expired=False)
        checks = [dict(name="verify", bucket="fail", link=f"https://github.com/{REPO}/actions/runs/42/job/71")]
        with self.mock_response(conclusion="failure", artifacts=[report]), \
                patch("ci_status.required_checks", return_value=checks):
            result = ci_status.lookup(REPO, pr=7, diagnose=True)
        self.assertEqual(result["first_failed_step"]["name"], "Test")
        self.assertEqual(result["reports"], "available")
        with tempfile.TemporaryDirectory() as directory:
            log = Path(directory) / "failed.log"

            def download(args, *, stdout, **kwargs):
                self.assertEqual(args[-5:], ["--attempt", "2", "--job", "71", "--log-failed"])
                stdout.write(b"details\n")
                stdout.flush()
                return subprocess.CompletedProcess(args, 0)

            with patch("ci_status.subprocess.run", side_effect=download):
                self.assertEqual(ci_status.save_failure_log(result, log), "saved")
                with self.assertRaises(FileExistsError):
                    ci_status.save_failure_log(result, log)
            self.assertEqual(log.read_bytes(), b"details\n")


class LocalWorkflowTest(unittest.TestCase):
    def test_git_rename_changes_and_conflicts(self):
        self.assertEqual(git_preflight.changes("R  new\npath\0old\0MM both\0?? untracked\0UU conflict\0"),
                         dict(staged=["new\npath", "both"], unstaged=["both"],
                              untracked=["untracked"], conflicted=["conflict"]))

    def test_local_profile_never_substitutes_the_android_check(self):
        self.assertEqual(list(checks_for("android", []))[-1],
                         ("android", ["./gradlew", "--console=plain", "check", "assembleDebug"]))
        self.assertEqual([label for label, _ in checks_for("python", [])],
                         ["staged-diff", "worktree-diff", "documentation", "python"])
        self.assertEqual([label for label, _ in checks_for("docs", ["new.md"])],
                         ["staged-diff", "worktree-diff", "documentation", "explicit-documents"])


class IntegrationTimingTest(unittest.TestCase):
    def test_clock_union_missing_data_and_legacy_seconds(self):
        now = datetime(2026, 11, 21, tzinfo=timezone.utc)

        def attempt(step, state, start, end, seconds):
            return dict(step=step, status=state, elapsed_seconds=seconds,
                        started_utc=(now + timedelta(seconds=start)).isoformat(),
                        ended_utc=(now + timedelta(seconds=end)).isoformat() if end is not None else None)

        result = integration_timing.summarize({"prepare": 0.1, "create": 5}, [
            attempt("create", "completed", 0, 5, 5),
            attempt("wait", "failed", 2, 7, 5),
            attempt("wait", "interrupted", 8, 9, 5),
            attempt("wait", "unfinished", 10, None, None),
        ])
        self.assertEqual(result["observed_active_seconds"], 7)
        self.assertEqual(result["observed_attempt_seconds"], 15)
        self.assertIsNone(result["window_seconds"])
        self.assertIn(dict(step="prepare", status="unmeasured", elapsed=0.1), result["rows"])

    def test_step_records_failure_and_success_without_repeating_completed_step(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "journal.json"
            args = argparse.Namespace(repo=REPO, head=SHA, step="prepare", run=None, record_timing=True)
            work = Integration(path, args)
            with patch.object(work, "prepare", side_effect=ValueError("test")):
                with self.assertRaisesRegex(ValueError, "test"):
                    work.execute()
            self.assertFalse(path.exists())
            args.head = "b" * 40
            with self.assertRaisesRegex(ValueError, "differ"):
                work.execute()
            args.head = SHA

            def prepare():
                work.state = dict(repo=REPO, head=SHA, done={})

            with patch.object(work, "prepare", side_effect=prepare):
                self.assertEqual(work.execute(), "completed")
                self.assertEqual(work.execute(), "already completed")
            records = json.loads(timing_path(path).read_text())["attempts"]
            self.assertEqual([row["status"] for row in records], ["failed", "completed"])
            self.assertTrue(all(row["ended_utc"] for row in records))
