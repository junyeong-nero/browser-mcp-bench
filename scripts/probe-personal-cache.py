#!/usr/bin/env python3
"""Development-only isolated Kitsune cache probe. NO Codex/model execution.

Uses the same private-browser setup as the native fixture integration tests.
Changes cache TTL only on the owned temporary bridge; never edits Kitsune source
or connects a normal profile. This is an intervention, not a benchmark score.
"""
from __future__ import annotations

import argparse
from contextlib import redirect_stderr
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
import tempfile
import time
from urllib.request import ProxyHandler, Request, build_opener

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))
from test_personal import isolated_kitsune
from browser_mcp_bench.adapter import write_json
from browser_mcp_bench.personal import PersonalServer, selected_tasks
from browser_mcp_bench.personal_session import NativeSession


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repeats", type=int, default=3)
    args = parser.parse_args()
    if not 1 <= args.repeats <= 5:
        parser.error("Choose 1..5 repetitions per condition.")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output = ROOT / "artifacts/personal" / ("cache-probe-" + stamp)
    output.mkdir(mode=0o700, parents=True, exist_ok=False)
    measurements = []
    task = selected_tasks(["pb-current-01"])[0]
    for repeat in range(args.repeats):
        for ttl in (5, 0):
            tag = f"r{repeat + 1}-ttl{ttl}"
            fd = os.open(output / (tag + "-stderr.log"), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "w") as log, redirect_stderr(log), tempfile.TemporaryDirectory(prefix="pb-", dir="/tmp") as folder, PersonalServer(task, 0) as fixture:
                fixture.begin("kitsune")
                trial = fixture.trials[fixture.by_target["kitsune"]]
                with isolated_kitsune(folder) as upstream:
                    # Only this helper's newly owned private bridge is modified.
                    request = Request(f'http://127.0.0.1:{os.environ["KITSUNE_HTTP_PORT"]}/api/cache',
                        data=json.dumps({"action": "ttl", "seconds": ttl}).encode(),
                        headers={"Content-Type": "application/json", "Authorization": "Bearer " + os.environ["KITSUNE_TOKEN"]})
                    with build_opener(ProxyHandler({})).open(request, timeout=3) as response:
                        if json.load(response).get("ttl") != ttl:
                            raise ValueError("Private cache TTL was not set.")
                    session = NativeSession({"target": "kitsune", "upstream": upstream,
                        "bootstrap_url": trial.url("/start"), "urls": [trial.url(p) for p in trial.paths],
                        "active_index": 0, "origin": fixture.origin,
                        "evidence_path": str(output / (tag + "-evidence.json")),
                        "diagnostics_path": str(output / (tag + "-rpc.jsonl"))})
                    try:
                        session.start()
                        session.request("initialize", {"protocolVersion": "2024-11-05", "capabilities": {},
                            "clientInfo": {"name": "cache-probe-no-model", "version": "1"}})
                        session.send({"jsonrpc": "2.0", "method": "notifications/initialized"})
                        started = time.monotonic()
                        session.prepare()
                        elapsed = time.monotonic() - started
                        setup_calls = session.evidence["harness_calls"]
                        # Check whether observation supplies task facts as well as UI refs.
                        snapshot = session.tool("browser_snapshot", {})
                        text = session.tool("browser_page_text", {})
                        item = {"repeat": repeat + 1, "ttl": ttl, "setup_sec": elapsed,
                            "setup_calls": setup_calls, "setup_verified": session.evidence["setup_complete"],
                            "snapshot_contains_deadline": trial.expected["answer"] in json.dumps(snapshot, ensure_ascii=False),
                            "page_text_contains_deadline": trial.expected["answer"] in json.dumps(text, ensure_ascii=False)}
                        measurements.append(item)
                        write_json(output / (tag + "-observations.json"), {"snapshot": snapshot, "page_text": text})
                    finally:
                        session.close()
    result = {"model_invoked": False, "browser": "isolated private Firefox/Kitsune", "task": task["id"],
              "intervention": "temporary bridge cache TTL 5 vs 0; no source or benchmark changes", "measurements": measurements}
    write_json(output / "results.json", result)
    print(json.dumps({"results_path": str(output / "results.json"), **result}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
