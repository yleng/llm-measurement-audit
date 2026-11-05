# Inspect adapter validation

Both JSON and `.eval` logs are tested with Inspect 0.3.287 on Python 3.12, using official `read_eval_log` and `write_eval_log` APIs. The fixtures are entirely fabricated and were generated with SDK models; no responses or judge ratings were obtained from an API.

Run the SDK tests from the repository root:

```sh
PYTHONPATH=src python -m unittest discover -s integrations/inspect_ai -q
```

Rebuild fixture logs with `python integrations/inspect_ai/build_fixture.py`. Rebuild documentation figures with `python docs/scripts/render_integration_figures.py` in a documentation environment with matplotlib installed. Plotting adds no base runtime dependency.

The eight-pair fixture produces a judge-only mean difference of +0.50, a human-reference corrected mean of −0.25, and an asymptotic 95% interval of approximately [−0.86, +0.36]. The report retains its small-sample and zero observed judge-variance warnings. This validates the conversion and calculation, rather than interval coverage or practical benefits.

The adapter uses the public log API as a local postprocessor. It is not a registered Inspect scorer/plugin or part of Inspect core. See the input guide for supported data and sampling requirements.
