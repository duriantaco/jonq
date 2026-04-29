Usage
======

Overview
---------

``jonq`` is a command-line tool for exploring, extracting, and reshaping JSON with readable jq-powered queries. It keeps familiar ``select`` / ``if`` syntax for common cases, but the goal is still JSON-native terminal workflows rather than database-style analytics.

Basic Command Structure
~~~~~~~~~~~~~~~~~~~~~~~~

Run ``jonq`` with the following syntax:

.. code-block:: bash

   jonq <path/to/json_file> "<query>" [options]

**Available Options:**

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Option
     - Description
   * - ``--format, -f``
     - Output format: ``json`` (default), ``jsonl``, ``csv``, ``table``, ``yaml``
   * - ``-t, --table``
     - Shorthand for ``--format table``
   * - ``--stream, -s``
     - Process row-wise root-array queries in memory-friendly chunks
   * - ``--ndjson``
     - Force NDJSON mode (auto-detected by default)
   * - ``--follow``
     - Stream NDJSON from stdin line-by-line
   * - ``--limit, -n N``
     - Limit rows post-query
   * - ``--out, -o PATH``
     - Write output to file
   * - ``--jq``
     - Print generated jq filter and exit
   * - ``--explain``
     - Show parsed query breakdown and generated jq filter
   * - ``--time``
     - Print execution timing to stderr
   * - ``--pretty, -p``
     - Pretty-print JSON output
   * - ``--watch, -w``
     - Re-run query when file changes
   * - ``--no-color``
     - Disable colorized output
   * - ``--completions SHELL``
     - Print shell completion script (``bash``, ``zsh``, ``fish``)
   * - ``--version``
     - Show the installed jonq version
   * - ``-i <file>``
     - Interactive query mode (REPL) with tab completion
   * - ``-h, --help``
     - Show help message

**Quick Example:**

.. code-block:: bash

   jonq users.json "select name, age if age > 30"

This command selects the ``name`` and ``age`` fields from ``users.json`` where the ``age`` is greater than 30.

Query Syntax Breakdown
-----------------------

The ``jonq`` query syntax mirrors SQL but is tailored for JSON. Here's the full structure:

.. code-block:: sql

   select [distinct] <fields> [from <path>] [if <condition>] [group by <fields> [having <condition>]] [sort <field> [asc|desc]] [limit N]

- **``<fields>``**: Fields to select (e.g., ``name``, ``age``), including aliases, expressions, or aggregations.
- **``distinct``**: Optional keyword to return only unique rows.
- **``from <path>``**: Optional path to query a specific part of the JSON (e.g., ``from products``).
- **``if <condition>``**: Optional filter (e.g., ``age > 30``).
- **``group by <fields>``**: Optional grouping (e.g., ``group by city``).
- **``having <condition>``**: Optional filter on grouped results (e.g., ``having count > 2``).
- **``sort <field>``**: Optional sorting field (e.g., ``sort age``).
- **``asc|desc``**: Optional sort direction (default: ``asc``).
- **``limit N``**: Optional number of results (e.g., ``limit 5``).

Field Selection
----------------

You can select specific fields, all fields, or even compute new values from your JSON data.

Selecting Fields
~~~~~~~~~~~~~~~~~

- **All Fields (``*``):**

  .. code-block:: bash

     jonq data.json "select *"

  Retrieves all top-level fields in each JSON object.

- **Specific Fields:**

  .. code-block:: bash

     jonq data.json "select name, age"

  Returns only ``name`` and ``age`` from each object.

- **Nested Fields (Using Dot Notation):**

  .. code-block:: bash

     jonq data.json "select profile.age, profile.address.city"

  Accesses nested fields like ``age`` inside ``profile`` and ``city`` inside ``address``.

- **Array Elements (Using Brackets):**

  .. code-block:: bash

     jonq data.json "select orders[0].item"

  Retrieves the ``item`` from the first element of the ``orders`` array.

- **Fields with Spaces or Special Characters (Quotes):**

  .. code-block:: bash

     jonq data.json "select 'first name', \"last-name\""

  Use single or double quotes for field names with spaces or special characters.

DISTINCT
~~~~~~~~~

Return only unique rows:

.. code-block:: bash

   jonq data.json "select distinct city"
   jonq data.json "select distinct name, city"

Aliases
~~~~~~~~

Rename fields in the output using ``as``:

.. code-block:: bash

   jonq data.json "select name as full_name, age as years"

**Output Example:**

