# Contributing

Open an issue with a minimal synthetic example, the package version, and the expected and observed behavior. Keep private evaluation records, participant data and credentials out of issues and pull requests.

For a code change, include a focused regression test and run:

```sh
PYTHONPATH=src python3 -m unittest discover -s tests -q
```

Explain any changes to the statistical target, score interpretation, exclusions or report schema. Synthetic tests establish software behavior; empirical usefulness requires separate evidence.

## README preview

`docs/scripts/render_readme_preview.py` runs the paired synthetic example and rebuilds the report snapshots in `examples/` and the visual summaries in `docs/assets/`. Run it after changing the example or report format:

```sh
python3 docs/scripts/render_readme_preview.py
```

Rendering requires matplotlib in your documentation environment; it is not a package runtime dependency. The illustration must use computed results and retain its synthetic-data label. Keep the full generated report available next to the visual summary.

`python3 docs/scripts/render_experiment_example.py` rebuilds the randomized-experiment CSV, report, summary, and article figures. See [reproduction details](../docs/experiment-example.md) for the fixed data-generating process and the human-only documentation baseline. The baseline is not an additional CLI output.

The workflow and equation figures are rebuilt with `python3 docs/scripts/render_audit_workflow.py` and `python3 docs/scripts/render_readme_math.py`. Figure typography uses modest headings and body-sized labels for display inside the README. Release file hashes live in `docs/release/MANIFEST.sha256.json`; paths are relative to the repository root.
