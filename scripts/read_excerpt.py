#!/usr/bin/env python3
"""Read a bounded UTF-8 log or saved search result, preserving source line numbers."""

import argparse
from collections import deque
import hashlib
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('path', type=Path)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--start', type=int, default=1, help='First line (1-based)')
    mode.add_argument('--tail', action='store_true')
    mode.add_argument('--match', help='First line containing this literal text')
    parser.add_argument('--before', type=int, default=3, help='Context before --match')
    parser.add_argument('--lines', type=int, default=40)
    parser.add_argument('--max-chars', type=int, default=8000)
    args = parser.parse_args()
    if min(args.start, args.lines, args.max_chars) < 1 or args.before < 0:
        parser.error('start, lines and max-chars must be positive; before must be nonnegative')
    try:
        selected = deque(maxlen=args.lines)
        previous = deque(maxlen=min(args.before, args.lines - 1))
        found = False
        total = 0
        digest = hashlib.sha256()
        # Scan the complete file for provenance, retaining only the selected lines.
        with args.path.open('rb') as source:
            for total, raw in enumerate(source, 1):
                digest.update(raw)
                line = raw.decode('utf-8').rstrip('\r\n')
                if args.tail:
                    selected.append((total, line))
                elif args.match is not None:
                    if not found and args.match in line:
                        selected.extend(previous)
                        found = True
                    if found and len(selected) < args.lines:
                        selected.append((total, line))
                    previous.append((total, line))
                elif total >= args.start and len(selected) < args.lines:
                    selected.append((total, line))
        if args.match is not None and not found:
            raise ValueError('match not found; no text returned')
        body = '\n'.join(f'{number}: {line}' for number, line in selected)
        metadata = {'path': str(args.path), 'sha256': digest.hexdigest(), 'total_lines': total,
                    'start_line': selected[0][0] if selected else None,
                    'end_line': selected[-1][0] if selected else None,
                    'omitted_lines': total - len(selected)}
        output = json.dumps(metadata, ensure_ascii=False) + '\n' + body + '\n'
        if len(output) > args.max_chars:
            raise ValueError('excerpt exceeds --max-chars; reduce --lines or increase limit; no text returned')
        print(output, end='')
    except (OSError, UnicodeError, ValueError) as error:
        parser.exit(1, f'{type(error).__name__}: {error}\n')


if __name__ == '__main__':
    main()
