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

Development Installation
-------------------------

If you want to contribute to the development of jonq, you can install from source:

.. code-block:: bash

   git clone https://github.com/duriantaco/jonq.git
   cd jonq
   pip install -e .