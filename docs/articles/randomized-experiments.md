# Human-audited inference for LLM-scored experiments and model comparisons

*Yan Leng · November 2026*

Many of us use LLM judges to score model responses, customer feedback, or written answers in experiments. They let us evaluate far more text than we could review by hand. But they also introduce measurement error: a judge may reward a longer or more polished answer even when a human would rate it no better. [Background on LLM judges and their biases](https://arxiv.org/abs/2306.05685).

That matters when we compare two groups or models. A higher average judge score may partly reflect the judge’s preferences rather than an improvement in the outcome we care about. Random assignment alone does not remove that scoring error.

I built `llmaudit` to help make these comparisons. It combines LLM scores for every response with human ratings from a probability sample, then reports the corrected difference and its uncertainty alongside the judge-only result.

A team rewrites a fee notice to make it easier to understand. Participants are randomly assigned to the current or new version, then explain when the fee applies. An LLM scores every answer for comprehension. The new notice comes out ahead.

The team needs to know whether people understand the rule better. Random assignment identifies an effect on the **judge's score**. Whether that score captures better comprehension is a measurement question. The new notice may also change the wording people use, and the judge may reward that wording.

The same question applies to a checkpoint with higher LLM-judge scores. In both settings, combine the automated scores with probability-sampled human ratings to estimate the difference under the human rubric and its confidence interval.

## LLM-as-a-judge bias can distort an A/B test

Consider two invented answers to “Does the fee apply if you cancel after the deadline?”

> “Yes, the fee applies.”
>
> “Yes. The policy clearly states that the fee applies when cancellation occurs after the deadline.”

A human rubric awarding a point for correctly identifying whether the fee applies gives both answers the same rating. Suppose the judge scores the second higher because it sounds more complete. If the new notice encourages that wording, the estimated score effect includes a style bonus alongside any comprehension effect.

The issue is whether measurement error differs between groups. An equal additive error cancels in their difference. An error favoring one group does not. High overall judge–human agreement does not establish that those errors cancel.

On a common numerical scale:

```text
Judge-score effect = human-reference effect
                   + difference in average judge–human error between groups
```

A larger experiment can give a precise judge-score estimate while leaving that discrepancy unresolved.

## Human-reference treatment effects: a worked example

The simulation creates 2,000 independent units, each assigned to a notice with probability 0.5. Human-reference scores have mean 50 and standard deviation 10. Each unit would receive the same human score under either notice, making the treatment effect zero by construction.

The simulated judge adds independent noise with standard deviation three and an eight-point bonus for the new-notice group. No real participants or LLM calls are involved; scores are illustrative points, not a validated comprehension scale.

Each answer is independently selected for human review with probability 0.2. This draw selects 366 answers. Twenty percent is the inclusion probability; the realized number reviewed is random.

![Synthetic randomized experiment comparing judge-only, human-only, and human-audited treatment-effect estimates and intervals.](../assets/experiment-results.png)

| Analysis | Estimated difference | Asymptotic 95% interval |
|---|---:|---:|
| Judge scores for all 2,000 answers | +7.55 | +6.62 to +8.47 |
| Human ratings for the 366 audited answers | −0.85 | −3.00 to +1.30 |
| Full scores plus sampled human correction | +1.11 | −0.28 to +2.50 |

The judge-only interval shows a positive effect on judge scores, as expected from the scoring bonus. Both human-reference intervals include zero: improvement remains unresolved. Including zero does not prove equivalence.

The correction has a narrower interval than human-only analysis in this draw, although its point estimate is farther from the known zero effect. This one simulation shows the calculation. It cannot establish coverage, typical superiority, or annotation savings. Seeds are fixed without searching for a favorable draw.

## How probability-sampled human ratings correct the comparison

Freeze the judge, human rubric, and audit rule. Score every response and obtain all prescribed human ratings from the probability audit. For reviewed answers, calculate human score minus judge score. With 20% inclusion probability, weight each discrepancy by five:

```text
Reviewed:   corrected contribution = judge score + 5 × (human − judge)
Unreviewed: corrected contribution = judge score
```

Compare the group averages of these contributions. Under the declared sampling design, the weighted discrepancies represent errors across the full experiment. Unreviewed human ratings remain missing; they are never filled with zeros.

![Synthetic randomized experiment showing judge means, audit adjustments within each group, corrected means, and the human-reference treatment effect with its confidence interval.](../assets/audit-workflow.png)

Informative scores can improve precision by accounting for outcome variation across the full sample. The human audit then estimates the remaining errors. The gain depends on those residuals; human-only analysis is a useful baseline.

The construction is established generalized-difference / augmented inverse-probability weighting (AIPW), related to [prediction-powered inference (PPI)](https://arxiv.org/abs/2301.09633) and [design-based supervised learning (DSL)](https://naokiegami.com/paper/dsl_ss.pdf). The package checks the declared sampling design and produces a local report with estimates and interpretation.

## Paired model evaluation: compare checkpoints on the same prompts

For model selection, evaluate two prespecified checkpoints or system prompts on the same prompts. Human reviewers rate both responses in each sampled pair. The correction operates on within-prompt differences and retains their dependence when estimating uncertainty.

![Synthetic paired checkpoint comparison: judge-only difference +0.50; human-reference correction −0.25 with an interval crossing zero.](../assets/paired-example.png)

The separate eight-pair synthetic fixture gives a judge-only difference of **+0.50**, a corrected difference of **−0.25**, and an asymptotic 95% interval of **−0.86 to +0.36**. It demonstrates pairing and report interpretation; its small sample does not validate coverage. This estimates a prompt-population mean quality difference, rather than a randomized causal effect or uncertainty conditional on a fixed benchmark archive.

## Where the comparison matters

| Field | Decision | Human outcome to define |
|---|---|---|
| Marketing | Replace a notice | Correct understanding of the rule and next step. |
| Enterprise AI | Roll out an assistant | Factual accuracy and task completion in written work. |
| Education | Choose tutoring feedback | Correct reasoning in an independently scored answer. |
| LLM evaluation | Select between two model versions | Response quality on paired prompts under a common rubric. |

These are possible uses; the examples do not document deployments. Each requires an appropriate design and a human rubric that measures the intended outcome.

## Run the package

With Python 3.10 or newer, from the repository root:

```bash
PYTHONPATH=src python -m llmaudit \
  --data examples/experiment.csv \
  --design examples/experiment_design.json \
  --output /tmp/llmaudit-experiment
```

For paired comparisons, use `examples/paired.csv`, `examples/paired_design.json`, and a different output prefix. The base package needs no API key or third-party runtime dependencies. Markdown reports show estimates, interpretation, audit coverage, and warnings; JSON retains structured results and provenance. The human-only baseline in the experiment figure is a documentation calculation, not an additional CLI feature.

Both modes assume IID units or pairs and independent Bernoulli audits with positive known probabilities and complete returns. Randomized mode requires independent Bernoulli assignment with a common known probability; paired audits require both ratings. Clustering, repeated outcomes, shared coder effects, fixed-size/adaptive audits, and inference for a fixed archive require another analysis. The interval concerns the specified human reference; it cannot establish that the rubric measures the intended construct.

[Experiment report](../../examples/experiment-report.md) · [Paired guide](../paired.md) · [Method and assumptions](../method.md) · [Example reproduction](../experiment-example.md)

## Citing this project

If you use `llmaudit` in research or an evaluation report, please cite the software and include the version or commit you used:

```bibtex
@software{Leng_llmaudit_2026,
  author = {Leng, Yan},
  title = {LLM Evaluation with Human Audits},
  year = {2026},
  version = {0.2.0.dev0},
  url = {https://github.com/yleng/llm-measurement-audit-release}
}
```

GitHub’s **Cite this repository** menu provides APA and BibTeX formats from [CITATION.cff](../../CITATION.cff). This citation is for the software; references for the underlying estimators are in the [method guide](../method.md).
