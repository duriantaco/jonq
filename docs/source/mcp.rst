Local MCP Server
================

``jonq mcp`` serves two tools for reviewing saved network logs. An MCP
client starts Jonq as a local subprocess and exchanges messages over
standard input and output. The server uses the same analyzers as
``jonq triage`` and ``jonq connections``.

Connect a client
----------------

On macOS or Linux, install the checkout and get the absolute paths for
the bundled examples. Run this from the repository root with your
Python environment active.

.. code-block:: bash

   python -m pip install -e .
   command -v jonq
   printf '%s\n' "$PWD/tests/json_test_files"

Set the first path as the client command. Pass ``mcp``,
``--log-root``, and the second path as three separate arguments. To review
your own logs, set the last argument to a directory containing those
exports.

For VS Code, use the following in ``.vscode/mcp.json``. Replace the two
example paths with the values from your terminal. Start the server
using the controls in the configuration editor.

.. code-block:: json

   {
     "servers": {
       "jonq": {
         "type": "stdio",
         "command": "/absolute/path/to/venv/bin/jonq",
         "args": ["mcp", "--log-root", "/absolute/path/to/jonq/tests/json_test_files"]
       }
     }
   }

See the `VS Code guide to local MCP servers <https://code.visualstudio.com/docs/agent-customization/mcp-servers>`_
for the client controls. For another stdio MCP client, use the same
executable and arguments in its configuration. The server supports MCP
protocol revisions ``2025-11-25``, ``2025-06-18``, ``2025-03-26``, and
``2024-11-05``.

Call the tools
--------------

Each call needs a file path relative to ``--log-root``. Jonq opens
regular files read-only and rejects symbolic links in tool paths.

Call ``triage`` with an EVE alert log or normalized firewall records.
``min_denials`` defaults to five denials per source.

.. code-block:: json

   {"path": "suricata_eve.ndjson"}

The bundled file's alert summary cites lines 6 and 8. Use those line
numbers to open the matching records in the input file.

Call ``connections`` with a Zeek JSON connection export or Suricata EVE
flow log. The bundled example reports two distinct peers on TCP/443
and cites lines 1 and 3.

.. code-block:: json

   {
     "path": "zeek_conn.ndjson",
     "scan_leads": true,
     "window_seconds": 60,
     "min_destinations": 2
   }

``window_seconds`` defaults to 60 and ``min_destinations`` to 10.
Optional ``src_cidr`` and ``dst_cidr`` are arrays of IP addresses or
networks. ``baseline`` takes a relative path to a second log and can
be used when ``scan_leads`` is false.

Results include the same counts and evidence as the CLI JSON report.
When records are invalid, the tool returns the report for valid records
with line diagnostics and marks the result as an error. See
:ref:`triage-network-logs` and :ref:`review-horizontal-scan-leads` for
commands that open those evidence lines.
