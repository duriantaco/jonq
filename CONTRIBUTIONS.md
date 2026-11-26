# Contributing to jonq

Thanks for your interest in helping with jonq! Here's how you can contribute:

## Quick Start

1. Fork the repo
2. Clone your fork: `git clone https://github.com/duriantaco/jonq.git`
3. Install for development: `pip install -e ".[dev]"`
4. Install hooks: `pre-commit install --install-hooks`
5. Install docs dependencies when editing docs: `pip install -r docs/requirements.txt`

## How to Contribute

### Reporting Bugs
- Check if the bug is already reported
- Include clear steps to reproduce
- Mention your environment (Python version, OS)

### Submitting Changes
1. Create a branch: `git switch -c fix-something`
2. Make your changes
3. Run tests: `pytest`
4. Build docs when documentation changed: `python -m sphinx -b html docs/source /tmp/jonq-docs`
5. Commit with a clear message
6. Push to your fork
7. Open a pull request

### Code Style
- Run `pre-commit run --all-files` before pushing
- Follow PEP 8 basics
- Include docstrings for functions and classes

## Testing
Run `pytest` before submitting your changes.

### Benchmark connection reports

From the repository root, point the benchmark at a local NDJSON export and scope it to the host you want to evaluate. For labeled captures, preserve the `label` and `det_label` fields when converting to NDJSON.

```bash
python tests/benchmark_connections.py CAPTURE.ndjson \
  --src-cidr HOST --window 60 --min-destinations 10 --runs 5
```

The benchmark runs `jonq connections` on all in-scope records. It reads labels after analysis to score the original lines in each reported peak. By default all records labeled `Malicious` are targets. To evaluate one category, add `--target-detail PartOfAHorizontalPortScan` or `--target-detail 'C&C'`. The flag matches `det_label` exactly and can be repeated to include multiple categories. [IoT-23 label definitions](https://www.stratosphereips.org/datasets-iot23)

The regular report contributes at most one peak window per source. Add `--scan-leads` to score peaks by source and TCP destination port using only rejected or unanswered attempts. The same input labels and time window apply in both modes. The JSON result includes label counts and an assessment for each selected window.

- `target_in_window` when the window contains at least one target record, including windows with mixed labels.
- `benign_only` when every record in the window is labeled benign.
- `unconfirmed` when the window has no target records and includes other or unlabeled records.
- `target_sources_without_peak` lists sources that had a target record but never met the threshold.
- `target_sources_with_peak_missing_target` lists sources that had a target record elsewhere in the capture but none in the selected peak.

Add `--baseline REFERENCE.ndjson` to report separate counts for review windows and windows within reference.

The benchmark runs once to warm up, then times a fresh CLI process for each measured run. Wall time includes startup, input parsing, analysis, and JSON output. The report gives median, minimum, and maximum times. On macOS and Linux it also gives peak child RSS including the warm-up. Label scoring happens outside the timed runs.

Use the included synthetic fixture to check the harness.

```bash
python tests/benchmark_connections.py tests/json_test_files/zeek_conn.ndjson \
  --src-cidr 192.0.2.10 --window 60 --min-destinations 3 --runs 5
```

The fixture has one qualifying peak. Its records have no labels, so the benchmark reports the window as `unconfirmed`.

## Documentation
Keep `README.md`, `USAGE.md`, `SYNTAX.md`, and the Sphinx docs in `docs/source/`
in sync when changing CLI behavior, query syntax, output formats, or the Python
API.

## Releases
Maintainers publish from GitHub Releases:

1. Update `pyproject.toml`, `jonq/constants.py`, and `CHANGELOG.md`
2. Open and merge the release prep PR
3. Create a GitHub Release for the version tag
4. The release workflow builds the package and publishes it to PyPI

PyPI publishing uses trusted publishing, so the PyPI project must allow this
repository and the `pypi` GitHub environment.

## Need Help?
Open an issue with your question!

Thanks for contributing!
