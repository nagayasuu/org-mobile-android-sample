#!/usr/bin/env python3
"""Run a check, retain its log and exit code, and summarize explicit XML reports."""

import argparse
from collections import Counter
from datetime import datetime, timezone
import glob
import hashlib
import json
from pathlib import Path
import subprocess
import time
import xml.etree.ElementTree as ET


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
            if severity not in ('Fatal', 'Error', 'Warning', 'Information', 'Informational', 'Hint', 'Ignore'):
                raise ValueError('unknown Lint severity')
            severities[severity] += 1
        reports.append(str(path))
    return {'severities': dict(severities), 'reports': reports}


def revision():
    head = subprocess.run(['git', 'rev-parse', 'HEAD'], capture_output=True)
    diff = subprocess.run(['git', 'diff', 'HEAD', '--binary'], capture_output=True)
    return {'head': head.stdout.decode().strip() if head.returncode == 0 else None,
            'tracked_diff_sha256': hashlib.sha256(diff.stdout).hexdigest() if diff.returncode == 0 else None}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True, help='New directory; never overwrites a previous run')
    parser.add_argument('--junit', action='append', default=[], metavar='GLOB', help='Fresh JUnit XML required after command')
    parser.add_argument('--lint', action='append', default=[], metavar='GLOB', help='Fresh Android Lint XML required after command')
    parser.add_argument('command', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command[1:] if args.command[:1] == ['--'] else args.command
    if not command:
        parser.error('a command after -- is required')
    try:
        args.output_dir.mkdir(parents=True, exist_ok=False)
    except OSError:
        parser.exit(2, 'cannot create a new output directory; choose an unused path\n')
    summary = {'status': 'unconfirmed', 'command': command, 'revision': revision(),
               'started_utc': datetime.now(timezone.utc).isoformat(),
               'command_exit_code': None, 'command_returncode': None, 'log': str(args.output_dir / 'command.log'),
               'report_errors': []}
    started = time.time_ns()
    exit_code = 1
    try:
        with (args.output_dir / 'command.log').open('wb') as log:
            try:
                process = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, check=False)
                exit_code = process.returncode if process.returncode >= 0 else 128 - process.returncode
                summary['command_returncode'] = process.returncode
                summary['command_exit_code'] = exit_code
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
