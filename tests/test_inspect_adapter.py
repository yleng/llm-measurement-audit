import copy
import csv
import json
from pathlib import Path
import unittest

from llmaudit.inspect_adapter import paired_records
from llmaudit.core import analyze

ROOT = Path(__file__).resolve().parents[1]


def fixture():
    with (ROOT/'examples/paired.csv').open() as handle:
        rows = list(csv.DictReader(handle))
    logs = []
    for side in (0, 1):
        samples = [dict(id=r['pair_id'], epoch=1, input='Prompt '+r['pair_id'], target='rubric',
                        scores={'judge': {'value': float(r[f'ai_score_{side}'])}}) for r in rows]
        logs.append(dict(status='success', eval={'dataset':{'samples':len(samples)}}, samples=samples))
    audits = [{key:r[key] for key in ['pair_id','audited','human_label_0','human_label_1','audit_probability']} for r in rows]
    config = json.loads((ROOT/'examples/paired_design.json').read_text())
    return logs, audits, config


class InspectAdapterTests(unittest.TestCase):
    def test_reordered_logs_reproduce_paired_estimate(self):
        logs, audits, cfg = fixture()
        logs[1]['samples'].reverse()
        result = analyze(paired_records(*logs, audits, 'judge', cfg), cfg)
        self.assertEqual(result['corrected']['estimate'], -.25)

    def rejects(self, mutate, message):
        logs, audits, cfg = fixture()
        mutate(logs, audits)
        with self.assertRaisesRegex(ValueError, message):
            paired_records(*logs, audits, 'judge', cfg)

    def test_missing_pair(self):
        self.rejects(lambda logs, a:logs[1]['samples'].pop(), 'frame|count')

    def test_duplicate_id(self):
        self.rejects(lambda logs, a:logs[1]['samples'].__setitem__(1, copy.deepcopy(logs[1]['samples'][0])), 'duplicate')

    def test_changed_prompt(self):
        self.rejects(lambda logs, a:logs[1]['samples'][0].update(input='Different'), 'prompt|context')

    def test_changed_target(self):
        self.rejects(lambda logs, a:logs[1]['samples'][0].update(target='Different'), 'prompt|context')

    def test_repeated_epoch(self):
        self.rejects(lambda logs, a:logs[1]['samples'][0].update(epoch=2), 'epoch')

    def test_error_sample(self):
        self.rejects(lambda logs, a:logs[1]['samples'][0].update(error={'message':'failed'}), 'error|invalid')

    def test_non_scalar_score(self):
        self.rejects(lambda logs, a:logs[1]['samples'][0]['scores']['judge'].update(value={'quality':1}), 'numeric')

    def test_boolean_score(self):
        self.rejects(lambda logs, a:logs[1]['samples'][0]['scores']['judge'].update(value=True), 'numeric')

    def test_nonfinite_score(self):
        self.rejects(lambda logs, a:logs[1]['samples'][0]['scores']['judge'].update(value=float('nan')), 'finite')

    def test_incomplete_human_pair(self):
        self.rejects(lambda logs, a:a[0].update(human_label_0=''), 'both human')

    def test_audit_frame_mismatch(self):
        self.rejects(lambda logs, a:a.pop(), 'audit.*frame')

    def test_edited_log(self):
        self.rejects(lambda logs, a:logs[1].update(config_updates=[{'x':1}]), 'edited|configuration')

    def test_external_files(self):
        self.rejects(lambda logs, a:logs[1]['samples'][0].update(files=['secret.txt']), 'files|text')

    def test_original_records_unchanged(self):
        logs, audits, cfg = fixture()
        original = copy.deepcopy([logs,audits])
        paired_records(*logs,audits,'judge',cfg)
        self.assertEqual([logs,audits],original)

    def test_eval_level_sandbox(self):
        self.rejects(lambda logs, a:logs[1]['eval'].update(sandbox={'type':'docker'}), 'sandbox')
