"""Run every graded track (personal 24×3 variants, gallery 21×3×2 layouts, MiniWoB) under one total budget.

Each track command gets the remaining budget via --budget-usd, so the suite as a whole never starts a pair
whose worst case would exceed it. A failed or stopped command is logged and the next one still runs.

usage: uv run --locked python scripts/run-full-suite.py --model claude-opus-5-5 --budget-usd 100 \
           --max-budget-usd-per-run 5 --kitsune-project artifacts/vendor/kitsune-pinned --out artifacts/opus-full
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path


def commands() -> list[tuple[str, list[str]]]:
    items = [(f"personal-v{v}", ["personal", "--all", "--variant", str(v)]) for v in range(3)]
    items += [(f"gallery-{layout}-v{v}", ["gallery", "--layout", layout, "--variant", str(v)])
              for layout in ("crowded", "isolated") for v in range(3)]
    items.append(("miniwob", ["benchmark"]))
    return items


def git_identity(project: str | Path, match: str | None = None) -> dict:
    """Revision and tag-relative name of a checkout, for grouping results by version."""
    def git(*argv: str) -> str | None:
        done = subprocess.run(["git", "-C", str(project), *argv], capture_output=True, text=True)
        return done.stdout.strip() if done.returncode == 0 else None
    pattern = ("--match", match) if match else ()
    return {"revision": git("rev-parse", "HEAD"), "describe": git("describe", "--tags", *pattern, "--dirty"),
            "tag": git("describe", "--tags", *pattern, "--abbrev=0")}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True)
    parser.add_argument("--budget-usd", type=float, required=True)
    parser.add_argument("--max-budget-usd-per-run", type=float, required=True)
    parser.add_argument("--kitsune-project", required=True)
    parser.add_argument("--harness", default="claude-api")
    parser.add_argument("--out", required=True)
    parser.add_argument("--spent-usd", type=float, default=0.0, help="Already spent toward the budget")
    args = parser.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    spent = args.spent_usd
    manifest = {"model": args.model, "harness": args.harness, "budget_usd": args.budget_usd,
                "max_budget_usd_per_run": args.max_budget_usd_per_run,
                "kitsune_project": str(Path(args.kitsune_project).resolve()),
                "kitsune": git_identity(args.kitsune_project),
                "taskset": git_identity(Path(__file__).resolve().parent.parent, "taskset-*"),
                "started": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "commands": [name for name, _ in commands()]}
    (out / "suite-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    log = out / "suite-log.jsonl"
    for name, argv in commands():
        remaining = args.budget_usd - spent
        worst_pair = 2 * args.max_budget_usd_per_run
        if remaining < worst_pair:
            entry = {"name": name, "skipped": "budget", "spent_usd": spent}
        else:
            full = [sys.executable, "-m", "kitsune_benchmark", *argv, "--harness", args.harness,
                    "--claude-model", args.model, "--max-budget-usd-per-run", str(args.max_budget_usd_per_run),
                    "--kitsune-project", args.kitsune_project, "--execute"]
            if name != "miniwob":
                full += ["--budget-usd", str(round(remaining, 6))]
            started = time.time()
            print(f"[{time.strftime('%H:%M:%S')}] {name}: remaining ${remaining:.2f}", flush=True)
            with (out / f"{name}.json").open("w") as stdout, (out / f"{name}.err").open("w") as stderr:
                code = subprocess.run(full, stdout=stdout, stderr=stderr).returncode
            try:
                result = json.loads((out / f"{name}.json").read_text())
            except (OSError, ValueError):
                result = {}
            cost = result.get("estimated_cost_usd")
            if cost is None and name == "miniwob":
                cost = worst_pair  # not reported by the MiniWoB runner; count its worst case
            spent += cost or 0.0
            entry = {"name": name, "exit": code, "seconds": round(time.time() - started, 1),
                     "cost_usd": cost, "spent_usd": round(spent, 6),
                     "attempted_pairs": result.get("attempted_pairs"), "requested_pairs": result.get("requested_pairs"),
                     "completed_pairs": result.get("completed_pairs"), "stopped_reason": result.get("stopped_reason"),
                     "suite_summary_path": result.get("suite_summary_path")}
        print(json.dumps(entry), flush=True)
        with log.open("a") as handle:
            handle.write(json.dumps(entry) + "\n")
    print(f"done; estimated spend ${spent:.2f} of ${args.budget_usd:.2f}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
