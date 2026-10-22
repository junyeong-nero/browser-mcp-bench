"""No-model Firefox checks for representation-only target views on both tracks."""
import copy
import json
import os
from pathlib import Path
import re
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'tests')]
os.environ['KITSUNE_PROJECT'] = str(ROOT / 'artifacts/vendor/kitsune-v0.3.0')
from test_personal import isolated_kitsune
from kitsune_benchmark.target_view import HEADER, reconstruct_snapshot
from kitsune_benchmark.target_view_session import TargetViewSession
from kitsune_benchmark.target_view_experiment import build_fixture, units


class SpySession(TargetViewSession):
    def __init__(self, settings):
        super().__init__(settings)
        self.agent_native = []
    def native_request(self, method, params=None, **kwargs):
        reply = super().native_request(method, params, **kwargs)
        if kwargs.get('role') == 'agent' and method == 'tools/call':
            self.agent_native.append(copy.deepcopy(reply))
        return reply


def snapshots(value):
    if isinstance(value, dict):
        for key, child in value.items():
            if key == 'snapshot' and isinstance(child, str):
                yield child
            else:
                yield from snapshots(child)
    elif isinstance(value, list):
        for child in value:
            yield from snapshots(child)


def main():
    output = ROOT / 'artifacts/target-view-probes-20261022'
    output.mkdir(exist_ok=True)
    report = []
    for unit in [u for u in units() if u['task'] in {'pb-current-01', 'ui-rowmenu', 'mm-video'}]:
        with tempfile.TemporaryDirectory(prefix='tv-', dir='/tmp') as folder, build_fixture({**unit, 'arm': 'B'}) as fixture:
            fixture.begin('kitsune')
            trial = fixture.trials[fixture.by_target['kitsune']]
            with isolated_kitsune(folder) as upstream:
                session = SpySession({'target': 'kitsune', 'target_view': 'catalog', 'upstream': upstream,
                    'bootstrap_url': trial.url('/start'), 'urls': [trial.url(p) for p in trial.paths],
                    'active_index': trial.active_index, 'evidence_path': folder + '/evidence.json',
                    'origin': fixture.origin, 'diagnostics_path': folder + '/rpc.jsonl'})
                try:
                    session.start()
                    session.request('initialize', {'protocolVersion': '2024-11-05', 'capabilities': {},
                        'clientInfo': {'name': 'target-view-probe', 'version': '1'}})
                    session.send({'jsonrpc': '2.0', 'method': 'notifications/initialized'})
                    session.prepare()
                    before_tabs = session.inventory()
                    reply = session.request('tools/call', {'name': 'browser_snapshot', 'arguments': {'text': True}}, role='agent')
                    assert len(session.agent_native) == 1
                    native = session.agent_native[0]
                    actual = json.loads(reply['result']['content'][0]['text'])
                    original = json.loads(native['result']['content'][0]['text'])
                    originals = list(snapshots(original))
                    formatted = list(snapshots(actual))
                    assert originals and len(originals) == len(formatted)
                    for old, new in zip(originals, formatted):
                        assert reconstruct_snapshot(new) == old
                        assert re.findall(r'\[ref=(\w+)\]', old) == re.findall(r'\[ref=(\w+)\]', reconstruct_snapshot(new))
                    ref = re.search(r'\[ref=(e\d+)\]', originals[0]).group(1)
                    reuse = session.request('tools/call', {'name': 'browser_snapshot', 'arguments': {'ref': ref}}, role='agent')
                    assert not reuse.get('result', {}).get('isError') and 'error' not in reuse
                    assert len(session.agent_native) == 2
                    assert session.inventory() == before_tabs
                    rpc = [json.loads(line) for line in Path(folder + '/rpc.jsonl').read_text().splitlines()]
                    stats = next(x for x in rpc if x['kind'] == 'target_view_delivered')
                    assert stats.get('formatted', 0) > 0
                    if unit['task'] == 'mm-video':
                        assert stats['media'] > 0
                    result = {**unit, 'lossless': True, 'ref_reuse_succeeded': True, 'agent_native_calls': 2,
                              'formatting': stats, 'native': original, 'catalog': actual}
                    (output / (unit['task'] + '.json')).write_text(json.dumps(result, ensure_ascii=False, indent=2))
                    report.append({**unit, 'lossless': True, 'ref_reuse_succeeded': True,
                                   'interactions': stats['interactions'], 'media': stats['media'],
                                   'native_bytes': stats['native_text_bytes'], 'catalog_bytes': stats['delivered_text_bytes']})
                finally:
                    session.close()
    (output / 'summary.json').write_text(json.dumps(report, indent=2))
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
