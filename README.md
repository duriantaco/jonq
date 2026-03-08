<div align="center">
  <img src="docs/source/_static/jonq.png" alt="jonq Logo" width="200"/>

# jonq

### Human-readable syntax for **jq**

[![PyPI version](https://img.shields.io/pypi/v/jonq.svg)](https://pypi.org/project/jonq/)
[![Python Versions](https://img.shields.io/pypi/pyversions/jonq.svg)](https://pypi.org/project/jonq/)
[![CI tests](https://github.com/duriantaco/jonq/actions/workflows/tests.yml/badge.svg)](https://github.com/duriantaco/jonq/actions)
[![Documentation Status](https://readthedocs.org/projects/jonq/badge/?version=latest)](https://jonq.readthedocs.io)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Skylos Grade](https://img.shields.io/badge/Skylos-A%2B%20%28100%29-brightgreen)](https://github.com/duriantaco/skylos)
</div>

---

## About

`jq` is unbeatable for JSON processing, but its syntax is hard to learn and easy to forget.
**jonq** wraps `jq` in a SQL-like layer you can read and remember.

> **jonq is NOT a database. It is NOT an alternative to DuckDB, Pandas, or Polars.**
> jonq is a thin CLI wrapper that translates human-friendly queries into jq filters.
> If you need analytics, joins, window functions, or anything beyond simple JSON wrangling — use a real database.

---

### What jonq IS for
- You have a `.json` file and want to quickly pull out some fields
- You know SQL but don't want to memorize jq syntax
- You need a one-liner in a shell script or CI pipeline
- You want to explore an API response or config file

### What jonq is NOT for
- **Data analysis** — use Pandas, Polars, or DuckDB
- **Joins across files** — use DuckDB or a real database
- **Large-scale ETL** — use Spark, DuckDB, or similar
- **Business intelligence** — use proper BI tools

**Rule of thumb:** if your question starts with "can jonq do X that DuckDB can do?" — the answer is probably "no, and that's by design." jonq does one thing: makes jq readable.

## Features at a glance

| Category          | What you can do | Example |
|-------------------|-----------------|---------|
| **Selection**     | Pick fields     | `select name, age` |
| **Wildcard**      | All fields      | `select *` |
| **DISTINCT**      | Unique results  | `select distinct city` |
| **Filtering**     | `and / or / not / between / contains / in / like` | `if age > 30 and city = 'NY'` |
| **Aggregations**  | `sum avg min max count` | `select avg(price) as avg_price` |
| **COUNT DISTINCT**| Unique counts   | `select count(distinct city) as n` |
| **Grouping**      | `group by` + `having`   | `... group by city having count > 2` |
| **Ordering**      | `sort <field> [asc\|desc]` | `sort age desc` |
| **LIMIT**         | Standalone limit | `select * limit 10` |
| **Nested arrays** | `from [].orders` or inline paths | `select products[].name ...` |
| **String funcs**  | `upper lower length` | `select upper(name) as name_upper` |
| **Math funcs**    | `round abs ceil floor` | `select round(price) as price_r` |
| **Inline maths**  | Field expressions | `age + 10 as age_plus_10` |
| **CSV / stream**  | `--format csv`, `--stream` | |
| **Schema preview** | Inspect fields & types | `jonq data.json` (no query) |
| **Interactive REPL** | Run queries interactively | `jonq -i data.json` |
| **Watch mode**    | Re-run on file change | `jonq data.json "select *" --watch` |
| **URL fetch**     | Query remote JSON | `jonq https://api.example.com/data "select id"` |
| **Multi-file glob** | Query across files | `jonq 'logs/*.json' "select *"` |
| **Auto NDJSON**   | Auto-detect line-delimited JSON | No flag needed |
| **Fuzzy suggest** | Typo correction for fields | Suggests similar field names |
| **Colorized output** | Syntax-highlighted JSON in terminal | Auto when TTY |

---

## Why Jonq?

### Jonq vs raw jq

| Task | Raw **jq** filter | **jonq** one-liner |
|------|------------------|--------------------|
| Select specific fields | `jq '.[]&#124;{name:.name,age:.age}'` | `jonq data.json "select name, age"` |
| Filter rows | `jq '.[]&#124;select(.age > 30)&#124;{name,age}'` | `... "select name, age if age > 30"` |
| Sort + limit | `jq 'sort_by(.age) &#124; reverse &#124; .[0:2]'` | `... "select name, age sort age desc 2"` |
| Standalone limit | `jq '.[0:5]'` | `... "select * limit 5"` |
| Distinct values | `jq '[.[].city] &#124; unique'` | `... "select distinct city"` |
| IN filter | `jq '.[] &#124; select(.city=="NY" or .city=="LA")'` | `... "select * if city in ('NY', 'LA')"` |
| NOT filter | `jq '.[] &#124; select((.age > 30) &#124; not)'` | `... "select * if not age > 30"` |
| LIKE filter | `jq '.[] &#124; select(.name &#124; startswith("Al"))'` | `... "select * if name like 'Al%'"` |
| Uppercase | `jq '.[] &#124; {name: (.name &#124; ascii_upcase)}'` | `... "select upper(name) as name"` |
| Count items | `jq 'map(select(.age>25)) &#124; length'` | `... "select count(*) as over_25 if age > 25"` |
| Count distinct | `jq '[.[].city] &#124; unique &#124; length'` | `... "select count(distinct city) as n"` |
| Group & count | `jq 'group_by(.city) &#124; map({city:.[0].city,count:length})'` | `... "select city, count(*) as count group by city"` |
| Group & HAVING | `jq 'group_by(.city) &#124; map(select(length>2)) &#124; ...'` | `... "select city, count(*) group by city having count > 2"` |
| Field expression | `jq '.[] &#124; {name, age_plus: (.age + 10)}'` | `... "select name, age + 10 as age_plus"` |

**Take-away:** a single `jonq` string replaces many pipes and brackets while still producing pure jq under the hood.

---

### jonq vs DuckDB vs Pandas — different tools for different jobs

jonq is **not** in the same category as DuckDB or Pandas. This table exists to show **when to reach for what**, not to compare them as competitors.

| | **jonq** | **DuckDB** | **Pandas** |
|---|---|---|---|
| **What it is** | CLI wrapper around jq | Embedded analytical database | Data manipulation library |
| **Use when** | Quick JSON field extraction, one-liners | SQL analytics on large datasets, joins, aggregations | Data science, cleaning, transformation in Python |
| **Install size** | ~500 KB (jq) | ~140 MB | ~20 MB |
| **Joins** | No | Yes | Yes |
| **Window functions** | No | Yes | Yes |
| **Scales to GB+** | No | Yes | With effort |

**TL;DR:** If you need to `select name, age if age > 30` from a JSON file in your terminal, use jonq. For anything more, use DuckDB or Pandas.

---

## Installation

**Supported Platforms**: Linux, macOS, and Windows with WSL.

### Prerequisites

- Python 3.9+
- `jq` command line tool installed (https://stedolan.github.io/jq/download/)

### Setup

**From PyPI**
```bash
pip install jonq
```

**From source**
```bash
git clone https://github.com/duriantaco/jonq.git
cd jonq && pip install -e .
```

### Quick Start

```bash
# Create a simple JSON file
echo '[{"name":"Alice","age":30,"city":"New York"},{"name":"Bob","age":25,"city":"LA"}]' > data.json

# Select fields
jonq data.json "select name, age if age > 25"
# Output: [{"name":"Alice","age":30}]

# Distinct values
jonq data.json "select distinct city"

# Limit results
jonq data.json "select * limit 1"

# Pattern matching
jonq data.json "select * if name like 'Al%'"

# String functions
jonq data.json "select upper(name) as name_upper"
```

## Query Syntax

```
select [distinct] <fields> [from <path>] [if <condition>] [group by <fields> [having <condition>]] [sort <field> [asc|desc]] [limit N]
```

Where:
* `distinct` - Optional, returns unique rows
* `<fields>` - Comma-separated list of fields, aggregations, or functions
* `from <path>` - Optional source path for nested data
* `if <condition>` - Optional filtering condition
* `group by <fields>` - Optional grouping by one or more fields
* `having <condition>` - Optional filter on grouped results
* `sort <field> [asc|desc]` - Optional ordering
* `limit N` - Optional result count limit

## Examples

Given this JSON (`simple.json`):

```json
[
  { "id": 1, "name": "Alice",   "age": 30, "city": "New York"    },
  { "id": 2, "name": "Bob",     "age": 25, "city": "Los Angeles" },
  { "id": 3, "name": "Charlie", "age": 35, "city": "Chicago"     }
]
```

### Selection
```bash
jonq simple.json "select *"                    # all fields
jonq simple.json "select name, age"            # specific fields
jonq simple.json "select name as full_name"    # with alias
```

### DISTINCT
```bash
jonq simple.json "select distinct city"
# [{"city":"Chicago"},{"city":"Los Angeles"},{"city":"New York"}]
```

### Filtering
```bash
jonq simple.json "select name, age if age > 30"
jonq simple.json "select name if age > 25 and city = 'New York'"
jonq simple.json "select name if age > 30 or city = 'Los Angeles'"
jonq simple.json "select name if age between 25 and 30"
```

### IN Operator
```bash
jonq simple.json "select * if city in ('New York', 'Chicago')"
# [{"id":1,"name":"Alice","age":30,"city":"New York"},{"id":3,"name":"Charlie","age":35,"city":"Chicago"}]
```

### NOT Operator
```bash
jonq simple.json "select * if not age > 30"
# [{"id":1,"name":"Alice","age":30,"city":"New York"},{"id":2,"name":"Bob","age":25,"city":"Los Angeles"}]
```

### LIKE Operator
```bash
jonq simple.json "select * if name like 'Al%'"     # starts with "Al"
jonq simple.json "select * if name like '%ice'"     # ends with "ice"
jonq simple.json "select * if name like '%li%'"     # contains "li"
```

### Sorting and Limiting
```bash
jonq simple.json "select name, age sort age desc"
jonq simple.json "select name, age sort age desc 2"   # sort + inline limit
jonq simple.json "select * limit 2"                    # standalone limit
```

### Aggregation
```bash
jonq simple.json "select sum(age) as total_age"
jonq simple.json "select avg(age) as average_age"
jonq simple.json "select count(*) as total"
jonq simple.json "select count(distinct city) as unique_cities"
```

### GROUP BY and HAVING
```bash
jonq simple.json "select city, count(*) as cnt group by city"
jonq simple.json "select city, avg(age) as avg_age group by city"
jonq simple.json "select city, count(*) as cnt group by city having cnt > 0"
```

### String Functions
```bash
jonq simple.json "select upper(name) as name_upper"
# [{"name_upper":"ALICE"},{"name_upper":"BOB"},{"name_upper":"CHARLIE"}]

jonq simple.json "select lower(city) as city_lower"
jonq simple.json "select length(name) as name_len"
```

### Math Functions
```bash
jonq simple.json "select round(age) as rounded_age"
jonq simple.json "select abs(age) as abs_age"
jonq simple.json "select ceil(age) as ceil_age"
jonq simple.json "select floor(age) as floor_age"
```

### Nested JSON

```bash
# nested field access
jonq nested.json "select name, profile.address.city"

# from: select from nested arrays
jonq complex.json "select name, type from products"

# boolean logic with nested fields
jonq nested.json "select name if profile.address.city = 'New York' or orders[0].price > 1000"
```

### Arithmetic Expressions
```bash
jonq simple.json "select name, age + 10 as age_plus_10"
```

## Output Formats

### CSV Output
```bash
jonq simple.json "select name, age" --format csv > output.csv
```

### Python API

```python
from jonq.csv_utils import flatten_json

data = {
    "user": {
        "name": "Alice",
        "address": {"city": "New York"},
        "orders": [
            {"id": 1, "item": "Laptop", "price": 1200},
            {"id": 2, "item": "Phone", "price": 800}
        ]
    }
}

flattened = flatten_json(data, sep=".")
print(flattened)
```

## Streaming Mode

For processing large JSON files efficiently:

```bash
jonq large.json "select name, age" --stream
```


## Schema Preview

Run `jonq` with just a file (no query) to inspect the schema:

```bash
jonq data.json
```

Output:
```
data.json  (3 items, array)

Fields:
  id    int     1
  name  str     "Alice"
  age   int     30
  city  str     "New York"

Sample:
  { "id": 1, "name": "Alice", "age": 30, "city": "New York" }

Tip: jonq data.json "select *" | head
```

## Interactive REPL

Launch an interactive session to run multiple queries against the same file:

```bash
jonq -i data.json
```

```
jonq interactive mode — querying data.json
Type a query (without jonq/filename), or 'quit' to exit.
Example: select name, age if age > 30

jonq> select name, age
[{"name":"Alice","age":30},{"name":"Bob","age":25}]
jonq> select * if age > 28
[{"id":1,"name":"Alice","age":30,"city":"New York"}]
jonq> quit
```

## Watch Mode

Re-run a query automatically whenever the file changes:

```bash
jonq data.json "select name, age" --watch
```

## Multiple Input Sources

### URL Fetch
```bash
jonq https://api.example.com/users.json "select name, email"
```

### Multi-File Glob
```bash
jonq 'logs/*.json' "select * if level = 'error'"
```

### Stdin
```bash
cat data.json | jonq - "select name, age"
curl -s https://api.example.com/data | jonq - "select id, name"
```

## Auto-detect NDJSON

jonq auto-detects NDJSON (newline-delimited JSON) files. No flag needed:

```bash
jonq data.ndjson "select name, age if age > 25"
```

You can still force it with `--ndjson` if needed. `--ndjson` cannot be combined with `--stream`.

## Fuzzy Field Suggestions

When you mistype a field name, jonq suggests similar fields:

```
$ jonq data.json "select nme, agge"
Field(s) 'nme, agge' not found. Available fields: age, city, id, name. Did you mean: 'nme' -> name; 'agge' -> age?
```

## CLI Options

| Option | Description |
|--------|-------------|
| `--format, -f csv\|json` | Output format (default: json) |
| `--stream, -s` | Stream root-array JSON in chunks |
| `--ndjson` | Force NDJSON mode (auto-detected by default) |
| `--limit, -n N` | Limit rows post-query |
| `--out, -o PATH` | Write output to file |
| `--jq` | Print generated jq filter and exit |
| `--pretty, -p` | Pretty-print JSON output |
| `--watch, -w` | Re-run query when file changes |
| `--no-color` | Disable colorized output |
| `-i <file>` | Interactive query mode (REPL) |
| `-h, --help` | Show help message |

## Colorized Output

When outputting to a terminal, jonq auto-pretty-prints and colorizes JSON. Pipe to a file or use `--no-color` to disable.

## Troubleshooting

### Common Errors

**Command 'jq' not found** - Make sure jq is installed and in your PATH. Install: https://stedolan.github.io/jq/download/

**Invalid JSON in file** - Check your JSON file for syntax errors. Use a JSON validator.

**Syntax error in query** - Verify your query follows the correct syntax. Check field names and quotes.

**No results returned** - Verify your condition isn't filtering out all records. Check field name casing.

## Known Limitations

* Performance: For very large JSON files (100MB+), processing may be slow.
* Advanced jq Features: Some advanced jq features aren't exposed in the jonq syntax.
* Custom Functions: User-defined functions aren't supported.
* Date/Time Operations: Limited support for date/time parsing or manipulation.

## Docs

Full documentation: https://jonq.readthedocs.io/en/latest/

See also: [SYNTAX.md](SYNTAX.md) for the complete syntax reference.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the LICENSE file for details.

### Misc.

- **jq**: This tool depends on the [jq command-line JSON processor](https://stedolan.github.io/jq/), which is licensed under the MIT License. jq is copyright (C) 2012 Stephen Dolan.

The jq tool itself is not included in this package - users need to install it separately.
