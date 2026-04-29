Contributing
=============

Contributions to jonq are welcome! Here's how you can help.

Setting Up Development Environment
-----------------------------------

1. Fork the repository on GitHub
2. Clone your fork locally:

   .. code-block:: bash

      git clone https://github.com/duriantaco/jonq.git
      cd jonq

3. Create a virtual environment and install development dependencies:

   .. code-block:: bash

      python -m venv venv
      source venv/bin/activate  # On Windows: venv\Scripts\activate
      python -m pip install --upgrade pip
      pip install -e .
      pip install pytest pytest-asyncio

   To build the documentation locally, also install the docs requirements:

   .. code-block:: bash

      pip install -r docs/requirements.txt

Running Tests
--------------

jonq uses pytest for testing. To run tests:

.. code-block:: bash

   pytest

Run the full test suite before opening a pull request. If you change only
documentation, build the Sphinx docs as well.

Manual Testing
---------------

You can also use the shell scripts in the ``tests`` directory to run manual checks:

.. code-block:: bash

   bash tests/test_simple.sh
   bash tests/test_nested.sh

Contributing Code
------------------

1. Create a new branch for your feature or bugfix:

   .. code-block:: bash

      git switch -c feature-name

2. Make your changes and add tests for new features
3. Run the test suite to make sure everything passes
4. Commit your changes:

   .. code-block:: bash

      git commit -m "Description of your changes"

5. Push your branch to GitHub:

   .. code-block:: bash

      git push origin feature-name

6. Create a Pull Request from your fork

Coding Style
-------------

Please follow PEP 8 coding conventions and include docstrings for new functions and classes.

Adding Documentation
---------------------

If you're adding new features, please update the documentation as well. jonq uses Sphinx for documentation:

1. Update or add docstrings to your code
2. Update RST files in the ``docs`` directory if needed
3. Build the documentation to check your changes:

   .. code-block:: bash

      cd docs
      make html

   The documentation will be built in ``docs/build/html``.

Reporting Issues
-----------------

If you find a bug or have a suggestion for improvement, please create an issue on the GitHub repository.
