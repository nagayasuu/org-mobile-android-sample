#!/usr/bin/env python3
"""Run a check, retain its log and exit code, and summarize explicit XML reports."""

import argparse
from collections import Counter
from datetime import datetime, timezone
import glob
import hashlib
import json
import math
import os
from pathlib import Path
import re
import signal
import subprocess
import time
import xml.etree.ElementTree as ET


LINT_SEVERITIES = ('Fatal', 'Error', 'Warning', 'Information', 'Informational', 'Hint', 'Ignore')


def report_paths(patterns, started):
    paths = set()
    for pattern in patterns:
        matches = glob.glob(pattern, recursive=True)
        if not matches:
            raise ValueError('requested report pattern has no matches')
        paths.update(Path(match) for match in matches)
    for path in sorted(paths):
        if not path.is_file() or path.stat().st_mtime_ns < started:
            raise ValueError('requested report is missing or older than this run')
        yield path


def junit_reports(paths):
    counts = Counter(tests=0, failures=0, errors=0, skipped=0)
    failed, reports = [], []

    def collect(node):
        actual = Counter(tests=0, failures=0, errors=0, skipped=0)
        for child in node:
            if child.tag in ('testsuite', 'testsuites'):
                actual.update(collect(child))
            elif child.tag == 'testcase':
                actual['tests'] += 1
                for tag, key in (('failure', 'failures'), ('error', 'errors'), ('skipped', 'skipped')):
                    if child.find(tag) is not None:
                        actual[key] += 1
                if child.find('failure') is not None or child.find('error') is not None:
                    failed.append('.'.join(filter(None, (child.get('classname'), child.get('name', '(unnamed)')))))
        for key in counts:
            if key in node.attrib and int(node.attrib[key]) != actual[key]:
                raise ValueError('JUnit counts do not match test cases')
        return actual

    for path in paths:
        root = ET.parse(path).getroot()
        if root.tag not in ('testsuite', 'testsuites'):
            raise ValueError('expected JUnit testsuite or testsuites')
        if root.tag == 'testsuites' and not list(root.iter('testsuite')):
            raise ValueError('JUnit report has no test suites')
        counts.update(collect(root))
        reports.append(str(path))
    return {**dict(counts), 'failed_cases': failed, 'reports': reports}


def lint_reports(paths):
    severities, reports = Counter(), []
    for path in paths:
        root = ET.parse(path).getroot()
        if root.tag != 'issues':
            raise ValueError('expected Android Lint issues')
        for issue in root.findall('issue'):
            severity = issue.get('severity')
            if severity not in LINT_SEVERITIES:
                raise ValueError('unknown Lint severity')
            severities[severity] += 1
        reports.append(str(path))
    return {'severities': dict(severities), 'reports': reports}


def revision():
    head = subprocess.run(['git', 'rev-parse', 'HEAD'], capture_output=True)
    diff = subprocess.run(['git', 'diff', 'HEAD', '--binary'], capture_output=True)
    return {'head': head.stdout.decode().strip() if head.returncode == 0 else None,
            'tracked_diff_sha256': hashlib.sha256(diff.stdout).hexdigest() if diff.returncode == 0 else None}


def comparison_key(args, command, revision_info):
    if not all(revision_info.values()):
        raise ValueError('comparison needs a Git HEAD and tracked diff')
    context = args.context_file.read_bytes()
    if not context.strip():
        raise ValueError('comparison needs a nonempty context file')
    conditions = {
        'version': 1,
        'cwd': str(Path.cwd()),
        'revision': revision_info,
        'command': command,
        'context_sha256': hashlib.sha256(context).hexdigest(),
        'junit': args.junit,
        'lint': args.lint,
        'timeout_seconds': args.timeout,
        'progress_interval_seconds': args.progress_interval,
    }
    return hashlib.sha256(json.dumps(conditions, sort_keys=True).encode('ascii')).hexdigest()


