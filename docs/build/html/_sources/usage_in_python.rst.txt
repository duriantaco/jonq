usage in python
=====================

While `jonq` is designed as a command-line tool, you can integrate its functionality into Python scripts in two ways:

1. **Using the `jonq_fast` extension** (if installed) for efficient JSON flattening.
2. **Calling `jonq` via the `subprocess` module** to execute queries from within Python.

This section provides examples and guidance for both approaches.

Using jonq_fast
----------------

If you have installed the optional `jonq-fast` extension (via `pip install jonq-fast`), you can use its `flatten` function directly in your Python code to flatten nested JSON structures efficiently. This is particularly useful for preparing JSON data for further processing, such as generating CSV output or performing data analysis.

### Example: Flattening JSON with `jonq_fast`

.. code-block:: python

   import jonq_fast

   data = {
       "user": {
           "name": "Alice",
           "address": {"city": "New York"},
           "orders": [
               {"id": 1, "item": "Laptop", "price": 1200},
               {"id": 2, "item": "Phone", "price": 800}
           ]
       }
   }

   flattened = jonq_fast.flatten(data, ".")

   print(flattened)

**Output:**

.. code-block:: json

   {
     "user.name": "Alice",
     "user.address.city": "New York",
     "user.orders.0.id": 1,
     "user.orders.0.item": "Laptop",
     "user.orders.0.price": 1200,
     "user.orders.1.id": 2,
     "user.orders.1.item": "Phone",
     "user.orders.1.price": 800
   }

The `flatten` function takes two arguments:

- `data`: The JSON object (as a Python dictionary or list) to flatten.
- `sep`: The separator to use for nested keys (e.g., `"."` for dot notation).

This function leverages Rust for improved performance, making it ideal for large or deeply nested JSON structures.

.. note::
   Ensure that `jonq-fast` is installed by running `pip install jonq-fast`. Without it, this functionality is unavailable.

Calling jonq via subprocess
----------------------------

To use `jonq`'s querying capabilities from within a Python script, you can call it via the `subprocess` module. This allows you to execute `jonq` commands programmatically and capture the output for further processing.

### Example: Running a `jonq` Query from Python

.. code-block:: python

   import subprocess
   import json

   def run_jonq(json_file, query):
       result = subprocess.run(['jonq', json_file, query], capture_output=True, text=True)
       if result.returncode == 0:
           return json.loads(result.stdout)
       else:
           raise Exception(result.stderr)

   try:
       data = run_jonq('simple.json', 'select name, age if age > 25')
       print(data)
   except Exception as e:
       print(f"Error: {e}")

**Example Output (using `simple.json` from the Examples section):**

.. code-block:: json

   [
     {"name": "Alice", "age": 30},
     {"name": "Charlie", "age": 35}
   ]

In this example:

- The `run_jonq` function executes a `jonq` query on the specified JSON file.
- It captures the output and parses it as JSON if the command succeeds.
- If `jonq` returns an error (e.g., invalid query or file not found), it raises an exception with the error message.

This approach is useful for integrating `jonq` into larger Python workflows, such as data pipelines or automated scripts.

.. warning::
   Ensure that `jonq` is installed and accessible in your system's PATH. Verify this by running `jonq --version` from the command line.

Additional Considerations
--------------------------

- **Performance**: For large JSON files, use the `--stream` option when calling `jonq` via `subprocess` to process data in chunks:

  .. code-block:: python

     result = subprocess.run(['jonq', 'large_data.json', 'select name, age', '--stream'], capture_output=True, text=True)

- **Error Handling**: Always check the return code and handle errors appropriately, as shown in the example.
- **Output Parsing**: The output from `jonq` is typically a JSON array or object. Use `json.loads()` to parse it into a Python data structure.

By leveraging these methods, you can incorporate `jonq`'s powerful JSON querying capabilities into your Python projects.