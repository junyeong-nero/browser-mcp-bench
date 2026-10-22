import io
import json
from pathlib import Path
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

from kitsune_benchmark.__main__ import main
from kitsune_benchmark.smoke import ROOT, WS_SETTING, benchmark_source, copy_extension, experiment, private_ports, run_pair


class SmokeTests(unittest.TestCase):
    def test_benchmark_source_names_the_taskset_tag(self):
        source = benchmark_source()
        self.assertRegex(source["revision"], r"^[0-9a-f]{40}$")
        self.assertTrue(source["taskset"].startswith("taskset-v"))

    def test_exact_requested_model_and_reasoning_pin(self):
        spec = experiment()
        self.assertEqual(spec["model"], "gpt-6-luna")
        self.assertEqual(spec["reasoning_effort"], "medium")

    def test_default_plan_has_no_process_or_browser_side_effects(self):
        with patch("subprocess.Popen", side_effect=AssertionError("no model or browser")):
            result = run_pair()
        self.assertFalse(result["model_invoked"])
        self.assertEqual(result["mode"], "smoke_plan_only")

    def test_cli_smoke_default_is_safe(self):
        output = io.StringIO()
        with patch("subprocess.Popen", side_effect=AssertionError("no model")), redirect_stdout(output):
            self.assertEqual(main(["smoke"]), 0)
        self.assertFalse(json.loads(output.getvalue())["model_invoked"])

    def test_cli_smoke_custom_task_is_validated_and_plan_only(self):
        task = ROOT / "tasks/live/steam-goty-2025-negative-100h.json"
        with patch("subprocess.Popen", side_effect=AssertionError("no browser or inference")), \
                redirect_stdout(io.StringIO()) as out:
            code = main(["smoke", "--harness", "claude-api", "--task", str(task), "--ui-tools", "--targets", "kitsune"])
        self.assertEqual(code, 0)
        self.assertFalse(json.loads(out.getvalue())["model_invoked"])
        with tempfile.TemporaryDirectory() as folder, redirect_stdout(io.StringIO()):
            bad = Path(folder) / "task.json"
            bad.write_text(json.dumps({"id": "x", "prompt": ""}))
            self.assertEqual(main(["smoke", "--task", str(bad)]), 2)

    def test_extension_patch_only_changes_copy_endpoint(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / "source"
            (source / "background").mkdir(parents=True)
            original = "// header\n" + WS_SETTING + "\n// trailer\n"
            (source / "background/background.js").write_text(original)
            (source / "manifest.json").write_text('{"name":"test"}')
            destination = root / "private"
            result = copy_extension(source, destination, 51234)
            self.assertEqual((source / "background/background.js").read_text(), original)
            self.assertEqual((destination / "background/background.js").read_text(),
                             original.replace("47652", "51234"))
            self.assertEqual((destination / "manifest.json").read_bytes(), (source / "manifest.json").read_bytes())
            self.assertNotEqual(result["original_background_sha256"], result["patched_background_sha256"])
            with self.assertRaises(ValueError):
                copy_extension(source, root / "bad", 47652)
            with self.assertRaises(ValueError):
                copy_extension(source, root / "bad", 80)
            (source / "background/background.js").write_text("unexpected format")
            with self.assertRaises(ValueError):
                copy_extension(source, root / "bad", 51234)

    def test_private_ports_are_distinct_and_not_user_defaults(self):
        ports = private_ports()
        self.assertNotEqual(*ports)
        self.assertFalse(set(ports) & {47651, 47652})


if __name__ == "__main__":
    unittest.main()
