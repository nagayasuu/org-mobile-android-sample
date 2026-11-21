#!/usr/bin/env python3
"""Run the repository's local checks for an explicit change type."""

import argparse
from pathlib import Path
import subprocess
import sys


SCRIPTS = Path(__file__).resolve().parent


def checks_for(profile, documents):
    yield "staged-diff", ["git", "diff", "--cached", "--check"]
    yield "worktree-diff", ["git", "diff", "--check"]
    if profile in ("docs", "python"):
        yield "documentation", [sys.executable, str(SCRIPTS / "document_tools.py"), "check"]
    if documents:
        yield "explicit-documents", [
            sys.executable, str(SCRIPTS / "document_tools.py"), "check", "--", *documents
        ]
    if profile == "python":
        yield "python", [sys.executable, "-m", "unittest", "discover", "-s", "scripts/tests", "-q"]
    if profile == "android":
        yield "android", ["./gradlew", "--console=plain", "check", "assembleDebug"]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("profile", choices=("docs", "python", "android"))
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--document", action="append", default=[], metavar="PATH",
                        help="Also check this public Markdown file, including an untracked new document")
    args = parser.parse_args()
    if Path.cwd() != SCRIPTS.parent:
        parser.error("Run from the repository root")
    try:
        args.output_dir.mkdir(parents=True, exist_ok=False)
    except OSError:
        parser.error("Choose an unused output directory")
    for name, command in checks_for(args.profile, args.document):
        result = subprocess.run([sys.executable, str(SCRIPTS / "run_check.py"),
                                 "--output-dir", str(args.output_dir / name), "--", *command])
        if result.returncode:
            print(f"{name} stopped the {args.profile} profile", file=sys.stderr)
            return result.returncode
    return 0


if __name__ == "__main__":
    sys.exit(main())
