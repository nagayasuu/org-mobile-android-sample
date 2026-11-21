#!/usr/bin/env python3
"""Summarize local Codex rollout traces without exporting their contents."""

import argparse
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import secrets
import shlex
import sys

from summarize_usage import METRICS, number


ITEM_TYPES = {
    "message", "reasoning", "function_call", "function_call_output",
    "custom_tool_call", "custom_tool_call_output", "local_shell_call",
    "web_search_call", "image_generation_call", "compaction", "compaction_summary",
}
ROLES = {"developer", "system", "user", "assistant", "tool"}
VERBOSITY = {"low", "medium", "high"}
EFFORT = {"none", "minimal", "low", "medium", "high", "xhigh", "max", "ultra"}
STATUSES = {"running", "completed", "failed", "interrupted", "cancelled", "aborted", "pending"}
TRUNCATION = re.compile(r"output truncated|truncated output|\d+ tokens truncated|\d+ chars omitted", re.I)
RANGE = re.compile(r"(\d+)(?:,(\d+))?p")


def allowed(value, choices):
    return value if isinstance(value, str) and value in choices else None


def fingerprint(value, key):
    data = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return {"json_bytes": len(data), "hmac_sha256": hmac.digest(key, data, "sha256").hex()}


def item_metadata(item_type, role, value, key):
    return {"type": allowed(item_type, ITEM_TYPES) or "other",
            "role": allowed(role, ROLES), **fingerprint(value, key)}


def sequence(entry):
    return number(entry["execution"]["started_seq"], integer=True)


def bundle_json(bundle, filename):
    path = (bundle / filename).resolve(strict=True)
    if not path.is_relative_to(bundle) or not path.is_file():
        raise ValueError("Expected a file inside the bundle")
    return json.loads(path.read_bytes())


def wire_request(bundle, payloads, identifier):
    try:
        value = bundle_json(bundle, payloads[identifier]["path"])
    except (KeyError, OSError, RuntimeError, ValueError):
        return None
    return value if isinstance(value, dict) else None


def request_metadata(payload, outputs_by_call, key):
    if payload is None:
        return None
    items = payload.get("input")
    text = payload.get("text")
    reasoning = payload.get("reasoning")
    tools = payload.get("tools")
    input_items = None
    if isinstance(items, list):
        input_items = []
        for item in items:
            fields = item if isinstance(item, dict) else {}
            row = item_metadata(fields.get("type"), fields.get("role"), item, key)
            if row["type"] in {"function_call_output", "custom_tool_call_output"}:
                row["tool_outputs"] = outputs_by_call.get(fields.get("call_id"), [])
            input_items.append(row)
    return {
        "body": fingerprint(payload, key),
        "verbosity": allowed(text.get("verbosity"), VERBOSITY) if isinstance(text, dict) else None,
        "reasoning_effort": allowed(reasoning.get("effort"), EFFORT)
        if isinstance(reasoning, dict) else None,
        "instructions": fingerprint(payload["instructions"], key) if "instructions" in payload else None,
        "tools": [fingerprint(item, key) for item in tools] if isinstance(tools, list) else None,
        "input_items": input_items,
    }


def usage_metadata(usage):
    if usage is None:
        return None
    result = {field: number(usage[field], integer=True) if usage.get(field) is not None else None
              for field in METRICS}
    total, cached = result["input_tokens"], result["cached_input_tokens"]
    uncached = total - cached if total is not None and cached is not None else None
    if uncached is not None and uncached < 0:
        raise ValueError("Invalid usage")
    return {**result, "uncached_input_tokens": uncached}


def line_ranges(spec):
    ranges = []
    for part in spec.split(";"):
        match = RANGE.fullmatch(part)
        if not match:
            return None
        first, last = int(match[1]), int(match[2] or match[1])
        if not 1 <= first <= last:
            return None
        ranges.append([first, last])
    return ranges


def shell_segments(argv):
    if len(argv) < 3 or Path(argv[0]).name not in {"bash", "sh", "zsh"} or argv[1] not in {"-c", "-lc"}:
        return [(None, argv)]
    try:
        lexer = shlex.shlex(argv[2], posix=True, punctuation_chars=";&|\n")
        lexer.whitespace = " \t\r"
        lexer.whitespace_split = True
        commands = [(None, [])]
        for word in lexer:
            if word and not set(word) - set(";&|\n"):
                commands.append((word, []))
            else:
                commands[-1][1].append(word)
        return commands
    except ValueError:
        return []


def read_metadata(argv, key):
    commands = shell_segments(argv)
    reads = []
    for idx, (separator, args) in enumerate(commands):
        if not args:
            continue
        name, *params = args
        ranges = None
        if name == "sed" and len(params) in {2, 3} and params[0] == "-n":
            ranges = line_ranges(params[1])
            if ranges is None:
                continue
            if len(params) == 3:
                targets = [params[2]]
            elif idx and separator == "|":
                previous = commands[idx - 1][1]
                if len(previous) != 3 or previous[:2] != ["nl", "-ba"]:
                    continue
                targets = previous[2:]
            else:
                continue
        elif name == "cat" and params and not any(arg.startswith("-") for arg in params):
            targets = params
        elif name == "rg":
            # Recognize the common positional form. Options with values require
            # explicit handling so a search pattern cannot be mistaken for a path.
            params = list(params)
            while params[:1] and params[0] in {"-n", "-S", "-i", "-F", "-l", "-H", "--no-heading"}:
                params.pop(0)
            if params[:1] == ["--"]:
                params.pop(0)
            if not params or any(arg.startswith("-") for arg in params[1:]):
                continue
            if params[0].startswith("-"):
                if params[0] != "--files":
                    continue
                targets = params[1:] or ["."]
            else:
                targets = params[1:] or ["."]
        else:
            continue
        if any(re.search(r"[$*?~\[\]<>]", target) for target in targets):
            continue
        reads.append({"operation": name, "targets": [fingerprint(os.path.normpath(t), key) for t in targets],
                      "requested_lines": ranges})
    return reads


