"""Exercise result-comment updates through fake gh; never post to GitHub."""

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / 'update_pr_results.py'
MARKER = '<!-- org-mobile-android-sample:verification-results:v1 -->'
HEADING = '## 検証・レビュー結果（更新）'

FAKE_GH = '''#!/usr/bin/env python3
import json,os,sys
from pathlib import Path
root=Path(os.environ['PR_RESULTS_FIXTURE'])
state=json.loads((root/'state.json').read_text())
args=sys.argv[1:]
method=args[args.index('--method')+1]
endpoint=args[args.index('--method')+2]
payload=sys.stdin.read() if '--input' in args else ''
op=('target' if '/pulls/' in endpoint else 'viewer' if endpoint=='user' else
    'list' if method=='GET' else 'create' if method=='POST' else 'update')
with (root/'calls.jsonl').open('a') as output:
 output.write(json.dumps({'op':op,'args':args,'input':payload})+'\\n')
if state.get('fail')==op:
 print('sensitive-synthetic-detail',file=sys.stderr);sys.exit(22)
if state.get('bad_json')==op:
 print('{broken');sys.exit(0)
if op=='target':value=state.get('target',48)
elif op=='viewer':value=state.get('actor',7)
elif op=='list':value=state.get('pages',[[]])
else:value={'id':state.get('written_id',123)}
print(json.dumps(value))
'''


class PrResultsTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        (self.root/'gh').write_text(FAKE_GH)
        (self.root/'gh').chmod(0o755)
        self.body = '完了\r\nCIとレビューの結果\n'
        (self.root/'body.md').write_bytes(self.body.encode('utf-8'))
        self.state = {}

    def run_helper(self, *options):
        (self.root/'state.json').write_text(json.dumps(self.state))
        env = dict(os.environ, PATH=str(self.root)+os.pathsep+os.environ['PATH'],
                   PR_RESULTS_FIXTURE=str(self.root))
        return subprocess.run([sys.executable, str(SCRIPT), '--repo', 'example/project',
                               '--pr', '48', '--body-file', str(self.root/'body.md'), *options],
                              env=env, capture_output=True, text=True, timeout=10)

    def calls(self):
        p = self.root/'calls.jsonl'
        return [json.loads(line) for line in p.read_text().splitlines()] if p.exists() else []

    def comment(self, identity=123, actor=7, body=None):
        return {'id': identity, 'user': {'id': actor},
                'body': body if body is not None else MARKER+'\n'+HEADING+'\n\n'+self.body}

    def test_create_validated_body_via_stdin_without_editing_pr(self):
        result = self.run_helper()
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual('created', json.loads(result.stdout)['status'])
        calls = self.calls()
        self.assertEqual(['target', 'viewer', 'list', 'create'], [c['op'] for c in calls])
        self.assertEqual('api', calls[-1]['args'][0])
        self.assertIn('repos/example/project/issues/48/comments', calls[-1]['args'])
        self.assertIn('--paginate', calls[2]['args'])
        self.assertIn('--slurp', calls[2]['args'])
        self.assertNotIn(str(self.root/'body.md'), calls[-1]['args'])
        self.assertEqual({'body': MARKER+'\n'+HEADING+'\n\n'+self.body},
                         json.loads(calls[-1]['input']))
        self.assertNotIn(self.body, result.stdout+result.stderr)

    def test_only_own_marked_comment_on_later_page_is_updated(self):
        self.state['pages'] = [[self.comment(88, 8), self.comment(99, 7, 'ordinary comment')],
                               [self.comment(123, 7, MARKER+'\nold result')]]
        result = self.run_helper()
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual('updated', json.loads(result.stdout)['status'])
        mutation = self.calls()[-1]
        self.assertEqual('update', mutation['op'])
        self.assertIn('repos/example/project/issues/comments/123', mutation['args'])
        self.assertEqual(MARKER+'\n'+HEADING+'\n\n'+self.body, json.loads(mutation['input'])['body'])

    def test_identical_body_never_mutates(self):
        self.state['pages'] = [[self.comment()]]
        result = self.run_helper()
        self.assertEqual(0, result.returncode)
        self.assertEqual('unchanged', json.loads(result.stdout)['status'])
        self.assertEqual(['target', 'viewer', 'list'], [c['op'] for c in self.calls()])

    def test_check_mode_never_mutates(self):
        for comments, expected in [([], 'would-create'),
                                   ([self.comment(body=MARKER+'\nold')], 'would-update')]:
            with self.subTest(expected=expected):
                self.state['pages'] = [comments]
                result = self.run_helper('--check')
                self.assertEqual(0, result.returncode, result.stderr)
                self.assertEqual(expected, json.loads(result.stdout)['status'])
        self.assertTrue(all(c['op'] in ['target', 'viewer', 'list'] for c in self.calls()))

    def test_duplicate_markers_or_malformed_api_stop_without_mutation(self):
        cases = [({'pages': [[self.comment(), self.comment(124)]]}, 'ambiguous-comments'),
                 ({'actor': True}, 'invalid-response'),
                 ({'target': 49}, 'invalid-response'),
                 ({'pages': [None]}, 'invalid-response'),
                 ({'pages': [[self.comment(identity=True)]]}, 'invalid-response'),
                 ({'pages': [[self.comment(actor=True)]]}, 'invalid-response'),
                 ({'bad_json': 'viewer'}, 'invalid-response')]
        for state, expected in cases:
            with self.subTest(state=state):
                self.state = state
                result = self.run_helper()
                self.assertEqual(1, result.returncode)
                self.assertEqual(expected, json.loads(result.stdout)['error'])
        self.assertTrue(all(c['op'] in ['target', 'viewer', 'list'] for c in self.calls()))

    def test_api_failure_is_not_retried_or_echoed(self):
        self.state['fail'] = 'create'
        result = self.run_helper()
        self.assertEqual(1, result.returncode)
        self.assertEqual('github-command-failed', json.loads(result.stdout)['error'])
        self.assertEqual(1, sum(c['op']=='create' for c in self.calls()))
        self.assertNotIn('sensitive-synthetic-detail', result.stdout+result.stderr)
        self.assertNotIn(self.body, result.stdout+result.stderr)

    def test_unexpected_mutation_response_is_not_retried(self):
        self.state = {'pages': [[self.comment(body=MARKER+'\nold')]], 'written_id': 999}
        result = self.run_helper()
        self.assertEqual(1, result.returncode)
        self.assertEqual('invalid-response', json.loads(result.stdout)['error'])
        self.assertEqual(1, sum(c['op']=='update' for c in self.calls()))

    def test_invalid_input_never_reaches_gh(self):
        for data in [b'', b' \n', b'\xff', MARKER.encode()]:
            with self.subTest(data=data):
                (self.root/'body.md').write_bytes(data)
                result = self.run_helper()
                self.assertEqual(2, result.returncode)
                self.assertEqual([], self.calls())
        (self.root/'body.md').write_text('valid')
        for options in [('--repo', '../project'), ('--repo', 'owner/..'), ('--pr', '0')]:
            with self.subTest(options=options):
                self.assertEqual(2, self.run_helper(*options).returncode)
                self.assertEqual([], self.calls())


if __name__ == '__main__':
    unittest.main()
