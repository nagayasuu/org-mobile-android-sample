#!/usr/bin/env python3
"""Check repository Markdown or read complete sections without a model summary."""

import argparse
from functools import lru_cache
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unicodedata
from urllib.parse import unquote, urlsplit


ROOT = Path(__file__).resolve().parents[1]
INLINE_LINK = re.compile(r'!?\[[^\]\n]*\]\(\s*(<[^>\n]+>|(?:\\.|[^()\s]|\([^()\n]*\))+)(?:\s+["\'][^\n]*["\'])?\s*\)')
REFERENCE = re.compile(r'^ {0,3}\[([^\]]+)\]:\s*(<[^>]+>|\S+)')
EXPLICIT_ID = re.compile(r'<a\s+(?:id|name)=["\']([^"\']+)["\']\s*>\s*</a>', re.I)


def prose(text):
    """Mask comments and fenced blocks without changing line positions."""
    text = re.sub(r'<!--.*?-->', lambda m: '\n' * m.group().count('\n'), text, flags=re.S)
    result = []
    fence = None
    for line in text.splitlines():
        match = re.match(r'^ {0,3}(`{3,}|~{3,})(.*)$', line)
        if fence:
            if match and match[1][0] == fence[0] and len(match[1]) >= len(fence) and not match[2].strip():
                fence = None
            result.append('')
        elif match:
            fence = match[1]
            result.append('')
        else:
            result.append(line)
    return result


def slug(title):
    title = re.sub(r'\[([^\]]+)\]\([^)]*\)', r'\1', title)
    title = re.sub(r'<[^>]*>', '', title).replace('`', '').replace('*', '').lower()
    return ''.join(c for c in title if c in ' _-' or unicodedata.category(c)[0] in 'LNM').replace(' ', '-')


def parse_sections(text):
    lines = prose(text)
    sections, used, explicit = [], set(), []
    for index, line in enumerate(lines):
        without_code = re.sub(r'(`+).*?\1', '', line)
        for match in EXPLICIT_ID.finditer(without_code):
            explicit.append((match[1], index))
        match = re.match(r'^ {0,3}(#{1,6})\s+(.+?)\s*#*\s*$', line)
        if not match:
            continue
        title = match[2]
        base, suffix = slug(title), 0
        identifier = base
        while identifier in used:
            suffix += 1
            identifier = f'{base}-{suffix}'
        used.add(identifier)
        start = index
        while start and (not lines[start - 1].strip() or EXPLICIT_ID.fullmatch(lines[start - 1].strip())):
            start -= 1
        sections.append({'title': title, 'id': identifier, 'level': len(match[1]),
                         'heading': index, 'start': start})
    for section in sections:
        section['aliases'] = [name for name, index in explicit if section['start'] <= index < section['heading']]
        section['end'] = next((other['start'] for other in sections
                               if other['heading'] > section['heading'] and other['level'] <= section['level']), len(lines))
    return sections, {name for name, _ in explicit} | used


