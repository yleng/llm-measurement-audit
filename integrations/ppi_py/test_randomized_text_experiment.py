import unittest
import numpy as np

from randomized_text_experiment import generate_cohort, run_example


class PPITutorialTests(unittest.TestCase):
    def test_independent_cohorts_have_disjoint_ids(self):
        labeled = generate_cohort(100, 601, 'labeled')
        unlabeled = generate_cohort(200, 602, 'unlabeled')
        self.assertFalse(set(labeled['id']) & set(unlabeled['id']))

    def test_fixed_lambda_api_matches_armwise_mean_identity(self):
        from ppi_py import ppi_mean_pointestimate
        labeled = generate_cohort(800, 601, 'labeled')
        unlabeled = generate_cohort(4000, 602, 'unlabeled')
        result = run_example(labeled, unlabeled)
        estimates = []
        for arm in (0,1):
            li = labeled['arm'] == arm
            ui = unlabeled['arm'] == arm
            expected = unlabeled['judge'][ui].mean() + (labeled['human'][li]-labeled['judge'][li]).mean()
            actual = ppi_mean_pointestimate(labeled['human'][li],labeled['judge'][li],unlabeled['judge'][ui],lam=1)
            self.assertAlmostEqual(np.asarray(actual).item(), expected)
            estimates.append(expected)
        self.assertAlmostEqual(result['ppi']['estimate'],estimates[1]-estimates[0])

    def test_contrast_bounds_use_bonferroni_arm_intervals(self):
        from ppi_py import ppi_mean_ci
        labeled = generate_cohort(800,601,'labeled')
        unlabeled = generate_cohort(4000,602,'unlabeled')
        intervals=[]
        for arm in (0,1):
            li=labeled['arm']==arm
            ui=unlabeled['arm']==arm
            lo,hi=ppi_mean_ci(labeled['human'][li],labeled['judge'][li],unlabeled['judge'][ui],alpha=.025,lam=1)
            intervals.append([np.asarray(lo).item(),np.asarray(hi).item()])
        result=run_example(labeled,unlabeled)
        np.testing.assert_allclose(result['ppi']['confidence_interval'],
                                   [intervals[1][0]-intervals[0][1],intervals[1][1]-intervals[0][0]])

    def test_result_cannot_use_hidden_unlabeled_human_outcomes(self):
        labeled=generate_cohort(800,601,'labeled')
        unlabeled=generate_cohort(4000,602,'unlabeled')
        before=run_example(labeled,unlabeled)
        del unlabeled['human']
        self.assertEqual(run_example(labeled,unlabeled),before)
