"""Recording acceptance checks: synthetic commands, no model calls."""

import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import unittest

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))
from record_trial import summarize
from summarize_usage import event_usage


class RecordTrialTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)

    def command(self, name='one', code='pass', *options):
        return [sys.executable, str(SCRIPTS / 'record_trial.py'), 'run',
                '--output-dir', str(self.root / name), '--trial', 'D1', '--agent', 'author',
                '--attempt', name, '--scope', 'trial', '--phase', 'agent', *options,
                '--', sys.executable, '-c', code]

    def read(self, name, file):
        return json.loads((self.root / name / file).read_text())

    def test_failure_retains_streams_timeline_and_process_independently(self):
        code = "import sys; print('{\"type\":\"turn.started\"}'); print('日本語'); print('failure', file=sys.stderr); sys.exit(7)"
        result = subprocess.run(self.command(code=code), capture_output=True)
        self.assertEqual(7, result.returncode)
        final = self.read('one', 'process.json')
        self.assertEqual((7, 7, 'exited'), (final['returncode'], final['exit_code'], final['termination']))
        self.assertGreater(final['wall_seconds'], 0)
        self.assertIn('日本語', (self.root / 'one/stdout.log').read_text())
        self.assertEqual('failure\n', (self.root / 'one/stderr.log').read_text())
        timeline = [json.loads(line) for line in (self.root / 'one/timeline.jsonl').read_text().splitlines()]
        self.assertEqual(('turn.started', 1, 1), (timeline[0]['type'], timeline[0]['turn'], timeline[0]['line']))
        self.assertNotIn('日本語', json.dumps(timeline))
        before = (self.root / 'one/process.json').read_bytes()
        self.assertNotEqual(0, subprocess.run(self.command(), capture_output=True).returncode)
        self.assertEqual(before, (self.root / 'one/process.json').read_bytes())

    def test_timeout_and_signal_retained_without_fabricated_usage(self):
        result = subprocess.run(self.command('one', 'import time; time.sleep(60)', '--timeout', '0.1'), capture_output=True)
        self.assertEqual(124, result.returncode)
        self.assertEqual('timeout', self.read('one', 'process.json')['termination'])
        self.assertEqual(-signal.SIGKILL, self.read('one', 'process.json')['returncode'])
        self.assertEqual(b'', (self.root / 'one/stdout.log').read_bytes())
        result = subprocess.run(self.command('signal', 'import os, signal; os.kill(os.getpid(), signal.SIGTERM)'), capture_output=True)
        self.assertEqual(143, result.returncode)
        self.assertEqual(-15, self.read('signal', 'process.json')['returncode'])

    def test_interruption_and_resumption_use_distinct_attempts(self):
        process = subprocess.Popen(self.command(code='import time; time.sleep(60)'), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.addCleanup(lambda: process.poll() is None and process.kill())
        deadline = time.monotonic() + 5
        while not (self.root / 'one/stdout.log').exists() and time.monotonic() < deadline:
            time.sleep(0.01)
        process.terminate()
        process.communicate(timeout=5)
        self.assertEqual(143, process.returncode)
        original = (self.root / 'one/process.json').read_bytes()
        self.assertEqual(0, subprocess.run(self.command('resume'), capture_output=True).returncode)
        self.assertEqual(original, (self.root / 'one/process.json').read_bytes())
        summary = summarize([self.root / 'one', self.root / 'resume'])['groups'][0]
        self.assertEqual(2, len(summary['attempts']))
        self.assertEqual('interrupted', summary['attempts'][0]['termination'])

    def fixture(self, name, start=100, seconds=10, phase='agent', scope='trial'):
        directory = self.root / name
        directory.mkdir()
        (directory / 'start.json').write_text(json.dumps(dict(trial='D1', agent=name, attempt='1',
            phase=phase, scope=scope, started_unix_ns=start * 10**9)))
        if seconds is not None:
            (directory / 'process.json').write_text(json.dumps(dict(wall_seconds=seconds, exit_code=0, termination='exited')))
        return directory

    def test_parallel_elapsed_sum_and_outside_scope_are_distinct(self):
        a = self.fixture('author')
        b = self.fixture('reviewer', start=105, seconds=7, phase='review')
        c = self.fixture('prepare', seconds=3, phase='environment', scope='outside')
        groups = summarize([a, b, c])['groups']
        outside, trial = groups
        self.assertEqual(3, outside['attempt_seconds_sum'])
        self.assertEqual((17, 12, 12), (trial['attempt_seconds_sum'], trial['recorded_window_seconds'], trial['observed_active_seconds']))
        self.assertEqual(7, trial['phase_attempt_seconds']['review'])
        self.assertIsNone(trial['phase_attempt_seconds']['tool'])
        self.assertIsNone(trial['model_wait_seconds'])

    def test_missing_completion_and_duplicate_inputs_do_not_inflate_totals(self):
        a = self.fixture('complete')
        b = self.fixture('killed', seconds=None)
        group = summarize([a, b])['groups'][0]
        self.assertFalse(group['process_time_complete'])
        self.assertEqual(10, group['observed_attempt_seconds'])
        self.assertIsNone(group['attempt_seconds_sum'])
        self.assertIsNone(group['recorded_window_seconds'])
        self.assertIsNone(group['attempts'][1]['exit_code'])
        with self.assertRaises(ValueError):
            summarize([a, a])
        alias = self.root / 'alias'
        alias.mkdir()
        for name in ('start.json', 'process.json'):
            (alias / name).write_bytes((a / name).read_bytes())
        with self.assertRaises(ValueError):
            summarize([a, alias])

    def test_escaped_descendant_cannot_prevent_process_record(self):
        code = ("import subprocess, sys; p = subprocess.Popen([sys.executable, '-c', "
                "'import time; time.sleep(60)'], start_new_session=True); print(p.pid, flush=True)")
        try:
            result = subprocess.run(self.command(code=code), capture_output=True, timeout=5)
            self.assertEqual(1, result.returncode)
            final = self.read('one', 'process.json')
            self.assertEqual(0, final['returncode'])
            self.assertIn('stdout_eof_timeout', final['capture_errors'])
        finally:
            log = self.root / 'one/stdout.log'
            if log.exists() and log.read_text().strip():
                try:
                    os.kill(int(log.read_text().strip()), signal.SIGKILL)
                except ProcessLookupError:
                    pass

    def test_recorded_usage_is_compatible_with_existing_aggregation(self):
        events = [dict(type='turn.started'), dict(type='turn.completed', usage=dict(
            input_tokens=100, cached_input_tokens=60, output_tokens=10)), dict(type='turn.failed')]
        code = 'import json; ' + '; '.join('print(' + repr(json.dumps(event)) + ')' for event in events)
        self.assertEqual(0, subprocess.run(self.command(code=code), capture_output=True).returncode)
        totals, complete = event_usage(self.root / 'one/stdout.log')
        self.assertEqual(dict(input_tokens=100, cached_input_tokens=60, output_tokens=10), totals)
        self.assertFalse(complete)
        self.assertEqual(0, self.read('one', 'process.json')['exit_code'])

    def test_launch_failure_and_malformed_events_remain_available(self):
        command = self.command()
        command[-3:] = ['/nonexistent-ca001-command']
        self.assertEqual(127, subprocess.run(command, capture_output=True).returncode)
        self.assertIsNone(self.read('one', 'process.json')['returncode'])
        result = subprocess.run(self.command('malformed', "print('{\"type\":[]}'); print('not json')"), capture_output=True)
        self.assertEqual(0, result.returncode)
        self.assertEqual([], self.read('malformed', 'process.json')['capture_errors'])
        self.assertEqual(2, len((self.root / 'malformed/timeline.jsonl').read_text().splitlines()))


if __name__ == '__main__':
    unittest.main()
