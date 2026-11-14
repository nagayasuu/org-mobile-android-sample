"""Synthetic preflight acceptance cases; no model calls."""

import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))
from check_trial_input import check, digest


class CheckTrialInputTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        subprocess.run(['git', 'init', '-q', str(self.root)], check=True)
        subprocess.run(['git', '-C', str(self.root), '-c', 'user.name=Test',
                        '-c', 'user.email=test@example.invalid', 'commit', '-qm',
                        'fixture', '--allow-empty'], check=True)
        revision = subprocess.check_output(['git', '-C', str(self.root), 'rev-parse', 'HEAD'], text=True).strip()
        self.source = '// 日本語\nfun cancel() {\n    assertEquals("本文", actual)\n}\n'
        self.prompt = '取消後の本文を保持する\n' + self.source
        self.plan = {'schema_version': 1, 'revision': revision,
                     'prompt': self.file('prompt.txt', self.prompt),
                     'snippets': [{**self.file('source.kt', self.source),
                                   'start_line': 1, 'end_line': 4,
                                   'snippet_sha256': digest(self.source.encode())}],
                     'operations': ['取消後の本文を保持する'],
                     'assertions': ['assertEquals("本文", actual)'], 'files': []}

    def file(self, path, text):
        data = text.encode('utf-8')
        (self.root / path).write_bytes(data)
        return {'path': path, 'sha256': digest(data)}

    def test_valid_japanese_input(self):
        check(self.plan, self.root)

    def test_known_defects_even_when_whole_file_hashes_are_updated(self):
        cases = [
            ('prompt-final-newline', lambda p: p.update(prompt=self.file('prompt.txt', self.prompt.rstrip('\n')))),
            ('empty-input', lambda p: p.update(prompt=self.file('prompt.txt', ''))),
            ('range', lambda p: p['snippets'][0].update(end_line=0)),
            ('snippet-missing', lambda p: p.update(prompt=self.file('prompt.txt', '取消後の本文を保持する\n'))),
            ('operations-missing', lambda p: p.update(operations=['回転後の表示'])),
            ('assertions-missing', lambda p: p.update(assertions=['assertFalse(failed)'])),
            ('revision-mismatch', lambda p: p.update(revision='0' * 40)),
            ('hash-mismatch', lambda p: p['prompt'].update(sha256='0' * 64)),
            ('snippet-hash', lambda p: p['snippets'][0].update(snippet_sha256='0' * 64)),
        ]
        for code, mutate in cases:
            with self.subTest(code=code):
                plan = copy.deepcopy(self.plan)
                self.file('prompt.txt', self.prompt)
                mutate(plan)
                with self.assertRaisesRegex(ValueError, '^' + code + '$'):
                    check(plan, self.root)

    def test_no_vacuous_requirements(self):
        for field in ('operations', 'assertions', 'snippets'):
            for value in ([], None, [''] if field != 'snippets' else [{}]):
                with self.subTest(field=field, value=value):
                    plan = copy.deepcopy(self.plan)
                    plan[field] = value
                    with self.assertRaises(ValueError):
                        check(plan, self.root)

    def test_source_assertions_and_nonempty_ranges_are_checked(self):
        plan = copy.deepcopy(self.plan)
        plan['snippets'][0].update(start_line=2, end_line=2,
                                  snippet_sha256=digest('fun cancel() {\n'.encode()))
        with self.assertRaisesRegex(ValueError, '^assertion-not-in-source$'):
            check(plan, self.root)
        plan = copy.deepcopy(self.plan)
        plan['snippets'][0].update(**self.file('blank.kt', '// header\n  \n'), start_line=2, end_line=2)
        with self.assertRaisesRegex(ValueError, '^empty-snippet$'):
            check(plan, self.root)

    def test_extra_files_and_path_boundaries(self):
        self.plan['files'] = [self.file('tool.py', 'pass\n')]
        check(self.plan, self.root)
        (self.root / 'tool.py').write_text('raise Exception()\n')
        with self.assertRaisesRegex(ValueError, '^hash-mismatch$'):
            check(self.plan, self.root)
        self.plan['prompt']['path'] = '../outside.txt'
        with self.assertRaisesRegex(ValueError, '^path-outside-root$'):
            check(self.plan, self.root)

    def test_cli_failure_does_not_echo_private_input(self):
        self.plan['prompt']['path'] = 'private-synthetic-name.txt'
        plan_path = self.root / 'plan.json'
        plan_path.write_text(json.dumps(self.plan))
        result = subprocess.run([sys.executable, str(SCRIPTS / 'check_trial_input.py'),
                                 str(plan_path), '--root', str(self.root)], capture_output=True, text=True)
        self.assertEqual(1, result.returncode)
        self.assertEqual('', result.stderr)
        self.assertNotIn('private-synthetic', result.stdout)
        self.assertFalse(json.loads(result.stdout)['ok'])

    def test_cli_success(self):
        plan_path = self.root / 'plan.json'
        plan_path.write_text(json.dumps(self.plan))
        result = subprocess.run([sys.executable, str(SCRIPTS / 'check_trial_input.py'),
                                 str(plan_path), '--root', str(self.root)], capture_output=True, text=True)
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertTrue(json.loads(result.stdout)['ok'])

    def test_cli_rejects_malformed_input_without_tracebacks(self):
        plan_path = self.root / 'plan.json'
        for data in (b'{', b'null', b'[]', b'\xff'):
            with self.subTest(data=data):
                plan_path.write_bytes(data)
                result = subprocess.run([sys.executable, str(SCRIPTS / 'check_trial_input.py'),
                                         str(plan_path), '--root', str(self.root)],
                                        capture_output=True, text=True)
                self.assertEqual(1, result.returncode)
                self.assertEqual('', result.stderr)
                self.assertFalse(json.loads(result.stdout)['ok'])
        invalid = b'\xff\n'
        (self.root / 'prompt.txt').write_bytes(invalid)
        self.plan['prompt']['sha256'] = digest(invalid)
        plan_path.write_text(json.dumps(self.plan))
        result = subprocess.run([sys.executable, str(SCRIPTS / 'check_trial_input.py'),
                                 str(plan_path), '--root', str(self.root)], capture_output=True, text=True)
        self.assertEqual(1, result.returncode)
        self.assertEqual('', result.stderr)
        self.assertEqual('unreadable-or-invalid-input', json.loads(result.stdout)['error'])


if __name__ == '__main__':
    unittest.main()
