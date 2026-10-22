"""Offline MCP usage, with advertised-tool exposure and unique call/result IDs.

No API/model/browser calls. A zero-use tool is only evaluated when advertised.
Harness and disclosure RPCs are counted separately from agent-visible calls.
"""
from __future__ import annotations

import argparse
import collections
import csv
import json
from pathlib import Path


def iter_runs(summary, target):
    if 'pairs' in summary:
        for pair in summary['pairs']:
            if target in pair.get('results', {}):
                yield {'task': pair.get('personal_task', pair.get('gallery_task', 'unknown')), 'arm': None}, pair, pair['results'][target]
    elif 'runs' in summary:
        for entry in summary['runs']:
            pair = entry['pair']
            if target in pair.get('results', {}):
                yield entry, pair, pair['results'][target]
    else:
        raise ValueError('Expected a suite with pairs or experiment summary with runs')


def error_category(block):
    if not block.get('is_error'):
        return None
    raw = block.get('content', '')
    text = (raw if isinstance(raw, str) else json.dumps(raw)).lower()
    if 'expected outcome not observed' in text:
        return 'outcome_unmet'
    if 'stale ref' in text:
        return 'stale_ref'
    if 'expect needs' in text or 'unknown expect keys' in text:
        return 'expect_validation'
    if any(s in text for s in ('element not found', 'no element matches', 'selector not found')):
        return 'target_missing'
    if 'elements match' in text:
        return 'ambiguous_target'
    return 'other'


def calls_from_events(path):
    calls, results = {}, {}
    for line in path.read_text().splitlines():
        event = json.loads(line)
        content = event.get('message', {}).get('content', [])
        if not isinstance(content, list):
            continue
        for block in content:
            if event.get('type') == 'assistant' and block.get('type') == 'tool_use':
                calls[block['id']] = {'name': block['name'].split('__')[-1], 'input': block.get('input', {})}
            if block.get('type') == 'tool_result':
                results[block['tool_use_id']] = {'error': bool(block.get('is_error', False)), 'category': error_category(block)}
    return calls, results


def empty_tool():
    return {'exposed_runs': 0, 'used_runs': 0, 'calls': 0, 'completed': 0, 'errors': 0,
            'unadvertised_attempts': 0, 'actions': collections.Counter(), 'error_categories': collections.Counter(), 'native_schema_chars': []}


def aggregate(rows):
    tools = collections.defaultdict(empty_tool)
    rpc_roles = collections.Counter()
    rpc_by_role = collections.defaultdict(collections.Counter)
    for row in rows:
        for name, definition in row['advertised'].items():
            tool = tools[name]
            tool['exposed_runs'] += 1
            tool['native_schema_chars'].append(len(json.dumps(definition, ensure_ascii=False, separators=(',', ':'))))
        used = set()
        for call in row['calls']:
            name = call['name']
            tool = tools[name]
            tool['calls'] += 1
            tool['completed'] += call['completed']
            tool['errors'] += call['error'] is True
            if call.get('error_category'):
                tool['error_categories'][call['error_category']] += 1
            tool['unadvertised_attempts'] += name not in row['advertised']
            if name in row['advertised']:
                used.add(name)
            if name == 'browser_tabs':
                tool['actions'][call['arguments'].get('action', 'list')] += 1
        for name in used:
            tools[name]['used_runs'] += 1
        rpc_roles.update(row['rpc_roles'])
        for role, counts in row.get('rpc_tools_by_role', {}).items():
            rpc_by_role[role].update(counts)
    result = {}
    for name, stats in sorted(tools.items(), key=lambda item: (-item[1]['calls'], item[0])):
        schemas = stats.pop('native_schema_chars')
        result[name] = {**stats, 'actions': dict(stats['actions']),
            'used_run_rate': stats['used_runs'] / stats['exposed_runs'] if stats['exposed_runs'] else None,
            'error_rate': stats['errors'] / stats['completed'] if stats['completed'] else None,
            'native_definition_chars_min': min(schemas) if schemas else None,
            'native_definition_chars_max': max(schemas) if schemas else None}
    return {'runs': len(rows), 'models': sorted({r['model'] for r in rows}),
            'tool_calls': sum(t['calls'] for t in result.values()), 'tools': result,
            'native_rpc_calls_by_role': dict(rpc_roles), 'native_rpc_tools_by_role': {role: dict(counts) for role, counts in rpc_by_role.items()}}


