# Human-reference audit report

Reference: Fabricated 0-4 response-quality rubric. Units: points.

Matched prompts; checkpoint 1 minus checkpoint 0. IID prompt-population mean difference.

| Result | Estimate | Standard error |
|---|---:|---:|
| Human-reference correction | -0.25 | 0.313392 |
| AI-only score contrast | 0.5 | 0 |

Asymptotic 95% normal interval for the human-reference effect: [-0.864236, 0.364236].

## Interpretation

The interval includes zero: these data do not resolve the direction of the human-reference difference.

Read the estimate under the stated human rubric: higher scores mean improvement only if the rubric defines them that way. Use the interval to assess whether the data resolve a practically meaningful difference.

## Audit coverage

| Pairs | Audited pairs | Expected audited pairs | Max inverse probability | Weight ESS |
|---:|---:|---:|---:|---:|
| 8 | 4 | 4 | 2 | 4 |

Weight ESS is a descriptive concentration diagnostic, not the inferential sample size.

## Assumptions and limits

- Design declarations are user assertions; the CSV does not prove shared prompts, IID pairs, sampling, or rubric validity.
- Intervals are asymptotic IID prompt-population mean-difference intervals; fixed-archive conditional coverage is unsupported.
- Small prompt sample or pair audit count; normal intervals may be unreliable.
- Observed zero AI-only difference variance does not establish population certainty; normal inference can be degenerate.

The AI-only result compares judge scores. The corrected result targets the specified human-reference outcome.
