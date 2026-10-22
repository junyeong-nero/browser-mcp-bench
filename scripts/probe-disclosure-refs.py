"""No-model causal probe for ref invalidation by the rich page_text supplement."""
import json
import os
from pathlib import Path
import re
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "tests")]
os.environ["KITSUNE_PROJECT"] = str(ROOT / "artifacts/vendor/kitsune-v0.3.0")
from test_personal import isolated_kitsune
from kitsune_benchmark.personal import PersonalServer, selected_tasks
from kitsune_benchmark.disclosure_session import DisclosureSession


def probe(policy):
    task = selected_tasks(["pb-current-01"])[0]
    with tempfile.TemporaryDirectory(prefix="disc-ref-", dir="/tmp") as folder, PersonalServer(task, 0) as fixture:
        fixture.begin("kitsune")
        trial = fixture.trials[fixture.by_target["kitsune"]]
        with isolated_kitsune(folder) as upstream:
            session = DisclosureSession({"target": "kitsune", "disclosure_policy": policy, "upstream": upstream,
                "bootstrap_url": trial.url("/start"), "urls": [trial.url(p) for p in trial.paths],
                "active_index": trial.active_index, "evidence_path": folder + "/evidence.json", "origin": fixture.origin})
            try:
                session.start()
                session.request("initialize", {"protocolVersion": "2024-11-05", "capabilities": {},
                    "clientInfo": {"name": "disclosure-ref-probe", "version": "1"}})
                session.send({"jsonrpc": "2.0", "method": "notifications/initialized"})
                session.prepare()
                initial_tabs = session.inventory()
                before = session.tool("browser_snapshot", {})
                text = "\n".join(c.get("text", "") for c in before.get("content", []))
                ref = re.search(r"\[ref=(e\d+)\]", text).group(1)
                session.request("tools/call", {"name": "browser_page_text", "arguments": {}}, role="agent")
                after = session.request("tools/call", {"name": "browser_snapshot", "arguments": {"ref": ref}}, role="agent")
                return {"policy": policy, "old_ref": ref, "reuse_result": after.get("result"),
                        "tabs_unchanged": initial_tabs == session.inventory()}
            finally:
                session.close()


if __name__ == "__main__":
    results = [probe(policy) for policy in ("native", "rich")]
    assert not results[0]["reuse_result"].get("isError")
    assert results[1]["reuse_result"].get("isError")
    assert all(r["tabs_unchanged"] for r in results)
    print(json.dumps(results, ensure_ascii=False, indent=2))
