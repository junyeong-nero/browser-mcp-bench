"""Two parallel model workers, one-shot targeted A/B, hard bounded execution window."""
from __future__ import annotations

import argparse
import copy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

import psutil

from .adapter import write_json
from .personal import config as personal_config, pair_complete, UI_TOOLS
from .gallery import config as gallery_config
from .personal_session import NativeSession
from .smoke import ROOT, run_pair, source_revision
from .target_view_experiment import PIN, build_fixture, units

MODELS = {"sonnet": "claude-sonnet-5-5", "opus": "claude-opus-5-5"}
SELECTED = ("pb-research-01", "ui-rowmenu", "mm-chart", "mm-video")
FILES = ("target_view.py", "target_view_session.py", "target_view_experiment.py", "target_model_experiment.py")


def hashes():
    return {name: hashlib.sha256((ROOT / 'kitsune_benchmark' / name).read_bytes()).hexdigest() for name in FILES}


def schedule(model):
    selected = {u['task']: u for u in units()}
    offset = list(MODELS).index(model)
    return [{**selected[task], 'repeat': 0, 'arm': arm, 'position': pos,
             'block': selected[task]['unit'] + '/r0'}
            for i, task in enumerate(SELECTED)
            for pos, arm in enumerate('AB' if (i + offset) % 2 == 0 else 'BA')]


def spec_for(item, model):
    spec = copy.deepcopy(personal_config() if item['track'] == 'personal' else gallery_config())
    spec['claude_code']['model'] = MODELS[model]
    spec['claude_code']['max_budget_usd_per_run'] = .5
    spec['timeout_sec'] = 120
    spec['target_model_experiment'] = {**item, 'model': MODELS[model]}
    spec['variant'] = 0
    spec['layout'] = item['layout']
    spec['target_view'] = 'native' if item['arm'] == 'A' else 'catalog'
    return spec


def worker(output, project, model, deadline):
    plan = json.loads((output / 'plan.json').read_text())
    folder = output / model
    folder.mkdir(exist_ok=False)
    source = {'revision': PIN, 'dirty': False}
    state = {'state': 'running', 'model': MODELS[model], 'runs': [], 'estimated_cost_usd': 0.,
             'stopped_reason': None, 'started': datetime.now(timezone.utc).isoformat()}
    def save():
        NativeSession.write_private_json(folder / 'summary.json', state)
    save()
    for item in schedule(model):
        if time.time() + 180 > deadline:
            state['stopped_reason'] = 'deadline_reserve'
            break
        if state['estimated_cost_usd'] + .5 > 4:
            state['stopped_reason'] = 'budget_reserve'
            break
        if source_revision(project) != source or hashes() != plan['implementation_sha256']:
            state['stopped_reason'] = 'source_changed'
            break
        state['active'] = item
        save()
        try:
            with build_fixture(item) as fixture:
                pair = run_pair(execute=True, kitsune_project=str(project), executable='claude',
                    experiment_spec=spec_for(item, model), artifact_scope='target-models-' + model,
                    task_for_target=fixture.begin, prepare_server=fixture.prepare_server,
                    evaluate=fixture.evaluate, enabled_tools=UI_TOOLS, harness='claude-api',
                    kitsune_preset='lean', targets=('kitsune',))
        except Exception as error:
            state.update(state='stopped', stopped_reason='execution_exception', exception_type=type(error).__name__)
            save()
            raise
        result = pair['results'].get('kitsune', {})
        cost = result.get('list_price_cost_usd')
        state['estimated_cost_usd'] += cost if isinstance(cost, (int, float)) else .5
        state['runs'].append({**item, 'pair': pair, 'kitsune_source_after': source_revision(project)})
        save()
        if not pair_complete(pair, ('kitsune',)):
            state['stopped_reason'] = 'unscorable_run'
            break
        if source_revision(project) != source or hashes() != plan['implementation_sha256']:
            state['stopped_reason'] = 'source_changed'
            break
    state.pop('active', None)
    state['state'] = 'completed' if state['stopped_reason'] is None else 'stopped'
    state['ended'] = datetime.now(timezone.utc).isoformat()
    save()
    return 0 if state['state'] == 'completed' else 3


