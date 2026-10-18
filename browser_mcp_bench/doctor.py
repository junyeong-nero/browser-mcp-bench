"""Read-only Codex prerequisites checks. Never submits an agent/model request."""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path
from collections.abc import Callable, Mapping, Sequence
from typing import Any

from .runtime import API_ENV, find_codex

CommandRunner = Callable[[Sequence[str], Mapping[str, str]], subprocess.CompletedProcess[str]]


def run_command(argv: Sequence[str], env: Mapping[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        argv, env=dict(env), capture_output=True, text=True, timeout=15, check=False
    )


def diagnose(
    executable: str = "codex",
    codex_home: str | None = None,
    *,
    env: Mapping[str, str] | None = None,
    runner: CommandRunner = run_command,
    resolve: Callable[[str], str | None] = find_codex,
) -> dict[str, Any]:
    """Return allowlisted diagnostics, never raw auth output or credentials.

    This is not certification of MCP/tool isolation or benchmark readiness.
    Authentication is deliberately classified conservatively: unknown login
    output is not treated as a valid subscription session.
    """
    child_env = dict(os.environ if env is None else env)
    if codex_home is not None:
        child_env["CODEX_HOME"] = codex_home
    path = resolve(executable)
    if path:
        child_env["PATH"] = str(Path(path).absolute().parent) + os.pathsep + child_env.get("PATH", os.defpath)
    checks: list[dict[str, Any]] = []

    def add(name: str, passed: bool, detail: str) -> None:
        checks.append({"name": name, "passed": passed, "detail": detail})

    add("codex_installed", path is not None,
        "Executable found." if path else "Codex executable not found; install it or pass --codex PATH.")
    # Standalone doctor flags inherited API credentials. The execution adapter
    # instead supplies a restricted environment with those variables removed.
    api_auth_present = any(child_env.get(key) for key in API_ENV)
    add("no_api_key_environment", not api_auth_present,
        "API credential environment detected; unset it for subscription-only runs."
        if api_auth_present else "No known API credential environment detected.")

    if path is not None:
        commands = (
            ("codex_version", [path, "--version"]),
            ("exec_json_support", [path, "exec", "--help"]),
            ("chatgpt_login", [path, "login", "status"]),
        )
        for name, command in commands:
            try:
                result = runner(command, child_env)
            except (OSError, subprocess.TimeoutExpired):
                add(name, False, "Command could not complete; no raw output retained.")
                continue
            output = result.stdout + "\n" + result.stderr
            if result.returncode != 0:
                add(name, False, "Command failed; inspect the CLI locally (raw output omitted).")
            elif name == "codex_version":
                # Do not retain arbitrary subprocess output in the report.
                match = re.search(r"\bcodex(?:-cli)?\s+(\d+\.\d+\.\d+(?:[-+][\w.-]+)?)\b", output)
                add(name, match is not None,
                    "codex-cli " + match.group(1) if match else "Unrecognized version output.")
            elif name == "exec_json_support":
                required = ("--json", "--output-last-message", "--skip-git-repo-check")
                missing = [flag for flag in required if flag not in output]
                add(name, not missing,
                    "Expected exec flags available." if not missing else "Missing flags: " + ", ".join(missing))
            else:
                logged_in = "logged in using chatgpt" in output.lower()
                add(name, logged_in,
                    "ChatGPT subscription login reported."
                    if logged_in else "ChatGPT login not confirmed; run codex login in the intended CODEX_HOME.")

    return {
        "harness": "codex",
        "auth_policy": "chatgpt_subscription_only",
        "model_invoked": False,
        "prerequisites_ok": all(check["passed"] for check in checks),
        "checks": checks,
        "limitations": [
            "No model, MCP server, or browser was started.",
            "Model availability, quota, tool isolation, and environment reset remain unverified.",
            "Usage/cost reporting depends on the installed Codex version.",
        ],
    }