.. code-block:: json

   [
     {"full_name": "Alice", "years": 30},
     {"full_name": "Bob", "years": 25}
   ]

Arithmetic Expressions
~~~~~~~~~~~~~~~~~~~~~~~

Perform calculations within the ``select`` clause:

.. code-block:: bash

   jonq data.json "select name, age + 10 as age_plus_10, price * 2 as doubled_price"

String Functions
~~~~~~~~~~~~~~~~~

Transform string values with built-in functions:

.. code-block:: bash

   jonq data.json "select upper(name) as name_upper"     # ALICE, BOB, ...
   jonq data.json "select lower(city) as city_lower"     # new york, ...
   jonq data.json "select length(name) as name_len"      # 5, 3, ...

Math Functions
~~~~~~~~~~~~~~~

Apply math functions to numeric values:

.. code-block:: bash

   jonq data.json "select round(price) as price_rounded"
   jonq data.json "select abs(balance) as abs_balance"
   jonq data.json "select ceil(score) as score_ceil"
   jonq data.json "select floor(score) as score_floor"

Type Casting
~~~~~~~~~~~~~

Convert between types:

.. code-block:: bash

   jonq data.json "select int(price) as price"        # string → integer
   jonq data.json "select float(amount) as amount"     # string → float
   jonq data.json "select str(code) as code"           # number → string
   jonq data.json "select type(value) as t"            # get type name

Date/Time Functions
~~~~~~~~~~~~~~~~~~~~

Convert between epoch timestamps and ISO dates:

.. code-block:: bash

   jonq data.json "select todate(timestamp) as date"   # epoch → ISO date
   jonq data.json "select date(created_at) as d"       # alias for todate
   jonq data.json "select fromdate(iso_date) as epoch"  # ISO → epoch

Null-safe: returns ``null`` instead of crashing on null input.

CASE/WHEN Expressions
~~~~~~~~~~~~~~~~~~~~~~

Conditional logic inline in queries:

.. code-block:: bash

   jonq data.json "select name, case when age > 30 then 'senior' when age > 25 then 'mid' else 'junior' end as level"

Must include at least one ``WHEN ... THEN ...``, optional ``ELSE``, and close with ``END``.

COALESCE
~~~~~~~~~

Return the first non-null value:

.. code-block:: bash

   jonq data.json "select coalesce(nickname, name) as display"
   jonq data.json "select coalesce(todate(ts), 'unknown') as date"

String Concatenation
~~~~~~~~~~~~~~~~~~~~~

Use ``||`` (SQL standard) or ``+``:

.. code-block:: bash

   jonq data.json "select first || ' ' || last as full_name"
   jonq data.json "select name + ' (' + city + ')' as label"

IS NULL / IS NOT NULL
~~~~~~~~~~~~~~~~~~~~~~

Check for null values in conditions:

.. code-block:: bash

   jonq data.json "select name if email is not null"
   jonq data.json "select * if nickname is null"

FROM Clause
------------

The ``FROM`` clause lets you target a specific part of the JSON structure, such as a nested array.

- **Basic Usage:**

  .. code-block:: bash

     jonq data.json "select type, name from products"

  Queries the ``products`` array within the JSON.

- **With Filtering:**

  .. code-block:: bash

     jonq data.json "select order_id, price from [].orders if price > 800"

  Filters ``orders`` where ``price`` exceeds 800.

Filtering with Conditions
--------------------------

The ``if`` clause filters data based on conditions using comparison and logical operators.

Basic Filtering
~~~~~~~~~~~~~~~~

- **Comparison Operators:** ``=``, ``==``, ``!=``, ``>``, ``<``, ``>=``, ``<=``

  .. code-block:: bash

     jonq data.json "select name, age if age >= 30"

- **String Equality:**

  .. code-block:: bash

     jonq data.json "select name if city = 'New York'"

Logical Operators
~~~~~~~~~~~~~~~~~~

Combine conditions with ``and``, ``or``, and parentheses:

- **Multiple Conditions:**

  .. code-block:: bash

     jonq data.json "select name if age > 25 and city = 'Chicago'"

- **With ``or``:**

  .. code-block:: bash

     jonq data.json "select name if age > 30 or city = 'Los Angeles'"

- **Complex Logic:**

  .. code-block:: bash

     jonq data.json "select name if (age > 30 and city = 'Chicago') or profile.active = true"

Advanced Operators
~~~~~~~~~~~~~~~~~~~

- **IN (Set membership):**

  .. code-block:: bash

     jonq data.json "select * if city in ('New York', 'Chicago', 'Los Angeles')"

  Matches values in the given set.

