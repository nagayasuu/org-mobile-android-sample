#!/usr/bin/env python3
"""Validate this repository's commit convention without third-party packages."""

import argparse
import json
from pathlib import Path
import re
import subprocess
import sys


HEADER = re.compile(
    r"(?P<type>feat|fix|docs|refactor|test|build|ci|chore)"
    r"(?:\([^()\s]+\))?(?P<breaking>!)?: (?P<subject>\S.*)"
)
OID = re.compile(r"(?:[0-9a-f]{40}|[0-9a-f]{64})")


def validate(message):
    """Return actionable errors; do not echo potentially private message text."""
    lines = message.splitlines()
    if not lines or not lines[0].strip():
        return ["1行目: 要約が必要です。"]

    errors = []
    header = lines[0]
    match = HEADER.fullmatch(header)
    if not match:
        errors.append("1行目: type(scope): 要約 の形式と規定の type を使ってください。")
    elif match["subject"].strip().casefold() in {"修正", "update"}:
        errors.append("1行目: 変更内容が分かる具体的な要約を書いてください。")
    if header != header.rstrip():
        errors.append("1行目: 末尾の空白を除いてください。")
    if len(header) > 50:
        errors.append("1行目: type・scope を含め50文字以内にしてください。")
    if len(lines) > 1 and lines[1]:
        errors.append("2行目: 要約と本文の間に空行を置いてください。")
    for number, line in enumerate(lines[1:], 2):
        if len(line) > 72:
            errors.append(f"{number}行目: 本文・フッターは各行72文字以内にしてください。")

    breaking_lines = [line for line in lines[2:] if line.startswith("BREAKING CHANGE:")]
    breaking = bool(breaking_lines)
    if any(not re.match(r"^BREAKING CHANGE: \S", line) for line in breaking_lines):
        errors.append("BREAKING CHANGE: の後に説明を書いてください。")
    if match and bool(match["breaking"]) != breaking:
        errors.append("破壊的変更は要約の ! と本文の BREAKING CHANGE: 説明 を併記してください。")
    return errors


def git(*args, input=None):
    return subprocess.run(
        ["git", *args], input=input, encoding="utf-8", errors="strict",
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True,
    ).stdout


def hook_message(message):
    # Match Git's editor comments (including a configured comment character)
    # and exclude the verbose diff below its scissors marker.
    scissors = git(
        "stripspace", "--comment-lines",
        input="------------------------ >8 ------------------------\n",
    ).rstrip("\n")
    lines = message.splitlines(keepends=True)
    for index, line in enumerate(lines):
        if line.rstrip("\r\n") == scissors:
            lines = lines[:index]
            break
    return git("stripspace", "--strip-comments", input="".join(lines))


def revision_message(revision):
    oid = git("rev-parse", "--verify", "--end-of-options", f"{revision}^{{commit}}").strip()
    parents = git("rev-list", "--parents", "-n", "1", oid).split()
    if len(parents) > 2:
        return None  # Preserve the shared-branch merge workflow.
    return git("show", "-s", "--format=%B", oid)


def event_messages(event):
    if "pull_request" in event:
        pr = event["pull_request"]
        yield "PR title", pr["title"]
        base, head = pr["base"]["sha"], pr["head"]["sha"]
    else:
        base, head = event["before"], event["after"]
    if not OID.fullmatch(base) or not OID.fullmatch(head) or set(head) == {"0"}:
        raise ValueError("イベントのコミット SHA が不正です。")
    if set(base) == {"0"}:
        revisions = [head]  # A new branch has no previous tip.
    else:
        revisions = git("rev-list", "--reverse", "--no-merges", f"{base}..{head}").split()
    for revision in revisions:
        message = revision_message(revision)
        if message is not None:
            yield f"commit {revision[:12]}", message


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--message-file", help="UTF-8 message file, or - for stdin")
    source.add_argument("--revision", help="Existing commit, e.g. HEAD")
    source.add_argument("--github-event", type=Path, help="GitHub event JSON file")
    parser.add_argument("--hook", action="store_true", help="Clean Git editor comments")
    args = parser.parse_args()
    if args.hook and args.message_file is None:
        parser.error("--hook requires --message-file")

    try:
        if args.message_file is not None:
            message = (sys.stdin.buffer.read().decode("utf-8") if args.message_file == "-"
                       else Path(args.message_file).read_text(encoding="utf-8"))
            messages = [("message", hook_message(message) if args.hook else message)]
        elif args.revision is not None:
            message = revision_message(args.revision)
            messages = [] if message is None else [("commit", message)]
        else:
            messages = event_messages(json.loads(args.github_event.read_text(encoding="utf-8")))

        failed = False
        count = 0
        for label, message in messages:
            count += 1
            for error in validate(message):
                print(f"{label}: {error}", file=sys.stderr)
                failed = True
        if failed:
            print("規約: docs/git-workflow.md の『コミット規約』を参照してください。", file=sys.stderr)
            return 1
        print(f"Commit message checks passed ({count}).")
        return 0
    except (OSError, UnicodeError, ValueError, KeyError, TypeError, subprocess.CalledProcessError):
        print("検証入力または Git 履歴を読み取れません。UTF-8・イベント・取得済み履歴を確認してください。",
              file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
