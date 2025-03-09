Usage
======

Basic Usage
------------

jonq provides a command-line interface for querying JSON files using a SQL-like syntax.

The basic syntax is:

.. code-block:: bash

   jonq <path/to/json_file> "<query>"

Query Syntax
-------------

The query syntax follows a simplified SQL format:

.. code-block:: sql

   select <fields> [if <condition>] [group by <fields>] [sort <field> [asc|desc] [limit]]

Where:

* ``<fields>`` - Comma-separated list of fields to select or aggregations
* ``if <condition>`` - Optional filtering condition
* ``group by <fields>`` - Optional grouping by one or more fields
* ``sort <field>`` - Optional field to sort by
* ``asc|desc`` - Optional sort direction (default: asc)
* ``limit`` - Optional integer to limit the number of results

Field Selection
----------------

To select all fields:

.. code-block:: bash

   jonq data.json "select *"

To select specific fields:

.. code-block:: bash

   jonq data.json "select name, age"

Nested fields can be accessed using dot notation:

.. code-block:: bash

   jonq data.json "select name, profile.age, profile.address.city"

Array elements can be accessed using square brackets:

.. code-block:: bash

   jonq data.json "select name, orders[0].item"

You can use quotes for fields with spaces or special characters:

.. code-block:: bash

   jonq data.json "select 'first name', address.'street address'"

Filtering
----------

Filter results using the ``if`` keyword:

.. code-block:: bash

   jonq data.json "select name, age if age > 30"

Combine conditions with ``and`` and ``or``:

.. code-block:: bash

   jonq data.json "select name, age if age > 25 and city = 'New York'"
   jonq data.json "select name, age if age > 30 or city = 'Los Angeles'"

Use parentheses for complex expressions:

.. code-block:: bash

   jonq data.json "select name, age if (age > 30 and city = 'Chicago') or (age < 25 and city = 'New York')"

Sorting and Limiting
---------------------

Sort results by a field:

.. code-block:: bash

   jonq data.json "select name, age sort age"

Sort in descending order:

.. code-block:: bash

   jonq data.json "select name, age sort age desc"

Limit the number of results:

.. code-block:: bash

   jonq data.json "select name, age sort age desc 5"

Aggregation Functions
----------------------

jonq supports several aggregation functions:

* ``sum()`` - Calculate the sum of values
* ``avg()`` - Calculate the average of values
* ``count()`` - Count the number of items
* ``max()`` - Find the maximum value
* ``min()`` - Find the minimum value

Examples:

.. code-block:: bash

   jonq data.json "select sum(age) as total_age"
   jonq data.json "select avg(age) as average_age"
   jonq data.json "select count(*) as user_count"
   jonq data.json "select max(orders.price) as highest_price"
   jonq data.json "select min(orders.price) as lowest_price"

You can use aliases with the ``as`` keyword:

.. code-block:: bash

   jonq data.json "select count(*) as total_users"

Grouping
---------

Group data and perform aggregations per group:

.. code-block:: bash

   jonq data.json "select city, count(*) as user_count group by city"
   jonq data.json "select city, avg(age) as avg_age group by city"