- **NOT (Logical negation):**

  .. code-block:: bash

     jonq data.json "select * if not age > 30"

  Negates the condition.

- **LIKE (Pattern matching):**

  .. code-block:: bash

     jonq data.json "select * if name like 'Al%'"      # starts with "Al"
     jonq data.json "select * if name like '%ice'"      # ends with "ice"
     jonq data.json "select * if name like '%li%'"      # contains "li"

  Uses ``%`` as wildcard for pattern matching.

- **BETWEEN (Numeric Ranges):**

  .. code-block:: bash

     jonq data.json "select item, price from [].orders if price between 700 and 1000"

  Matches values inclusively between 700 and 1000.

- **CONTAINS (String Search):**

  .. code-block:: bash

     jonq data.json "select item from [].orders if item contains 'book'"

  Returns items with "book" in the string.

Sorting and Limiting
--------------------

Control the order and number of results.

- **Sort Ascending:**

  .. code-block:: bash

     jonq data.json "select name, age sort age"

- **Sort Descending:**

  .. code-block:: bash

     jonq data.json "select name, age sort age desc"

- **Inline Limit (after sort):**

  .. code-block:: bash

     jonq data.json "select name, age sort age desc 3"

  Returns the top 3 results sorted by ``age`` descending.

- **Standalone Limit:**

  .. code-block:: bash

     jonq data.json "select * limit 5"
     jonq data.json "select name, age if age > 25 limit 10"
     jonq data.json "select city, count(*) as cnt group by city limit 3"

  Can be used anywhere after the main query, independent of sorting.

Aggregation Functions
----------------------

Summarize data with built-in functions: ``sum``, ``avg``, ``count``, ``max``, ``min``.

- **Sum:**

  .. code-block:: bash

     jonq data.json "select sum(age) as total_age"

- **Average:**

  .. code-block:: bash

     jonq data.json "select avg(price) as average_price from [].orders"

- **Count:**

  .. code-block:: bash

     jonq data.json "select count(*) as total_users"

- **Count Distinct:**

  .. code-block:: bash

     jonq data.json "select count(distinct city) as unique_cities"

- **Maximum:**

  .. code-block:: bash

     jonq data.json "select max(age) as oldest"

- **Minimum:**

  .. code-block:: bash

     jonq data.json "select min(age) as youngest"

Combining Aggregations
~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: bash

   jonq data.json "select sum(price) as total, avg(price) as avg_price from [].orders"

Grouping Data
--------------

Use ``group by`` to aggregate data by categories.

- **Simple Grouping:**

  .. code-block:: bash

     jonq data.json "select city, count(*) as user_count group by city"

- **Multiple Fields:**

  .. code-block:: bash

     jonq data.json "select city, country, avg(age) as avg_age group by city, country"

Having Clause
-------------

Filter grouped results with ``having``:

- **Basic Example:**

  .. code-block:: bash

     jonq data.json "select city, count(*) as cnt group by city having cnt > 2"

- **With Aggregation:**

  .. code-block:: bash

     jonq data.json "select city, avg(age) as avg_age group by city having avg_age >= 30"

- **Complex Conditions:**

  .. code-block:: bash

     jonq data.json "select city, count(*) as cnt, avg(age) as avg_age group by city having cnt > 1 and avg_age > 25"

Output Formats
---------------

Choose how results are displayed:

- **JSON (Default):**

  .. code-block:: bash

      jonq data.json "select name, age"

- **Table:**

  .. code-block:: bash

      jonq data.json "select name, age" -t
      jonq data.json "select name, age" --format table

  Renders aligned columns with headers and separators.

- **CSV:**

  .. code-block:: bash

      jonq data.json "select name, age" --format csv

- **JSONL:**

  .. code-block:: bash

      jonq data.json "select name, age" --format jsonl

- **YAML:**

  .. code-block:: bash

      jonq data.json "select name, age" --format yaml

  Uses ``pyyaml`` if installed, built-in fallback otherwise.

Path Explorer
--------------

Run ``jonq`` with just a file (no query) to inspect nested JSON paths before writing a query:

.. code-block:: bash

   jonq data.json

This shows file info, nested paths with inferred types, and a truncated sample object.

Interactive REPL
-----------------

Launch an interactive session with tab completion and persistent history:

.. code-block:: bash

   jonq -i data.json

