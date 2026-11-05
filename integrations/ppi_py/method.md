# Statistical design and reproduction

The example uses established PPI through `ppi_mean_pointestimate` and `ppi_mean_ci`, with fixed `lam=1`. It introduces no new estimator. Two independent IID cohorts follow the same Bernoulli randomized assignment with probability 0.5: 800 labeled and 4,000 unlabeled units. Seeds 601 and 602 are fixed without choosing a favorable result.

Human scores are `H = 50 + Normal(0,10²)`, with identical potential human outcomes under either treatment. Judge scores are `S = H + 8A + Normal(0,3²)`. These are unbounded illustrative points, not a validated comprehension scale. Unlabeled human outcomes are deleted before estimation.

Within each arm, PPI adds the mean human-minus-judge residual in the labeled sample to the mean prediction in the unlabeled sample. It receives predictions from the separate unlabeled cohort, rather than the full frame. Overlapping labeled/unlabeled samples invalidate this tutorial's independence argument. Human ratings must align with their corresponding predictions.

Each arm receives an asymptotic 97.5% interval (`alpha=0.025`). The contrast interval is `[lower_1-upper_0, upper_1-lower_0]`. Bonferroni gives conservative nominal 95% asymptotic coverage if the component intervals have their stated asymptotic validity. The human-only baseline uses the same conservative armwise interval construction. Judge-only uses an ordinary two-arm normal interval for its own score target. Their intervals need not have identical widths or target the same outcome.

Valid intervals require the stated IID design, a stable reference rubric, fixed predictions, and suitable moments and sample sizes. This single draw cannot validate coverage, typical superiority, or annotation savings.

Run the companion checks from the repository root:

```sh
python -m unittest discover -s integrations/ppi_py -q
```

Rebuild the self-contained notebook and capture its code-cell output with `python docs/scripts/build_ppi_notebook.py`. Rebuild the README figures with `python docs/scripts/render_integration_figures.py` in a documentation environment with matplotlib installed. Figure rendering adds no runtime dependency.
