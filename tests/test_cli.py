import csv
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

from test_core import records, design


class CLITests(unittest.TestCase):
    def invoke(self, root, rows=None, config=None):
        data=root/'data.csv'; cfg=root/'design.json'; prefix=root/'report'
        if rows is not None:
            with data.open('w',newline='') as f:
                writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
        if config is not None:cfg.write_text(json.dumps(config))
        env=dict(os.environ, PYTHONPATH=str(Path(__file__).resolve().parents[1]/'src'),
                 PYTHONDONTWRITEBYTECODE='1')
        run=subprocess.run([os.sys.executable,'-m','llmaudit','--data',str(data),
                            '--design',str(cfg),'--output',str(prefix)],env=env,cwd=root,
                           text=True,capture_output=True)
        return run,prefix

    def test_cli_report_and_provenance_no_raw_records(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);run,prefix=self.invoke(root,records(),design())
            self.assertEqual(run.returncode,0,run.stderr)
            result=json.loads(prefix.with_suffix('.json').read_text())
            self.assertAlmostEqual(result['corrected']['estimate'],2)
            self.assertEqual(len(result['provenance']['input_sha256']),64)
            text=prefix.with_suffix('.md').read_text()
            self.assertIn('Human-reference',text)
            self.assertIn('## Interpretation',text)
            self.assertNotIn('## Provenance',text)
            self.assertNotIn(result['provenance']['input_sha256'],text)
            self.assertNotIn('0-0',text)
            self.assertIn('user assertions',text)

    def test_invalid_input_has_no_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            rows=records();rows[0]['audit_probability']=''
            run,prefix=self.invoke(Path(tmp),rows,design())
            self.assertEqual(run.returncode,2)
            self.assertFalse(prefix.with_suffix('.json').exists())
            self.assertFalse(prefix.with_suffix('.md').exists())

    def test_no_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);run,prefix=self.invoke(root,records(),design())
            self.assertEqual(run.returncode,0,run.stderr)
            before=prefix.with_suffix('.json').read_bytes()
            run,prefix=self.invoke(root)
            self.assertEqual(run.returncode,2)
            self.assertEqual(before,prefix.with_suffix('.json').read_bytes())

    def test_duplicate_csv_headers_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'data.csv').write_text('record_id,record_id\na,b\n')
            run,prefix=self.invoke(root,config=design())
            self.assertEqual(run.returncode,2)
            self.assertIn('duplicate',run.stderr.lower())

    def test_duplicate_json_keys_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); self.invoke(root,records(),design())
            (root/'design.json').write_text('{"audit":"fixed_size","audit":"independent_bernoulli"}')
            run,_=self.invoke(root)
            self.assertEqual(run.returncode,2)
            self.assertIn('duplicate',run.stderr.lower())


if __name__=='__main__':unittest.main()
