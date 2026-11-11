#!/usr/bin/env python3
"""Check repository Markdown or read complete sections without a model summary."""

import argparse
from functools import lru_cache
import hashlib
import json
from pathlib import Path
import re
import subprocess
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


def section_result(repository, name, identifiers, max_chars):
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
    indexes = sorted({i for section in selected for i in range(section['start'], section['end'])})
    lines = text.splitlines()
    output = '\n'.join(f'{i + 1}: {lines[i]}' for i in indexes)
    if max_chars < 1 or len(output) > max_chars:
        raise ValueError('section exceeds --max-chars; select a child heading or increase the limit; no text returned')
    metadata = {'path': path.relative_to(repository.root).as_posix(),
                'sha256': hashlib.sha256(text.encode('utf-8')).hexdigest(),
                'sections': [{'id': s['id'], 'start_line': s['start'] + 1, 'end_line': s['end']} for s in selected]}
    return metadata, output


def read(repository, name, identifiers, max_chars):
    metadata, output = section_result(repository, name, identifiers, max_chars)
    print(json.dumps(metadata, ensure_ascii=False))
    print(output)
    return 0


def context(repository, profile, max_chars):
    """Return fixed common instructions; task-specific dependencies remain caller-selected."""
    path = repository.path('AGENTS.md')
    text = repository.text(path)
    lines = text.splitlines()
    documents = [{'path': 'AGENTS.md', 'sha256': hashlib.sha256(text.encode('utf-8')).hexdigest(),
                  'sections': [{'id': 'whole-file', 'start_line': 1, 'end_line': len(lines)}]}]
    bodies = ['--- AGENTS.md ---\n' + '\n'.join(f'{i}: {line}' for i, line in enumerate(lines, 1))]
    development = ['workflow-reading', '共通の検証', 'agent-context', 'agent-review',
                   'review-checklist', '6. 完了条件と報告']
    if profile == 'change':
        development.append('change-steps')
    selections = [('docs/development-workflow.md', development),
                  ('docs/git-workflow.md', ['1. 基本方針', '6. Codex が作業するときの手順'])]
    for name, identifiers in selections:
        metadata, body = section_result(repository, name, identifiers, max_chars)
        documents.append(metadata)
        bodies.append(f'--- {name} ---\n{body}')
    output = json.dumps({'profile': profile, 'documents': documents}, ensure_ascii=False) + '\n' + '\n'.join(bodies)
    if max_chars < 1 or len(output) > max_chars:
        raise ValueError('context exceeds --max-chars; increase the limit or use read; no text returned')
    print(output)
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
    bundle = commands.add_parser('context', help='Read common instructions atomically; add task-specific sections separately')
    bundle.add_argument('profile', choices=['change', 'review'])
    bundle.add_argument('--max-chars', type=int, default=24000)
    args = parser.parse_args()
    repository = Repository(args.root)
    try:
        if args.operation == 'check':
            paths = args.paths or repository.tracked()
            if not paths:
                raise ValueError('no Markdown documents selected')
            return check(repository, paths)
        if args.operation == 'context':
            return context(repository, args.profile, args.max_chars)
        return read(repository, args.path, args.sections, args.max_chars)
    except (OSError, UnicodeError, ValueError, subprocess.CalledProcessError) as error:
        parser.exit(1, f'{type(error).__name__}: {error}\n')


if __name__ == '__main__':
    raise SystemExit(main())
