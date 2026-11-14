#!/usr/bin/env python3
"""Retain one command attempt and summarize explicitly selected attempt directories."""

import argparse
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import re
import select
import signal
import subprocess
import threading
import time

from run_check import revision


PHASES = ('agent', 'tool', 'environment', 'review')
EVENTS = {'thread.started', 'turn.started', 'turn.completed', 'turn.failed',
          'item.started', 'item.updated', 'item.completed', 'error'}


def save(path, value):
    # Exclusive creation: a late/incomplete writer cannot replace a final record.
    with path.open('x', encoding='utf-8') as output:
        json.dump(value, output, ensure_ascii=False, indent=2, allow_nan=False)
        output.write('\n')
        output.flush()
        os.fsync(output.fileno())


def record(args):
    command = args.command[1:] if args.command[:1] == ['--'] else args.command
    if not command:
        raise ValueError('command is required')
    for value in (args.trial, args.agent, args.attempt):
        if not re.fullmatch(r'[A-Za-z0-9_-]+', value):
            raise ValueError('IDs must contain only ASCII letters, digits, underscore or hyphen')
    if args.timeout is not None and (not 0 < args.timeout < float('inf')):
        raise ValueError('timeout must be finite and positive')
    args.output_dir.mkdir(parents=True, exist_ok=False)
    target_revision = revision()
    began = time.monotonic_ns()
    start = {'trial': args.trial, 'agent': args.agent, 'attempt': args.attempt,
             'scope': args.scope, 'phase': args.phase, 'revision': target_revision,
             'started_utc': datetime.now(timezone.utc).isoformat(),
             'started_unix_ns': time.time_ns()}
    save(args.output_dir / 'start.json', start)
    failures = []

    finished = threading.Event()

    def capture(pipe, raw, timeline):
        turn, line_number = 0, 0
        pending = b''

        def emit(line):
            nonlocal turn, line_number
            line_number += 1
            entry = {'line': line_number, 'elapsed_seconds': (time.monotonic_ns() - began) / 1e9}
            # Raw IDs, commands, text and tool arguments stay in stdout.log.
            try:
                event = json.loads(line)
                kind = event.get('type') if isinstance(event, dict) else None
                if isinstance(kind, str) and kind in EVENTS:
                    if kind == 'turn.started':
                        turn += 1
                    entry.update(type=kind, turn=turn)
            except (ValueError, UnicodeError):
                pass
            timeline.write(json.dumps(entry) + '\n')
            timeline.flush()

        try:
            drain_started = None
            with pipe:
                while True:
                    if finished.is_set() and drain_started is None:
                        drain_started = time.monotonic()
                    ready, _, _ = select.select([pipe], [], [], 0.05)
                    if drain_started is not None and (not ready or time.monotonic() - drain_started > 1):
                        # An escaped descendant can retain the pipe after the command
                        # exits. Do not lose the process record waiting for its EOF.
                        failures.append('stdout_eof_timeout')
                        break
                    if not ready:
                        continue
                    chunk = os.read(pipe.fileno(), 65536)
                    if not chunk:
                        break
                    raw.write(chunk)
                    raw.flush()
                    pending += chunk
                    while b'\n' in pending:
                        line, pending = pending.split(b'\n', 1)
                        emit(line)
                if pending:
                    emit(pending)
        except Exception as error:
            failures.append(type(error).__name__)

    result = {'returncode': None, 'exit_code': None, 'termination': None}
    process = None
    interrupted = []

    def stop(signum, frame):
        interrupted.append(signum)
        if process is not None:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass

    previous = {sig: signal.signal(sig, stop) for sig in (signal.SIGINT, signal.SIGTERM)}
    try:
        with (args.output_dir / 'stdout.log').open('xb') as raw, \
                (args.output_dir / 'stderr.log').open('xb') as errors, \
                (args.output_dir / 'timeline.jsonl').open('x', encoding='utf-8') as timeline:
            try:
                process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=errors,
                                           start_new_session=True)
            except OSError as error:
                result.update(termination='launch_error', exit_code=127, error_type=type(error).__name__)
            else:
                reader = threading.Thread(target=capture, args=(process.stdout, raw, timeline))
                reader.start()
                try:
                    if interrupted:
                        stop(interrupted[-1], None)
                    process.wait(timeout=args.timeout)
                    result['termination'] = 'interrupted' if interrupted else 'exited'
                except subprocess.TimeoutExpired:
                    stop(signal.SIGTERM, None)
                    process.wait()
                    result['termination'] = 'timeout'
                finally:
                    # Descendants must not retain the stdout pipe after the command exits.
                    try:
                        os.killpg(process.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                    finished.set()
                    reader.join()
                code = process.returncode
                result.update(returncode=code, exit_code=124 if result['termination'] == 'timeout'
                              else 128 + interrupted[-1] if result['termination'] == 'interrupted'
                              else code if code >= 0 else 128 - code)
    finally:
        for sig, handler in previous.items():
            signal.signal(sig, handler)
        result.update(wall_seconds=(time.monotonic_ns() - began) / 1e9,
                      ended_utc=datetime.now(timezone.utc).isoformat(), capture_errors=failures)
        save(args.output_dir / 'process.json', result)
    print(json.dumps({'exit_code': result['exit_code'], 'termination': result['termination'],
                      'capture_complete': not failures}))
    return result['exit_code'] or (1 if failures else 0)


def summarize(paths):
    seen_paths, identities = set(), set()
    groups = {}
    for path in paths:
        path = path.resolve()
        if path in seen_paths:
            raise ValueError('duplicate directory')
        seen_paths.add(path)
        start = json.loads((path / 'start.json').read_text(encoding='utf-8'))
        if start['scope'] not in ('trial', 'outside') or start['phase'] not in PHASES:
            raise ValueError('invalid scope or phase')
        for key in ('trial', 'agent', 'attempt'):
            if not isinstance(start[key], str) or not re.fullmatch(r'[A-Za-z0-9_-]+', start[key]):
                raise ValueError('invalid identity')
        if type(start['started_unix_ns']) is not int or start['started_unix_ns'] < 0:
            raise ValueError('invalid start time')
        identity = tuple(start[key] for key in ('scope', 'trial', 'agent', 'attempt'))
        if identity in identities:
            raise ValueError('duplicate attempt identity')
        identities.add(identity)
        final = path / 'process.json'
        process = json.loads(final.read_text(encoding='utf-8')) if final.exists() else None
        if process is not None:
            seconds = process['wall_seconds']
            if type(seconds) not in (int, float) or not math.isfinite(seconds) or seconds < 0:
                raise ValueError('invalid duration')
        group = groups.setdefault((start['scope'], start['trial']), [])
        group.append({'agent': start['agent'], 'attempt': start['attempt'], 'phase': start['phase'],
                      'start': start['started_unix_ns'] / 1e9,
                      'seconds': process['wall_seconds'] if process else None,
                      'exit_code': process['exit_code'] if process else None,
                      'termination': process['termination'] if process else None,
                      'capture_complete': not process['capture_errors']
                      if process and 'capture_errors' in process else None})
    output = []
    for (scope, trial), runs in sorted(groups.items()):
        complete = all(run['seconds'] is not None for run in runs)
        observed = [run for run in runs if run['seconds'] is not None]
        intervals = sorted((run['start'], run['start'] + run['seconds']) for run in observed)
        union = 0
        end = float('-inf')
        for left, right in intervals:
            union += max(0, right - max(left, end))
            end = max(end, right)
        phase_totals = {phase: sum(run['seconds'] for run in observed if run['phase'] == phase)
                        if complete and any(run['phase'] == phase for run in runs) else None
                        for phase in PHASES}
        output.append({'scope': scope, 'trial': trial, 'attempts': runs,
                       'process_time_complete': complete,
                       'observed_attempt_seconds': sum(run['seconds'] for run in observed),
                       'attempt_seconds_sum': sum(run['seconds'] for run in observed) if complete else None,
                       'observed_active_seconds': union,
                       'recorded_window_seconds': max(right for _, right in intervals) - min(left for left, _ in intervals)
                       if complete else None,
                       'phase_attempt_seconds': phase_totals,
                       'model_wait_seconds': None})
    return {'groups': output}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_subparsers(dest='mode', required=True)
    run = modes.add_parser('run')
    run.add_argument('--output-dir', required=True, type=Path)
    for key in ('trial', 'agent', 'attempt'):
        run.add_argument('--' + key, required=True)
    run.add_argument('--scope', choices=('trial', 'outside'), required=True)
    run.add_argument('--phase', choices=PHASES, required=True)
    run.add_argument('--timeout', type=float)
    run.add_argument('command', nargs=argparse.REMAINDER)
    summary = modes.add_parser('summarize')
    summary.add_argument('directories', type=Path, nargs='+')
    args = parser.parse_args()
    try:
        if args.mode == 'run':
            return record(args)
        print(json.dumps(summarize(args.directories), indent=2, allow_nan=False))
        return 0
    except (OSError, ValueError, KeyError, TypeError):
        parser.exit(2, 'cannot record or summarize; check inputs and choose unused output directories\n')


if __name__ == '__main__':
    raise SystemExit(main())
