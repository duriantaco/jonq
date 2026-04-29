# jonq Usage Guide

This file is a compact, copyable guide. The full documentation lives in
`docs/source/` and at https://jonq.readthedocs.io.

## Sample Data

Most examples below use this file:

```bash
cat > users.json <<'JSON'
[
  {"id": 1, "name": "Alice", "age": 30, "city": "New York"},
  {"id": 2, "name": "Bob", "age": 25, "city": "Los Angeles"},
  {"id": 3, "name": "Charlie", "age": 35, "city": "Chicago"}
]
JSON
```

Nested examples use:

```bash
cat > nested.json <<'JSON'
[
  {
    "id": 1,
    "name": "Alice",
    "profile": {"age": 30, "address": {"city": "New York"}},
    "orders": [
      {"order_id": 101, "item": "Laptop", "price": 1200},
      {"order_id": 102, "item": "Phone", "price": 800}
    ]
  },
  {
    "id": 2,
    "name": "Bob",
    "profile": {"age": 25, "address": {"city": "Los Angeles"}},
    "orders": [
      {"order_id": 103, "item": "Tablet", "price": 500}
    ]
  }
]
JSON
```

## Inspect JSON First

Run jonq with no query to see paths, types, sample values, and a suggested query:

```bash
jonq users.json
```

## Select Fields

```bash
jonq users.json "select *"
jonq users.json "select name, age"
jonq users.json "select name as full_name, age as years"
```

## Filter Rows

```bash
jonq users.json "select name, age if age > 30"
jonq users.json "select name if city = 'New York'"
jonq users.json "select name if city in ('New York', 'Chicago')"
jonq users.json "select name if not age > 30"
jonq users.json "select name if name like 'Al%'"
jonq users.json "select name if age between 25 and 35"
```

## Sort, Limit, and Distinct

```bash
jonq users.json "select name, age sort age desc"
jonq users.json "select name, age sort age desc limit 2"
jonq users.json "select * limit 2"
jonq users.json "select distinct city"
```

## Aggregate and Group

```bash
jonq users.json "select count(*) as total"
jonq users.json "select sum(age) as total_age"
jonq users.json "select avg(age) as avg_age"
jonq users.json "select count(distinct city) as unique_cities"
jonq users.json "select city, count(*) as count group by city"
jonq users.json "select city, avg(age) as avg_age group by city having avg_age > 30"
```

## Expressions and Functions

```bash
jonq users.json "select upper(name) as name"
jonq users.json "select name || ' from ' || city as label"
jonq users.json "select age * 2 + 3 as score"
jonq users.json "select str(age) as age"
jonq users.json "select case when age > 30 then 'senior' else 'junior' end as segment"
jonq users.json "select coalesce(nickname, name) as display"
```

## Nested Objects and Arrays

Nested fields:

```bash
jonq nested.json "select name, profile.age, profile.address.city"
```

Array indexes:

```bash
jonq nested.json "select name, orders[0].item as first_order"
```

Query array elements with `from`:

```bash
jonq nested.json "select order_id, item, price from [].orders"
jonq nested.json "select order_id, item, price from [].orders if price > 800"
```

Aggregations inside each row:

```bash
jonq nested.json "select name, count(orders) as order_count"
```

## Output Formats

```bash
jonq users.json "select name, age"                 # JSON
jonq users.json "select name, age" -t              # table
jonq users.json "select name, age" --format csv    # CSV
jonq users.json "select name, age" --format jsonl  # JSONL
jonq users.json "select name, age" --format yaml   # YAML
```

## Input Sources

```bash
jonq data.json "select id, name"
cat data.json | jonq - "select id, name"
curl -s https://api.example.com/users | jonq "select id, name"
jonq 'logs/*.json' "select * if level = 'error'"
jonq app.ndjson "select level, message if level = 'error'"
tail -f app.ndjson | jonq --follow "select level, message if level = 'error'" -t
```

## Streaming

Streaming mode is for row-wise queries over root-array JSON:

```bash
jonq large.json "select id, name if active = true" --stream
```

It rejects global operations such as aggregation, grouping, sorting, distinct, and limit because those require the full input.

## Debugging Queries

```bash
jonq users.json "select name if age > 30" --jq
jonq users.json "select name if age > 30" --explain
jonq users.json "select name if age > 30" --time
```

## Python API

```python
from jonq import query, execute, compile_query

data = [{"name": "Alice", "age": 30}, {"name": "Bob", "age": 25}]

rows = query(data, "select name if age > 25")

result = execute(data, "select name", format="jsonl")
print(result.text)

compiled = compile_query("select name")
print(query([{"name": "Bob"}], compiled))
```
