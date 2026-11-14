"""Acceptance checks using synthetic logs and token usage only."""

import hashlib
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SCRIPTS = Path(__file__).resolve().parents[1]


class AdoptionToolsTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)

    def cli(self, script, *args):
        return subprocess.run([sys.executable, str(SCRIPTS / script), *map(str, args)],
                              capture_output=True, text=True, cwd=self.root)

    def test_excerpt_ranges_tail_match_and_provenance(self):
        log = self.root / 'log.txt'
        log.write_text('開始\ninfo\nERROR failure\nrecovery\nend\n', encoding='utf-8')
        for options, start, end, expected in [
            (['--lines', '2'], 1, 2, '1: 開始\n2: info'),
            (['--tail', '--lines', '2'], 4, 5, '4: recovery\n5: end'),
            (['--match', 'ERROR', '--before', '1', '--lines', '3'], 2, 4,
             '2: info\n3: ERROR failure\n4: recovery'),
            (['--start', '5'], 5, 5, '5: end'),
        ]:
            with self.subTest(options=options):
                result = self.cli('read_excerpt.py', log, *options)
                self.assertEqual(0, result.returncode, result.stderr)
                header, body = result.stdout.split('\n', 1)
                metadata = json.loads(header)
                self.assertEqual((start, end), (metadata['start_line'], metadata['end_line']))
                self.assertEqual(5 - (end - start + 1), metadata['omitted_lines'])
                self.assertEqual(hashlib.sha256(log.read_bytes()).hexdigest(), metadata['sha256'])
                self.assertEqual(expected + '\n', body)

    def test_excerpt_failures_never_return_partial_text(self):
        log = self.root / 'log.txt'
        log.write_text('secret synthetic text\n' + 'x' * 10000, encoding='utf-8')
        for options in [[], ['--match', 'missing'], ['--lines', '0'], ['--max-chars', '1']]:
            result = self.cli('read_excerpt.py', log, *options)
            self.assertNotEqual(0, result.returncode)
            self.assertEqual('', result.stdout)
        log.write_bytes(b'\xff')
        self.assertNotEqual(0, self.cli('read_excerpt.py', log).returncode)

    def trial(self, identity='one', success=True):
        events = self.root / f'{identity}.jsonl'
        events.write_text(json.dumps({'type': 'turn.completed', 'usage': {
            'input_tokens': 100, 'cached_input_tokens': 60, 'output_tokens': 10}}) + '\n', encoding='utf-8')
        return {'id': identity, 'condition': 'baseline', 'task_kind': 'docs',
                'revision': 'fixture-v1', 'environment': 'synthetic', 'model': 'fixture',
                'reasoning_effort': 'fixed', 'review_mode': 'separate-agent',
                'success': success, 'agents_complete': True,
                'agents': [{'id': 'author', 'events': events.name, 'cost_usd': 0.25}]}

    def usage(self, trials, *options):
        manifest = self.root / 'manifest.json'
        manifest.write_text(json.dumps({'trials': trials}), encoding='utf-8')
        return self.cli('summarize_usage.py', manifest, *options)

    def test_compact_usage_retains_all_fields_and_values(self):
        trial = self.trial()
        trial.update(task_id='日本語文書', measurements={'rereads': 0, 'completion_seconds': None})
        formatted = self.usage([trial])
        compact = self.usage([trial], '--compact')
        self.assertEqual(0, compact.returncode, compact.stderr)
        self.assertEqual(json.loads(formatted.stdout), json.loads(compact.stdout))
        self.assertLess(len(compact.stdout), len(formatted.stdout))
        self.assertEqual(1, compact.stdout.count('\n'))

    def test_usage_includes_failed_trials_and_reviewers_without_adding_cache_twice(self):
        success = self.trial()
        failure = self.trial('two', False)
        reviewer = self.trial('reviewer')['agents'][0]
        reviewer['id'] = 'reviewer'
        success['agents'].append(reviewer)
        result = self.usage([success, failure])
        self.assertEqual(0, result.returncode, result.stderr)
        group = json.loads(result.stdout)['groups'][0]
        self.assertEqual((2, 1, 0.5), (group['trials'], group['successes'], group['success_rate']))
        self.assertEqual({'input_tokens': 300, 'cached_input_tokens': 180, 'output_tokens': 30},
                         group['observed_tokens'])
        self.assertEqual(300, group['input_tokens_per_success'])
        self.assertEqual(0.75, group['cost_usd_per_success'])

    def test_usage_missing_coverage_failure_and_zero_success_are_not_zero_usage(self):
        for case in ('missing', 'agents', 'failed_turn', 'unfinished', 'no_success', 'no_cost'):
            with self.subTest(case=case):
                trial = self.trial()
                if case == 'missing':
                    trial['agents'].append({'id': 'reviewer', 'events': None})
                elif case == 'agents':
                    trial['agents_complete'] = False
                elif case in ('failed_turn', 'unfinished'):
                    with (self.root / 'one.jsonl').open('a', encoding='utf-8') as source:
                        source.write(json.dumps({'type': 'turn.failed' if case == 'failed_turn'
                                                 else 'turn.started'}) + '\n')
                elif case == 'no_success':
                    trial['success'] = False
                elif case == 'no_cost':
                    trial['agents'][0]['cost_usd'] = None
                result = self.usage([trial])
                self.assertEqual(0, result.returncode, result.stderr)
                group = json.loads(result.stdout)['groups'][0]
                if case != 'no_cost':
                    self.assertIsNone(group['input_tokens_per_success'])
                self.assertIsNone(group['cost_usd_per_success'])
                self.assertEqual(100, group['observed_tokens']['input_tokens'])

    def test_usage_separates_conditions_and_sums_multiple_turns(self):
        first, second = self.trial(), self.trial('two')
        second['review_mode'] = 'self'
        events = self.root / 'one.jsonl'
        events.write_bytes(events.read_bytes() * 2)
        result = self.usage([first, second])
        self.assertEqual(0, result.returncode, result.stderr)
        groups = json.loads(result.stdout)['groups']
        self.assertEqual(2, len(groups))
        self.assertEqual([100, 200], sorted(group['observed_tokens']['input_tokens'] for group in groups))

    def test_evaluation_measurements_preserve_task_outcomes_and_missing_values(self):
        first, second = self.trial(), self.trial('two', False)
        first.update(task_id='docs-link', measurements={
            'completion_seconds': 10, 'rereads': 0, 'review_rework': 1})
        second.update(task_id='docs-link', measurements={
            'completion_seconds': 30, 'rereads': None, 'review_rework': 2})
        result = self.usage([first, second])
        self.assertEqual(0, result.returncode, result.stderr)
        group = json.loads(result.stdout)['groups'][0]
        self.assertEqual(80, group['uncached_input_tokens'])
        self.assertEqual(0.6, group['cache_ratio'])
        self.assertEqual({'observed': 2, 'missing': 0, 'total': 40, 'median': 20, 'p95': None},
                         group['measurements']['completion_seconds'])
        self.assertEqual({'observed': 1, 'missing': 1, 'total': None, 'median': None, 'p95': None},
                         group['measurements']['rereads'])
        self.assertEqual(3, group['measurements']['review_rework']['total'])
        self.assertEqual([('docs-link', True), ('docs-link', False)],
                         [(trial['task_id'], trial['success']) for trial in group['trial_results']])
        # Legacy manifests still work; absence of measurement is never treated as zero.
        result = self.usage([self.trial()])
        group = json.loads(result.stdout)['groups'][0]
        self.assertIsNone(group['trial_results'][0]['task_id'])
        self.assertEqual({}, group['measurements'])

    def test_evaluation_p95_requires_twenty_complete_trials(self):
        trials = [self.trial(str(index)) for index in range(1, 21)]
        for index, trial in enumerate(trials, 1):
            trial['measurements'] = {'completion_seconds': index}
        result = self.usage(trials[:19])
        self.assertIsNone(json.loads(result.stdout)['groups'][0]['measurements']['completion_seconds']['p95'])
        result = self.usage(trials)
        self.assertEqual(0, result.returncode, result.stderr)
        stats = json.loads(result.stdout)['groups'][0]['measurements']['completion_seconds']
        self.assertEqual((210, 10.5, 19), (stats['total'], stats['median'], stats['p95']))
        trials[0]['measurements']['completion_seconds'] = None
        result = self.usage(trials)
        self.assertIsNone(json.loads(result.stdout)['groups'][0]['measurements']['completion_seconds']['p95'])

    def test_evaluation_rejects_invalid_measurements(self):
        for measurements in ([], {'unknown': 1}, {'rereads': True}, {'retries': 1.5},
                             {'completion_seconds': -1}, {'generation_seconds': float('inf')}):
            trial = self.trial()
            trial['measurements'] = measurements
            result = self.usage([trial])
            self.assertNotEqual(0, result.returncode)
            self.assertEqual('', result.stdout)

    def test_usage_rejects_invalid_records_and_double_counting_atomically(self):
        original = self.trial()
        for mutation in ('duplicate_id', 'reuse', 'boolean', 'negative', 'bad_cost', 'bad_agents'):
            with self.subTest(mutation=mutation):
                trial = copy.deepcopy(original)
                trials = [trial]
                if mutation == 'duplicate_id':
                    trials.append(copy.deepcopy(trial))
                elif mutation == 'reuse':
                    trials.append({**copy.deepcopy(trial), 'id': 'different'})
                elif mutation == 'boolean':
                    trial['success'] = 'true'
                elif mutation == 'negative':
                    trial['agents'][0]['cost_usd'] = -1
                elif mutation == 'bad_cost':
                    trial['agents'][0]['cost_usd'] = float('nan')
                else:
                    trial['agents'] = []
                result = self.usage(trials)
                self.assertNotEqual(0, result.returncode)
                self.assertEqual('', result.stdout)
        for usage in ({}, {'input_tokens': True, 'cached_input_tokens': 0, 'output_tokens': 1},
                      {'input_tokens': 1, 'cached_input_tokens': 2, 'output_tokens': 1}):
            (self.root / 'one.jsonl').write_text(json.dumps({'type': 'turn.completed', 'usage': usage}))
            result = self.usage([original])
            self.assertNotEqual(0, result.returncode)
            self.assertEqual('', result.stdout)
        (self.root / 'one.jsonl').write_text('private synthetic malformed JSON')
        result = self.usage([original])
        self.assertNotEqual(0, result.returncode)
        self.assertNotIn('private synthetic', result.stderr)


if __name__ == '__main__':
    unittest.main()
