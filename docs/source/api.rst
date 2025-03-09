API Reference
==============

This section provides detailed information about the jonq API.

Main Module (jonq.main)
------------------------

The main module provides the command-line interface for jonq.

**main()**

Main entry point for the jonq command-line tool. This function:

* Processes the command-line arguments
* Parses the SQL-like query
* Translates it to a jq filter
* Executes it against the specified JSON file

Command line usage:

.. code-block:: bash

    jonq <path/json_file> "<query>"

Where:

* ``<path/json_file>`` - Path to the JSON file to query
* ``<query>`` - SQL-like query in double quotes

Query Parser (jonq.query_parser)
---------------------------------

The Query Parser module provides functions to parse SQL-like queries into a structured format 
that can be translated into jq filters.

**tokenize(query)**

Tokenize a SQL-like query string into individual tokens.

Parameters:
    * **query** (*str*) - The SQL-like query string to tokenize

Returns:
    * **list** - A list of string tokens from the query

Example:

.. code-block:: python

    >>> tokenize("select name, age if age > 30")
    ['select', 'name', ',', 'age', 'if', 'age', '>', '30']

**parse_query(tokens)**

Parse tokenized query into structured field selections and clauses.

Parameters:
    * **tokens** (*list*) - List of string tokens from a tokenized query

Returns:
    * **tuple** - A tuple containing:
        * **fields** (*list*) - List of field specifications
          Each field is a tuple in one of these formats:
          
          * ``('field', field_name, alias)``
          * ``('aggregation', function_name, field_name, alias)``
          * ``('expression', expression_text, alias)``
          
        * **condition** (*str*) - Filter condition or None
        * **group_by** (*list*) - List of fields to group by or None
        * **order_by** (*str*) - Field to sort by or None
        * **sort_direction** (*str*) - Sort direction ('asc' or 'desc')
        * **limit** (*str*) - Maximum number of results or None

Raises:
    * **ValueError** - If the query syntax is invalid

Example:

.. code-block:: python

    >>> tokens = tokenize("select name, age if age > 30 sort age desc 5")
    >>> parse_query(tokens)
    ([('field', 'name', 'name'), ('field', 'age', 'age')], 
     '.age? > 30', None, 'age', 'desc', '5')

**parse_condition(tokens)**

Parse condition tokens into a jq-compatible filter expression.

Parameters:
    * **tokens** (*list*) - List of tokens representing the condition

Returns:
    * **str** - A jq-compatible filter expression or None if no condition

Raises:
    * **ValueError** - If the condition syntax is invalid

**parse_or_expression(tokens, pos)**

Parse tokens for OR expressions, which have the lowest precedence.

Parameters:
    * **tokens** (*list*) - List of tokens in the condition
    * **pos** (*int*) - Current position in the token list

Returns:
    * **tuple** - (AST node representing the OR expression, new position)

**parse_and_expression(tokens, pos)**

Parse tokens for AND expressions, which have higher precedence than OR.

Parameters:
    * **tokens** (*list*) - List of tokens in the condition
    * **pos** (*int*) - Current position in the token list

Returns:
    * **tuple** - (AST node representing the AND expression, new position)

**parse_comparison(tokens, pos)**

Parse tokens for comparison expressions or parenthesized expressions.

Parameters:
    * **tokens** (*list*) - List of tokens in the condition
    * **pos** (*int*) - Current position in the token list

Returns:
    * **tuple** - (AST node, new position)

Raises:
    * **ValueError** - If the syntax is invalid

**transform_ast(ast)**

Transform an abstract syntax tree (AST) into a jq-compatible expression.

Parameters:
    * **ast** - The AST node to transform

Returns:
    * **str** - A jq-compatible filter expression

Raises:
    * **ValueError** - If the AST node is invalid

**transform_field(token)**

Transform a field token into a jq path expression.

Parameters:
    * **token** (*str*) - The field token to transform

Returns:
    * **str** - A jq path expression with nullable access

Raises:
    * **ValueError** - If the field name is invalid

**transform_value(token)**

Transform a value token into a jq-compatible value.

Parameters:
    * **token** (*str*) - The value token to transform

Returns:
    * **str** - A jq-compatible value string

Raises:
    * **ValueError** - If the value is invalid

**transform_operator(op)**

Transform an operator token into a jq-compatible operator.

Parameters:
    * **op** (*str*) - The operator token to transform

Returns:
    * **str** - A jq-compatible operator

**find_lowest_precedence_operator(tokens)**

Find the operator with the lowest precedence in a list of tokens.

Parameters:
    * **tokens** (*list*) - List of tokens to search

Returns:
    * **int** - Index of the lowest precedence operator, or -1 if none found

**is_balanced(tokens)**

Check if parentheses in tokens are balanced.

Parameters:
    * **tokens** (*list*) - List of tokens to check

Returns:
    * **bool** - True if parentheses are balanced, False otherwise

**parse_query_compat(tokens)**

