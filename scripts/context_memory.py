#!/usr/bin/env python3
"""Record public source ranges locally; reject reuse after source or dependency changes."""

import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess

from document_tools import Repository, ROOT


def state_path(repository, value):
    local = (repository.root / '.local').resolve()
    path = (repository.root / value).resolve()
    if not local.is_relative_to(repository.root) or not path.is_relative_to(local) or path == local:
        raise ValueError('memory must be stored under repository .local/')
    return path


def fingerprint(repository, value):
    path = repository.path(value)
    raw = path.read_bytes()
    text = raw.decode('utf-8')
    return {'path': path.relative_to(repository.root).as_posix(),
            'sha256': hashlib.sha256(raw).hexdigest()}, len(text.splitlines())


def save(repository, args):
    path = state_path(repository, args.state)
    source, length = fingerprint(repository, args.path)
    end = args.end if args.end is not None else length
    if not 1 <= args.start <= end <= length:
        raise ValueError('read range must be within a nonempty source')
    dependencies = [fingerprint(repository, name)[0] for name in args.depends]
    names = [source['path'], *(item['path'] for item in dependencies)]
    if len(set(names)) != len(names):
        raise ValueError('source and dependencies must be distinct')
    record = {'version': 1, 'source': source, 'start_line': args.start, 'end_line': end,
              'identifier': args.identifier, 'dependencies': dependencies}
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8') as stream:
        stream.write(json.dumps(record, ensure_ascii=False, indent=2) + '\n')
    return {'status': 'recorded', 'source': source, 'start_line': args.start, 'end_line': end}


def check(repository, value):
    record = json.loads(state_path(repository, value).read_text(encoding='utf-8'))
    if not isinstance(record, dict) or record.get('version') != 1 or type(record['version']) is not int:
        raise ValueError('unsupported memory format')
    dependencies = record.get('dependencies')
    if not isinstance(dependencies, list) or not isinstance(record.get('source'), dict):
        raise ValueError('invalid source or dependency metadata')
    for key in ('start_line', 'end_line'):
        if type(record.get(key)) is not int:
            raise ValueError('invalid read range')
    if not 1 <= record['start_line'] <= record['end_line']:
        raise ValueError('invalid read range')
    if not isinstance(record.get('identifier'), str):
        raise ValueError('invalid identifier')
    changed, names = [], set()
    for item in [record['source'], *dependencies]:
        if (not isinstance(item, dict) or not isinstance(item.get('path'), str)
                or not isinstance(item.get('sha256'), str)
                or not re.fullmatch('[0-9a-f]{64}', item['sha256'])):
            raise ValueError('invalid fingerprint')
        path = repository.path(item['path'])
        name = path.relative_to(repository.root).as_posix()
        if name in names:
            raise ValueError('duplicate source or dependency')
        names.add(name)
        try:
            current, length = fingerprint(repository, item['path'])
        except (FileNotFoundError, UnicodeError):
            changed.append(name)
            continue
        if current != item or (item == record['source'] and record['end_line'] > length):
            changed.append(name)
    if changed:
        return {'status': 'stale', 'changed': changed}
    return {'status': 'unchanged', 'source': record['source'],
            'start_line': record['start_line'], 'end_line': record['end_line'],
            'identifier': record['identifier'], 'dependencies': dependencies}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT)
    operations = parser.add_subparsers(dest='operation', required=True)
    writer = operations.add_parser('save', help='Record a range already read; never overwrite')
    writer.add_argument('state', help='New .local/ JSON path')
    writer.add_argument('path', help='Public UTF-8 source path')
    writer.add_argument('--start', type=int, default=1)
    writer.add_argument('--end', type=int)
    writer.add_argument('--identifier', default='')
    writer.add_argument('--depends', action='append', default=[])
    reader = operations.add_parser('check', help='Check all hashes; stale exits 1 without source text')
    reader.add_argument('state')
    args = parser.parse_args()
    try:
        repository = Repository(args.root)
        git_root = subprocess.run(['git', '-C', str(repository.root), 'rev-parse', '--show-toplevel'],
                                  capture_output=True, text=True, check=True)
        if Path(git_root.stdout.strip()).resolve() != repository.root:
            raise ValueError('root must be the Git repository root')
        result = save(repository, args) if args.operation == 'save' else check(repository, args.state)
        print(json.dumps(result, ensure_ascii=False))
        return 1 if result['status'] == 'stale' else 0
    except (OSError, UnicodeError, ValueError, subprocess.CalledProcessError) as error:
        # Memory may be malformed; do not echo its contents.
        parser.exit(2, f'{type(error).__name__}: cannot record or reuse memory; check paths and metadata\n')


if __name__ == '__main__':
    raise SystemExit(main())
