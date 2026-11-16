"""Reject comparison mismatches before Gradle, using a real isolated Git fixture."""

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))
from run_coverage import APPLY, REPORT, SETTINGS, TOOL_INPUTS


@unittest.skipUnless(os.name == 'posix', 'fake Gradle shell command requires POSIX')
class BuildPreflightTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        (self.root/'scripts').mkdir()
        for name in ['run_coverage.py', 'check_coverage.py']:
            shutil.copyfile(SCRIPTS/name, self.root/'scripts'/name)
        for name in (*TOOL_INPUTS, SETTINGS):
            p = self.root/name
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text('original setting\n')
        self.source = self.root/'app/src/main/java/example/App.kt'
        self.source.parent.mkdir(parents=True)
        self.source.write_text('class App\n')
        (self.root/'gradlew').write_text('#!/bin/sh\necho invoked >> gradle-calls\nexit 99\n')
        (self.root/'gradlew').chmod(0o755)
        self.git('init', '-q')
        self.git('add', '.')
        self.git('-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid',
                 'commit', '-qm', 'fixture baseline')
        self.base = self.git('rev-parse', 'HEAD').strip()
        self.report = self.root/REPORT
        self.report.parent.mkdir(parents=True)
        self.report.write_text('previous report')

    def git(self, *args):
        return subprocess.check_output(['git', *args], cwd=self.root, text=True)

    def run_coverage(self, *options):
        return subprocess.run([sys.executable, 'scripts/run_coverage.py', *options],
                              cwd=self.root, capture_output=True, text=True, timeout=10)

    def assert_no_build(self):
        self.assertFalse((self.root/'gradle-calls').exists(), 'Gradle must not start')

    def test_preflight_matches_and_preserves_reports_and_configuration(self):
        self.source.write_text('class App { val value = 1 }\n')
        result = self.run_coverage('--preflight-only', '--base-ref', self.base)
        self.assertEqual(0, result.returncode, result.stderr)
        data = json.loads(result.stdout)
        self.assertEqual('preflight', data['mode'])
        self.assertEqual('not-run', data['coverage'])
        self.assertEqual(self.base, data['base'])
        self.assertEqual(self.base, data['head'])
        self.assertTrue(data['conditions_checked'])
        self.assertEqual(['example/App.kt'], data['changed_sources'])
        for name in (*TOOL_INPUTS, SETTINGS):
            self.assertEqual(hashlib.sha256((self.root/name).read_bytes()).hexdigest(),
                             data['input_sha256'][name])
        self.assertEqual('previous report', self.report.read_text())
        self.assertFalse((self.root/'app/build/reports/coverage/comparison.json').exists())
        self.assert_no_build()

    def test_each_existing_tool_condition_is_checked_before_build(self):
        self.source.write_text('class App { val value = 1 }\n')
        for name in TOOL_INPUTS:
            with self.subTest(name=name):
                p = self.root/name
                original = p.read_bytes()
                p.write_text('changed setting\n')
                result = self.run_coverage('--preflight-only', '--base-ref', self.base)
                self.assertEqual(1, result.returncode)
                self.assertIn('Measurement conditions changed: '+name, result.stderr)
                self.assertEqual('previous report', self.report.read_text())
                self.assert_no_build()
                p.write_bytes(original)

    def test_full_runner_rejects_before_gradle_and_keeps_failed_result(self):
        self.source.write_text('class App { val value = 1 }\n')
        (self.root/'app/build.gradle.kts').write_text('changed assets layout\n')
        result = self.run_coverage('--base-ref', self.base)
        self.assertEqual(1, result.returncode)
        self.assertIn('Measurement conditions changed: app/build.gradle.kts', result.stderr)
        self.assert_no_build()
        self.assertFalse(self.report.exists())
        record = json.loads((self.root/'app/build/reports/coverage/comparison.json').read_text())
        self.assertEqual('failed', record['status'])

    def test_only_the_existing_apply_and_blank_line_exceptions_are_allowed(self):
        self.source.write_text('class App { val value = 1 }\n')
        p = self.root/'app/build.gradle.kts'
        p.write_text('original setting\n\n  '+APPLY+'  \n')
        self.assertEqual(0, self.run_coverage('--preflight-only', '--base-ref', self.base).returncode)
        p.write_text('original setting\n// different measurement condition\n'+APPLY+'\n')
        self.assertEqual(1, self.run_coverage('--preflight-only', '--base-ref', self.base).returncode)
        self.assert_no_build()

    def test_no_comparable_sources_does_not_introduce_a_new_gate(self):
        (self.root/'app/build.gradle.kts').write_text('changed setting\n')
        asset = self.root/'app/src/main/assets/sample.org'
        asset.parent.mkdir(parents=True)
        asset.write_text('* public fixture\n')
        result = self.run_coverage('--preflight-only', '--base-ref', self.base)
        self.assertEqual(0, result.returncode, result.stderr)
        data = json.loads(result.stdout)
        self.assertFalse(data['conditions_checked'])
        self.assertEqual([], data['changed_sources'])
        self.assert_no_build()

    def test_optional_input_absence_without_comparison_is_recorded(self):
        (self.root/'gradle.properties').unlink()
        result = self.run_coverage('--preflight-only', '--base-ref', self.base)
        self.assertEqual(0, result.returncode, result.stderr)
        data = json.loads(result.stdout)
        self.assertFalse(data['conditions_checked'])
        self.assertIsNone(data['input_sha256']['gradle.properties'])
        self.assert_no_build()

    def test_preflight_rejects_github_event_without_running_git_fetch(self):
        event = self.root/'event.json'
        event.write_text('{"pull_request":{"base":{"ref":"main"}}}')
        fake = self.root/'fake-bin'
        fake.mkdir()
        (fake/'git').write_text('#!/bin/sh\necho invoked > git-was-called\nexit 99\n')
        (fake/'git').chmod(0o755)
        result = subprocess.run(
            [sys.executable, 'scripts/run_coverage.py', '--preflight-only', '--github-event', 'event.json'],
            cwd=self.root, env=dict(os.environ, PATH=str(fake)+os.pathsep+os.environ['PATH']),
            capture_output=True, text=True, timeout=10)
        self.assertEqual(2, result.returncode)
        self.assertIn('requires an explicit --base-ref', result.stderr)
        self.assertFalse((self.root/'git-was-called').exists())
        self.assertEqual('previous report', self.report.read_text())
        self.assert_no_build()

    def test_missing_or_unknown_base_is_never_a_pass(self):
        for options, expected in [(('--preflight-only',), 2),
                                  (('--preflight-only', '--base-ref', 'absent'), 1),
                                  (('--preflight-only', '--base-ref=--help'), 1)]:
            with self.subTest(options=options):
                result = self.run_coverage(*options)
                self.assertEqual(expected, result.returncode)
                self.assertEqual('previous report', self.report.read_text())
                self.assert_no_build()

    def test_build_time_configuration_change_invalidates_the_run(self):
        self.source.write_text('class App { val value = 1 }\n')
        (self.root/'gradlew').write_text('#!/bin/sh\necho changed >> gradle.properties\nexit 0\n')
        result = self.run_coverage('--base-ref', self.base)
        self.assertEqual(1, result.returncode)
        self.assertIn('Build inputs changed during verification', result.stderr)
        record = json.loads((self.root/'app/build/reports/coverage/comparison.json').read_text())
        self.assertEqual('failed', record['status'])

    def test_build_time_comparison_source_set_change_invalidates_the_run(self):
        (self.root/'gradlew').write_text(
            '#!/bin/sh\necho "class App { val value = 1 }" > app/src/main/java/example/App.kt\nexit 0\n')
        result = self.run_coverage('--base-ref', self.base)
        self.assertEqual(1, result.returncode)
        self.assertIn('Comparison source set changed during verification', result.stderr)
        record = json.loads((self.root/'app/build/reports/coverage/comparison.json').read_text())
        self.assertEqual('failed', record['status'])


if __name__ == '__main__':
    unittest.main()
