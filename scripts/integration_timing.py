#!/usr/bin/env python3
"""Report integration step timings from the local journal and recorded attempts."""

import argparse
import json
import math
from pathlib import Path

from ci_verification import SHA
from integrate_pr import REPO, STEPS, timing_path
from integration_usage import summarize_usage, utc


def seconds(value):
    if type(value) not in (float, int) or not math.isfinite(value) or value < 0:
        raise ValueError("Invalid elapsed seconds")
    return value


def summarize(done, attempts):
    if not isinstance(done, dict) or set(done) - set(STEPS) or not isinstance(attempts, list):
        raise ValueError("Invalid timing records")
    done = {step: seconds(value) for step, value in done.items()}
    groups = {step: [] for step in STEPS}
    intervals = []
    closed = []
    for item in attempts:
        step, status = item["step"], item["status"]
        invoked_step = item.get("invoked_step")
        valid_commands = (step, "verify-pr") if step in ("wait", "artifacts") else (step,)
        if invoked_step is not None and invoked_step not in valid_commands:
            raise ValueError("Invalid invocation for timing step")
        if status not in ("completed", "failed", "interrupted", "unfinished"):
            raise ValueError("Invalid attempt status")
        start = utc(item["started_utc"])
        end_text, elapsed = item["ended_utc"], item["elapsed_seconds"]
        clock_matches = None
        if status == "unfinished":
            if end_text is not None or elapsed is not None:
                raise ValueError("Unexpected completion for unfinished attempt")
            end = None
        else:
            end = utc(end_text)
            elapsed = seconds(elapsed)
            closed.append(elapsed)
            span = (end - start).total_seconds()
            clock_matches = span >= 0 and abs(span - elapsed) <= 1
            if clock_matches:
                intervals.append((start, end))
        groups[step].append(dict(invoked_step=invoked_step, status=status, start=start.isoformat(),
                                 end=end.isoformat() if end else None, elapsed=elapsed,
                                 clock_matches=clock_matches))

    rows = []
    timed_completed = set()
    for step, group in groups.items():
        for index, item in enumerate(group, 1):
            rows.append(dict(step=step, attempt=index, **item))
        if any(item["status"] == "completed" for item in group):
            timed_completed.add(step)
        elif step in done:
            rows.append(dict(step=step, status="unmeasured", elapsed=done[step]))
        elif not group:
            rows.append(dict(step=step, status="no-record"))

    active = 0
    if intervals:
        intervals.sort()
        left = end = intervals[0][0]
        for start, right in intervals:
            active += max(0, (right - max(start, end)).total_seconds())
            end = max(right, end)
        window = (end - left).total_seconds()
    else:
        window = None
    complete = bool(attempts) and timed_completed == set(done) and len(intervals) == len(attempts)
    return dict(rows=rows, journal_completed_seconds=done, interval_timings_complete=complete,
                observed_attempt_seconds=round(sum(closed), 3) if closed else None,
                observed_active_seconds=round(active, 3) if intervals else None,
                observed_window_seconds=round(window, 3) if window is not None else None,
                active_seconds=round(active, 3) if complete else None,
                window_seconds=round(window, 3) if complete else None)


def markdown(report):
    print("| 工程 | 実行コマンド | 試行 | 結果 | 開始 UTC | 終了 UTC | 秒 | 台帳の成功秒数 |")
    print("| --- | --- | ---: | --- | --- | --- | ---: | ---: |")
    for row in report["rows"]:
        step = row["step"]
        status = row["status"] + ("（時計不一致）" if row.get("clock_matches") is False else "")
        journal_seconds = report["journal_completed_seconds"].get(step) if row["status"] in (
            "completed", "unmeasured"
        ) else None
        values = [step, row.get("invoked_step"), row.get("attempt"), status, row.get("start"), row.get("end"),
                  row.get("elapsed"), journal_seconds]
        print("| " + " | ".join("—" if value is None else str(value) for value in values) + " |")
    print()
    for label, key in (("観測できた試行時間の合計", "observed_attempt_seconds"),
                       ("観測できた区間の和集合", "observed_active_seconds"),
                       ("観測できた経過窓", "observed_window_seconds"),
                       ("全記録の区間の和集合", "active_seconds"), ("全記録の経過窓", "window_seconds")):
        value = report[key]
        print(f"- {label}　{'未計測' if value is None else f'{value} 秒'}")
    if "usage" in report:
        print_usage(report)


def print_usage(report):
    print("\n| 工程・試行 | 区間 | 完全性確認済み／対象担当 | 観測応答数 | 観測入力 | うちキャッシュ | 観測出力 | 観測入出力計 | 全担当の入出力計 |")
    print("| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |")
    for row in report["rows"]:
        usage = row.get("usage")
        if usage is None:
            continue
        observed, total = usage["observed"] or {}, usage["total"] or {}
        coverage = f"{usage['complete_actors']}/{usage['expected_actors']}"
        values = [f"{row['step']} #{row['attempt']}", usage["scope"], coverage,
                  observed.get("responses"), observed.get("input_tokens"),
                  observed.get("cached_input_tokens"), observed.get("output_tokens"),
                  observed.get("total_tokens"), total.get("total_tokens")]
        print("| " + " | ".join("—" if value is None else str(value) for value in values) + " |")
    if not report["usage"]["actors_complete"]:
        print("\n- 対象担当の一覧は未確定。")
    unassigned = report["usage"]["unassigned"]
    if unassigned:
        print(f"\n- 工程未割当の観測値　{unassigned['responses']} 応答、{unassigned['total_tokens']} トークン")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", type=Path, required=True, help="Integration journal")
    parser.add_argument("--usage-manifest", type=Path, help="Local actor logs and optional phase boundaries")
    parser.add_argument("--format", choices=("markdown", "json"), default="markdown")
    args = parser.parse_args()
    timing = timing_path(args.state)
    try:
        exists = args.state.exists()
        journal = json.loads(args.state.read_text(encoding="utf-8")) if exists else {}
        identity = journal
        attempts = []
        if timing.exists():
            data = json.loads(timing.read_text(encoding="utf-8"))
            repo, head = data["repo"], data["head"]
            if (not REPO.fullmatch(repo) or not SHA.fullmatch(head)
                    or (exists and (journal["repo"].lower() != repo.lower() or journal["head"] != head))):
                raise ValueError("Timing records differ from the journal")
            attempts = data["attempts"]
            identity = data
        elif not exists:
            raise ValueError("No integration journal or timing records")
        report = summarize(journal.get("done", {}), attempts)
    except (AttributeError, KeyError, OSError, OverflowError, TypeError, ValueError):
        parser.exit(2, "Cannot read integration timing records\n")
    if args.usage_manifest:
        try:
            manifest = json.loads(args.usage_manifest.read_text(encoding="utf-8"))
            if (manifest["head"] != identity["head"]
                    or manifest["repo"].lower() != identity["repo"].lower()):
                raise ValueError("Usage manifest differs from the journal")
            report["usage"] = summarize_usage(report["rows"], manifest, args.usage_manifest.parent)
        except (AttributeError, KeyError, OSError, OverflowError, TypeError, ValueError):
            parser.exit(2, "Cannot read integration usage; check the manifest and local session logs\n")
    if args.format == "markdown":
        markdown(report)
    else:
        print(json.dumps(report, allow_nan=False))


if __name__ == "__main__":
    main()
