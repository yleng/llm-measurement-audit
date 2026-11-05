import math
import sys
import unittest

sys.path.insert(0, 'src')
try:
    from llmaudit.core import analyze, crossfit_predictions, validate
except ImportError:
    analyze = crossfit_predictions = validate = None


def design():
    return dict(units='iid', assignment='bernoulli_randomized', assignment_probability=.5,
                audit='independent_bernoulli', audit_policy_frozen=True,
                scorer_frozen=True, reference_frozen=True, complete_audit_returns=True,
                score_protocol='synthetic-v1', human_reference='fixed synthetic rubric',
                outcome_units='points', mode='frozen_score', alpha=.05,
                folds=2, fold_seed='before-labels', ridge=1.0)


def records(full=False):
    rows = []
    for arm in (0, 1):
        for i in range(12):
            audited = full or i % 2 == 0
            rows.append(dict(record_id=f'{arm}-{i}', arm=arm, ai_score=float(i + arm),
                             audited=int(audited), human_label=float(i + 2*arm) if audited else None,
                             audit_probability=1.0 if full else .5))
    return rows


class CoreTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(analyze, 'the public analysis API must exist')

    def test_known_answer_frozen_score_and_variance(self):
        out = analyze(records(), design())
        self.assertAlmostEqual(out['corrected']['estimate'], 2.0)
        self.assertAlmostEqual(out['ai_only']['estimate'], 1.0)
        # phi in arm 0 is i; arm 1 is i+3 for even i, i+1 for odd i.
        a = list(range(12)); b = [i+3 if i%2==0 else i+1 for i in range(12)]
        var = lambda x: sum((z-sum(x)/len(x))**2 for z in x)/(len(x)-1)
        expected = math.sqrt(var(a)/12 + var(b)/12)
        self.assertAlmostEqual(out['corrected']['standard_error'], expected)

    def test_full_audit_equals_human_contrast_and_welch_se(self):
        out = analyze(records(True), design())
        self.assertAlmostEqual(out['corrected']['estimate'], 2.0)
        self.assertAlmostEqual(out['corrected']['standard_error'], math.sqrt(13/6))

    def test_known_unequal_probabilities_are_used(self):
        rows = records()
        rows[12]['audit_probability'] = .25
        self.assertAlmostEqual(analyze(rows, design())['corrected']['estimate'], 2 + 2/12)

    def test_row_order_invariant_and_does_not_mutate_inputs(self):
        rows=records(); before=repr(rows)
        self.assertEqual(analyze(rows,design()), analyze(list(reversed(rows)),design()))
        self.assertEqual(repr(rows),before)

    def test_no_label_clipping(self):
        rows=records(True); rows[12]['human_label']=-100.0
        self.assertLess(analyze(rows,design())['corrected']['estimate'],0)

    def test_bad_records_fail_closed(self):
        mutations = [
            lambda r:r.append(dict(r[0])),
            lambda r:r[0].pop('audit_probability'),
            lambda r:r[0].update(audit_probability=0),
            lambda r:r[0].update(audit_probability=1.1),
            lambda r:r[0].update(ai_score=float('nan')),
            lambda r:r[0].update(human_label=None),
            lambda r:r[1].update(human_label=5),
            lambda r:r[1].update(audit_probability=1),
            lambda r:r[0].update(arm=2),
            lambda r:r[0].update(audited='False'),
            lambda r:r[0].update(scorer_version='different'),
        ]
        for change in mutations:
            with self.subTest(change=change):
                rows=records();change(rows)
                with self.assertRaises(ValueError): analyze(rows,design())

    def test_bad_design_and_numeric_config_fail(self):
        for field,value in [('units','clusters'),('assignment','observational'),('audit','fixed_size'),
                            ('scorer_frozen',False),('audit_policy_frozen',False),
                            ('complete_audit_returns',False),('reference_frozen',False),
                            ('alpha',float('nan')),('assignment_probability',float('inf')),
                            ('folds',2.5),('ridge',float('inf')),('mode','guess'),
                            ('cluster_id','customer')]:
            with self.subTest(field=field):
                cfg=design();cfg[field]=value
                with self.assertRaises(ValueError): analyze(records(),cfg)

    def test_insufficient_audits_fail_even_frozen_score(self):
        rows=records()
        for row in rows:
            if row['arm']==1 and row['record_id']!='1-0':
                row.update(audited=0,human_label=None)
        with self.assertRaises(ValueError): analyze(rows,design())

    def test_weights_and_small_sample_warnings(self):
        rows=records();rows[0]['audit_probability']=.01
        out=analyze(rows,design())
        self.assertEqual(out['arms']['0']['max_audit_weight'],100)
        self.assertLess(out['arms']['0']['audit_weight_ess'],6)
        self.assertTrue(any('weight' in x.lower() for x in out['warnings']))
        self.assertTrue(any('small' in x.lower() for x in out['warnings']))

    def test_crossfit_predictions_exclude_own_fold_labels(self):
        cfg=design();cfg['mode']='crossfit_ridge'
        rows=records(True)
        first=crossfit_predictions(rows,cfg)
        target='0-0'; fold=first[target]['fold']
        changed=[dict(x) for x in rows]
        for row in changed:
            if row['arm']==0 and first[row['record_id']]['fold']==fold:
                row['human_label'] += 1000
        second=crossfit_predictions(changed,cfg)
        self.assertEqual(first[target]['prediction'],second[target]['prediction'])
        self.assertEqual(first[target]['fold'],second[target]['fold'])

    def test_crossfit_sparse_training_fails_without_fallback(self):
        cfg=design();cfg.update(mode='crossfit_ridge',folds=12)
        rows=records()
        # At least two labels per arm, but fewer than three in every training fold.
        for row in rows:
            if int(row['record_id'].split('-')[1])>2:row.update(audited=0,human_label=None)
        with self.assertRaises(ValueError):analyze(rows,cfg)

    def test_crossfit_full_audit_still_equals_human_result(self):
        cfg=design();cfg['mode']='crossfit_ridge'
        self.assertEqual(analyze(records(True),cfg)['corrected'], analyze(records(True),design())['corrected'])

    def test_unrepresentable_inverse_probability_fails(self):
        rows=records(True);rows[0]['audit_probability']=1e-320
        with self.assertRaises(ValueError):analyze(rows,design())

    def test_zero_variance_is_flagged(self):
        rows=records(True)
        for row in rows:row['human_label']=float(row['arm'])
        out=analyze(rows,design())
        self.assertEqual(out['corrected']['standard_error'],0)
        self.assertTrue(any('zero' in x.lower() for x in out['warnings']))

    def test_no_audited_row_or_cluster_columns_fail(self):
        for mutation in [lambda r:r[0].update(cluster_id='person'),
                         lambda r:[x.update(audited=0,human_label=None) for x in r]]:
            rows=records();mutation(rows)
            with self.assertRaises(ValueError):analyze(rows,design())

    def test_effect_and_se_translation_and_scaling(self):
        rows=records();baseline=analyze(rows,design())
        for row in rows:
            row['ai_score']=3*row['ai_score']+7
            if row['audited']:row['human_label']=3*row['human_label']+7
        changed=analyze(rows,design())
        self.assertAlmostEqual(changed['corrected']['estimate'],3*baseline['corrected']['estimate'])
        self.assertAlmostEqual(changed['corrected']['standard_error'],3*baseline['corrected']['standard_error'])

    def test_unrepresentable_confidence_quantile_fails(self):
        # Finite variance and SE, but alpha cannot produce a representable quantile.
        from llmaudit.core import _contrast
        with self.assertRaises(ValueError):
            _contrast({0:[-1e153,1e153],1:[-1e153,1e153]}, 1e-320)

    def test_crossfit_public_api_wraps_numeric_overflow(self):
        cfg=design();cfg['mode']='crossfit_ridge'
        rows=records(True)
        for i,row in enumerate(rows):row['ai_score']=1e200 if i%2 else -1e200
        with self.assertRaises(ValueError):crossfit_predictions(rows,cfg)

    def test_root_independent_known_answer(self):
        # Independent audit_reference.json: phi0=(2,3,2,3), phi1=(4,5,2,3).
        rows=[]
        for arm in (0,1):
            for i in range(4):
                rows.append(dict(record_id=f'{arm}-{i}',arm=arm,ai_score=float(i),audited=int(i<2),
                                 human_label=float(i+arm+1) if i<2 else None,audit_probability=.5))
        out=analyze(rows,design())
        self.assertAlmostEqual(out['corrected']['estimate'],1)
        self.assertAlmostEqual(out['corrected']['standard_error']**2,.5)

    def test_full_audit_bypasses_large_prediction_cancellation(self):
        rows=records(True)
        for row in rows:
            row['ai_score']=1e16
            row['human_label']=float(row['arm']+1)
        self.assertAlmostEqual(analyze(rows,design())['corrected']['estimate'],1.0)

    def test_certainty_row_uses_label_in_mixed_audit(self):
        rows=records()
        # The first control row is certainly audited; huge predictor must cancel exactly.
        rows[0].update(ai_score=1e16,human_label=1.0,audit_probability=1.0)
        self.assertAlmostEqual(analyze(rows,design())['corrected']['estimate'],2-1/12)


if __name__=='__main__': unittest.main()
