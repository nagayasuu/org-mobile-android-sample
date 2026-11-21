#!/usr/bin/env python3
"""Report the local Git state before starting work or committing."""

import argparse
import json
from pathlib import Path
import subprocess
import sys


OPERATIONS = {
    "MERGE_HEAD": "merge", "CHERRY_PICK_HEAD": "cherry-pick", "REVERT_HEAD": "revert",
    "BISECT_START": "bisect", "sequencer": "sequencer",
}
CONFLICTS = {"DD", "AU", "UD", "UA", "DU", "AA", "UU"}


def git(*args, allowed=(0,)):
    result = subprocess.run(["git", "--no-optional-locks", *args], capture_output=True, timeout=30)
    if result.returncode not in allowed:
        raise ValueError("Cannot read Git state")
    # Preserve unusual filenames without emitting raw control characters.
    return result.stdout.decode("utf-8", errors="surrogateescape")


def changes(raw):
    groups = {name: [] for name in ("staged", "unstaged", "untracked", "conflicted")}
    records = iter(raw.split("\0"))
    for entry in records:
        if not entry:
            continue
        code, path = entry[:2], entry[3:]
        if "R" in code or "C" in code:
            next(records)  # Porcelain v1 -z puts the destination first.
        if code == "??":
            groups["untracked"].append(path)
        elif code in CONFLICTS:
            groups["conflicted"].append(path)
        else:
            if code[0] != " ":
                groups["staged"].append(path)
            if code[1] != " ":
                groups["unstaged"].append(path)
    return groups


def inspect():
    branch = git("symbolic-ref", "--quiet", "--short", "HEAD", allowed=(0, 1)).rstrip("\n")
    head = git("rev-parse", "--verify", "--quiet", "HEAD", allowed=(0, 1)).strip()
    base = git("rev-parse", "--verify", "--quiet", "refs/remotes/origin/main^{commit}", allowed=(0, 1)).strip()
    markers = [*OPERATIONS, "rebase-merge", "rebase-apply", "rebase-apply/applying"]
    paths = [git("rev-parse", "--git-path", marker).removesuffix("\n") for marker in markers]
    present = {marker for marker, path in zip(markers, paths) if Path(path).exists()}
    operations = [label for marker, label in OPERATIONS.items() if marker in present]
    if "rebase-merge" in present or "rebase-apply" in present:
        operations.append("am" if "rebase-apply/applying" in present else "rebase")
    counts = None
    if head and base:
        ahead, behind = map(int, git("rev-list", "--left-right", "--count", f"{head}...{base}").split())
        counts = dict(ahead=ahead, behind=behind)
    groups = changes(git("status", "--porcelain=v1", "-z", "--untracked-files=all"))
    return dict(branch=branch or None, head=head or None, operations=operations,
                origin_main=base or None, relative_to_origin_main=counts), groups


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--paths", action="store_true", help="Include local filenames for the operator")
    args = parser.parse_args()
    try:
        result, groups = inspect()
    except (OSError, ValueError, StopIteration, subprocess.TimeoutExpired) as error:
        print(f"Git preflight failed ({type(error).__name__})", file=sys.stderr)
        return 2
    result["changes"] = {key: len(paths) for key, paths in groups.items()}
    if args.paths:
        result["paths"] = groups
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
