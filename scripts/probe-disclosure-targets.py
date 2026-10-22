"""No-model Firefox probe: computed text inputs vs explicit type attributes.

Uses existing disposable fixture/bootstrap helpers. No everyday browser/profile.
"""
import json
import os
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "tests")]
os.environ["KITSUNE_PROJECT"] = str(ROOT / "artifacts/vendor/kitsune-v0.3.0")
from test_personal import isolated_kitsune
from kitsune_benchmark.personal import PersonalServer, selected_tasks
from kitsune_benchmark.personal_session import NativeSession


def main():
    task = selected_tasks(["pb-current-02"])[0]
    with tempfile.TemporaryDirectory(prefix="disc-probe-", dir="/tmp") as folder, PersonalServer(task, 0) as fixture:
        fixture.begin("kitsune")
        trial = fixture.trials[fixture.by_target["kitsune"]]
        with isolated_kitsune(folder) as upstream:
            session = NativeSession({"target": "kitsune", "upstream": upstream,
                "bootstrap_url": trial.url("/start"), "urls": [trial.url(p) for p in trial.paths],
                "active_index": trial.active_index, "evidence_path": folder + "/evidence.json", "origin": fixture.origin})
            try:
                session.start()
                session.request("initialize", {"protocolVersion": "2024-11-05", "capabilities": {},
                    "clientInfo": {"name": "disclosure-target-probe", "version": "1"}})
                session.send({"jsonrpc": "2.0", "method": "notifications/initialized"})
                session.prepare()
                tab = next(t for t in session.inventory() if t["url"] == trial.url("/memo"))
                results = {}
                for selector in ('form input[type="text"]', 'form input', 'input[name="신청 자격"]'):
                    results[selector] = session.request("tools/call", {"name": "browser_snapshot",
                        "arguments": {"tab_id": tab["id"], "selector": selector}})["result"]
                results["forms"] = session.tool("browser_forms", {"tab_id": tab["id"]})
                print(json.dumps(results, ensure_ascii=False, indent=2))
            finally:
                session.close()


if __name__ == "__main__":
    main()
