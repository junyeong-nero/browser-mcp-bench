import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

from kitsune_benchmark.target_model_experiment import MODELS, PIN, schedule, spec_for, worker, coordinate, hashes
from kitsune_benchmark.personal import config


class TargetModelTests(unittest.TestCase):
    def test_opposite_paired_orders_and_exact_coverage(self):
        sonnet, opus = schedule('sonnet'), schedule('opus')
        self.assertEqual(len(sonnet), 8)
        self.assertEqual(len(opus), 8)
        for a, b in zip(sonnet, opus):
            self.assertEqual(a['task'], b['task'])
            self.assertNotEqual(a['arm'], b['arm'])
        self.assertEqual(len({x['unit'] for x in sonnet}), 4)

    def test_model_override_is_local_and_time_budget_fixed(self):
        original = config()
        for model in MODELS:
            for item in schedule(model):
                spec = spec_for(item, model)
                self.assertEqual(spec['claude_code']['model'], MODELS[model])
                self.assertEqual(spec['claude_code']['effort'], 'medium')
                self.assertEqual(spec['claude_code']['max_budget_usd_per_run'], .5)
                self.assertEqual(spec['timeout_sec'], 120)
        self.assertEqual(config(), original)

    def test_plan_has_no_process_or_directory_side_effect(self):
        with tempfile.TemporaryDirectory() as root, patch('kitsune_benchmark.target_model_experiment.subprocess.Popen') as launch:
            output = Path(root) / 'new'
            plan = coordinate(output, Path(root))
            self.assertEqual(plan['execution_window_sec'], 1080)
            self.assertEqual(plan['total_budget_usd'], 8)
            self.assertFalse(output.exists())
            launch.assert_not_called()

    def test_worker_status_updates_and_correct_executable(self):
        fake = {'results': {'kitsune': {'benchmark_evaluation': {'scorable': True}, 'list_price_cost_usd': .01}}}
        with tempfile.TemporaryDirectory() as root, \
                patch('kitsune_benchmark.target_model_experiment.schedule', return_value=schedule('sonnet')[:2]), \
                patch('kitsune_benchmark.target_model_experiment.source_revision', return_value={'revision': PIN, 'dirty': False}), \
                patch('kitsune_benchmark.target_model_experiment.build_fixture'), \
                patch('kitsune_benchmark.target_model_experiment.run_pair', return_value=fake) as execute:
            output = Path(root)
            (output / 'plan.json').write_text(json.dumps({'implementation_sha256': hashes()}))
            result = worker(output, output, 'sonnet', time.time() + 500)
            self.assertEqual(result, 0)
            state = json.loads((output / 'sonnet/summary.json').read_text())
            self.assertEqual(len(state['runs']), 2)
            self.assertAlmostEqual(state['estimated_cost_usd'], .02)
            self.assertEqual(execute.call_args.kwargs['executable'], 'claude')
            self.assertEqual(execute.call_args.kwargs['experiment_spec']['claude_code']['model'], MODELS['sonnet'])

    def test_analysis_matches_pairs_without_inventing_repetitions(self):
        from kitsune_benchmark.target_model_analysis import contrast
        rows = [dict(task=task, repeat=0, arm=arm, success=True,
                     requests=value, input=value*100, elapsed=value, cost=value/1000)
                for task in ('one', 'two') for arm, value in (('B', 8), ('A', 10))]
        result = contrast(rows)
        self.assertEqual(result['all']['pairs'], 2)
        self.assertAlmostEqual(result['all']['metrics']['requests']['pct'], -20)
        self.assertNotIn('confidence_intervals', result)

    def test_worker_deadline_reserve_prevents_inference(self):
        with tempfile.TemporaryDirectory() as root, patch('kitsune_benchmark.target_model_experiment.run_pair') as execute:
            output = Path(root)
            (output / 'plan.json').write_text(json.dumps({'implementation_sha256': hashes()}))
            self.assertEqual(worker(output, output, 'opus', time.time() + 10), 3)
            state = json.loads((output / 'opus/summary.json').read_text())
            self.assertEqual(state['stopped_reason'], 'deadline_reserve')
            self.assertEqual(state['runs'], [])
            execute.assert_not_called()


if __name__ == '__main__':
    unittest.main()
