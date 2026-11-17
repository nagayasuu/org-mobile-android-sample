"""One-launch monitoring, with synthetic commands and no model/network calls."""

import json
import os
from pathlib import Path
import select
import signal
import subprocess
import sys
import tempfile
import time
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / 'run_check.py'


@unittest.skipUnless(os.name == 'posix', 'monitored process groups require POSIX')
class RunCheckMonitorTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)

    def command(self, code, *options):
        return [sys.executable, str(SCRIPT), '--output-dir', 'result', *options,
                '--', sys.executable, '-c', code]

    def result(self):
        return json.loads((self.root / 'result/summary.json').read_text())

    def run_command(self, code, *options):
        return subprocess.run(self.command(code, *options), cwd=self.root,
                              capture_output=True, text=True, timeout=8)

    def test_periodic_notifications_keep_full_log_and_launch_only_once(self):
        code = ("from pathlib import Path; import time; "
                "p=Path('launches'); p.write_text(p.read_text()+'x' if p.exists() else 'x'); "
                "print('日本語の詳細'*2000,flush=True)\n"
                "while not Path('release').exists(): time.sleep(0.01)\n"
                "time.sleep(0.25)")
        process = subprocess.Popen(self.command(code, '--progress-interval', '0.05', '--timeout', '5'),
                                   cwd=self.root, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            self.assertTrue(select.select([process.stdout], [], [], 3)[0])
            first = process.stdout.readline()
            self.assertIsNone(process.poll(), 'notification must arrive before command completion')
            (self.root/'release').touch()
            stdout, stderr = process.communicate(timeout=8)
            stdout = first+stdout
            self.assertEqual(0, process.returncode, stderr)
        finally:
            if process.poll() is None:
                process.terminate()
                process.communicate(timeout=5)
        events = [json.loads(line) for line in stdout.splitlines() if line.startswith('{')]
        self.assertEqual('started', events[0]['event'])
        running = [event for event in events if event['event'] == 'running']
        self.assertGreaterEqual(len(running), 1)
        self.assertLess(len(running), 20)
        # A notification may precede the child's first write under CPU load.
        # The contract permits zero bytes; the retained log must still be exact.
        sizes = [event['log_bytes'] for event in events]
        self.assertEqual(sorted(sizes), sizes)
        self.assertNotIn('日本語の詳細', stdout)
        self.assertEqual('日本語の詳細'*2000+'\n', (self.root/'result/command.log').read_text())
        self.assertEqual('x', (self.root/'launches').read_text())
        self.assertEqual('passed', self.result()['status'])
        self.assertEqual(len(events), self.result()['progress_notifications'])
        self.assertEqual(0.05, self.result()['progress_interval_seconds'])
        self.assertEqual(5, self.result()['timeout_seconds'])

    def test_completion_does_not_wait_for_next_progress_notification(self):
        result = self.run_command("print('finished')", '--progress-interval', '60', '--timeout', '5')
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual('passed', self.result()['status'])
        self.assertEqual(1, self.result()['progress_notifications'])
        self.assertEqual('finished\n', (self.root / 'result/command.log').read_text())

    def test_monitoring_keeps_report_failure_and_original_nonzero_exit(self):
        code = ("from pathlib import Path; "
                "Path('tests.xml').write_text('<testsuite tests=\"1\"><testcase name=\"bad\">'"
                "'<failure/></testcase></testsuite>'); print('synthetic details')")
        result = self.run_command(code, '--progress-interval', '0.05', '--junit', 'tests.xml')
        self.assertEqual(1, result.returncode, result.stderr)
        self.assertEqual(0, self.result()['command_exit_code'])
        self.assertEqual(1, self.result()['junit']['failures'])
        # A new output directory is required even when monitoring is enabled.
        before = (self.root/'result/summary.json').read_bytes()
        again = self.run_command("raise SystemExit(0)", '--progress-interval', '0.05')
        self.assertEqual(2, again.returncode)
        self.assertEqual(before, (self.root/'result/summary.json').read_bytes())
        (self.root/'result/summary.json').unlink()
        (self.root/'result/command.log').unlink()
        (self.root/'result').rmdir()
        failed = self.run_command("print('failed detail'); raise SystemExit(7)",
                                  '--progress-interval', '0.05')
        self.assertEqual(7, failed.returncode, failed.stderr)
        self.assertEqual(7, self.result()['command_returncode'])
        self.assertIn('failed detail', (self.root/'result/command.log').read_text())

    def test_timeout_terminates_ignoring_command_and_descendant(self):
        code = ("import signal,subprocess,sys,time; from pathlib import Path; "
                "signal.signal(signal.SIGTERM,signal.SIG_IGN); "
                "p=subprocess.Popen([sys.executable,'-c','import time; time.sleep(60)']); "
                "Path('descendant').write_text(str(p.pid)); print('before timeout',flush=True); "
                "time.sleep(60)")
        try:
            result = self.run_command(code, '--progress-interval', '0.1', '--timeout', '1')
            self.assertEqual(124, result.returncode, result.stderr)
            summary = self.result()
            self.assertEqual('timeout', summary['termination'])
            self.assertEqual('failed', summary['status'])
            self.assertEqual(-signal.SIGKILL, summary['command_returncode'])
            self.assertIn('before timeout', (self.root/'result/command.log').read_text())
            pid = int((self.root/'descendant').read_text())
            # A reparented zombie is terminated, although its init may reap it later.
            stat = Path(f'/proc/{pid}/stat')
            if Path('/proc').exists() and stat.exists():
                self.assertEqual('Z', stat.read_text().split(') ')[1].split()[0])
        finally:
            if (self.root/'descendant').exists():
                try:
                    os.kill(int((self.root/'descendant').read_text()), signal.SIGKILL)
                except ProcessLookupError:
                    pass

    def interrupt_and_check(self, sig):
        code = ("from pathlib import Path; import time; "
                "print('before interruption',flush=True); Path('ready').touch(); time.sleep(60)")
        process = subprocess.Popen(self.command(code, '--progress-interval', '0.05'),
                                   cwd=self.root, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                   text=True)
        try:
            deadline = time.monotonic()+5
            while not (self.root/'ready').exists() and process.poll() is None and time.monotonic()<deadline:
                time.sleep(0.01)
            self.assertTrue((self.root/'ready').exists())
            process.send_signal(sig)
            stdout, stderr = process.communicate(timeout=5)
            self.assertEqual(128+sig, process.returncode, stderr)
            self.assertNotIn('before interruption', stdout)
            self.assertEqual('interrupted', self.result()['termination'])
            self.assertEqual(-signal.SIGTERM, self.result()['command_returncode'])
            self.assertEqual(128+sig, self.result()['command_exit_code'])
            self.assertIn('before interruption', (self.root/'result/command.log').read_text())
        finally:
            if process.poll() is None:
                process.kill()
                process.communicate()

    def test_sigterm_records_interruption_and_preserves_output(self):
        self.interrupt_and_check(signal.SIGTERM)

    def test_sigint_records_interruption_and_preserves_output(self):
        self.interrupt_and_check(signal.SIGINT)

    def test_invalid_limits_fail_before_launch_or_directory_creation(self):
        for option in ['--progress-interval', '--timeout']:
            for value in ['0', '-1', 'nan', 'inf']:
                with self.subTest(option=option, value=value):
                    result = self.run_command("raise SystemExit(99)", option, value)
                    self.assertEqual(2, result.returncode)
                    self.assertFalse((self.root/'result').exists())


if __name__ == '__main__':
    unittest.main()
