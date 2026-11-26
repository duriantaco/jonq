Cookbook
========

These recipes focus on the workflows jonq is meant to make fast: inspect unknown JSON, find the fields you need, and turn the result into a useful terminal-friendly shape.

jonq is still a jq-powered exploration and extraction tool. If the task becomes joins, window functions, repeated analytical queries, or long-running pipelines with connectors, use a database or ETL system instead.

Inspect Unknown JSON First
--------------------------

Inspect a saved API response to find the fields and the array that holds
the rows. This sample includes metadata alongside the ``users`` array.

.. code-block:: bash

   cat > response.json <<'JSON'
   {
     "meta": {"total": 2},
     "users": [{"name": "Asha", "age": 29}, {"name": "Jules", "age": 35}]
   }
   JSON
   jonq response.json

The inspector shows ``users[].name`` and suggests a query using
``from users``. Use that clause to select the array, then filter and
export the rows you need.

.. code-block:: bash

   jonq response.json "select age, name from users where age > 30" -t
   jonq response.json "select age, name from users where age > 30" --format csv --out older-users.csv

The CSV contains one row.

.. code-block:: text

   age,name
   35,Jules

Pipe JSON into ``jonq`` to inspect a response without saving it. NDJSON
files can be inspected the same way as ordinary JSON files.

.. code-block:: bash

   cat response.json | jonq
   jonq response.json "select * from users" --format jsonl --out users.ndjson
   jonq users.ndjson
   cat users.ndjson | jonq --ndjson "select name"

Turn API JSON Into a Table
--------------------------

Many APIs return arrays of objects. jonq is useful when you want a few readable columns instead of a large JSON blob.

.. code-block:: bash

   curl -s https://api.github.com/users/octocat/repos \
     | jonq "select name, stargazers_count as stars, pushed_at sort stargazers_count desc limit 10" -t

When you need the generated jq filter, add ``--explain``:

.. code-block:: bash

   curl -s https://api.github.com/users/octocat/repos \
     | jonq "select name, stargazers_count as stars limit 5" --explain

Flatten Nested Arrays
---------------------

Use ``from`` when the rows you care about live inside nested arrays.

.. code-block:: json

   [
     {
       "name": "Alice",
       "orders": [
         {"order_id": 101, "item": "Laptop", "price": 1200},
         {"order_id": 102, "item": "Phone", "price": 800}
       ]
     },
     {
       "name": "Bob",
       "orders": [
         {"order_id": 103, "item": "Tablet", "price": 500}
       ]
     }
   ]

.. code-block:: bash

   jonq users.json "select order_id, item, price from [].orders if price > 700" -t

This treats each order as a row and then filters by ``price``.

Export JSON to CSV or JSONL
---------------------------

Use CSV when the next step is a spreadsheet or a tabular tool:

.. code-block:: bash

   jonq users.json "select id, name, city" --format csv > users.csv

Use JSONL when the next step expects one JSON object per line:

.. code-block:: bash

   jonq users.json "select id, name, city" --format jsonl > users.jsonl

Use raw output for shell loops and simple command substitution:

.. code-block:: bash

   jonq users.json "select name" -r

Follow NDJSON Logs
------------------

For newline-delimited JSON logs, combine ``tail -f`` with ``--follow``:

.. code-block:: bash

   tail -f app.ndjson \
     | jonq --follow "select timestamp, level, message if level = 'error'" -t

This is for line-by-line log inspection. Use non-follow mode when you need global operations such as grouping, sorting, distinct, or aggregation.

Recover From Field Typos
------------------------

If you mistype a field, jonq validates the query against the payload and prints a copy-pasteable repair suggestion:

.. code-block:: bash

   jonq users.json "select nme"

.. code-block:: text

   Error: Unknown field(s): nme
   Did you mean: nme -> name?
   Available fields: id, name, age, city
   Try: jonq users.json "select name"

This is most useful while exploring unfamiliar payloads where field names are long, nested, or easy to mistype.

Know When to Drop to jq
-----------------------

Use raw jq when you need full jq language control, complex reductions, custom recursive transforms, or jq modules.

Use jonq when the task is common enough to read like:

.. code-block:: text

   select these fields
   from this nested array
   where this condition is true
   sort and limit the rows
   print as table, CSV, JSONL, YAML, JSON, or raw values

That boundary keeps jonq useful without turning it into a second full query language.
