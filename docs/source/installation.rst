Installation
=============

Prerequisites
--------------

Before installing jonq, ensure you have the following:

* Python 3.9 or higher
* jq command line tool installed

Installing jq
--------------

jonq requires the jq command-line tool to be installed on your system.

For Linux (Debian/Ubuntu):

.. code-block:: bash

   sudo apt-get install jq

For macOS using Homebrew:

.. code-block:: bash

   brew install jq

For Windows using Chocolatey:

.. code-block:: bash

   choco install jq

You can verify jq is installed correctly by running:

.. code-block:: bash

   jq --version

Installing jonq
----------------

Install jonq using pip:

.. code-block:: bash

   pip install jonq

For improved performance, especially when processing large or complex JSON structures (e.g., for CSV output), install the optional **jonq-fast** Rust extension:

.. code-block:: bash 

   pip install jonq-fast

- **Purpose**: **jonq-fast** provides a faster JSON flattening implementation, beneficial when using the `--fast` or `-F` option with CSV output.
- **Requirements**: Typically, `pip install jonq-fast` installs a pre-built wheel. If a wheel is unavailable for your platform, you'll need a Rust compiler to build it from source.
- **Usage**: After installation, use the `--fast` flag for enhanced performance:

Development Installation
-------------------------

If you want to contribute to the development of jonq, you can install from source:

.. code-block:: bash

   git clone https://github.com/duriantaco/jonq.git
   cd jonq
   pip install -e .