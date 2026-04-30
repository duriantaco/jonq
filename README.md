<div align="center">
  <img src="docs/source/_static/jonq.png" alt="jonq - SQL-like JSON query tool for the command line" width="200"/>

# jonq - readable JSON queries for the terminal

### A jq-powered CLI for inspecting, filtering, and reshaping JSON without memorizing jq syntax

[![PyPI version](https://img.shields.io/pypi/v/jonq.svg)](https://pypi.org/project/jonq/)
[![Python Versions](https://img.shields.io/pypi/pyversions/jonq.svg)](https://pypi.org/project/jonq/)
[![CI tests](https://github.com/duriantaco/jonq/actions/workflows/tests.yml/badge.svg)](https://github.com/duriantaco/jonq/actions)
[![Documentation Status](https://readthedocs.org/projects/jonq/badge/?version=latest)](https://jonq.readthedocs.io)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](License)
[![Skylos Grade](https://img.shields.io/badge/Skylos-A%2B%20%28100%29-brightgreen)](https://github.com/duriantaco/skylos)
</div>

---

## Install

jonq requires Python 3.9+ and the `jq` command-line tool.

```bash
pipx install jonq
# or
pip install jonq
```

Check that `jq` is available:

```bash
jq --version
```

## What jonq is

`jonq` is a command-line JSON query tool for the messy first minutes with an API response, config file, generated JSON, or log payload.

It lets you inspect an unfamiliar payload before writing a query:

```bash
jonq data.json
```

Then extract what you need with readable, SQL-like syntax:

```bash
jonq users.json "select name, age if age > 30" -t
```

Instead of writing the equivalent raw jq:

```bash
jq '.[] | select(.age > 30) | {name, age}' users.json
```

jonq compiles your query to jq and executes it with a reusable jq worker. It is useful when you need to understand JSON shape, extract fields, filter rows, flatten nested arrays, or turn JSON into table, CSV, JSONL, YAML, or raw scalar output.

It also helps when you mistype fields:

```text
Unknown field(s): firts_name
Did you mean: firts_name -> first_name?
Try: jonq users.json "select first_name"
```

> jonq is not a database, ETL framework, or analytics engine. It is a JSON exploration and shaping tool for terminal workflows.

## When to use it

Use jonq when you need to:

- inspect an API response, config file, generated JSON, or log payload
- select and rename fields without remembering jq object syntax
- filter JSON with readable conditions
- query nested objects and arrays
- produce table, CSV, JSONL, YAML, raw scalar, or compact JSON output
- run the same query in shell scripts, CI, or Python code
- follow NDJSON logs line-by-line

Use another tool when you need:

- exact jq language control: use raw `jq`
- Python expressions over JSON: use [`jello`](https://github.com/kellyjonbrazil/jello)
- grep-friendly flattened assignment lines: use [`gron`](https://github.com/tomnomnom/gron)
- joins, window functions, or relational analytics: use a database or analytics engine
- production ETL, scheduling, or connectors: use an ETL system

## From Source

```bash
git clone https://github.com/duriantaco/jonq.git
cd jonq
pip install -e .
```

## Quick Start

Create a sample file:

```bash
cat > users.json <<'JSON'
[
  {"id": 1, "name": "Alice", "age": 30, "city": "New York"},
  {"id": 2, "name": "Bob", "age": 25, "city": "Los Angeles"},
  {"id": 3, "name": "Charlie", "age": 35, "city": "Chicago"}
]
JSON
```

Select fields:

```bash
jonq users.json "select name, age"
```

Filter rows:

```bash
jonq users.json "select name, age if age > 30"
```

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

Select nested fields with dot notation:

```bash
jonq users.json "select profile.email, profile.address.city"
```

Select from nested arrays with `from`:

```bash
jonq orders.json "select id, total from orders"
jonq users.json "select order_id, price from [].orders if price > 100"
```

Use array indexes:

```bash
jonq users.json "select name, orders[0].item as first_order"
```

Use functions and expressions:

```bash
jonq users.json "select upper(name) as name, str(age) as age"
jonq users.json "select name || ' (' || city || ')' as label"
jonq users.json "select age * 2 + 3 as score"
jonq users.json "select coalesce(nickname, name) as display"
jonq users.json "select case when age > 30 then 'senior' else 'junior' end as segment"
```

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

JSON is the default:

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
jonq app.ndjson "select level, message if level = 'error'"
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

## Streaming and Watch Modes

Streaming mode processes root-array JSON in chunks:

```bash
jonq large.json "select id, name if active = true" --stream
```

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
- Cross-file joins, window functions, and relational analytics are out of scope.
- URL fetch is a convenience feature, not a full HTTP client.
- Very large files can still be slow if the query requires full-input state.

## Documentation

- Full docs: https://jonq.readthedocs.io/en/latest/
- Syntax reference: [SYNTAX.md](SYNTAX.md)
- Usage examples: [USAGE.md](USAGE.md)
- Contributing: [CONTRIBUTIONS.md](CONTRIBUTIONS.md)

## License

jonq is licensed under the MIT License. See [License](License).

jonq depends on the [jq command-line JSON processor](https://stedolan.github.io/jq/). jq is licensed under the MIT License and is not bundled with jonq.
