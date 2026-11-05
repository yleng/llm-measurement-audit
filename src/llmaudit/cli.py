"""Local aggregate reports. Does not call models, sample audits or contact services."""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
from pathlib import Path
import sys

from . import __version__
from .core import analyze


def _object(pairs):
    obj = {}
    for key, value in pairs:
        if key in obj:
            raise ValueError(f'duplicate JSON key: {key}')
        obj[key] = value
    return obj


def _read_csv(data):
    reader = csv.DictReader(io.StringIO(data.decode('utf-8-sig')), strict=True)
    if not reader.fieldnames or len(reader.fieldnames) != len(set(reader.fieldnames)):
        raise ValueError('CSV needs unique headers; duplicate headers are rejected')
    rows = list(reader)
    if any(None in row or any(v is None for v in row.values()) for row in rows):
        raise ValueError('CSV row length does not match headers')
    return rows


def _plain(value):
    return str(value).replace('\n', ' ').replace('\r', ' ').replace('|', '/').replace('`', "'")


def markdown(report):
    corrected, ai = report['corrected'], report['ai_only']
    low, high = corrected['confidence_interval']
    cfg = report['design']
    paired = report.get('comparison') == 'paired'
    subject = 'checkpoint 1 relative to checkpoint 0' if paired else 'arm 1 relative to arm 0'
    if low > 0:
        interpretation = f'The interval is above zero: the estimated human-reference score is higher for {subject}.'
    elif high < 0:
        interpretation = f'The interval is below zero: the estimated human-reference score is lower for {subject}.'
    else:
        interpretation = 'The interval includes zero: these data do not resolve the direction of the human-reference difference.'
    target = ('Matched prompts; checkpoint 1 minus checkpoint 0. IID prompt-population mean difference.'
              if paired else 'Arm 1 minus arm 0; IID superpopulation average treatment effect.')
    lines = ['# Human-reference audit report', '',
             f"Reference: {_plain(cfg['human_reference'])}. Units: {_plain(cfg['outcome_units'])}.",
             '', target, '',
             '| Result | Estimate | Standard error |', '|---|---:|---:|',
             f"| Human-reference correction | {corrected['estimate']:.6g} | {corrected['standard_error']:.6g} |",
             f"| AI-only score contrast | {ai['estimate']:.6g} | {ai['standard_error']:.6g} |", '',
             f"Asymptotic {100*(1-corrected['alpha']):.6g}% normal interval for the human-reference effect: [{low:.6g}, {high:.6g}].", '',
             '## Interpretation', '', interpretation, '',
             'Read the estimate under the stated human rubric: higher scores mean improvement only if the rubric defines them that way. Use the interval to assess whether the data resolve a practically meaningful difference.', '',
             '## Audit coverage', '']
    if paired:
        stats = report['pairs']
        lines += ['| Pairs | Audited pairs | Expected audited pairs | Max inverse probability | Weight ESS |',
                  '|---:|---:|---:|---:|---:|',
                  f"| {stats['units']} | {stats['audited']} | {stats['expected_audited']:.6g} | {stats['max_audit_weight']:.6g} | {stats['audit_weight_ess']:.6g} |"]
    else:
        lines += ['| Arm | Units | Audited | Expected audited | Max inverse probability | Weight ESS |',
                  '|---|---:|---:|---:|---:|---:|']
        for arm, stats in report['arms'].items():
            lines.append(f"| {arm} | {stats['units']} | {stats['audited']} | {stats['expected_audited']:.6g} | {stats['max_audit_weight']:.6g} | {stats['audit_weight_ess']:.6g} |")
    lines += ['', 'Weight ESS is a descriptive concentration diagnostic, not the inferential sample size.', '',
              '## Assumptions and limits', '']
    lines += ['- ' + warning for warning in report['warnings']]
    lines += ['', 'The AI-only result compares judge scores. The corrected result targets the specified human-reference outcome.', '']
    return '\n'.join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description='Human-reference reports for randomized two-arm or paired prompt comparisons.')
    parser.add_argument('--data', required=True, type=Path, help='full frame CSV; known audit_probability required')
    parser.add_argument('--design', required=True, type=Path, help='explicit design/protocol JSON assertions')
    parser.add_argument('--output', required=True, type=Path, help='new output prefix; writes PREFIX.json and PREFIX.md')
    args = parser.parse_args(argv)
    try:
        data, design = args.data.read_bytes(), args.design.read_bytes()
        config = json.loads(design.decode('utf-8'), object_pairs_hook=_object)
        result = analyze(_read_csv(data), config)
        result['provenance'] = dict(package_version=__version__,
                                    input_sha256=hashlib.sha256(data).hexdigest(),
                                    design_sha256=hashlib.sha256(design).hexdigest())
        json_text = json.dumps(result, indent=2, allow_nan=False, sort_keys=True) + '\n'
        md_text = markdown(result)
        # Append suffixes: a prefix containing a dot must not silently lose its stem.
        targets = [(Path(str(args.output)+'.json'), json_text), (Path(str(args.output)+'.md'), md_text)]
        if any(p.exists() for p, _ in targets):
            raise ValueError('report output already exists; choose a new prefix')
        created = []
        try:
            for path, text in targets:
                with path.open('x', encoding='utf-8') as output:
                    created.append(path)
                    output.write(text)
        except OSError:
            for path in created:
                path.unlink(missing_ok=True)
            raise
        print(f'Wrote {targets[0][0]} and {targets[1][0]}')
        return 0
    except (OSError, UnicodeError, ValueError, TypeError, csv.Error) as exc:
        print(f'llmaudit: {exc}', file=sys.stderr)
        return 2
