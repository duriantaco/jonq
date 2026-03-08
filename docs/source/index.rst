Welcome to jonq's documentation!
================================

.. image:: https://img.shields.io/pypi/v/jonq.svg
   :target: https://pypi.org/project/jonq/
   :alt: PyPI Version

.. image:: https://img.shields.io/badge/Skylos-A%2B%20%28100%29-brightgreen
   :target: https://github.com/duriantaco/skylos
   :alt: Skylos Grade

jonq is a Python tool that provides a SQL-like syntax for querying JSON files, built as a wrapper around the powerful ``jq`` utility. It simplifies JSON querying for users familiar with SQL, making it easier to extract and manipulate data without needing to master ``jq``'s complex syntax.

.. important::

   jonq is NOT a database. It is NOT an alternative to DuckDB, Pandas, or Polars.
   jonq is a thin CLI wrapper that translates human-friendly queries into jq filters.

Key Features
-------------

- **SQL-like syntax**: ``select name, age if age > 30``
- **DISTINCT, LIMIT, IN, NOT, LIKE** operators
- **String functions**: ``upper``, ``lower``, ``length``
- **Math functions**: ``round``, ``abs``, ``ceil``, ``floor``
- **Aggregations**: ``sum``, ``avg``, ``min``, ``max``, ``count``, ``count(distinct ...)``
- **GROUP BY** with **HAVING**
- **Schema preview**: run ``jonq data.json`` with no query
- **Interactive REPL**: ``jonq -i data.json``
- **Watch mode**: ``--watch`` to re-run on file change
- **Multiple inputs**: local files, URLs, globs, stdin, NDJSON
- **Fuzzy suggestions**: typo correction for field names
- **Colorized output**: syntax-highlighted JSON in terminal

.. toctree::
   :maxdepth: 2
   :caption: Contents:

   installation
   usage
   usage_in_python
   comparison
   examples
   api
   contribution

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
