"""Offline image/asset trace inspection for the target-view experiment."""
import base64
import collections
import io
import json
from pathlib import Path
import sys

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from kitsune_benchmark.target_view import HEADER, reconstruct_snapshot, ROLE, MEDIA


def payloads(content):
    blocks = content if isinstance(content, list) else [{'type': 'text', 'text': content}]
    for block in blocks:
        if block.get('type') != 'text':
            continue
        try:
            yield json.loads(block.get('text', ''))
        except (ValueError, TypeError):
            pass


def snapshots(value):
    if isinstance(value, dict):
        for key, child in value.items():
            if key == 'snapshot' and isinstance(child, str):
                yield reconstruct_snapshot(child) if child.startswith(HEADER + '\n') else child
            else:
                yield from snapshots(child)
    elif isinstance(value, list):
        for child in value:
            yield from snapshots(child)


def main():
    folder = ROOT / 'artifacts/target-view-experiment-20261022'
    summary = json.loads((folder / 'summary.json').read_text())
    result = {}
    for task in ('mm-chart', 'mm-video'):
        result[task] = {}
        for arm in 'AB':
            counts = collections.Counter()
            dimensions = collections.Counter()
            args = collections.Counter()
            image_pixels = 0
            asset_roles = collections.Counter()
            for entry in summary['runs']:
                if entry['task'] != task or entry['arm'] != arm:
                    continue
                path = Path(entry['pair']['results']['kitsune']['run_dir']) / 'events.jsonl'
                for line in path.read_text().splitlines():
                    content = json.loads(line).get('message', {}).get('content', [])
                    if not isinstance(content, list):
                        continue
                    for item in content:
                        if item.get('type') == 'tool_use' and item['name'].endswith('browser_screenshot'):
                            selector = item['input'].get('selector')
                            kind = 'selector:' + selector if selector else 'ref' if item['input'].get('ref') else 'page'
                            args[kind] += 1
                        if item.get('type') != 'tool_result':
                            continue
                        for payload in payloads(item.get('content', [])):
                            for snapshot in snapshots(payload):
                                counts['snapshot_strings'] += 1
                                for line in snapshot.splitlines():
                                    match = ROLE.match(line)
                                    if match and match[2] in MEDIA:
                                        asset_roles[match[2]] += 1
                                counts['omission_markers'] += 'more similar items' in snapshot
                        if not isinstance(item.get('content'), list):
                            continue
                        for block in item['content']:
                            if block.get('type') != 'image':
                                continue
                            data = base64.b64decode(block['source']['data'])
                            with Image.open(io.BytesIO(data)) as image:
                                width, height = image.size
                            dimensions[f'{width}x{height}'] += 1
                            image_pixels += width * height
                            counts['images'] += 1
                            counts['image_bytes'] += len(data)
            result[task][arm] = {'counts': dict(counts), 'asset_roles_in_snapshots': dict(asset_roles),
                                'screenshot_requests': dict(args), 'image_dimensions': dict(dimensions),
                                'total_image_pixels': image_pixels}
    (folder / 'media-analysis.json').write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