def compare_records(paths, key):
    records = []
    for path in paths:
        entry = {'summary': str(path)}
        try:
            summary = json.loads(path.read_text(encoding='utf-8'))
            status = summary['status']
            if status not in ('passed', 'failed', 'unconfirmed'):
                raise ValueError
            prior_key = summary.get('comparison_sha256')
            if prior_key is None:
                entry['status'] = 'insufficient-record'
            elif not re.fullmatch(r'[0-9a-f]{64}', prior_key):
                raise ValueError
            elif prior_key != key:
                entry['status'] = 'different-conditions'
            elif not path.with_name('command.log').is_file():
                entry['status'] = 'missing-log'
            else:
                entry['status'] = {'passed': 'reuse-candidate', 'failed': 'previous-failure',
                                   'unconfirmed': 'previous-unconfirmed'}[status]
                entry['log'] = str(path.with_name('command.log'))
        except (KeyError, OSError, TypeError, ValueError):
            entry['status'] = 'invalid-record'
        records.append(entry)
    print(json.dumps({'records': records}, ensure_ascii=False))
    return 2 if any(entry['status'] == 'invalid-record' for entry in records) else 0


def positive_seconds(value):
    seconds = float(value)
    if not math.isfinite(seconds) or seconds <= 0:
        raise argparse.ArgumentTypeError('seconds must be finite and positive')
    return seconds


