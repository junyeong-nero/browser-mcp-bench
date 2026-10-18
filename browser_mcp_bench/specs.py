"""Small, explicit input format. No arbitrary Codex config overrides."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import re


@dataclass(frozen=True)
class Server:
    id: str
    command: str
    args: tuple[str, ...]
    env_vars: tuple[str, ...] = ()
    startup_timeout_sec: int = 60
    tool_timeout_sec: int = 60
    enabled_tools: tuple[str, ...] = ()


@dataclass(frozen=True)
class Task:
    id: str
    prompt: str


def text(value: object, name: str) -> str:
    if not isinstance(value, str) or not value.strip() or "\x00" in value:
        raise ValueError(f"{name} must be a nonempty string without NUL characters.")
    if any(marker in value for marker in ("/ABSOLUTE/PATH/", "REPLACE_ME", "SET_EXPLICIT_MODEL")):
        raise ValueError(f"Replace the placeholder in {name} before use.")
    return value


def identifier(value: object) -> str:
    value = text(value, "id")
    if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_.-]{0,79}", value):
        raise ValueError("id must contain only letters, digits, '.', '_' and '-'.")
    return value


def strings(value: object, name: str) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise ValueError(f"{name} must be an array of strings.")
    return tuple(text(item, name) for item in value)


def positive_int(value: object, name: str) -> int:
    if type(value) is not int or value <= 0:
        raise ValueError(f"{name} must be a positive integer.")
    return value


def load_object(path: str | Path, allowed: set[str]) -> dict:
    value = json.loads(Path(path).read_text())
    if not isinstance(value, dict) or set(value) - allowed:
        raise ValueError("Expected a JSON object with only documented fields.")
    return value


def load_server(path: str | Path) -> Server:
    value = load_object(path, {"id", "command", "args", "env_vars", "startup_timeout_sec", "tool_timeout_sec", "enabled_tools"})
    env_vars = strings(value.get("env_vars", []), "env_vars")
    if any(not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", v) for v in env_vars):
        raise ValueError("Invalid environment variable name.")
    return Server(
        identifier(value.get("id")), text(value.get("command"), "command"),
        strings(value.get("args", []), "args"), env_vars,
        positive_int(value.get("startup_timeout_sec", 60), "startup_timeout_sec"),
        positive_int(value.get("tool_timeout_sec", 60), "tool_timeout_sec"),
        strings(value.get("enabled_tools", []), "enabled_tools"),
    )


def load_task(path: str | Path) -> Task:
    value = load_object(path, {"id", "prompt"})
    return Task(identifier(value.get("id")), text(value.get("prompt"), "prompt"))


def toml_value(value: object) -> str:
    """Serialize the bounded types used in -c overrides as TOML inline values."""
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=True)
    if isinstance(value, bool):
        return "true" if value else "false"
    if type(value) is int:
        return str(value)
    if isinstance(value, (tuple, list)):
        return "[" + ", ".join(toml_value(v) for v in value) + "]"
    if isinstance(value, dict):
        return "{ " + ", ".join(toml_value(k) + " = " + toml_value(v) for k, v in value.items()) + " }"
    raise ValueError("Unsupported TOML value type.")
