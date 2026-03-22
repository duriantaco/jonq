API Reference
=============

High-Level Python API (jonq.api)
--------------------------------

**compile_query(query)**

Compile a jonq query string into a reusable ``CompiledQuery`` object.

- **Parameters:** ``query`` (str)
- **Returns:** ``CompiledQuery``

**query(source, query, ...)**

Execute a query and return parsed Python data by default.

- **Parameters:**
  - ``source``: Python object, raw JSON string, or file path
  - ``query`` (str or ``CompiledQuery``)
- **Returns:** Parsed Python data, or raw text when ``format="json"`` or ``format="csv"``

**execute(source, query, ...)**

Execute a query and return a structured ``QueryResult`` object.

- **Parameters:**
  - ``source``: Python object, raw JSON string, or file path
  - ``query`` (str or ``CompiledQuery``)
- **Returns:** ``QueryResult`` with ``text``, ``data``, and ``compiled`` metadata

**query_async(...) / execute_async(...)**

Async variants of the high-level execution helpers.

Main Module (jonq.main)
-----------------------

**main()**

The entry point for the jonq command-line tool.

**Usage:**

.. code-block:: bash

   jonq <path/to/json_file> "<query>" [--format csv|json] [--stream] [--watch] [--jq] [--pretty] [--no-color] [--ndjson] [--limit N] [--out PATH] [--version]

Query Parser (jonq.query_parser)
--------------------------------

**tokenize_query(query)**

Tokenizes a query string into a list of tokens.

- **Parameters:** ``query`` (str)
- **Returns:** List of string tokens
- **Raises:** ``ValueError`` if syntax is invalid

**parse_query(tokens)**

Parses tokens into structured query components.

- **Parameters:** ``tokens`` (list)
- **Returns:** Tuple ``(fields, condition, group_by, having, order_by, sort_direction, limit, from_path, distinct)``
- **Raises:** ``ValueError`` if syntax is invalid

JQ Filter (jonq.jq_filter)
--------------------------

**generate_jq_filter(fields, condition, group_by, having, order_by, sort_direction, limit, from_path, distinct)**

Generates a jq filter string from parsed query components.

- **Parameters:**
  - ``fields`` (list): Field specifications
  - ``condition`` (str): Filter condition
  - ``group_by`` (list): Fields to group by
  - ``having`` (str): Condition for grouped results
  - ``order_by`` (str): Field to sort by
  - ``sort_direction`` (str): 'asc' or 'desc'
  - ``limit`` (str): Result limit
  - ``from_path`` (str): Path for FROM clause
  - ``distinct`` (bool): Whether to return unique results
- **Returns:** jq filter string

Executor (jonq.executor)
------------------------

**run_jq(json_file, jq_filter)**

Executes a jq filter against a JSON file (synchronous).

- **Parameters:**
  - ``json_file`` (str): Path to JSON file
  - ``jq_filter`` (str): jq filter string
- **Returns:** Tuple ``(stdout, stderr)``
- **Raises:** ``ValueError``, ``FileNotFoundError``

**run_jq_async(json_file, jq_filter)**

Executes a jq filter against a JSON file (async).

- **Parameters:**
  - ``json_file`` (str): Path to JSON file
  - ``jq_filter`` (str): jq filter string
- **Returns:** Tuple ``(stdout, stderr)``

CSV Utils (jonq.csv_utils)
--------------------------

**flatten_json(data, parent_key='', sep='.')**

Flattens nested JSON for CSV output.

- **Parameters:**
  - ``data``: JSON data
  - ``parent_key`` (str): Parent key for recursion
  - ``sep`` (str): Separator for nested keys
- **Returns:** Flattened dictionary

**json_to_csv(json_data)**

Converts JSON data to CSV format.

- **Parameters:** ``json_data`` (str or dict/list)
- **Returns:** CSV string

Error Handler (jonq.error_handler)
-----------------------------------

**validate_query_against_schema(json_file, query)**

Validates query field names against the JSON file's actual fields. Provides fuzzy suggestions when field names are close to valid ones.

- **Parameters:**
  - ``json_file`` (str): Path to JSON file
  - ``query`` (str): The query string
- **Returns:** Error message string with suggestions, or ``None`` if valid

**handle_error_with_context(error, json_file, query, jq_filter)**

Analyzes jq errors and provides user-friendly error messages with suggestions.

- **Parameters:**
  - ``error``: The exception
  - ``json_file`` (str): Path to JSON file
  - ``query`` (str): The query string
  - ``jq_filter`` (str): The generated jq filter