def execute(command, log, summary, interval=None, timeout=None):
    """Wait inside this process; only bounded metadata reaches its caller."""
    began = time.monotonic()
    process = None
    interrupted = []
    notifications = 0

    def send(sig):
        try:
            if os.name == 'posix':
                os.killpg(process.pid, sig)
            else:
                process.send_signal(sig)
        except ProcessLookupError:
            pass

    def interrupt(sig, _frame):
        interrupted.append(sig)
        if process is not None:
            send(signal.SIGTERM)

    def stop():
        send(signal.SIGTERM)
        try:
            process.wait(timeout=1)
        except subprocess.TimeoutExpired:
            pass
        finally:
            # Also terminate descendants still in the command's process group.
            send(signal.SIGKILL)
            process.wait()

    def notify(event):
        nonlocal notifications
        print(json.dumps({'event': event, 'elapsed_seconds': round(time.monotonic()-began, 3),
                          'log_bytes': os.fstat(log.fileno()).st_size}), flush=True)
        notifications += 1

    previous = {sig: signal.signal(sig, interrupt) for sig in (signal.SIGINT, signal.SIGTERM)}
    try:
        process = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT,
                                   start_new_session=os.name == 'posix')
        if interval is not None:
            notify('started')
        next_notice = began + interval if interval is not None else float('inf')
        deadline = began + timeout if timeout is not None else float('inf')
        termination = 'exited'
        while True:
            if interrupted:
                termination = 'interrupted'
                stop()
                break
            if process.poll() is not None:
                break
            now = time.monotonic()
            if now >= deadline:
                termination = 'timeout'
                stop()
                break
            if now >= next_notice:
                notify('running')
                next_notice = now + interval
            try:
                process.wait(timeout=max(0.001, min(1, deadline-now, next_notice-now)))
            except subprocess.TimeoutExpired:
                pass
        raw_code = process.wait()
        exit_code = (124 if termination == 'timeout' else 128 + interrupted[0]
                     if termination == 'interrupted' else raw_code if raw_code >= 0 else 128-raw_code)
        summary.update(command_returncode=raw_code, command_exit_code=exit_code,
                       termination=termination)
        if interrupted:
            summary['interrupted'] = True
        return exit_code
    finally:
        try:
            if process is not None and process.poll() is None:
                stop()
        finally:
            for sig, handler in previous.items():
                signal.signal(sig, handler)
            if interval is not None:
                summary['progress_notifications'] = notifications


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--output-dir', type=Path, help='New directory; never overwrites a previous run')
    mode.add_argument('--compare-only', action='append', type=Path, metavar='SUMMARY',
                      help='Compare a saved summary without running the command; repeat for multiple records')
    parser.add_argument('--context-file', type=Path, metavar='FILE',
                        help='Record declared inputs and environment by file hash; required for comparison')
    parser.add_argument('--junit', action='append', default=[], metavar='GLOB', help='Fresh JUnit XML required after command')
    parser.add_argument('--lint', action='append', default=[], metavar='GLOB', help='Fresh Android Lint XML required after command')
    parser.add_argument('--progress-interval', type=positive_seconds, metavar='SECONDS',
                        help='Emit metadata-only progress at this interval (POSIX; e.g. 60)')
    parser.add_argument('--timeout', type=positive_seconds, metavar='SECONDS',
                        help='Stop the command process group after this limit (POSIX)')
    parser.add_argument('command', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command[1:] if args.command[:1] == ['--'] else args.command
    if not command:
        parser.error('a command after -- is required')
    if (args.progress_interval is not None or args.timeout is not None) and os.name != 'posix':
        parser.error('monitoring and time limits require POSIX')
    if args.compare_only and args.context_file is None:
        parser.error('--compare-only requires --context-file')
    revision_info = revision()
    key = None
    if args.context_file is not None:
        try:
            key = comparison_key(args, command, revision_info)
        except OSError:
            parser.error('cannot read the comparison context')
        except ValueError as error:
            parser.error(str(error))
    if args.compare_only:
        return compare_records(args.compare_only, key)
    try:
        args.output_dir.mkdir(parents=True, exist_ok=False)
    except OSError:
        parser.exit(2, 'cannot create a new output directory; choose an unused path\n')
    summary = {'status': 'unconfirmed', 'command': command, 'revision': revision_info,
               'started_utc': datetime.now(timezone.utc).isoformat(),
               'command_exit_code': None, 'command_returncode': None, 'log': str(args.output_dir / 'command.log'),
               'report_errors': []}
    if args.progress_interval is not None or args.timeout is not None:
        summary.update(progress_interval_seconds=args.progress_interval, timeout_seconds=args.timeout)
    started = time.time_ns()
    exit_code = 1
    try:
        with (args.output_dir / 'command.log').open('wb') as log:
            try:
                exit_code = execute(command, log, summary, args.progress_interval, args.timeout)
            except OSError as error:
                summary['launch_error'] = type(error).__name__
                exit_code = 127
            except KeyboardInterrupt:
                summary['interrupted'] = True
                exit_code = 130
        for kind, patterns, collector in (('junit', args.junit, junit_reports), ('lint', args.lint, lint_reports)):
            if patterns:
                try:
                    summary[kind] = collector(report_paths(patterns, started))
                except (OSError, ValueError, ET.ParseError) as error:
                    summary['report_errors'].append({'kind': kind, 'reason': str(error)})
        tests = summary.get('junit', {})
        lint = summary.get('lint', {}).get('severities', {})
        failed_reports = tests.get('failures', 0) + tests.get('errors', 0) + lint.get('Error', 0) + lint.get('Fatal', 0)
        if exit_code or failed_reports:
            summary['status'] = 'failed'
        elif not summary['report_errors']:
            summary['status'] = 'passed'
        # An original command failure takes precedence over summary failures.
        if exit_code == 0 and summary['status'] != 'passed':
            exit_code = 1
    finally:
        summary['wall_seconds'] = round((time.time_ns() - started) / 1e9, 3)
        if key is not None:
            try:
                if key == comparison_key(args, command, revision()):
                    summary['comparison_sha256'] = key
            except (OSError, ValueError):
                # Keep the run record even when its comparison context is unavailable.
                pass
        summary_path = args.output_dir / 'summary.json'
        summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f"{summary['status'].upper()}: command_exit_code={summary['command_exit_code']}; summary={summary_path}; log={summary['log']}")
    if 'junit' in summary:
        counts = summary['junit']
        print('JUnit: ' + ', '.join(f'{key}={counts[key]}' for key in ('tests', 'failures', 'errors', 'skipped')))
    if 'lint' in summary:
        print('Lint: ' + json.dumps(summary['lint']['severities'], ensure_ascii=False))
    for error in summary['report_errors']:
        print(f"{error['kind']}: {error['reason']}")
    return exit_code


if __name__ == '__main__':
    raise SystemExit(main())
