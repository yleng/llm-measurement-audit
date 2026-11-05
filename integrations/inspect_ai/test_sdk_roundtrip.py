"""Integration tests require the optional Inspect SDK, not API credentials."""
import csv
import json
from pathlib import Path
import tempfile
import unittest

from inspect_ai.log import read_eval_log, write_eval_log
from llmaudit.inspect_adapter import main
from llmaudit.core import analyze

HERE=Path(__file__).resolve().parent


class InspectSDKTests(unittest.TestCase):
    def test_json_and_eval_formats_match_existing_paired_inference(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            for fmt in ('json','eval'):
                for name in ('baseline','candidate'):
                    log=read_eval_log(HERE/'fixtures'/(name+'.json'))
                    write_eval_log(log,root/(name+'.'+fmt),format=fmt)
                output=root/(fmt+'.csv')
                args=['--baseline',str(root/('baseline.'+fmt)),
                      '--candidate',str(root/('candidate.'+fmt)),
                      '--audit',str(HERE/'fixtures/audit.csv'),'--scorer','judge',
                      '--design',str(HERE/'fixtures/design.json'),'--output',str(output)]
                self.assertEqual(main(args),0)
                with output.open() as handle:
                    rows=list(csv.DictReader(handle))
                report=analyze(rows,json.loads((HERE/'fixtures/design.json').read_text()))
                self.assertEqual(report['corrected']['estimate'],-.25)
                self.assertNotIn('Fabricated prompt',output.read_text())
                before=output.read_bytes()
                self.assertEqual(main(args),2)
                self.assertEqual(output.read_bytes(),before)

    def test_official_log_with_global_sandbox_is_rejected(self):
        from inspect_ai.log import EvalLog
        from llmaudit.inspect_adapter import paired_records
        left=read_eval_log(HERE/'fixtures/baseline.json').model_dump(mode='json')
        right=read_eval_log(HERE/'fixtures/candidate.json').model_dump(mode='json')
        right['eval']['sandbox']={'type':'local'}
        right=EvalLog.model_validate(right).model_dump(mode='json')
        with (HERE/'fixtures/audit.csv').open() as handle:
            audits=list(csv.DictReader(handle))
        config=json.loads((HERE/'fixtures/design.json').read_text())
        with self.assertRaisesRegex(ValueError,'sandbox'):
            paired_records(left,right,audits,'judge',config)
