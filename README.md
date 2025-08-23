<div align="center">
  <img src="docs/source/_static/jonq.png" alt="jonq Logo" width="200"/>

# jonq

### Human‑readable syntax for **jq**

[![PyPI version](https://img.shields.io/pypi/v/jonq.svg)](https://pypi.org/project/jonq/)
[![Python Versions](https://img.shields.io/pypi/pyversions/jonq.svg)](https://pypi.org/project/jonq/)
[![CI tests](https://github.com/duriantaco/jonq/actions/workflows/tests.yml/badge.svg)](https://github.com/duriantaco/jonq/actions)
[![Documentation Status](https://readthedocs.org/projects/jonq/badge/?version=latest)](https://jonq.readthedocs.io)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
</div>

---

## About 

`jq` is unbeatable for JSON processing, but its syntax requires a lot of learning.  
**jonq** wraps `jq` in a SQL-lish/pythonic layer you can read and remember.

**Who It's For**: Jonq is designed for anyone who needs to work with JSON data. It's good for quick JSON exploration, lightweight ETL tasks, or validating config files in CI pipelines.

**jonq is NOT a database. It's NOT competing with DuckDB or Pandas. jonq is a command-line tool that makes jq accessible by wrapping it in SQL-like syntax.**
---

### What jonq IS for:
* Quick JSON exploration
* jq beginners
* Ad-hoc JSON tasks - No setup, just run a command
* Config file validation - Quick checks in scripts

### What jonq is NOT for:
1. Data analysis - Use Pandas, or Polars or DuckDB
2. Complex joins - Use DuckDB, PostgreSQL, or whatever DB you want
3. Business intelligence - Use proper BI tools

## Features at a glance

| Category          | What you can do | Example |
|-------------------|-----------------|---------|
| **Selection**     | Pick fields     | `select name, age` |
| **Wildcard**      | All fields      | `select *` |
| **Filtering**     | Python‑style ops<br>`and / or / between / contains` | `if age > 30 and city = 'NY'` |
| **Aggregations**  | `sum avg min max count` | `select avg(price) as avg_price` |
| **Grouping**      | `group by` + `having`   | `… group by city having count > 2` |
| **Ordering**      | `sort <field> [asc\|desc] <limit>` | `sort age desc 5` |
| **Nested arrays** | `from [].orders` or inline paths | `select products[].name …` |
| **Inline maths**  | Real expressions | `sum(items.price) * 2 as double_total` |
| **CSV / stream**  | `--format csv`, `--stream` |

---

## Why Jonq?  

### Jonq vs raw jq  

| Task | Raw **jq** filter | **jonq** one‑liner |
|------|------------------|--------------------|
| Select specific fields | `jq '.[]&#124;{name:.name,age:.age}'` | `jonq data.json "select name, age"` |
| Filter rows | `jq '.[]&#124;select(.age &gt; 30)&#124;{name,age}'` | `… "select name, age if age > 30"` |
| Sort + limit | `jq 'sort_by(.age) | reverse | .[0:2]'` | `… "select name, age sort age desc 2"` |
| Deep filter | `jq '.[]&#124;select(.profile.address.city=="NY")&#124;{name,city:.profile.address.city}'` | `… "select name, profile.address.city if profile.address.city = 'NY'"` |
| Count items | `jq 'map(select(.age>25)) | length'` | `… "select count(*) as over_25 if age > 25"` |
| Group & count | `jq 'group_by(.city) | map({city:.[0].city,count:length})'` | `… "select city, count(*) as count group by city"` |
| Complex boolean | `jq '.[] | select(.age>25 and (.city=="NY" or .city=="Chicago"))'` | `… "select * if age > 25 and (city = 'NY' or city = 'Chicago')"` |
| Group & HAVING | `jq 'group_by(.city) | map(select(length>2)) | map({city:.[0].city,count:length})'` | `… "select city, count(*) group by city having count > 2"` |
| Aggregation expression | - | `… "select sum(price) * 1.07 as total_gst"` |
| Nested‑array aggregation | - | `… "select avg(products[].versions[].pricing.monthly) as avg_price"` |

**Take‑away:** a single `jonq` string replaces many pipes and brackets while still producing pure jq under the hood.

---

### Jonq vs DuckDB vs Pandas (JSON extension)

| Aspect | **jonq** | **DuckDB** | **Pandas** |
|--------|------------|----------|----------|
| Primary Use Case | Fast, lightweight JSON querying directly from the command line | General-purpose data manipulation and analysis in Python | Analytical SQL queries on large datasets, including JSON |
| Setup | No DB, can stream **root-array** JSON | Requires DB file / extension | Requires a Python environment with pandas and its dependencies installed |
| Query language | Familiar SQL‑ish, no funky `json_extract`| SQL + JSON functions | Python code for data manipulation and analysis |
| Footprint | Minimal: requires only jq (a ~500 KB binary); no environment setup | ~ 140 MB binary | Larger: ~20 MB for pandas and its dependencies |
| Streaming | `--stream` processes **root-array** JSON in chunks concurrently | Must load into table | Can process large files using chunking, but not as memory-efficient |
| Memory Usage | Low; streams data to avoid loading full JSON into memory | In-memory database, but optimized for large data with columnar storage | Loads data into memory; can strain RAM with large datasets |
| jq ecosystem | Leverages **all** jq filters for post‑processing | No | Part of the Python data science ecosystem; integrates with NumPy, Matplotlib, scikit-learn, etc |

---

### Why you’ll reach for Jonq

1. **Instant JSON Querying, No Setup Hassle**

You have a JSON file (data.json) and need to extract all records where age > 30 in seconds.

* With `jonq`: Run `jonq data.json "select * if age > 30"`. Done. No environment setup, no imports. Just install jq and go.

* Pandas: Fire up Python, write a script (`import pandas as pd; df = pd.read_json('data.json'); df[df['age'] > 30]`), and run it. More steps. 

* DuckDB: Set up a database, load the JSON (`SELECT * FROM read_json('data.json') WHERE age > 30`), and execute. Powerful, but overkill for a quick task.

2. **Command-Line Power**

Use Case: Chain commands in a pipeline, like cat data.json | jonq - "select name, age" | grep "John".

`Jonq` thrives in shell scripts or CI/CD workflows. Pandas and DuckDB require scripting or a heavier integration layer. 

3. **Lightweight and Efficient**

`Jonq` streams large **root-array** JSON files by chunking (`jq -c '.[]'`) and processing chunks concurrently — no jq `--stream`. This avoids loading the entire file into memory.

Comparison: Pandas loads everything into a DataFrame (RAM-intensive), and while DuckDB is memory-efficient for analytics, it’s still a full database engine, thus there'll be significant overhead.

4. **SQL Simplicity for JSON**

Example: `jonq users.json "select name, email if status = 'active' sort name"`.

Advantage: If you know SQL, "jonq" feels natural for JSON—no need to learn jq’s super difficult syntax.

5. **Speed for Ad-Hoc Tasks**

Test Case: Querying a 1 GB JSON file for specific fields.

* Jonq: Streams it in seconds with minimal memory use.

* Pandas: Might choke or require chunking hacks.

* DuckDB: Fast, but setup and SQL complexity add time.

## Installation

**Supported Platforms**: Jonq works on Linux, macOS, and Windows with WSL.

### Prerequisites

- Python 3.9+
- `jq` command line tool installed (https://stedolan.github.io/jq/download/)

### Setup

**From PyPI**
```bash
pip install jonq # latest stable
```

**From source**
```bash
git clone https://github.com/duriantaco/jonq.git
cd jonq && pip install -e .
```
 
**Verify Installation**: After installation, run `jonq --version` to ensure it's working correctly.

We will explain more about this down below

### Quick Start 

# Create a simple JSON file
`echo '[{"name":"Alice","age":30},{"name":"Bob","age":25}]' > data.json`

# Run a query

```bash
jonq data.json "select name, age if age > 25"

# Output: [{"name":"Alice","age":30}]

```

## Query Syntax

The query syntax follows a simplified format:

```bash
select <fields> [if <condition>] [group by <fields> [having <condition>]] [sort <field> [asc|desc] [limit]] [from <path>]
```
where:

* `<fields>` - Comma-separated list of fields to select or aggregations
* `if <condition>` - Optional filtering condition
* `group by <fields>` - Optional grouping by one or more fields
* `sort <field>` - Optional field to sort by
* `asc|desc` - Optional sort direction (default: asc)
* `limit` - Optional integer to limit the number of results

## Example Simple JSON

You can also refer to the `json_test_files` for the test jsons and look up `USAGE.md` guide. Anyway let's start with `simple.json`. 

Imagine a json like the following: 

```json
[
  { "id": 1, "name": "Alice",   "age": 30, "city": "New York"    },
  { "id": 2, "name": "Bob",     "age": 25, "city": "Los Angeles" },
  { "id": 3, "name": "Charlie", "age": 35, "city": "Chicago"     }
]
```

### To select all fields:
```bash
jonq path/to/simple.json "select *"
```

### Select specific fields:
```bash
jonq path/to/simple.json "select name, age"
```

### Filter with conditions:
```bash
jonq path/to/simple.json "select name, age if age > 30"
```

### Sorting:
```bash
jonq path/to/simple.json "select name, age sort age desc 2"
```

### Aggregation:
```bash
jonq path/to/simple.json "select sum(age) as total_age"
jonq path/to/simple.json "select avg(age) as average_age"
jonq path/to/simple.json "select count(age) as count"
```

Simple enough i hope? Now let's move on to nested jsons 

## Example with Nested JSON 

Imagine a nested json like below:

```json
[
  {
    "id": 1,
    "name": "Alice",
    "profile": {
      "age": 30,
      "address": { "city": "New York", "zip": "10001" }
    },
    "orders": [
      { "order_id": 101, "item": "Laptop", "price": 1200 },
      { "order_id": 102, "item": "Phone",  "price": 800  }
    ]
  },
  { "id": 2, "name": "Bob", "profile": { "age": 25, "address": { "city": "Los Angeles", "zip": "90001" } }, "orders": [ { "order_id": 103, "item": "Tablet", "price": 500 } ] }
]
```

### Common patterns
```bash
# nested field access
jonq nested.json "select name, profile.age"
jonq nested.json "select name, profile.address.city"

# count array elements
jonq nested.json "select name, count(orders) as order_count"

# boolean logic (AND / OR / parentheses)
jonq nested.json "select name if profile.address.city = 'New York' or orders[0].price > 1000"
jonq nested.json "select name if (profile.age > 25 and profile.address.city = 'New York') or (profile.age < 26 and profile.address.city = 'Los Angeles')"
```

### Advanced Filtering with Complex Boolean Expressions

```bash
 jonq nested.json "select name, profile.age if profile.address.city = 'New York' or orders[0].price > 1000"

### Find users who are both under 30 **and** from Los Angeles
jonq nested.json "select name, profile.age if profile.age < 30 and profile.address.city = 'Los Angeles'"

### Using parentheses for complex logic
jonq nested.json "select name, profile.age if (profile.age > 25 and profile.address.city = 'New York') or (profile.age < 26 and profile.address.city = 'Los Angeles')"
```

## Output Formats

### CSV Output
jonq can output results in CSV format using the `--format csv` or `-f csv` option:

```bash
jonq path/to/simple.json "select name, age" --format csv  > output.csv
```

### Python code

Using flatten_json in your code:

```python

from jonq.csv_utils import flatten_json
import csv

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

For processing large JSON files efficiently, jonq supports streaming mode with the `--stream` or `-s` option:

```bash
jonq path/to/large.json "select name, age" --stream
```

## NDJSON (newline-delimited JSON)

Enable NDJSON input with `--ndjson`. Jonq will read each **non-empty line** as a JSON value and wrap them into a single array before running your query

```bash
# from .ndjson file
jonq data.ndjson "select name, age if age > 25" --ndjson

# from stdin
cat data.ndjson | jonq - "select name, age if age > 25" --ndjson
```

**Notes**
- `--ndjson` cannot be combined with `--stream`
- Lines must be valid JSON values (objects, arrays, strings, etc.). Blank lines are ignored.

### CLI Options (quick reference)
- `--format, -f csv|json`  Output format (default: json)
- `--stream, -s`           Stream root-array JSON in chunks
- `--ndjson`               Input one JSON object per line (not compatible with `--stream`)
- `--limit, -n N`          Limit rows post-query
- `--out, -o PATH`         Output
- `--jq`                   Print generated jq filter and exit
- `--pretty, -p`           Pretty-print output

## Troubleshooting
### Common Errors
#### Error: Command 'jq' not found

* Make sure jq is installed on your system
* Verify jq is in your PATH by running `jq --version`
* Install jq: https://stedolan.github.io/jq/download/

#### Error: Invalid JSON in file

* Check your JSON file for syntax errors
* Verify the file exists and is readable
* Use a JSON validator to check your file structure

#### Error: Syntax error in query

* Verify your query follows the correct syntax format
* Ensure field names match exactly what's in your JSON
* Check for missing quotes around string values in conditions

#### Error: No results returned

* Verify your condition isn't filtering out all records
* Check if your field names match the casing in the JSON
* For nested fields, ensure the dot notation path is correct

## Known Limitations

* Performance: For very large JSON files (100MB+), processing may be slow.
* Advanced jq Features: Some advanced jq features aren't exposed in the jonq syntax.
* Multiple File Joins: No support for joining data from multiple JSON files.
* Custom Functions: User-defined functions aren't supported in the current version.
* Date/Time Operations: Limited support for date/time parsing or manipulation.

## Go Tos: 
Pandas: Go here for complex analysis (e.g., merging datasets, statistical ops, plotting). `Jonq` won’t crunch numbers or integrate with machine learning libraries.

DuckDB: Pick this for big data analytics with joins, aggregates, or window functions across multiple files. `Jonq` is simpler, **not** a database.

## Docs

Docs here: `https://jonq.readthedocs.io/en/latest/`

## Contributing
Contributions are welcome! Please feel free to submit a Pull Request.

## License
This project is licensed under the MIT License - see the LICENSE file for details.
 
### Misc. 

- **jq**: This tool depends on the [jq command-line JSON processor](https://stedolan.github.io/jq/), which is licensed under the MIT License. jq is copyright (C) 2012 Stephen Dolan.

The jq tool itself is not included in this package - users need to install it separately. 