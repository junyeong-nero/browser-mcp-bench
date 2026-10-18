"""Codex CLI orchestration. No direct model API client or credential copying."""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import tempfile
import time
import uuid

from .audit import audit_events
from .doctor import diagnose
from .runtime import codex_environment, find_codex
from .resources import ResourceCollector, ResourceRoot
from .specs import Server, Task, positive_int, text, toml_value

PINNED_CODEX_VERSION = "0.163.0"
DISABLED_FEATURES = (
    "shell_tool", "apps", "browser_use", "browser_use_external", "in_app_browser",
    "image_generation", "view_image", "multi_agent", "multi_agent_v2", "memories",
    "external_agent_memory_import", "hooks", "plugins", "remote_plugin",
    "skill_search", "skill_mcp_dependency_install", "shell_snapshot", "tool_suggest",
)
COMMON_INSTRUCTIONS = (
    "Perform the user task using only the tools from the browser MCP server. "
    "Do not use shell, filesystem, built-in search, other agents, or alternative network access. "
    "Do not modify browser settings, unrelated tabs, or accounts. "
    "If blocked, report the blocker honestly. State the final result concisely. "
    "Do not claim that an external evaluator has marked the task successful."
)
REQUIRED_EXEC_FLAGS = (
    "--ignore-user-config", "--ignore-rules", "--ephemeral", "--json",
    "--output-last-message", "--skip-git-repo-check",
)


def settings(server: Server) -> dict:
    values = {
        "model_provider": "openai",
        "model_reasoning_effort": "medium",
        "forced_login_method": "chatgpt",
        "approval_policy": "never",
        "web_search": "disabled",
        "project_doc_max_bytes": 0,
        "suppress_unstable_features_warning": True,
        "developer_instructions": COMMON_INSTRUCTIONS,
        "skills.include_instructions": False,
        "skills.bundled.enabled": False,
        "plugins._default.enabled": False,
        "features.skip_host_skill_discovery": True,
        "mcp_servers": {"browser": {
            "command": server.command, "args": server.args, "env_vars": server.env_vars,
            "startup_timeout_sec": server.startup_timeout_sec,
            "tool_timeout_sec": server.tool_timeout_sec,
            "required": True, "enabled": True,
            "default_tools_approval_mode": "approve",
        }},
    }
    if server.enabled_tools:
        values["mcp_servers"]["browser"]["enabled_tools"] = server.enabled_tools
    values.update({f"features.{name}": False for name in DISABLED_FEATURES})
    return values


def command(executable: str, server: Server, model: str, final_path: Path) -> list[str]:
    text(model, "model")
    argv = [
        executable, "exec", "--ignore-user-config", "--ignore-rules", "--ephemeral",
        "--skip-git-repo-check", "--sandbox", "read-only", "--json", "--color", "never",
        "--model", model, "--output-last-message", str(final_path),
    ]
    for key, value in settings(server).items():
        argv.extend(["-c", key + "=" + toml_value(value)])
    # Prompt travels through stdin rather than the process argument list.
    return argv + ["-"]


def resolve(executable: str) -> str:
    found = find_codex(executable)
    if found is None:
        raise ValueError("Codex not found; pass --codex with the executable path.")
    return str(Path(found).absolute())


def plan(server: Server, task: Task, model: str, executable: str = "codex", timeout: int = 300) -> dict:
    positive_int(timeout, "timeout")
    path = resolve(executable)
    return {
        "mode": "plan_only", "model_invoked": False,
        "expected_codex_version": PINNED_CODEX_VERSION,
        "reasoning_effort": "medium",
        "model": text(model, "model"), "server": asdict(server), "task": asdict(task),
        "timeout_sec": timeout,
        "argv_template": command(path, server, model, Path("<PRIVATE_RUN_DIR>/final.txt")),
        "auth": "Existing ChatGPT CLI login; API/provider environment not inherited.",
        "workspace": "Fresh temporary directory outside the source repository.",
        "scoring": "Unscored; no external evaluator implemented.",
    }


def preflight(path: str, env: dict[str, str]) -> dict:
    report = diagnose(path, env=env)
    if not report["prerequisites_ok"]:
        failures = ", ".join(c["name"] for c in report["checks"] if not c["passed"])
        raise ValueError("Codex preflight failed: " + failures)
    version = next(c["detail"] for c in report["checks"] if c["name"] == "codex_version")
    if version != "codex-cli " + PINNED_CODEX_VERSION:
        raise ValueError("Codex version differs from the validated pin " + PINNED_CODEX_VERSION)
    result = subprocess.run([path, "exec", "--help"], env=env,
                            capture_output=True, text=True, timeout=15, check=False)
    if result.returncode or any(flag not in result.stdout for flag in REQUIRED_EXEC_FLAGS):
        raise ValueError("Installed Codex lacks required isolation/trace options.")
    return report


def write_json(path: Path, value: dict) -> None:
    with path.open("x") as stream:
        json.dump(value, stream, indent=2, ensure_ascii=False)
        stream.write("\n")
    path.chmod(0o600)


def _has_live_group(pgid: int) -> bool:
    result = subprocess.run(["ps", "-axo", "pgid=,stat="],
                            capture_output=True, text=True, timeout=2, check=True)
    for line in result.stdout.splitlines():
        fields = line.split()
        if len(fields) >= 2 and fields[0] == str(pgid) and not fields[1].startswith("Z"):
            return True
    return False


