"""CLI acceptance tests with public synthetic documents and reports."""

import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


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

    def context_fixture(self):
        self.write('AGENTS.md', '# Instructions\nAGENT_MARKER\n')
        sections = [
            ('workflow-reading', '作業に応じた読み方', 'READING_TABLE'),
            ('change-steps', '変更の共通手順', 'CHANGE_STEPS'),
            ('', '共通の検証', 'REQUIRED_CHECKS'),
            ('agent-context', 'agent の入力と出力を絞る', 'CONTEXT_RULES'),
            ('agent-review', 'agent によるレビュー手順', 'REVIEW_RULES'),
            ('review-checklist', 'レビューチェックリスト',
             '### 記録と判定\nUNCONFIRMED_RULE\n' + '\n'.join(f'R{i:02}: criterion' for i in range(1, 31))),
            ('completion', '完了条件と報告', 'COMPLETION_RULES'),
            ('', '対象固有の節', 'UNRELATED_SECTION'),
        ]
        for name, selected in [
            ('docs/workflow/development.md', [0, 1, 6, 7]),
            ('docs/workflow/verification.md', [2]),
            ('docs/guides/agent-tools.md', [3]),
            ('docs/workflow/review.md', [4, 5]),
        ]:
            self.write(name, '\n'.join(
                (f'<a id="{anchor}"></a>\n\n' if anchor else '') + f'## {title}\n{body}\n'
                for anchor, title, body in (sections[index] for index in selected)))
        self.write('docs/workflow/git.md', '## 1. 基本方針\nGIT_POLICY\n'
                   '## 6. Codex が作業するときの手順\nGIT_STEPS\n')

    def test_context_change_returns_complete_common_rules_with_original_hashes(self):
        self.context_fixture()
        result = self.docs('context', 'change')
        self.assertEqual(0, result.returncode, result.stderr)
        metadata = json.loads(result.stdout.splitlines()[0])
        self.assertEqual('change', metadata['profile'])
        self.assertEqual(6, len(metadata['documents']))
        for document in metadata['documents']:
            self.assertEqual(hashlib.sha256((self.root / document['path']).read_bytes()).hexdigest(), document['sha256'])
        for marker in ['AGENT_MARKER', 'READING_TABLE', 'CHANGE_STEPS', 'REQUIRED_CHECKS', 'CONTEXT_RULES',
                       'REVIEW_RULES', 'UNCONFIRMED_RULE', 'COMPLETION_RULES', 'GIT_POLICY', 'GIT_STEPS',
                       *(f'R{i:02}: criterion' for i in range(1, 31))]:
            self.assertEqual(1, result.stdout.count(marker), marker)
        self.assertNotIn('UNRELATED_SECTION', result.stdout)

    def test_context_review_retains_decision_rules_without_change_steps(self):
        self.context_fixture()
        result = self.docs('context', 'review')
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn('UNCONFIRMED_RULE', result.stdout)
        self.assertIn('R30: criterion', result.stdout)
        self.assertNotIn('CHANGE_STEPS', result.stdout)

    def test_context_rejects_combined_size_even_when_each_document_fits(self):
        self.context_fixture()
        # Every individual numbered document is below 2,000 characters;
        # their combined payload and provenance exceed that shared budget.
        result = self.docs('context', 'change', '--max-chars', '2000')
        self.assertNotEqual(0, result.returncode)
        self.assertEqual('', result.stdout)
        self.assertIn('context exceeds', result.stderr)

    def test_context_failure_is_atomic_for_missing_ambiguous_and_large_inputs(self):
        for failure in ['missing', 'ambiguous', 'limit']:
            with self.subTest(failure=failure):
                self.context_fixture()
                if failure == 'missing':
                    (self.root / 'docs/workflow/git.md').unlink()
                elif failure == 'ambiguous':
                    self.write('docs/workflow/git.md', '## 1. 基本方針\nA\n## 1. 基本方針\nB\n'
                               '## 6. Codex が作業するときの手順\nC\n')
                result = self.docs('context', 'change', *(['--max-chars', '10'] if failure == 'limit' else []))
                self.assertNotEqual(0, result.returncode)
                self.assertEqual('', result.stdout)

    def context_state_fixture(self):
        self.context_fixture()
        subprocess.run(['git', 'init', '-q', str(self.root)], check=True)
        self.write('.gitignore', '.local/\n')

    def cached_context(self, *args, reader='task-author'):
        return self.docs('context', 'change', '--state', '.local/context.json',
                         '--reader', reader, *args)

    def test_context_includes_multiple_documents_and_deduplicates_overlapping_sections(self):
        self.context_fixture()
        self.write('extra.md', '# Extra\nPARENT\n## Child\nCHILD\n')
        result = self.docs('context', 'change',
                           '--include', 'docs/workflow/development.md', '対象固有の節', 'workflow-reading',
                           '--include', 'extra.md', 'Extra', 'Child',
                           '--include', 'extra.md', 'Child')
        self.assertEqual(0, result.returncode, result.stderr)
        for marker in ['UNRELATED_SECTION', 'PARENT', 'CHILD', 'R01: criterion', 'R30: criterion']:
            self.assertEqual(1, result.stdout.count(marker), marker)
        self.assertEqual(7, len(json.loads(result.stdout.splitlines()[0])['documents']))

    def test_context_receipt_reuses_only_delivered_ranges_and_expands_without_repeating(self):
        self.context_state_fixture()
        self.write('extra.md', '# Extra\n## First\nFIRST_BODY\n' + 'X' * 6000 + '\n## Second\nSECOND_BODY\n')
        first = self.cached_context('--include', 'extra.md', 'First')
        self.assertEqual(0, first.returncode, first.stderr)
        state = self.root / '.local/context.json'
        saved = state.read_bytes()
        self.assertNotIn(b'FIRST_BODY', saved)
        again = self.cached_context('--include', 'extra.md', 'First', '--max-chars', '4000')
        self.assertEqual(0, again.returncode, again.stderr)
        self.assertEqual('unchanged', json.loads(again.stdout)['status'])
        self.assertNotIn('AGENT_MARKER', again.stdout)
        self.assertNotIn('FIRST_BODY', again.stdout)
        self.assertEqual(saved, state.read_bytes())
        expanded = self.cached_context('--include', 'extra.md', 'Extra')
        self.assertEqual(0, expanded.returncode, expanded.stderr)
        self.assertIn('SECOND_BODY', expanded.stdout)
        self.assertNotIn('FIRST_BODY', expanded.stdout)
        self.assertNotIn('AGENT_MARKER', expanded.stdout)

    def test_context_changed_file_invalidates_all_its_old_ranges(self):
        self.context_state_fixture()
        source = self.write('extra.md', '# Extra\n## First\nFIRST_BODY\n## Second\nOLD_BODY\n')
        self.assertEqual(0, self.cached_context('--include', 'extra.md', 'Extra').returncode)
        source.write_text(source.read_text() + 'NEW_BODY\n')
        result = self.cached_context('--include', 'extra.md', 'First')
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn('FIRST_BODY', result.stdout)
        self.assertNotIn('AGENT_MARKER', result.stdout)
        result = self.cached_context('--include', 'extra.md', 'Second')
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn('OLD_BODY', result.stdout)
        self.assertIn('NEW_BODY', result.stdout)

    def test_context_public_symlink_alias_is_deduplicated_and_receipt_remains_reusable(self):
        self.context_state_fixture()
        target = self.write('docs/shared.md', '# Instructions\nAGENT_MARKER\n')
        (self.root / 'AGENTS.md').unlink()
        (self.root / 'AGENTS.md').symlink_to(target)
        first = self.cached_context('--include', 'docs/shared.md', 'Instructions')
        self.assertEqual(0, first.returncode, first.stderr)
        self.assertEqual(1, first.stdout.count('AGENT_MARKER'))
        again = self.cached_context('--include', 'AGENTS.md', 'Instructions')
        self.assertEqual(0, again.returncode, again.stderr)
        self.assertEqual('unchanged', json.loads(again.stdout)['status'])

    def test_context_refresh_and_independent_reader_do_not_trust_previous_delivery(self):
        self.context_state_fixture()
        self.assertEqual(0, self.cached_context().returncode)
        state = self.root / '.local/context.json'
        before = state.read_bytes()
        other = self.cached_context(reader='task-reviewer')
        self.assertNotEqual(0, other.returncode)
        self.assertEqual('', other.stdout)
        self.assertEqual(before, state.read_bytes())
        refreshed = self.cached_context('--refresh')
        self.assertEqual(0, refreshed.returncode, refreshed.stderr)
        self.assertIn('AGENT_MARKER', refreshed.stdout)
        self.assertIn('R30: criterion', refreshed.stdout)

    def test_context_errors_are_atomic_for_receipt_and_all_includes(self):
        self.context_state_fixture()
        self.assertEqual(0, self.cached_context().returncode)
        state = self.root / '.local/context.json'
        before = state.read_bytes()
        self.write('ambiguous.md', '# Same\nONE\n# Same\nTWO\n')
        self.write('bad.md', '# Bad\n').write_bytes(b'\xff')
        for options in [('--include', 'missing.md', 'Missing'),
                        ('--include', 'ambiguous.md', 'Same'),
                        ('--include', 'bad.md', 'Bad'),
                        ('--include', '.local/private.md', 'Secret'),
                        ('--include', 'extra.md'), ('--max-chars', '10')]:
            with self.subTest(options=options):
                result = self.cached_context(*options)
                self.assertNotEqual(0, result.returncode)
                self.assertEqual('', result.stdout)
                self.assertEqual(before, state.read_bytes())
        (self.root / 'docs/workflow/git.md').unlink()
        result = self.cached_context()
        self.assertNotEqual(0, result.returncode)
        self.assertEqual('', result.stdout)
        self.assertEqual(before, state.read_bytes())

    def test_context_rejects_malformed_receipts_and_nonlocal_or_tracked_state(self):
        self.context_state_fixture()
        self.assertEqual(0, self.cached_context().returncode)
        state = self.root / '.local/context.json'
        original = json.loads(state.read_text())
        for damaged in ['{', json.dumps({**original, 'version': True}),
                        json.dumps({**original, 'documents': [{'path': '.local/secret.md'}]})]:
            with self.subTest(damaged=damaged):
                state.write_text(damaged)
                result = self.cached_context()
                self.assertNotEqual(0, result.returncode)
                self.assertEqual('', result.stdout)
                self.assertEqual(damaged, state.read_text())
        state.write_text(json.dumps(original))
        for value in ['outside.json', '../outside.json', '.git/context.json']:
            result = self.docs('context', 'change', '--state', value, '--reader', 'task-author')
            self.assertNotEqual(0, result.returncode)
            self.assertEqual('', result.stdout)
        subprocess.run(['git', '-C', str(self.root), 'add', '-f', '.local/context.json'], check=True)
        result = self.cached_context()
        self.assertNotEqual(0, result.returncode)
        self.assertEqual('', result.stdout)

    def test_context_new_required_section_and_invalid_coverage_are_not_silently_skipped(self):
        self.context_state_fixture()
        review = self.docs('context', 'review', '--state', '.local/context.json', '--reader', 'task-author')
        self.assertEqual(0, review.returncode, review.stderr)
        change = self.cached_context()
        self.assertEqual(0, change.returncode, change.stderr)
        self.assertIn('CHANGE_STEPS', change.stdout)
        self.assertNotIn('R30: criterion', change.stdout)
        state = self.root / '.local/context.json'
        record = json.loads(state.read_text())
        record['documents'][0]['ranges'] = [[1, 999999]]
        state.write_text(json.dumps(record))
        before = state.read_bytes()
        rejected = self.cached_context()
        self.assertNotEqual(0, rejected.returncode)
        self.assertEqual('', rejected.stdout)
        self.assertEqual(before, state.read_bytes())

    def test_context_state_rejects_symlink_escape_and_requires_explicit_scope_and_ignore(self):
        self.context_state_fixture()
        self.write('safe.json', 'SENTINEL')
        (self.root / '.local').mkdir()
        (self.root / '.local/state.json').symlink_to(self.root / 'safe.json')
        result = self.docs('context', 'change', '--state', '.local/state.json', '--reader', 'task-author')
        self.assertNotEqual(0, result.returncode)
        self.assertEqual('', result.stdout)
        self.assertEqual('SENTINEL', (self.root / 'safe.json').read_text())
        for options in [('--state', '.local/new.json'), ('--reader', 'task-author'), ('--refresh',)]:
            result = self.docs('context', 'change', *options)
            self.assertNotEqual(0, result.returncode)
            self.assertEqual('', result.stdout)
        (self.root / '.gitignore').write_text('')
        result = self.cached_context()
        self.assertNotEqual(0, result.returncode)
        self.assertEqual('', result.stdout)

    def test_context_receipt_is_not_advanced_if_stdout_write_or_flush_fails(self):
        self.context_state_fixture()
        self.assertEqual(0, self.cached_context().returncode)
        state = self.root / '.local/context.json'
        before = state.read_bytes()
        self.write('extra.md', '# Extra\nNEW_BODY\n')
        spec = importlib.util.spec_from_file_location('context_delivery_test', SCRIPTS / 'document_tools.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        for stage in ['write', 'flush']:
            stream = mock.Mock()
            getattr(stream, stage).side_effect = BrokenPipeError('consumer closed')
            with self.subTest(stage=stage), mock.patch.object(module.sys, 'stdout', stream):
                with self.assertRaises(BrokenPipeError):
                    module.context(module.Repository(self.root), 'change', 24000,
                                   [('extra.md', 'Extra')], '.local/context.json', 'task-author')
            self.assertEqual(before, state.read_bytes())

    def test_context_receipt_replace_failure_is_reported_without_advancing_state(self):
        self.context_state_fixture()
        self.assertEqual(0, self.cached_context().returncode)
        state = self.root / '.local/context.json'
        before = state.read_bytes()
        self.write('extra.md', '# Extra\nNEW_BODY\n')
        spec = importlib.util.spec_from_file_location('context_replace_test', SCRIPTS / 'document_tools.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        output = io.StringIO()
        with mock.patch.object(module.sys, 'stdout', output), \
                mock.patch.object(module.os, 'replace', side_effect=PermissionError('replace denied')):
            with self.assertRaises(PermissionError):
                module.context(module.Repository(self.root), 'change', 24000,
                               [('extra.md', 'Extra')], '.local/context.json', 'task-author')
        self.assertIn('NEW_BODY', output.getvalue())
        self.assertEqual(before, state.read_bytes())
        self.assertEqual([state], list(state.parent.iterdir()))

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
