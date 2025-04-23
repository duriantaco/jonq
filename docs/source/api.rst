API Reference
=============

Main Module (jonq.main)
-----------------------

**main()**

The entry point for the jonq command-line tool. It:

- Parses command-line arguments
- Validates the input JSON file
- Tokenizes and parses the query
- Generates and executes a jq filter
- Handles output formatting (JSON or CSV)

**Usage:**

.. code-block:: bash

   jonq <path/to/json_file> "<query>" [--format csv|json] [--stream]

Query Parser (jonq.query_parser)
--------------------------------

**tokenize_query(query)**

Tokenizes a query string into a list of tokens.

- **Parameters:** `query` (str)
- **Returns:** List of string tokens
- **Raises:** `ValueError` if syntax is invalid

**parse_query(tokens)**

Parses tokens into structured query components.

- **Parameters:** `tokens` (list)
- **Returns:** Tuple `(fields, condition, group_by, having, order_by, sort_direction, limit, from_path)`
- **Raises:** `ValueError` if syntax is invalid

JQ Filter (jonq.jq_filter)
--------------------------

**generate_jq_filter(fields, condition, group_by, having, order_by, sort_direction, limit, from_path)**

Generates a jq filter string from parsed query components.

- **Parameters:**
  - `fields` (list): Field specifications
  - `condition` (str): Filter condition
  - `group_by` (list): Fields to group by
  - `having` (str): Condition for grouped results
  - `order_by` (str): Field to sort by
  - `sort_direction` (str): 'asc' or 'desc'
  - `limit` (str): Result limit
  - `from_path` (str): Path for FROM clause
- **Returns:** jq filter string

Executor (jonq.executor)
------------------------

**run_jq(json_file, jq_filter)**

Executes a jq filter against a JSON file.

- **Parameters:**
  - `json_file` (str): Path to JSON file
  - `jq_filter` (str): jq filter string
- **Returns:** Tuple `(stdout, stderr)`
- **Raises:** `ValueError`, `RuntimeError`

**run_jq_streaming(json_file, jq_filter, chunk_size=1000)**

Executes a jq filter in streaming mode.

- **Parameters:**
  - `json_file` (str): Path to JSON file
  - `jq_filter` (str): jq filter string
  - `chunk_size` (int): Number of items per chunk
- **Returns:** Tuple `(stdout, stderr)`

CSV Utils (jonq.csv_utils)
--------------------------

**flatten_json(data, parent_key='', sep='.')**

Flattens nested JSON for CSV output.

- **Parameters:**
  - `data`: JSON data
  - `parent_key` (str): Parent key for recursion
  - `sep` (str): Separator for nested keys
- **Returns:** Flattened dictionary

**json_to_csv(json_data)**

Converts JSON data to CSV format.

- **Parameters:** `json_data` (str or dict/list)
- **Returns:** CSV string