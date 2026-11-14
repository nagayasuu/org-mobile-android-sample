"""CLI checks for source/dependency invalidation and public-source boundaries."""

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / 'context_memory.py'


class ContextMemoryTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        subprocess.run(['git', 'init', '-q', str(self.root)], check=True)
        (self.root / '.gitignore').write_text('.local/\nprivate/\n', encoding='utf-8')
        (self.root / 'source.kt').write_text('object Example {\n  // 日本語\n}\n', encoding='utf-8')
        (self.root / 'dependency.md').write_text('# Contract\n', encoding='utf-8')
        self.state = '.local/memory/entry.json'

    def cli(self, *args):
        return subprocess.run([sys.executable, str(SCRIPT), '--root', str(self.root), *args],
                              capture_output=True, text=True)

    def save(self, *args):
        return self.cli('save', self.state, 'source.kt', '--start', '2', '--end', '2',
                        '--identifier', 'Example', '--depends', 'dependency.md', *args)

    def test_unchanged_source_preserves_range_but_not_source_text(self):
        self.assertEqual(0, self.save().returncode)
        result = self.cli('check', self.state)
        self.assertEqual(0, result.returncode, result.stderr)
        record = json.loads(result.stdout)
        self.assertEqual(('unchanged', 2, 2, 'Example'),
                         (record['status'], record['start_line'], record['end_line'], record['identifier']))
        self.assertEqual('dependency.md', record['dependencies'][0]['path'])
        self.assertNotIn('日本語', (self.root / self.state).read_text())
        self.assertNotIn('日本語', result.stdout)
        self.assertNotEqual(0, self.save().returncode)

    def test_source_dependency_change_and_deletion_invalidate_all_ranges(self):
        for name, delete in [('source.kt', False), ('dependency.md', False),
                             ('dependency.md', True), ('source.kt', 'invalid_utf8')]:
            with self.subTest(name=name, delete=delete):
                state = self.root / self.state
                if state.exists():
                    state.unlink()
                self.assertEqual(0, self.save().returncode)
                path = self.root / name
                original = path.read_bytes()
                if delete == 'invalid_utf8':
                    path.write_bytes(b'\xff')
                elif delete:
                    path.unlink()
                else:
                    path.write_bytes(original + b'changed\n')
                result = self.cli('check', self.state)
                self.assertEqual(1, result.returncode, result.stderr)
                self.assertEqual({'status': 'stale', 'changed': [name]}, json.loads(result.stdout))
                self.assertNotIn('start_line', result.stdout)
                path.write_bytes(original)

    def test_ignored_external_git_and_symlink_sources_are_rejected(self):
        private = self.root / 'private'
        private.mkdir()
        (private / 'secret.txt').write_text('PRIVATE_SYNTHETIC_TEXT')
        (self.root / 'alias.txt').symlink_to(private / 'secret.txt')
        for name in ['private/secret.txt', 'alias.txt', '.git/config', '../outside.txt']:
            result = self.cli('save', self.state, name)
            self.assertNotEqual(0, result.returncode)
            self.assertEqual('', result.stdout)
            self.assertNotIn('PRIVATE_SYNTHETIC_TEXT', result.stderr)
        self.assertFalse((self.root / self.state).exists())

    def test_bad_ranges_and_nonlocal_state_are_rejected(self):
        for options in [('--start', '0'), ('--end', '9'), ('--start', '3', '--end', '1')]:
            result = self.save(*options)
            self.assertNotEqual(0, result.returncode)
        result = self.cli('save', 'public-memory.json', 'source.kt')
        self.assertNotEqual(0, result.returncode)
        self.assertFalse((self.root / 'public-memory.json').exists())
        (self.root / 'source.kt').write_bytes(b'\xff')
        self.assertNotEqual(0, self.save().returncode)

    def test_invalid_memory_cannot_be_reused(self):
        self.assertEqual(0, self.save().returncode)
        path = self.root / self.state
        original = path.read_text()
        for change in [{'version': 2}, {'start_line': True}, {'dependencies': None},
                       {'source': {'path': '.git/config', 'sha256': '0' * 64}},
                       {'source': {'path': 'source.kt', 'sha256': 'bad'}}]:
            record = json.loads(original)
            record.update(change)
            path.write_text(json.dumps(record))
            result = self.cli('check', self.state)
            self.assertNotEqual(0, result.returncode)
            self.assertEqual('', result.stdout)
        path.write_text('PRIVATE_SYNTHETIC_MALFORMED_JSON')
        result = self.cli('check', self.state)
        self.assertNotEqual(0, result.returncode)
        self.assertNotIn('PRIVATE_SYNTHETIC', result.stderr)

    def test_root_must_have_git_ignore_policy(self):
        subdirectory = self.root / 'subdirectory'
        subdirectory.mkdir()
        result = subprocess.run([sys.executable, str(SCRIPT), '--root', str(subdirectory),
                                 'save', self.state, '../source.kt'], capture_output=True, text=True)
        self.assertNotEqual(0, result.returncode)
        self.assertEqual('', result.stdout)


if __name__ == '__main__':
    unittest.main()
