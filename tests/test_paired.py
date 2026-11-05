import copy
import csv
import itertools
import json
import math
import os
from pathlib import Path
import statistics
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, 'src')
from llmaudit import analyze


def paired_design():
    return dict(comparison='paired', units='iid_prompts', audit='independent_bernoulli',
                audit_policy_frozen=True, scorer_frozen=True, reference_frozen=True,
                complete_audit_returns=True, score_protocol='synthetic-paired-v1',
                human_reference='fixed synthetic rubric', outcome_units='points',
                mode='frozen_score', alpha=.05)


def paired_records(full=False):
    # Huge variation in prompt difficulty, but small within-prompt differences.
    # D=(1,2,3,4); G=(2,1,4,3); partial phi=(3,2,5,4).
    result = []
    for i, (base, delta, human_delta) in enumerate(zip(
            [0, 100, 200, 300], [1, 2, 3, 4], [2, 1, 4, 3])):
        audited = full or i % 2 == 0
        result.append(dict(pair_id=f'prompt-{i}', ai_score_0=base,
                           ai_score_1=base+delta, audited=int(audited),
                           human_label_0=base if audited else None,
                           human_label_1=base+human_delta if audited else None,
                           audit_probability=1.0 if full else .5))
    return result


class PairedTests(unittest.TestCase):
    def test_known_partial_audit_mean_and_paired_variance(self):
        out = analyze(paired_records(), paired_design())
        self.assertAlmostEqual(out['corrected']['estimate'], 3.5)
        self.assertAlmostEqual(out['corrected']['standard_error']**2, 5/12)
        self.assertAlmostEqual(out['ai_only']['estimate'], 2.5)
        self.assertAlmostEqual(out['ai_only']['standard_error']**2, 5/12)
        self.assertEqual(out['comparison'], 'paired')
        self.assertEqual(out['pairs']['units'], 4)
        self.assertEqual(out['pairs']['audited'], 2)
        self.assertNotIn('ATE', out['estimand'])

    def test_complete_audit_equals_human_paired_mean_and_se(self):
        out = analyze(paired_records(True), paired_design())
        self.assertAlmostEqual(out['corrected']['estimate'], 2.5)
        self.assertAlmostEqual(out['corrected']['standard_error'], math.sqrt(5/12))

    def test_pair_covariance_preserved_for_constant_difference(self):
        rows = paired_records(True)
        for row in rows:
            row['human_label_1'] = row['human_label_0'] + 2
        out = analyze(rows, paired_design())
        self.assertEqual(out['corrected']['estimate'], 2)
        self.assertEqual(out['corrected']['standard_error'], 0)
        self.assertTrue(any('zero' in w.lower() for w in out['warnings']))

    def test_unequal_pair_probabilities_change_residual_weights(self):
        rows = paired_records()
        rows[0]['audit_probability'] = .25
        out = analyze(rows, paired_design())
        # phi=(5,2,5,4), not a correction using observed audit fractions.
        self.assertAlmostEqual(out['corrected']['estimate'], 4)
        self.assertAlmostEqual(out['corrected']['standard_error'], math.sqrt(.5))
        self.assertEqual(out['pairs']['expected_audited'], 1.75)

    def test_expectation_over_all_audit_selections_recovers_human_mean(self):
        # Two certainty pairs ensure every enumerated sample has arithmetic support.
        rows = paired_records(True)
        for i in (0, 1):
            rows[i]['ai_score_1'] = rows[i]['ai_score_0'] + (
                rows[i]['human_label_1']-rows[i]['human_label_0'])
        probabilities = [.2, .7]
        truth = statistics.mean(r['human_label_1']-r['human_label_0'] for r in rows)
        expectation = 0
        for flags in itertools.product([0, 1], repeat=2):
            sample = copy.deepcopy(rows)
            weight = 1
            for index, (flag, pi) in enumerate(zip(flags, probabilities), start=2):
                sample[index].update(audited=flag, audit_probability=pi)
                if not flag:
                    sample[index].update(human_label_0=None, human_label_1=None)
                weight *= pi if flag else 1-pi
            expectation += weight * analyze(sample, paired_design())['corrected']['estimate']
        self.assertAlmostEqual(expectation, truth)

    def test_swapping_checkpoint_sides_reverses_estimate_and_interval(self):
        rows = paired_records()
        original = analyze(rows, paired_design())
        for row in rows:
            for prefix in ('ai_score', 'human_label'):
                row[prefix+'_0'], row[prefix+'_1'] = row[prefix+'_1'], row[prefix+'_0']
        swapped = analyze(rows, paired_design())
        for key in ('corrected', 'ai_only'):
            self.assertAlmostEqual(swapped[key]['estimate'], -original[key]['estimate'])
            self.assertEqual(swapped[key]['standard_error'], original[key]['standard_error'])
            lo, hi = original[key]['confidence_interval']
            self.assertEqual(swapped[key]['confidence_interval'], [-hi, -lo])

    def test_common_shift_scale_order_and_nonmutation(self):
        rows = paired_records()
        before = copy.deepcopy(rows)
        original = analyze(rows, paired_design())
        self.assertEqual(rows, before)
        self.assertEqual(original, analyze(list(reversed(rows)), paired_design()))
        for row in rows:
            for key in ('ai_score_0', 'ai_score_1', 'human_label_0', 'human_label_1'):
                if row[key] is not None:
                    row[key] = 3*row[key]+17
        scaled = analyze(rows, paired_design())
        self.assertAlmostEqual(scaled['corrected']['estimate'], 3*original['corrected']['estimate'])
        self.assertAlmostEqual(scaled['corrected']['standard_error'], 3*original['corrected']['standard_error'])

    def test_certainty_pair_avoids_large_prediction_cancellation(self):
        rows = paired_records()
        rows[0].update(ai_score_0=-1e16, ai_score_1=1e16,
                       human_label_0=0, human_label_1=2, audit_probability=1)
        self.assertAlmostEqual(analyze(rows, paired_design())['corrected']['estimate'], 3.25)

    def test_invalid_pairs_rejected(self):
        mutations = [
            lambda r: r.append(dict(r[0])),
            lambda r: r[0].update(pair_id=' '),
            lambda r: r[0].pop('ai_score_1'),
            lambda r: r[0].update(ai_score_0=float('nan')),
            lambda r: r[0].update(ai_score_1=True),
            lambda r: r[0].update(human_label_0=None),
            lambda r: r[0].update(human_label_1=None),
            lambda r: r[1].update(human_label_0=0),
            lambda r: r[1].update(human_label_1=1),
            lambda r: r[0].update(human_label_1=float('inf')),
            lambda r: r[0].pop('audit_probability'),
            lambda r: r[0].update(audit_probability=0),
            lambda r: r[0].update(audit_probability=1.1),
            lambda r: r[0].update(audit_probability=1e-320),
            lambda r: r[1].update(audit_probability=1),
            lambda r: r[0].update(audited=2),
            lambda r: r[0].update(audited=True),
            lambda r: r[0].update(scorer_version='changed'),
            lambda r: r[0].update(cluster_id='user'),
            lambda r: r[0].update(stratum='topic'),
            lambda r: r[0].update(arm=0),
        ]
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                rows = paired_records()
                mutation(rows)
                with self.assertRaises(ValueError):
                    analyze(rows, paired_design())

    def test_missing_empty_and_unsupported_config_rejected(self):
        mutations = [(key, value) for key, value in [
            ('units', 'clusters'), ('comparison', 'unpaired'), ('audit', 'fixed_size'),
            ('mode', 'crossfit_ridge'), ('audit_policy_frozen', False),
            ('scorer_frozen', False), ('reference_frozen', False),
            ('complete_audit_returns', False), ('alpha', 0), ('alpha', 1),
            ('alpha', float('nan')), ('score_protocol', ''), ('human_reference', ''),
            ('outcome_units', ''), ('assignment_probability', .5), ('folds', 2)]]
        for key, value in mutations:
            with self.subTest(key=key, value=value):
                cfg = paired_design()
                cfg[key] = value
                with self.assertRaises(ValueError):
                    analyze(paired_records(), cfg)
        for key in paired_design():
            cfg = paired_design()
            del cfg[key]
            with self.assertRaises(ValueError):
                analyze(paired_records(), cfg)

    def test_insufficient_pairs_or_audits_rejected(self):
        for rows in [[], paired_records()[:1], paired_records()[:2]]:
            with self.assertRaises(ValueError):
                analyze(rows, paired_design())

    def test_weight_concentration_warns(self):
        rows = paired_records()
        rows[0]['audit_probability'] = .001
        out = analyze(rows, paired_design())
        self.assertEqual(out['pairs']['max_audit_weight'], 1000)
        self.assertLess(out['pairs']['audit_weight_ess'], 2)
        self.assertTrue(any('weight' in w.lower() for w in out['warnings']))

    def test_constant_judge_differences_warn_about_zero_ai_variance(self):
        rows = paired_records(True)
        for row in rows:
            row['ai_score_1'] = row['ai_score_0'] + 1
        out = analyze(rows, paired_design())
        self.assertEqual(out['ai_only']['standard_error'], 0)
        self.assertTrue(any('AI-only' in w and 'zero' in w for w in out['warnings']))

    def test_low_probability_on_unaudited_pair_still_warns(self):
        rows = paired_records()
        rows[1]['audit_probability'] = .001
        out = analyze(rows, paired_design())
        self.assertEqual(out['pairs']['min_audit_probability'], .001)
        self.assertEqual(out['pairs']['max_audit_weight'], 2)
        self.assertTrue(any('weight' in w.lower() for w in out['warnings']))

    def test_nonfinite_difference_or_variance_becomes_value_error(self):
        rows = paired_records(True)
        rows[0].update(ai_score_0=-1e308, ai_score_1=1e308)
        with self.assertRaises(ValueError):
            analyze(rows, paired_design())
        rows = paired_records(True)
        rows[0]['human_label_1'] = 1e308
        with self.assertRaises(ValueError):
            analyze(rows, paired_design())


