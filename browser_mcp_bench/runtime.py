"""Executable discovery and deliberately restricted child environments."""

from __future__ import annotations

import os
from pathlib import Path
import shutil
from collections.abc import Mapping

API_ENV = frozenset({"OPENAI_API_KEY", "CODEX_API_KEY", "OPENAI_AUTH_TOKEN", "AZURE_OPENAI_API_KEY"})
BASE_ENV = frozenset({
    "HOME", "USER", "LOGNAME", "SHELL", "PATH", "TMPDIR", "TMP", "TEMP",
    "LANG", "LC_ALL", "LC_CTYPE", "SYSTEMROOT", "SystemRoot", "USERPROFILE",
    "__CF_USER_TEXT_ENCODING",
})


def find_codex(executable: str = "codex") -> str | None:
    """Prefer PATH. Only infer an nvm installation when it is unambiguous."""
    found = shutil.which(executable)
    if found or executable != "codex":
        return found
    home = Path.home()
    candidates = [home / ".local/bin/codex", home / ".bun/bin/codex",
                  Path("/opt/homebrew/bin/codex"), Path("/usr/local/bin/codex")]
    candidates.extend(home.glob(".nvm/versions/node/*/bin/codex"))
    runnable = [p for p in candidates if p.is_file() and os.access(p, os.X_OK)]
    if len(runnable) > 1:
        raise ValueError("Multiple Codex installations found; pass --codex explicitly.")
    return str(runnable[0]) if runnable else None


def codex_environment(
    executable: str,
    codex_home: str | None = None,
    extra_names: tuple[str, ...] = (),
    source: Mapping[str, str] | None = None,
) -> dict[str, str]:
    """Do not inherit model API keys, provider overrides, or arbitrary hooks.

    Extra variables are for explicitly declared MCP credentials/configuration.
    Their values must never be written to a manifest. Model API credentials
    cannot be opted back in through that mechanism.
    """
    source = os.environ if source is None else source
    for name in extra_names:
        if (name in BASE_ENV or name in {"NODE_OPTIONS", "NODE_PATH", "LD_PRELOAD",
                "DYLD_INSERT_LIBRARIES", "DYLD_LIBRARY_PATH", "PYTHONPATH", "PYTHONHOME"}
                or name.startswith(("CODEX_", "OPENAI_", "AZURE_OPENAI_"))):
            raise ValueError("MCP env_vars cannot override harness authentication, runtime, or configuration.")
        if name not in source:
            raise ValueError(f"Required MCP environment variable is missing: {name}")
    env = {k: v for k, v in source.items() if k in BASE_ENV or k in extra_names}
    env["PATH"] = str(Path(executable).absolute().parent) + os.pathsep + env.get("PATH", os.defpath)
    home = codex_home or source.get("CODEX_HOME") or str(Path(source.get("HOME", str(Path.home()))) / ".codex")
    env["CODEX_HOME"] = str(Path(home).expanduser().absolute())
    env["NO_COLOR"] = "1"
    return env
