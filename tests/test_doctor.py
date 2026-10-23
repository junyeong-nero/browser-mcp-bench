import io
import json
import subprocess
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

from kitsune_benchmark.__main__ import main
from kitsune_benchmark.doctor import diagnose


class DoctorTests(unittest.TestCase):
    def setUp(self):
        self.calls = []

    def runner(self, argv, env):
        self.calls.append((list(argv), dict(env)))
        if argv[1:] == ["--version"]:
            return subprocess.CompletedProcess(argv, 0, "codex-cli 0.100.0\n", "")
        if argv[1:] == ["exec", "--help"]:
            return subprocess.CompletedProcess(argv, 0,
                "--json --output-last-message --skip-git-repo-check", "")
        if argv[1:] == ["login", "status"]:
            return subprocess.CompletedProcess(argv, 0, "", "Logged in using ChatGPT\n")
        self.fail(f"Unexpected command: {argv}")

    def diagnose(self, **kwargs):
        return diagnose(env={}, resolve=lambda _: "/test/codex", runner=self.runner, **kwargs)

    def test_chatgpt_prerequisites(self):
        report = self.diagnose()
        self.assertTrue(report["prerequisites_ok"])
        self.assertFalse(report["model_invoked"])
        self.assertEqual(len(self.calls), 3)
        self.assertNotIn(["/test/codex", "exec"], [argv for argv, _ in self.calls])

    def test_missing_executable_never_runs_subprocess(self):
        report = diagnose(env={}, resolve=lambda _: None, runner=self.runner)
        self.assertFalse(report["prerequisites_ok"])
        self.assertEqual(self.calls, [])

    def test_api_key_environment_fails_without_disclosing_secret(self):
        for key in ("OPENAI_API_KEY", "CODEX_API_KEY", "OPENAI_AUTH_TOKEN"):
            with self.subTest(key=key):
                report = diagnose(env={key: "private-secret"},
                    resolve=lambda _: "/test/codex", runner=self.runner)
                self.assertFalse(report["prerequisites_ok"])
                self.assertNotIn("private-secret", json.dumps(report))

    def test_api_login_is_not_subscription_login(self):
        def api_runner(argv, env):
            if argv[1:] == ["login", "status"]:
                return subprocess.CompletedProcess(argv, 0, "Logged in using an API key: SECRET", "")
            return self.runner(argv, env)
        report = diagnose(env={}, resolve=lambda _: "/test/codex", runner=api_runner)
        self.assertFalse(report["prerequisites_ok"])
        self.assertNotIn("SECRET", json.dumps(report))

    def test_unknown_login_fails_closed(self):
        def unknown_runner(argv, env):
            if argv[1:] == ["login", "status"]:
                return subprocess.CompletedProcess(argv, 0, "Some new login mechanism", "")
            return self.runner(argv, env)
        report = diagnose(env={}, resolve=lambda _: "/test/codex", runner=unknown_runner)
        self.assertFalse(report["prerequisites_ok"])

    def test_home_override_does_not_mutate_environment(self):
        env = {"CODEX_HOME": "/old"}
        diagnose(codex_home="/isolated", env=env,
            resolve=lambda _: "/test/codex", runner=self.runner)
        self.assertEqual(env["CODEX_HOME"], "/old")
        self.assertTrue(all(e["CODEX_HOME"] == "/isolated" for _, e in self.calls))

    def test_missing_exec_flags(self):
        def old_runner(argv, env):
            if argv[1:] == ["exec", "--help"]:
                return subprocess.CompletedProcess(argv, 0, "old CLI", "")
            return self.runner(argv, env)
        report = diagnose(env={}, resolve=lambda _: "/test/codex", runner=old_runner)
        self.assertFalse(report["prerequisites_ok"])

    def test_timeout_and_os_error_are_sanitized(self):
        for error in (subprocess.TimeoutExpired("SECRET", 15), OSError("SECRET")):
            with self.subTest(error=type(error).__name__):
                def failing_runner(argv, env):
                    raise error
                report = diagnose(env={}, resolve=lambda _: "/test/codex", runner=failing_runner)
                self.assertFalse(report["prerequisites_ok"])
                self.assertNotIn("SECRET", json.dumps(report))

    def test_nonzero_exit_and_arbitrary_version_output_are_not_leaked(self):
        for code in (0, 1):
            with self.subTest(code=code):
                report = diagnose(env={}, resolve=lambda _: "/test/codex",
                    runner=lambda argv, env: subprocess.CompletedProcess(argv, code, "SECRET", ""))
                self.assertFalse(report["prerequisites_ok"])
                self.assertNotIn("SECRET", json.dumps(report))

    def test_cli_json_and_exit_codes(self):
        for ready, expected in ((True, 0), (False, 2)):
            report = {"prerequisites_ok": ready, "checks": []}
            with patch("kitsune_benchmark.__main__.diagnose", return_value=report) as mocked:
                out = io.StringIO()
                with redirect_stdout(out):
                    code = main(["doctor", "--harness", "codex", "--codex", "/custom/codex", "--codex-home", "/home", "--json"])
                self.assertEqual(code, expected)
                self.assertEqual(json.loads(out.getvalue()), report)
                mocked.assert_called_once_with("/custom/codex", "/home")


if __name__ == "__main__":
    unittest.main()