class PairedCLITests(unittest.TestCase):
    def run_cli(self, root, rows):
        with (root/'data.csv').open('w', newline='') as source:
            writer = csv.DictWriter(source, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
        (root/'design.json').write_text(json.dumps(paired_design()))
        return subprocess.run([sys.executable, '-m', 'llmaudit', '--data', str(root/'data.csv'),
                               '--design', str(root/'design.json'), '--output', str(root/'report')],
                              cwd=root, capture_output=True, text=True,
                              env=dict(os.environ, PYTHONPATH=str(Path(__file__).resolve().parents[1]/'src'),
                                       PYTHONDONTWRITEBYTECODE='1'))

    def test_paired_cli_labels_covariance_and_provenance(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run = self.run_cli(root, paired_records())
            self.assertEqual(run.returncode, 0, run.stderr)
            result = json.loads((root/'report.json').read_text())
            self.assertEqual(result['comparison'], 'paired')
            self.assertAlmostEqual(result['corrected']['standard_error']**2, 5/12)
            self.assertEqual(len(result['provenance']['input_sha256']), 64)
            text = (root/'report.md').read_text()
            self.assertIn('checkpoint 1 minus checkpoint 0', text)
            self.assertIn('Pairs', text)
            self.assertNotIn('treatment effect', text)
            self.assertNotIn('prompt-0', text)

    def test_incomplete_pair_returns_exit_two_without_reports(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            rows = paired_records()
            rows[0]['human_label_1'] = None
            run = self.run_cli(root, rows)
            self.assertEqual(run.returncode, 2)
            self.assertFalse((root/'report.json').exists())
            self.assertFalse((root/'report.md').exists())


if __name__ == '__main__':
    unittest.main()
