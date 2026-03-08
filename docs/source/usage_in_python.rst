Usage in Python
=====================

While ``jonq`` is designed as a command-line tool, you can integrate its functionality into Python scripts.

Calling jonq via subprocess
----------------------------

To use ``jonq``'s querying capabilities from within a Python script, you can call it via the ``subprocess`` module:

.. code-block:: python

   import subprocess
   import json

   def run_jonq(json_file, query):
       result = subprocess.run(['jonq', json_file, query], capture_output=True, text=True)
       if result.returncode == 0:
           return json.loads(result.stdout)
       else:
           raise Exception(result.stderr or result.stdout)

   try:
       data = run_jonq('simple.json', 'select name, age if age > 25')
       print(data)
   except Exception as e:
       print(f"Error: {e}")

**Example Output (using ``simple.json``):**

.. code-block:: json

   [
     {"name": "Alice", "age": 30},
     {"name": "Charlie", "age": 35}
   ]

Using jonq's Python modules directly
--------------------------------------

You can also import and use jonq's internal modules:

.. code-block:: python

   from jonq.csv_utils import flatten_json

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

   flattened = flatten_json(data, sep=".")
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

Additional Considerations
--------------------------

- **Performance**: For large JSON files, use the ``--stream`` option when calling ``jonq`` via ``subprocess``:

  .. code-block:: python

     result = subprocess.run(['jonq', 'large_data.json', 'select name, age', '--stream'], capture_output=True, text=True)

- **Error Handling**: Always check the return code and handle errors appropriately, as shown in the example.
- **Output Parsing**: The output from ``jonq`` is typically a JSON array or object. Use ``json.loads()`` to parse it into a Python data structure.

.. warning::
   Ensure that ``jonq`` is installed and accessible in your system's PATH. Verify this by running ``jonq --version`` from the command line.
