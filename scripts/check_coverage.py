#!/usr/bin/env python3
"""Validate JaCoCo XML with exact ratios and compare existing changed sources."""

import argparse
from fractions import Fraction
from pathlib import Path
import xml.etree.ElementTree as ET


METRICS = ("LINE", "BRANCH")
MINIMUM = Fraction(4, 5)
SOURCE_ROOT = Path("app/src/main/java")
REPORT = Path("app/build/reports/coverage/test/debug/report.xml")
EXECUTION_DATA = Path("app/build/outputs/unit_test_code_coverage/debugUnitTest/testDebugUnitTest.exec")


def require_artifacts(root):
    for artifact in (REPORT, REPORT.parent / "index.html", EXECUTION_DATA):
        path = root / artifact
        if not path.is_file() or not path.stat().st_size:
            raise ValueError(f"Missing or empty coverage artifact: {artifact}")


def counters(element):
    result = {}
    for metric in METRICS:
        node = element.find(f"counter[@type='{metric}']")
        missed, covered = (0, 0) if node is None else (
            int(node.attrib["missed"]), int(node.attrib["covered"]))
        if missed < 0 or covered < 0:
            raise ValueError("Negative coverage counter")
        result[metric] = (covered, missed + covered)
    return result


def read_report(path, source_root):
    root = ET.parse(path).getroot()
    if root.tag != "report" or root.find("sessioninfo") is None:
        raise ValueError("Missing JaCoCo execution session")
    sources = {}
    for package in root.findall("package"):
        for source in package.findall("sourcefile"):
            key = f"{package.attrib['name']}/{source.attrib['name']}"
            if key in sources:
                raise ValueError(f"Duplicate source: {key}")
            sources[key] = counters(source)
    expected = {
        path.relative_to(source_root).as_posix()
        for path in source_root.rglob("*") if path.suffix in (".kt", ".java")
    }
    if not expected or expected - sources.keys():
        raise ValueError(f"Missing application sources: {sorted(expected - sources.keys())}")
    # AGP may list an inlined dependency source with no executable counters.
    for key in sources.keys() - expected:
        if any(total for _, total in sources[key].values()):
            raise ValueError(f"Unexpected executable source: {key}")
    total = counters(root)
    if not total["LINE"][1] or not total["LINE"][0]:
        raise ValueError("Missing application execution data")
    for metric in METRICS:
        summed = tuple(sum(sources[key][metric][i] for key in expected) for i in (0, 1))
        if total[metric] != summed:
            raise ValueError(f"Report/source totals differ: {metric}")
    return total, sources


def describe(value):
    covered, total = value
    return "N/A (no branches)" if total == 0 else f"{covered}/{total} ({100 * covered / total:.2f}%)"


def check_minimum(total):
    for metric in METRICS:
        covered, count = total[metric]
        print(f"Overall {metric}: {describe(total[metric])}")
        if count and Fraction(covered, count) < MINIMUM:
            raise ValueError(f"{metric} coverage is below 80%")


def compare(before, after, changed):
    if not changed:
        print("Regression comparison: no comparable changed existing sources")
        return
    for key in changed:
        if key not in before or key not in after:
            raise ValueError(f"Missing comparison source: {key}")
    for metric in METRICS:
        old = tuple(sum(before[key][metric][i] for key in changed) for i in (0, 1))
        new = tuple(sum(after[key][metric][i] for key in changed) for i in (0, 1))
        print(f"Changed sources {metric}: {describe(old)} -> {describe(new)}")
        if not old[1] or not new[1]:
            print(f"Regression {metric}: N/A (zero denominator)")
        elif Fraction(new[0], new[1]) < Fraction(old[0], old[1]):
            raise ValueError(f"Changed sources {metric} coverage decreased")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, default=REPORT)
    args = parser.parse_args()
    try:
        total, _ = read_report(args.report, SOURCE_ROOT)
        check_minimum(total)
    except (OSError, ET.ParseError, KeyError, ValueError) as error:
        parser.exit(1, f"Coverage check failed: {error}\n")


if __name__ == "__main__":
    main()
