# Human-reference audit report

Reference: Synthetic comprehension points; fabricated labels and scores. Units: illustrative points.

Arm 1 minus arm 0; IID superpopulation average treatment effect.

| Result | Estimate | Standard error |
|---|---:|---:|
| Human-reference correction | 1.11175 | 0.710283 |
| AI-only score contrast | 7.54523 | 0.471589 |

Asymptotic 95% normal interval for the human-reference effect: [-0.280374, 2.50388].

## Interpretation

The interval includes zero: these data do not resolve the direction of the human-reference difference.

Read the estimate under the stated human rubric: higher scores mean improvement only if the rubric defines them that way. Use the interval to assess whether the data resolve a practically meaningful difference.

## Audit coverage

| Arm | Units | Audited | Expected audited | Max inverse probability | Weight ESS |
|---|---:|---:|---:|---:|---:|
| 0 | 1036 | 200 | 207.2 | 5 | 200 |
| 1 | 964 | 166 | 192.8 | 5 | 166 |

Weight ESS is a descriptive concentration diagnostic, not the inferential sample size.

## Assumptions and limits

- Design declarations are user assertions; the CSV does not prove randomization, sampling, or rubric validity.
- Intervals are asymptotic IID superpopulation ATE intervals; fixed-archive conditional coverage is unsupported.

The AI-only result compares judge scores. The corrected result targets the specified human-reference outcome.
