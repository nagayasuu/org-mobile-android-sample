#!/usr/bin/env python3
"""Render selected verification records as Markdown for a PR or review."""

import argparse
from contextlib import redirect_stdout
import io
import json
import math
from pathlib import Path
import re

from ci_verification import SCHEMA_VERSION, SHA, SHA256, TEST_COUNTS, is_count, validate_results
from run_check import LINT_SEVERITIES


STATUSES = {"passed": "成功", "failed": "失敗", "unconfirmed": "未確認"}
REPORT_NAMES = {"junit": "JUnit", "lint": "Lint"}


def checked(condition):
    if not condition:
        raise ValueError("Invalid verification record")


def junit_text(counts):
    checked(all(is_count(counts[key]) for key in TEST_COUNTS))
    return "総数 {} / 失敗 {} / エラー {} / スキップ {}".format(
        *(counts[key] for key in TEST_COUNTS)
    )


def lint_text(counts):
    checked(isinstance(counts, dict) and counts.keys() <= set(LINT_SEVERITIES)
            and all(is_count(value) for value in counts.values()))
    severities = [f"{key} {counts[key]}" for key in LINT_SEVERITIES if counts.get(key)]
    return "、".join(severities) or "指摘 0"


def local_result(record):
    status = record["status"]
    revision = record["revision"]
    head, diff = revision["head"], revision.get("tracked_diff_sha256")
    checked(head is None or SHA.fullmatch(head))
    checked(diff is None or SHA256.fullmatch(diff))
    seconds = record["wall_seconds"]
    code = record["command_exit_code"]
    checked(type(seconds) in (int, float) and math.isfinite(seconds) and seconds >= 0)
    checked(code is None or is_count(code))
    checked(isinstance(record["report_errors"], list))
    reports = {error["kind"] for error in record["report_errors"]}
    checked(reports <= REPORT_NAMES.keys())
    checked(status != "passed" or (code == 0 and not reports))
    status_text = STATUSES[status]
    tests = record.get("junit")
    lint = record.get("lint")
    details = [status_text, f"終了コード {code if code is not None else '未確認'}", f"{seconds:.3f} 秒"]
    if tests is not None:
        details.append(f"JUnit {junit_text(tests)}")
        checked(status != "passed" or not (tests["failures"] or tests["errors"]))
    if lint is not None:
        severities = lint["severities"]
        details.append(f"Lint {lint_text(severities)}")
        checked(status != "passed" or not (severities.get("Error") or severities.get("Fatal")))
    missing = [f"{name} レポート未確認" for kind, name in REPORT_NAMES.items() if kind in reports]
    if head is None:
        missing.append("HEAD 未確認")
    if status != "passed":
        missing.append("元の検証記録を確認")
    target = f"HEAD {head or '未確認'} / 追跡済み差分 SHA-256 {diff or '未確認'}"
    return target, "、".join(details), "ローカル検証記録", "、".join(missing)


def ci_result(record):
    checked(isinstance(record["done"], dict) and {"wait", "artifacts"} <= record["done"].keys())
    repo, head, base = record["repo"], record["head"], record["base"]
    checked(re.fullmatch(r"[A-Za-z0-9_-]+/[A-Za-z0-9_.-]+", repo)
            and repo.split("/")[1] not in (".", "..")
            and SHA.fullmatch(head) and SHA.fullmatch(base))
    run, attempt, pr = record["run"], record["attempt"], record["pr"]
    checked(all(is_count(value) and value > 0 for value in (run, attempt, pr)))
    evidence = record["evidence"]
    tested = evidence["tested_sha"]
    checked(type(evidence["schema_version"]) is int and evidence["schema_version"] == SCHEMA_VERSION
            and SHA.fullmatch(tested) and tested != head and evidence["parents"] == [base, head])
    coverage = dict(base=base, status="passed", regression=evidence["regression"],
                    counters=evidence["coverage"])
    with redirect_stdout(io.StringIO()):
        validate_results({**evidence, "coverage": coverage})
    details = ["必須 verify 成功"]
    details.extend(f"{variant} JUnit {junit_text(evidence['tests'][variant])}"
                   for variant in ("Debug", "Release"))
    details.append(f"Lint {lint_text(evidence['lint'])}")
    counters = " / ".join(f"{metric} {covered}/{total}"
                          for metric, (covered, total) in sorted(coverage["counters"].items(), reverse=True))
    details.append(f"カバレッジ {counters}（比較 {coverage['regression']}）")
    details.append(f"Debug APK SHA-256 {evidence['apk_sha256']}")
    source = f"[PR #{pr} / run {run} / attempt {attempt}](https://github.com/{repo}/actions/runs/{run})"
    return f"PR 先端 {head} / 検証対象 {tested}", "、".join(details), source, ""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--format", choices=("pr", "review"), required=True)
    parser.add_argument("--check", action="append", nargs=2, metavar=("ID", "SUMMARY"), default=[])
    parser.add_argument("--ci", action="append", nargs=2, metavar=("ID", "JOURNAL"), default=[])
    args = parser.parse_args()
    rows = {}
    for inputs, renderer in ((args.check, local_result), (args.ci, ci_result)):
        for label, path in inputs:
            if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,31}", label) or label in rows:
                parser.error("Use unique verification IDs of 1–32 letters, digits, hyphens or underscores")
            try:
                rows[label] = renderer(json.loads(Path(path).read_text(encoding="utf-8")))
            except (KeyError, OSError, OverflowError, TypeError, ValueError):
                parser.error(f"{label}: invalid or incomplete verification record")
    if not rows:
        parser.error("Select at least one --check or --ci record")
    if args.format == "review":
        print("| 検証ID | 実行者・今回実行／参照 | 対象版・環境・コマンド | 結果・件数・時間 | 根拠の参照先 | 未確認事項・次の確認 |")
        print("| --- | --- | --- | --- | --- | --- |")
        for label, (target, details, source, missing) in rows.items():
            print(f"| {label} | 記録参照 | {target} | {details} | {source} | {missing} |")
    else:
        for label, (target, details, source, missing) in rows.items():
            summary = "。".join(filter(None, (target, details, source, missing)))
            print(f"- {label} {summary}。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
