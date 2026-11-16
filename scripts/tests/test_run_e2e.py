"""Exercise the E2E gate and evidence retention without a device or network."""

import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


SCRIPT = Path(__file__).resolve().parents[1] / 'run_e2e.py'
spec = importlib.util.spec_from_file_location('run_e2e', SCRIPT)
e2e = importlib.util.module_from_spec(spec)
spec.loader.exec_module(e2e)


class RunE2eTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        previous = Path.cwd()
        os.chdir(self.temp.name)
        self.addCleanup(os.chdir, previous)

    def fake_run(self, command):
        output = Path(command[command.index('--output-dir') + 1])
        phase = output.name
        output.mkdir(parents=True)
        names = ([e2e.PREFLIGHT] if phase == 'preflight' else
                 ['scenario' + str(i) for i in range(9)])
        xml = Path(e2e.JUNIT.replace('TEST-*.xml', 'TEST-reader.xml'))
        xml.parent.mkdir(parents=True, exist_ok=True)
        xml.write_text('<testsuite>' + ''.join(
            '<testcase classname="' + e2e.TEST_CLASS + '" name="' + n + '"/>'
            for n in names) + '</testsuite>')
        diagnostic = Path('app/build/outputs/managed_device_android_test_additional_output/screen.png')
        diagnostic.parent.mkdir(parents=True, exist_ok=True)
        diagnostic.write_text(phase)
        (output / 'summary.json').write_text(json.dumps({
            'status': 'passed', 'junit': {'tests': len(names), 'skipped': 0, 'reports': [str(xml)]}}))
        return type('Result', (), {'returncode': 0})()

    def test_separate_evidence_survives_next_phase(self):
        with patch.object(e2e.subprocess, 'run', side_effect=self.fake_run):
            for phase in ('preflight', 'suite'):
                self.assertEqual(0, e2e.run_phase(Path('run'), phase)[0])
        for phase in ('preflight', 'suite'):
            p = Path('run') / phase / 'outputs/managed_device_android_test_additional_output/screen.png'
            self.assertEqual(phase, p.read_text())
        summary = json.loads(Path('run/preflight/summary.json').read_text())
        report = Path(summary['junit']['reports'][0])
        self.assertTrue(report.is_file())
        self.assertIn(e2e.PREFLIGHT, report.read_text())
        self.assertNotIn('scenario0', report.read_text())

    def test_bad_selection_is_rejected_even_when_command_succeeds(self):
        def wrong(command):
            result = self.fake_run(command)
            summary = Path('run/preflight/summary.json')
            data = json.loads(summary.read_text())
            data['junit']['skipped'] = 1
            summary.write_text(json.dumps(data))
            return result
        with patch.object(e2e.subprocess, 'run', side_effect=wrong):
            self.assertEqual(1, e2e.run_phase(Path('run'), 'preflight')[0])

    def test_failed_gate_stops_suite_and_keeps_original_exit(self):
        def failed(root, phase):
            self.assertEqual('preflight', phase)
            return 124, set()
        with patch.object(e2e, 'run_phase', side_effect=failed) as run:
            with patch('sys.argv', ['run_e2e.py', '--output-dir', 'run']):
                self.assertEqual(124, e2e.main())
            self.assertEqual(1, run.call_count)

    def test_suite_cannot_silently_repeat_the_gate(self):
        def duplicate(command):
            result = self.fake_run(command)
            xml = Path(e2e.JUNIT.replace('TEST-*.xml', 'TEST-reader.xml'))
            xml.write_text(xml.read_text().replace('scenario0', e2e.PREFLIGHT))
            return result
        with patch.object(e2e.subprocess, 'run', side_effect=duplicate):
            self.assertEqual(1, e2e.run_phase(Path('run'), 'suite')[0])

    def test_failed_launch_does_not_relabel_old_diagnostics(self):
        diagnostic = Path('app/build/outputs/managed_device_android_test_additional_output/old.png')
        diagnostic.parent.mkdir(parents=True)
        diagnostic.write_text('previous phase')
        with patch.object(e2e.subprocess, 'run', return_value=type('Result', (), {'returncode': 7})()):
            self.assertEqual(7, e2e.run_phase(Path('run'), 'suite')[0])
        self.assertFalse(diagnostic.exists())

    def test_archive_failure_preserves_original_timeout(self):
        def failed(command):
            self.fake_run(command)
            return type('Result', (), {'returncode': 124})()
        with patch.object(e2e.subprocess, 'run', side_effect=failed):
            with patch.object(e2e.shutil, 'copytree', side_effect=OSError('disk full')):
                self.assertEqual(124, e2e.run_phase(Path('run'), 'preflight')[0])
        summary = json.loads(Path('run/preflight/summary.json').read_text())
        self.assertEqual('failed', summary['status'])
        self.assertTrue(summary['archive_errors'])

    def test_archive_failure_does_not_report_success(self):
        with patch.object(e2e.subprocess, 'run', side_effect=self.fake_run):
            with patch.object(e2e.shutil, 'copytree', side_effect=OSError('disk full')):
                self.assertEqual(1, e2e.run_phase(Path('run'), 'preflight')[0])

    def test_profile_listing_failure_preserves_original_exit(self):
        Path('build/reports/profile').mkdir(parents=True)
        def failed(command):
            self.fake_run(command)
            return type('Result', (), {'returncode': 7})()
        with patch.object(e2e.subprocess, 'run', side_effect=failed):
            with patch.object(Path, 'iterdir', side_effect=OSError('cannot list profile')):
                self.assertEqual(7, e2e.run_phase(Path('run'), 'preflight')[0])
        self.assertTrue(json.loads(Path('run/preflight/summary.json').read_text())['archive_errors'])


if __name__ == '__main__':
    unittest.main()
