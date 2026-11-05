"""Build and execute the self-contained randomized-experiment tutorial, without Jupyter."""
from pathlib import Path
import contextlib
import io
import json

ROOT=Path(__file__).resolve().parents[2]
HERE=ROOT/'integrations/ppi_py'
source=(HERE/'randomized_text_experiment.py').read_text()
imports_and_data=source[:source.index('def _scalar')]
estimation=source[source.index('def _scalar'):source.index("if __name__ == '__main__':")]
run='''labeled = generate_cohort(800, 601, "labeled")
unlabeled = generate_cohort(4000, 602, "unlabeled")
assert not set(labeled["id"]) & set(unlabeled["id"])
del unlabeled["human"]  # Never available to the estimator.
result = run_example(labeled, unlabeled)
print("Synthetic example: population human-reference effect = 0")
print("800 labeled units; 4,000 independent unlabeled units")
for key in ("judge_only", "human_only", "ppi"):
    value = result[key]
    low, high = value["confidence_interval"]
    print(f"{key:12s} {value['estimate']:+.2f}  [{low:+.2f}, {high:+.2f}]")
'''
contents=[
('markdown','''# Your experiment is randomized. What does its LLM score measure?

A new fee notice may change how people explain a rule. If an LLM rewards the changed writing style, the score contrast combines comprehension with scoring error. This synthetic tutorial uses **existing ppi_py APIs** to estimate the human-reference treatment effect.

Applications include marketing (notice comprehension), enterprise AI (task accuracy), education (conceptual understanding), and LLM evaluation (human-rated quality when independent requests are randomized between models). Same-prompt model comparisons require paired inference rather than this randomized route. Human raters define the outcome; judge scores make the larger sample useful. These are possible applications, not demonstrated deployments.

Install `ppi-python==0.2.3`, `numpy==1.26.4`, and `scipy==1.13.1`. The example generates its data locally and needs no API key.

## 1. Independent labeled and unlabeled experiments

Both cohorts follow the same randomized assignment (probability 0.5). Human scores have mean 50 and SD 10, and treatment changes no human outcome. Judge scores add eight points in arm 1, plus noise with SD 3. The numbers are unbounded illustrative points. Fixed seeds 601 and 602 are not searched for favorable results. Separate IDs make the cohorts disjoint.'''),
('code',imports_and_data),
('markdown','''## 2. Estimate each human-reference arm mean with PPI

For each arm, call `ppi_mean_pointestimate` and `ppi_mean_ci` with aligned human labels/predictions from the labeled cohort and predictions **only from the independent unlabeled cohort**. Set `lam=1` in advance for ordinary PPI without power tuning.

The estimate is the unlabeled prediction mean plus the labeled mean residual. Each arm gets a 97.5% asymptotic interval. Subtract bounds as `[lower_1-upper_0, upper_1-lower_0]`: Bonferroni gives a conservative nominal 95% contrast interval when the arm intervals have their stated asymptotic coverage. Coverage is asymptotic rather than an exact finite-sample guarantee.

The human-only baseline uses the same conservative armwise construction. Judge-only has an ordinary two-arm interval for its own score target.'''),
('code',estimation),
('markdown','''## 3. Run one fixed draw

Delete the unlabeled human outcomes before analysis. They are simulated for constructing the toy judge, but the estimator cannot access them. A useful judge may reduce the uncertainty relative to human-only inference; that advantage depends on the residual errors.'''),
('code',run),
('markdown','''## 4. Interpret the comparison

![Synthetic experiment: judge-only +8.08; PPI +0.46 with an interval crossing zero.](assets/results.png)

The judge-score interval excludes zero, but its target includes the deliberately injected eight-point scoring bonus. Both human-reference intervals include zero, leaving the direction unresolved; they do not prove equivalence. One draw is not a coverage study or evidence of typical superiority or cost savings. Eight hundred labels are an illustrative input, not a budget recommendation.

The validity argument requires independent IID labeled and unlabeled cohorts from the same population/design, frozen predictions and a specified human rubric, aligned labels/predictions, and sufficient moments/sample sizes for the upstream asymptotic intervals. Conditional grouping by randomized arm preserves the arm distributions. These statements do not cover clustering, nonuniform/adaptive labeling, train-on-evaluation leakage, or reuse of labeled cases in `Yhat_unlabeled`.

Human ratings must measure the outcome the experiment is intended to change. Keep labeled observations out of `Yhat_unlabeled`; this tutorial requires separate IID cohorts.

Methods and attribution: [ppi_py](https://github.com/aangelopoulos/ppi_py), [Prediction-Powered Inference](https://arxiv.org/abs/2301.09633), [DSL](https://naokiegami.com/paper/dsl_ss.pdf).''')]
namespace={'__name__':'__notebook__'}
cells=[]
count=0
for kind,text in contents:
    cell={'cell_type':kind,'metadata':{},'source':text.splitlines(keepends=True)}
    if kind=='code':
        count+=1
        stream=io.StringIO()
        with contextlib.redirect_stdout(stream):
            exec(compile(text,'<ppi tutorial cell>','exec'),namespace)
        cell.update(execution_count=count,outputs=([{'output_type':'stream','name':'stdout','text':stream.getvalue().splitlines(keepends=True)}] if stream.getvalue() else []))
    cells.append(cell)
notebook={'cells':cells,'metadata':{'kernelspec':{'display_name':'Python 3','language':'python','name':'python3'},'language_info':{'name':'python','version':'3.12'}},'nbformat':4,'nbformat_minor':5}
for index,cell in enumerate(cells):
    cell['id']=f'ppi-experiment-{index+1}'
(HERE/'randomized_text_experiment.ipynb').write_text(json.dumps(notebook,indent=2)+'\n')
print('Executed all notebook code cells against installed upstream APIs.')
