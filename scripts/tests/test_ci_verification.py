import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ci_verification import APK, REPORTS, collect


BASE, HEAD, TESTED = ("a" * 40, "b" * 40, "c" * 40)
JUNIT = '<testsuite tests="2" failures="0" errors="0" skipped="1"><testcase/><testcase><skipped/></testcase></testsuite>'


class CIEvidenceTest(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.coverage = dict(head=TESTED, base=BASE, status="passed", regression="no comparable sources",
                             counters={"LINE": [80, 100], "BRANCH": [9, 10]})
        self.write(REPORTS / "coverage/comparison.json", json.dumps(self.coverage))
        self.write(REPORTS / "lint-results-debug.xml", '<issues><issue severity="Hint"/></issues>')
        self.write(APK, "apk")
        self.junit_paths = [Path(f"app/build/test-results/test{variant}UnitTest/TEST-Example.xml")
                            for variant in ("Debug", "Release")]
        for path in self.junit_paths:
            self.write(path, JUNIT)
        self.event = dict(number=7, pull_request=dict(head=dict(sha=HEAD), base=dict(sha=BASE)))
        self.env = dict(GITHUB_EVENT_PATH=str(self.root / "event.json"), GITHUB_EVENT_NAME="pull_request",
                        GITHUB_SHA=TESTED, GITHUB_REPOSITORY="example/project",
                        GITHUB_RUN_ID="42", GITHUB_RUN_ATTEMPT="2")

    def write(self, relative, text):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def collect(self, checkout=f"{TESTED} {BASE} {HEAD}\n"):
        self.write("event.json", json.dumps(self.event))
        with patch("ci_verification.subprocess.check_output", return_value=checkout):
            return collect(self.root, self.env)

    def test_pr_separates_checkout_from_head_and_summarizes_machine_reports(self):
        manifest = self.collect()
        self.assertEqual((manifest["tested_sha"], manifest["pr_head_sha"], manifest["parents"]),
                         (TESTED, HEAD, [BASE, HEAD]))
        self.assertEqual((manifest["run_id"], manifest["run_attempt"], manifest["pr_number"]), (42, 2, 7))
        counts = dict(tests=2, failures=0, errors=0, skipped=1)
        self.assertEqual(manifest["tests"], {"Debug": counts, "Release": counts})
        self.assertEqual(manifest["lint"], {"Hint": 1})
        self.assertEqual(manifest["coverage"]["counters"], self.coverage["counters"])
        self.assertEqual(manifest["apk_sha256"], "dd37c2d7274f7ea982cb83390c36918fee9ce8889073c44b68cdc00bdb8c3e04")

    def test_push_keeps_actual_parents_and_has_no_pr_head(self):
        self.env["GITHUB_EVENT_NAME"] = "push"
        self.event = dict(before=BASE, after=TESTED)
        manifest = self.collect(f"{TESTED} {BASE}\n")
        self.assertEqual(manifest["parents"], [BASE])
        self.assertIsNone(manifest["pr_number"])
        self.assertIsNone(manifest["pr_head_sha"])

    def test_coverage_and_checkout_must_match_event(self):
        with self.assertRaisesRegex(ValueError, "Checkout parents"):
            self.collect(f"{TESTED} {HEAD} {BASE}\n")
        self.write(REPORTS / "coverage/comparison.json", json.dumps(self.coverage | {"base": HEAD}))
        with self.assertRaisesRegex(ValueError, "different checkout or base"):
            self.collect()

    def test_missing_failed_and_all_skipped_junit_stop_manifest(self):
        (self.root / self.junit_paths[1]).unlink()
        with self.assertRaisesRegex(ValueError, "Missing Release JUnit XML"):
            self.collect()
        self.write(self.junit_paths[1], '<testsuite tests="1" failures="1"><testcase><failure/></testcase></testsuite>')
        with self.assertRaisesRegex(ValueError, "Release JUnit tests did not pass"):
            self.collect()
        self.write(self.junit_paths[1], '<testsuite tests="1" skipped="1"><testcase><skipped/></testcase></testsuite>')
        with self.assertRaisesRegex(ValueError, "none ran"):
            self.collect()

    def test_lint_warning_and_low_coverage_stop_manifest(self):
        lint = REPORTS / "lint-results-debug.xml"
        self.write(lint, '<issues><issue severity="Warning"/></issues>')
        with self.assertRaisesRegex(ValueError, "Android Lint reported errors or warnings"):
            self.collect()
        self.write(lint, "<issues/>")
        self.coverage["counters"]["BRANCH"] = [7, 10]
        self.write(REPORTS / "coverage/comparison.json", json.dumps(self.coverage))
        with self.assertRaisesRegex(ValueError, "BRANCH coverage is below 80%"):
            self.collect()
