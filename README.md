# LLM Evaluation with Human Audits

**Estimate experiment effects and model differences when an LLM scores the outcomes.**

Many of us use LLM judges to score model responses, customer feedback, or written answers in experiments. They let us evaluate far more text than we could review by hand. But they also introduce measurement error: a judge may reward a longer or more polished answer even when a human would rate it no better. [Background on LLM judges and their biases](https://arxiv.org/abs/2306.05685).

That matters when we compare two groups or models. A higher average judge score may partly reflect the judge’s preferences rather than an improvement in the outcome we care about. Random assignment alone does not remove that scoring error.

I built `llmaudit` to help make these comparisons. It combines LLM scores for every response with human ratings from a probability sample, then reports the corrected difference and its uncertainty alongside the judge-only result.

[![Tests](https://github.com/yleng/llm-measurement-audit/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/yleng/llm-measurement-audit/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB)](pyproject.toml)
[![License: MIT](https://img.shields.io/badge/License-MIT-475569)](LICENSE)

## Example use cases

| Field | Decision | Human-defined outcome |
|---|---|---|
| Marketing | Replace a notice | Correct understanding of the rule and next step. |
| Enterprise AI | Roll out a writing assistant | Factual accuracy and task completion. |
| Education | Choose tutoring feedback | Correct reasoning in a student's answer. |
| LLM evaluation | Select between two model versions | Response quality on the same prompts. |

## Method intuition

![Synthetic randomized A/B test: judge-only effect +7.55 points, human-only −0.85, corrected +1.11. Both human-reference intervals include zero.](docs/assets/experiment-results.png)

In this **synthetic example**, the intervention has zero human-reference effect by construction, while the simulated judge gives its responses an eight-point bonus. The corrected effect is **+1.11 points, with a 95% interval of −0.28 to +2.50**: improvement remains unresolved.

Human-only analysis uses the same 366 sampled ratings. The correction has a narrower interval here, but its point estimate is farther from zero.

[Read the short article](docs/articles/randomized-experiments.md) · [Report](examples/experiment-report.md)

## Try it

Python 3.10 or newer. No API key or third-party runtime dependencies for the base package.

```bash
git clone https://github.com/yleng/llm-measurement-audit.git
cd llm-measurement-audit

PYTHONPATH=src python -m llmaudit \
  --data examples/experiment.csv \
  --design examples/experiment_design.json \
  --output /tmp/llmaudit-experiment
```

Open `/tmp/llmaudit-experiment.md` for results and interpretation, or `.json` for structured results and provenance. Existing files are never overwritten; use a new prefix on subsequent runs.

## How the human audit works

![Synthetic notice experiment: judge means of 50.2 and 57.7 receive audit adjustments of −0.2 and −6.6, giving corrected means of 50.0 and 51.1. The computed effect is +1.11 with a 95% interval crossing zero.](docs/assets/audit-workflow.png)

The human audit lowers the new-notice mean much more than the current-notice mean. Correct each group separately, then compare the corrected means.

The audit observes human-minus-judge discrepancies. Weight them by their known selection probabilities and add them to the full-sample scores before comparing groups. A 20% inclusion probability gives weight five.

### The estimator

In the default `frozen_score` mode, correct each response, then compare the randomized groups:

$$
\phi_i = S_i + \frac{R_i}{\pi_i}(H_i-S_i)
$$

$$
\widehat{\tau} = \overline{\phi}_1-\overline{\phi}_0
$$

$$
\mathrm{SE}(\widehat{\tau}) = \sqrt{\frac{s_1^2}{n_1}+\frac{s_0^2}{n_0}}
$$

- $S_i$ is the judge score; $H_i$ is the human rating.
- $R_i$ is 1 for a reviewed response and 0 otherwise; $\pi_i$ is its known audit probability.
- $\phi_i$ is the corrected contribution. In group $a$, $s_a^2$ is its sample variance and $n_a$ is the group size.

Unreviewed responses contribute their judge score directly; missing human ratings never enter the calculation. The standard error accounts for population outcome variability and audit uncertainty under the stated design.

The estimator uses established generalized-difference / augmented inverse-probability weighting (AIPW), related to prediction-powered inference (PPI) and design-based supervised learning (DSL). Informative scores can improve precision by leaving smaller discrepancies to estimate. [Equations and references](docs/method.md)

## Paired model evaluation and checkpoint comparisons

Evaluate both versions on the **same prompts** and human-rate both responses in each sampled pair. Paired inference preserves within-prompt dependence. It estimates the population mean quality difference across prompts.

Apply the correction to **within-prompt differences**, then average across prompts:

$$
\psi_i = D_i + \frac{R_i}{\pi_i}(G_i-D_i)
$$

$$
\widehat{\Delta} = \frac{1}{n}\sum_{i=1}^{n}\psi_i
$$

$$
\mathrm{SE}(\widehat{\Delta}) = \frac{s_{\psi}}{\sqrt{n}}
$$

$D_i=S_{i1}-S_{i0}$ is the candidate-minus-baseline judge-score difference; $G_i=H_{i1}-H_{i0}$ is the corresponding human-rating difference. $R_i$ and $\pi_i$ refer to selection of the complete pair. $s_{\psi}$ is the sample standard deviation of corrected pair differences, and $n$ is the number of prompts. Unreviewed pairs contribute $D_i$ directly.

For either comparison, the asymptotic 95% interval is the estimate $\pm 1.96\times\mathrm{SE}$.

Run the same command with `examples/paired.csv` and `examples/paired_design.json`, using a new output prefix. [Paired input guide](docs/paired.md) · [Paired report](examples/paired-report.md)

## Bring your data

Supply a **CSV** of scores, sampled human ratings, and known audit probabilities, plus a **design JSON** specifying the comparison and frozen rules. Raw response text is not needed. [Randomized-experiment inputs and Python API](docs/usage.md) · [Paired inputs](docs/paired.md)

Both modes require IID units or pairs, independent Bernoulli audits, positive known inclusion probabilities, and complete returns. Randomized mode requires independent Bernoulli assignment with a common known probability. Paired audits require both ratings. The package analyzes supplied scores and audits.

Intervals target population effects or mean differences. Fixed-size/adaptive audits, clusters, repeated outcomes, shared coder effects, and conditional inference for a fixed archive need another analysis. [Full assumptions](docs/method.md)

## Guides and integrations

- [Method](docs/method.md): measurement-error correction, variance, and inference scope.
- [Contributing](.github/CONTRIBUTING.md): tests and rebuilding figures.
- [Inspect adapter](integrations/inspect_ai/README.md): use completed evaluation logs with sampled human pair ratings; optional dependency.
- [PPI tutorial](integrations/ppi_py/README.md): a separate worked example using `ppi_py` APIs and independent labeled/unlabeled cohorts.

Install with `python3 -m pip install .` for the `llmaudit` command and Python API. [Attribution](docs/legal/NOTICE.md) · [MIT license](LICENSE) · [Citation](CITATION.cff)

## Citing this project

If you use `llmaudit` in research or an evaluation report, please cite:

```bibtex
@software{leng2026llmaudit,
  author = {Leng, Yan},
  title  = {llmaudit: human-audited inference for LLM-scored experiments and model comparisons},
  year   = {2026},
  note   = {Version 0.2.0.dev0.}
}
```

Use the version you ran, or include the commit hash for an untagged checkout. Machine-readable citation metadata is available in [CITATION.cff](CITATION.cff). This citation is for the software; references for the underlying estimators are in the [method guide](docs/method.md).
