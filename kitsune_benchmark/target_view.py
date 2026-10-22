"""Lossless presentation of existing snapshot lines; no browser/model calls.

Each record carries its source line number, parent line, a role-derived hint,
and the exact original line. Sorting records reconstructs the native string.
"""
from __future__ import annotations

import copy
import json
import re

HEADER = "Target view: n<parent hint | original line. Hints are role-based candidates, not verified actionability; 0=no parent."
ROLE = re.compile(r"^( *)(?:- )([\w-]+)(?:\s|$)")
RECORD = re.compile(r"^(\d+)<(\d+) ([\w-]+) \| (.*)$")
MEDIA = {"img", "image", "video", "audio"}
ACTIONS = {
    "button": "click", "link": "click", "checkbox": "toggle", "radio": "choose",
    "switch": "toggle", "textbox": "type", "searchbox": "type", "combobox": "choose",
    "listbox": "choose", "option": "choose", "slider": "adjust", "spinbutton": "adjust",
    "tab": "choose", "menuitem": "click", "menuitemcheckbox": "toggle", "menuitemradio": "choose",
}


def format_snapshot(snapshot: str):
    """Return formatted text and counts; leave empty/unrecognized content alone."""
    lines = snapshot.split("\n")
    if not snapshot or not any(ROLE.match(line) for line in lines):
        return snapshot, {"formatted": 0, "fallback": 1, "interactions": 0, "media": 0, "context": len(lines)}
    groups = {"INTERACTIONS": [], "MEDIA": [], "CONTEXT": []}
    stack = []
    for number, line in enumerate(lines, 1):
        match = ROLE.match(line)
        role = match[2] if match else None
        parent = 0
        if match:
            indent = len(match[1])
            while stack and stack[-1][0] >= indent:
                stack.pop()
            parent = stack[-1][1] if stack else 0
            stack.append((indent, number))
        group = "MEDIA" if role in MEDIA else "INTERACTIONS" if role in ACTIONS else "CONTEXT"
        hint = ACTIONS.get(role, "inspect" if role in MEDIA else "read")
        # Match flags outside the quoted accessible name, not name text such as "[disabled]".
        attributes = re.sub(r'"(?:\\.|[^"\\])*"', '""', line)
        if role in ACTIONS and re.search(r"\[disabled(?:=true)?\]", attributes):
            hint = "disabled"
        elif role in {"textbox", "searchbox", "combobox", "spinbutton"} and re.search(r"\[(?:readonly|read-only)(?:=true)?\]", attributes):
            hint = "readonly"
        groups[group].append(f"{number}<{parent} {hint} | {line}")
    output = [HEADER]
    for name, records in groups.items():
        output.append(f"[{name}]")
        output.extend(records)
    formatted = "\n".join(output)
    assert reconstruct_snapshot(formatted) == snapshot
    return formatted, {"formatted": 1, "fallback": 0,
                       **{key.lower(): len(value) for key, value in groups.items()}}


def reconstruct_snapshot(formatted):
    if not formatted.startswith(HEADER + "\n"):
        raise ValueError("Not a target-view snapshot")
    records = {}
    for line in formatted.split("\n")[1:]:
        if line in {"[INTERACTIONS]", "[MEDIA]", "[CONTEXT]"}:
            continue
        match = RECORD.fullmatch(line)
        if not match or int(match[1]) in records:
            raise ValueError("Malformed target-view record")
        records[int(match[1])] = match[4]
    if set(records) != set(range(1, len(records) + 1)):
        raise ValueError("Missing source lines")
    return "\n".join(records[i] for i in range(1, len(records) + 1))


def format_result(message):
    """Transform JSON snapshot fields in text/structured content, leaving other fields intact.

    Text and structured copies may both contain a snapshot; counts are physical
    representations transformed, not unique browser observations.
    """
    output = copy.deepcopy(message)
    counts = {k: 0 for k in ("formatted", "fallback", "interactions", "media", "context")}
    def walk(value):
        if isinstance(value, dict):
            for key, child in list(value.items()):
                if key == "snapshot" and isinstance(child, str):
                    value[key], stats = format_snapshot(child)
                    for name, count in stats.items():
                        counts[name] += count
                else:
                    walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)
    result = output.get("result", {})
    for item in result.get("content", []):
        if item.get("type") != "text":
            continue
        try:
            payload = json.loads(item["text"])
        except (ValueError, KeyError):
            continue
        before = copy.deepcopy(payload)
        walk(payload)
        if payload != before:
            item["text"] = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    if "structuredContent" in result:
        walk(result["structuredContent"])
    return output, counts
