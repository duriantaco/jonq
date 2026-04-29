Welcome to jonq's documentation!
================================

.. image:: https://img.shields.io/pypi/v/jonq.svg
   :target: https://pypi.org/project/jonq/
   :alt: PyPI Version

.. image:: https://img.shields.io/badge/Skylos-A%2B%20%28100%29-brightgreen
   :target: https://github.com/duriantaco/skylos
   :alt: Skylos Grade

jonq is a command-line JSON tool for exploring, extracting, and reshaping payloads with readable jq-powered queries. It keeps familiar ``select`` / ``if`` syntax for common cases, accepts ``where`` as a filter alias, and stays focused on JSON-native terminal workflows.

.. important::

   jonq is not a database, ETL system, or full jq replacement.
   Use it to understand and shape JSON quickly from the shell.

Key Features
-------------

- **Readable jq syntax**: ``select name, age if age > 30``
- **DISTINCT, LIMIT, IN, NOT, LIKE, IS NULL** operators
- **CASE/WHEN**: conditional expressions inline
- **COALESCE**: null fallback with nested function support
- **String concat**: ``||`` or ``+`` for concatenation
- **String functions**: ``upper``, ``lower``, ``length``, ``trim``
- **Math functions**: ``round``, ``abs``, ``ceil``, ``floor``
- **Type casting**: ``int``, ``float``, ``str``, ``type``
- **Date/time**: ``todate``, ``fromdate``, ``date``
- **Aggregations**: ``sum``, ``avg``, ``min``, ``max``, ``count``, ``count(distinct ...)``
- **GROUP BY** with **HAVING**
- **Table output**: ``-t`` for aligned terminal tables
- **JSONL / YAML output**: ``--format jsonl`` and ``--format yaml``
- **Raw scalar output**: ``-r`` for unquoted values in shell pipelines
- **Path explorer**: run ``jonq data.json`` with no query
- **Interactive REPL**: ``jonq -i data.json`` with tab completion and history
- **Follow mode**: ``--follow`` to stream NDJSON line-by-line
- **Streaming mode**: ``--stream`` for row-wise root-array queries
- **Watch mode**: ``--watch`` to re-run on file change
- **Multiple inputs**: local files, URLs, globs, stdin (auto-detected), NDJSON
- **Shell completions**: ``--completions bash|zsh|fish``
- **Explain mode**: ``--explain`` to see query breakdown and jq filter
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
