#!/usr/bin/env python3
"""Allocate bounded candidate paths and ranges, expanding only after explicit feedback."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
from context_memory import state_path
from document_tools import Repository, ROOT


def allocate(repository, query):
    result = subprocess.run(['git', '-C', str(repository.root), 'ls-files', '-z', '--', '*.kt'], capture_output=True, check=True)
    candidates = []
    fingerprints = {}
    for name in result.stdout.decode('utf-8').split('\0'):
        if not name:
            continue
        path = repository.path(name)
        try:
            raw = path.read_bytes()
        except FileNotFoundError:
            # An unstaged deletion remains in git ls-files. Its absent fingerprint
            # must invalidate a previous sufficient assessment.
            continue
        lines = raw.decode('utf-8').splitlines()
        digest = hashlib.sha256(raw).hexdigest()
        fingerprints[name] = digest
        matches = [i + 1 for i, line in enumerate(lines) if query in line]
        if matches:
            candidates.append({'path': name, 'sha256': digest, 'match_count': len(matches),
                               'ranges': [{'start_line': max(1, i - 3), 'end_line': min(len(lines), i + 3)}
                                          for i in matches[:3]]})
    candidates.sort(key=lambda item: item['path'])
    return candidates, fingerprints


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('state', help='Local JSON state; existing state must belong to this tool')
    parser.add_argument('query', help='Literal case-sensitive text; tracked Kotlin only')
    parser.add_argument('--feedback', choices=['insufficient', 'sufficient'])
    args = parser.parse_args()
    try:
        if not args.query.strip():
            raise ValueError('nonempty query required')
        repository = Repository(args.root)
        git_root = subprocess.run(['git', '-C', str(repository.root), 'rev-parse', '--show-toplevel'], capture_output=True, text=True, check=True)
        if Path(git_root.stdout.strip()).resolve() != repository.root:
            raise ValueError('root must be Git repository root')
        state = state_path(repository, args.state)
        old = None
        if state.exists():
            old = json.loads(state.read_text(encoding='utf-8'))
            if (not isinstance(old, dict) or old.get('purpose') != 'exploration_budget'
                    or type(old.get('version')) is not int or old['version'] != 1
                    or old.get('query') != args.query or type(old.get('level')) is not int
                    or not 0 <= old['level'] <= 2 or not isinstance(old.get('fingerprints'), dict)):
                raise ValueError('incompatible state; choose a new local file')
        elif args.feedback:
            raise ValueError('feedback requires a previous plan')
        level = old['level'] if old else 0
        candidates, fingerprints = allocate(repository, args.query)
        invalidated = old is not None and old['fingerprints'] != fingerprints
        if invalidated:
            level = 0
        elif old and args.feedback == 'insufficient':
            level = min(2, level + 1)
        cap, char_budget = 3 * 2 ** level, 2000 * 2 ** level
        selected = candidates[:cap]
        exhausted = old is not None and old['level'] == 2 and args.feedback == 'insufficient' and not invalidated
        status = ('needs_recheck' if invalidated else 'manual_investigation' if exhausted else
                  'no_matches' if not candidates else 'ready_for_edit' if args.feedback == 'sufficient' else 'explore')
        result = {'status': status, 'query': args.query, 'level': level,
                  'scope': 'tracked public Kotlin files; literal matches, not semantic resolution',
                  'candidate_budget': cap, 'max_chars': char_budget, 'total_candidates': len(candidates),
                  'omitted_candidates': len(candidates) - len(selected), 'candidates': selected}
        while True:
            result['candidates'] = selected
            result['omitted_candidates'] = len(candidates) - len(selected)
            output = json.dumps(result, ensure_ascii=False) + '\n'
            if len(output) <= char_budget:
                break
            if not selected:
                raise ValueError('metadata exceeds allocation budget')
            selected.pop()
        record = {'purpose': 'exploration_budget', 'version': 1, 'query': args.query,
                  'level': level, 'fingerprints': fingerprints, 'last_status': status}
        state.parent.mkdir(parents=True, exist_ok=True)
        temporary_name = None
        try:
            with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=state.parent, delete=False) as stream:
                temporary_name = stream.name
                stream.write(json.dumps(record, ensure_ascii=False, indent=2) + '\n')
            os.replace(temporary_name, state)
        finally:
            if temporary_name and Path(temporary_name).exists():
                Path(temporary_name).unlink()
        print(output, end='')
        return 1 if status in ['manual_investigation', 'no_matches', 'needs_recheck'] else 0
    except (OSError, UnicodeError, ValueError, subprocess.CalledProcessError) as error:
        parser.exit(2, f'{type(error).__name__}: cannot allocate; check query, public source and local state\n')

if __name__ == '__main__':
    raise SystemExit(main())
