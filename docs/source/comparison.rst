Comparison
===========

Where jonq Fits
----------------

jonq is a CLI JSON exploration and extraction tool. It is not a database, ETL system, or BI layer.

.. important::

   Use jonq while the problem is still "understand this JSON" or "reshape this payload" from the shell.
   Once the problem becomes relational analytics, joins, window functions, or large-scale data movement, move to a tool built for that job.

When to Use jonq
~~~~~~~~~~~~~~~~~

- You have raw JSON from an API, config file, or log stream.
- You want to inspect nested paths before writing a query.
- You need a readable jq one-liner in a shell script or CI job.
- You want to reshape nested JSON before handing it to another system.

When to Use Something Else
~~~~~~~~~~~~~~~~~~~~~~~~~~~

- Use **raw jq** when you already know the exact jq filter you want.
- Use `jello <https://github.com/kellyjonbrazil/jello>`_ when you want Python expressions over JSON from the CLI.
- Use `gron <https://github.com/tomnomnom/gron>`_ when you want grep-friendly flattened assignment lines.
- Use an **analytics engine or database** when you need joins, window functions, or repeated analytical queries over larger datasets.

Typical Workflow
~~~~~~~~~~~~~~~~~

1. Explore unknown JSON with jonq.
2. Extract or normalize the fields you need.
3. Pipe the result into the next shell command, script, or analytical system if you need more processing afterward.

jonq vs raw jq
---------------

The examples query the same array and produce equivalent results. Jonq
checks that values compared with numeric thresholds are JSON numbers.
Its ``coalesce`` uses the first non-null value and preserves ``false``.
The corresponding jq filters include those checks explicitly.

.. code-block:: bash

   cat > data.json <<'JSON'
   [
     {"name":"Alice","first":"Alice","last":"Ng","age":35,"city":"NY",
      "nickname":false,"email":"alice@example.com","price":"12.5","ts":1700000000},
     {"name":"Bob","first":"Bob","last":"Lee","age":"35","city":"LA",
      "nickname":null,"email":null,"price":null,"ts":null}
   ]
   JSON

.. list-table::
   :header-rows: 1
   :widths: 25 35 40

   * - Task
     - Raw **jq** filter
     - **jonq** one-liner
   * - Select fields
     - ``jq 'map({name, age})' data.json``
     - ``jonq data.json "select name, age"``
   * - Filter rows
     - ``jq 'map(select((.age | type) == "number" and .age > 30) | {name, age})' data.json``
     - ``jonq data.json "select name, age where age > 30"``
   * - Sort + limit
     - ``jq 'sort_by(.age) | reverse | .[:2] | map({name, age})' data.json``
     - ``jonq data.json "select name, age sort age desc limit 2"``
   * - Standalone limit
     - ``jq '.[0:5]' data.json``
     - ``jonq data.json "select * limit 5"``
   * - Distinct values
     - ``jq 'map({city}) | unique' data.json``
     - ``jonq data.json "select distinct city"``
   * - IN filter
     - ``jq 'map(select(.city == "NY" or .city == "LA"))' data.json``
     - ``jonq data.json "select * if city in ('NY', 'LA')"``
   * - NOT filter
     - ``jq 'map(select(((.age | type) == "number" and .age > 30) | not))' data.json``
     - ``jonq data.json "select * if not age > 30"``
   * - LIKE filter
     - ``jq 'map(select(.name | tostring | startswith("Al")))' data.json``
     - ``jonq data.json "select * if name like 'Al%'"``
   * - Uppercase
     - ``jq 'map({name: (.name | ascii_upcase)})' data.json``
     - ``jonq data.json "select upper(name) as name"``
   * - Group & count
     - ``jq 'group_by(.city) | map({city: .[0].city, count: length})' data.json``
     - ``jonq data.json "select city, count(*) as count group by city"``
   * - CASE/WHEN
     - ``jq 'map({level: (if (.age | type) == "number" and .age > 30 then "senior" else "junior" end)})' data.json``
     - ``jonq data.json "select case when age > 30 then 'senior' else 'junior' end as level"``
   * - COALESCE
     - ``jq 'map({display: first(((.nickname, .name) | select(. != null)), null)})' data.json``
     - ``jonq data.json "select coalesce(nickname, name) as display"``
   * - IS NULL
     - ``jq 'map(select(.email != null))' data.json``
     - ``jonq data.json "select * if email is not null"``
   * - String concat
     - ``jq 'map({full: (.first + " " + .last)})' data.json``
     - ``jonq data.json "select first || ' ' || last as full"``
   * - Type cast
     - ``jq 'map({p: (.price | if . == null then null else tonumber end)})' data.json``
     - ``jonq data.json "select float(price) as p"``
   * - Date convert
     - ``jq 'map({d: (.ts | if . == null then null else todate end)})' data.json``
     - ``jonq data.json "select todate(ts) as d"``
   * - Tabular output
     - ``jq -r '(["name", "age"], (.[] | [.name, .age])) | @tsv' data.json`` (TSV)
     - ``jonq data.json "select name, age" -t``
