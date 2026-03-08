Examples
========

Simple JSON
-----------

Consider ``simple.json``:

.. code-block:: json

   [
     {"id": 1, "name": "Alice", "age": 30, "city": "New York"},
     {"id": 2, "name": "Bob", "age": 25, "city": "Los Angeles"},
     {"id": 3, "name": "Charlie", "age": 35, "city": "Chicago"}
   ]

- **Select all fields:**

  .. code-block:: bash

     jonq simple.json "select *"

- **Filter and sort:**

  .. code-block:: bash

     jonq simple.json "select name, age if age > 25 sort age desc 2"

  **Output:**

  .. code-block:: json

     [
       {"name": "Charlie", "age": 35},
       {"name": "Alice", "age": 30}
     ]

- **Distinct values:**

  .. code-block:: bash

     jonq simple.json "select distinct city"

- **Standalone limit:**

  .. code-block:: bash

     jonq simple.json "select * limit 2"

- **IN operator:**

  .. code-block:: bash

     jonq simple.json "select * if city in ('New York', 'Chicago')"

- **NOT operator:**

  .. code-block:: bash

     jonq simple.json "select * if not age > 30"

- **LIKE operator:**

  .. code-block:: bash

     jonq simple.json "select * if name like 'Al%'"

- **String functions:**

  .. code-block:: bash

     jonq simple.json "select upper(name) as name_upper"

  **Output:**

  .. code-block:: json

     [
       {"name_upper": "ALICE"},
       {"name_upper": "BOB"},
       {"name_upper": "CHARLIE"}
     ]

- **Math functions:**

  .. code-block:: bash

     jonq simple.json "select round(age) as rounded_age"

- **Count distinct:**

  .. code-block:: bash

     jonq simple.json "select count(distinct city) as unique_cities"

- **Aggregation with having:**

  .. code-block:: bash

     jonq simple.json "select city, avg(age) as avg_age group by city having avg_age > 25"

  **Output:**

  .. code-block:: json

     [
       {"city": "Chicago", "avg_age": 35},
       {"city": "New York", "avg_age": 30}
     ]

- **Arithmetic expression:**

  .. code-block:: bash

     jonq simple.json "select max(age) - min(age) as age_range"

  **Output:**

  .. code-block:: json

     {"age_range": 10}

Nested JSON
-----------

Consider ``nested.json``:

.. code-block:: json

   [
     {
       "id": 1, "name": "Alice",
       "profile": {"age": 30, "address": {"city": "New York", "zip": "10001"}},
       "orders": [
         {"order_id": 101, "item": "Laptop", "price": 1200},
         {"order_id": 102, "item": "Phone", "price": 800}
       ]
     },
     {
       "id": 2, "name": "Bob",
       "profile": {"age": 25, "address": {"city": "Los Angeles", "zip": "90001"}},
       "orders": [
         {"order_id": 103, "item": "Tablet", "price": 500}
       ]
     }
   ]

- **Nested fields:**

  .. code-block:: bash

     jonq nested.json "select name, profile.address.city"

  **Output:**

  .. code-block:: json

     [
       {"name": "Alice", "city": "New York"},
       {"name": "Bob", "city": "Los Angeles"}
     ]

- **Array operations:**

  .. code-block:: bash

     jonq nested.json "select name, count(orders) as order_count"

  **Output:**

  .. code-block:: json

     [
       {"name": "Alice", "order_count": 2},
       {"name": "Bob", "order_count": 1}
     ]

- **BETWEEN operator:**

  .. code-block:: bash

     jonq nested.json "select order_id, price from [].orders if price between 700 and 1000"

  **Output:**

  .. code-block:: json

     [
       {"order_id": 102, "price": 800}
     ]

- **CONTAINS operator:**

  .. code-block:: bash

     jonq nested.json "select order_id, item from [].orders if item contains 'a'"

  **Output:**

  .. code-block:: json

     [
       {"order_id": 101, "item": "Laptop"},
       {"order_id": 103, "item": "Tablet"}
     ]

- **FROM clause:**

  .. code-block:: bash

     jonq nested.json "select type, name from products"

Multiple Input Sources
-----------------------

- **URL fetch:**

  .. code-block:: bash

     jonq https://api.example.com/users.json "select name, email"

- **Glob multiple files:**

  .. code-block:: bash

     jonq 'logs/*.json' "select * if level = 'error'"

- **Stdin:**

  .. code-block:: bash

     cat data.json | jonq - "select name, age"

- **NDJSON (auto-detected):**

  .. code-block:: bash

     jonq data.ndjson "select name, age if age > 25"
