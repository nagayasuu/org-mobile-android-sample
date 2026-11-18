import argparse
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from integrate_pr import Integration, STEPS

HEAD, BASE, MERGED = ("a" * 40, "b" * 40, "c" * 40)
REPO, BRANCH = "example/project", "test/integration"


class IntegrationTest(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.path = Path(directory.name) / "journal.json"
        self.args = argparse.Namespace(repo=REPO, step="prepare", apply=False,
                                       head=None, run=None, timeout=30, title="test: 統合する", body_file=self.path.with_name("body"))
        self.args.body_file.write_text("検証を確認する。")
        self.work = Integration(self.path, self.args)

    def at(self, step):
        self.args.step = step
        self.work.state = dict(repo=REPO, head=HEAD, base=BASE, branch=BRANCH,
                               workflow=15, pr=7, run=42, attempt=1, merged=MERGED,
                               main_run=44, main_attempt=1,
                               done=dict.fromkeys(STEPS[:STEPS.index(step)], 0.1))

    def pr(self, merged=False):
        repo = {"full_name": REPO}
        return dict(number=7, head=dict(sha=HEAD, ref=BRANCH, repo=repo),
                    base=dict(ref="main", repo=repo), state="closed" if merged else "open",
                    draft=False, merged=merged, merge_commit_sha=MERGED if merged else None)

    def test_write_permission_order_and_completed_step(self):
        self.at("create")
        with patch.object(self.work, "create") as create:
            with self.assertRaisesRegex(ValueError, "--apply"):
                self.work.execute()
            self.args.step = "merge"
            with self.assertRaisesRegex(ValueError, "previous"):
                self.work.execute()
            self.args.step = "create"
            self.args.apply = True
            self.assertEqual(self.work.execute(), "completed")
            self.assertEqual(Integration(self.path, self.args).execute(), "already completed")
            create.assert_called_once()

    def test_changed_ref_stops_before_pr_creation(self):
        self.at("create")
        self.args.apply = True
        with patch.object(self.work, "branch_sha", return_value=BASE), patch.object(self.work, "api") as api:
            with self.assertRaisesRegex(ValueError, "Remote head changed"):
                self.work.execute()
            api.assert_not_called()
        self.assertFalse(self.path.exists())

    def test_interrupted_create_reconciles_without_resending(self):
        self.at("create")
        self.args.apply = True
        with patch.object(self.work, "live_refs"), patch.object(self.work, "api", side_effect=[[], OSError()]):
            with self.assertRaises(OSError):
                self.work.execute()
        resumed = Integration(self.path, self.args)
        with patch.object(resumed, "live_refs"), patch.object(resumed, "api", return_value=[]) as api:
            with self.assertRaisesRegex(ValueError, "unresolved"):
                resumed.execute()
            api.assert_called_once()
        with patch.object(resumed, "live_refs"), patch.object(resumed, "api", return_value=[self.pr()]) as api:
            self.assertEqual(resumed.execute(), "completed")
            api.assert_called_once()
        self.assertEqual(json.loads(self.path.read_text())["pr"], 7)

    def test_failed_ci_cannot_advance(self):
        self.at("wait")
        self.args.run = 42
        with patch.object(self.work, "live_refs"), patch.object(self.work, "pr", return_value=self.pr()), \
                patch.object(self.work, "run"), patch("integrate_pr.command", side_effect=ValueError("CI failed")):
            with self.assertRaisesRegex(ValueError, "CI failed"):
                self.work.execute()
        self.assertNotIn("wait", self.work.state["done"])

    def test_replaced_ci_attempt_stops_merge(self):
        self.at("merge")
        self.args.apply = True
        with patch.object(self.work, "pr", return_value=self.pr()), patch.object(self.work, "protection"), \
                patch.object(self.work, "success", return_value=(2, "2026-11-18T00:00:00Z")), patch.object(self.work, "api") as api:
            with self.assertRaisesRegex(ValueError, "attempt changed"):
                self.work.execute()
            api.assert_not_called()

    def test_interrupted_merge_recovers_only_matching_commit(self):
        self.at("merge")
        self.args.apply = True
        self.work.state["merge_pending"] = True
        tree = "d" * 40
        with patch.object(self.work, "pr", return_value=self.pr(True)), \
                patch.object(self.work, "api", return_value={"parents": [{"sha": BASE}], "tree": {"sha": tree}}) as api, \
                patch("integrate_pr.command", return_value=tree):
            self.assertEqual(self.work.execute(), "completed")
            api.assert_called_once_with(f"git/commits/{MERGED}")
        self.assertEqual(self.work.state["merged"], MERGED)

    def test_cleanup_stops_on_branch_advance(self):
        self.at("cleanup")
        self.args.apply = True
        with patch.object(self.work, "pr", return_value=self.pr(True)), \
                patch.object(self.work, "success", return_value=(1, "2026-11-18T00:00:00Z")), \
                patch.object(self.work, "api", return_value=[]), \
                patch("integrate_pr.command", return_value=f"{BASE}\trefs/heads/{BRANCH}") as command:
            with self.assertRaisesRegex(ValueError, "branch advanced"):
                self.work.execute()
            command.assert_called_once()

    def test_artifacts_reject_different_tested_tree(self):
        self.at("artifacts")

        def download(*args):
            directory = Path(args[-1])
            if directory.name == "android-reports":
                (directory / "coverage").mkdir(parents=True)
                (directory / "coverage/comparison.json").write_text(
                    json.dumps(dict(status="passed", base=BASE, head=MERGED)))
            return "d" * 40

        commit = {"parents": [{"sha": BASE}, {"sha": HEAD}], "tree": {"sha": "e" * 40}}
        with patch.object(self.work, "live_refs"), patch.object(self.work, "pr"), \
                patch.object(self.work, "current_evidence"), patch.object(self.work, "artifact_ids"), \
                patch.object(self.work, "api", return_value=commit), \
                patch("integrate_pr.command", side_effect=download):
            with self.assertRaisesRegex(ValueError, "different content"):
                self.work.execute()
        self.assertNotIn("artifacts", self.work.state["done"])

    def test_artifacts_record_matching_reports_and_apk(self):
        self.at("artifacts")

        def download(*args):
            directory = Path(args[-1])
            directory.mkdir()
            if directory.name == "android-reports":
                (directory / "coverage").mkdir()
                (directory / "coverage/comparison.json").write_text(json.dumps(dict(
                    status="passed", base=BASE, head=HEAD, counters={"LINE": [8, 10], "BRANCH": [0, 0]})))
                for variant in ("Debug", "Release"):
                    report = directory / f"tests/test{variant}UnitTest/index.html"
                    report.parent.mkdir(parents=True)
                    report.write_text("test report")
                (directory / "lint-results-debug.xml").write_text("<issues/>")
            else:
                (directory / "app-debug.apk").write_bytes(b"apk")

        with patch.object(self.work, "live_refs"), patch.object(self.work, "pr"), \
                patch.object(self.work, "current_evidence"), \
                patch.object(self.work, "artifact_ids", return_value={"android-reports": 5, "org-reader-debug": 6}), \
                patch("integrate_pr.command", side_effect=download), patch("sys.stderr"):
            self.assertEqual(self.work.execute(), "completed")
        evidence = json.loads(self.path.read_text())["evidence"]
        self.assertEqual(evidence["tested_sha"], HEAD)
        self.assertEqual(len(evidence["apk_sha256"]), 64)

    def test_stale_artifact_is_rejected(self):
        self.at("artifacts")
        artifacts = [dict(name="android-reports", id=1, expired=False, created_at="2026-11-18T00:00:00Z")]
        with patch.object(self.work, "api", return_value={"total_count": 1, "artifacts": artifacts}):
            with self.assertRaisesRegex(ValueError, "predates"):
                self.work.artifact_ids("2026-11-18T00:05:00Z")

    def test_conflicting_explicit_target_stops_even_on_resume(self):
        self.at("merge")
        self.work.save()
        self.args.repo = "example/other"
        with self.assertRaisesRegex(ValueError, "--repo differs"):
            Integration(self.path, self.args)
        self.args.repo = REPO
        self.args.head = BASE
        with self.assertRaisesRegex(ValueError, "--head differs"):
            Integration(self.path, self.args)
        self.args.head = HEAD
        self.args.step = "wait"
        self.args.run = 43
        with self.assertRaisesRegex(ValueError, "--run differs"):
            Integration(self.path, self.args).execute()

    def test_invalid_journal_shape_preserves_original(self):
        self.path.write_text("[]")
        with self.assertRaisesRegex(ValueError, "JSON object"):
            Integration(self.path, self.args)
        self.assertEqual(self.path.read_text(), "[]")
