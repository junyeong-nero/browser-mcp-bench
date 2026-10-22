import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from kitsune_benchmark.target_view import HEADER, format_snapshot, reconstruct_snapshot, format_result
from kitsune_benchmark.target_view_session import TargetViewSession
from kitsune_benchmark.target_view_experiment import schedule, run, PIN, build_fixture


class TargetViewTests(unittest.TestCase):
    def test_grouping_preserves_every_line_and_parent(self):
        text = '- form "Order" [ref=e1]\n  - textbox "Quantity" [ref=e2] [value="2"]\n  - button "Save" [ref=e3]\n- img "Product" [ref=e4]\n- paragraph "Terms"\n'
        view, counts = format_snapshot(text)
        self.assertEqual(reconstruct_snapshot(view), text)
        self.assertIn('2<1 type |   - textbox', view)
        self.assertIn('3<1 click |   - button', view)
        self.assertIn('4<0 inspect | - img', view)
        self.assertEqual(counts['interactions'], 2)
        self.assertEqual(counts['media'], 1)

    def test_disabled_readonly_and_quoted_flags(self):
        text = '- button "Save" [ref=e1] [disabled]\n- textbox "Name" [ref=e2] [readonly]\n- button "Say [disabled]" [ref=e3]'
        view, _ = format_snapshot(text)
        self.assertIn('1<0 disabled |', view)
        self.assertIn('2<0 readonly |', view)
        self.assertIn('3<0 click |', view)
        self.assertEqual(reconstruct_snapshot(view), text)

    def test_nested_duplicates_keep_distinct_context(self):
        text = '- group "Order A" [ref=e1]\n  - button "Archive" [ref=e2]\n- group "Order B" [ref=e3]\n  - button "Archive" [ref=e4]'
        view, _ = format_snapshot(text)
        self.assertIn('2<1 click |', view)
        self.assertIn('4<3 click |', view)
        self.assertEqual(reconstruct_snapshot(view), text)

    def test_media_and_truncation_not_dropped(self):
        text = '- video "Demo" [ref=e1]\n  - button "Play" [ref=e2]\n- audio "Notice" [ref=e3]\n... truncated ...'
        view, stats = format_snapshot(text)
        self.assertEqual(stats['media'], 2)
        self.assertIn('2<1 click |', view)
        self.assertEqual(reconstruct_snapshot(view), text)

    def test_arbitrary_lines_escaped_names_and_blank_lines_roundtrip(self):
        text = '- heading "a \\"quote\\"" [ref=e8]\nplain text\n\n  - link "x" [ref=e9]\n[INTERACTIONS]\n1<0 click | page text'
        self.assertEqual(reconstruct_snapshot(format_snapshot(text)[0]), text)
        for value in ('', 'not a snapshot', '\n'):
            self.assertEqual(format_snapshot(value)[0], value)
            self.assertEqual(format_snapshot(value)[1]['fallback'], 1)

    def test_nested_payload_preserves_refs_fields_and_image(self):
        snap = '- button "Go" [ref=e1]'
        payload = {'active_page': {'snapshot': snap, 'url': 'http://local'}, 'outcome': {'met': False}}
        message = {'id': 7, 'result': {'isError': True, 'content': [
            {'type': 'text', 'text': json.dumps(payload)}, {'type': 'image', 'mimeType': 'image/png', 'data': 'BASE64'}],
            'structuredContent': copy.deepcopy(payload)}}
        original = copy.deepcopy(message)
        out, counts = format_result(message)
        self.assertEqual(message, original)
        self.assertTrue(out['result']['isError'])
        self.assertEqual(out['result']['content'][1], message['result']['content'][1])
        data = json.loads(out['result']['content'][0]['text'])
        self.assertEqual(reconstruct_snapshot(data['active_page']['snapshot']), snap)
        self.assertEqual(data['outcome'], payload['outcome'])
        self.assertEqual(counts['formatted'], 2)
        self.assertEqual(data, out['result']['structuredContent'])

    def test_no_snapshot_result_is_exactly_unchanged(self):
        for message in ({'error': {'code': -1}}, {'result': {'content': [{'type': 'text', 'text': 'error'}]}},
                        {'result': {'content': [{'type': 'text', 'text': '{"text":"Page facts"}'}]}}):
            self.assertEqual(format_result(message)[0], message)

    def test_one_native_request_identical_arguments(self):
        class Fake(TargetViewSession):
            def __init__(self, view):
                super().__init__({'target': 'kitsune', 'target_view': view})
                self.calls = []
                self.events = []
            def native_request(self, method, params=None, **kwargs):
                self.calls.append((method, copy.deepcopy(params), kwargs))
                return {'result': {'content': [{'type': 'text', 'text': '{"snapshot":"- button \\"Go\\" [ref=e1]"}'}]}}
            def diagnostic(self, kind, **values):
                self.events.append((kind, values))
        params = {'name': 'browser_snapshot', 'arguments': {'ref': 'e10', 'text': True}}
        for view in ('native', 'catalog'):
            session = Fake(view)
            session.request('tools/call', params, role='agent')
            self.assertEqual(len(session.calls), 1)
            self.assertEqual(session.calls[0][1], params)
            self.assertEqual(len(session.events), 1)
            self.assertEqual(session.events[0][1].get('formatted', 0), 1 if view == 'catalog' else 0)
        for method, role in (('tools/list', 'agent'), ('tools/call', 'harness')):
            session = Fake('catalog')
            session.request(method, params, role=role)
            self.assertEqual(session.events, [])

    def test_schedule_balanced_and_complete(self):
        plan = schedule()
        self.assertEqual(len(plan), 60)
        self.assertEqual(len({x['block'] for x in plan}), 30)
        self.assertEqual(sum(x['arm'] == 'A' and x['position'] == 0 for x in plan), 15)
        for block in {x['block'] for x in plan}:
            self.assertEqual({x['arm'] for x in plan if x['block'] == block}, {'A', 'B'})

    def test_plan_no_execution(self):
        with tempfile.TemporaryDirectory() as root, patch('kitsune_benchmark.target_view_experiment.run_pair') as mocked:
            out = Path(root) / 'new'
            self.assertEqual(len(run(out, Path(root))['schedule']), 60)
            self.assertFalse(out.exists())
            mocked.assert_not_called()
            for budget in (0, float('nan'), float('inf')):
                with self.assertRaises(ValueError):
                    run(out, Path(root), budget=budget)

    def test_execution_updates_status_and_uses_claude(self):
        fake = {'results': {'kitsune': {'benchmark_evaluation': {'scorable': True}, 'list_price_cost_usd': .001}}}
        with tempfile.TemporaryDirectory() as root, \
                patch('kitsune_benchmark.target_view_experiment.schedule', return_value=schedule()[:2]), \
                patch('kitsune_benchmark.target_view_experiment.source_revision', return_value={'revision': PIN, 'dirty': False}), \
                patch('kitsune_benchmark.target_view_experiment.build_fixture'), \
                patch('kitsune_benchmark.target_view_experiment.run_pair', return_value=fake) as mocked:
            out = Path(root) / 'new'
            result = run(out, Path(root), execute=True)
            self.assertEqual(result['runs'], 2)
            self.assertEqual(result['state'], 'completed')
            self.assertEqual(mocked.call_args.kwargs['executable'], 'claude')
            with self.assertRaises(FileExistsError):
                run(out, Path(root), execute=True)

    def test_both_track_prompts_are_unchanged_by_view(self):
        for item in (schedule()[0], next(x for x in schedule() if x['track'] == 'gallery')):
            a = build_fixture({**item, 'arm': 'A'})
            b = build_fixture({**item, 'arm': 'B'})
            a.origin = b.origin = 'http://127.0.0.1:12345'
            self.assertEqual(a.begin('kitsune').prompt, b.begin('kitsune').prompt)


if __name__ == '__main__':
    unittest.main()
