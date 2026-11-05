"""Read local Inspect logs into the existing paired probability-audit workflow.

Inspect is optional. No model calls, score conversion, intersection filtering, or
statistical redesign happens here. See integrations/inspect_ai/README.md.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
import sys

from .paired import validate_paired

_AUDIT_FIELDS = {'pair_id', 'audited', 'human_label_0', 'human_label_1', 'audit_probability'}


def _index(log, scorer):
    if log.get('status') != 'success' or log.get('invalidated'):
        raise ValueError('only successful, non-invalidated logs are supported')
    if log.get('config_updates'):
        raise ValueError('logs with edited configuration are unsupported')
    if log.get('eval', {}).get('sandbox'):
        raise ValueError('evaluation-level sandbox context is unsupported')
    samples = log.get('samples')
    count = log.get('eval', {}).get('dataset', {}).get('samples')
    if not samples or type(count) is not int or count != len(samples):
        raise ValueError('complete logged sample count must match the declared dataset frame')
    indexed = {}
    for sample in samples:
        raw_id = sample.get('id')
        if type(raw_id) not in (int, str) or not str(raw_id).strip():
            raise ValueError('sample IDs must be nonempty strings or integers')
        pair_id = str(raw_id).strip()
        if pair_id in indexed:
            raise ValueError('duplicate sample ID; repeated outputs are unsupported')
        if type(sample.get('epoch')) is not int or sample['epoch'] != 1:
            raise ValueError('one epoch (epoch=1) per prompt is required')
        if sample.get('error') or sample.get('invalidation') or sample.get('limit'):
            raise ValueError('sample has an error, invalidation, or execution limit')
        if any(sample.get(k) for k in ('files', 'setup', 'sandbox')):
            raise ValueError('only self-contained text prompts are supported; no files or sandboxes')
        prompt = sample.get('input')
        text = isinstance(prompt, str) or (isinstance(prompt, list) and bool(prompt)
                    and all(isinstance(m, dict) and isinstance(m.get('content'), str) for m in prompt))
        if not text or 'attachment://' in json.dumps(prompt):
            raise ValueError('only resolved, self-contained text input is supported')
        if 'target' not in sample:
            raise ValueError('sample target is required for prompt/context matching')
        value = (sample.get('scores') or {}).get(scorer, {}).get('value')
        if type(value) not in (int, float):
            raise ValueError('selected scorer must have a scalar numeric value; no implicit conversion')
        if not math.isfinite(value):
            raise ValueError('selected score must be finite')
        context = {k:sample.get(k) for k in ('input','target','choices','metadata')}
        indexed[pair_id] = (context, value)
    return indexed


def paired_records(baseline, candidate, audit_rows, scorer, config):
    """Match complete text-only log frames by ID and validate pair-level ratings.

    Args:
        baseline: JSON-mode model dump of a complete Inspect EvalLog.
        candidate: JSON-mode model dump of the candidate EvalLog.
        audit_rows: Complete pair manifest, including unaudited pairs and known pi.
        scorer: Exact score key, shared across logs; finite numeric scores only.
        config: Existing llmaudit paired-design declarations.

    Returns:
        Validated paired records for llmaudit.core.analyze or the ordinary CLI.
    """
    if not isinstance(scorer, str) or not scorer.strip():
        raise ValueError('an explicit scorer name is required')
    left, right = _index(baseline, scorer), _index(candidate, scorer)
    if left.keys() != right.keys():
        raise ValueError('baseline and candidate frames differ; intersection filtering is forbidden')
    audits = {}
    for row in audit_rows:
        if not isinstance(row, dict) or set(row) != _AUDIT_FIELDS:
            raise ValueError('audit manifest needs exactly the five documented fields')
        pair_id = row['pair_id']
        if not isinstance(pair_id, str) or not pair_id.strip():
            raise ValueError('audit pair_id must be nonempty text')
        pair_id = pair_id.strip()
        if pair_id in audits:
            raise ValueError('duplicate audit pair_id')
        audits[pair_id] = dict(row, pair_id=pair_id)
    if audits.keys() != left.keys():
        raise ValueError('audit manifest frame must match both complete log frames')
    result = []
    for pair_id in sorted(left):
        if left[pair_id][0] != right[pair_id][0]:
            raise ValueError('matched ID has different prompt or task context')
        result.append(dict(audits[pair_id], ai_score_0=left[pair_id][1], ai_score_1=right[pair_id][1]))
    return validate_paired(result, config)


def main(argv=None):
    """Convert local Inspect logs to a validated paired CSV; refuse overwrite."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline', required=True)
    parser.add_argument('--candidate', required=True)
    parser.add_argument('--audit', required=True)
    parser.add_argument('--scorer', required=True)
    parser.add_argument('--design', required=True)
    parser.add_argument('--output', required=True, help='New paired CSV path')
    args = parser.parse_args(argv)
    try:
        from inspect_ai.log import read_eval_log
    except ImportError:
        parser.error('Inspect adapter requires Python >=3.11 and pip install ".[inspect]"')
    try:
        from .cli import _object, _read_csv
        paths = [Path(p) for p in (args.baseline, args.candidate)]
        if not all(p.is_file() for p in paths):
            raise ValueError('both logs must be existing local files')
        logs = [read_eval_log(p, resolve_attachments=True).model_dump(mode='json') for p in paths]
        audits = _read_csv(Path(args.audit).read_bytes())
        cfg = json.loads(Path(args.design).read_text(), object_pairs_hook=_object)
        rows = paired_records(*logs, audits, args.scorer, cfg)
        with Path(args.output).open('x', newline='') as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows({k:('' if v is None else v) for k,v in row.items()} for row in rows)
    except (ValueError, OSError) as exc:
        print(f'Inspect conversion failed: {exc}', file=sys.stderr)
        return 2
    print(f'Wrote {len(rows)} matched pairs to {args.output}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
