# jonq

<img src="docs/source/_static/jonq.png" alt="" width="96" align="right" />

Inspect and reshape JSON with a jq-powered CLI. Explore unfamiliar payloads, write SQL-like queries, and export a table, CSV, or JSONL. You can also check JSON shape in CI.

[Try from source](#from-source) · [JSON quick start](#quick-start) · [Documentation](https://jonq.readthedocs.io) · [PyPI releases](https://pypi.org/project/jonq/) · [CI](https://github.com/duriantaco/jonq/actions)

## From Source

Use this checkout for the examples below. jonq requires Python 3.9+. SQL-like queries use the `jq` command-line tool.

```bash
git clone https://github.com/duriantaco/jonq.git
cd jonq
pip install -e .
```

## Install

Install a published release from PyPI. For the current inspection workflow shown here, [install from source](#from-source).

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
