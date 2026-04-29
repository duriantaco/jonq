<div align="center">
  <img src="docs/source/_static/jonq.png" alt="jonq — SQL-like JSON query tool for the command line" width="200"/>

# jonq — query JSON with SQL-like syntax from the terminal

### A readable alternative to jq for JSON extraction, filtering, and exploration

[![PyPI version](https://img.shields.io/pypi/v/jonq.svg)](https://pypi.org/project/jonq/)
[![Python Versions](https://img.shields.io/pypi/pyversions/jonq.svg)](https://pypi.org/project/jonq/)
[![CI tests](https://github.com/duriantaco/jonq/actions/workflows/tests.yml/badge.svg)](https://github.com/duriantaco/jonq/actions)
[![Documentation Status](https://readthedocs.org/projects/jonq/badge/?version=latest)](https://jonq.readthedocs.io)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Skylos Grade](https://img.shields.io/badge/Skylos-A%2B%20%28100%29-brightgreen)](https://github.com/duriantaco/skylos)
</div>

---

## What is jonq?

**jonq** is a command-line JSON query tool that lets you `select`, `filter`, `group`, and `reshape` JSON data using SQL-like syntax instead of raw jq. It generates pure jq under the hood, so you get jq's speed with a syntax you can actually remember.

```bash
# Instead of: jq '.[] | select(.age > 30) | {name, age}'
jonq data.json "select name, age if age > 30" -t
```

```
name    | age
--------|----
Alice   | 35
Charlie | 42
```

> **jonq is not a database.** It is a readable jq frontend for exploring, extracting, and reshaping JSON. If you need joins, window functions, or large-scale analytics, shape the JSON with jonq first and then hand it to DuckDB, Polars, or Pandas.

---

### Use jonq when you need to
- Query JSON from APIs, config files, or log streams in the terminal
- Explore unfamiliar JSON with the built-in path explorer
- Write readable jq one-liners in shell scripts and CI pipelines
- Filter, aggregate, or reshape nested JSON without memorizing jq syntax
- Stream and filter NDJSON log output in real time

### Use something else when you need
- **Tabular analytics** — DuckDB, Polars, Pandas
- **Joins across files** — a database or dataframe engine
- **Large-scale ETL** — tools built for analytical pipelines

**Rule of thumb:** if the problem is still "I need to understand this JSON", jonq is a good fit. If the problem has become relational analytics, move to a database.

## Features at a glance

| Category          | What you can do | Example |
|-------------------|-----------------|---------|
| **Selection**     | Pick fields     | `select name, age` |
| **Wildcard**      | All fields      | `select *` |
| **DISTINCT**      | Unique results  | `select distinct city` |
| **Filtering**     | `and / or / not / between / contains / in / like` | `if age > 30 and city = 'NY'` |
| **IS NULL**       | Null checks     | `if email is not null` |
| **Aggregations**  | `sum avg min max count` | `select avg(price) as avg_price` |
| **COUNT DISTINCT**| Unique counts   | `select count(distinct city) as n` |
| **Grouping**      | `group by` + `having`   | `... group by city having count > 2` |
| **Ordering**      | `sort <field> [asc\|desc]` | `sort age desc` |
| **LIMIT**         | Standalone limit | `select * limit 10` |
| **CASE/WHEN**     | Conditional expressions | `case when age > 30 then 'senior' else 'junior' end` |
| **COALESCE**      | Null fallback   | `coalesce(nickname, name) as display` |
| **String concat** | `+` or `\|\|`   | `first \|\| ' ' \|\| last as full_name` |
| **Nested arrays** | `from [].orders` or inline paths | `select products[].name ...` |
| **String funcs**  | `upper lower length trim` | `select upper(name) as name_upper` |
| **Math funcs**    | `round abs ceil floor` | `select round(price) as price_r` |
| **Type casting**  | `int float str type` | `select int(price) as price` |
| **Date/time**     | `todate fromdate date` | `select todate(ts) as date` |
| **Inline maths**  | Field expressions | `age + 10 as age_plus_10` |
| **Table output**  | Aligned terminal tables | `--format table` or `-t` |
| **YAML output**   | YAML rendering  | `--format yaml` |
| **CSV / JSONL / stream**  | `--format csv`, `--format jsonl`, `--stream` | |
| **Follow mode**   | Stream NDJSON line-by-line | `tail -f log \| jonq --follow "..."` |
| **Worker reuse**  | Reuse jq workers for repeated filters | `--watch`, `--stream`, Python loops |
| **Path explorer** | Inspect nested JSON paths and types | `jonq data.json` (no query) |
| **Interactive REPL** | Tab completion + history | `jonq -i data.json` |
| **Watch mode**    | Re-run on file change | `jonq data.json "select *" --watch` |
| **URL fetch**     | Query remote JSON | `jonq https://api.example.com/data "select id"` |
| **Multi-file glob** | Query across files | `jonq 'logs/*.json' "select *"` |
| **Auto stdin**    | Auto-detect piped input | `curl ... \| jonq "select id"` |
| **Auto NDJSON**   | Auto-detect line-delimited JSON | No flag needed |
| **Shell completions** | Bash/Zsh/Fish completions | `jonq --completions bash` |
| **Explain mode**  | Show query breakdown + jq filter | `--explain` |
| **Timing**        | Execution timing | `--time` |
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
| CASE/WHEN | `jq '.[] &#124; if .age>30 then "senior" else "junior" end'` | `... "select case when age > 30 then 'senior' else 'junior' end as level"` |
| COALESCE | `jq '.[] &#124; {d: (.nick // .name)}'` | `... "select coalesce(nickname, name) as display"` |
| IS NULL | `jq '.[] &#124; select(.email != null)'` | `... "select * if email is not null"` |
| String concat | `jq '.[] &#124; {f: (.first + " " + .last)}'` | `... "select first &#124;&#124; ' ' &#124;&#124; last as full"` |
| Type cast | `jq '.[] &#124; {p: (.price &#124; tonumber)}'` | `... "select float(price) as p"` |
| Date convert | `jq '.[] &#124; {d: (.ts &#124; todate)}'` | `... "select todate(ts) as d"` |

**Take-away:** a single `jonq` string replaces many pipes and brackets while still producing pure jq under the hood.

---

### Where jonq fits

- Use **jonq** when the source of truth is still raw JSON and you need to inspect fields, paths, filters, or nested values quickly.
- Use **raw jq** when you already know the exact jq filter you want and do not need the friendlier syntax.
- Use **DuckDB / Polars / Pandas** after the JSON has become a tabular analytics problem.

**TL;DR:** jonq is the "understand and shape this JSON" step, not the database step.

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

# Table output
jonq data.json "select name, age, city" -t

# Pipe from stdin (no '-' needed)
curl -s https://api.example.com/data | jonq "select id, name" -t

# Conditional expressions
jonq data.json "select name, case when age > 28 then 'senior' else 'junior' end as level" -t

# Null handling
jonq data.json "select coalesce(nickname, name) as display"

# Type casting
jonq data.json "select name, str(age) as age_str"

# String concatenation
jonq data.json "select name || ' (' || city || ')' as label"

# YAML output
jonq data.json "select name, age" -f yaml

# See what jq jonq generates
jonq data.json "select name, age if age > 25" --explain
```

## Query Syntax

```
select [distinct] <fields> [from <path>] [if <condition>] [group by <fields> [having <condition>]] [sort <field> [asc|desc]] [limit N]
```

Where:
* `distinct` - Optional, returns unique rows
* `<fields>` - Comma-separated: fields, aliases, `CASE/WHEN`, `coalesce()`, functions, aggregations, expressions
* `from <path>` - Optional source path for nested data
* `if <condition>` - Optional filter (supports `=`, `!=`, `>`, `<`, `>=`, `<=`, `and`, `or`, `not`, `in`, `like`, `between`, `contains`, `is null`, `is not null`)
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

### CASE/WHEN Expressions
```bash
jonq simple.json "select name, case when age > 30 then 'senior' when age > 25 then 'mid' else 'junior' end as level"
# [{"name":"Alice","level":"mid"},{"name":"Bob","level":"junior"},{"name":"Charlie","level":"senior"}]
```

### COALESCE
```bash
jonq data.json "select coalesce(nickname, name) as display_name"
# Falls back to name when nickname is null

# Works with nested functions
jonq data.json "select coalesce(todate(timestamp), 'unknown') as date"
```

### IS NULL / IS NOT NULL
```bash
jonq data.json "select name if email is not null"
jonq data.json "select name if nickname is null"
```

### String Concatenation
```bash
# Using || (SQL standard)
jonq simple.json "select name || ' from ' || city as label"

# Using + (also works)
jonq simple.json "select name + ' from ' + city as label"
```

### Type Casting
```bash
jonq data.json "select int(price) as price"        # string → integer
jonq data.json "select float(amount) as amount"     # string → float
jonq data.json "select str(code) as code"           # number → string
jonq data.json "select type(value) as t"            # get type name
```

### Date/Time Functions
```bash
jonq data.json "select todate(timestamp) as date"   # epoch → ISO date
jonq data.json "select date(created_at) as d"       # alias for todate
```

### Arithmetic Expressions
```bash
jonq simple.json "select name, age + 10 as age_plus_10"
```

## Output Formats

### Table Output
```bash
jonq simple.json "select name, age, city" -t
# name    | age | city
# --------|-----|-------------
#  Alice   | 30  | New York
#  Bob     | 25  | Los Angeles
#  Charlie | 35  | Chicago
```

### CSV Output
```bash
jonq simple.json "select name, age" --format csv > output.csv
```

### JSONL Output
```bash
jonq simple.json "select name, age" --format jsonl > output.jsonl
```

### YAML Output
```bash
jonq simple.json "select name, age" --format yaml
# - name: Alice
#   age: 30
# - name: Bob
#   age: 25
```

### Python API

```python
from jonq import compile_query, query

data = [
    {"name": "Alice", "age": 30, "city": "New York"},
    {"name": "Bob", "age": 25, "city": "LA"},
]

compiled = compile_query("select name, city if age > 26")
result = query(data, compiled)
print(result)
```

Output:

```python
[{"name": "Alice", "city": "New York"}]
```

If you want metadata such as the generated jq filter, use `execute(...)` instead of `query(...)`.

Repeated identical filters reuse a live jq worker in long-lived Python processes, which reduces jq startup overhead in loops and services.

## Streaming Mode

For processing large root-array JSON files more efficiently:

```bash
jonq large.json "select name, age" --stream
```

Chunk execution stays in memory and reuses the same jq worker for the generated filter instead of writing chunk temp files and starting a fresh jq subprocess for every chunk.

## Path Explorer

Run `jonq` with just a file (no query) to inspect nested JSON paths before writing a query:

```bash
jonq data.json
```

Output:
```
data.json  (array, sampled 3 items)

Paths:
  id             int               1
  name           str               "Alice"
  age            int               30
  city           str               "New York"
  orders[]       array[object]
  orders[].id    int               1
  orders[].item  str               "Laptop"

Sample:
  { "id": 1, "name": "Alice", "age": 30, "city": "New York", "orders": [{ "id": 1, "item": "Laptop" }] }

Tip: jonq data.json "select name, orders[].item"
```

## Interactive REPL

Launch an interactive session with tab completion and persistent history:

```bash
jonq -i data.json
```

```
jonq interactive mode — querying data.json
Type a query, or 'quit' to exit. Tab completes field names.
Example: select name, age if age > 30

jonq> select name, age
[{"name":"Alice","age":30},{"name":"Bob","age":25}]
jonq> select * if age > 28
[{"id":1,"name":"Alice","age":30,"city":"New York"}]
jonq> quit
```

Features:
- **Tab completion** for field names and SQL keywords
- **Persistent history** saved to `~/.jonq_history`
- **Up/down arrow** to recall previous queries

## Watch Mode

Re-run a query automatically whenever the file changes:

```bash
jonq data.json "select name, age" --watch
```

Because watch mode reruns the same filter repeatedly inside one loop, jonq reuses a live jq worker to reduce refresh overhead.

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
# Auto-detected — no '-' needed
curl -s https://api.example.com/data | jonq "select id, name"

# Explicit stdin still works
cat data.json | jonq - "select name, age"
```

## Follow Mode

Stream NDJSON from stdin line-by-line, applying the query to each object as it arrives:

```bash
tail -f app.log | jonq --follow "select level, message if level = 'error'" -t
```

Only matching lines are printed. Non-matching lines are silently skipped.

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
| `--format, -f` | Output format: `json` (default), `jsonl`, `csv`, `table`, `yaml` |
| `-t, --table` | Shorthand for `--format table` |
| `--stream, -s` | Process row-wise root-array queries in memory-friendly chunks |
| `--ndjson` | Force NDJSON mode (auto-detected by default) |
| `--follow` | Stream NDJSON from stdin line-by-line |
| `--limit, -n N` | Limit rows post-query |
| `--out, -o PATH` | Write output to file |
| `--jq` | Print generated jq filter and exit |
| `--explain` | Show parsed query breakdown and generated jq filter |
| `--time` | Print execution timing to stderr |
| `--pretty, -p` | Pretty-print JSON output |
| `--watch, -w` | Re-run query when file changes |
| `--no-color` | Disable colorized output |
| `--completions SHELL` | Print shell completion script (`bash`, `zsh`, `fish`) |
| `--version` | Show the installed jonq version |
| `-i <file>` | Interactive query mode (REPL) with tab completion |
| `-h, --help` | Show help message |

## Shell Completions

Generate completion scripts for your shell:

```bash
# Bash
eval "$(jonq --completions bash)"

# Zsh
eval "$(jonq --completions zsh)"

# Fish
jonq --completions fish > ~/.config/fish/completions/jonq.fish
```

## Colorized Output

When outputting to a terminal, jonq auto-pretty-prints and colorizes JSON. Pipe to a file or use `--no-color` to disable.

## Troubleshooting

### Common Errors

**Command 'jq' not found** - Make sure jq is installed and in your PATH. Install: https://stedolan.github.io/jq/download/

**Invalid JSON in file** - Check your JSON file for syntax errors. Use a JSON validator.

**Syntax error in query** - Verify your query follows the correct syntax. Check field names and quotes.

**Runtime jq error** - Errors like `Cannot iterate over string` or `Cannot iterate over null` are surfaced immediately. Adjust the field path or inspect the input with `jonq data.json`.

**No results returned** - Verify your condition isn't filtering out all records. Check field name casing.

## Known Limitations

* Performance: For very large JSON files (100MB+), processing may still be slow. `--stream` is more memory-friendly now, but jonq is still not an analytical engine.
* Advanced jq Features: Some advanced jq features (recursive descent, custom filters) aren't exposed in the jonq syntax.
* Custom Functions: User-defined functions aren't supported.
* Joins: Cross-file joins are not supported — use a database for relational queries.
* Window Functions: Not supported — use DuckDB or Polars for analytical queries.

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
