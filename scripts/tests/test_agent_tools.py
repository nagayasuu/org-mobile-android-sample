"""CLI acceptance tests with public synthetic documents and reports."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


SCRIPTS = Path(__file__).resolve().parents[1]


class AgentToolsTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)

    def write(self, name, body):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")
        return path

    def docs(self, *args):
        return subprocess.run(
            [sys.executable, str(SCRIPTS / "document_tools.py"), "--root", str(self.root), *args],
            capture_output=True, text=True,
        )

    def run_check(self, body, *args):
        return subprocess.run(
            [sys.executable, str(SCRIPTS / "run_check.py"), "--output-dir", str(self.root / "result"),
             *args, "--", sys.executable, "-c", body],
            capture_output=True, text=True, cwd=self.root,
        )

    def test_local_links_japanese_duplicates_explicit_ids_and_fences(self):
        self.write("target.md", '# 日本語の見出し\n\n## Same\n\n## Same\n\n<a id="manual"></a>\n\n## Last\n')
        self.write("source.md", '[和文](target.md#日本語の見出し) [重複](target.md#same-1)\n'
                   '[明示](target.md#manual) [空白](<with space.md>)\n'
                   '[ref][target]\n\n[target]: target.md#same\n'
                   '```md\n[無効な例](missing.md)\n# Fake\n```\n')
        self.write("with space.md", "# Space\n")
        result = self.docs("check", "source.md", "target.md", "with space.md")
        self.assertEqual(0, result.returncode, result.stderr + result.stdout)

    def test_missing_file_anchor_and_whitespace_fail_with_locations(self):
        self.write("source.md", "# Source\n\n[broken](absent.md)\n[anchor](#absent)  \n")
        result = self.docs("check", "source.md")
        self.assertNotEqual(0, result.returncode)
        for expected in ("source.md:3", "source.md:4", "missing target", "missing anchor", "trailing whitespace"):
            self.assertIn(expected, result.stdout)

    def test_invalid_utf8_and_missing_newline_fail(self):
        (self.root / "bad.md").write_bytes(b"\xff")
        self.write("no-newline.md", "# Header")
        for name in ("bad.md", "no-newline.md"):
            with self.subTest(name=name):
                self.assertNotEqual(0, self.docs("check", name).returncode)

    def test_default_checks_tracked_files_and_skips_untracked_material(self):
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        self.write("public.md", "# Public\n")
        self.write("private.md", "broken  ")
        subprocess.run(["git", "-C", str(self.root), "add", "public.md"], check=True)
        result = self.docs("check")
        self.assertEqual(0, result.returncode, result.stderr + result.stdout)
        self.assertNotIn("private.md", result.stdout)

    def test_section_is_complete_and_does_not_read_following_anchor(self):
        self.write("guide.md", '# Guide\n\n<a id="selected"></a>\n\n## Chosen\n'
                   '日本語本文\n```md\n## Fake\n```\n### Child\n末尾\n\n'
                   '<a id="next"></a>\n\n## Next\nnext body\n')
        result = self.docs("read", "guide.md", "selected")
        self.assertEqual(0, result.returncode, result.stderr)
        for expected in ('"sha256"', "5: ## Chosen", "11: 末尾"):
            self.assertIn(expected, result.stdout)
        self.assertNotIn('id="next"', result.stdout)
        self.assertNotIn("next body", result.stdout)

    def test_unknown_ambiguous_and_too_large_sections_fail_without_partial_body(self):
        self.write("guide.md", "# Guide\n## Same\nbody1\n## Same\nbody2\n")
        for args in (("missing",), ("Same",), ("guide", "--max-chars", "4")):
            with self.subTest(args=args):
                result = self.docs("read", "guide.md", *args)
                self.assertNotEqual(0, result.returncode)
                self.assertNotIn("body1", result.stdout)
        self.assertIn("body2", self.docs("read", "guide.md", "same-1").stdout)

    def test_link_cannot_read_outside_root_or_ignored_file(self):
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        self.write(".gitignore", "secret.md\n")
        self.write("secret.md", "# Secret\n")
        self.write("source.md", "[out](../outside.md) [ignored](secret.md#secret)\n")
        result = self.docs("check", "source.md")
        self.assertNotEqual(0, result.returncode)
        self.assertNotIn("# Secret", result.stdout)

    def test_command_success_log_and_structured_status(self):
        result = self.run_check("print('detail ' * 10000)")
        self.assertEqual(0, result.returncode, result.stderr)
        output = self.root / "result"
        self.assertGreater(len((output / "command.log").read_text()), 50000)
        summary = json.loads((output / "summary.json").read_text())
        self.assertEqual(0, summary["command_exit_code"])
        self.assertEqual("passed", summary["status"])
        self.assertLess(len(result.stdout), 1200)

    def test_original_failure_code_and_full_log_survive(self):
        result = self.run_check("import sys; print('failure detail'); sys.exit(7)")
        self.assertEqual(7, result.returncode)
        summary = json.loads((self.root / "result/summary.json").read_text())
        self.assertEqual("failed", summary["status"])
        self.assertEqual(7, summary["command_exit_code"])
        self.assertIn("failure detail", (self.root / "result/command.log").read_text())

    def test_junit_failure_and_skips_are_reported_even_for_zero_exit(self):
        body = "from pathlib import Path; Path('tests.xml').write_text(" + repr(
            '<testsuite tests="3" failures="1" errors="0" skipped="1">'
            '<testcase name="pass"/><testcase name="bad" classname="Example"><failure>details</failure></testcase>'
            '<testcase name="skip"><skipped/></testcase></testsuite>') + ")"
        result = self.run_check(body, "--junit", "tests.xml")
        self.assertEqual(1, result.returncode)
        summary = json.loads((self.root / "result/summary.json").read_text())
        self.assertEqual(3, summary["junit"]["tests"])
        self.assertEqual(1, summary["junit"]["skipped"])
        self.assertEqual(["Example.bad"], summary["junit"]["failed_cases"])

    def test_lint_counts_severity_and_keeps_detail_in_report(self):
        body = "from pathlib import Path; Path('lint.xml').write_text(" + repr(
            '<issues><issue id="A" severity="Warning"/><issue id="B" severity="Hint"/></issues>') + ")"
        result = self.run_check(body, "--lint", "lint.xml")
        self.assertEqual(0, result.returncode, result.stderr)
        summary = json.loads((self.root / "result/summary.json").read_text())
        self.assertEqual({"Warning": 1, "Hint": 1}, summary["lint"]["severities"])
        self.assertIn("Warning", result.stdout)

    def test_missing_malformed_and_stale_reports_do_not_pass(self):
        for label, body in (("missing", "pass"), ("malformed", "from pathlib import Path; Path('tests.xml').write_text('oops')"),
                            ("stale", "pass")):
            with self.subTest(label=label):
                shutil.rmtree(self.root / "result", ignore_errors=True)
                report = self.root / "tests.xml"
                report.unlink(missing_ok=True)
                if label == "stale":
                    self.write("tests.xml", '<testsuite tests="0" failures="0" errors="0" skipped="0"/>')
                    os.utime(report, (1, 1))
                result = self.run_check(body, "--junit", "tests.xml")
                self.assertEqual(1, result.returncode)
                self.assertEqual("unconfirmed", json.loads((self.root / "result/summary.json").read_text())["status"])

    def test_existing_output_directory_is_not_overwritten(self):
        self.write("result/command.log", "previous run\n")
        result = self.run_check("print('new run')")
        self.assertNotEqual(0, result.returncode)
        self.assertEqual("previous run\n", (self.root / "result/command.log").read_text())

    def test_overlapping_sections_return_each_source_line_once(self):
        self.write("guide.md", "# Guide\n## Parent\nintro\n### Child\ntail\n## Next\nother\n")
        result = self.docs("read", "guide.md", "parent", "child")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(1, result.stdout.count("5: tail"))
        self.assertNotIn("other", result.stdout)

    def test_inline_code_does_not_create_an_anchor(self):
        self.write("guide.md", '# Guide\n`<a id="fake"></a>`\n[broken](#fake)\n')
        self.assertEqual(1, self.docs("check", "guide.md").returncode)

    def test_external_symlink_is_rejected(self):
        (self.root / "outside.md").symlink_to(SCRIPTS / "document_tools.py")
        self.assertNotEqual(0, self.docs("read", "outside.md", "anything").returncode)

    def test_junit_parent_counts_are_validated_without_double_counting(self):
        body = "from pathlib import Path; Path('tests.xml').write_text(" + repr(
            '<testsuites tests="1"><testsuite tests="1"><testsuite tests="1">'
            '<testcase name="pass"/></testsuite></testsuite></testsuites>') + ")"
        result = self.run_check(body, "--junit", "tests.xml")
        self.assertEqual(0, result.returncode, result.stderr + result.stdout)
        summary = json.loads((self.root / "result/summary.json").read_text())
        self.assertEqual(1, summary['junit']['tests'])
        shutil.rmtree(self.root / "result")
        result = self.run_check(body.replace('tests="1"', 'tests="2"', 1), "--junit", "tests.xml")
        self.assertEqual(1, result.returncode)

    def test_report_error_does_not_replace_original_command_failure(self):
        result = self.run_check("import sys; sys.exit(9)", "--lint", "missing.xml")
        self.assertEqual(9, result.returncode)
        summary = json.loads((self.root / "result/summary.json").read_text())
        self.assertEqual("failed", summary['status'])
        self.assertTrue(summary['report_errors'])

    @unittest.skipUnless(os.name == 'posix', 'POSIX signal return code')
    def test_signal_termination_records_raw_and_shell_return_codes(self):
        result = self.run_check("import os, signal; os.kill(os.getpid(), signal.SIGTERM)")
        self.assertEqual(143, result.returncode)
        summary = json.loads((self.root / "result/summary.json").read_text())
        self.assertEqual(-15, summary['command_returncode'])

    def test_missing_executable_records_launch_failure(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPTS / "run_check.py"), "--output-dir", str(self.root / "result"),
             "--", str(self.root / "nonexistent")], capture_output=True, text=True)
        self.assertEqual(127, result.returncode)
        summary = json.loads((self.root / "result/summary.json").read_text())
        self.assertEqual('FileNotFoundError', summary['launch_error'])

    def test_lint_errors_fail_but_unknown_severity_is_unconfirmed(self):
        for severity, expected in (("Error", "failed"), ("Other", "unconfirmed")):
            with self.subTest(severity=severity):
                shutil.rmtree(self.root / "result", ignore_errors=True)
                body = "from pathlib import Path; Path('lint.xml').write_text(" + repr(
                    f'<issues><issue id="A" severity="{severity}"/></issues>') + ")"
                result = self.run_check(body, "--lint", "lint.xml")
                self.assertEqual(1, result.returncode)
                summary = json.loads((self.root / "result/summary.json").read_text())
                self.assertEqual(expected, summary['status'])


if __name__ == "__main__":
    unittest.main()
