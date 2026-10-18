import io
import json
from pathlib import Path
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

from browser_mcp_bench.__main__ import main


class CLITests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.server = root / "server.json"
        self.server.write_text(json.dumps({"id": "test", "command": "test-mcp", "args": []}))
        self.task = root / "task.json"
        self.task.write_text(json.dumps({"id": "task", "prompt": "test prompt"}))
        self.flags = ["--server", str(self.server), "--task", str(self.task), "--model", "fixed-model"]

    def test_plan_outputs_json_without_processes(self):
        out = io.StringIO()
        with patch("browser_mcp_bench.adapter.resolve", return_value="/codex"), patch(
                "subprocess.Popen", side_effect=AssertionError("No model in plan")), redirect_stdout(out):
            code = main(["plan", *self.flags])
        self.assertEqual(code, 0)
        self.assertFalse(json.loads(out.getvalue())["model_invoked"])

    def test_run_requires_operator_confirmation(self):
        out = io.StringIO()
        with redirect_stdout(out), patch("subprocess.Popen", side_effect=AssertionError("No confirmation")):
            code = main(["run", *self.flags])
        self.assertEqual(code, 2)
        self.assertIn("No API fallback", out.getvalue())

    def test_execution_status_exit_codes_and_arguments(self):
        for status, expected in (("completed_unscored", 0), ("invalid_trace", 3), ("timeout", 3)):
            with self.subTest(status=status), patch("browser_mcp_bench.__main__.run",
                    return_value={"execution_status": status}) as mocked, redirect_stdout(io.StringIO()):
                code = main(["run", *self.flags, "--confirm-isolated-browser", "--timeout", "17"])
                self.assertEqual(code, expected)
                self.assertTrue(mocked.call_args.kwargs["confirm_isolated_browser"])
                self.assertEqual(mocked.call_args.kwargs["timeout"], 17)


if __name__ == "__main__":
    unittest.main()
