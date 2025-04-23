Comparison
===========

Below is a comparison of ``jonq`` with Pandas and DuckDB, highlighting their differences in use cases, setup, and capabilities.

.. list-table::
   :header-rows: 1
   :widths: 20 30 30 30

   * - Aspect
     - **jonq**
     - **Pandas**
     - **DuckDB**
   * - Primary Use Case
     - Fast, lightweight JSON querying from the command line
     - General-purpose data manipulation and analysis in Python
     - Analytical SQL queries on large datasets, including JSON
   * - Setup
     - Minimal: requires only ``jq`` and Python
     - Requires a Python environment with Pandas installed
     - Requires installing DuckDB
   * - Query Language
     - SQL-like syntax (e.g., ``select name, age if age > 30``)
     - Python code (e.g., ``df[df['age'] > 30]``)
     - SQL with JSON functions (e.g., ``SELECT * FROM read_json(...)``)
   * - Footprint
     - Small (~500 KB for ``jq``)
     - Larger (~20 MB for Pandas)
     - Larger (~140 MB for DuckDB)
   * - Streaming
     - Supports streaming for large JSON files (``--stream`` option)
     - Can handle large files with chunking (e.g., ``pd.read_json(..., chunksize=...)``)
     - Must load data into tables
   * - Memory Usage
     - Low, due to streaming capabilities
     - Higher, typically loads data into memory
     - Optimized for large datasets with columnar storage
   * - Ecosystem
     - Leverages ``jq`` for post-processing
     - Integrates with Python data science tools (NumPy, Matplotlib)
     - Can be used standalone or with Python