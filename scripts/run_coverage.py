#!/usr/bin/env python3
"""Build fresh coverage and enforce the minimum and changed-source regression gate."""

import argparse
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
    return [line for line in path.read_text().splitlines()
            if line.strip() and line.strip() != APPLY]


def measure_base(base, destination):
    # git archive supplies only tracked public files, never local configuration.
    with tempfile.TemporaryFile() as archive:
        subprocess.run(["git", "archive", base], cwd=ROOT, stdout=archive, check=True)
        archive.seek(0)
        subprocess.run(["tar", "-xf", "-", "-C", str(destination)], stdin=archive, check=True)
    for name in TOOL_INPUTS:
        old = normalized_build(destination / name)
        new = normalized_build(ROOT / name)
        if old != new:
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
    args = parser.parse_args()
    os.chdir(ROOT)
    reports = ROOT / "app/build/reports/coverage"
    result = {"status": "failed"}
    # Remove reports even when resolving the base fails before Gradle can clean.
    shutil.rmtree(reports, ignore_errors=True)
    try:
        base = (resolve_base(args.github_event) if args.github_event else
                git("rev-parse", f"{args.base_ref}^{{commit}}") if args.base_ref else None)
        head = git("rev-parse", "HEAD")
        result.update(head=head, base=base)
        print(f"Coverage head: {head}; base: {base or 'unavailable'}", flush=True)
        # clean prevents stale XML/exec files, including after a failed test run.
        gradle(ROOT, ":app:clean", "check", "assembleDebug", ":app:createDebugUnitTestCoverageReport")
        require_artifacts(ROOT)
        total, current = read_report(ROOT / REPORT, ROOT / SOURCE_ROOT)
        result["counters"] = total
        check_minimum(total)
        changed = []
        if base:
            names = git("diff", "--no-renames", "--name-only", "--diff-filter=M", "-z",
                        base, "--", SOURCE_ROOT.as_posix()).split("\0")
            changed = sorted(str(Path(name).relative_to(SOURCE_ROOT)) for name in names
                             if name and Path(name).suffix in (".kt", ".java"))
            result["changed_sources"] = changed
            if changed:
                with tempfile.TemporaryDirectory(prefix="org-coverage-base-") as temporary:
                    destination = Path(temporary)
                    _, previous = measure_base(base, destination)
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
