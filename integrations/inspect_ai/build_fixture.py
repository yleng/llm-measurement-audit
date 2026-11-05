"""Build fabricated logs with the official Inspect SDK. No evaluations run."""
from pathlib import Path
import csv
import json

from inspect_ai.log import EvalLog, EvalSpec, EvalDataset, EvalSample, EvalConfig, write_eval_log
from inspect_ai.scorer import Score

ROOT=Path(__file__).resolve().parents[2]
HERE=Path(__file__).resolve().parent


def build():
    with (ROOT/'examples/paired.csv').open() as handle:
        rows=list(csv.DictReader(handle))
    destination=HERE/'fixtures'
    destination.mkdir(exist_ok=True)
    for side,name in [(0,'baseline'),(1,'candidate')]:
        samples=[EvalSample(id=r['pair_id'],epoch=1,input='Fabricated prompt '+r['pair_id'],
                            target='Fabricated quality rubric',
                            scores={'judge':Score(value=float(r[f'ai_score_{side}']))}) for r in rows]
        log=EvalLog(status='success',eval=EvalSpec(created='2026-11-04T00:00:00Z',
            task='synthetic-audit-fixture',model='mockllm/'+name,config=EvalConfig(epochs=1),
            dataset=EvalDataset(name='synthetic-paired',samples=len(rows),sample_ids=[r['pair_id'] for r in rows])),
            samples=samples)
        write_eval_log(log,destination/(name+'.json'),format='json')
    fields=['pair_id','audited','human_label_0','human_label_1','audit_probability']
    with (destination/'audit.csv').open('w',newline='') as handle:
        writer=csv.DictWriter(handle,fieldnames=fields)
        writer.writeheader()
        writer.writerows({k:r[k] for k in fields} for r in rows)
    config=json.loads((ROOT/'examples/paired_design.json').read_text())
    (destination/'design.json').write_text(json.dumps(config,indent=2)+'\n')


if __name__=='__main__':
    build()
