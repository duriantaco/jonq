Usage
======

Overview
---------

`jonq` is a command-line tool that lets you query JSON files using a SQL-like syntax, making it approachable for users familiar with SQL while leveraging the power of the `jq` utility behind the scenes. Whether you're working with simple flat data or complex nested structures, `jonq` provides an intuitive way to select, filter, sort, group, and aggregate JSON data.

### Basic Command Structure

Run `jonq` with the following syntax:

.. code-block:: bash

   jonq <path/to/json_file> "<query>" [options]

**Available Options:**

- `--format, -f <csv|json>`: Choose output format (default: `json`).
- `--stream, -s`: Enable streaming mode for processing large files efficiently.
- `--fast, -F`: Use the Rust extension for faster processing (requires `jonq-fast`).
- `--format csv`: Output results in CSV format.
- `-h, --help`: Display the help message and exit.
- `format csv --fast > output.csv`: Redirect output to a file.
- `--version`: Show the version of `jonq`.

**Quick Example:**

.. code-block:: bash

   jonq users.json "select name, age if age > 30"

This command selects the `name` and `age` fields from `users.json` where the `age` is greater than 30.

Query Syntax Breakdown
-----------------------

The `jonq` query syntax mirrors SQL but is tailored for JSON. Here’s the full structure:

.. code-block:: sql

   select <fields> [from <path>] [if <condition>] [group by <fields>] [having <condition>] [sort <field> [asc|desc] [limit]]

- **`<fields>`**: Fields to select (e.g., `name`, `age`), including aliases, expressions, or aggregations.
- **`from <path>`**: Optional path to query a specific part of the JSON (e.g., `from [].orders`).
- **`if <condition>`**: Optional filter (e.g., `age > 30`).
- **`group by <fields>`**: Optional grouping (e.g., `group by city`).
- **`having <condition>`**: Optional filter on grouped results (e.g., `having count > 2`).
- **`sort <field>`**: Optional sorting field (e.g., `sort age`).
- **`asc|desc`**: Optional sort direction (default: `asc`).
- **`limit`**: Optional number of results (e.g., `5`).

Let’s dive into each part with detailed explanations and examples!

Field Selection
----------------

You can select specific fields, all fields, or even compute new values from your JSON data.

### Selecting Fields

- **All Fields (`*`):**

  .. code-block:: bash

     jonq data.json "select *"

  Retrieves all top-level fields in each JSON object.

- **Specific Fields:**

  .. code-block:: bash

     jonq data.json "select name, age"

  Returns only `name` and `age` from each object.

- **Nested Fields (Using Dot Notation):**

  .. code-block:: bash

     jonq data.json "select profile.age, profile.address.city"

  Accesses nested fields like `age` inside `profile` and `city` inside `address`.

- **Array Elements (Using Brackets):**

  .. code-block:: bash

     jonq data.json "select orders[0].item"

  Retrieves the `item` from the first element of the `orders` array.

- **Fields with Spaces or Special Characters (Quotes):**

  .. code-block:: bash

     jonq data.json "select 'first name', \"last-name\""

  Use single or double quotes for field names with spaces or special characters.

### Aliases

Rename fields in the output using `as`:

.. code-block:: bash

   jonq data.json "select name as full_name, age as years"

**Output Example:**

.. code-block:: json

   [
     {"full_name": "Alice", "years": 30},
     {"full_name": "Bob", "years": 25}
   ]

### Arithmetic Expressions

Perform calculations within the `select` clause:

.. code-block:: bash

   jonq data.json "select name, age + 10 as age_plus_10, price * 2 as doubled_price"

**Output Example:**

.. code-block:: json

   [
     {"name": "Alice", "age_plus_10": 40, "doubled_price": 2400},
     {"name": "Bob", "age_plus_10": 35, "doubled_price": 1000}
   ]

FROM Clause
------------

The `FROM` clause lets you target a specific part of the JSON structure, such as a nested array.

- **Basic Usage:**

  .. code-block:: bash

     jonq data.json "select order_id, item from [].orders"

  Queries the `orders` array within each top-level object.

- **With Filtering:**

  .. code-block:: bash

     jonq data.json "select order_id, price from [].orders if price > 800"

  Filters `orders` where `price` exceeds 800.

**Example JSON:**

.. code-block:: json

   [
     {"id": 1, "orders": [{"order_id": 101, "price": 1200}, {"order_id": 102, "price": 800}]},
     {"id": 2, "orders": [{"order_id": 103, "price": 500}]}
   ]

**Output:**

.. code-block:: json

   [
     {"order_id": 101, "price": 1200}
   ]

Filtering with Conditions
--------------------------

The `if` clause filters data based on conditions using comparison and logical operators.

### Basic Filtering

- **Comparison Operators:** `=`, `==`, `!=`, `>`, `<`, `>=`, `<=`

  .. code-block:: bash

     jonq data.json "select name, age if age >= 30"

- **String Equality:**

  .. code-block:: bash

     jonq data.json "select name if city = 'New York'"

### Logical Operators

Combine conditions with `and`, `or`, and parentheses:

- **Multiple Conditions:**

  .. code-block:: bash

     jonq data.json "select name if age > 25 and city = 'Chicago'"

- **With `or`:**

  .. code-block:: bash

     jonq data.json "select name if age > 30 or city = 'Los Angeles'"

- **Complex Logic:**

  .. code-block:: bash

     jonq data.json "select name if (age > 30 and city = 'Chicago') or profile.active = true"

### Advanced Operators

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