def terminate_owned_tree(pid):
    """Terminate only this worker and its snapshotted descendants, including new sessions."""
    try:
        root = psutil.Process(pid)
        processes = root.children(recursive=True) + [root]
    except psutil.NoSuchProcess:
        return
    for process in reversed(processes):
        try:
            process.terminate()
        except psutil.NoSuchProcess:
            pass
    _, alive = psutil.wait_procs(processes, timeout=5)
    for process in alive:
        try:
            process.kill()
        except psutil.NoSuchProcess:
            pass
    psutil.wait_procs(alive, timeout=5)


def coordinate(output, project, execute=False):
    plan = {'models': MODELS, 'schedules': {m: schedule(m) for m in MODELS},
            'implementation_sha256': hashes(), 'kitsune_pin': PIN, 'execution_window_sec': 1080,
            'agent_timeout_sec': 120, 'budget_usd_per_model': 4, 'total_budget_usd': 8,
            'per_run_cap_usd': .5, 'harness': 'claude-api', 'effort': 'medium'}
    if not execute:
        return plan
    if source_revision(project) != {'revision': PIN, 'dirty': False}:
        raise ValueError('Requires clean pinned Kitsune v0.3.0')
    output.mkdir(parents=True, exist_ok=False)
    write_json(output / 'plan.json', plan)
    started = time.time()
    deadline = started + plan['execution_window_sec']
    handles, processes = [], {}
    status = {'state': 'running', 'started': datetime.now(timezone.utc).isoformat(), 'workers': {}}
    def save():
        NativeSession.write_private_json(output / 'status.json', status)
    save()
    try:
        for model in MODELS:
            stdout = (output / (model + '.stdout.log')).open('w')
            stderr = (output / (model + '.stderr.log')).open('w')
            handles.extend([stdout, stderr])
            process = subprocess.Popen([sys.executable, '-m', 'kitsune_benchmark.target_model_experiment',
                '--worker', model, '--output', str(output), '--kitsune-project', str(project),
                '--deadline', str(deadline)], cwd=ROOT, stdout=stdout, stderr=stderr,
                stdin=subprocess.DEVNULL, start_new_session=True)
            processes[model] = process
            status['workers'][model] = {'pid': process.pid, 'state': 'running'}
        save()
        while any(p.poll() is None for p in processes.values()) and time.time() < deadline:
            for model, process in processes.items():
                code = process.poll()
                if code is not None:
                    status['workers'][model].update(state='completed' if code == 0 else 'stopped', returncode=code)
            save()
            time.sleep(2)
        for model, process in processes.items():
            if process.poll() is None:
                terminate_owned_tree(process.pid)
                status['workers'][model].update(state='deadline', returncode=process.wait())
                summary_path = output / model / 'summary.json'
                if summary_path.exists():
                    summary = json.loads(summary_path.read_text())
                    summary.update(state='stopped', stopped_reason='coordinator_deadline')
                    NativeSession.write_private_json(summary_path, summary)
            else:
                status['workers'][model].update(state='completed' if process.returncode == 0 else 'stopped', returncode=process.returncode)
        status['state'] = 'completed' if all(w['state'] == 'completed' for w in status['workers'].values()) else 'partial'
        status['elapsed_sec'] = time.time() - started
        status['ended'] = datetime.now(timezone.utc).isoformat()
        save()
        return status
    finally:
        for process in processes.values():
            if process.poll() is None:
                terminate_owned_tree(process.pid)
        for handle in handles:
            handle.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--worker', choices=MODELS)
    parser.add_argument('--deadline', type=float)
    parser.add_argument('--output', type=Path, default=ROOT / 'artifacts/target-models-20261022')
    parser.add_argument('--kitsune-project', type=Path, default=ROOT / 'artifacts/vendor/kitsune-v0.3.0')
    args = parser.parse_args()
    if args.worker:
        if args.deadline is None:
            parser.error('--worker requires --deadline')
        return worker(args.output.resolve(), args.kitsune_project.resolve(), args.worker, args.deadline)
    result = coordinate(args.output.resolve(), args.kitsune_project.resolve(), args.execute)
    print(json.dumps(result, indent=2))
    return 0 if result.get('state', 'completed') == 'completed' else 3


if __name__ == '__main__':
    raise SystemExit(main())
