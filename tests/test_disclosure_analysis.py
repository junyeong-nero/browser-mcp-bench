import json
from pathlib import Path
import tempfile
import unittest

from kitsune_benchmark.disclosure_analysis import trace, paired


class DisclosureAnalysisTests(unittest.TestCase):
    def test_deduplicates_request_and_tool_ids_and_classifies_sequences(self):
        call = {"type": "tool_use", "id": "t1", "name": "mcp__browser__browser_snapshot", "input": {}}
        first = {"type": "assistant", "message": {"id": "m1", "content": [call]}}
        events = [first, first,
                  {"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": "t1", "is_error": True,
                      "content": json.dumps({"error": "expect needs exactly one of ..."})}]}},
                  {"type": "assistant", "message": {"id": "m2", "content": [
                      {"type": "tool_use", "id": "t2", "name": "mcp__browser__browser_page_text", "input": {}},
                      {"type": "tool_use", "id": "t3", "name": "mcp__browser__browser_tabs", "input": {"action": "list"}}]}},
                  {"type": "assistant", "message": {"id": "m3", "content": [{"type": "text", "text": "done"}]}}]
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "events.jsonl"
            path.write_text("\n".join(json.dumps(x) for x in events))
            result = trace(path)
        self.assertEqual(result["trace_requests"], 3)
        self.assertEqual(result["multi_tool_requests"], 1)
        self.assertEqual(result["read_calls"], 3)
        self.assertEqual(result["consecutive_reads"], 1)
        self.assertEqual(result["request_after_error"], 1)
        self.assertEqual(result["errors_expect_validation"], 1)

    def test_pairs_by_task_repeat_not_order_and_keeps_failed_runs(self):
        rows = []
        for task in ("one", "two"):
            for arm, value in (("B", 8), ("A", 10)):
                rows.append({"task": task, "block": task + "/r0", "arm": arm,
                             "success": not (task == "two" and arm == "B"),
                             "requests": value, "input": value, "elapsed": value, "cost": value})
        result = paired(rows, "A", "B")
        self.assertEqual(result["all"]["blocks"], 2)
        self.assertEqual(result["joint_success"]["blocks"], 1)
        self.assertAlmostEqual(result["all"]["metrics"]["input"]["pct"], -20)
        self.assertEqual(result["per_task"]["one"]["requests"], -2)
        self.assertAlmostEqual(result["task_cluster_bootstrap_pct_95"]["requests"][0], -20)


if __name__ == "__main__":
    unittest.main()
