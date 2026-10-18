from contextlib import nullcontext
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import psutil

from browser_mcp_bench.resources import ResourceCollector, ResourceRoot, ProcessProbe, component_for


def process(pid=100, created=1.0, rss=100, user=5.0, owner="kitsune", component="browser", external=False):
    return {"pid": pid, "create_time": created, "ppid": 1, "name": "test", "status": "sleeping",
            "rss_bytes": rss, "cpu_user_sec": user, "cpu_system_sec": 0.0,
            "owner": owner, "component": component, "externally_managed": external}


class FakeProbe:
    errors = 0

    def __init__(self):
        self.rows = []
        self.roots = []

    def register(self, root):
        self.roots.append(root)

    def capture(self):
        return [dict(p) for p in self.rows], {"available_memory_bytes": 123}


class ResourceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def manual(self):
        probe = FakeProbe()
        collector = ResourceCollector(self.root, probe=probe, interval_sec=60)
        collector._file = io.StringIO()
        collector._started = 0
        collector._wall_started = 100
        return collector, probe

    def test_weighted_mean_cpu_deltas_and_phase_boundaries(self):
        collector, probe = self.manual()
        probe.rows = [process()]
        with patch("browser_mcp_bench.resources.time.monotonic", return_value=0):
            collector.sample()
        probe.rows = [process(rss=200, user=7)]
        with patch("browser_mcp_bench.resources.time.monotonic", return_value=2):
            collector.sample()
        with patch("browser_mcp_bench.resources.time.monotonic", return_value=4):
            collector.set_phase("task")
        probe.rows = [process(rss=300, user=9)]
        with patch("browser_mcp_bench.resources.time.monotonic", return_value=6):
            collector.__exit__(None, None, None)
        all_metrics = collector.summary["metrics"]["all"]
        self.assertEqual(all_metrics["sampled_peak_rss_bytes"], 300)
        self.assertAlmostEqual(all_metrics["time_weighted_mean_rss_bytes"], (100 * 2 + 200 * 4) / 6)
        self.assertAlmostEqual(all_metrics["observed_cpu_user_sec"], 4)
        self.assertIn("phase/task/all", collector.summary["metrics"])
        self.assertEqual(collector.summary["unexpected_alive_at_stop"], [100])

    def test_pid_reuse_has_a_separate_cpu_baseline(self):
        collector, probe = self.manual()
        probe.rows = [process(user=10)]
        with patch("browser_mcp_bench.resources.time.monotonic", return_value=0):
            collector.sample()
        probe.rows = [process(created=2, user=50)]
        with patch("browser_mcp_bench.resources.time.monotonic", return_value=1):
            collector.sample()
        self.assertEqual(collector._previous["processes"][0]["cpu_user_delta_sec"], 0)
        self.assertEqual(len(collector._identities), 2)
        collector._file.close()

    def test_new_children_cpu_and_owner_separation(self):
        collector, probe = self.manual()
        probe.rows = [process(created=101, user=0.5, owner="playwright"),
                      process(pid=200, user=5, external=True)]
        with patch("browser_mcp_bench.resources.time.monotonic", return_value=2):
            collector.sample()
        row = collector._previous
        self.assertEqual(row["groups"]["owner/playwright"]["user"], 0.5)
        self.assertEqual(row["groups"]["owner/kitsune"]["user"], 0)
        self.assertEqual(row["groups"]["all"]["count"], 2)
        collector._file.close()

    def test_permission_failure_is_reported(self):
        collector, probe = self.manual()
        with patch.object(probe, "capture", side_effect=PermissionError()):
            collector.sample()
        self.assertEqual(collector._errors, 1)
        self.assertEqual(collector._samples, 0)
        collector._file.close()

    def test_roles_do_not_treat_codex_launcher_as_mcp_root(self):
        self.assertEqual(component_for("node", "harness"), "mcp")
        self.assertEqual(component_for("codex", "harness"), "harness")
        self.assertEqual(component_for("python", "bridge"), "bridge")
        self.assertEqual(component_for("firefox", "browser_launcher"), "browser")
        self.assertEqual(component_for("plugin-container", "mcp"), "browser")

    def test_recycled_root_is_not_followed(self):
        probe = ProcessProbe()
        p = SimpleNamespace(pid=123, create_time=lambda: 1.0)
        with patch("browser_mcp_bench.resources.psutil.Process", return_value=p):
            probe.register(ResourceRoot(123, "harness", "test"))
        p.create_time = lambda: 2.0
        p.oneshot = nullcontext
        p.children = lambda: self.fail("Never follow children of a recycled root")
        with patch("browser_mcp_bench.resources.psutil.Process", return_value=p):
            rows, _ = probe.capture()
        self.assertEqual(rows, [])

    def test_real_child_sampling_private_outputs_and_external_lifetime(self):
        child = subprocess.Popen([sys.executable, "-c", "import time; x=bytearray(8000000); time.sleep(10)"])
        try:
            with ResourceCollector(self.root, interval_sec=0.05,
                    roots=(ResourceRoot(child.pid, "browser", "test", True),)) as collector:
                collector.set_phase("task")
                time.sleep(0.25)
            data = collector.summary
            self.assertGreaterEqual(data["samples"], 3)
            self.assertGreater(data["metrics"]["all"]["sampled_peak_rss_bytes"], 1000000)
            self.assertEqual(data["unexpected_alive_at_stop"], [])
            self.assertTrue(data["alive_at_stop"])
            for name in ("resources.jsonl", "resource-summary.json"):
                path = self.root / name
                self.assertEqual(path.stat().st_mode & 0o777, 0o600)
                self.assertNotIn("command_line", path.read_text())
            for line in (self.root / "resources.jsonl").read_text().splitlines():
                self.assertNotIn(os.getpid(), [p["pid"] for p in json.loads(line)["processes"]])
        finally:
            child.terminate()
            child.wait(timeout=5)

    def test_interval_validation(self):
        for interval in (0, -1, 100):
            with self.assertRaises(ValueError):
                ResourceCollector(self.root, interval_sec=interval)


if __name__ == "__main__":
    unittest.main()
