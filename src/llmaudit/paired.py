"""Probability-audit correction of within-prompt checkpoint differences."""
from __future__ import annotations

import math
import statistics

from .core import _number


_REQUIRED = {'pair_id', 'ai_score_0', 'ai_score_1', 'audited',
             'human_label_0', 'human_label_1', 'audit_probability'}
_CONFIG = {'comparison', 'units', 'audit', 'audit_policy_frozen', 'scorer_frozen',
           'reference_frozen', 'complete_audit_returns', 'score_protocol',
           'human_reference', 'outcome_units', 'mode', 'alpha'}


def validate_paired(records, config):
    """Validate complete pairs and an explicit, fixed-predictor audit design."""
    if not isinstance(config, dict) or set(config) != _CONFIG:
        raise ValueError('paired config must contain exactly the documented paired design fields')
    for key, expected in [('comparison', 'paired'), ('units', 'iid_prompts'),
                          ('audit', 'independent_bernoulli'), ('mode', 'frozen_score')]:
        if config[key] != expected:
            raise ValueError(f'unsupported paired {key}: expected {expected}')
    for key in ['audit_policy_frozen', 'scorer_frozen', 'reference_frozen', 'complete_audit_returns']:
        if config[key] is not True:
            raise ValueError(f'{key} must be explicitly true')
    for key in ['score_protocol', 'human_reference', 'outcome_units']:
        if not isinstance(config[key], str) or not config[key].strip():
            raise ValueError(f'{key} must be nonempty text')
    if not 0 < _number(config['alpha'], 'alpha') < 1:
        raise ValueError('alpha must lie in (0,1)')
    rows, ids = [], set()
    for raw in records:
        if not isinstance(raw, dict) or not _REQUIRED <= set(raw):
            raise ValueError('each paired row needs both scores, both label columns, and known audit_probability')
        if not isinstance(raw['pair_id'], str) or not raw['pair_id'].strip():
            raise ValueError('pair_id must be nonempty text')
        pair_id = raw['pair_id'].strip()
        if pair_id in ids:
            raise ValueError('duplicate pair_id: each prompt must appear exactly once')
        ids.add(pair_id)
        if any(key in raw for key in ['cluster_id', 'stratum', 'arm']):
            raise ValueError('paired rows require IID prompts with both checkpoints; clusters, strata and arm rows are unsupported')
        audited = _number(raw['audited'], 'audited')
        if audited not in (0, 1):
            raise ValueError('audited must be numeric 0 or 1')
        pi = _number(raw['audit_probability'], 'audit_probability')
        if not 0 < pi <= 1:
            raise ValueError('known pair audit_probability must lie in (0,1]')
        if not math.isfinite(1/pi):
            raise ValueError('inverse pair audit probability is not representable')
        if pi == 1 and not audited:
            raise ValueError('a pair inclusion probability of one requires both human labels')
        if raw.get('scorer_version', config['score_protocol']) != config['score_protocol']:
            raise ValueError('scorer_version disagrees with frozen score_protocol')
        row = dict(pair_id=pair_id, audited=int(audited), audit_probability=pi)
        for side in (0, 1):
            row[f'ai_score_{side}'] = _number(raw[f'ai_score_{side}'], f'ai_score_{side}')
            label = raw[f'human_label_{side}']
            blank = label is None or (isinstance(label, str) and not label.strip())
            if bool(audited) == blank:
                raise ValueError('audited pairs require both human labels; unaudited pairs require both labels blank')
            row[f'human_label_{side}'] = None if blank else _number(label, f'human_label_{side}')
        rows.append(row)
    if len(rows) < 2 or sum(row['audited'] for row in rows) < 2:
        raise ValueError('paired analysis needs >=2 prompt pairs and >=2 fully audited pairs')
    return sorted(rows, key=lambda row: row['pair_id'])


def _mean_interval(values, alpha):
    estimate = statistics.mean(values)
    se = math.sqrt(statistics.variance(values)/len(values))
    z = statistics.NormalDist().inv_cdf(1-alpha/2)
    interval = [estimate-z*se, estimate+z*se]
    if not all(math.isfinite(value) for value in [estimate, se, z] + interval):
        raise ValueError('nonfinite paired inference result: rescale values and inspect audit weights')
    return dict(estimate=estimate, standard_error=se, confidence_interval=interval, alpha=alpha)


def analyze_paired(records, config):
    """Estimate a population mean difference using IID, completely audited pairs."""
    rows = validate_paired(records, config)
    corrected, scores = [], []
    for row in rows:
        delta = _number(row['ai_score_1']-row['ai_score_0'], 'within-pair AI difference')
        phi = delta
        if row['audited']:
            human_delta = _number(row['human_label_1']-row['human_label_0'], 'within-pair human difference')
            # Exact human difference for certainty pairs avoids cancellation of large predictions.
            phi = human_delta if row['audit_probability'] == 1 else (
                delta + (human_delta-delta)/row['audit_probability'])
        corrected.append(_number(phi, 'corrected pair difference'))
        scores.append(delta)
    audited = [row for row in rows if row['audited']]
    weights = [1/row['audit_probability'] for row in audited]
    largest = max(weights)
    scaled = [weight/largest for weight in weights]
    ess = math.fsum(scaled)**2/math.fsum(weight*weight for weight in scaled)
    diagnostics = dict(units=len(rows), audited=len(audited),
                       expected_audited=math.fsum(row['audit_probability'] for row in rows),
                       min_audit_probability=min(row['audit_probability'] for row in rows),
                       max_audit_weight=largest, audit_weight_ess=ess)
    warnings = [
        'Design declarations are user assertions; the CSV does not prove shared prompts, IID pairs, sampling, or rubric validity.',
        'Intervals are asymptotic IID prompt-population mean-difference intervals; fixed-archive conditional coverage is unsupported.',
    ]
    if len(rows) < 30 or len(audited) < 20:
        warnings.append('Small prompt sample or pair audit count; normal intervals may be unreliable.')
    if 1/diagnostics['min_audit_probability'] > 10 or ess < len(audited)/2:
        warnings.append('Potentially unstable pair audit weights; inspect full-frame minimum audit probability, audited maximum weight, and descriptive weight ESS.')
    output = dict(schema_version='0.2', comparison='paired',
                  estimand='population mean human-reference difference (checkpoint 1 minus checkpoint 0)',
                  method='paired_generalized_difference', mode=config['mode'], design=dict(config),
                  pairs=diagnostics, corrected=_mean_interval(corrected, float(config['alpha'])),
                  ai_only=_mean_interval(scores, float(config['alpha'])), warnings=warnings)
    if output['corrected']['standard_error'] == 0:
        warnings.append('Observed zero corrected-difference variance does not establish population certainty; normal inference can be degenerate.')
    if output['ai_only']['standard_error'] == 0:
        warnings.append('Observed zero AI-only difference variance does not establish population certainty; normal inference can be degenerate.')
    return output
