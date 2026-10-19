"""CLI: model execution requires `run` or an explicit `--execute`."""

from __future__ import annotations

import argparse
import json
import subprocess

from .adapter import plan, run
from .doctor import diagnose
from .specs import load_server, load_task
from .smoke import run_pair
from .miniwob import run_benchmark
from .personal import run_personal


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Browser MCP benchmark tooling")
    subparsers = parser.add_subparsers(dest="command", required=True)
    doctor = subparsers.add_parser("doctor", help="Check Codex prerequisites without a model call")
    doctor.add_argument("--codex", default="codex", help="Codex executable name or path")
    doctor.add_argument("--codex-home", help="Existing Codex home to check; no credentials are copied")
    doctor.add_argument("--json", action="store_true", help="Print machine-readable diagnostics")
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
    smoke.add_argument("--timeout", type=int, help="Wall-clock seconds per Codex run")
    benchmark = subparsers.add_parser("benchmark", help="MiniWoB++ UI-only pilot; defaults to a plan")
    benchmark.add_argument("--execute", action="store_true", help="Run the pinned external task; consumes subscription quota")
    benchmark.add_argument("--fetch", action="store_true", help="Download the pinned upstream source, without inference unless --execute")
    benchmark.add_argument("--codex", default="codex")
    benchmark.add_argument("--kitsune-project")
    personal = subparsers.add_parser("personal", help="Personal browsing: 24 specs, six runnable local tasks; plan by default")
    personal.add_argument("--execute", action="store_true", help="Run selected pairs; consumes subscription quota")
    personal.add_argument("--task", action="append", dest="task_ids", help="Runnable task ID; repeat to select several; default: six pilot tasks")
    personal.add_argument("--variant", type=int, choices=(0, 1, 2), default=0)
    personal.add_argument("--codex", default="codex")
    personal.add_argument("--kitsune-project")
    args = parser.parse_args(argv)
    try:
        if args.command == "doctor":
            report = diagnose(args.codex, args.codex_home)
            if args.json:
                print(json.dumps(report, indent=2))
            else:
                for check in report["checks"]:
                    print(f"{'OK' if check['passed'] else 'FAIL'} {check['name']}: {check['detail']}")
                print("No model invoked. These checks do not certify benchmark readiness.")
            return 0 if report["prerequisites_ok"] else 2
        if args.command == "personal":
            result = run_personal(execute=args.execute, task_ids=args.task_ids, variant=args.variant,
                                  executable=args.codex, kitsune_project=args.kitsune_project)
            print(json.dumps(result, indent=2, ensure_ascii=False))
            if not args.execute:
                return 0
            return 0 if result["completed_pairs"] == result["requested_pairs"] and all(
                len(pair["results"]) == 2 and all(
                    run.get("benchmark_evaluation", {}).get("scorable") for run in pair["results"].values())
                for pair in result["pairs"]) else 3
        if args.command == "benchmark":
            result = run_benchmark(execute=args.execute, fetch=args.fetch,
                                   executable=args.codex, kitsune_project=args.kitsune_project)
            print(json.dumps(result, indent=2, ensure_ascii=False))
            if not args.execute:
                return 0
            results = result["results"]
            return 0 if len(results) == 2 and all(
                item.get("benchmark_evaluation", {}).get("scorable") for item in results.values()) else 3
        if args.command == "smoke":
            result = run_pair(execute=args.execute, kitsune_project=args.kitsune_project,
                              executable=args.codex, timeout=args.timeout)
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
