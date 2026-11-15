#!/usr/bin/env python3
"""Reproduce CA-007's model-free preflight; raw logs remain in an ignored directory."""

import argparse
import hashlib
import json
from pathlib import Path
import platform
import statistics
import subprocess
import sys
import time


ROOT = Path(__file__).resolve().parents[3]
PYTHON = sys.executable


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    # Keep all raw logs local, even when invoked with an absolute destination.
    destination = args.output_dir.resolve()
    if not destination.is_relative_to(ROOT / '.local'):
        parser.error('output-dir must be inside .local')
    destination.mkdir(parents=True, exist_ok=False)
    started = time.monotonic()
    rows = []

    def invoke(argv):
        before = time.monotonic()
        try:
            remaining = 120 - (before - started)
            if remaining <= 0:
                raise TimeoutError('overall budget exceeded')
            result = subprocess.run(argv, cwd=ROOT, capture_output=True,
                                    encoding='utf-8', timeout=min(30, remaining))
        except (subprocess.TimeoutExpired, OSError, TimeoutError, KeyboardInterrupt) as error:
            failure = dict(status='aborted', reason=type(error).__name__,
                           failed_command=argv, completed_trials=rows,
                           elapsed_seconds=time.monotonic() - started,
                           input_tokens=None, output_tokens=None)
            (destination / 'failure.json').write_text(
                json.dumps(failure, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
            for name in ('stdout', 'stderr'):
                partial = getattr(error, name, None)
                if partial:
                    (destination / ('partial-' + name + '.log')).write_bytes(
                        partial.encode('utf-8') if isinstance(partial, str) else partial)
            raise
        return result, time.monotonic() - before

    noisy = [f'INFO synthetic progress {number:03d}\n' for number in range(1, 121)]
    noisy[19] = 'ERROR E_FIRST: 日本語の先頭診断\n'
    noisy[99] = 'ERROR E_LATE: second independent failure\n'
    noisy[109] = 'WARNING W_LATE: recovery required\n'
    fixtures = {
        'T2': ''.join(noisy),
        'T4': ''.join(f'synthetic/File{number:03d}.kt:{number}: '
                      + ('TARGET required dependency' if number in (20, 100) else 'unrelated match')
                      + '\n' for number in range(1, 121)),
        'T5': '日本語' + 'x' * 10000 + ' END_LONG\n',
    }
    expected = {
        'T1': ['PASSED'], 'T2': ['E_FIRST', 'E_LATE', 'W_LATE'],
        'T3': ['skipped=1', '"Warning": 1'],
        'T4': ['File020.kt:20: TARGET', 'File100.kt:100: TARGET'],
        'T5': ['日本語', 'END_LONG'],
    }
    for case in ('T1', 'T2', 'T3', 'T4', 'T5'):
        for repeat in (1, 2):
            order = ('full', 'aggregate') if repeat == 1 else ('aggregate', 'full')
            for condition in order:
                run_dir = destination / f'{case}-{repeat}-{condition}'
                run_dir.mkdir()
                relative = run_dir.relative_to(ROOT)
                returned, seconds, additional, refused = [], 0.0, 0, 0
                initial_missing = []

                def call(argv):
                    nonlocal seconds
                    result, elapsed = invoke(argv)
                    seconds += elapsed
                    returned.append(result.stdout + result.stderr)
                    return result

                def excerpt(*options):
                    return call([PYTHON, 'scripts/read_excerpt.py', str(log), *options])

                if case in ('T1', 'T2', 'T3'):
                    reports = []
                    if case == 'T1':
                        command = [PYTHON, '-m', 'unittest', 'discover', '-s',
                                   'scripts/tests', '-p', 'test_adoption_tools.py', '-v']
                    elif case == 'T2':
                        command = [PYTHON, '-c', 'import sys; sys.stdout.write('
                                   + repr(fixtures[case]) + '); sys.exit(7)']
                    else:
                        junit = '<testsuite tests="1" skipped="1"><testcase name="synthetic"><skipped/></testcase></testsuite>'
                        lint = '<issues><issue severity="Warning"/></issues>'
                        command = [PYTHON, '-c', 'from pathlib import Path; '
                                   + f'Path({str(relative / "junit.xml")!r}).write_text({junit!r}); '
                                   + f'Path({str(relative / "lint.xml")!r}).write_text({lint!r}); '
                                   + 'print(\'skipped=1; "Warning": 1\')']
                        reports = ['--junit', str(relative / 'junit.xml'),
                                   '--lint', str(relative / 'lint.xml')]
                    log = relative / 'check' / 'command.log'
                    if condition == 'aggregate':
                        result = call([PYTHON, 'scripts/run_check.py', '--output-dir',
                                       str(relative / 'check'), *reports, '--', *command])
                    else:
                        result = call(command)
                        log.parent.mkdir()
                        log.write_text(returned[-1], encoding='utf-8')
                    command_code = result.returncode
                else:
                    log = relative / 'source.log'
                    log.write_text(fixtures[case], encoding='utf-8')
                    command_code = 0
                    if condition == 'full':
                        result = call([PYTHON, '-c', 'import sys; from pathlib import Path; '
                                       'sys.stdout.write(Path(sys.argv[1]).read_text())', str(log)])

                if condition == 'aggregate' and case in ('T2', 'T4', 'T5'):
                    if case == 'T2':
                        excerpt('--match', 'ERROR', '--before', '1', '--lines', '4')
                    elif case == 'T4':
                        excerpt('--match', 'TARGET', '--before', '1', '--lines', '4')
                    else:
                        result = excerpt()
                        refused = int(result.returncode != 0)
                    initial_missing = [token for token in expected[case]
                                       if token not in ''.join(returned)]
                    if initial_missing:
                        additional += 1
                        # Fixed recovery policy: read all for separated diagnostics,
                        # the later search hit, or explicitly raise a long-line cap.
                        if case == 'T2':
                            excerpt('--lines', '120')
                        elif case == 'T4':
                            excerpt('--start', '99', '--lines', '4')
                        else:
                            excerpt('--lines', '1', '--max-chars', '12000')

                body = ''.join(returned)
                (run_dir / 'returned.txt').write_text(body, encoding='utf-8')
                tokens = ['OK'] if case == 'T1' and condition == 'full' else expected[case]
                missing = [token for token in tokens if token not in body]
                expected_code = 7 if case == 'T2' else 0
                rows.append(dict(case=case, repeat=repeat, condition=condition,
                                 returned_chars=len(body), wall_seconds=round(seconds, 6),
                                 additional_reads=additional, refused_reads=refused,
                                 initial_missing=initial_missing, final_missing=missing,
                                 command_exit_code=command_code,
                                 oracle_passed=not missing and command_code == expected_code,
                                 returned_sha256=hashlib.sha256(body.encode()).hexdigest()))
                (destination / 'progress.json').write_text(
                    json.dumps({'completed_trials': rows}, ensure_ascii=False, indent=2) + '\n',
                    encoding='utf-8')

    sources = ['scripts/run_check.py', 'scripts/read_excerpt.py',
               'scripts/tests/test_adoption_tools.py',
               'docs/records/evaluations/2026-11-15-ca007-protocol.md',
               str(Path(__file__).relative_to(ROOT))]
    result = dict(schema_version=1, scope='model-free preflight; not task success',
                  head=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT,
                                               text=True).strip(),
                  python=platform.python_version(),
                  source_sha256={path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest()
                                 for path in sources},
                  fixture_sha256={key: hashlib.sha256(value.encode()).hexdigest()
                                  for key, value in fixtures.items()},
                  measurements=dict(all_agent_input_tokens=None, all_agent_output_tokens=None,
                                    task_completion_seconds=None, actual_cost=None,
                                    model_additional_reads=None, review_rework=None),
                  preparation_and_probe_seconds=round(time.monotonic() - started, 6),
                  trials=rows, summary=[])
    for case in expected:
        groups = {condition: [r for r in rows if r['case'] == case and r['condition'] == condition]
                  for condition in ('full', 'aggregate')}
        totals = {condition: sum(r['returned_chars'] for r in group)
                  for condition, group in groups.items()}
        result['summary'].append(dict(case=case, returned_chars=totals,
                                      char_reduction_percent=round(100 * (1 - totals['aggregate'] / totals['full']), 3),
                                      median_seconds={condition: statistics.median(r['wall_seconds'] for r in group)
                                                      for condition, group in groups.items()}))
    (destination / 'results.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'trials': len(rows), 'oracle_passed': sum(r['oracle_passed'] for r in rows),
                      'summary': result['summary']}, ensure_ascii=False, indent=2))
    return 0 if all(row['oracle_passed'] for row in rows) else 1


if __name__ == '__main__':
    raise SystemExit(main())
