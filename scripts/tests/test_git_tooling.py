"""Exercise message policy, real Git hooks, and GitHub event validation."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

SCRIPTS = Path(__file__).resolve().parents[1]
ROOT = SCRIPTS.parent
sys.path.insert(0, str(SCRIPTS))
from check_commit_message import validate


class MessagePolicyTest(unittest.TestCase):
    def test_accepts_repository_convention_and_unicode_boundaries(self):
        messages = [
            f"{kind}: 動作を確認する" for kind in
            ("feat", "fix", "docs", "refactor", "test", "build", "ci", "chore")
        ] + [
            "fix(reader): 読み込みを修正する\n\n失敗後も再選択できるようにする。\n\nRefs: #123\n",
            "feat(reader)!: 保存形式を変更する\n\nBREAKING CHANGE: 新形式へ移行する。\n",
            "feat!: 形式を変更する\n\nBREAKING CHANGE: 移行手順を記録する。",
            "docs: " + "あ" * 44 + "\n\n" + "あ" * 72,
        ]
        for message in messages:
            with self.subTest(message=message):
                self.assertEqual([], validate(message))

    def test_rejects_invalid_headers_and_body_layout(self):
        for message in (
            "", "\nfix: 修正する", "update", "perf: 高速化する", "docs(): 説明する",
            "fix: ", "fix: 修正", "chore: UPDATE", "fix: 直す ",
            "fix: 直す\n理由を記録する", "docs: " + "あ" * 45,
            "docs: 説明する\n\n" + "あ" * 73,
            "docs: 説明する\n\nhttps://example.com/" + "a" * 73,
            "feat!: 形式を変更する", "feat!: 形式を変更する\n\nBREAKING CHANGE: ",
            "feat: 形式を変更する\n\nBREAKING CHANGE:",
            "feat: 形式を変更する\n\nBREAKING CHANGE: 移行する。",
        ):
            with self.subTest(message=message):
                self.assertTrue(validate(message))


class GitIntegrationTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="git tooling ")
        self.addCleanup(self.temp.cleanup)
        self.repo = Path(self.temp.name)
        self.env = os.environ.copy()
        for key in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_COMMON_DIR"):
            self.env.pop(key, None)
        self.env.update(GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull)
        (self.repo / "scripts").mkdir()
        for name in ("check_commit_message.py", "install-git-hooks.sh"):
            shutil.copy2(SCRIPTS / name, self.repo / "scripts" / name)
        shutil.copytree(ROOT / ".githooks", self.repo / ".githooks")
        self.git("init", "--initial-branch=main")
        self.git("config", "user.name", "Git tooling test")
        self.git("config", "user.email", "test@example.invalid")

    def run_command(self, *args, check=True, input=None):
        return subprocess.run(
            args, cwd=self.repo, env=self.env, input=input, text=True,
            encoding="utf-8", stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=check,
        )

    def git(self, *args, **kwargs):
        return self.run_command("git", *args, **kwargs)

    def install(self, **kwargs):
        return self.run_command("sh", "scripts/install-git-hooks.sh", **kwargs)

    def commit(self, message, **kwargs):
        return self.git("commit", "--allow-empty", "-m", message, **kwargs)

    def event_check(self, event):
        path = self.repo / "event.json"
        path.write_text(json.dumps(event), encoding="utf-8")
        return self.run_command(
            sys.executable, "scripts/check_commit_message.py", "--github-event", str(path),
            check=False,
        )

    def test_install_is_repeatable_and_hook_blocks_bad_commit_and_amend(self):
        self.install()
        self.install()
        self.assertEqual(".githooks", self.git("config", "--local", "core.hooksPath").stdout.strip())
        self.assertNotEqual(0, self.commit("invalid", check=False).returncode)
        self.commit("fix: 読み込みを修正する")
        self.assertNotEqual(0, self.git("commit", "--amend", "-m", "invalid", check=False).returncode)
        self.assertEqual("fix: 読み込みを修正する", self.git("log", "-1", "--format=%s").stdout.strip())

    def test_existing_hook_path_is_preserved(self):
        self.git("config", "core.hooksPath", "existing hooks")
        self.assertNotEqual(0, self.install(check=False).returncode)
        self.assertEqual("existing hooks", self.git("config", "core.hooksPath").stdout.strip())

    def test_existing_default_hook_is_preserved(self):
        hook = self.repo / ".git/hooks/pre-commit"
        hook.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        hook.chmod(0o755)
        self.assertNotEqual(0, self.install(check=False).returncode)
        self.assertEqual(1, self.git("config", "--local", "--get", "core.hooksPath", check=False).returncode)
        self.assertTrue(hook.exists())

    def test_pre_commit_checks_staged_content_only(self):
        self.install()
        path = self.repo / "sample.txt"
        path.write_text("valid\n", encoding="utf-8")
        self.git("add", "sample.txt")
        path.write_text("unstaged trailing space \n", encoding="utf-8")
        self.commit("test: 差分の確認を追加する")
        self.git("add", "sample.txt")
        self.assertNotEqual(0, self.commit("test: 空白の確認を追加する", check=False).returncode)

    def test_editor_comments_and_verbose_diff_use_configured_comment_character(self):
        self.install()
        self.git("config", "core.commentChar", ";")
        message = self.repo / "message.txt"
        message.write_text(
            "docs: 説明を更新する\n\n理由を残す。\n; " + "x" * 90 +
            "\n; ------------------------ >8 ------------------------\n" + "diff " * 90,
            encoding="utf-8",
        )
        result = self.run_command(".githooks/commit-msg", str(message), check=False)
        self.assertEqual(0, result.returncode, result.stderr)

    def test_ci_catches_bypassed_hook_in_entire_pr_and_title_edits(self):
        self.install()
        self.commit("chore: 初期状態を作る")
        base = self.git("rev-parse", "HEAD").stdout.strip()
        self.commit("fix: 読み込みを修正する")
        head = self.git("rev-parse", "HEAD").stdout.strip()
        event = {"pull_request": {
            "title": "fix: 読み込みを修正する", "base": {"sha": base}, "head": {"sha": head},
        }}
        self.assertEqual(0, self.event_check(event).returncode)
        event["pull_request"]["title"] = "invalid"
        self.assertNotEqual(0, self.event_check(event).returncode)
        event["pull_request"]["title"] = "fix: 読み込みを修正する"
        self.git("-c", "core.hooksPath=/dev/null", "commit", "--allow-empty", "-m", "invalid")
        self.commit("fix: 後続の修正を追加する")
        event["pull_request"]["head"]["sha"] = self.git("rev-parse", "HEAD").stdout.strip()
        self.assertNotEqual(0, self.event_check(event).returncode)

    def test_existing_invalid_history_is_not_checked_again(self):
        self.git("-c", "core.hooksPath=/dev/null", "commit", "--allow-empty", "-m", "legacy")
        base = self.git("rev-parse", "HEAD").stdout.strip()
        self.install()
        self.commit("fix: 読み込みを修正する")
        head = self.git("rev-parse", "HEAD").stdout.strip()
        self.assertEqual(0, self.event_check({"before": base, "after": head}).returncode)

    def test_push_checks_all_new_commits_and_handles_new_branch(self):
        self.install()
        self.commit("chore: 初期状態を作る")
        base = self.git("rev-parse", "HEAD").stdout.strip()
        self.commit("fix: 読み込みを修正する")
        head = self.git("rev-parse", "HEAD").stdout.strip()
        for before in (base, "0" * 40):
            self.assertEqual(0, self.event_check({"before": before, "after": head}).returncode)
        self.git("-c", "core.hooksPath=/dev/null", "commit", "--allow-empty", "-m", "invalid")
        self.commit("fix: 後続の修正を追加する")
        head = self.git("rev-parse", "HEAD").stdout.strip()
        self.assertNotEqual(0, self.event_check({"before": base, "after": head}).returncode)

    def test_merge_commits_work_locally_and_ci_checks_their_non_merge_commits(self):
        self.install()
        self.commit("chore: 初期状態を作る")
        base = self.git("rev-parse", "HEAD").stdout.strip()
        self.git("switch", "-c", "topic")
        self.commit("fix: 読み込みを修正する")
        self.git("switch", "main")
        self.commit("docs: 説明を追加する")
        self.git("merge", "--no-ff", "--no-edit", "topic")
        head = self.git("rev-parse", "HEAD").stdout.strip()
        self.assertEqual(0, self.event_check({"before": base, "after": head}).returncode)

    def test_invalid_utf8_and_missing_history_fail_without_echoing_input(self):
        message = self.repo / "message.txt"
        message.write_bytes(b"\xff")
        result = self.run_command(
            sys.executable, "scripts/check_commit_message.py", "--message-file", str(message),
            check=False,
        )
        self.assertNotEqual(0, result.returncode)
        self.assertNotIn("Traceback", result.stderr)
        self.assertNotEqual(0, self.event_check({"before": "a" * 40, "after": "b" * 40}).returncode)
        self.assertNotEqual(0, self.event_check({}).returncode)


if __name__ == "__main__":
    unittest.main()