def _await_dead_group(pgid: int) -> bool:
    deadline = time.monotonic() + 2
    while _has_live_group(pgid):
        if time.monotonic() >= deadline:
            return False
        time.sleep(0.05)
    return True


def terminate_group(process: subprocess.Popen) -> None:
    """Bound cleanup to this run's process group, including MCP children."""
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    except PermissionError:
        # Darwin can report EPERM for a group containing only dead/zombie
        # descendants. Allow a bounded grace period for in-flight exits.
        # Never swallow a permission error for surviving live processes.
        if not _await_dead_group(process.pid):
            raise
    try:
        process.wait(timeout=1)
    except subprocess.TimeoutExpired:
        pass
    # The parent may have exited while children ignored SIGTERM.
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    except PermissionError:
        if not _await_dead_group(process.pid):
            raise
    process.wait()


def run(
    server: Server, task: Task, model: str, *, executable: str = "codex",
    codex_home: str | None = None, timeout: int = 300, output_root: str = "runs",
    confirm_isolated_browser: bool = False,
    resource_roots: tuple[ResourceRoot, ...] = (),
    resource_observer: ResourceCollector | None = None,
) -> dict:
    if os.name != "posix":
        raise ValueError("Process-group cleanup is currently supported only on POSIX.")
    if not confirm_isolated_browser:
        raise ValueError("Use --confirm-isolated-browser only after setting up a dedicated test browser/profile.")
    positive_int(timeout, "timeout")
    text(model, "model")
    path = resolve(executable)
    env = codex_environment(path, codex_home, server.env_vars)
    preflight_report = preflight(path, env)
    root = Path(output_root).expanduser().absolute()
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    run_dir = root / (datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ-") + uuid.uuid4().hex[:12])
    run_dir.mkdir(mode=0o700)
    final_path = run_dir / "final.txt"
    argv = command(path, server, model, final_path)
    manifest = {
        "schema_version": 1, "harness": "codex", "codex_version": PINNED_CODEX_VERSION,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "model": model, "reasoning_effort": "medium",
        "server": asdict(server), "task": asdict(task),
        "harness_sha256": hashlib.sha256(b"".join(
            p.name.encode() + b"\x00" + p.read_bytes()
            for p in sorted(Path(__file__).parent.glob("*.py"))
        )).hexdigest(),
        "prompt_sha256": hashlib.sha256(task.prompt.encode()).hexdigest(),
        "timeout_sec": timeout, "auth_policy": "chatgpt_subscription_only",
        "argv": argv, "preflight": preflight_report,
        "isolated_browser_confirmed_by_operator": True,
        "environment_reset": "not_implemented", "external_evaluation": "not_implemented",
        "token_budget": "not_enforced", "api_cost": None,
        "resource_sampling_interval_sec": 1.0,
        "privacy": "Private raw artifacts; review/redact before sharing.",
    }
    write_json(run_dir / "manifest.json", manifest)
    started = time.monotonic()
    timed_out = False
    interrupted = False
    returncode = None
    launch_failed = False
    events_path = run_dir / "events.jsonl"
    stderr_path = run_dir / "stderr.log"
    with ResourceCollector(run_dir, roots=resource_roots) as resources:
        with tempfile.TemporaryDirectory(prefix="browser-mcp-bench-") as workspace:
            with events_path.open("xb") as stdout, stderr_path.open("xb") as stderr:
                try:
                    process = subprocess.Popen(argv, cwd=workspace, env=env,
                        stdin=subprocess.PIPE, stdout=stdout, stderr=stderr, start_new_session=True)
                except OSError:
                    launch_failed = True
                else:
                    resource_root = ResourceRoot(process.pid, "harness", server.id)
                    resources.register(resource_root)
                    if resource_observer is not None:
                        resource_observer.register(resource_root)
                    resources.set_phase("task")
                    try:
                        process.communicate(task.prompt.encode(), timeout=timeout)
                    except subprocess.TimeoutExpired:
                        timed_out = True
                    except KeyboardInterrupt:
                        interrupted = True
                    finally:
                        resources.set_phase("cleanup")
                        terminate_group(process)
                    returncode = process.returncode
    # Even stderr and successful final answers may contain private page contents.
    for file in run_dir.iterdir():
        if file.is_file():
            file.chmod(0o600)
    audit = audit_events(events_path, allowed_tools=server.enabled_tools or None)
    if interrupted:
        status = "interrupted"
    elif timed_out:
        status = "timeout"
    elif launch_failed or returncode != 0 or audit["harness_error"]:
        status = "harness_error"
    elif audit["violations"]:
        status = "invalid_trace"
    elif not audit["turn_completed"] or not audit["completed_mcp_calls"] or not final_path.is_file():
        status = "incomplete"
    else:
        status = "completed_unscored"
    summary = {
        "schema_version": 1, "run_dir": str(run_dir), "execution_status": status,
        "returncode": returncode, "elapsed_sec": round(time.monotonic() - started, 3),
        "model": model, "server_id": server.id, "task_id": task.id, **audit,
        "resources": {
            "summary_path": str(run_dir / "resource-summary.json"),
            "task": resources.summary["metrics"].get("phase/task/all"),
            "sampling_errors": resources.summary["sampling_errors"],
            "unexpected_alive_at_stop": resources.summary["unexpected_alive_at_stop"],
        },
    }
    write_json(run_dir / "summary.json", summary)
    return summary
