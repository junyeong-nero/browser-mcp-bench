"""One-shot stronger-model follow-up analysis; no confidence intervals from four pairs."""
from __future__ import annotations

import argparse
import base64
import collections
import io
import json
from pathlib import Path

from PIL import Image
from .target_view_analysis import metrics, aggregate
from .target_model_experiment import SELECTED


def media_and_errors(run_dir):
    calls = {}
    counts = collections.Counter()
    dimensions = collections.Counter()
    scopes = collections.Counter()
    errors = collections.Counter()
    actual_models = set()
    pixels = 0
    for line in (Path(run_dir) / 'events.jsonl').read_text().splitlines():
        event = json.loads(line)
        message = event.get('message', {})
        if event.get('type') == 'assistant' and message.get('model'):
            actual_models.add(message['model'])
        content = message.get('content', [])
        if not isinstance(content, list):
            continue
        for item in content:
            if item.get('type') == 'tool_use':
                if item['id'] in calls:
                    continue
                calls[item['id']] = item
                if item['name'].endswith('browser_screenshot'):
                    args = item['input']
                    scopes['selector:' + args['selector'] if args.get('selector') else 'ref' if args.get('ref') else 'page'] += 1
            if item.get('type') != 'tool_result':
                continue
            raw = item.get('content', [])
            blocks = raw if isinstance(raw, list) else [{'type': 'text', 'text': raw}]
            if item.get('is_error'):
                text = '\n'.join(b.get('text', '') for b in blocks if b.get('type') == 'text')
                category = 'outcome_timeout' if 'Expected outcome not observed' in text else 'stale_ref' if 'stale ref' in text else 'target_missing' if any(s in text for s in ('No element matches', 'Element not found', 'Selector not found')) else 'expect_validation' if 'expect' in text else 'other'
                errors[category] += 1
            for block in blocks:
                if block.get('type') != 'image':
                    continue
                data = base64.b64decode(block['source']['data'])
                with Image.open(io.BytesIO(data)) as image:
                    width, height = image.size
                dimensions[f'{width}x{height}'] += 1
                pixels += width * height
                counts['images'] += 1
                counts['image_bytes'] += len(data)
    return {'actual_models': sorted(actual_models), 'image_dimensions': dict(dimensions), 'screenshot_scopes': dict(scopes),
            'errors': dict(errors), 'total_image_pixels': pixels, **counts}


def contrast(rows):
    pairs = []
    lookup = {(r['task'], r['repeat'], r['arm']): r for r in rows}
    for a in rows:
        key = (a['task'], a['repeat'], 'B')
        if a['arm'] == 'A' and key in lookup:
            pairs.append((a, lookup[key]))
    result = {}
    for scope, subset in [('all', pairs), ('joint_success', [(a, b) for a, b in pairs if a['success'] and b['success']])]:
        result[scope] = {'pairs': len(subset), 'metrics': {}}
        for name in ('requests', 'input', 'elapsed', 'cost'):
            before = sum(a[name] for a, b in subset)
            after = sum(b[name] for a, b in subset)
            result[scope]['metrics'][name] = {'A': before, 'B': after,
                'pct': (after / before - 1) * 100 if before else None}
    return result


def analyze(folder, historical):
    result = {'models': {}}
    for name in ('sonnet', 'opus'):
        path = folder / name / 'summary.json'
        if not path.exists():
            result['models'][name] = {'state': 'not_started'}
            continue
        state = json.loads(path.read_text())
        rows, invalid = [], []
        for entry in state['runs']:
            run = entry['pair']['results'].get('kitsune', {})
            if not run.get('benchmark_evaluation', {}).get('scorable'):
                invalid.append({k: entry[k] for k in ('task', 'arm')})
                continue
            row = metrics(entry)
            row['wrong_attempts'] = run['benchmark_evaluation'].get('wrong_attempts')
            row['trace_details'] = media_and_errors(run['run_dir'])
            rows.append(row)
        result['models'][name] = {'state': state['state'], 'model': state['model'], 'unscorable': invalid,
            'cost_all_attempts': state['estimated_cost_usd'], 'rows': rows,
            'arms': {a: aggregate([r for r in rows if r['arm'] == a]) for a in 'AB'},
            'contrast': contrast(rows)}
    old = json.loads(historical.read_text())
    rows = [row for row in old['rows'] if row['task'] in SELECTED]
    result['historical_haiku'] = {'source': str(historical), 'repeats': 3,
        'arms': {a: aggregate([r for r in rows if r['arm'] == a]) for a in 'AB'},
        'contrast': contrast(rows)}
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('folder', type=Path)
    parser.add_argument('--historical', type=Path, default=Path('artifacts/target-view-experiment-20261022/analysis.json'))
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = analyze(args.folder.resolve(), args.historical.resolve())
    with args.output.open('x') as file:
        json.dump(result, file, indent=2)
    print(json.dumps({name: {'state': model['state'], 'contrast': model.get('contrast')}
                      for name, model in result['models'].items()}, indent=2))


if __name__ == '__main__':
    main()
