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
    "nickname": "Al",
    "profile": {"age": 30, "address": {"city": "New York"}},
    "orders": [
      {"order_id": 101, "item": "Laptop", "price": 1200},
      {"order_id": 102, "item": "Phone", "price": 800}
    ]
  },
  {
    "id": 2,
    "name": "Bob",
    "nickname": null,
    "profile": {"age": 25, "address": {"city": "Los Angeles"}},
    "orders": [
      {"order_id": 103, "item": "Tablet", "price": 500}
    ]
  }
]
JSON
```

## Inspect JSON First

Run jonq with no query to see the root shape, fields, sample values, and suggested queries. This also works with piped input.

```bash
jonq users.json
cat users.json | jonq
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
jonq users.json "select name, age where age > 30"
jonq users.json "select name if city = 'New York'"
jonq users.json "select name if city in ('New York', 'Chicago')"
jonq users.json "select name if not age > 30"
jonq users.json "select name if name like 'Al%'"
jonq users.json "select name if age between 25 and 35"
```

In an ordered comparison such as `where age > 30`, a numeric literal requires the other operand to be a JSON number. The example skips missing ages, `null`, and strings such as `"35"`.

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
jonq nested.json "select coalesce(nickname, name) as display"
```

`coalesce` returns the first non-null value, preserving `false`.

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
jonq users.json "select name" -r                   # raw values
```

## Input Sources

```bash
jonq users.json "select id, name"
cat users.json | jonq - "select id, name"
cat users.json | jonq "select id, name where age > 30"
curl -s https://api.example.com/users | jonq "select id, name"
jonq 'logs/*.json' "select * if level = 'error'"
```

Inspect or query a newline-delimited JSON file directly. Use `--ndjson` to select that format explicitly on stdin.

```bash
printf '%s\n' '{"level":"info","message":"Started"}' '{"level":"error","message":"Could not load settings"}' > app.ndjson
jonq app.ndjson
jonq app.ndjson "select level, message if level = 'error'"
cat app.ndjson | jonq --ndjson "select level, message if level = 'error'"
```

Use `--follow` to query an ongoing stream one record at a time.

```bash
tail -f app.ndjson | jonq --follow "select level, message if level = 'error'" -t
```

## Network Log Reports

From the repository root, install the checkout and run the bundled fixtures.

```bash
python -m pip install -e .
jonq triage tests/json_test_files/suricata_eve.ndjson
jonq connections tests/json_test_files/zeek_conn.ndjson --scan-leads --min-destinations 2
```

`triage` summarizes recorded Suricata EVE alerts and firewall denials.
The report starts with the alert event and alert type counts, then shows
the first matching input line and timestamp for each signature. Use
`--format json` to keep up to two examples per signature.

`connections` accepts Zeek `conn.log` in JSON mode and Suricata EVE flow
records. Use `--scan-leads` to group rejected and unanswered TCP attempts by
source and destination port. The default threshold is 10 different
destination IPs in 60 seconds. Several records for one IP count as one
destination. The smaller threshold shows the fixture's two-destination
lead. Each run accepts at most one of `--scan-leads` and `--baseline`.

The reports give a command to open the first cited line when reading a
named file on macOS or Linux. Here are the first alert and both scan-lead
records for the examples above.

```bash
sed -n '6p' < tests/json_test_files/suricata_eve.ndjson
sed -n -e '1p' -e '3p' < tests/json_test_files/zeek_conn.ndjson
```

Check whether the source host was scheduled to contact the reported IPs
and port during that window. Expected health-check retries can qualify.
If there are no leads, the report distinguishes no in-scope records,
no eligible TCP observations, and no window meeting the threshold.

Both report commands use Python's standard library and support `-` for stdin,
`--format json`, and `--no-color`. Malformed records produce line diagnostics
and exit status 1 while valid records still contribute to the report.
[Network log cookbook](docs/source/cookbook.rst#triage-network-logs) ·
[Scan-lead replay](CONTRIBUTIONS.md#replay-the-scan-lead-accuracy-cases)

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

If a field is misspelled, jonq suggests nearby fields and a copy-paste repair:

```text
Error: Unknown field(s): cty
Did you mean: cty -> city?
Available fields: id, name, age, city
Try: jonq users.json "select name where city = 'Chicago'"
```

If the input came from a pipe, pass the same data to the suggested command and keep any input flags such as `--ndjson`.

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
