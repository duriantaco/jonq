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
- `target_sources_without_peak` lists sources with at least one target record and no reported peak.
- `target_sources_with_peak_missing_target` lists sources that had a target record elsewhere in the capture but none in the selected peak.

Add `--baseline REFERENCE.ndjson` to report separate counts for review windows and windows within reference.

Use `--labels LABELED.ndjson` to score a matching copy while running the detector on input with both label fields removed. The benchmark checks event values and physical line positions before scoring. Each window's `first_input_line` and `first_displayed_evidence_label` refer to the first evidence line printed in the terminal. Both are `null` when the text preview omits the window. `earliest_input_line` is the lowest input line number among all evidence records in that window.

The benchmark runs once to warm up, then times a fresh CLI process for each measured run. Wall time includes startup, input parsing, analysis, and JSON output. The report gives median, minimum, and maximum times. On macOS and Linux it also gives peak child RSS including the warm-up. Label scoring happens outside the timed runs.

Use the included synthetic fixture to check the harness.

```bash
python tests/benchmark_connections.py tests/json_test_files/zeek_conn.ndjson \
  --src-cidr 192.0.2.10 --window 60 --min-destinations 3 --runs 5
```

The fixture has one qualifying peak. Its records have no labels, so the benchmark reports the window as `unconfirmed`.

### Replay the scan-lead accuracy cases

Run the bundled benign lookalike from the repository root.

```bash
python tests/replay_scan_leads.py --case benign-retries --runs 1
```

The fixture models a controller retrying HTTPS health checks across twelve peers. It should produce one benign-only lead. This is a check on a known false lead, so a change to the report needs review.

The [replay manifest](tests/scan_lead_replay_cases.json) lists the other inputs, source URLs, filenames, SHA-256 hashes, and expected results. Save each connection log under its listed filename in a local directory. For Hide and Seek, retrieve bytes 0–4194303 of the published file with an HTTP range request and save them as `hide-and-seek.prefix`. The replay discards any partial line at the end of that excerpt. Run all cases or use `--case` to select a subset.

```bash
python tests/replay_scan_leads.py --captures /path/to/captures --runs 5
```

The replay verifies each source hash before it runs. It converts the Zeek rows to two aligned NDJSON files and runs Jonq against the copy with label fields removed. The benchmark uses the labeled copy afterward and checks that its event fields and line positions match the detector input. Evidence line numbers refer to the converted NDJSON. The original Zeek UID is retained in that input.

The profile uses a 60-second window and a threshold of ten distinct peers. For each source and TCP destination port, the scorer checks whether the target-labeled rejections and unanswered records alone can meet that threshold. A selected window counts as a hit only when its target-labeled peers also meet the threshold. The report lists below-threshold groups, eligible groups without a lead, and eligible groups whose selected window misses the target threshold. It also scores the first line each lead actually shows in the terminal.

Benign-only leads per observed hour uses the span between the first and last in-scope connection records. The rate is unavailable when that span is zero. A window with unknown labels and no known target observations is unconfirmed. A hit requires the distinct-peer threshold to be met by known target observations. Timing and memory observations are reported separately from the replay assertions.

| Case | Observed result |
| --- | --- |
| Muhstik 3-1 | 1 of 1 eligible group surfaced. Its TCP/22 window covers 68 peers, including 67 distinct target-labeled peers. |
| Hide and Seek 1-1, first 4 MiB | 4 of 4 eligible groups surfaced. |
| Mirai 34-1 | 122 target-labeled records. The TCP observations reach one distinct peer, below the breadth threshold. |
| Echo, Hue, and Somfy first-start | Zero scan leads. The 1,561 benign connections in scope contained zero records eligible for scan review. |
| Synthetic HTTPS retries | One benign-only lead from twelve peers on TCP/443. |

These are outcomes for specific IoT-23 lab inputs and one synthetic fixture. The three benign lab inputs check filtering and the synthetic fixture checks a benign pattern that crosses the threshold. A source-and-port group may contain multiple episodes, and Jonq selects one peak window per group. Production alert rates and per-episode coverage need separate measurement. [IoT-23 dataset and label methodology](https://www.stratosphereips.org/datasets-iot23)

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
