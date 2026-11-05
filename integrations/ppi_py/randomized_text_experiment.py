"""Human-reference treatment effects for synthetic randomized text outcomes.

Uses upstream APIs, independent labeled/unlabeled IID cohorts, and fixed lam=1.
The conservative contrast interval uses Bonferroni arm intervals. Uses the existing PPI implementation; no model calls or participant data.
"""
import json
import numpy as np
from scipy.stats import norm
from ppi_py import ppi_mean_ci, ppi_mean_pointestimate


def generate_cohort(n, seed, prefix):
    """Simulate an independent IID experiment; the human treatment effect is zero."""
    rng = np.random.default_rng(seed)
    arm = rng.binomial(1, .5, n)
    human = 50 + rng.normal(0, 10, n)
    judge = human + 8*arm + rng.normal(0, 3, n)
    return {'id':np.array([f'{prefix}-{i}' for i in range(n)]),
            'arm':arm, 'human':human, 'judge':judge}


def _scalar(value):
    return np.asarray(value).item()


def run_example(labeled, unlabeled, alpha=.05):
    """Estimate arm means through upstream PPI, then contrast their intervals.

    Both cohorts must be independent IID draws from the same randomized design.
    Human labels and predictions must be aligned within the labeled cohort.
    The unlabeled cohort's human outcomes are never accessed.
    """
    ppi, human_only, judge_only = [], [], []
    for arm in (0,1):
        li = labeled['arm'] == arm
        ui = unlabeled['arm'] == arm
        y, predicted, unpredicted = (labeled['human'][li], labeled['judge'][li], unlabeled['judge'][ui])
        estimate = _scalar(ppi_mean_pointestimate(y,predicted,unpredicted,lam=1))
        lo,hi = ppi_mean_ci(y,predicted,unpredicted,alpha=alpha/2,lam=1)
        ppi.append({'estimate':estimate, 'interval':[_scalar(lo),_scalar(hi)]})
        # Same conservative armwise construction for the human-only comparison.
        half = norm.ppf(1-alpha/4)*np.std(y,ddof=1)/np.sqrt(len(y))
        human_only.append({'estimate':float(y.mean()), 'interval':[float(y.mean()-half),float(y.mean()+half)]})
        judge_only.append(np.concatenate([predicted,unpredicted]))
    def difference(arms):
        return {'estimate':arms[1]['estimate']-arms[0]['estimate'],
                'confidence_interval':[arms[1]['interval'][0]-arms[0]['interval'][1],
                                       arms[1]['interval'][1]-arms[0]['interval'][0]]}
    judge = float(judge_only[1].mean()-judge_only[0].mean())
    half = float(norm.ppf(1-alpha/2)*np.sqrt(sum(np.var(g,ddof=1)/len(g) for g in judge_only)))
    return {'synthetic':True,'population_human_effect':0,'injected_score_bonus':8,
            'labeled_units':len(labeled['arm']),'unlabeled_units':len(unlabeled['arm']),
            'alpha':alpha,'lam':1,'contrast_interval':'Bonferroni combination of armwise asymptotic intervals',
            'ppi':difference(ppi),'human_only':difference(human_only),
            'judge_only':{'estimate':judge,'confidence_interval':[judge-half,judge+half]}}


if __name__ == '__main__':
    # Fixed seeds; no searching over draws. IDs make cohort separation visible.
    labeled = generate_cohort(800,601,'labeled')
    unlabeled = generate_cohort(4000,602,'unlabeled')
    del unlabeled['human']
    print(json.dumps(run_example(labeled,unlabeled),indent=2))
