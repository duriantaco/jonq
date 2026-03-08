Comparison
===========

jonq vs DuckDB vs Pandas
--------------------------

jonq is **not** in the same category as DuckDB or Pandas. This table exists to show **when to reach for what**, not to compare them as competitors.

.. important::

   jonq is a thin CLI wrapper that translates human-friendly queries into jq filters.
   If you need analytics, joins, window functions, or anything beyond simple JSON wrangling — use a real database.

.. list-table::
   :header-rows: 1
   :widths: 20 27 27 27

   * - Aspect
     - **jonq**
     - **DuckDB**
     - **Pandas**
   * - What it is
     - CLI wrapper around jq
     - Embedded analytical database
     - Data manipulation library
   * - Use when
     - Quick JSON field extraction, one-liners, shell scripts
     - SQL analytics on large datasets, joins, aggregations
     - Data science, cleaning, transformation in Python
   * - Install size
     - ~500 KB (jq)
     - ~140 MB
     - ~20 MB
   * - Query Language
     - SQL-like syntax (``select name, age if age > 30``)
     - SQL with JSON functions (``SELECT * FROM read_json(...)``)
     - Python code (``df[df['age'] > 30]``)
   * - Joins
     - No
     - Yes
     - Yes
   * - Window functions
     - No
     - Yes
     - Yes
   * - Scales to GB+
     - No
     - Yes
     - With effort
   * - Streaming
     - Yes (``--stream`` option)
     - Must load data into tables
     - Can chunk with ``pd.read_json(..., chunksize=...)``
   * - Memory Usage
     - Low, due to streaming capabilities
     - Optimized with columnar storage
     - Higher, typically loads data into memory

**TL;DR:** If you need to ``select name, age if age > 30`` from a JSON file in your terminal, use jonq. For anything more, use DuckDB or Pandas.

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