class Repository:
    def __init__(self, root):
        self.root = root.resolve()

    def path(self, value):
        path = (self.root / value).resolve()
        if not path.is_relative_to(self.root):
            raise ValueError('path outside repository')
        relative = path.relative_to(self.root).as_posix()
        if relative == '.git' or relative.startswith('.git/') or self.ignored(relative):
            raise ValueError('local-only path is not a public document')
        return path

    @lru_cache(maxsize=None)
    def ignored(self, relative):
        result = subprocess.run(['git', '-C', str(self.root), 'check-ignore', '-q', '--', relative],
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return result.returncode == 0

    @lru_cache(maxsize=None)
    def text(self, path):
        return path.read_bytes().decode('utf-8')

    def tracked(self):
        result = subprocess.run(['git', '-C', str(self.root), 'ls-files', '-z', '--', '*.md'],
                                capture_output=True, check=True)
        return result.stdout.decode('utf-8').rstrip('\0').split('\0') if result.stdout else []


def links(text):
    lines = prose(text)
    references = {}
    for line in lines:
        match = REFERENCE.match(line)
        if match:
            references[' '.join(match[1].lower().split())] = match[2]
    for number, line in enumerate(lines, 1):
        if REFERENCE.match(line):
            # Check definitions as well as uses, including unused definitions.
            yield number, REFERENCE.match(line)[2]
            continue
        line = re.sub(r'(`+).*?\1', '', line)
        for match in INLINE_LINK.finditer(line):
            yield number, match[1]
        remainder = INLINE_LINK.sub('', line)
        for match in re.finditer(r'!?\[([^\]]+)\]\[([^\]]*)\]', remainder):
            label = ' '.join((match[2] or match[1]).lower().split())
            yield number, references.get(label)
        remainder = re.sub(r'!?\[[^\]]+\]\[[^\]]*\]', '', remainder)
        for match in re.finditer(r'!?\[([^\]]+)\]', remainder):
            label = ' '.join(match[1].lower().split())
            if label in references:
                yield number, references[label]


def check(repository, paths):
    errors, link_count = [], 0
    for name in paths:
        try:
            path = repository.path(name)
            text = repository.text(path)
            if text and not text.endswith('\n'):
                errors.append(f'{name}:1: missing final newline')
            for line, body in enumerate(text.splitlines(), 1):
                if body.rstrip() != body:
                    errors.append(f'{name}:{line}: trailing whitespace')
            for line, target in links(text):
                try:
                    if target is None:
                        raise ValueError('undefined reference link')
                    url = urlsplit(target.strip('<>'))
                    if url.scheme or url.netloc:
                        continue
                    link_count += 1
                    destination = repository.path(path.parent / unquote(url.path)) if url.path else path
                    if not destination.exists():
                        raise ValueError('missing target')
                    if url.fragment:
                        if not destination.is_file() or destination.suffix.lower() != '.md':
                            raise ValueError('anchor target is not Markdown')
                        _, anchors = parse_sections(repository.text(destination))
                        if unquote(url.fragment) not in anchors:
                            raise ValueError('missing anchor')
                except (OSError, UnicodeError, ValueError) as error:
                    errors.append(f'{name}:{line}: {error}')
        except (OSError, UnicodeError, ValueError) as error:
            # Never echo source contents or invalid bytes.
            errors.append(f'{name}:1: {type(error).__name__}: cannot check document')
    print('\n'.join(errors) if errors else f'PASS: {len(paths)} documents, {link_count} local links')
    return int(bool(errors))


def section_selection(repository, name, identifiers):
    path = repository.path(name)
    text = repository.text(path)
    sections, _ = parse_sections(text)
    selected = []
    for identifier in identifiers:
        exact = [s for s in sections if identifier == s['title']]
        matches = exact or [s for s in sections if identifier == s['id'] or identifier in s['aliases']]
        if len(matches) != 1:
            raise ValueError(f'section is missing or ambiguous: {identifier}')
        selected.append(matches[0])
    indexes = {i + 1 for section in selected for i in range(section['start'], section['end'])}
    metadata = {'path': path.relative_to(repository.root).as_posix(),
                'sha256': hashlib.sha256(text.encode('utf-8')).hexdigest(),
                'sections': [{'id': s['id'], 'start_line': s['start'] + 1, 'end_line': s['end']} for s in selected]}
    return metadata, indexes


def section_result(repository, name, identifiers, max_chars):
    metadata, indexes = section_selection(repository, name, identifiers)
    lines = repository.text(repository.path(name)).splitlines()
    output = '\n'.join(f'{i}: {lines[i - 1]}' for i in sorted(indexes))
    if max_chars < 1 or len(output) > max_chars:
        raise ValueError('section exceeds --max-chars; select a child heading or increase the limit; no text returned')
    return metadata, output


def read(repository, name, identifiers, max_chars):
    metadata, output = section_result(repository, name, identifiers, max_chars)
    print(json.dumps(metadata, ensure_ascii=False))
    print(output)
    return 0


def line_ranges(indexes):
    ranges = []
    for index in sorted(indexes):
        if ranges and index == ranges[-1][1] + 1:
            ranges[-1][1] = index
        else:
            ranges.append([index, index])
    return ranges


def context_receipt(repository, value, reader):
    """Validate an explicit, local delivery receipt, never an assertion of understanding."""
    if not isinstance(reader, str) or not reader.strip() or len(reader) > 128 or any(ord(c) < 32 for c in reader):
        raise ValueError('--state requires a nonempty --reader task/agent label')
    git_root = subprocess.run(['git', '-C', str(repository.root), 'rev-parse', '--show-toplevel'],
                              capture_output=True, text=True, check=True)
    if Path(git_root.stdout.strip()).resolve() != repository.root:
        raise ValueError('state requires the Git repository root')
    local = repository.root / '.local'
    path = (repository.root / value).resolve()
    if local.is_symlink() or not path.is_relative_to(local) or path == local:
        raise ValueError('state must be stored under repository .local/')
    relative = path.relative_to(repository.root).as_posix()
    tracked = subprocess.run(['git', '-C', str(repository.root), 'ls-files', '-z', '--', relative],
                             capture_output=True, check=True)
    if tracked.stdout or not repository.ignored(relative):
        raise ValueError('state must be Git-ignored and untracked')
    if not path.exists():
        return path, {'version': 1, 'reader': reader, 'documents': []}
    try:
        record = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, UnicodeError, ValueError):
        raise ValueError('invalid context state; use a new local receipt') from None
    if (not isinstance(record, dict) or set(record) != {'version', 'reader', 'documents'}
            or type(record['version']) is not int or record['version'] != 1
            or not isinstance(record['documents'], list)):
        raise ValueError('unsupported context state')
    if record['reader'] != reader:
        raise ValueError('context state belongs to a different reader; use a separate receipt')
    names = set()
    for item in record['documents']:
        if (not isinstance(item, dict) or set(item) != {'path', 'sha256', 'ranges'}
                or not isinstance(item['path'], str) or not isinstance(item['sha256'], str)
                or not re.fullmatch('[0-9a-f]{64}', item['sha256']) or not isinstance(item['ranges'], list)):
            raise ValueError('invalid context document metadata')
        name = repository.path(item['path']).relative_to(repository.root).as_posix()
        if name != item['path'] or name in names:
            raise ValueError('duplicate or noncanonical context document')
        names.add(name)
        end = 0
        for pair in item['ranges']:
            if (not isinstance(pair, list) or len(pair) != 2 or any(type(v) is not int for v in pair)
                    or not end < pair[0] <= pair[1]):
                raise ValueError('invalid context delivery range')
            end = pair[1]
    return path, record


