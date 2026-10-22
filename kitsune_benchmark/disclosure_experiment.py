"""Bounded 2x2 exploratory experiment. Plans by default; --execute consumes API credit."""
from __future__ import annotations

import argparse
from dataclasses import replace
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

from .adapter import write_json
from .personal import PersonalServer, config, selected_tasks, pair_complete, UI_TOOLS
from .personal_session import NativeSession
from .smoke import ROOT, run_pair, source_revision

TASKS = ("pb-current-01", "pb-current-02", "pb-tabs-01", "pb-research-01", "pb-account-01", "pb-handoff-01")
ARMS = {"A": ("native", False), "B": ("rich", False), "C": ("native", True), "D": ("rich", True)}
ORDERS = ("ABDC", "BCAD", "CDBA", "DACB")
PIN = "99a90d22c83d6e931814b3c3dadd96c08c633820"
EXPECT_GUIDANCE = """
액션의 expect는 실제로 확인할 수 있는 후속 조건이 있을 때 사용하세요.
입력값 확인은 {"selector":"대상 CSS","value":"기대값"}처럼 대상을 지정합니다.
{"value":"기대값"}만 단독으로 지정하지 마세요. selector는 실제 페이지에서 확인한 것을 사용하세요.
같은 URL에서 저장하는 동작에 url_changed를 기대하지 마세요. 새 탭 열기는 new_tab 조건과 구분하세요.
액션 응답이 이미 충분히 완료를 확인해 주면 불필요한 expect나 중복 확인을 추가하지 마세요.
후속 조건 실패라도 dispatched=true이면 쓰기가 수행됐을 수 있습니다. 같은 쓰기를 재실행하기 전에
반환 상태 또는 페이지를 확인하세요. 필요한 결과 확인과 원래 안전 요구사항은 생략하지 마세요.
""".strip()


def schedule(repeats=3):
    return [{"task": task, "repeat": rep, "arm": arm, "position": pos,
             "block": f"{task}/r{rep}"}
            for rep in range(repeats) for i, task in enumerate(TASKS)
            for pos, arm in enumerate(ORDERS[(i + rep) % 4])]


class ExperimentFixture(PersonalServer):
    def __init__(self, task, variant, arm):
        super().__init__(task, variant)
        self.arm = arm
        self.policy, self.guidance = ARMS[arm]

    def begin(self, target):
        task = super().begin(target)
        return replace(task, prompt=task.prompt + "\n" + EXPECT_GUIDANCE) if self.guidance else task

    def prepare_server(self, target, server, task, pair_dir):
        prepared = super().prepare_server(target, server, task, pair_dir)
        path = Path(prepared.args[-1])
        settings = json.loads(path.read_text())
        settings["disclosure_policy"] = self.policy
        NativeSession.write_private_json(path, settings)
        return replace(prepared, args=(str(ROOT / "kitsune_benchmark/disclosure_session.py"), str(path)))


def budget_allows(spent, budget, per_run):
    return spent + per_run <= budget


def run(output: Path, project: Path, budget=2.0, execute=False):
    if budget <= 0:
        raise ValueError("Budget must be positive")
    spec = config()
    per_run = spec["claude_code"]["max_budget_usd_per_run"]
    plan = {"design": "2x2 disclosure x expect guidance", "schedule": schedule(),
            "harness": "claude-api", "kitsune_preset": "lean", "variant": 0,
            "budget_usd": budget, "max_budget_usd_per_run": per_run,
            "kitsune_pin": PIN, "guidance": EXPECT_GUIDANCE,
            "guidance_sha256": hashlib.sha256(EXPECT_GUIDANCE.encode()).hexdigest(),
            "implementation_sha256": {name: hashlib.sha256((ROOT / "kitsune_benchmark" / name).read_bytes()).hexdigest()
                                      for name in ("disclosure_experiment.py", "disclosure_session.py")}}
    if not execute:
        return plan
    if not budget_allows(0, budget, per_run):
        raise ValueError("Budget below one run cap")
    output.mkdir(parents=True, exist_ok=False)
    write_json(output / "plan.json", plan)
    source = source_revision(project)
    if source != {"revision": PIN, "dirty": False}:
        raise ValueError("Requires clean pinned Kitsune v0.3.0")
    tasks = {t["id"]: t for t in selected_tasks(list(TASKS))}
    state = {"state": "running", "runs": [], "estimated_cost_usd": 0.0,
             "started": datetime.now(timezone.utc).isoformat(), "stopped_reason": None}
    def save():
        NativeSession.write_private_json(output / "summary.json", state)
    save()
    for item in plan["schedule"]:
        if not budget_allows(state["estimated_cost_usd"], budget, per_run):
            state["stopped_reason"] = "budget_reserve"
            break
        if source_revision(project) != source:
            state["stopped_reason"] = "kitsune_revision_changed"
            break
        if any(hashlib.sha256((ROOT / "kitsune_benchmark" / name).read_bytes()).hexdigest() != digest
               for name, digest in plan["implementation_sha256"].items()):
            state["stopped_reason"] = "experiment_code_changed"
            break
        state["active"] = item
        save()
        experiment = {**spec, "selected_task": tasks[item["task"]], "variant": 0,
                      "disclosure_experiment": item, "disclosure_policy": ARMS[item["arm"]][0],
                      "expect_guidance": ARMS[item["arm"]][1],
                      "guidance_sha256": plan["guidance_sha256"],
                      "catalog_sha256": hashlib.sha256((ROOT / spec["catalog"]).read_bytes()).hexdigest()}
        try:
            with ExperimentFixture(tasks[item["task"]], 0, item["arm"]) as fixture:
                pair = run_pair(execute=True, kitsune_project=str(project),
                    experiment_spec=experiment, artifact_scope="disclosure", task_for_target=fixture.begin,
                    prepare_server=fixture.prepare_server, evaluate=fixture.evaluate, enabled_tools=UI_TOOLS,
                    harness="claude-api", executable="claude", kitsune_preset="lean", targets=("kitsune",))
        except Exception as error:
            state["stopped_reason"] = "execution_exception"
            state["exception_type"] = type(error).__name__
            state["state"] = "stopped"
            save()
            raise
        result = pair["results"].get("kitsune", {})
        cost = result.get("list_price_cost_usd")
        state["estimated_cost_usd"] += cost if isinstance(cost, (int, float)) else per_run
        entry = {**item, "pair": pair, "kitsune_source_after": source_revision(project)}
        state["runs"].append(entry)
        save()
        if not pair_complete(pair, ("kitsune",)):
            state["stopped_reason"] = "unscorable_run"
            break
        if entry["kitsune_source_after"] != source:
            state["stopped_reason"] = "kitsune_revision_changed"
            break
    state.pop("active", None)
    state["state"] = "completed" if state["stopped_reason"] is None else "stopped"
    state["ended"] = datetime.now(timezone.utc).isoformat()
    save()
    return {"state": state["state"], "runs": len(state["runs"]),
            "estimated_cost_usd": state["estimated_cost_usd"], "stopped_reason": state["stopped_reason"],
            "summary_path": str(output / "summary.json")}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--output", type=Path, default=ROOT / "artifacts/disclosure-experiment-20261022")
    parser.add_argument("--kitsune-project", type=Path, default=ROOT / "artifacts/vendor/kitsune-v0.3.0")
    parser.add_argument("--budget-usd", type=float, default=2.0)
    args = parser.parse_args()
    result = run(args.output.resolve(), args.kitsune_project.resolve(), args.budget_usd, args.execute)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result.get("state", "completed") == "completed" else 3


if __name__ == "__main__":
    sys.exit(main())
