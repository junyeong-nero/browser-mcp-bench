"""No-model v0.3.0 video screenshot ref-vs-selector probe; disposable Firefox."""
import base64
import io
import json
import os
from pathlib import Path
import re
import sys
import tempfile

from PIL import Image
ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'tests')]
os.environ['KITSUNE_PROJECT'] = str(ROOT / 'artifacts/vendor/kitsune-v0.3.0')
from test_personal import isolated_kitsune
from kitsune_benchmark.gallery import GalleryServer, select
from kitsune_benchmark.personal_session import NativeSession


def summarize(result):
    info = {'isError': result.get('isError', False)}
    for item in result.get('content', []):
        if item.get('type') == 'image':
            with Image.open(io.BytesIO(base64.b64decode(item['data']))) as image:
                info['image_dimensions'] = list(image.size)
        elif item.get('type') == 'text':
            try:
                data = json.loads(item['text'])
                if isinstance(data, dict) and data.get('error'):
                    info['error'] = data['error']
            except ValueError:
                pass
    return info


def main():
    with tempfile.TemporaryDirectory(prefix='media-ref-', dir='/tmp') as folder, GalleryServer(select(['mm-video'])[0], 0, 'isolated') as fixture:
        fixture.begin('kitsune')
        trial = fixture.trials[fixture.by_target['kitsune']]
        with isolated_kitsune(folder) as upstream:
            session = NativeSession({'target': 'kitsune', 'upstream': upstream,
                'bootstrap_url': trial.url('/start'), 'urls': [trial.url(p) for p in trial.paths],
                'active_index': trial.active_index, 'evidence_path': folder + '/evidence.json', 'origin': fixture.origin})
            try:
                session.start()
                session.request('initialize', {'protocolVersion': '2024-11-05', 'capabilities': {},
                    'clientInfo': {'name': 'media-ref-probe', 'version': '1'}})
                session.send({'jsonrpc': '2.0', 'method': 'notifications/initialized'})
                session.prepare()
                before = session.inventory()
                tab_id = next(t['id'] for t in before if t['active'])
                snapshot = session.tool('browser_snapshot', {'tab_id': tab_id, 'text': True})
                payload = json.loads(next(c['text'] for c in snapshot['content'] if c['type'] == 'text'))
                ref = re.search(r'- video .*?\[ref=(e\d+)\]', payload['snapshot']).group(1)
                by_ref = session.request('tools/call', {'name': 'browser_screenshot', 'arguments': {'tab_id': tab_id, 'ref': ref}})['result']
                by_selector = session.request('tools/call', {'name': 'browser_screenshot', 'arguments': {'tab_id': tab_id, 'selector': 'video'}})['result']
                result = {'video_ref': ref, 'ref_capture': summarize(by_ref), 'selector_capture': summarize(by_selector),
                          'tabs_unchanged': before == session.inventory()}
                print(json.dumps(result, indent=2))
            finally:
                session.close()


if __name__ == '__main__':
    main()
