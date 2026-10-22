import json
import tempfile
import unittest
from pathlib import Path

from kitsune_benchmark.tool_usage import aggregate, calls_from_events, error_category, iter_runs


class ToolUsageTests(unittest.TestCase):
    def test_deduplicates_calls_and_results(self):
        events = [
            {'type': 'assistant', 'message': {'content': [{'type': 'tool_use', 'id': '1', 'name': 'mcp__browser__browser_click', 'input': {}}]}},
            {'type': 'user', 'message': {'content': [{'type': 'tool_result', 'tool_use_id': '1', 'is_error': True, 'content': 'Expected outcome not observed'}]}},
        ]
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'events.jsonl'
            path.write_text('\n'.join(json.dumps(e) for e in events + events))
            calls, results = calls_from_events(path)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls['1']['name'], 'browser_click')
        self.assertEqual(results['1']['category'], 'outcome_unmet')

    def test_separates_exposure_usage_and_missing_results(self):
        rows = [{'model': 'model', 'advertised': {'visible': {}, 'unused': {}}, 'rpc_roles': {'agent': 2},
                 'calls': [{'name': 'visible', 'arguments': {}, 'completed': True, 'error': False},
                           {'name': 'hidden', 'arguments': {}, 'completed': False, 'error': None}]},
                {'model': 'model', 'advertised': {'unused': {}}, 'rpc_roles': {}, 'calls': []}]
        result = aggregate(rows)
        self.assertEqual(result['tool_calls'], 2)
        self.assertEqual(result['tools']['visible']['used_run_rate'], 1)
        self.assertEqual(result['tools']['unused']['exposed_runs'], 2)
        self.assertEqual(result['tools']['unused']['calls'], 0)
        self.assertIsNone(result['tools']['hidden']['used_run_rate'])
        self.assertIsNone(result['tools']['hidden']['error_rate'])
        self.assertEqual(result['tools']['hidden']['unadvertised_attempts'], 1)

    def test_frequency_does_not_inflate_used_run_count(self):
        row = {'model': 'm', 'advertised': {'browser_tabs': {}}, 'rpc_roles': {},
               'calls': [{'name': 'browser_tabs', 'arguments': {'action': 'new'}, 'completed': True, 'error': False}] * 3}
        tool = aggregate([row])['tools']['browser_tabs']
        self.assertEqual((tool['calls'], tool['used_runs']), (3, 1))
        self.assertEqual(tool['actions'], {'new': 3})

    def test_error_classification_does_not_label_success(self):
        self.assertIsNone(error_category({'content': 'stale ref'}))
        self.assertEqual(error_category({'is_error': True, 'content': [{'type': 'text', 'text': 'Unknown expect keys'}]}), 'expect_validation')
        self.assertEqual(error_category({'is_error': True, 'content': 'No element matches: e10'}), 'target_missing')

    def test_accepts_suite_and_experiment_shapes(self):
        pair = {'results': {'kitsune': {'model': 'm'}}, 'personal_task': 'pb-one'}
        self.assertEqual(next(iter_runs({'pairs': [pair]}, 'kitsune'))[0]['task'], 'pb-one')
        self.assertEqual(next(iter_runs({'runs': [{'task': 'x', 'arm': 'B', 'pair': pair}]}, 'kitsune'))[0]['arm'], 'B')
        self.assertEqual(list(iter_runs({'pairs': [pair]}, 'playwright')), [])


if __name__ == '__main__':
    unittest.main()
