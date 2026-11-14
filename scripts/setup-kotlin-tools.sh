#!/usr/bin/env bash
set -eu

task_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
task_destination=${1:-"$task_root/.local/kotlin-tools"}
task_destination=$(python3 - "$task_root" "$task_destination" <<'PY'
from pathlib import Path
import sys
root, destination = Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve()
local = (root / '.local').resolve()
if not local.is_relative_to(root) or not destination.is_relative_to(local) or destination == local:
    raise SystemExit('destination must be under repository .local/')
if destination.exists():
    raise SystemExit('choose an unused destination; existing tools are not overwritten')
print(destination)
PY
)

grammar_revision=d6af96d2e23ef0a8ff5ab512864378cf08fba311
mkdir -p -- "$task_destination/source"
python3 -m venv "$task_destination/venv"
"$task_destination/venv/bin/python" -m pip install --disable-pip-version-check \
  -r "$task_root/scripts/requirements-kotlin-tools.txt"
gh api "repos/fwcd/tree-sitter-kotlin/tarball/$grammar_revision" > "$task_destination/source.tar.gz"
tar -xzf "$task_destination/source.tar.gz" --strip-components=1 -C "$task_destination/source"
cc -shared -fPIC -O2 -I "$task_destination/source/src" \
  "$task_destination/source/src/parser.c" "$task_destination/source/src/scanner.c" \
  -o "$task_destination/kotlin.so"
printf 'Kotlin declaration tools installed at the requested local destination.\n'
