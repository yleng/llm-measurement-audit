"""Standard generalized-difference correction, with explicit design assertions.

IID randomized two-arm inference and paired prompt comparisons are implemented.
A declared design cannot be established from a CSV. See docs/method.md.
"""
from __future__ import annotations

import hashlib
import math
import statistics


_REQUIRED = {'record_id', 'arm', 'ai_score', 'audited', 'human_label', 'audit_probability'}
_CONFIG = {'units', 'assignment', 'assignment_probability', 'audit', 'audit_policy_frozen',
           'scorer_frozen', 'reference_frozen', 'complete_audit_returns', 'score_protocol',
           'human_reference', 'outcome_units', 'mode', 'alpha', 'folds', 'fold_seed', 'ridge'}


def _number(value, name):
    if isinstance(value, bool):
        raise ValueError(f'{name} must be a finite number')
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f'{name} must be a finite number') from exc
    if not math.isfinite(number):
        raise ValueError(f'{name} must be a finite number')
    return number


def validate(records, config):
    """Normalize a copy of input data, rejecting unsupported or incomplete inputs."""
    if not isinstance(config, dict) or set(config) != _CONFIG:
        raise ValueError('config must contain exactly the documented design fields')
    for key, expected in [('units', 'iid'), ('assignment', 'bernoulli_randomized'),
                          ('audit', 'independent_bernoulli')]:
        if config[key] != expected:
            raise ValueError(f'unsupported {key}: expected {expected}')
    for key in ['audit_policy_frozen', 'scorer_frozen', 'reference_frozen', 'complete_audit_returns']:
        if config[key] is not True:
            raise ValueError(f'{key} must be explicitly true')
    for key in ['score_protocol', 'human_reference', 'outcome_units', 'fold_seed']:
        if not isinstance(config[key], str) or not config[key].strip():
            raise ValueError(f'{key} must be nonempty text')
    e = _number(config['assignment_probability'], 'assignment_probability')
    alpha = _number(config['alpha'], 'alpha')
    ridge = _number(config['ridge'], 'ridge')
    if not 0 < e < 1 or not 0 < alpha < 1 or ridge <= 0:
        raise ValueError('assignment_probability and alpha must lie in (0,1); ridge must be positive')
    if type(config['folds']) is not int or config['folds'] < 2:
        raise ValueError('folds must be an integer >=2')
    if config['mode'] not in ['frozen_score', 'crossfit_ridge']:
        raise ValueError('mode must be frozen_score or crossfit_ridge')
    rows, ids = [], set()
    for raw in records:
        if not isinstance(raw, dict) or not _REQUIRED <= set(raw):
            raise ValueError('each row must contain the required columns, including known audit_probability')
        if not isinstance(raw['record_id'], str) or not raw['record_id'].strip():
            raise ValueError('record_id must be nonempty text')
        record_id = raw['record_id'].strip()
        if record_id in ids:
            raise ValueError('duplicate record_id')
        ids.add(record_id)
        arm = _number(raw['arm'], 'arm')
        audited = _number(raw['audited'], 'audited')
        if arm not in (0, 1) or audited not in (0, 1):
            raise ValueError('arm and audited must be numeric 0 or 1')
        pi = _number(raw['audit_probability'], 'audit_probability')
        if not 0 < pi <= 1:
            raise ValueError('known audit_probability must lie in (0,1]')
        if not math.isfinite(1/pi):
            raise ValueError('inverse audit probability is not representable')
        if pi == 1 and not audited:
            raise ValueError('an inclusion probability of one requires an audited label')
        label = raw['human_label']
        blank = label is None or (isinstance(label, str) and not label.strip())
        if bool(audited) == blank:
            raise ValueError('audited labels must exist; unaudited labels must be blank')
        if raw.get('scorer_version', config['score_protocol']) != config['score_protocol']:
            raise ValueError('scorer_version disagrees with frozen score_protocol')
        # Cluster data are outside the supported IID design, even with an IID assertion.
        if any(k in raw for k in ['cluster_id', 'pair_id', 'stratum']):
            raise ValueError('cluster, pair and stratum columns are unsupported in randomized mode; matched prompts need the paired comparison design')
        rows.append(dict(record_id=record_id, arm=int(arm), audited=int(audited),
                         ai_score=_number(raw['ai_score'], 'ai_score'), audit_probability=pi,
                         human_label=None if blank else _number(label, 'human_label')))
    rows.sort(key=lambda row: row['record_id'])
    for arm in (0, 1):
        group = [r for r in rows if r['arm'] == arm]
        if len(group) < 2 or sum(r['audited'] for r in group) < 2:
            raise ValueError(f'arm {arm} needs >=2 units and >=2 audited labels')
    return rows