def terminal_metadata(operation, key):
    if operation is None:
        return None
    request = operation["request"]
    argv = request.get("command")
    result = operation.get("result")
    output = result.get("formatted_output") if result else None
    exit_code = result.get("exit_code") if result else None
    return {
        "kind": allowed(operation.get("kind"), {"exec_command", "write_stdin"}),
        "command": fingerprint(argv, key) if isinstance(argv, list) else None,
        "reads": read_metadata(argv, key) if argv else [],
        "exit_code": exit_code if type(exit_code) is int else None,
        "stdout": fingerprint(result["stdout"], key) if result else None,
        "stderr": fingerprint(result["stderr"], key) if result else None,
        "formatted_output": fingerprint(output, key) if isinstance(output, str) else None,
        "truncation_marker": bool(TRUNCATION.search(output)) if isinstance(output, str) else None,
    }


def summarize(bundle, key):
    state = bundle_json(bundle, "state.json")
    if state.get("schema_version") != 2:
        raise ValueError("Unsupported reduced trace schema")

    items = state["conversation_items"]
    tools = state["tool_calls"]
    terminals = state["terminal_operations"]
    calls = sorted(state["inference_calls"].values(), key=sequence)
    tool_order = sorted(tools, key=lambda identity: sequence(tools[identity]))
    tool_numbers = {identity: idx for idx, identity in enumerate(tool_order, 1)}
    thread_numbers = {identity: idx for idx, identity in enumerate(dict.fromkeys(
        call["thread_id"] for call in calls), 1)}
    turn_numbers = {identity: idx for idx, identity in enumerate(dict.fromkeys(
        (call["thread_id"], call["codex_turn_id"]) for call in calls), 1)}
    response_numbers = {(call["thread_id"], call.get("response_id")): idx
                        for idx, call in enumerate(calls, 1) if call.get("response_id")}
    output_tools = {}
    tool_rows = []
    for identity in tool_order:
        tool = tools[identity]
        terminal = terminals.get(tool.get("terminal_operation_id"))
        output_ids = set(tool["model_visible_output_item_ids"])
        if terminal:
            for observation in terminal["model_observations"]:
                output_ids.update(observation["output_item_ids"])
        for item_id in output_ids:
            output_tools.setdefault(item_id, []).append(tool_numbers[identity])
        tool_rows.append({"tool": tool_numbers[identity], "start_seq": sequence(tool),
                          "terminal": terminal_metadata(terminal, key)})

    requests = []
    for idx, call in enumerate(calls, 1):
        thread = call["thread_id"]
        end_seq = call["execution"]["ended_seq"]
        payload = wire_request(bundle, state["raw_payloads"], call.get("raw_request_payload_id"))
        previous = payload.get("previous_response_id") if payload else None
        linked = []
        outputs_by_call = {}
        for item_id in call["request_item_ids"]:
            item = items[item_id]
            outputs = output_tools.get(item_id, [])
            linked.append(dict(item_metadata(item["kind"], item.get("role"), item["body"], key),
                               tool_outputs=outputs))
            if outputs and item.get("call_id"):
                outputs_by_call[item["call_id"]] = outputs
        requests.append({
            "request": idx, "thread": thread_numbers[thread],
            "turn": turn_numbers[(thread, call["codex_turn_id"])], "start_seq": sequence(call),
            "end_seq": number(end_seq, integer=True) if end_seq is not None else None,
            "status": allowed(call["execution"]["status"], STATUSES),
            "usage": usage_metadata(call.get("usage")),
            "previous_response_referenced": bool(previous) if payload is not None else None,
            "previous_request": response_numbers.get((thread, previous)) if previous else None,
            "wire": request_metadata(payload, outputs_by_call, key),
            "logical_input_items": linked,
            "tools_started": [tool_numbers[identity] for identity in call["tool_call_ids_started_by_response"]],
        })

    return {"trace_status": allowed(state.get("status"), STATUSES),
            "requests": requests, "tools": tool_rows,
            "compaction_request_count": len(state["compaction_requests"])}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundles", type=Path, nargs="+", help="Local trace bundles containing state.json")
    args = parser.parse_args()
    key = secrets.token_bytes(hashlib.sha256().digest_size)
    try:
        result = {"schema_version": 1, "traces": [summarize(path.resolve(), key) for path in args.bundles]}
    except (OSError, RuntimeError, ValueError, KeyError, TypeError, AttributeError):
        print("Unable to read a supported Codex trace bundle (reduced schema 2).", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