- **Limit Results:**

  .. code-block:: bash

     jonq data.json "select name, age sort age desc 3"

  Returns the top 3 results sorted by `age` descending.

Aggregation Functions
----------------------

Summarize data with built-in functions: `sum`, `avg`, `count`, `max`, `min`.

- **Sum:**

  .. code-block:: bash

     jonq data.json "select sum(age) as total_age"

- **Average:**

  .. code-block:: bash

     jonq data.json "select avg(price) as average_price from [].orders"

- **Count:**

  .. code-block:: bash

     jonq data.json "select count(*) as total_users"

- **Maximum:**

  .. code-block:: bash

     jonq data.json "select max(orders.price) as highest_price"

- **Minimum:**

  .. code-block:: bash

     jonq data.json "select min(age) as youngest"

### Combining Aggregations

.. code-block:: bash

   jonq data.json "select sum(price) as total, avg(price) as avg_price from [].orders"

**Output Example:**

.. code-block:: json

   {"total": 2500, "avg_price": 833.33}

Grouping Data
--------------

Use `group by` to aggregate data by categories.

- **Simple Grouping:**

  .. code-block:: bash

     jonq data.json "select city, count(*) as user_count group by city"

- **Multiple Fields:**

  .. code-block:: bash

     jonq data.json "select city, country, avg(age) as avg_age group by city, country"

Having Clause
-------------

Filter grouped results with `having`:

- **Basic Example:**

  .. code-block:: bash

     jonq data.json "select city, count(*) as count group by city having count > 2"

- **With Aggregation:**

  .. code-block:: bash

     jonq data.json "select city, avg(age) as avg_age group by city having avg_age >= 30"

- **Complex Conditions:**

  .. code-block:: bash

     jonq data.json "select city, sum(price) as total group by city having total > 1000 and count(*) > 1"

Output Formats
---------------

Choose how results are displayed:

- **JSON (Default):**

  .. code-block:: bash

      jonq data.json "select name, age"

- **CSV:**

  .. code-block:: bash

      jonq data.json "select name, age" --format csv

  **Output Example:**

  .. code-block:: text

     name,age
     Alice,30
     Bob,25

Optional
---------

For users dealing with large or complex nested JSON structures, we recommend installing the optional `jonq_fast` Rust extension. 

- **Fast:**

      jonq data.json "select name, age" --fast

Handling Large Files
---------------------

For big JSON files, use streaming mode:

.. code-block:: bash

   jonq large_data.json "select name, age" --stream

- **Requirement:** The JSON must be an array at the root level.
- **Benefit:** Processes data in chunks, reducing memory usage.

Tips and Tricks
----------------

### Debugging Queries

- **Test Small:** Start with a simple `select *` to verify the JSON structure.
- **Check Paths:** Use tools like `jq '.' data.json` to inspect nested paths.
- **Quote Strings:** Always quote string literals in conditions (e.g., `'New York'`).

### Optimizing Performance

- **Use FROM:** Narrow down the data with `from` to avoid processing unnecessary parts.
- **Limit Early:** Apply `limit` or strict `if` conditions to reduce output size.
- **Stream Large Files:** Always use `--stream` for files over 100MB.

### Working with Arrays

- **Unpack Arrays:** Use `from [].path` to query array elements directly.
- **Index Safely:** Check array lengths in your data to avoid out-of-bounds errors.

### Handling Nulls

- **Filter Nulls:** Add `if field != null` to exclude missing values.
- **Default Values:** Use expressions like `field + 0` to treat null as zero in calculations.

Best Practices
---------------

To optimize your experience with ``jonq``, follow these best practices:

- **Use the `from` Clause**: Specify a `from` clause (e.g., ``from [].orders``) to target specific JSON structures, reducing processed data (supported in `SYNTAX.md` and `jonq/query_parser.py`).
- **Limit Results Early**: Apply filters (e.g., ``if price > 1000``) and limits (e.g., ``sort age desc 5``) early in queries to minimize data handling (see `USAGE.md` examples).
- **Stream Large Files**: Use the ``--stream`` option for large JSON files to process data in chunks and avoid memory overload (implemented in `jonq/main.py` and `jonq/stream_utils.py`).
- **Test Queries on Small Data**: Validate queries on smaller JSON subsets before running on large datasets to ensure correctness and performance (a practical tip from usage patterns).
- **Handle Nulls Carefully**: Use conditions like ``age is not null`` to manage null values explicitly, as ``jonq`` handles them automatically but may need specific filtering (noted in `SYNTAX.md`).

Known Limitations
------------------

While ``jonq`` excels at lightweight JSON querying, it has some constraints based on its design and implementation:

- **Performance with Very Large Files**: Processing JSON files exceeding 100MB may be slow, even with streaming (``--stream``), due to JSON parsing overhead (noted in `README.md`).
- **Advanced jq Features**: Some complex ``jq`` functionalities (e.g., recursive descent or custom filters) are not exposed through ``jonq``’s SQL-like syntax (see `jonq/jq_filter.py`).
- **Multiple File Joins**: ``jonq`` does not support joining data across multiple JSON files, limiting it to single-file operations (evident from `jonq/main.py` accepting one file).
- **Custom Functions**: Users cannot define custom functions within queries, restricting extensibility (confirmed by `SYNTAX.md` lacking such syntax).
- **Date/Time Operations**: Limited support for parsing or manipulating date/time data (e.g., no date-specific functions in `SYNTAX.md` or test cases like `test_manual_edge.sh`).