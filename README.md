# jonq

<img src="docs/source/_static/jonq.png" alt="" width="96" align="right" />

Inspect and reshape JSON with a jq-powered CLI. Explore unfamiliar payloads, write SQL-like queries, and export a table, CSV, or JSONL. You can also check JSON shape in CI and review saved network logs with evidence tied to the original input.

[Try from source](#from-source) · [Network log commands](#network-log-triage) · [MCP setup](#local-mcp-server) · [JSON quick start](#quick-start) · [Documentation](https://jonq.readthedocs.io) · [PyPI releases](https://pypi.org/project/jonq/) · [CI](https://github.com/duriantaco/jonq/actions)

## Recorded Network Traffic

### Review a connection lead

![Terminal scan lead report with a UTC interval, recorded TCP outcomes, and an input line to review.](docs/source/_static/jonq-scan.png)

The report comes from recorded CTU lab traffic during a controlled Muhstik capture. It shows 68 destination IPs on TCP/22 and points to line 11,912 of the NDJSON export for a recorded attempt. Of the 117 records in the lead, the dataset labels associate 116 with a horizontal port scan and one with benign traffic. [CTU IoT-23 capture 3-1](https://mcfp.felk.cvut.cz/publicDatasets/IoT-23-Dataset-v2/CTU-IoT-Malware-Capture-3-1/), [published Zeek log](https://mcfp.felk.cvut.cz/publicDatasets/IoT-23-Dataset/IndividualScenarios/CTU-IoT-Malware-Capture-3-1/bro/), [IoT-23 label methodology](https://www.stratosphereips.org/datasets-iot23)

### Summarize recorded alerts

![Terminal report listing Suricata alert signatures, counts, and original input lines.](docs/source/_static/jonq-triage.png)

`jonq triage` summarizes alert signatures already present in the Suricata EVE log from a controlled Mirai capture. Each signature points to a matching input line and shows its recorded timestamp when available. [CTU IoT-23 capture 34-1](https://mcfp.felk.cvut.cz/publicDatasets/IoT-23-Dataset-v2/CTU-IoT-Malware-Capture-34-1/), [published Suricata logs](https://mcfp.felk.cvut.cz/publicDatasets/IoT-23-Dataset/IndividualScenarios/CTU-IoT-Malware-Capture-34-1/suricata/)

## From Source

Use this checkout for the examples below and the network log commands. jonq requires Python 3.9+. SQL-like queries use the `jq` command-line tool.

```bash
git clone https://github.com/duriantaco/jonq.git
cd jonq
python -m pip install -e .
```

Run both reports from the repository root using the included sample logs.

```bash
zeek=tests/json_test_files/zeek_conn.ndjson
eve=tests/json_test_files/suricata_eve.ndjson
jonq connections "$zeek" --scan-leads --min-destinations 2
sed -n '1p' < "$zeek"
jonq triage "$eve"
sed -n '6p' < "$eve"
```

The scan report highlights two destination IPs on TCP port 443 and cites line 1. The alert report summarizes three recorded events across two alert types and cites line 6 for the first signature. With a named file on macOS or Linux, both reports show a shell command to open the cited line. Run `jonq connections --help` or `jonq triage --help` to see the available options.

## Install

Install a published release from PyPI. For the current inspection workflow and network log commands shown here, [install from source](#from-source).

```bash
pipx install jonq
# or
pip install jonq
```

Check that `jq` is available before running SQL-like queries.

```bash
jq --version
```

## Quick Start

Save a sample API response with users inside a `users` array.

```bash
cat > response.json <<'JSON'
{
  "meta": {"total": 3},
  "users": [
    {"id": 1, "name": "Alice", "age": 30, "city": "New York"},
    {"id": 2, "name": "Bob", "age": 25, "city": "Los Angeles"},
    {"id": 3, "name": "Charlie", "age": 35, "city": "Chicago"}
  ]
}
JSON
```

Inspect the file or pipe the same JSON to find paths such as `users[].name` and a suggested query using `from users`.

```bash
jonq response.json
cat response.json | jonq
```

Use `from users` to choose the array to query. Preview the result as a table, then save it as CSV.

```bash
jonq response.json "select age, name from users where age > 30" -t
jonq response.json "select age, name from users where age > 30" --format csv --out older-users.csv
```

`older-users.csv` contains one matching row.

```csv
age,name
35,Charlie
```

Create `users.json` for the examples that follow.

```bash
jonq response.json "select * from users" --out users.json
```

Select fields:

```bash
jonq users.json "select name, age"
```

Filter rows:

```bash
jonq users.json "select name, age if age > 30"
```

In a `where` filter, an ordered comparison against a number matches JSON number values. For example, `age > 30` skips missing ages and ages stored as strings.

Print raw values for shell pipelines:

```bash
jonq users.json "select name" -r
```

Render a table:

```bash
jonq users.json "select name, city, age sort age desc" -t
```

Get unique values:

```bash
jonq users.json "select distinct city"
```

Aggregate:

```bash
jonq users.json "select count(*) as total, avg(age) as avg_age"
```

See what jq will run:

```bash
jonq users.json "select name if age > 30" --explain
```

## Query Syntax

```text
select [distinct] <fields>
  [from <path>]
  [if|where <condition>]
  [group by <fields> [having <condition>]]
  [sort <field> [asc|desc]]
  [limit N]
```

Examples:

```bash
jonq users.json "select *"
jonq users.json "select name as full_name, age"
jonq users.json "select name if city in ('New York', 'Chicago')"
jonq users.json "select name where age > 30"
jonq users.json "select name if not age > 30"
jonq users.json "select name if name like 'Al%'"
jonq users.json "select name if age between 25 and 35"
jonq users.json "select city, count(*) as count group by city"
jonq users.json "select city, avg(age) as avg_age group by city having avg_age > 30"
jonq users.json "select name, age sort age desc limit 2"
```

## Fields and Expressions

Create a sample with nested fields, an array, and optional values.

```bash
cat > details.json <<'JSON'
[
  {
    "name": "Alice",
    "nickname": null,
    "notifications": false,
    "profile": {"email": "alice@example.com", "address": {"city": "New York"}},
    "orders": [{"order_id": 42, "item": "Monitor", "price": 150}]
  }
]
JSON
```

Select nested fields with dot notation.

```bash
jonq details.json "select profile.email, profile.address.city"
```

Select rows from the Quick Start response or from arrays inside each user.

```bash
jonq response.json "select id, name from users"
jonq details.json "select order_id, price from [].orders if price > 100"
```

`from [].orders` makes each order a row. For a root array, use `from []` to select a parent field while expanding one child array. Query independent child arrays separately. [See the nested array syntax](SYNTAX.md#nested-arrays-with-from).

Use an array index to select the first order.

```bash
jonq details.json "select name, orders[0].item as first_order"
```

Use functions and expressions to transform values or add a derived column.

```bash
jonq users.json "select upper(name) as name, str(age) as age"
jonq users.json "select name || ' (' || city || ')' as label"
jonq users.json "select age * 2 + 3 as score"
jonq details.json "select coalesce(nickname, name) as display, coalesce(notifications, true) as notifications"
jonq users.json "select case when age > 30 then 'senior' else 'junior' end as segment"
```

`coalesce` falls back on `null` or a missing field. It preserves the `false` value for `notifications`.

Common functions:

| Category | Functions |
|----------|-----------|
| Strings | `upper`, `lower`, `length`, `trim`, `ltrim`, `rtrim` |
| Math | `round`, `abs`, `ceil`, `floor` |
| Casting | `int`, `float`, `str`, `string`, `type` |
| Dates | `todate`, `fromdate`, `date`, `timestamp` |
| JSON/arrays | `keys`, `values`, `tojson`, `fromjson`, `reverse`, `sort`, `unique`, `flatten` |
| Nulls | `coalesce`, `is null`, `is not null` |

## Output Formats

JSON is the default. Query results go to stdout and error messages go to stderr.

```bash
jonq users.json "select name, age"
```

Table:

```bash
jonq users.json "select name, age, city" -t
jonq users.json "select name, age, city" --format table
```

CSV:

```bash
jonq users.json "select name, age" --format csv > users.csv
```

JSONL:

```bash
jonq users.json "select name, age" --format jsonl > users.jsonl
```

YAML:

```bash
jonq users.json "select name, age" --format yaml
```

Raw scalar values:

```bash
jonq users.json "select name" -r
```

## Input Sources

Local file:

```bash
jonq data.json "select id, name"
```

Piped stdin:

```bash
curl -s https://api.example.com/users | jonq "select id, name" -t
cat data.json | jonq "select id, name where active = true"
cat data.json | jonq - "select id, name"
```

URL:

```bash
jonq https://api.example.com/users.json "select id, email"
```

Glob:

```bash
jonq 'logs/*.json' "select * if level = 'error'"
```

NDJSON file:

```bash
jonq app.ndjson
jonq app.ndjson "select level, message if level = 'error'"
```

Use `--ndjson` to make the input format explicit when piping records.

```bash
cat app.ndjson | jonq --ndjson "select level, message"
```

Follow live NDJSON from stdin:

```bash
tail -f app.ndjson | jonq --follow "select level, message if level = 'error'" -t
```

## Inspect Before Querying

Run jonq with no query to inspect shape, fields, sample values, and suggested queries:

```bash
jonq data.json
```

Example output:

```text
data.json
Root: array of objects (sampled 3 items)

Fields:
  id    number  sample: 1
  name  string  sample: "Alice"
  age   number  sample: 30
  city  string  sample: "New York"

Sample:
  {
    "id": 1,
    "name": "Alice",
    "age": 30,
    "city": "New York"
  }

Suggested queries:
  jonq data.json "select id, name, city" -t
  jonq data.json "select name" -r
  jonq data.json "select city, count(*) as count group by city" -t
```

## Profile, Diff, And Check

Use `profile` when you need more than the quick no-query inspect view:

```bash
jonq profile response.json
```

It reports each discovered path, inferred types, present count, null count, missing count, and a sample value. Use JSON output when another tool needs the profile:

```bash
jonq profile response.json --format json
```

Compare two payload shapes with `diff`:

```bash
jonq diff old-response.json new-response.json
jonq diff old-response.json new-response.json --fail-on-change
```

Run one-off checks from flags:

```bash
jonq check response.json \
  --require id,email,status \
  --type id:number \
  --type email:string \
  --no-null id,email \
  --min-count 1
```

Or save queries and checks in `jonq.yaml`:

```yaml
queries:
  active_users:
    source: users.json
    query: select id, email, status if status = 'active'
    format: table

checks:
  user_contract:
    source: users.json
    require:
      - id
      - email
      - status
    types:
      id: number
      email: string
      status: string
    no_null:
      - id
      - email
    min_count: 1
```

Then run the saved workflow:

```bash
jonq run active_users
jonq check user_contract
jonq check --all
```

## Network Log Triage

`jonq triage` uses Python to summarize alert signatures and flag repeated firewall denials by source IP in an NDJSON export. It accepts Suricata EVE alert records and firewall records with `event_type: firewall`, `src_ip`, and `action`. [Install from source](#from-source) to try it.

```bash
jonq triage eve.json
jonq triage - --min-denials 10 --format json < firewall.ndjson
```

Use `-` to read stdin. The denial threshold defaults to five and counts across the entire input, so use a bounded export for each review period. The counts help you decide which events to inspect. Malformed records produce line diagnostics and exit status `1` while valid records still contribute to the report. [Try the cookbook examples](docs/source/cookbook.rst#triage-network-logs).

The JSON alert summary keeps up to two source lines per signature. Use the cookbook example to verify those records and export the citations to CSV. [Export alert evidence](docs/source/cookbook.rst#triage-network-logs)

Both network reports use color in a terminal. Pass `--no-color` or set `NO_COLOR=1` for plain text.

`jonq connections` reads a Zeek connection log exported as newline-delimited JSON or Suricata EVE flow records. It groups records by IP pair, shows a count for each direction, and reports each qualifying source's peak distinct destination count in a rolling window. The default window is 60 seconds and the default threshold is 10 destinations. To replay a published IoT-23 tab-separated Zeek capture, use the converter in the [accuracy replay](CONTRIBUTIONS.md#replay-the-scan-lead-accuracy-cases).

```bash
jonq connections conn.ndjson --src-cidr 192.0.2.0/24 --min-destinations 3
jonq connections conn.ndjson --baseline previous.ndjson --min-destinations 3
jonq connections conn.ndjson --scan-leads --src-cidr 192.0.2.0/24
```

The terminal report puts findings and their UTC windows first. It groups recorded outcomes by protocol and destination port and points to an original input line to inspect. A baseline compares peak destination counts and shows which destinations in the current peak are absent from the reference. Use `--format json` for the full set of evidence records and service groups.

`--scan-leads` shows when a source tried to reach enough different destination IPs on one TCP port within a short window. Repeated records for one destination count once toward that threshold. Open the cited line and check whether the host was expected to contact those addresses and that port at the reported time. Scheduled health-check retries can produce the same pattern. Each run accepts at most one of `--scan-leads` and `--baseline`. [Try the scan lead example](docs/source/cookbook.rst#review-horizontal-scan-leads).

The replay checks labeled lab logs and a synthetic benign retry pattern at fixed thresholds. [Run the accuracy replay](CONTRIBUTIONS.md#replay-the-scan-lead-accuracy-cases)

Pass a bounded export or use `-` for stdin. [Try the connections cookbook example](docs/source/cookbook.rst#review-connection-activity).

## Local MCP Server

Use `jonq mcp` to give a local MCP client read-only access to the network reports. From the repository root, get the paths for a client config that uses the bundled samples.

```bash
command -v jonq
printf '%s\n' "$PWD/tests/json_test_files"
```

Set the first path as the command and pass `mcp --log-root` followed by the second path as arguments. Call `triage` with `{"path":"suricata_eve.ndjson"}` or `connections` with `{"path":"zeek_conn.ndjson","scan_leads":true,"min_destinations":2}`. [Copyable client setup and options](docs/source/mcp.rst).

## Streaming and Watch Modes

Streaming mode reads a local root-array JSON file incrementally and runs the query in chunks.

```bash
jonq large.json "select id, name if active = true" --stream
```

Field checks still run before execution. The CLI stages JSON, JSONL, and raw results on disk and publishes them after successful processing. CSV, table, YAML, and Python API results are assembled in memory. An individual large record can still use substantial memory.

Streaming is for row-wise queries. It intentionally rejects queries that require global input state, including `group by`, `sort`, `distinct`, `limit`, `count`, `sum`, `avg`, `min`, `max`, and `count(distinct ...)`.

Watch mode reruns a query when a file changes:

```bash
jonq data.json "select name, age" --watch
```

Interactive mode provides history and field-aware completion:

```bash
jonq -i data.json
```

## Python API

Use `query(...)` when you want Python data back:

```python
from jonq import query

data = [
    {"name": "Alice", "age": 30},
    {"name": "Bob", "age": 25},
]

rows = query(data, "select name if age > 26")
print(rows)
```

Use `execute(...)` when you want text output plus metadata:

```python
from jonq import execute

result = execute(data, "select name, age", format="jsonl")
print(result.text)
print(result.compiled.jq_filter)
```

Compile once and reuse:

```python
from jonq import compile_query, query

compiled = compile_query("select name if age > 25")
print(query([{"name": "Alice", "age": 30}], compiled))
```

Async helpers are also available: `query_async(...)` and `execute_async(...)`.

## CLI Options

Workbench commands:

| Command | Description |
|---------|-------------|
| `jonq profile FILE` | Show field paths, types, present/null/missing counts, and samples |
| `jonq diff OLD NEW` | Compare two JSON profiles and show shape drift |
| `jonq check [NAME\|FILE]` | Run named checks from `jonq.yaml` or inline flag-based checks |
| `jonq run NAME` | Run a named query from `jonq.yaml` |
| `jonq triage [FILE\|-]` | Summarize alert signatures and repeated firewall denials in NDJSON |
| `jonq connections [FILE\|-]` | Summarize IP pairs and peak distinct destination counts in Zeek or EVE logs |
| `jonq mcp --log-root DIR` | Serve the two network log reports to a local MCP client over stdio |

Query options:

| Option | Description |
|--------|-------------|
| `-f, --format {json,jsonl,csv,table,yaml}` | Output format |
| `-t, --table` | Shorthand for `--format table` |
| `-r, --raw, --raw-output` | Print scalar values without JSON quoting |
| `-s, --stream` | Chunk-safe streaming for root-array JSON |
| `--ndjson` | Force NDJSON mode |
| `--follow` | Process NDJSON from stdin line-by-line |
| `-n, --limit N` | Limit rows after query execution |
| `-o, --out PATH` | Write output to a file |
| `--jq` | Print the generated jq filter and exit |
| `--explain` | Show parsed query details and generated jq |
| `--time` | Print parse/execute/format timing to stderr |
| `-p, --pretty` | Pretty-print JSON output |
| `-w, --watch` | Rerun when the input file changes |
| `--no-color` | Disable terminal color |
| `--completions {bash,zsh,fish}` | Print shell completions |
| `--version` | Print version |
| `-i FILE, --interactive FILE` | Start the REPL |

## Shell Completions

```bash
# Bash
eval "$(jonq --completions bash)"

# Zsh
eval "$(jonq --completions zsh)"

# Fish
jonq --completions fish > ~/.config/fish/completions/jonq.fish
```

## Troubleshooting

- **`jq` is not found**: Install jq and make sure it is on `PATH`.

- **No query was provided**: Run `jonq data.json` to inspect the file, or pass a query such as `jonq data.json "select *"`.

- **A field is missing or misspelled**: jonq validates fields in selections, filters, sorting, grouping, and aggregations, then suggests close matches and a copy-paste `Try:` command.

- **Streaming mode rejected a query**: Use non-streaming mode for global operations like aggregation, grouping, sorting, distinct, or limit.

- **The generated jq looks surprising**: Run the same command with `--explain` to see the parsed query and generated jq filter.

## Known Limitations

- jonq exposes a practical subset of jq, not the full jq language.
- Streaming mode supports row-wise queries only.
- Joins, SQL window functions, and relational analytics are outside the query language.
- URL fetch is a convenience feature, not a full HTTP client.
- Very large files can still be slow if the query requires full-input state.

## Documentation

- Full docs: https://jonq.readthedocs.io/en/latest/
- Cookbook: https://jonq.readthedocs.io/en/latest/cookbook.html
- Tool comparison: [jq, jello, gron, and other tools](docs/source/comparison.rst)
- Syntax reference: [SYNTAX.md](SYNTAX.md)
- Usage examples: [USAGE.md](USAGE.md)
- Contributing: [CONTRIBUTIONS.md](CONTRIBUTIONS.md)

## License

jonq is licensed under the MIT License. See [License](License).

SQL-like queries use the [jq command-line JSON processor](https://stedolan.github.io/jq/), available separately under the MIT License.
