#!/usr/bin/env python3
"""Write the machine-readable evidence for a successful Android verify job."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import xml.etree.ElementTree as ET

from check_coverage import METRICS, check_minimum
from run_check import LINT_SEVERITIES, junit_reports, lint_reports


SCHEMA_VERSION = 1
MANIFEST = "verification.json"
OUTPUT = Path("app/build/ci-verification") / MANIFEST
APK = Path("app/build/outputs/apk/debug/app-debug.apk")
REPORTS = Path("app/build/reports")
VARIANTS = ("Debug", "Release")
TEST_COUNTS = ("tests", "failures", "errors", "skipped")
SHA = re.compile(r"[0-9a-f]{40}")
SHA256 = re.compile(r"[0-9a-f]{64}")


def is_count(value):
    return type(value) is int and value >= 0


def apk_sha256(path):
    if not path.stat().st_size:
        raise ValueError("Debug APK is empty")
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for block in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def validate_results(manifest):
    tests = manifest.get("tests")
    if not isinstance(tests, dict) or set(tests) != set(VARIANTS):
        raise ValueError("Expected Debug and Release JUnit summaries")
    for variant in VARIANTS:
        counts = tests[variant]
        if (not isinstance(counts, dict) or set(counts) != set(TEST_COUNTS)
                or not all(is_count(count) for count in counts.values())):
            raise ValueError(f"Invalid {variant} JUnit counts")
        if counts["tests"] <= counts["skipped"] or counts["failures"] or counts["errors"]:
            raise ValueError(f"{variant} JUnit tests did not pass or none ran")

    lint = manifest.get("lint")
    if (not isinstance(lint, dict) or lint.keys() - set(LINT_SEVERITIES)
            or not all(is_count(count) for count in lint.values())):
        raise ValueError("Invalid Android Lint counts")
    if any(lint.get(severity, 0) for severity in ("Fatal", "Error", "Warning")):
        raise ValueError("Android Lint reported errors or warnings")

    coverage = manifest.get("coverage")
    if not isinstance(coverage, dict) or coverage.get("status") != "passed":
        raise ValueError("Coverage verification did not pass")
    regression_options = ("passed", "no comparable sources") if coverage.get("base") else ("not performed",)
    if coverage.get("regression") not in regression_options:
        raise ValueError("Invalid coverage regression result")
    counters = coverage.get("counters")
    if not isinstance(counters, dict) or set(counters) != set(METRICS):
        raise ValueError("Missing coverage counters")
    for metric in METRICS:
        values = counters[metric]
        if (not isinstance(values, list) or len(values) != 2
                or not all(is_count(count) for count in values) or values[0] > values[1]):
            raise ValueError(f"Invalid {metric} coverage counters")
    if not counters["LINE"][1]:
        raise ValueError("Coverage lacks line data")
    check_minimum(counters)

    digest = manifest.get("apk_sha256")
    if not isinstance(digest, str) or not SHA256.fullmatch(digest):
        raise ValueError("Invalid debug APK SHA-256")


def collect(root, env):
    event = json.loads(Path(env["GITHUB_EVENT_PATH"]).read_text(encoding="utf-8"))
    event_name = env["GITHUB_EVENT_NAME"]
    tested, *parents = subprocess.check_output(
        ["git", "rev-list", "--parents", "-n", "1", "HEAD"], cwd=root, text=True
    ).split()
    if tested != env["GITHUB_SHA"] or not all(SHA.fullmatch(sha) for sha in [tested, *parents]):
        raise ValueError("Checkout does not match the workflow SHA")

    pr_number = pr_head = None
    if event_name == "pull_request":
        pr_number = event["number"]
        pr_head = event["pull_request"]["head"]["sha"]
        base = event["pull_request"]["base"]["sha"]
        if parents != [base, pr_head] or not is_count(pr_number) or not pr_number:
            raise ValueError("Checkout parents do not match the PR base and head")
    elif event_name == "push":
        base = event["before"]
        if base == "0" * 40:
            base = None
        if tested != event["after"]:
            raise ValueError("Checkout does not match the pushed SHA")
    else:
        raise ValueError("Unsupported workflow event")

    run_id = int(env["GITHUB_RUN_ID"])
    attempt = int(env["GITHUB_RUN_ATTEMPT"])
    if run_id < 1 or attempt < 1:
        raise ValueError("Invalid workflow run or attempt")

    report = json.loads((root / REPORTS / "coverage/comparison.json").read_text(encoding="utf-8"))
    if report["head"] != tested or report["base"] != base:
        raise ValueError("Coverage was measured for a different checkout or base")
    tests = {}
    for variant in VARIANTS:
        paths = sorted((root / f"app/build/test-results/test{variant}UnitTest").glob("TEST-*.xml"))
        if not paths:
            raise ValueError(f"Missing {variant} JUnit XML")
        result = junit_reports(paths)
        tests[variant] = {key: result[key] for key in TEST_COUNTS}
    lint = lint_reports([root / REPORTS / "lint-results-debug.xml"])
    manifest = dict(
        schema_version=SCHEMA_VERSION, repository=env["GITHUB_REPOSITORY"],
        run_id=run_id, run_attempt=attempt, event=event_name, pr_number=pr_number,
        pr_head_sha=pr_head, tested_sha=tested, parents=parents, tests=tests,
        lint=lint["severities"],
        coverage={key: report[key] for key in ("base", "status", "regression", "counters")},
        apk_sha256=apk_sha256(root / APK),
    )
    validate_results(manifest)
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    output = root / OUTPUT
    try:
        output.unlink(missing_ok=True)
        manifest = collect(root, os.environ)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    except (OSError, ValueError, KeyError, TypeError, ET.ParseError, subprocess.CalledProcessError) as error:
        message = str(error) if type(error) is ValueError else type(error).__name__
        parser.exit(1, f"CI verification manifest failed: {message}\n")


if __name__ == "__main__":
    main()
