"""Check request ordering, tool attribution, and safe output from offline traces."""

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "trace_trial_requests.py"


def execution(start):
    return {"started_seq": start, "ended_seq": start + 1, "status": "completed"}


class TrialRequestTraceTest(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.bundle = self.root / "bundle"
        self.bundle.mkdir()
        tool_output = {"type": "function_call_output", "call_id": "PRIVATE-CALL", "output": "PRIVATE-RESULT"}
        self.state = {
            "schema_version": 2, "status": "completed",
            "conversation_items": {
                "message": {"kind": "message", "role": "user", "body": "PRIVATE-MESSAGE"},
                "output": {"kind": "function_call_output", "role": "tool", "call_id": "PRIVATE-CALL",
                           "body": "PRIVATE-RESULT"},
            },
            "inference_calls": {
                "second": self.request(9, "second", ["message", "output"], []),
                "first": self.request(3, "first", ["message"], ["PRIVATE-TOOL"]),
            },
            "tool_calls": {
                "PRIVATE-TOOL": {"execution": execution(5), "terminal_operation_id": "terminal",
                                 "model_visible_output_item_ids": ["output"]},
            },
            "terminal_operations": {
                "terminal": {"kind": "exec_command", "model_observations": [],
                             "request": {"command": ["bash", "-lc",
                                         "sed -n '3,8p;7,9p' ./PRIVATE-PATH\nrg -n needle PRIVATE-PATH"]},
                             "result": {"stdout": "PRIVATE-RESULT", "stderr": "", "exit_code": 0,
                                        "formatted_output": "Warning: truncated output"}},
            },
            "compaction_requests": {},
            "raw_payloads": {"first": {"path": "first.json"}, "second": {"path": "second.json"}},
        }
        message = {"type": "message", "role": "user", "content": ["PRIVATE-MESSAGE"]}
        self.write("first.json", {"input": [message], "text": {"verbosity": "low"}})
        self.write("second.json", {"input": [tool_output], "previous_response_id": "PRIVATE-RESPONSE-first"})

    def request(self, start, name, items, tools):
        return {"execution": execution(start), "thread_id": "PRIVATE-THREAD", "codex_turn_id": "PRIVATE-TURN",
                "response_id": f"PRIVATE-RESPONSE-{name}", "raw_request_payload_id": name,
                "request_item_ids": items, "tool_call_ids_started_by_response": tools,
                "usage": {"input_tokens": start * 10, "cached_input_tokens": start, "output_tokens": 3}}

    def write(self, name, data):
        (self.bundle / name).write_text(json.dumps(data), encoding="utf-8")

    def run_trace(self, *bundles):
        self.write("state.json", self.state)
        return subprocess.run([sys.executable, SCRIPT, *(bundles or (self.bundle,))],
                              text=True, capture_output=True, check=False)

    def read_trace(self):
        result = self.run_trace()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("PRIVATE", result.stdout)
        return json.loads(result.stdout)["traces"][0]

    def test_followup_links_usage_to_tool_result_and_keeps_incremental_wire_input(self):
        first, second = self.read_trace()["requests"]
        self.assertEqual([first["start_seq"], second["start_seq"]], [3, 9])
        self.assertEqual(first["tools_started"], [1])
        self.assertEqual(second["usage"]["uncached_input_tokens"], 81)
        self.assertEqual(first["wire"]["verbosity"], "low")
        self.assertIsNone(second["wire"]["verbosity"])
        self.assertEqual(second["previous_request"], 1)
        self.assertEqual(len(second["wire"]["input_items"]), 1)
        self.assertEqual(second["wire"]["input_items"][0]["tool_outputs"], [1])
        self.assertEqual(second["logical_input_items"][1]["tool_outputs"], [1])
        self.assertEqual(first["logical_input_items"][0]["hmac_sha256"],
                         second["logical_input_items"][0]["hmac_sha256"])

    def test_read_ranges_and_search_paths_are_summarized_without_a_filename(self):
        terminal = self.read_trace()["tools"][0]["terminal"]
        self.assertTrue(terminal["truncation_marker"])
        read, search = terminal["reads"]
        self.assertEqual(read["requested_lines"], [[3, 8], [7, 9]])
        self.assertIsNone(search["requested_lines"])
        self.assertEqual(read["targets"], search["targets"])

    def test_missing_usage_and_unsafe_payload_reference_remain_unknown(self):
        outside = self.root / "outside.json"
        outside.write_text('{"text":{"verbosity":"high"}}', encoding="utf-8")
        del self.state["inference_calls"]["second"]["usage"]["cached_input_tokens"]
        self.state["raw_payloads"]["second"]["path"] = "../outside.json"
        second = self.read_trace()["requests"][1]
        self.assertIsNone(second["wire"])
        self.assertEqual(second["usage"]["input_tokens"], 90)
        self.assertIsNone(second["usage"]["cached_input_tokens"])
        self.assertIsNone(second["usage"]["uncached_input_tokens"])
        self.assertIsNone(second["previous_response_referenced"])

    def test_rejects_a_state_symlink_that_points_outside_the_bundle(self):
        self.write("state.json", self.state)
        other = self.root / "other"
        other.mkdir()
        (other / "state.json").symlink_to(self.bundle / "state.json")
        result = self.run_trace(other)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout, "")
        self.assertNotIn(str(other), result.stderr)

    def test_an_output_symlink_loop_leaves_the_wire_request_unknown(self):
        (self.bundle / "loop").symlink_to("loop")
        self.state["raw_payloads"]["second"]["path"] = "loop"
        self.assertIsNone(self.read_trace()["requests"][1]["wire"])

    def test_rejects_unsupported_reduced_schema(self):
        self.state["schema_version"] = 999
        result = self.run_trace()
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout, "")
        self.assertNotIn(str(self.bundle), result.stderr)


if __name__ == "__main__":
    unittest.main()
