#!/usr/bin/env python3
"""Build fresh coverage and enforce the minimum and changed-source regression gate."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import xml.etree.ElementTree as ET

from check_coverage import REPORT, SOURCE_ROOT, check_minimum, compare, read_report, require_artifacts


ROOT = Path(__file__).resolve().parents[1]
SETTINGS = "gradle/coverage.gradle"
APPLY = 'apply(from = rootProject.file("gradle/coverage.gradle"))'
TOOL_INPUTS = (
    "build.gradle.kts", "app/build.gradle.kts", "settings.gradle.kts",
    "gradle.properties", "gradle/wrapper/gradle-wrapper.properties",
)


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT).decode().strip()


def resolve_base(event_path):
    event = json.loads(event_path.read_text())
    if "pull_request" in event:
        branch = event["pull_request"]["base"]["ref"]
        subprocess.run(["git", "fetch", "--no-tags", "origin", f"refs/heads/{branch}"],
                       cwd=ROOT, check=True)
        return git("rev-parse", "FETCH_HEAD")
    before = event.get("before", "")
    return None if not before or set(before) == {"0"} else git("rev-parse", f"{before}^{{commit}}")


def gradle(directory, *tasks):
    subprocess.run([str(directory / "gradlew"), "--no-daemon", "--console=plain", *tasks],
                   cwd=directory, check=True)


def normalized_build(path):
    return normalized_text(path.read_text(encoding='utf-8'))


def normalized_text(text):
    return [line for line in text.splitlines()
            if line.strip() and line.strip() != APPLY]


def changed_sources(base):
    if not base:
        return []
    names = git("diff", "--no-renames", "--name-only", "--diff-filter=M", "-z",
                base, "--", SOURCE_ROOT.as_posix()).split("\0")
    return sorted(str(Path(name).relative_to(SOURCE_ROOT)) for name in names
                  if name and Path(name).suffix in (".kt", ".java"))


def build_conditions(base, required=True):
    inputs = {}
    for name in (*TOOL_INPUTS, SETTINGS):
        try:
            inputs[name] = (ROOT / name).read_bytes()
        except FileNotFoundError:
            inputs[name] = None
    if required:
        if any(data is None for data in inputs.values()):
            raise ValueError('Missing comparison input; restore build and coverage settings')
        for name in TOOL_INPUTS:
            previous = subprocess.check_output(["git", "show", f"{base}:{name}"], cwd=ROOT)
            if normalized_text(previous.decode('utf-8')) != normalized_text(inputs[name].decode('utf-8')):
                raise ValueError(f"Measurement conditions changed: {name}; compare with matching tool settings")
    return {"conditions_checked": required,
            "input_sha256": {name: hashlib.sha256(data).hexdigest() if data is not None else None
                             for name, data in inputs.items()}}


def context(args):
    base = (resolve_base(args.github_event) if args.github_event else
            git("rev-parse", "--verify", "--end-of-options", f"{args.base_ref}^{{commit}}")
            if args.base_ref else None)
    return base, git("rev-parse", "HEAD"), changed_sources(base)


def confirm_inputs(conditions, base, changed):
    if conditions['input_sha256'] != build_conditions(None, required=False)['input_sha256']:
        raise ValueError('Build inputs changed during verification; repeat with fixed inputs')
    if changed_sources(base) != changed:
        raise ValueError('Comparison source set changed during verification; repeat with fixed inputs')


def measure_base(base, destination):
    # git archive supplies only tracked public files, never local configuration.
    with tempfile.TemporaryFile() as archive:
        subprocess.run(["git", "archive", base], cwd=ROOT, stdout=archive, check=True)
        archive.seek(0)
        subprocess.run(["tar", "-xf", "-", "-C", str(destination)], stdin=archive, check=True)
    # Keep the original guard on the files actually exported for the baseline.
    for name in TOOL_INPUTS:
        if normalized_build(destination / name) != normalized_build(ROOT / name):
            raise ValueError(f"Measurement conditions changed: {name}; compare with matching tool settings")
    (destination / SETTINGS).parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(ROOT / SETTINGS, destination / SETTINGS)
    app_build = destination / "app/build.gradle.kts"
    if APPLY not in app_build.read_text():
        with app_build.open("a") as output:
            output.write(f"\n{APPLY}\n")
    gradle(destination, ":app:createDebugUnitTestCoverageReport")
    require_artifacts(destination)
    return read_report(destination / REPORT, destination / SOURCE_ROOT)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--base-ref", help="Base Git commit; includes uncommitted changes locally")
    group.add_argument("--github-event", type=Path)
    parser.add_argument("--preflight-only", action="store_true",
                        help="Read-only build-condition check; never runs Gradle or deletes reports")
    args = parser.parse_args()
    if args.preflight_only and not args.base_ref:
        parser.error('--preflight-only requires an explicit --base-ref')
    os.chdir(ROOT)
    if args.preflight_only:
        try:
            base, head, changed = context(args)
            if not base:
                raise ValueError('A resolved base is required for preflight')
            conditions = build_conditions(base, required=bool(changed))
            print(json.dumps({"status": "passed", "mode": "preflight", "coverage": "not-run",
                              "head": head, "base": base, "changed_sources": changed, **conditions}))
            return 0
        except (OSError, ValueError, KeyError, subprocess.CalledProcessError) as error:
            parser.exit(1, f"Build preflight failed: {error}\n")
    reports = ROOT / "app/build/reports/coverage"
    result = {"status": "failed"}
    # Remove reports even when resolving the base fails before Gradle can clean.
    shutil.rmtree(reports, ignore_errors=True)
    try:
        base, head, changed = context(args)
        result.update(head=head, base=base, changed_sources=changed)
        conditions = build_conditions(base, required=bool(changed))
        result.update(conditions)
        print(f"Coverage head: {head}; base: {base or 'unavailable'}", flush=True)
        # clean prevents stale XML/exec files, including after a failed test run.
        gradle(ROOT, ":app:clean", "check", "assembleDebug", ":app:createDebugUnitTestCoverageReport")
        confirm_inputs(conditions, base, changed)
        require_artifacts(ROOT)
        total, current = read_report(ROOT / REPORT, ROOT / SOURCE_ROOT)
        result["counters"] = total
        check_minimum(total)
        if base:
            if changed:
                with tempfile.TemporaryDirectory(prefix="org-coverage-base-") as temporary:
                    destination = Path(temporary)
                    _, previous = measure_base(base, destination)
                    confirm_inputs(conditions, base, changed)
                    shutil.copytree(destination / REPORT.parent, reports / "baseline")
                    compare(previous, current, changed)
            else:
                compare({}, current, changed)
        else:
            print("Regression comparison: NOT PERFORMED (no base revision)")
        result.update(status="passed", changed_sources=changed,
                      regression="passed" if changed else "no comparable sources" if base else "not performed")
    except (OSError, ValueError, KeyError, ET.ParseError, subprocess.CalledProcessError) as error:
        parser.exit(1, f"Coverage verification failed: {error}\n")
    finally:
        reports.mkdir(parents=True, exist_ok=True)
        (reports / "comparison.json").write_text(json.dumps(result, indent=2) + "\n")


if __name__ == "__main__":
    main()
