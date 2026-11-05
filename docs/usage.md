# Randomized-experiment input, configuration, and API guide

This guide covers the original randomized two-arm mode. For two checkpoints answering the same prompts, use the separate [paired comparison guide](paired.md). See the [README](../README.md) for both workflows, and the [method](method.md) for equations and assumptions.

## Supported design and target

- Independent, identically distributed (IID) units; one response per unit, with no inter-unit interference.
- Two groups, with each unit independently randomized to an arm using a common known assignment probability strictly between zero and one.
- A frozen score protocol and specified frozen human-reference rubric.
- Independent Bernoulli audits with known positive inclusion probabilities for every unit. The fixed policy may depend on observed arm and score. Every selected label must be returned.
- Target: the **superpopulation average treatment effect on the specified human-reference score**, arm 1 minus arm 0. Equality with a latent construct effect needs additional substantive assumptions.

The primary `frozen_score` route uses the supplied score as a fixed predictor. Optional `crossfit_ridge` fits a separate affine calibration in each arm, with strict held-out folds and no training fallback. It adds nuisance-stability assumptions and is an experimental option.

Fixed-size samples, clusters, stratified designs, adaptive audits, observational effects, population generalization to new coders, and conditional inference for a fixed archive are unsupported. Paired comparisons require the separate paired input and configuration. Configuration assertions do not prove how an experiment or audit was performed.

## CSV columns

| Column | Meaning |
|---|---|
| `record_id` | Unique, predetermined unit ID. |
| `arm` | Numeric `0` or `1`. The effect is arm 1 minus arm 0. |
| `ai_score` | Finite frozen score for **every** frame unit. |
| `audited` | Numeric `0` or `1`: selected for the declared audit. |
| `human_label` | Finite label when audited; blank otherwise. |
| `audit_probability` | Known design probability in `(0,1]`, including unaudited rows. Never estimated from observed fractions. |

If `scorer_version` is supplied, every row must equal the configuration's `score_protocol`. Cluster, pair, and stratum columns are rejected. Other extra columns are ignored; reports do not export records or IDs. Raw response text is not needed.

Include the complete analysis frame. The tool cannot detect an omitted unit or a falsely changed audit flag from the CSV alone: reconcile the file with your frozen frame and sampling manifest first. Human nonresponse cannot be repaired by changing a selected unit to `audited=0`.

## Configuration

Copy [examples/design.json](../examples/design.json). Every listed key is required; unknown keys are rejected.

| Field | Required value or meaning |
|---|---|
| `units` | `"iid"` |
| `assignment` | `"bernoulli_randomized"` |
| `assignment_probability` | Common probability of arm 1; finite and strictly between 0 and 1. |
| `audit` | `"independent_bernoulli"` |
| `audit_policy_frozen` | JSON `true`. |
| `scorer_frozen` | JSON `true`. |
| `reference_frozen` | JSON `true`. |
| `complete_audit_returns` | JSON `true`; asserts complete labels for all originally selected units. |
| `score_protocol` | Nonempty text identifying the frozen scoring protocol. |
| `human_reference` | Nonempty text describing the specified human rubric/protocol. |
| `outcome_units` | Nonempty text, such as `"comprehension points"`. |
| `mode` | `"frozen_score"` or `"crossfit_ridge"`. |
| `alpha` | Finite number strictly between 0 and 1; `0.05` gives a nominal 95% interval. |
| `folds` | Integer at least 2; required in both modes, used for cross-fitting. |
| `fold_seed` | Nonempty, predeclared string; required in both modes. |
| `ridge` | Finite positive number; required in both modes, used for calibration. |

Both modes require at least two audited labels per arm and two units per arm. These are arithmetic support checks, **not** adequacy recommendations. Cross-fitting additionally requires at least three audited training labels in every arm/fold and at least `folds` units per arm. IDs and the fold seed must be fixed independently of scores, labels, and audit selection. No missing-label imputation, probability inference, clipping, or fold repair occurs.

## CLI and reports

From the repository root:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -m llmaudit \
  --data examples/synthetic.csv --design examples/design.json \
  --output /tmp/llmaudit-example
```

Use an existing output directory and a new prefix. The command writes `PREFIX.json` and `PREFIX.md` and refuses to overwrite either file. Prefixes containing a dot retain that dot.

JSON contains design assertions, estimates, normal intervals, arm sizes, actual/expected audit counts, maximum inverse probabilities, descriptive weight ESS, warnings, package version, and SHA-256 hashes of both input files. Markdown explains the results without row-level data.

Small samples, concentrated weights, and zero empirical variance generate warnings; passing checks does not ensure reliable inference. The report estimates effects under the declared human rubric. Launch decisions, construct validity, and review-cost savings need separate evidence.

CLI success exits `0`; invalid input, unsupported design, or output-write failure exits `2` without a completed new report pair. The CLI does not run models or draw the audit sample.

## Python API

Install from the repository with `python3 -m pip install .`, or set `PYTHONPATH=src` when running your script.

```python
import csv
import json
from llmaudit import analyze

with open("examples/synthetic.csv", newline="") as source:
    records = list(csv.DictReader(source))
with open("examples/design.json") as source:
    config = json.load(source)

report = analyze(records, config)
print(report["corrected"])
```

The library raises `ValueError` for invalid or unsupported data. Input file hashes are added by the CLI; the direct `analyze` result contains the statistical report without those file hashes.

## Verification

```bash
PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \
VECLIB_MAXIMUM_THREADS=1 NUMEXPR_NUM_THREADS=1 TOKENIZERS_PARALLELISM=false \
python -m unittest discover -s tests -v
```

Tests cover hand-calculated estimates/variance, full-audit equivalence, unequal probabilities, strict held-out behavior, numerical failures, invalid inputs, and CLI outputs. These checks establish engineering behavior; empirical efficacy, confidence-interval coverage, saved human hours, and better organizational decisions require separate validation.
