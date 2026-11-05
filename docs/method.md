# Estimator, variance and scope

The package implements existing generalized-difference estimators for two designs: randomized two-arm experiments and paired prompt comparisons. Both use established methods for correcting measurement error.

## Randomized two-arm experiments

For unit i, A_i is randomized arm, H_i the human-reference score, S_i the frozen AI score, R_i the Bernoulli audit flag, and pi_i its known positive inclusion probability. H_i is observed only when R_i=1. Let m_i=S_i in the primary frozen-score route. Form:

```
phi_i = m_i + R_i * (H_i - m_i) / pi_i
tau_hat = mean(phi | A=1) - mean(phi | A=0)
SE² = sample_variance(phi | A=1)/n_1 + sample_variance(phi | A=0)/n_0
CI = tau_hat +/- NormalQuantile(1-alpha/2) * SE
```

The implementation branches on R before accessing H, so missing labels never enter arithmetic. It uses H without clipping and requires pi to be supplied. For full audits phi=H exactly, yielding the human contrast and the usual two-arm sample-variance SE. AI-only intervals use S and target the score contrast rather than the human-reference contrast.

## Why this variance belongs to this target

The target is E[H(1)]-E[H(0)] for an IID population under independent randomized treatment assignment. For a fixed predictor, E[phi|A]=E[H|A] when E[R|A,S,H]=pi(A,S) and pi is correct. Conditional on A and observed score/covariates, Bernoulli audit randomness adds `(1-pi)/pi * E[(H-m)^2 | A,S]` to the human-outcome variance after averaging over the population. The variance of phi therefore includes both population outcome variability and the audit residual variability. Estimating it with within-arm sample variances does not omit the nuisance residual term; adding a separate audit term to this sample-variance formula would double count that contribution.

Known random-assignment probability is recorded and validated. The estimator uses observed arm means (a ratio form), whose asymptotic influence is `A/e*(phi-mu_1) - (1-A)/(1-e)*(phi-mu_0)`; the reported arm-sample variance estimates its asymptotic variance. This is not a Horvitz–Thompson estimator for random assignment, and finite-sample unbiasedness under empty/random arm sizes is not claimed.

Conditional audit uncertainty for a fixed set of realized responses requires a separate design-based variance and a different interpretation. There is no fixed-population finite-sampling correction or exact randomization interval here.

## Paired prompt comparisons

For each IID prompt pair i, define the frozen judge-score difference `D_i = S_i1 - S_i0` and human-reference difference `G_i = H_i1 - H_i0`. Both responses are available for each prompt; both human ratings are observed only when that complete pair is selected for audit. Let `R_i` be the pair's independent Bernoulli audit flag and `pi_i` its known positive inclusion probability. Compute:

```
phi_i = D_i + R_i * (G_i - D_i) / pi_i
delta_hat = mean(phi)
SE² = sample_variance(phi) / n_pairs
CI = delta_hat +/- NormalQuantile(1-alpha/2) * SE
```

The target is `E[H_1 - H_0]` for the declared population of prompts under fixed checkpoint, response-generation, judge, and human-reference protocols. The comparison requires no randomized assignment between checkpoints and is not labeled a causal ATE. Conditional on the complete pair, `E[R_i | pair] = pi_i` gives `E[phi_i | pair] = G_i`. A policy may depend on observable prompt features and frozen scores, but not on unavailable human ratings; pair selections must follow the declared independent Bernoulli design, and both ratings must be returned for every selected pair.

For a fixed predictor and valid audit design:

```
Var(phi) = Var(G) + E[(1-pi)/pi * (G-D)²]
```

Sample variance of the corrected **pair differences**, divided by the number of pairs, includes population and audit uncertainty. In particular, `Var(G) = Var(H_1) + Var(H_0) - 2 Cov(H_1,H_0)`: treating the sides as independent would discard the within-prompt covariance. Adding a separate audit variance term to the implemented sample variance would double count audit uncertainty.