.. code-block:: text

   jonq interactive mode — querying data.json
   Type a query, or 'quit' to exit. Tab completes field names.

   jonq> select name, age
   [{"name":"Alice","age":30},{"name":"Bob","age":25}]
   jonq> select * if age > 28
   [{"id":1,"name":"Alice","age":30,"city":"New York"}]
   jonq> quit

Features: tab completion for field names + keywords, persistent history (``~/.jonq_history``), up/down arrow recall.

Watch Mode
-----------

Re-run a query automatically whenever the file changes:

.. code-block:: bash

   jonq data.json "select name, age" --watch

Multiple Input Sources
-----------------------

**URL Fetch:**

.. code-block:: bash

   jonq https://api.example.com/users.json "select name, email"

**Multi-File Glob:**

.. code-block:: bash

   jonq 'logs/*.json' "select * if level = 'error'"

**Stdin (auto-detected):**

.. code-block:: bash

   curl -s https://api.example.com/data | jonq "select id, name"
   cat data.json | jonq - "select name, age"

Follow Mode
------------

Stream NDJSON from stdin line-by-line, applying the query to each object:

.. code-block:: bash

   tail -f app.log | jonq --follow "select level, message if level = 'error'" -t

Non-matching lines are silently skipped. Combine with ``-t`` for table output or ``-f yaml`` for YAML.

Shell Completions
------------------

Generate completion scripts for your shell:

.. code-block:: bash

   # Bash
   eval "$(jonq --completions bash)"

   # Zsh
   eval "$(jonq --completions zsh)"

   # Fish
   jonq --completions fish > ~/.config/fish/completions/jonq.fish

Auto-detect NDJSON
-------------------

jonq auto-detects NDJSON (newline-delimited JSON) files. No flag needed:

.. code-block:: bash

   jonq data.ndjson "select name, age if age > 25"

You can still force it with ``--ndjson`` if needed. ``--ndjson`` cannot be combined with ``--stream``.

Fuzzy Field Suggestions
------------------------

When you mistype a field name, jonq suggests similar fields:

.. code-block:: text

   $ jonq data.json "select nme, agge"
   Field(s) 'nme, agge' not found. Available fields: age, city, id, name.
   Did you mean: 'nme' -> name; 'agge' -> age?

Colorized Output
-----------------

When outputting to a terminal, jonq auto-pretty-prints and colorizes JSON output with syntax highlighting. Pipe to a file or use ``--no-color`` to disable.

Handling Large Files
---------------------

For big JSON files, use streaming mode:

.. code-block:: bash

   jonq large_data.json "select name, age" --stream

- **Requirement:** The JSON must be an array at the root level.
- **Benefit:** Processes data in chunks in memory, avoiding temp chunk files in the main execution path.

Tips and Tricks
----------------

Debugging Queries
~~~~~~~~~~~~~~~~~~

- **Test Small:** Start with a simple ``select *`` to verify the JSON structure.
- **Use the Path Explorer:** Run ``jonq data.json`` (no query) to inspect nested paths and types.
- **See the jq filter:** Use ``--jq`` to see the generated jq filter, or ``--explain`` for a full breakdown.
- **Quote Strings:** Always quote string literals in conditions (e.g., ``'New York'``).

Optimizing Performance
~~~~~~~~~~~~~~~~~~~~~~~

- **Use FROM:** Narrow down the data with ``from`` to avoid processing unnecessary parts.
- **Limit Early:** Apply ``limit`` or strict ``if`` conditions to reduce output size.
- **Stream Large Files:** Use ``--stream`` for large root-array JSON files when you want lower-overhead chunk processing.

Working with Arrays
~~~~~~~~~~~~~~~~~~~~

- **Unpack Arrays:** Use ``from [].path`` to query array elements directly.
- **Index Safely:** Check array lengths in your data to avoid out-of-bounds errors.

Handling Nulls
~~~~~~~~~~~~~~~

- **Filter Nulls:** Use ``if field is not null`` or ``if field != null`` to exclude missing values.
- **Default Values:** Use ``coalesce(field, default)`` to provide fallback values.
- **Null-safe functions:** Date/time and type casting functions return ``null`` on null input instead of crashing.

Known Limitations
------------------

- **Performance with Very Large Files**: Processing JSON files exceeding 100MB may still be slow, even with streaming.
- **Advanced jq Features**: Some complex ``jq`` functionalities (e.g., recursive descent or custom filters) are not exposed through ``jonq``'s readable query syntax.
- **Joins**: ``jonq`` does not support joining data across multiple JSON files.
- **Custom Functions**: Users cannot define custom functions within queries.
- **Window Functions**: Not supported — use an analytical query engine for analytical queries.
