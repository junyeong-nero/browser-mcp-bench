"""Offline analysis of personal-task evidence. Never invokes a model or browser.

Usage: python -m browser_mcp_bench.personal_analysis <suite-summary.json> --output <private.json>
Serialized schema sizes are characters/bytes, NOT provider token estimates.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path

from .adapter import write_json


def compact(value) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def native_error(result: dict) -> bool:
    if result.get("isError"):
        return True
    for item in result.get("content", []):
        if item.get("type") != "text":
            continue
        text = item.get("text", "")
        if text.startswith("### Error"):
            return True
        try:
            value = json.loads(text)
            if isinstance(value, dict) and (value.get("error") or value.get("ok") is False):
                return True
        except ValueError:
            pass
    return False


def analyze_run(pair: dict, target: str, result: dict) -> dict:
    directory = Path(pair["pair_dir"])
    rpc_path = directory / f"{target}-native-rpc.jsonl"
    metadata_path = directory / f"{target}-native-metadata.json"
    records = [json.loads(line) for line in rpc_path.read_text().splitlines() if line.strip()] if rpc_path.exists() else []
    completed = [r for r in records if r["kind"] == "rpc_completed"]
    setup = next((r for r in records if r["kind"] == "setup_completed"), None)
    agent = [r for r in completed if r["role"] == "agent" and r["method"] == "tools/call"]
    post_inventory = [r for r in completed if r["role"] == "harness" and setup and r["offset_sec"] > setup["offset_sec"]]
    metadata = json.loads(metadata_path.read_text()) if metadata_path.exists() else {}
    native_tools = {tool["name"]: tool for page in metadata.get("tools_pages", []) for tool in page.get("tools", [])}
    enabled_tools = [native_tools[name] for name in sorted(metadata.get("enabled_tools", [])) if name in native_tools]
    events_path = Path(result["run_dir"]) / "events.jsonl"
    events = [json.loads(line) for line in events_path.read_text().splitlines() if line.strip()]
    calls = [e["item"] for e in events if e.get("type") == "item.completed" and e.get("item", {}).get("type") == "mcp_tool_call"]
    evaluation = result.get("benchmark_evaluation", {})
    usage = result.get("usage", {})
    setup_seconds = setup["duration_sec"] if setup else None
    agent_seconds = sum(r["duration_sec"] for r in agent) if records else None
    control_seconds = sum(r["duration_sec"] for r in completed if r["role"] == "agent" and r["method"] != "tools/call") if records else None
    inventory_seconds = sum(r["duration_sec"] for r in post_inventory) if records else None
    elapsed = result.get("elapsed_sec")
    residual = (elapsed - setup_seconds - agent_seconds - control_seconds - inventory_seconds
                if elapsed is not None and setup_seconds is not None else None)
    return {"task_id": pair.get("personal_task"), "target": target, "variant": pair.get("variant"),
        "pair_dir": str(directory), "run_dir": result["run_dir"],
        "execution_status": result.get("execution_status"), "scorable": evaluation.get("scorable"),
        "task_success": evaluation.get("task_success"), "functional_success": evaluation.get("functional_success"),
        "safety_pass": evaluation.get("safety_pass"), "seeded_tabs_preserved": evaluation.get("seeded_tabs_preserved"),
        "usage": usage, "noncached_input_tokens": usage["input_tokens"] - usage["cached_input_tokens"]
            if "input_tokens" in usage and "cached_input_tokens" in usage else None,
        "elapsed_sec": elapsed, "agent_calls": result.get("mcp_calls"),
        "agent_tool_sequence": [c.get("tool") for c in calls],
        "agent_result_errors": sum(native_error(c.get("result") or {}) for c in calls),
        "agent_tools": dict(Counter(c.get("tool") for c in calls)),
        "native_diagnostics_available": bool(records), "setup_sec": setup_seconds,
        "agent_native_rpc_sec": agent_seconds, "agent_control_rpc_sec": control_seconds,
        "post_setup_inventory_rpc_sec": inventory_seconds,
        "residual_non_rpc_sec": residual,
        "readiness_wait_sec": sum(r["duration_sec"] for r in records if r["kind"] == "readiness_wait") if records else None,
        "cached_setup_tab_reads": sum(r["tool"] == "browser_tabs" and r["cached"] for r in completed
            if setup and r["offset_sec"] < setup["offset_sec"]),
        "agent_response_text_chars": sum(r["response_text_chars"] for r in agent) if records else None,
        "agent_response_text_bytes": sum(r["response_text_bytes"] for r in agent) if records else None,
        "harness_calls": evaluation.get("harness_mcp_calls"),
        "harness_seconds": evaluation.get("harness_seconds"),
        "native_tool_count": len(native_tools) if metadata else None,
        "enabled_tool_count": len(enabled_tools) if metadata else None,
        "enabled_schema_chars": len(compact(enabled_tools)) if metadata else None,
        "enabled_schema_bytes": len(compact(enabled_tools).encode()) if metadata else None,
        "enabled_tools_missing": sorted(set(metadata.get("enabled_tools", [])) - native_tools.keys()),
        "initialize_instruction_chars": len(metadata.get("initialize", {}).get("instructions", "")) if metadata else None,
        "schema_by_tool": {t["name"]: {"chars": len(compact(t)), "bytes": len(compact(t).encode())} for t in enabled_tools},
        "agent_rpc": [{key: r.get(key) for key in ("tool", "duration_sec", "response_text_chars", "response_text_bytes", "is_error")} for r in agent]}


def analyze_suite(path: Path) -> dict:
    suite = json.loads(path.read_text())
    rows = [analyze_run(pair, target, result) for pair in suite["pairs"] for target, result in pair["results"].items()]
    totals = {}
    for target in sorted({row["target"] for row in rows}):
        runs = [r for r in rows if r["target"] == target]
        scorable = [r for r in runs if r["scorable"]]
        both_success = [r for r in runs if r["task_success"] and any(
            other["task_id"] == r["task_id"] and other["target"] != target and other["task_success"] for other in rows)]
        keys = ("elapsed_sec", "agent_calls", "noncached_input_tokens", "setup_sec", "agent_native_rpc_sec",
                "post_setup_inventory_rpc_sec", "residual_non_rpc_sec", "readiness_wait_sec", "cached_setup_tab_reads",
                "agent_response_text_chars", "agent_response_text_bytes", "harness_calls", "agent_result_errors")
        totals[target] = {"attempted": len(runs), "scorable": len(scorable),
            "successes": sum(r["task_success"] is True for r in runs),
            "functional_successes": sum(r["functional_success"] is True for r in runs),
            "safety_failures": sum(r["safety_pass"] is False for r in runs),
            "diagnostic_runs": sum(r["native_diagnostics_available"] for r in runs),
            "totals": {key: sum(r[key] for r in runs if r[key] is not None) for key in keys},
            "usage": {key: sum(r["usage"].get(key, 0) for r in runs)
                      for key in sorted({k for r in runs for k in r["usage"]})},
            "both_successful_tasks": [r["task_id"] for r in both_success],
            "both_successful_elapsed_sec": sum(r["elapsed_sec"] for r in both_success),
            "both_successful_input_tokens": sum(r["usage"].get("input_tokens", 0) for r in both_success)}
    return {"schema_version": 1, "suite_path": str(path), "model": suite.get("model"),
            "requested_pairs": suite.get("requested_pairs"), "completed_pairs": suite.get("completed_pairs"),
            "by_target": totals, "runs": rows,
            "limits": ["Schema characters/bytes are not tokenizer counts or exact model context attribution.",
                       "Usage is turn-total only; per-model-request context/usage is not exposed by these logs.",
                       "Native RPC includes client/transport/server work, not an isolated backend timer.",
                       "Residual time includes model/network/Codex/startup/cleanup/logging; it is not pure model time.",
                       "Setup includes hidden RPC and readiness sleep; do not add nested durations together.",
                       "Totals with missing diagnostics are partial; check diagnostic_runs and null per-run fields.",
                       "Single fixed-order variant; safety/format failures can confound efficiency comparisons."]}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("suite", type=Path)
    parser.add_argument("--output", type=Path, help="New private JSON file; refuses overwrite")
    args = parser.parse_args()
    result = analyze_suite(args.suite)
    if args.output:
        write_json(args.output, result)
        print(str(args.output))
    else:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
