Examples
========

Simple JSON
-----------

Consider `simple.json`:

.. code-block:: json

   [
     {"id": 1, "name": "Alice", "age": 30, "city": "New York"},
     {"id": 2, "name": "Bob", "age": 25, "city": "Los Angeles"},
     {"id": 3, "name": "Charlie", "age": 35, "city": "Chicago"}
   ]

- **Select all fields:**

  .. code-block:: bash

     jonq simple.json "select *"

  **Output:**

  .. code-block:: json

     [
       {"id": 1, "name": "Alice", "age": 30, "city": "New York"},
       {"id": 2, "name": "Bob", "age": 25, "city": "Los Angeles"},
       {"id": 3, "name": "Charlie", "age": 35, "city": "Chicago"}
     ]

- **Filter and sort:**

  .. code-block:: bash

     jonq simple.json "select name, age if age > 25 sort age desc 2"

  **Output:**

  .. code-block:: json

     [
       {"name": "Charlie", "age": 35},
       {"name": "Alice", "age": 30}
     ]

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

Consider `nested.json`:

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

Complex JSON
------------

Consider `complex.json` (abbreviated):

.. code-block:: json

   {
     "company": {
       "subsidiaries": [
         {"name": "TechCorp Asia", "employees": 250, "financials": {"revenue": 42000000}},
         {"name": "TechCorp Europe", "employees": 300, "financials": {"revenue": 58000000}}
       ]
     },
     "products": [
       {"id": "P001", "type": "Software", "versions": [{"pricing": {"monthly": 199.99}}]},
       {"id": "P002", "type": "Software", "versions": [{"pricing": {"monthly": 149.99}}]}
     ]
   }
  
- **Filtering:**

  .. code-block:: bash

      jonq complex.json "select name, founded from company.subsidiaries[] if founded > 2008"

  **Output:**

  .. code-block:: json

     [
       {"name": "TechCorp Asia", "founded": 2010},
     ]

- **Deep nesting:**

  .. code-block:: bash

     jonq complex.json "select company.headquarters.coordinates.latitude"

  **Output:**
  .. code-block:: json

     {
       "latitude": 37.7749
     }
     
- **Complex grouping:**

  .. code-block:: bash

     jonq complex.json "select type, avg(versions[].pricing.monthly) as avg_price group by type from products[]"

  **Output:**

  .. code-block:: json

     [
       {"type": "Software", "avg_price": 216.67}
     ]