def collect(cohorts, target='kitsune'):
    rows, seen = [], set()
    for label, path in cohorts:
        summary = json.loads(path.read_text())
        for entry, pair, run in iter_runs(summary, target):
            run_dir = Path(run['run_dir'])
            if str(run_dir) in seen:
                raise ValueError('Duplicate run directory across cohorts: ' + str(run_dir))
            seen.add(str(run_dir))
            metadata = json.loads((Path(pair['pair_dir']) / f'{target}-native-metadata.json').read_text())
            enabled = set(metadata['enabled_tools'])
            advertised = {t['name']: t for page in metadata['tools_pages'] for t in page.get('tools', []) if t['name'] in enabled}
            calls, results = calls_from_events(run_dir / 'events.jsonl')
            rpc_roles = collections.Counter()
            rpc_tools_by_role = collections.defaultdict(collections.Counter)
            for line in (Path(pair['pair_dir']) / f'{target}-native-rpc.jsonl').read_text().splitlines():
                rpc = json.loads(line)
                if rpc.get('kind') == 'rpc_completed' and rpc.get('method') == 'tools/call':
                    rpc_roles[rpc['role']] += 1
                    rpc_tools_by_role[rpc['role']][rpc.get('tool', 'unknown')] += 1
            records = [{'name': call['name'], 'arguments': call['input'], 'completed': cid in results,
                        'error': results.get(cid, {}).get('error'), 'error_category': results.get(cid, {}).get('category')}
                       for cid, call in calls.items()]
            rows.append({'cohort': label, 'task': entry.get('task', 'unknown'), 'arm': entry.get('arm'),
                'model': run['model'], 'run_dir': str(run_dir), 'scorable': run.get('benchmark_evaluation', {}).get('scorable'),
                'advertised': advertised, 'allowlisted_but_not_advertised': sorted(enabled - set(advertised)),
                'calls': records, 'rpc_roles': dict(rpc_roles), 'rpc_tools_by_role': dict(rpc_tools_by_role),
                'audited_mcp_calls': run.get('mcp_calls')})
    groups = {label: aggregate([r for r in rows if r['cohort'] == label]) for label, _ in cohorts}
    by_arm = {label: {str(arm): aggregate([r for r in rows if r['cohort'] == label and r['arm'] == arm])
                      for arm in sorted({r['arm'] for r in rows if r['cohort'] == label}, key=str)}
              for label, _ in cohorts}
    # Do not retain arbitrary tool arguments/content in this derived public-ready artifact.
    manifests = [{k: row[k] for k in ('cohort', 'task', 'arm', 'model', 'run_dir', 'scorable',
                                     'allowlisted_but_not_advertised', 'rpc_roles', 'audited_mcp_calls')}
                 | {'agent_attempts': len(row['calls']), 'missing_results': sum(not c['completed'] for c in row['calls'])}
                 for row in rows]
    return {'target': target, 'cohorts': groups, 'by_arm': by_arm, 'pooled_exploratory': aggregate(rows),
            'runs': manifests, 'sources': {label: str(path) for label, path in cohorts}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cohort', action='append', required=True, help='LABEL=SUMMARY_PATH')
    parser.add_argument('--target', default='kitsune', choices=('kitsune', 'playwright'))
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--csv', type=Path)
    args = parser.parse_args()
    cohorts = []
    for value in args.cohort:
        label, path = value.split('=', 1)
        if not label or label in {c[0] for c in cohorts}:
            parser.error('Cohort labels must be nonempty and unique')
        cohorts.append((label, Path(path).resolve()))
    result = collect(cohorts, args.target)
    with args.output.open('x') as output:
        json.dump(result, output, indent=2)
    if args.csv:
        with args.csv.open('x', newline='') as output:
            writer = csv.DictWriter(output, fieldnames=('cohort', 'tool', 'exposed_runs', 'used_runs', 'calls', 'completed', 'errors', 'used_run_rate', 'error_rate'))
            writer.writeheader()
            for label, summary in result['cohorts'].items():
                for name, data in summary['tools'].items():
                    writer.writerow({'cohort': label, 'tool': name, **{k: data[k] for k in writer.fieldnames if k not in ('cohort', 'tool')}})
    print(json.dumps({'runs': len(result['runs']), 'cohorts': {k: {'runs': v['runs'], 'calls': v['tool_calls']} for k,v in result['cohorts'].items()}}, indent=2))


if __name__ == '__main__':
    main()
