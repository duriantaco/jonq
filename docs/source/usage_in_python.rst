Usage in Python
=====================

``jonq`` ships with a small Python API for compiling and executing queries directly.

Quick Start
-----------

Use ``query(...)`` when you want Python data back immediately:

.. code-block:: python

   from jonq import query

   data = [
       {"name": "Alice", "age": 30, "city": "New York"},
       {"name": "Bob", "age": 25, "city": "LA"},
   ]

   rows = query(data, "select name, city if age > 26")
   print(rows)

.. code-block:: python

   [{"name": "Alice", "city": "New York"}]

Compiling Once, Reusing Many Times
----------------------------------

Use ``compile_query(...)`` when you want to reuse the generated jq filter:

.. code-block:: python

   from jonq import compile_query, query

   compiled = compile_query("select name if age > 25")

   result_1 = query([{"name": "Alice", "age": 30}], compiled)
   result_2 = query([{"name": "Bob", "age": 20}], compiled)

   print(compiled.jq_filter)
   print(result_1)
   print(result_2)

Structured Results
------------------

Use ``execute(...)`` when you want metadata such as the generated jq filter or raw text output:

.. code-block:: python

   from jonq import execute

   result = execute(
       [{"name": "Alice", "age": 30}],
       "select name, age",
       format="csv",
   )

   print(result.output_format)
   print(result.text)

Supported Inputs
----------------

The high-level API accepts:

- Python objects like ``dict`` and ``list``
- Raw JSON strings
- File paths (``str`` or ``pathlib.Path``)

Async Usage
-----------

Async variants are also available:

.. code-block:: python

   import asyncio
   from jonq import query_async

   async def main():
       rows = await query_async([{"name": "Alice"}], "select name")
       print(rows)

   asyncio.run(main())

CLI Fallback
------------

If you still prefer the CLI from Python, ``subprocess`` works as expected:

.. code-block:: python

   import json
   import subprocess

   result = subprocess.run(
       ["jonq", "simple.json", "select name, age if age > 25"],
       capture_output=True,
       text=True,
       check=True,
   )
   rows = json.loads(result.stdout)
