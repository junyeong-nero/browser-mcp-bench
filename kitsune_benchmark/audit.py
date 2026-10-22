"""Conservative post-run audit of Codex JSONL; never judge task success."""

from __future__ import annotations

import json
from pathlib import Path

ALLOWED_ITEMS = {"agent_message", "reasoning", "plan", "mcp_tool_call", "error"}
ALLOWED_EVENTS = {
    "thread.started", "turn.started", "turn.completed", "turn.failed", "error",
    "item.started", "item.updated", "item.completed",
}


def audit_events(path: Path, *, allowed_tools: tuple[str, ...] | None = None) -> dict:
    violations: set[str] = set()
    calls: set[str] = set()
    failed_calls: set[str] = set()
    completed_calls: set[str] = set()
    usage: dict[str, int] = {}
    completed = False
    harness_error = False
    events = 0
    with path.open("rb") as stream:
        for raw_line in stream:
            if not raw_line.strip():
                continue
            events += 1
            try:
                event = json.loads(raw_line.decode("utf-8"))
            except (ValueError, UnicodeError):
                violations.add("malformed_jsonl")
                continue
            if not isinstance(event, dict):
                violations.add("malformed_event")
                continue
            kind = event.get("type")
            if not isinstance(kind, str) or kind not in ALLOWED_EVENTS:
                violations.add("unrecognized_event")
                continue
            if kind in {"error", "turn.failed"}:
                harness_error = True
            if kind == "turn.completed":
                completed = True
                tokens = event.get("usage")
                if isinstance(tokens, dict):
                    for key in ("input_tokens", "cached_input_tokens", "output_tokens", "reasoning_output_tokens"):
                        value = tokens.get(key)
                        if type(value) is int and value >= 0:
                            usage[key] = usage.get(key, 0) + value
            if kind.startswith("item."):
                item = event.get("item")
                if not isinstance(item, dict):
                    violations.add("malformed_item")
                    continue
                item_type = item.get("type")
                if not isinstance(item_type, str) or item_type not in ALLOWED_ITEMS:
                    violations.add("forbidden_or_unknown_item")
                elif item_type == "error":
                    harness_error = True
                elif item_type == "mcp_tool_call":
                    if allowed_tools is not None:
                        if item.get("tool") not in allowed_tools:
                            violations.add("tool_outside_benchmark_allowlist")
                        arguments = item.get("arguments")
                        if isinstance(arguments, dict):
                            url = arguments.get("url")
                            if isinstance(url, str) and url.strip().lower().startswith(("javascript:", "data:", "file:")):
                                violations.add("forbidden_navigation_scheme")
                    if item.get("server") != "browser":
                        violations.add("unexpected_mcp_server")
                    call_id = item.get("id")
                    if not isinstance(call_id, str):
                        violations.add("missing_mcp_call_id")
                        continue
                    calls.add(call_id)
                    if kind == "item.completed" and item.get("status") == "completed":
                        completed_calls.add(call_id)
                    result = item.get("result")
                    is_error = isinstance(result, dict) and result.get("isError") is True
                    if item.get("status") == "failed" or item.get("error") or is_error:
                        failed_calls.add(call_id)
    return {
        "events": events,
        "turn_completed": completed,
        "harness_error": harness_error,
        "mcp_calls": len(calls),
        "completed_mcp_calls": len(completed_calls),
        "failed_mcp_calls": len(failed_calls),
        "usage": usage,
        "violations": sorted(violations),
        "task_success": None,
        "evaluation": "not_implemented",
    }
