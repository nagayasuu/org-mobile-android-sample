#!/usr/bin/env python3
"""Run the settings gate and E2E suite once, retaining separate evidence."""

import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time
import xml.etree.ElementTree as ET


TEST_CLASS = 'dev.orgmobile.reader.ReaderE2eTest'
PREFLIGHT = 'settingsPreflightRestoresCustomNightModesAndWaitsForDocument'
JUNIT = 'app/build/outputs/androidTest-results/managedDevice/debug/pixel2Api37/TEST-*.xml'
EVIDENCE = ('reports/androidTests', 'outputs/androidTest-results',
            'outputs/managed_device_android_test_additional_output')


def run_phase(root, phase):
    output = root / phase
    started = time.time_ns()
    command = ['./gradlew', '--console=plain', '--profile',
               ':app:pixel2Api37DebugAndroidTest', '--rerun',
               '-Pandroid.testoptions.manageddevices.emulator.gpu=swangle']
    selection = TEST_CLASS + ('#' + PREFLIGHT if phase == 'preflight' else '')
    command.append('-Pandroid.testInstrumentationRunnerArguments.class=' + selection)
    if phase == 'suite':
        command.append('-Pandroid.testInstrumentationRunnerArguments.notClass=' + TEST_CLASS + '#' + PREFLIGHT)
    # These are generated device-test outputs only. Never let a failed launch
    # preserve a previous phase's XML or screenshots as its own evidence.
    for relative in EVIDENCE:
        source = Path('app/build') / relative
        if source.is_dir():
            shutil.rmtree(source)
    check = Path(__file__).with_name('run_check.py').resolve()
    result = subprocess.run([sys.executable, str(check), '--output-dir', str(output),
                             '--progress-interval', '60', '--timeout', '1200',
                             '--junit', JUNIT, '--', *command])
    # A failed command must also retain its reports and device diagnostics.
    # Archiving failures fail a successful run, but never replace its original
    # nonzero exit (including a timeout) with a generic exception exit.
    archive_errors = []

    def archive(source, target):
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            if source.is_dir():
                shutil.copytree(source, target)
            else:
                shutil.copy2(source, target)
        except OSError as error:
            archive_errors.append({'source': str(source), 'error': type(error).__name__})

    try:
        for relative in EVIDENCE:
            source = Path('app/build') / relative
            if source.is_dir():
                archive(source, output / relative)
        profile = Path('build/reports/profile')
        if profile.is_dir():
            for source in profile.iterdir():
                if source.is_dir() or source.stat().st_mtime_ns >= started:
                    archive(source, output / 'gradle-profile' / source.name)
    except OSError as error:
        archive_errors.append({'source': 'phase evidence listing', 'error': type(error).__name__})
    summary_file = output / 'summary.json'
    try:
        summary = json.loads(summary_file.read_text()) if summary_file.exists() else {}
    except (OSError, ValueError):
        print('FAILED: phase summary could not be read', file=sys.stderr)
        return result.returncode or 1, set()
    cases = set()
    code = result.returncode
    if archive_errors:
        summary['status'] = 'failed'
        summary['archive_errors'] = archive_errors
        code = code or 1
    # Point saved evidence at this phase's copy, since the next phase replaces
    # the original generated files. Never let preflight refer to suite XML.
    if 'junit' in summary and not archive_errors:
        summary['junit']['reports'] = [str(output / Path(path).relative_to('app/build'))
                                       for path in summary['junit']['reports']]
    if code == 0:
        try:
            for path in summary.get('junit', {}).get('reports', []):
                for case in ET.parse(path).getroot().iter('testcase'):
                    cases.add((case.get('classname'), case.get('name')))
            expected = 1 if phase == 'preflight' else 9
            counts = summary.get('junit', {})
            valid = (counts.get('tests') == expected and len(cases) == expected and
                     counts.get('skipped') == 0 and
                     (cases == {(TEST_CLASS, PREFLIGHT)} if phase == 'preflight' else
                      (TEST_CLASS, PREFLIGHT) not in cases and all(c == TEST_CLASS for c, _ in cases)))
        except (OSError, ValueError, ET.ParseError):
            valid = False
        if not valid:
            summary['status'] = 'failed'
            summary['selection_error'] = 'Unexpected E2E cases or skipped tests'
            print('FAILED: unexpected E2E selection; see ' + str(summary_file), file=sys.stderr)
            code = 1
    if summary_file.exists():
        try:
            summary_file.write_text(json.dumps(summary, indent=2) + '\n')
        except OSError:
            print('FAILED: phase evidence summary could not be saved', file=sys.stderr)
            code = code or 1
    return code, cases


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True,
                        help='New directory for phase logs, timing, reports and diagnostics')
    args = parser.parse_args()
    if any(args.output_dir.resolve().is_relative_to((Path('app/build') / path).resolve())
           for path in EVIDENCE):
        parser.error('output directory must be outside generated device-test outputs')
    try:
        args.output_dir.mkdir(parents=True, exist_ok=False)
    except OSError:
        parser.error('choose an unused output directory')
    executed = set()
    for phase in ('preflight', 'suite'):
        code, cases = run_phase(args.output_dir, phase)
        if code:
            return code
        if executed & cases:
            return 1
        executed.update(cases)
    (args.output_dir / 'selection.json').write_text(json.dumps({
        'tests': len(executed), 'cases': sorted(name for _, name in executed),
        'scope': 'one settings gate plus nine remaining scenarios; no retries or shards',
    }, indent=2) + '\n')
    print('PASSED: 10 distinct E2E scenarios (settings gate 1 + remaining 9)')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
