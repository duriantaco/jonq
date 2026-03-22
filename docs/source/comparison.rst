Comparison
===========

Where jonq Fits
----------------

jonq is a JSON exploration and extraction tool. It is not a database, dataframe engine, or BI layer.

.. important::

   Use jonq while the problem is still "understand this JSON" or "reshape this payload".
   Once the problem becomes relational analytics, joins, window functions, or large-scale aggregation, move to an analytical tool.

When to Use jonq
~~~~~~~~~~~~~~~~~

- You have raw JSON from an API, config file, or log stream.
- You want to inspect nested paths before writing a query.
- You need a readable jq one-liner in a shell script or CI job.
- You want to reshape nested JSON before handing it to another system.

When to Use Something Else
~~~~~~~~~~~~~~~~~~~~~~~~~~~

- Use **raw jq** when you already know the exact jq filter you want.
- Use **DuckDB / Polars / Pandas** when the data is now a tabular analytics problem.
- Use a **database or warehouse** when you need joins, window functions, or repeated analytical queries over larger datasets.

Typical Workflow
~~~~~~~~~~~~~~~~~

1. Explore unknown JSON with jonq.
2. Extract or normalize the fields you need.
3. Pipe the result into DuckDB, Polars, Pandas, or a database if you need analytics afterward.

jonq vs raw jq
---------------

jonq's advantage is readability. The same query in raw jq requires more syntax:

.. list-table::
   :header-rows: 1
   :widths: 25 35 40

   * - Task
     - Raw **jq** filter
     - **jonq** one-liner
   * - Select fields
     - ``jq '.[]{name:.name,age:.age}'``
     - ``jonq data.json "select name, age"``
   * - Filter rows
     - ``jq '.[]|select(.age > 30)|{name,age}'``
     - ``... "select name, age if age > 30"``
   * - Sort + limit
     - ``jq 'sort_by(.age) | reverse | .[0:2]'``
     - ``... "select name, age sort age desc 2"``
   * - Standalone limit
     - ``jq '.[0:5]'``
     - ``... "select * limit 5"``
   * - Distinct values
     - ``jq '[.[].city] | unique'``
     - ``... "select distinct city"``
   * - IN filter
     - ``jq '.[] | select(.city=="NY" or .city=="LA")'``
     - ``... "select * if city in ('NY', 'LA')"``
   * - NOT filter
     - ``jq '.[] | select((.age > 30) | not)'``
     - ``... "select * if not age > 30"``
   * - LIKE filter
     - ``jq '.[] | select(.name | startswith("Al"))'``
     - ``... "select * if name like 'Al%'"``
   * - Uppercase
     - ``jq '.[] | {name: (.name | ascii_upcase)}'``
     - ``... "select upper(name) as name"``
   * - Group & count
     - ``jq 'group_by(.city) | map({city:.[0].city,count:length})'``
     - ``... "select city, count(*) as count group by city"``
   * - CASE/WHEN
     - ``jq '.[] | if .age>30 then "senior" else "junior" end'``
     - ``... "select case when age > 30 then 'senior' else 'junior' end as level"``
   * - COALESCE
     - ``jq '.[] | {d: (.nick // .name)}'``
     - ``... "select coalesce(nickname, name) as display"``
   * - IS NULL
     - ``jq '.[] | select(.email != null)'``
     - ``... "select * if email is not null"``
   * - String concat
     - ``jq '.[] | {f: (.first + " " + .last)}'``
     - ``... "select first || ' ' || last as full"``
   * - Type cast
     - ``jq '.[] | {p: (.price | tonumber)}'``
     - ``... "select float(price) as p"``
   * - Date convert
     - ``jq '.[] | {d: (.ts | todate)}'``
     - ``... "select todate(ts) as d"``
   * - Table output
     - (pipe through ``column -t``)
     - ``jonq data.json "select name, age" -t``
