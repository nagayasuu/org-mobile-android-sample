"""Attribute local Codex response usage to explicit integration time windows."""

from datetime import datetime, timedelta
import json
import re

from summarize_usage import METRICS, number


def utc(value):
    fraction = re.search(r"[.,][0-9]{6}([0-9]+)", value)
    if fraction and fraction[1].strip("0"):
        raise ValueError("UTC timestamps must have microsecond precision or less")
    timestamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if timestamp.utcoffset() != timedelta(0):
        raise ValueError("Timestamps must be UTC")
    return timestamp


def load_session(path):
    """Read only the owning thread's response metadata from an explicit log."""
    responses = {}
    with path.open(encoding="utf-8") as source:
        metadata = json.loads(next(source, ""))
        if metadata["type"] != "session_meta":
            raise ValueError("Expected session metadata")
        thread = metadata["payload"]["id"]
        if not isinstance(thread, str) or not thread:
            raise ValueError("Missing thread identity")
        first = last = utc(metadata["timestamp"])
        for line in source:
            event = json.loads(line)
            last = max(last, utc(event["timestamp"]))
            if event["type"] != "token_usage_record":
                continue
            record = event["payload"]
            if record["thread_id"] != thread:
                continue
            response = record["response_id"]
            if not isinstance(response, str) or not response:
                raise ValueError("Missing response identity")
            usage = {key: number(record["usage"][key], integer=True) for key in METRICS}
            if usage["cached_input_tokens"] > usage["input_tokens"]:
                raise ValueError("Cached input cannot exceed total input")
            when = utc(event["timestamp"])
            if response in responses:
                earlier, previous = responses[response]
                if previous != usage:
                    raise ValueError("Conflicting response usage")
                when = min(earlier, when)
            responses[response] = when, usage
    return thread, (first, last) if responses else None, responses


def totals(samples):
    tokens = {key: sum(sample[key] for sample in samples) for key in METRICS}
    return dict(responses=len(samples), **tokens,
                uncached_input_tokens=tokens["input_tokens"] - tokens["cached_input_tokens"],
                total_tokens=tokens["input_tokens"] + tokens["output_tokens"])


def usage_windows(rows, supplied, actors):
    if not isinstance(supplied, list):
        raise ValueError("Usage windows must be a list")
    attempts = {(row["step"], row["attempt"]): row for row in rows if "attempt" in row}
    windows = {}
    for item in supplied:
        key = item["step"], item["attempt"]
        if type(key[1]) is not int or key in windows or key not in attempts:
            raise ValueError("Usage window must identify one recorded attempt")
        start, end = utc(item["start"]), utc(item["end"])
        complete = item.get("complete_actors", [])
        if (not isinstance(complete, list) or len(set(complete)) != len(complete)
                or set(complete) - actors or start >= end):
            raise ValueError("Invalid usage window")
        row = attempts[key]
        if start > utc(row["start"]) or (row["end"] and end < utc(row["end"])):
            raise ValueError("Usage window must include the command interval")
        windows[key] = start, end, set(complete) if row.get("clock_matches") else set(), "phase"
    for key, row in attempts.items():
        if key not in windows and row.get("clock_matches"):
            windows[key] = utc(row["start"]), utc(row["end"]), set(), "command"
    return windows


def summarize_usage(rows, manifest, directory):
    actors = manifest["actors"]
    if not isinstance(actors, list) or not actors or type(manifest["actors_complete"]) is not bool:
        raise ValueError("List expected actors and attest whether the list is complete")
    ids = set()
    for actor in actors:
        label = actor["id"]
        if not re.fullmatch(r"[A-Za-z0-9_-]+", label) or label in ids:
            raise ValueError("Expected unique non-sensitive actor labels")
        ids.add(label)
    windows = usage_windows(rows, manifest.get("windows", []), ids)
    by_window = {key: [] for key in windows}
    unassigned = []
    if windows:
        span_start = min(window[0] for window in windows.values())
        span_end = max(window[1] for window in windows.values())
        threads = set()
        response_ids = set()
        for actor in actors:
            path = actor["events"]
            samples = {key: [] for key in windows}
            ambiguous = set()
            if path is None:
                bounds, responses = None, {}
            else:
                thread, bounds, responses = load_session(directory / path)
                if thread in threads:
                    raise ValueError("Thread listed more than once")
                if response_ids.intersection(responses):
                    raise ValueError("Response recorded under multiple threads")
                threads.add(thread)
                response_ids.update(responses)
            for when, usage in responses.values():
                if not span_start < when <= span_end:
                    continue
                matches = [key for key, (start, end, _, _) in windows.items() if start < when <= end]
                if len(matches) == 1:
                    samples[matches[0]].append(usage)
                else:
                    ambiguous.update(matches)
                    unassigned.append(usage)
            for key, (start, end, declared, _) in windows.items():
                covered = bool(bounds and bounds[0] <= start <= end <= bounds[1])
                if path is None:
                    reason = "missing-log"
                elif bounds is None:
                    reason = "no-response-records"
                elif key in ambiguous:
                    reason = "overlapping-windows"
                elif not covered:
                    reason = "log-does-not-cover-window"
                elif actor["id"] not in declared:
                    reason = "coverage-not-verified"
                else:
                    reason = None
                complete = reason is None
                observed = bool(samples[key]) or (covered and key not in ambiguous)
                by_window[key].append(dict(id=actor["id"], complete=complete,
                                           missing_reason=reason,
                                           observed=totals(samples[key]) if observed else None))

    for row in rows:
        key = row["step"], row.get("attempt")
        if key not in windows:
            row["usage"] = None
            continue
        start, end, _, scope = windows[key]
        measured = by_window[key]
        records = [actor["observed"] for actor in measured if actor["observed"] is not None]
        observed = ({field: sum(record[field] for record in records) for field in records[0]}
                    if records else None)
        complete_count = sum(actor["complete"] for actor in measured)
        row["usage"] = dict(scope=scope, start=start.isoformat(), end=end.isoformat(),
                            actors=measured, complete_actors=complete_count, expected_actors=len(ids),
                            observed=observed, total=observed if manifest["actors_complete"]
                            and complete_count == len(ids) else None)
    return dict(actors_complete=manifest["actors_complete"],
                unassigned=totals(unassigned) if unassigned else None)