For `pi=1`, the implementation uses `G` directly to avoid numerical cancellation, so a complete audit gives the ordinary paired human mean and SE exactly. Unaudited pairs contribute `D`; missing human labels never enter arithmetic. The judge-only interval also uses paired differences. This mode uses frozen scores and does not fit calibration on the audit labels.

Inference requires IID prompt pairs, no dependence across pairs, and finite second moments of `phi`, including the weighted audit residual. Strictly positive probabilities alone do not guarantee stable inference. The stated interval is asymptotic prompt-population inference, not conditional audit-only coverage for a fixed archive. Repeated outputs per prompt, shared random coder effects, clustered users, incomplete pair audits, fixed-size or adaptive audit designs, and extrapolation to new prompt or coder populations require separate analysis. Frozen configuration assertions cannot verify shared prompts, representative sampling, or a valid rubric.

See the [paired guide](paired.md) for the exact input schema and required assertions.

## Optional held-out calibration (randomized mode only)

`crossfit_ridge` orders predetermined IDs by SHA-256 of a predeclared seed and ID, assigning folds cyclically within each arm. Neither label values nor audit counts choose or repair folds. For each arm and held-out fold, it uses only audited rows in other folds to fit `m(S)=intercept+slope*S`. Weights are `1/pi`; the intercept is unpenalized and the slope penalty is the fixed positive configuration value `ridge`. Prediction uses the weighted training means and centered weighted covariance divided by centered weighted score sum of squares plus ridge. It is conventional weighted affine ridge, with no tuning or model search.

At least three training audit labels are required in every arm/fold. Insufficient support fails the entire analysis; no same-fold fit, all-label fallback or score substitution occurs. At full auditing the correction still equals H regardless of fitted prediction.

The same SE formula is asymptotically appropriate only with fixed fold count, suitable finite moments/positivity, and calibration converging in L2 to a stable finite-variance limit. Cross-fitting removes own-fold training leakage; it does **not** by itself prove these regularity conditions or provide finite-sample independence of the pseudo-outcomes. Different folds share training data. No exact finite-sample coverage or variance unbiasedness is claimed. The minimum training count lets the software run; it does not establish that the fitted calibration is stable.

## Randomized-mode assumptions users must substantiate

- IID units and randomized assignment independent of potential outcomes, with common probability in (0,1); no interference or outcome-dependent attrition.
- The included frame is complete for the declared analysis; human-reference definition and scorer were frozen; scores exist for all included units.
- Independent Bernoulli audit selections with correct known probabilities, fixed before reference outcomes are inspected; conditional selection does not use unavailable H. All selected labels are returned under the fixed reference protocol.
- Suitable finite second moments and an audit probability floor sufficient for regular asymptotics. The software only requires representable positive pi and warns on concentrated weights; positivity alone is not a guarantee of stable inference.
- For cross-fitting: predetermined non-outcome-derived IDs and seed, fixed folds and stable nuisance fitting as above.

The report conditions on the specified human-reference protocol. A rubric can be wrong for the intended construct. Shared coder effects, inter-unit clustering, a new coder population, fixed-size or adaptive audit selection, and observational causal effects need a different implementation. Paired comparisons use the distinct route above. Typed assertions and data validation cannot establish these assumptions.

## References and comparison boundary

The equations are the conventional augmented inverse-probability/generalized-difference construction. Related established frameworks include [Prediction-Powered Inference](https://arxiv.org/abs/2301.09633), [Design-based Supervised Learning](https://papers.nips.cc/paper_files/paper/2023/file/d862f7f5445255090de13b825b880d59-Paper-Conference.pdf), [ppi_py](https://github.com/aangelopoulos/ppi_py), and [GLIDE](https://arxiv.org/abs/2605.31278). This is an independently written limited interface to that existing construction, not a claim to have invented it. No comparator-performance, prospective usability, cost-saving, or scientific-efficacy conclusion follows from the included arithmetic tests.
