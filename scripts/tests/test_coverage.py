"""Acceptance tests for the coverage gate, independent of Android/Gradle."""

import contextlib
import io
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from check_coverage import EXECUTION_DATA, REPORT, check_minimum, compare, read_report, require_artifacts
import run_coverage


def counts(line=(80, 100), branch=(80, 100)):
    return {"LINE": line, "BRANCH": branch}


class CoverageGateTest(unittest.TestCase):
    def setUp(self):
        self.output = contextlib.redirect_stdout(io.StringIO())
        self.output.__enter__()
        self.addCleanup(self.output.__exit__, None, None, None)

    def test_exactly_eighty_percent_passes(self):
        check_minimum(counts())

    def test_line_below_eighty_fails_even_when_display_rounds_up(self):
        with self.assertRaisesRegex(ValueError, "LINE.*below"):
            check_minimum(counts(line=(799999, 1000000)))

    def test_branch_below_eighty_fails_independently(self):
        with self.assertRaisesRegex(ValueError, "BRANCH.*below"):
            check_minimum(counts(branch=(79, 100)))

    def test_no_branches_is_not_a_minimum_failure(self):
        check_minimum(counts(branch=(0, 0)))

    def test_unchanged_or_increased_coverage_passes(self):
        compare({"a.kt": counts()}, {"a.kt": counts(line=(9, 10))}, ["a.kt"])

    def test_regression_above_eighty_fails(self):
        with self.assertRaisesRegex(ValueError, "LINE.*decreased"):
            compare({"a.kt": counts(line=(9, 10))},
                    {"a.kt": counts(line=(89, 100))}, ["a.kt"])

    def test_branch_regression_fails_independently(self):
        with self.assertRaisesRegex(ValueError, "BRANCH.*decreased"):
            compare({"a.kt": counts(branch=(9, 10))}, {"a.kt": counts()}, ["a.kt"])

    def test_compare_aggregates_only_the_same_changed_source_group(self):
        before = {"a.kt": counts(line=(9, 10)), "b.kt": counts(line=(8, 10)),
                  "untouched.kt": counts()}
        after = {"a.kt": counts(line=(8, 10)), "b.kt": counts(line=(9, 10)),
                 "new.kt": counts(line=(0, 100))}
        compare(before, after, ["a.kt", "b.kt"])

    def test_missing_baseline_or_current_source_fails(self):
        for before, after in [({}, {"a.kt": counts()}), ({"a.kt": counts()}, {})]:
            with self.subTest(before=before), self.assertRaisesRegex(ValueError, "Missing comparison"):
                compare(before, after, ["a.kt"])

    def test_zero_branch_denominator_and_no_changed_sources_are_explicit(self):
        compare({"a.kt": counts(branch=(0, 0))}, {"a.kt": counts()}, ["a.kt"])
        compare({}, {}, [])


class CoverageReportTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        (self.root / "example").mkdir()
        (self.root / "example/App.kt").write_text("class App")
        self.xml = self.root / "report.xml"
        self.report = ET.Element("report")
        ET.SubElement(self.report, "sessioninfo", id="test", start="1", dump="2")
        package = ET.SubElement(self.report, "package", name="example")
        self.source = ET.SubElement(package, "sourcefile", name="App.kt")
        for node in (self.report, self.source):
            ET.SubElement(node, "counter", type="LINE", missed="1", covered="9")
            ET.SubElement(node, "counter", type="BRANCH", missed="0", covered="2")

    def read(self):
        ET.ElementTree(self.report).write(self.xml)
        return read_report(self.xml, self.root)

    def test_realistic_report_has_source_and_total_counts(self):
        total, sources = self.read()
        self.assertEqual((9, 10), total["LINE"])
        self.assertEqual({"example/App.kt"}, sources.keys())

    def test_missing_and_malformed_xml_fail(self):
        with self.assertRaises(OSError):
            read_report(self.xml, self.root)
        self.xml.write_text("not XML")
        with self.assertRaises(ET.ParseError):
            read_report(self.xml, self.root)

    def test_missing_execution_session_fails(self):
        self.report.remove(self.report.find("sessioninfo"))
        with self.assertRaisesRegex(ValueError, "execution session"):
            self.read()

    def test_unreported_application_source_fails(self):
        (self.root / "example/Missing.kt").write_text("class Missing")
        with self.assertRaisesRegex(ValueError, "Missing application"):
            self.read()

    def test_totals_not_matching_sources_fail(self):
        self.source.find("counter").set("covered", "8")
        with self.assertRaisesRegex(ValueError, "totals differ"):
            self.read()

    def test_missing_line_or_zero_execution_data_fail(self):
        self.report.find("counter").set("covered", "0")
        with self.assertRaisesRegex(ValueError, "execution data"):
            self.read()

    def test_negative_counters_fail(self):
        self.source.find("counter").set("missed", "-1")
        with self.assertRaisesRegex(ValueError, "Negative"):
            self.read()


class CoverageRunnerTest(unittest.TestCase):
    def test_all_report_artifacts_are_required_and_nonempty(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            artifacts = [root / REPORT, root / REPORT.parent / "index.html", root / EXECUTION_DATA]
            for path in artifacts:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b"generated")
            require_artifacts(root)
            for path in artifacts:
                with self.subTest(path=path):
                    path.write_bytes(b"")
                    with self.assertRaisesRegex(ValueError, "Missing or empty"):
                        require_artifacts(root)
                    path.unlink()
                    with self.assertRaisesRegex(ValueError, "Missing or empty"):
                        require_artifacts(root)
                    path.write_bytes(b"generated")

    def test_push_uses_previous_main_and_initial_push_has_no_base(self):
        with tempfile.TemporaryDirectory() as temporary:
            event = Path(temporary) / "event.json"
            event.write_text('{"before": "' + "a" * 40 + '"}')
            with patch.object(run_coverage, "git", return_value="resolved") as git:
                self.assertEqual("resolved", run_coverage.resolve_base(event))
                git.assert_called_once_with("rev-parse", "a" * 40 + "^{commit}")
            event.write_text('{"before": "' + "0" * 40 + '"}')
            self.assertIsNone(run_coverage.resolve_base(event))

    def test_pr_fetches_latest_target_branch_not_event_snapshot(self):
        with tempfile.TemporaryDirectory() as temporary:
            event = Path(temporary) / "event.json"
            event.write_text('{"pull_request":{"base":{"ref":"main","sha":"old"}}}')
            with patch.object(run_coverage.subprocess, "run") as command, \
                    patch.object(run_coverage, "git", return_value="latest") as git:
                self.assertEqual("latest", run_coverage.resolve_base(event))
                self.assertIn("refs/heads/main", command.call_args.args[0])
                git.assert_called_once_with("rev-parse", "FETCH_HEAD")

    def test_failed_base_resolution_removes_stale_report_and_records_failure(self):
        original = Path.cwd()
        self.addCleanup(os.chdir, original)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            report = root / run_coverage.REPORT
            report.parent.mkdir(parents=True)
            report.write_text("stale coverage")
            with patch.object(run_coverage, "ROOT", root), \
                    patch.object(sys, "argv", ["run_coverage.py", "--base-ref", "missing"]), \
                    patch.object(run_coverage, "git", side_effect=ValueError("missing base")), \
                    contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as failure:
                run_coverage.main()
            self.assertEqual(1, failure.exception.code)
            self.assertFalse(report.exists())
            self.assertIn('"status": "failed"',
                          (root / "app/build/reports/coverage/comparison.json").read_text())


if __name__ == "__main__":
    unittest.main()
