"""Plan or run the representation-only target-view A/B (60 runs, bounded API spend)."""
from __future__ import annotations

import argparse
from dataclasses import replace
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

from .adapter import write_json
from .personal import PersonalServer, config as personal_config, selected_tasks, pair_complete, UI_TOOLS
from .gallery import GalleryServer, config as gallery_config, select as gallery_tasks
from .personal_session import NativeSession
from .smoke import ROOT, run_pair, source_revision

PIN = "99a90d22c83d6e931814b3c3dadd96c08c633820"
PERSONAL = ("pb-current-01", "pb-current-02", "pb-tabs-01", "pb-research-01", "pb-account-01", "pb-handoff-01")
GALLERY = (("ui-select", "crowded"), ("ui-rowmenu", "crowded"), ("mm-chart", "isolated"), ("mm-video", "isolated"))
FILES = ("target_view.py", "target_view_session.py", "target_view_experiment.py")


def units():
    return ([{"task": t, "track": "personal", "layout": None, "unit": "personal/" + t} for t in PERSONAL]
            + [{"task": t, "track": "gallery", "layout": layout, "unit": f"gallery/{t}/{layout}"} for t, layout in GALLERY])


def schedule():
    return [{**unit, "repeat": rep, "arm": arm, "position": pos, "block": f"{unit['unit']}/r{rep}"}
            for rep in range(3) for i, unit in enumerate(units())
            for pos, arm in enumerate("AB" if (i + rep) % 2 == 0 else "BA")]


class ViewFixtureMixin:
    def __init__(self, *args, view, **kwargs):
        super().__init__(*args, **kwargs)
        self.view = view

    def prepare_server(self, target, server, task, pair_dir):
        prepared = super().prepare_server(target, server, task, pair_dir)
        path = Path(prepared.args[-1])
        settings = json.loads(path.read_text())
        settings["target_view"] = self.view
        NativeSession.write_private_json(path, settings)
        return replace(prepared, args=(str(ROOT / "kitsune_benchmark/target_view_session.py"), str(path)))


class PersonalView(ViewFixtureMixin, PersonalServer):
    pass


class GalleryView(ViewFixtureMixin, GalleryServer):
    pass


def build_fixture(item):
    view = "native" if item["arm"] == "A" else "catalog"
    if item["track"] == "personal":
        return PersonalView(selected_tasks([item["task"]])[0], 0, view=view)
    return GalleryView(gallery_tasks([item["task"]])[0], 0, item["layout"], view=view)


def code_hashes():
    return {name: hashlib.sha256((ROOT / "kitsune_benchmark" / name).read_bytes()).hexdigest() for name in FILES}


def run(output: Path, project: Path, budget=2.0, execute=False):
    import math
    if not math.isfinite(budget) or budget <= 0:
        raise ValueError("Budget must be finite and positive")
    plan = {"design": "representation-only native vs target/action catalog", "schedule": schedule(),
            "harness": "claude-api", "kitsune_preset": "lean", "variant": 0, "budget_usd": budget,
            "kitsune_pin": PIN, "implementation_sha256": code_hashes(),
            "personal_config": personal_config(), "gallery_config": gallery_config()}
    if not execute:
        return plan
    if budget < max(spec["claude_code"]["max_budget_usd_per_run"] for spec in (personal_config(), gallery_config())):
        raise ValueError("Budget below one run cap")
    source = source_revision(project)
    if source != {"revision": PIN, "dirty": False}:
        raise ValueError("Requires clean pinned Kitsune v0.3.0")
    output.mkdir(parents=True, exist_ok=False)
    write_json(output / "plan.json", plan)
    state = {"state": "running", "runs": [], "estimated_cost_usd": 0.0,
             "started": datetime.now(timezone.utc).isoformat(), "stopped_reason": None}
    def save():
        NativeSession.write_private_json(output / "summary.json", state)
    save()
    for item in plan["schedule"]:
        spec = personal_config() if item["track"] == "personal" else gallery_config()
        cap = spec["claude_code"]["max_budget_usd_per_run"]
        if state["estimated_cost_usd"] + cap > budget:
            state["stopped_reason"] = "budget_reserve"
            break
        if source_revision(project) != source or code_hashes() != plan["implementation_sha256"]:
            state["stopped_reason"] = "source_changed"
            break
        state["active"] = item
        save()
        experiment = {**spec, "target_view_experiment": item, "variant": 0,
                      "layout": item["layout"], "target_view": "native" if item["arm"] == "A" else "catalog",
                      "implementation_sha256": plan["implementation_sha256"]}
        try:
            with build_fixture(item) as fixture:
                pair = run_pair(execute=True, kitsune_project=str(project), executable="claude",
                    experiment_spec=experiment, artifact_scope="target-view", task_for_target=fixture.begin,
                    prepare_server=fixture.prepare_server, evaluate=fixture.evaluate, enabled_tools=UI_TOOLS,
                    harness="claude-api", kitsune_preset="lean", targets=("kitsune",))
        except Exception as error:
            state.update(state="stopped", stopped_reason="execution_exception", exception_type=type(error).__name__)
            save()
            raise
        cost = pair["results"].get("kitsune", {}).get("list_price_cost_usd")
        state["estimated_cost_usd"] += cost if isinstance(cost, (int, float)) else cap
        state["runs"].append({**item, "pair": pair, "kitsune_source_after": source_revision(project)})
        save()
        if not pair_complete(pair, ("kitsune",)):
            state["stopped_reason"] = "unscorable_run"
            break
        if source_revision(project) != source or code_hashes() != plan["implementation_sha256"]:
            state["stopped_reason"] = "source_changed"
            break
    state.pop("active", None)
    state["state"] = "completed" if state["stopped_reason"] is None else "stopped"
    state["ended"] = datetime.now(timezone.utc).isoformat()
    save()
    return {"state": state["state"], "runs": len(state["runs"]), "estimated_cost_usd": state["estimated_cost_usd"],
            "stopped_reason": state["stopped_reason"], "summary_path": str(output / "summary.json")}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--output", type=Path, default=ROOT / "artifacts/target-view-experiment-20261022")
    parser.add_argument("--kitsune-project", type=Path, default=ROOT / "artifacts/vendor/kitsune-v0.3.0")
    parser.add_argument("--budget-usd", type=float, default=2.0)
    args = parser.parse_args()
    result = run(args.output.resolve(), args.kitsune_project.resolve(), args.budget_usd, args.execute)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result.get("state", "completed") == "completed" else 3


if __name__ == "__main__":
    raise SystemExit(main())