def context(repository, profile, max_chars, includes=(), state=None, reader=None, refresh=False):
    """Bundle common and selected instructions, optionally omitting previously delivered lines."""
    if state is None and (reader is not None or refresh):
        raise ValueError('--reader and --refresh require --state')
    state_path, receipt = context_receipt(repository, state, reader) if state is not None else (None, None)
    path = repository.path('AGENTS.md')
    agent_name = path.relative_to(repository.root).as_posix()
    text = repository.text(path)
    lines = text.splitlines()
    selected = {agent_name: ({'path': agent_name, 'sha256': hashlib.sha256(text.encode('utf-8')).hexdigest(),
                              'sections': [{'id': 'whole-file', 'start_line': 1, 'end_line': len(lines)}]},
                             set(range(1, len(lines) + 1)))}
    development = ['workflow-reading', '共通の検証', 'agent-context', 'agent-review',
                   'review-checklist', '6. 完了条件と報告']
    if profile == 'change':
        development.append('change-steps')
    selections = [('docs/development-workflow.md', development),
                  ('docs/git-workflow.md', ['1. 基本方針', '6. Codex が作業するときの手順'])]
    for include in includes:
        if len(include) < 2:
            raise ValueError('--include requires a path and at least one section')
        selections.append((include[0], include[1:]))
    grouped = {}
    for name, identifiers in selections:
        name = repository.path(name).relative_to(repository.root).as_posix()
        grouped.setdefault(name, []).extend(identifiers)
    for name, identifiers in grouped.items():
        metadata, indexes = section_selection(repository, name, identifiers)
        if name in selected:
            previous, covered = selected[name]
            metadata['sections'] = previous['sections'] + metadata['sections']
            indexes |= covered
        # Alias/parent/child requests may overlap; source lines are emitted once.
        metadata['sections'] = list({(s['id'], s['start_line'], s['end_line']): s
                                     for s in metadata['sections']}.values())
        selected[name] = metadata, indexes
    known = {item['path']: item for item in receipt['documents']} if receipt else {}
    updated = dict(known)
    documents, bodies = [], []
    for name, (metadata, indexes) in selected.items():
        lines = repository.text(repository.path(name)).splitlines()
        previous = known.get(name)
        covered = set()
        if previous and previous['sha256'] == metadata['sha256']:
            if any(pair[1] > len(lines) for pair in previous['ranges']):
                raise ValueError('context delivery range exceeds current document')
            covered = {i for start, end in previous['ranges'] for i in range(start, end + 1)}
        emitted = indexes if refresh else indexes - covered
        if receipt is not None:
            metadata['emitted_ranges'] = line_ranges(emitted)
            metadata['reused_ranges'] = line_ranges(indexes - emitted)
        documents.append(metadata)
        if emitted:
            bodies.append(f'--- {name} ---\n' + '\n'.join(f'{i}: {lines[i - 1]}' for i in sorted(emitted)))
        updated[name] = {'path': name, 'sha256': metadata['sha256'], 'ranges': line_ranges(covered | indexes)}
    header = {'profile': profile, 'documents': documents}
    if receipt is not None:
        header.update(reader=reader, status='updated' if bodies else 'unchanged',
                      refresh='use --refresh if output was truncated or context was lost')
    output = json.dumps(header, ensure_ascii=False) + ('\n' + '\n'.join(bodies) if bodies else '')
    if max_chars < 1 or len(output) > max_chars:
        raise ValueError('context exceeds --max-chars; increase the limit or use read; no text returned')
    next_receipt = {'version': 1, 'reader': reader, 'documents': list(updated.values())}
    temporary = None
    try:
        if state_path is not None and (not state_path.exists() or next_receipt != receipt):
            state_path.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=state_path.parent, delete=False) as stream:
                temporary = Path(stream.name)
                stream.write(json.dumps(next_receipt, ensure_ascii=False, indent=2) + '\n')
        print(output)
        sys.stdout.flush()
        if temporary is not None:
            os.replace(temporary, state_path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT)
    commands = parser.add_subparsers(dest='operation', required=True)
    checker = commands.add_parser('check', help='Check named public Markdown; default: all tracked Markdown')
    checker.add_argument('paths', nargs='*')
    reader = commands.add_parser('read', help='Read complete sections by heading title or anchor')
    reader.add_argument('path')
    reader.add_argument('sections', nargs='+')
    reader.add_argument('--max-chars', type=int, default=16000)
    bundle = commands.add_parser('context', help='Bundle common and selected instructions; optionally reuse a local delivery receipt')
    bundle.add_argument('profile', choices=['change', 'review'])
    bundle.add_argument('--max-chars', type=int, default=24000)
    bundle.add_argument('--include', nargs='+', action='append', default=[], metavar='PATH_OR_SECTION',
                        help='Add PATH SECTION [SECTION ...]; repeat for other documents')
    bundle.add_argument('--state', help='Optional Git-ignored .local/ delivery receipt for one task and reader')
    bundle.add_argument('--reader', help='Task/agent label required with --state; independent readers use separate receipts')
    bundle.add_argument('--refresh', action='store_true', help='Return all requested source despite the receipt')
    args = parser.parse_args()
    repository = Repository(args.root)
    try:
        if args.operation == 'check':
            paths = args.paths or repository.tracked()
            if not paths:
                raise ValueError('no Markdown documents selected')
            return check(repository, paths)
        if args.operation == 'context':
            return context(repository, args.profile, args.max_chars, args.include, args.state, args.reader, args.refresh)
        return read(repository, args.path, args.sections, args.max_chars)
    except (OSError, UnicodeError, ValueError, subprocess.CalledProcessError) as error:
        parser.exit(1, f'{type(error).__name__}: {error}\n')


if __name__ == '__main__':
    raise SystemExit(main())
