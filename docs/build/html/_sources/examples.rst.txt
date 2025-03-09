Examples
=========

Simple JSON
------------

Consider this simple JSON file (``simple.json``):

.. code-block:: json

   [
     {
       "id": 1,
       "name": "Alice",
       "age": 30,
       "city": "New York"
     },
     {
       "id": 2,
       "name": "Bob",
       "age": 25,
       "city": "Los Angeles"
     },
     {
       "id": 3,
       "name": "Charlie",
       "age": 35,
       "city": "Chicago"
     }
   ]

Select all fields:

.. code-block:: bash

   jonq simple.json "select *"

Output:

.. code-block:: json

   [
     {
       "id": 1,
       "name": "Alice",
       "age": 30,
       "city": "New York"
     },
     {
       "id": 2,
       "name": "Bob",
       "age": 25,
       "city": "Los Angeles"
     },
     {
       "id": 3,
       "name": "Charlie",
       "age": 35,
       "city": "Chicago"
     }
   ]

Select specific fields:

.. code-block:: bash

   jonq simple.json "select name, age"

Output:

.. code-block:: json

   [
     {
       "name": "Alice",
       "age": 30
     },
     {
       "name": "Bob",
       "age": 25
     },
     {
       "name": "Charlie",
       "age": 35
     }
   ]

Filter with conditions:

.. code-block:: bash

   jonq simple.json "select name, age if age > 30"

Output:

.. code-block:: json

   [
     {
       "name": "Charlie",
       "age": 35
     }
   ]

Sorting:

.. code-block:: bash

   jonq simple.json "select name, age sort age desc 2"

Output:

.. code-block:: json

   [
     {
       "name": "Charlie",
       "age": 35
     },
     {
       "name": "Alice",
       "age": 30
     }
   ]

Aggregation:

.. code-block:: bash

   jonq simple.json "select sum(age) as total_age"

Output:

.. code-block:: json

   {
     "total_age": 90
   }

Nested JSON
------------

For more complex, nested JSON files:

.. code-block:: json

   [
     {
       "id": 1,
       "name": "Alice",
       "profile": {
         "age": 30,
         "address": {
           "city": "New York",
           "zip": "10001"
         }
       },
       "orders": [
         {
           "order_id": 101,
           "item": "Laptop",
           "price": 1200
         },
         {
           "order_id": 102,
           "item": "Phone",
           "price": 800
         }
       ]
     },
     {
       "id": 2,
       "name": "Bob",
       "profile": {
         "age": 25,
         "address": {
           "city": "Los Angeles",
           "zip": "90001"
         }
       },
       "orders": [
         {
           "order_id": 103,
           "item": "Tablet",
           "price": 500
         }
       ]
     }
   ]

Query nested fields:

.. code-block:: bash

   jonq nested.json "select name, profile.age"

Output:

.. code-block:: json

   [
     {
       "name": "Alice",
       "age": 30
     },
     {
       "name": "Bob",
       "age": 25
     }
   ]

Access deeply nested fields:

.. code-block:: bash

   jonq nested.json "select name, profile.address.city"

Output:

.. code-block:: json

   [
     {
       "name": "Alice",
       "city": "New York"
     },
     {
       "name": "Bob",
       "city": "Los Angeles"
     }
   ]

Count items in arrays:

.. code-block:: bash

   jonq nested.json "select name, count(orders) as order_count"

Output:

.. code-block:: json

   [
     {
       "name": "Alice",
       "order_count": 2
     },
     {
       "name": "Bob",
       "order_count": 1
     }
   ]

Complex filtering:

.. code-block:: bash

   jonq nested.json "select name, profile.age if profile.address.city = 'New York' or orders[0].price > 1000"

Output:

.. code-block:: json

   [
     {
       "name": "Alice",
       "age": 30
     }
   ]

Group by with aggregation:

.. code-block:: bash

   jonq nested.json "select profile.address.city, avg(profile.age) as avg_age group by profile.address.city"

Output:

.. code-block:: json

   [
     {
       "city": "New York",
       "avg_age": 30
     },
     {
       "city": "Los Angeles",
       "avg_age": 25
     }
   ]