Compatibility wrapper for parse_query that returns a subset of results.

Parameters:
    * **tokens** (*list*) - List of tokens to parse

Returns:
    * **tuple** - (fields, condition, order_by, sort_direction, limit)

JQ Filter (jonq.jq_filter)
---------------------------

The JQ Filter module converts parsed query data into jq filter strings.

**format_field_path(field)**

Format a field path with proper nullable access for jq.

Parameters:
    * **field** (*str*) - The field path to format

Returns:
    * **str** - Formatted field path with proper nullable access

Examples:

.. code-block:: python

    >>> format_field_path('name')
    'name?'
    >>> format_field_path('profile.address.city')
    'profile?.address?.city?'
    >>> format_field_path('orders[0].item')
    'orders[0]?.item?'
    >>> format_field_path('first name')
    '"first name"?'

**build_jq_path(field_path)**

Build a jq path expression from a field path.

Parameters:
    * **field_path** (*str*) - The field path to convert

Returns:
    * **str** - jq path expression

Examples:

.. code-block:: python

    >>> build_jq_path('name')
    '.name?'
    >>> build_jq_path('profile.age')
    '.profile?.age?'

**translate_expression(expression)**

Translate a jonq expression to a jq expression.

Parameters:
    * **expression** (*str*) - jonq expression string

Returns:
    * **str** - Translated jq expression

Raises:
    * **ValueError** - If the function is unsupported

**escape_string(s)**

Escape a string for use in a jq filter.

Parameters:
    * **s** (*str*) - The string to escape

Returns:
    * **str** - The escaped string

**generate_jq_filter(fields, condition, group_by, order_by, sort_direction, limit)**

Generate a jq filter from the parsed query components.

Parameters:
    * **fields** (*list*) - List of field specifications
    * **condition** (*str*) - Filter condition or None
    * **group_by** (*list*) - List of fields to group by or None
    * **order_by** (*str*) - Field to sort by or None
    * **sort_direction** (*str*) - Sort direction ('asc' or 'desc')
    * **limit** (*str*) - Maximum number of results or None

Returns:
    * **str** - A jq filter string

Raises:
    * **ValueError** - If the expression is invalid

Example:

.. code-block:: python

    >>> generate_jq_filter(
    ...     [('field', 'name', 'name'), ('field', 'age', 'age')],
    ...     '.age? > 30', None, 'age', 'desc', '5'
    ... )
    'if type == "array" then . | map(select(.age? > 30) | { "name": (.name? // null), "age": (.age? // null) }) elif type == "object" then [select(.age? > 30) | { "name": (.name? // null), "age": (.age? // null) }] elif type == "number" then if .age? > 30 then [{"value": .}] else [] end elif type == "string" then if .age? > 30 then [{"value": .}] else [] end else [] end | sort_by(.age) | reverse | .[0:5]'

Executor (jonq.executor)
-------------------------

The Executor module handles the execution of jq filters against JSON files.

**run_jq(json_file, jq_filter)**

Run a jq filter against a JSON file.

Parameters:
    * **json_file** (*str*) - Path to the JSON file
    * **jq_filter** (*str*) - jq filter string to execute

Returns:
    * **tuple** - (stdout, stderr) from the jq command

Raises:
    * **ValueError** - If the JSON file or jq filter is invalid
    * **RuntimeError** - If jq execution fails

Query Syntax
-------------

jonq uses a SQL-like syntax for querying JSON data:

.. code-block:: sql

    select <fields> [if <condition>] [group by <fields>] [sort <field> [asc|desc] [limit]]

Where:

* ``<fields>`` - Comma-separated list of fields to select or aggregations
* ``if <condition>`` - Optional filtering condition
* ``group by <fields>`` - Optional grouping by one or more fields
* ``sort <field>`` - Optional field to sort by
* ``asc|desc`` - Optional sort direction (default: asc)
* ``limit`` - Optional integer to limit the number of results

Field Selection:

* Simple fields: ``select name, age``
* All fields: ``select *``
* Nested fields: ``select profile.address.city``
* Array access: ``select orders[0].item``
* Fields with spaces: ``select 'first name'``
* Aggregations: ``select sum(price) as total``
* Expressions: ``select price * 0.7 as discounted_price``
* Aliases: ``select name as customer_name``

Filtering:

* Simple comparison: ``if age > 30``
* String comparison: ``if city = 'New York'``
* Combined with AND: ``if age > 25 and city = 'Chicago'``
* Combined with OR: ``if age > 30 or city = 'Los Angeles'``
* Nested conditions: ``if (age > 30 and city = 'Chicago') or (age < 25 and city = 'New York')``

Grouping:

* Simple grouping: ``group by city``
* With aggregation: ``select city, count(*) as count group by city``
* Multiple fields: ``group by city, country``

Sorting:

* Ascending (default): ``sort age``
* Descending: ``sort age desc``
* With limit: ``sort age desc 5``