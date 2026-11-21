#!/usr/bin/env python3
"""Report integration step timings from the local journal and recorded attempts."""

import argparse
from datetime import datetime, timedelta
import json
import math
from pathlib import Path

from ci_verification import SHA
from integrate_pr import REPO, STEPS, timing_path


def seconds(value):
    if type(value) not in (float, int) or not math.isfinite(value) or value < 0:
        raise ValueError("Invalid elapsed seconds")
    return value


def utc(value):
    timestamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if timestamp.utcoffset() != timedelta(0):
        raise ValueError("Timestamps must be UTC")
    return timestamp


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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", type=Path, required=True, help="Integration journal")
    parser.add_argument("--format", choices=("markdown", "json"), default="markdown")
    args = parser.parse_args()
    timing = timing_path(args.state)
    try:
        exists = args.state.exists()
        journal = json.loads(args.state.read_text(encoding="utf-8")) if exists else {}
        attempts = []
        if timing.exists():
            data = json.loads(timing.read_text(encoding="utf-8"))
            repo, head = data["repo"], data["head"]
            if (not REPO.fullmatch(repo) or not SHA.fullmatch(head)
                    or (exists and (journal["repo"].lower() != repo.lower() or journal["head"] != head))):
                raise ValueError("Timing records differ from the journal")
            attempts = data["attempts"]
        elif not exists:
            raise ValueError("No integration journal or timing records")
        report = summarize(journal.get("done", {}), attempts)
    except (AttributeError, KeyError, OSError, OverflowError, TypeError, ValueError):
        parser.exit(2, "Cannot read integration timing records\n")
    if args.format == "markdown":
        markdown(report)
    else:
        print(json.dumps(report, allow_nan=False))


if __name__ == "__main__":
    main()
