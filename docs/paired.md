# Paired checkpoint comparisons

Use this mode when both checkpoints answer the same prompts. Each row contains one complete response pair. Checkpoint `0` is the baseline and checkpoint `1` is the candidate; a positive difference means the candidate scores higher under your rubric.

The target is the **population mean human-reference difference, checkpoint 1 minus checkpoint 0**, for the declared prompt population and fixed checkpoint, generation, and scoring protocols. Both outputs are observed, so randomized checkpoint assignment is unnecessary. The estimate describes a quality difference rather than a causal treatment effect.

## Prepare the audit

1. Freeze the checkpoint identities, generation settings, judge protocol, and human rubric. Keep their mapping to columns `0` and `1` in your evaluation manifest.
2. Obtain one response from each checkpoint for each independently sampled prompt. Score every response with the frozen judge. Keep all prompt pairs in the analysis frame.
3. Freeze a rule assigning a known positive audit probability to every pair. The rule may use observed prompt features or frozen scores. Select each pair independently by its recorded probability, without using unobserved human ratings. A constant probability such as 0.2 is a possible design, not a recommended audit budget.
4. Obtain both human ratings for every selected pair under the fixed rubric. Blind checkpoint identities and randomize presentation order where feasible. Shared random coder effects across pairs would require a different uncertainty calculation.
5. Reconcile the CSV with the generation and sampling manifests, then run the report. The package does not generate responses, draw the sample, or obtain the ratings.

A selected pair with one missing human rating is incomplete and is rejected. Do not change its audit flag to hide nonresponse. This mode does not accept separate response-level audit draws or a direct pairwise preference vote; supply two numeric ratings under the same rubric and the **pair's** inclusion probability.

## CSV columns

| Column | Meaning |
|---|---|
| `pair_id` | Unique, predetermined prompt ID; one row per prompt. |
| `ai_score_0` | Finite frozen judge score for the baseline response. |
| `ai_score_1` | Finite frozen judge score for the candidate response to the same prompt. |
| `audited` | Numeric `0` or `1`: selected for a complete-pair human audit. |
| `human_label_0` | Finite baseline human rating if audited; blank otherwise. |
| `human_label_1` | Finite candidate human rating if audited; blank otherwise. |
| `audit_probability` | Known pair inclusion probability in `(0,1]`, including unaudited pairs. |

Copy [examples/paired.csv](../examples/paired.csv). A probability of `1` requires an audited pair. Duplicate pair IDs, incomplete columns, nonfinite values, and partial or undeclared labels are rejected. If `scorer_version` is present, it must match `score_protocol`. Columns named `arm`, `cluster_id`, or `stratum` are rejected in this mode. Other extra columns are ignored; reports contain no pair IDs or raw records.

## Configuration

Copy [examples/paired_design.json](../examples/paired_design.json). All fields are required and unknown fields are rejected.

| Field | Required value or meaning |
|---|---|
| `comparison` | `"paired"` |
| `units` | `"iid_prompts"` |
| `audit` | `"independent_bernoulli"` |
| `audit_policy_frozen`, `scorer_frozen`, `reference_frozen`, `complete_audit_returns` | Each must be JSON `true`. |
| `score_protocol`, `human_reference`, `outcome_units` | Nonempty strings describing the judge, human protocol, and score units. |
| `mode` | `"frozen_score"` |
| `alpha` | Finite number in `(0,1)`; `0.05` gives a nominal 95% interval. |

Assignment probabilities and cross-fitting fields belong to the randomized mode and are rejected here. Paired calibration fitting is not implemented. At least two complete pairs and two fully audited pairs are required for arithmetic support; these minimums let the calculation run and are not sample-size recommendations.

## Run and interpret

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -m llmaudit \
  --data examples/paired.csv --design examples/paired_design.json \
  --output /tmp/llmaudit-paired-example
```

Choose an existing output directory and a new prefix. The command writes `PREFIX.json` and `PREFIX.md` and refuses to overwrite either file. Invalid data, unsupported designs, and output-write failures exit `2` without a completed new report pair.

The JSON report identifies `comparison: "paired"` and `method: "paired_generalized_difference"`. It reports `corrected` and `ai_only` estimates, standard errors and normal intervals, a `pairs` summary, design assertions, warnings, and input hashes. Pair count is the analysis sample size; the two responses are not counted as two independent units. Weight ESS is a descriptive concentration diagnostic.

The Python API is unchanged: load the CSV into a list of dictionaries, load the paired JSON into a dictionary, and call `from llmaudit import analyze; report = analyze(records, config)`. Input-file hashes are added by the CLI, not by the direct API.

Intervals describe uncertainty across IID prompts and pair-level audit selection. They are asymptotic and can be unreliable with few pairs, few audited pairs, or concentrated weights. A convenient fixed benchmark is not automatically an IID sample from the deployment population. The current interval is not a conditional audit-only interval for that fixed archive. You must also verify that both outputs use the same prompt and that pairs are independent. Unique IDs alone cannot establish either condition.

For equations and finite-variance assumptions, see [the method](method.md#paired-prompt-comparisons). The example is entirely synthetic and establishes arithmetic behavior only.
