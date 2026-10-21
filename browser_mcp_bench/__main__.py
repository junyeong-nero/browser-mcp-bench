"""CLI: model execution requires `run` or an explicit `--execute`."""

from __future__ import annotations

import argparse
import json
import subprocess

from .adapter import HARNESSES, plan, run
from . import claude_harness
from .doctor import diagnose
from .specs import load_server, load_task
from .smoke import run_pair
from .miniwob import run_benchmark
from .personal import config as personal_config, pair_complete, run_personal, runnable_ids


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Browser MCP benchmark tooling")
    subparsers = parser.add_subparsers(dest="command", required=True)
    doctor = subparsers.add_parser("doctor", help="Check Codex prerequisites without a model call")
    doctor.add_argument("--codex", default="codex", help="Codex executable name or path")
    doctor.add_argument("--codex-home", help="Existing Codex home to check; no credentials are copied")
    doctor.add_argument("--json", action="store_true", help="Print machine-readable diagnostics")
    doctor.add_argument("--harness", choices=HARNESSES, default="codex")
    doctor.add_argument("--claude", default="claude", help="Claude Code executable name or path")
    for name in ("plan", "run"):
        child = subparsers.add_parser(name, help=(
            "Print configuration without invoking Codex" if name == "plan"
            else "Invoke Codex; consumes subscription usage"))
        child.add_argument("--server", required=True, help="Server JSON configuration")
        child.add_argument("--task", required=True, help="Task JSON configuration")
        child.add_argument("--model", required=True, help="Explicit subscription-accessible model ID")
        child.add_argument("--codex", default="codex")
        child.add_argument("--timeout", type=int, default=300, help="Wall-clock seconds per run")
        if name == "run":
            child.add_argument("--codex-home", help="Auth home; its config.toml is ignored")
            child.add_argument("--output-root", default="runs")
            child.add_argument("--confirm-isolated-browser", action="store_true",
                               help="Confirm a dedicated test browser/profile, not your everyday session")
    smoke = subparsers.add_parser("smoke", help="Plan or explicitly execute the isolated smoke pair")
    smoke.add_argument("--execute", action="store_true", help="Start private browsers and consume subscription quota")
    smoke.add_argument("--codex", default="codex")
    smoke.add_argument("--kitsune-project", help="Kitsune source checkout; defaults to sibling directory")
    smoke.add_argument("--timeout", type=int, help="Wall-clock seconds per agent run")
    benchmark = subparsers.add_parser("benchmark", help="MiniWoB++ UI-only pilot; defaults to a plan")
    benchmark.add_argument("--execute", action="store_true", help="Run the pinned external task; consumes subscription quota")
    benchmark.add_argument("--fetch", action="store_true", help="Download the pinned upstream source, without inference unless --execute")
    benchmark.add_argument("--codex", default="codex")
    benchmark.add_argument("--kitsune-project")
    personal = subparsers.add_parser("personal", help="Personal browsing: 24 runnable local tasks (six-task pilot by default); plan by default")
    personal.add_argument("--execute", action="store_true", help="Run selected pairs; consumes subscription quota")
    personal.add_argument("--task", action="append", dest="task_ids", help="Runnable task ID; repeat to select several; default: six pilot tasks")
    personal.add_argument("--all", action="store_true", help="Select all 24 runnable tasks (48 agent runs with --execute)")
    personal.add_argument("--variant", type=int, choices=(0, 1, 2), default=0)
    personal.add_argument("--codex", default="codex")
    personal.add_argument("--kitsune-project")
    personal.add_argument("--kitsune-preset", help="Set KITSUNE_TOOL_PRESET for Kitsune (e.g. lean) for A/B arms")
    personal.add_argument("--targets", default="playwright,kitsune",
                          help="Comma-separated MCPs to run: playwright,kitsune (default both)")
    personal.add_argument("--budget-usd", type=float,
                          help="claude-api only: stop before a pair whose worst case would exceed this total")
    for child in (smoke, benchmark, personal):
        child.add_argument("--harness", choices=HARNESSES, default="codex",
                           help="Agent CLI: codex (ChatGPT login), claude (Claude Code, claude.ai login) "
                                "claude-api (Claude Code --bare, ANTHROPIC_API_KEY from .env; billed per token) "
                                "or claude-api-full (same key, no --bare: full tool descriptions)")
        child.add_argument("--claude", default="claude", help="Claude Code executable name or path")
    args = parser.parse_args(argv)
    claude = getattr(args, "harness", "codex").startswith("claude")
    executable = getattr(args, "claude", None) if claude else args.codex
    try:
        if args.command == "doctor":
            if claude:
                api = args.harness in ("claude-api", "claude-api-full")
                model = personal_config()["claude_code"]["model"] if api else None
                report = claude_harness.diagnose(args.claude, api=api, model=model)
            else:
                report = diagnose(args.codex, args.codex_home)
            if args.json:
                print(json.dumps(report, indent=2))
            else:
                for check in report["checks"]:
                    print(f"{'OK' if check['passed'] else 'FAIL'} {check['name']}: {check['detail']}")
                print("No model invoked. These checks do not certify benchmark readiness.")
            return 0 if report["prerequisites_ok"] else 2
        if args.command == "personal":
            if args.all and args.task_ids:
                raise ValueError("Use either --all or --task.")
            result = run_personal(execute=args.execute, task_ids=runnable_ids() if args.all else args.task_ids, variant=args.variant,
                                  executable=executable, kitsune_project=args.kitsune_project,
                                  harness=args.harness, budget_usd=args.budget_usd,
                                  kitsune_preset=args.kitsune_preset, targets=tuple(args.targets.split(",")))
            print(json.dumps(result, indent=2, ensure_ascii=False))
            if not args.execute:
                return 0
            return 0 if result["completed_pairs"] == result["requested_pairs"] and all(
                pair_complete(pair, tuple(result["targets"])) for pair in result["pairs"]) else 3
        if args.command == "benchmark":
            result = run_benchmark(execute=args.execute, fetch=args.fetch,
                                   executable=executable, kitsune_project=args.kitsune_project,
                                   harness=args.harness)
            print(json.dumps(result, indent=2, ensure_ascii=False))
            if not args.execute:
                return 0
            results = result["results"]
            return 0 if len(results) == 2 and all(
                item.get("benchmark_evaluation", {}).get("scorable") for item in results.values()) else 3
        if args.command == "smoke":
            result = run_pair(execute=args.execute, kitsune_project=args.kitsune_project,
                              executable=executable, timeout=args.timeout, harness=args.harness)
            print(json.dumps(result, indent=2, ensure_ascii=False))
            if not args.execute:
                return 0
            results = result["results"]
            return 0 if len(results) == 2 and all(
                item["execution_status"] == "completed_unscored" for item in results.values()) else 3
        server, task = load_server(args.server), load_task(args.task)
        if args.command == "plan":
            result = plan(server, task, args.model, args.codex, args.timeout)
        else:
            result = run(server, task, args.model, executable=args.codex,
                         codex_home=args.codex_home, timeout=args.timeout,
                         output_root=args.output_root,
                         confirm_isolated_browser=args.confirm_isolated_browser)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        if args.command == "plan" or result["execution_status"] == "completed_unscored":
            return 0
        return 3
    except (OSError, ValueError, subprocess.SubprocessError):
        # JSON/OS exceptions may include config lines, paths, or secrets.
        # Do not echo raw exception text to automated logs.
        print("Preflight/input error. Check CLI location/login, input schema, explicit model, "
              "required environment, and isolated-browser confirmation. No API fallback.")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