def _crossfit(rows, config):
    result = {}
    k = config['folds']
    for arm in (0, 1):
        group = [r for r in rows if r['arm'] == arm]
        if len(group) < k:
            raise ValueError('each arm must have at least folds units')
        # Predeclared seed and IDs only: never select folds from labels/audit counts.
        ordered = sorted(group, key=lambda r: (hashlib.sha256(
            (config['fold_seed'] + '\0' + r['record_id']).encode()).hexdigest(), r['record_id']))
        folds = {r['record_id']: i % k for i, r in enumerate(ordered)}
        for fold in range(k):
            train = [r for r in group if r['audited'] and folds[r['record_id']] != fold]
            if len(train) < 3:
                raise ValueError(f'arm {arm}, fold {fold}: fewer than 3 training audit labels; no fallback')
            weights = [1/r['audit_probability'] for r in train]
            total = math.fsum(weights)
            mx = math.fsum(w*r['ai_score'] for w, r in zip(weights, train))/total
            my = math.fsum(w*r['human_label'] for w, r in zip(weights, train))/total
            xx = math.fsum(w*(r['ai_score']-mx)**2 for w, r in zip(weights, train))
            xy = math.fsum(w*(r['ai_score']-mx)*(r['human_label']-my) for w, r in zip(weights, train))
            slope = xy/(xx + float(config['ridge']))
            for row in group:
                if folds[row['record_id']] == fold:
                    prediction = my + slope*(row['ai_score']-mx)
                    if not math.isfinite(prediction):
                        raise ValueError('nonfinite calibration result')
                    result[row['record_id']] = dict(prediction=prediction, fold=fold)
    return result


def crossfit_predictions(records, config):
    """Strict arm-specific out-of-fold affine ridge predictions; never clips scores."""
    try:
        return _crossfit(validate(records, config), config)
    except (OverflowError, statistics.StatisticsError, ZeroDivisionError) as exc:
        raise ValueError('numerically unstable calibration inputs; check support and rescale') from exc


def _contrast(values, alpha):
    means = [statistics.mean(values[a]) for a in (0, 1)]
    variance = math.fsum(statistics.variance(values[a])/len(values[a]) for a in (0, 1))
    se = math.sqrt(variance)
    estimate = means[1]-means[0]
    z = statistics.NormalDist().inv_cdf(1-alpha/2)
    endpoints = [estimate-z*se, estimate+z*se]
    if not all(math.isfinite(x) for x in [estimate, se, z] + endpoints):
        raise ValueError('nonfinite inference result: rescale extreme input values')
    return dict(estimate=estimate, standard_error=se,
                confidence_interval=endpoints, alpha=alpha)


def analyze(records, config):
    """Return aggregate generalized-difference effect and asymptotic IID inference."""
    try:
        if isinstance(config, dict) and config.get('comparison') == 'paired':
            from .paired import analyze_paired
            return analyze_paired(records, config)
        return _analyze(records, config)
    except (OverflowError, statistics.StatisticsError, ZeroDivisionError) as exc:
        raise ValueError('numerically unstable inputs; check support and rescale') from exc


def _analyze(records, config):
    rows = validate(records, config)
    preds = _crossfit(rows, config) if config['mode'] == 'crossfit_ridge' else None
    corrected, scores = {0: [], 1: []}, {0: [], 1: []}
    for row in rows:
        # Certainty observations reduce exactly to H; avoid m+(H-m) cancellation.
        if row['audit_probability'] == 1:
            phi = row['human_label']
        else:
            m = row['ai_score'] if preds is None else preds[row['record_id']]['prediction']
            # Missing H is never used in arithmetic or imputed as zero.
            phi = m + (row['human_label']-m)/row['audit_probability'] if row['audited'] else m
        if not math.isfinite(phi):
            raise ValueError('nonfinite pseudo-outcome: rescale values and inspect audit weights')
        corrected[row['arm']].append(phi)
        scores[row['arm']].append(row['ai_score'])
    warnings = ['Design declarations are user assertions; the CSV does not prove randomization, sampling, or rubric validity.',
                'Intervals are asymptotic IID superpopulation ATE intervals; fixed-archive conditional coverage is unsupported.']
    arms = {}
    for arm in (0, 1):
        group = [r for r in rows if r['arm'] == arm]
        audited = [r for r in group if r['audited']]
        weights = [1/r['audit_probability'] for r in audited]
        # Scale ESS to avoid overflow without changing its value.
        largest = max(weights)
        scaled = [w/largest for w in weights]
        ess = math.fsum(scaled)**2 / math.fsum(w*w for w in scaled)
        arms[str(arm)] = dict(units=len(group), audited=len(audited),
                              expected_audited=math.fsum(r['audit_probability'] for r in group),
                              min_audit_probability=min(r['audit_probability'] for r in group),
                              max_audit_weight=largest, audit_weight_ess=ess)
        if len(group) < 30 or len(audited) < 20:
            warnings.append(f'Arm {arm}: small sample or audit count; normal intervals may be unreliable.')
        if largest > 10 or ess < len(audited)/2:
            warnings.append(f'Arm {arm}: unstable audit weights; inspect maximum weight and descriptive weight ESS.')
    output = dict(schema_version='0.1', estimand='superpopulation human-reference ATE (arm 1 minus arm 0)',
                  method='generalized_difference', mode=config['mode'], design=dict(config), arms=arms,
                  corrected=_contrast(corrected, float(config['alpha'])),
                  ai_only=_contrast(scores, float(config['alpha'])), warnings=warnings)
    if preds is not None:
        warnings.append('Cross-fitted inference additionally requires a stable finite-variance nuisance limit; software checks cannot establish it.')
    if output['corrected']['standard_error'] == 0:
        warnings.append('Observed zero pseudo-outcome variance does not establish population certainty; normal inference can be degenerate.')
    return output
