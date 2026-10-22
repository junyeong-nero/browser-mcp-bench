import io
import json
from pathlib import Path
import re
import tempfile
import unittest
from contextlib import redirect_stdout
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlsplit
from urllib.request import Request, build_opener, ProxyHandler
from unittest.mock import patch

from kitsune_benchmark.__main__ import main
from kitsune_benchmark.adapter import settings
from kitsune_benchmark.audit import audit_events
from kitsune_benchmark.miniwob import BenchmarkServer, Trial, UI_TOOLS, bootstrap, config, run_benchmark
from kitsune_benchmark.specs import Server


def event(kind="end", raw=1, reward=0.9):
    return {"kind": kind, "task_id": "click-test-2", "seed": 42,
            "timer_budget_ms": 120000, "done": True, "raw_reward": raw, "reward": reward}


class MiniwobTests(unittest.TestCase):
    def test_official_reward_not_agent_answer_is_the_success_label(self):
        for raw, success in ((1, True), (-1, False), (0, False)):
            with self.subTest(raw=raw):
                trial = Trial("click-test-2", 42, 120000, page_loads=1)
                self.assertTrue(trial.event(event("start")))
                self.assertTrue(trial.event(event(raw=raw)))
                result = trial.evaluate("completed_unscored")
                self.assertTrue(result["scorable"])
                self.assertEqual(result["task_success"], success)
                self.assertIsNone(trial.evaluate("invalid_trace")["task_success"])

    def test_restart_reload_bad_reward_and_modified_timer_are_not_scorable(self):
        for mutation in ({"seed": 43}, {"timer_budget_ms": 500000},
                         {"raw_reward": float("nan")}, {"raw_reward": True},
                         {"reward": 2}, {"done": False}):
            trial = Trial("click-test-2", 42, 120000, page_loads=1)
            trial.event(event("start"))
            self.assertFalse(trial.event({**event(), **mutation}))
            self.assertFalse(trial.evaluate("completed_unscored")["scorable"])
        trial = Trial("click-test-2", 42, 120000, page_loads=1)
        trial.event(event("start")); trial.event(event("start")); trial.event(event())
        self.assertFalse(trial.evaluate("completed_unscored")["scorable"])
        trial = Trial("click-test-2", 42, 120000, page_loads=2, starts=1)
        self.assertFalse(trial.evaluate("completed_unscored")["scorable"])

    def test_ui_track_hides_code_and_reward_manipulation_surfaces(self):
        for tools in UI_TOOLS.values():
            self.assertFalse(set(tools) & {"browser_js", "browser_evaluate", "browser_run_code",
                                          "browser_parallel", "browser_batch", "browser_workflow"})
        server = Server("x", "mcp", (), enabled_tools=("browser_click",))
        self.assertEqual(settings(server)["mcp_servers"]["browser"]["enabled_tools"], ("browser_click",))

    def test_http_instrumentation_and_reward_route(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder)
            directory = source / "miniwob/html/miniwob"
            directory.mkdir(parents=True)
            original = "<html><body>Original upstream task</body></html>"
            path = directory / "click-test-2.html"
            path.write_text(original)
            spec = config()
            with BenchmarkServer(source, spec) as server:
                task = server.begin("playwright")
                url = re.search(r"http://\S+", task.prompt).group()
                opener = build_opener(ProxyHandler({}))
                with opener.open(url, timeout=2) as response:
                    page = response.read().decode()
                self.assertIn("Original upstream task", page)
                self.assertIn("core.endEpisode", page)
                self.assertIn("Math.seedrandom", page)
                self.assertEqual(path.read_text(), original)
                parsed = urlsplit(url); token = parse_qs(parsed.query)["trial"][0]
                endpoint = f"http://{parsed.netloc}/__bench/{token}/event"
                for payload in (event("start"), event()):
                    with opener.open(Request(endpoint, data=json.dumps(payload).encode(),
                                             headers={"Content-Type": "application/json"}), timeout=2) as response:
                        self.assertEqual(response.status, 204)
                outcome = server.evaluate("playwright", {"execution_status": "completed_unscored"})
                self.assertTrue(outcome["task_success"])
                with self.assertRaises(HTTPError):
                    opener.open(Request(endpoint, data=b'null'), timeout=2)

    def test_benchmark_default_does_not_start_processes(self):
        with patch("subprocess.Popen", side_effect=AssertionError("no processes in plan")):
            result = run_benchmark()
        self.assertFalse(result["model_invoked"])
        self.assertEqual(result["config"]["model"], "gpt-6-luna")
        with patch("subprocess.Popen", side_effect=AssertionError("no model")), redirect_stdout(io.StringIO()):
            self.assertEqual(main(["benchmark"]), 0)

    def test_audit_catches_code_tool_or_javascript_navigation(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "events.jsonl"
            for tool, args in (("browser_js", {}), ("browser_navigate", {"url": "javascript:core.endEpisode(1)"})):
                path.write_text(json.dumps({"type": "item.completed", "item": {
                    "id": "call", "type": "mcp_tool_call", "server": "browser", "tool": tool,
                    "status": "completed", "arguments": args}}))
                result = audit_events(path, allowed_tools=("browser_navigate", "browser_click"))
                self.assertTrue(result["violations"])


if __name__ == "__main__":
    unittest.main()
