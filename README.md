<div align="center">
  <img src="docs/source/_static/jonq.png" alt="jonq Logo" width="200"/>

# jonq

### Human-readable syntax for JQ

[![PyPI version](https://img.shields.io/pypi/v/jonq.svg)](https://pypi.org/project/jonq/)
[![Python Versions](https://img.shields.io/pypi/pyversions/jonq.svg)](https://pypi.org/project/jonq/)
[![Tests](https://github.com/duriantaco/jonq/actions/workflows/tests.yml/badge.svg)](https://github.com/duriantaco/jonq/actions)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Documentation Status](https://readthedocs.org/projects/jonq/badge/?version=latest)](https://jonq.readthedocs.io)
</div>

A Pythonish-SQL-like query tool for JSON files, built as a Python wrapper around the super awesome but difficult to use jq utility.

## Table of Contents
- [Overview](#overview)
- [Quick Start](#quick-start)
- [Features](#features)
- [jonq vs Native](#jonq-vs-native)
- [Installation](#installation)
- [Usage](#usage)
- [Example Simple JSON](#example-simple-json)
- [Example with Nested JSON](#example-with-nested-json)
- [Advanced Filtering](#advanced-filtering-with-complex-boolean-expressions)
- [Grouping and Aggregation](#grouping-and-aggregation-with-group-by)
- [Troubleshooting](#troubleshooting)
- [Known Limitations](#known-limitations)
- [Contributing](#contributing)
- [License](#license)

## Overview

jonq allows you to query JSON data using familiar Pythonish-SQL-like syntax. It translates these queries into jq filters, making it easier for users familiar with SQL and Python to extract and manipulate data from JSON files without learning the full jq syntax (it's just too complex imo). 

## Features

* SQL-like Syntax: Query JSON with familiar `SELECT` statements and traverse nested JSONs with pythonic like syntax aka `abc.def`
* Field Selection: Choose specific fields from your JSON data
* Filtering: Filter your results using the `if` keyword
* Sorting: Order results with ascending or descending sort
* Pagination: Limit the number of results returned
* Aggregation Functions: Use functions like `sum()`, `avg()`, `count()`, `max()` and `min()`

## jonq vs Native

While jq is incredibly powerful, its syntax is a pain to use. I can't be the only one who feels that way right? jonq simplifies JSON querying with familiar, intuitive syntax:

| Task | Native jq | jonq | 
|------|-----------|------|
| Select specific fields | `jq '.[] \| {name: .name, age: .age}'` | `jonq data.json "select name, age"` |
| Filter with condition | `jq '.[] \| select(.age > 30) \| {name, age}'` | `jonq data.json "select name, age if age > 30"` |
| Sort results | `jq 'sort_by(.age) \| reverse \| .[0:2]'` | `jonq data.json "select name, age sort age desc 2"` |
| Work with nested data | `jq '.[] \| select(.profile.address.city == "New York") \| {name, city: .profile.address.city}'` | `jonq data.json "select name, profile.address.city if profile.address.city = 'New York'"` |
| Count items | `jq 'map(select(.age > 25)) \| length'` | `jonq data.json "select count(*) as count_over_25 if age > 25"` |
| Group & aggregate | `jq 'group_by(.city) \| map({city: .[0].city, count: length})'` | `jonq data.json "select city, count(*) as user_count group by city"` |
| Complex filters | `jq '.[] \| select(.age > 25 and (.city == "New York" or .city == "Chicago"))'` | `jonq data.json "select * if age > 25 and (city = 'New York' or city = 'Chicago')"` |

As you can see, jonq offers:
- **Simpler syntax**: I'm not sure how much simpler can it get
- **Familiar patterns**: Py + SQL-like keywords
- **Readability**: For human readability 
- **Faster development**: Write complex queries in a fraction of the time

## Installation

### Prerequisites

- Python 3.9+
- jq command line tool installed (https://stedolan.github.io/jq/download/)

### Setup

1. Clone this repository:
`pip install jonq`
 
**Make sure you have jq installed:**
   ```
   jq --version
   ```

### Quick Start 

# Create a simple JSON file
echo '[{"name":"Alice","age":30},{"name":"Bob","age":25}]' > data.json

# Run a query
jonq data.json "select name, age if age > 25"
# Output: [{"name":"Alice","age":30}]

## Query Syntax

The query syntax follows a simplified format:

```bash
select <fields> [if <condition>] [sort <field> [asc|desc] [limit]]
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

Image a json like the following: 

```json
[
  {
    "id": 1,
    "name": "Alice",
    "age": 30,
    "city": "New York"
  },
  {
    "id": 2,
    "name": "Bob",
    "age": 25,
    "city": "Los Angeles"
  },
  {
    "id": 3,
    "name": "Charlie",
    "age": 35,
    "city": "Chicago"
  }
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
      "address": {
        "city": "New York",
        "zip": "10001"
      }
    },
    "orders": [
      {
        "order_id": 101,
        "item": "Laptop",
        "price": 1200
      },
      {
        "order_id": 102,
        "item": "Phone",
        "price": 800
      }
    ]
  },
  {
    "id": 2,
    "name": "Bob",
    "profile": {
      "age": 25,
      "address": {
        "city": "Los Angeles",
        "zip": "90001"
      }
    },
    "orders": [
      {
        "order_id": 103,
        "item": "Tablet",
        "price": 500
      }
    ]
  }
]
```

### Query nested fields with dot notation
```bash
jonq path/to/nested.json "select name, profile.age"
jonq path/to/nested.json "select name, profile.address.city"
```

### Count items in nested fields
```bash
jonq path/to/nested.json "select name, count(orders) as order_count"
```

## Advanced Filtering with Complex Boolean Expressions

jonq supports complex boolean conditions using AND, OR, and parentheses:

### Find users either from New York OR with orders costing more than 1000

```bash
jonq nested.json "select name, profile.age if profile.address.city = 'New York' or orders[0].price > 1000"

### Find users who are both under 30 AND from Los Angeles
jonq nested.json "select name, profile.age if profile.age < 30 and profile.address.city = 'Los Angeles'"

### Using parentheses for complex logic
jonq nested.json "select name, profile.age if (profile.age > 25 and profile.address.city = 'New York') or (profile.age < 26 and profile.address.city = 'Los Angeles')"
```

## Grouping and Aggregation with GROUP BY
jonq supports grouping data and performing aggregations per group:

```bash
# Group by city and count users in each city
jonq nested.json "select profile.address.city, count(*) as user_count group by profile.address.city"

# Group by city and get average age in each city
jonq nested.json "select profile.address.city, avg(profile.age) as avg_age group by profile.address.city"

# Group by city and get total orders and average order price
jonq nested.json "select profile.address.city, count(orders) as order_count, avg(orders.price) as avg_price group by profile.address.city"
```

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

* Write Operations: jonq doesn't support writing results back to files. It's a read-only tool (or at least for now).
* Performance: For very large JSON files (100MB+), processing may be slow.
* Advanced jq Features: Some advanced jq features aren't exposed in the jonq syntax.
* CSV Output: Currently only outputs JSON format. CSV export is planned for future versions.
* Multiple File Joins: No support for joining data from multiple JSON files.
* Custom Functions: User-defined functions aren't supported in the current version.
* Date/Time Operations: Limited support for date/time parsing or manipulation.

## Docs

Docs here: `https://jonq.readthedocs.io/en/latest/`

## Contributing
Contributions are welcome! Please feel free to submit a Pull Request.

## License
This project is licensed under the MIT License - see the LICENSE file for details.
 
### Misc. 

- **jq**: This tool depends on the [jq command-line JSON processor](https://stedolan.github.io/jq/), which is licensed under the MIT License. jq is copyright (C) 2012 Stephen Dolan.

The jq tool itself is not included in this package - users need to install it separately. 