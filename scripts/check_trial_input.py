#!/usr/bin/env python3
"""Check frozen evaluation inputs locally; never invoke a model or print inputs."""

import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import time


class InputError(ValueError):
    """A public error code without source data."""


def require(condition, code):
    if not condition:
        raise InputError(code)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def check(plan, root):
    """Paths are relative to root; hashes cover raw bytes, ranges are 1-based inclusive."""
    require(isinstance(plan, dict) and plan.get('schema_version') == 1, 'schema')
    revision = plan.get('revision')
    require(isinstance(revision, str) and re.fullmatch(r'[0-9a-f]{40}', revision), 'revision-format')
    actual = subprocess.run(['git', '-C', str(root), 'rev-parse', 'HEAD'],
                            capture_output=True, check=True, text=True).stdout.strip()
    require(actual == revision, 'revision-mismatch')

    def read(item):
        require(isinstance(item, dict), 'file-schema')
        path, expected = item.get('path'), item.get('sha256')
        require(isinstance(path, str) and path and not Path(path).is_absolute(), 'path')
        target = (root / path).resolve()
        require(target.is_relative_to(root.resolve()), 'path-outside-root')
        require(isinstance(expected, str) and re.fullmatch(r'[0-9a-f]{64}', expected), 'hash-format')
        data = target.read_bytes()
        require(digest(data) == expected, 'hash-mismatch')
        text = data.decode('utf-8')
        require(text.strip(), 'empty-input')
        return text

    prompt = read(plan.get('prompt'))
    require(prompt.endswith('\n'), 'prompt-final-newline')
    snippets = plan.get('snippets')
    require(isinstance(snippets, list) and snippets, 'snippets-required')
    extracted = []
    for item in snippets:
        source = read(item)
        start, end = item.get('start_line'), item.get('end_line')
        lines = source.splitlines(keepends=True)
        require(type(start) is int and type(end) is int and 1 <= start <= end <= len(lines), 'range')
        snippet = ''.join(lines[start - 1:end])
        require(snippet.strip(), 'empty-snippet')
        require(digest(snippet.encode('utf-8')) == item.get('snippet_sha256'), 'snippet-hash')
        require(snippet.endswith('\n'), 'snippet-final-newline')
        require(snippet in prompt, 'snippet-missing')
        extracted.append(snippet)
    for field in ('operations', 'assertions'):
        values = plan.get(field)
        require(isinstance(values, list) and values, field + '-required')
        for value in values:
            require(isinstance(value, str) and value.strip(), field + '-empty')
            require(value in prompt, field + '-missing')
            if field == 'assertions':
                require(any(value in snippet for snippet in extracted), 'assertion-not-in-source')
    files = plan.get('files')
    require(isinstance(files, list), 'files-required')
    for item in files:
        read(item)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('plan', type=Path)
    parser.add_argument('--root', type=Path, default=Path.cwd())
    args = parser.parse_args()
    began = time.monotonic()
    try:
        check(json.loads(args.plan.read_text(encoding='utf-8')), args.root)
        result = {'ok': True}
    except (ValueError, OSError, RuntimeError, subprocess.SubprocessError) as error:
        # File errors and decoding errors can contain private paths or text.
        code = str(error) if isinstance(error, InputError) else 'unreadable-or-invalid-input'
        result = {'ok': False, 'error': code}
    result['check_seconds'] = time.monotonic() - began
    print(json.dumps(result))
    return 0 if result['ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
