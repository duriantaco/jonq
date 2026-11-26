Cookbook
========

These recipes focus on the workflows jonq is meant to make fast: inspect unknown JSON, find the fields you need, and turn the result into a useful terminal-friendly shape.

jonq is still a jq-powered exploration and extraction tool. If the task becomes joins, window functions, repeated analytical queries, or long-running pipelines with connectors, use a database or ETL system instead.

Inspect Unknown JSON First
--------------------------

Inspect a saved API response to find the fields and the array that holds
the rows. This sample includes metadata alongside the ``users`` array.

.. code-block:: bash

   cat > response.json <<'JSON'
   {
     "meta": {"total": 2},
     "users": [{"name": "Asha", "age": 29}, {"name": "Jules", "age": 35}]
   }
   JSON
   jonq response.json

The inspector shows ``users[].name`` and suggests a query using
``from users``. Use that clause to select the array, then filter and
export the rows you need.

.. code-block:: bash

   jonq response.json "select age, name from users where age > 30" -t
   jonq response.json "select age, name from users where age > 30" --format csv --out older-users.csv

The CSV contains one row.

.. code-block:: text

   age,name
   35,Jules

Pipe JSON into ``jonq`` to inspect a response without saving it. NDJSON
files can be inspected the same way as ordinary JSON files.

.. code-block:: bash

   cat response.json | jonq
   jonq response.json "select * from users" --format jsonl --out users.ndjson
   jonq users.ndjson
   cat users.ndjson | jonq --ndjson "select name"

Turn API JSON Into a Table
--------------------------

Many APIs return arrays of objects. jonq is useful when you want a few readable columns instead of a large JSON blob.

.. code-block:: bash

   curl -s https://api.github.com/users/octocat/repos \
     | jonq "select name, stargazers_count as stars, pushed_at sort stargazers_count desc limit 10" -t

When you need the generated jq filter, add ``--explain``:

.. code-block:: bash

   curl -s https://api.github.com/users/octocat/repos \
     | jonq "select name, stargazers_count as stars limit 5" --explain

Flatten Nested Arrays
---------------------

Use ``from`` when the rows you care about live inside nested arrays.

.. code-block:: json

   [
     {
       "name": "Alice",
       "orders": [
         {"order_id": 101, "item": "Laptop", "price": 1200},
         {"order_id": 102, "item": "Phone", "price": 800}
       ]
     },
     {
       "name": "Bob",
       "orders": [
         {"order_id": 103, "item": "Tablet", "price": 500}
       ]
     }
   ]

.. code-block:: bash

   jonq users.json "select order_id, item, price from [].orders if price > 700" -t

This treats each order as a row and then filters by ``price``.

Export JSON to CSV or JSONL
---------------------------

Use CSV when the next step is a spreadsheet or a tabular tool:

.. code-block:: bash

   jonq users.json "select id, name, city" --format csv > users.csv

Use JSONL when the next step expects one JSON object per line:

.. code-block:: bash

   jonq users.json "select id, name, city" --format jsonl > users.jsonl

Use raw output for shell loops and simple command substitution:

.. code-block:: bash

   jonq users.json "select name" -r

Follow NDJSON Logs
------------------

For newline-delimited JSON logs, combine ``tail -f`` with ``--follow``:

.. code-block:: bash

   tail -f app.ndjson \
     | jonq --follow "select timestamp, level, message if level = 'error'" -t

This is for line-by-line log inspection. Use non-follow mode when you need global operations such as grouping, sorting, distinct, or aggregation.

.. _triage-network-logs:

Triage Network Logs
-------------------

``jonq triage`` uses Python's standard library to analyze existing NDJSON
exports. It counts recorded alerts by signature and highlights repeated
firewall denials by source IP. Each nonblank input line must be a UTF-8
JSON object with an ``event_type`` string.

From the jonq repository root, try the synthetic EVE fixture. It is ready
to read offline and contains five flow records and three alert records.
On a real EVE export, Suricata supplies the alert records and jonq
summarizes them. See the `Suricata EVE format guide <https://docs.suricata.io/en/suricata-8.0.7/output/eve/eve-json-format.html#event-type-alert>`_.

.. code-block:: bash

   eve=tests/json_test_files/suricata_eve.ndjson
   jonq triage "$eve"
   jonq triage "$eve" --format json > alert-summary.json

The summary starts with three recorded alert events across two alert types.
It counts two events for signature ``900001`` and one for ``900002``.
The terminal shows the first matching input line and its timestamp when
available for each signature. With a named file on macOS or Linux, it also
shows a shell command to open the first cited line. The JSON report keeps
up to two examples per signature in input order. Missing or invalid
timestamps appear as ``null``. Each ``line`` value is a one-based line
number in the original input, including blank lines in the count.

Open line 6 to verify the first example for signature ``900001``. Export
one example per signature to share the counts and source references.

.. code-block:: bash

   sed -n '6p' < "$eve"
   jonq alert-summary.json \
     "select signature_id, signature, count, examples[0].line as example_line, examples[0].timestamp as example_timestamp from alerts" \
     --format csv > alert-evidence.csv

To reproduce the recorded IoT-23 example, download the published
Suricata EVE log and inspect the first cited IRC alert.

.. code-block:: bash

   curl -fsSLo eve.ndjson 'https://mcfp.felk.cvut.cz/publicDatasets/IoT-23-Dataset/IndividualScenarios/CTU-IoT-Malware-Capture-34-1/suricata/eve.json'
   jonq triage eve.ndjson
   sed -n '8p' eve.ndjson | jonq 'select timestamp, alert.signature_id, alert.signature' -t

Line 8 reports signature ``2002028``, ``ET CHAT IRC PONG response``.

``jonq triage`` and ``jonq connections`` color their text reports when
stdout is a terminal. Use ``--no-color`` or set ``NO_COLOR=1`` for plain
text in a terminal.

For firewall exports, use records with ``event_type`` set to ``firewall``
and a top-level ``action`` field. Denials must also include a valid
``src_ip``. The command counts ``block``, ``deny``, ``drop``, ``reject``,
and their past-tense forms. The example reads from stdin and reports
``192.0.2.10`` with two denials.

.. code-block:: bash

   jonq triage - --min-denials 2 <<'NDJSON'
   {"event_type":"firewall","src_ip":"192.0.2.10","action":"deny"}
   {"event_type":"firewall","src_ip":"192.0.2.10","action":"drop"}
   {"event_type":"firewall","src_ip":"192.0.2.11","action":"allow"}
   NDJSON

The default threshold is five denials per source across the supplied
records. Use one bounded export for the period you want to review. Treat
both signature and denial counts as signals to inspect the relevant events.
The command reports malformed records by line number on stderr, summarizes
the valid records, and exits with status ``1`` if any records were malformed.

Review Connection Activity
--------------------------

``jonq connections`` uses Python's standard library to summarize a bounded
export of observed traffic. Zeek ``conn.log`` records in JSON mode use
numeric Unix epoch seconds in ``ts`` and the literal keys ``id.orig_h`` and
``id.resp_h``. Suricata EVE contributes ``flow`` events with ``src_ip`` and
``dest_ip``. The command uses ``flow.start`` when present and ``timestamp``
otherwise, with a timezone on either timestamp.
See the `Zeek connection log guide <https://docs.zeek.org/en/current/reference/logs/conn.html>`_
and the `Suricata EVE flow format <https://docs.suricata.io/en/suricata-8.0.7/output/eve/eve-json-format.html#event-type-flow>`_.

Run this example from the jonq repository root. It highlights ``192.0.2.10``
because the log shows three distinct destination IPs for it in one 60-second
window.

.. code-block:: bash

   jonq connections tests/json_test_files/zeek_conn.ndjson \
     --min-destinations 3 --src-cidr 192.0.2.0/24

The terminal report opens with each qualifying source's peak distinct
destination count, UTC window bounds, and destination IPs in that window.
Repeated records for one destination count once toward the peak. Each
finding groups recorded outcomes by protocol and destination port and
points to an original input line to inspect. The report then groups
records by IP pair and shows a count for each direction.

For Zeek TCP records, jonq uses ``S0`` for no reply observed, ``REJ`` for
rejected, and ``S1``, ``S2``, ``S3``, ``SF``, or ``RSTO`` for established.
For EVE TCP, it uses explicit
flow state and the packet count toward the client. When the recorded fields
leave the outcome unclear, jonq shows ``outcome unavailable``. See the
`Zeek connection state reference <https://docs.zeek.org/en/lts/scripts/base/protocols/conn/main.zeek.html#type-Conn::Info>`_
and the `Suricata EVE flow fields <https://docs.suricata.io/en/suricata-8.0.7/output/eve/eve-json-format.html#event-type-flow>`_.

Set ``--window SECONDS`` to change the 60-second window and
``--min-destinations N`` to change the threshold of 10, with a minimum of
two. A source qualifies when its peak reaches the threshold, and records
exactly one window apart count together. Repeat ``--src-cidr`` or
``--dst-cidr`` to match any of the supplied IPv4 or IPv6 hosts or networks
on that side. Filters use the original source and destination before
either summary. The command keeps selected connection metadata in memory
so it can order records by timestamp after reading the input. Use one
export per capture when logs contain overlapping observations. Use ``-``
to read stdin. The terminal previews up to eight IPs per destination list,
three protocol and port groups per finding, and twelve conversation rows.
Use ``--format json`` for the full report. Its ``evidence`` is keyed by
source IP and includes every record and service group in the selected peak
window.
Malformed records produce line diagnostics on stderr and exit status ``1``
while valid records still contribute to the report.

.. _review-horizontal-scan-leads:

Review Horizontal Scan Leads
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Use ``--scan-leads`` on captured logs to review horizontal patterns. It
groups TCP records with an observed rejection or no reply by source IP
and destination port. For each source and port, it reports the window
with the most distinct destination IPs if that count reaches the threshold.
Established connections and records with unavailable outcomes stay outside
this calculation. Attempts exactly one window apart count together.

The same ``--window``, ``--min-destinations``, ``--src-cidr``, and
``--dst-cidr`` options apply. Each run accepts at most one of
``--scan-leads`` and ``--baseline``.

.. code-block:: bash

   jonq connections tests/json_test_files/zeek_conn.ndjson \
     --min-destinations 2 --scan-leads --src-cidr 192.0.2.0/24

The fixture shows an attempt to each of two addresses on TCP port 443
within 60 seconds. Zeek recorded no reply from ``198.51.100.11`` or
``198.51.100.12``. The report cites line 1 and shows a shell command to open
it on macOS and Linux. The two matching records are on lines 1 and 3.
Use ``--format json`` for all cited records. Run the regular ``connections``
report to review overall breadth and established traffic in the same capture.

Check whether the source host was scheduled to contact the listed
addresses and TCP port during the window. This synthetic health-check
fixture meets the threshold because the source retries across 12 addresses.

.. code-block:: bash

   jonq connections tests/json_test_files/benign_health_check_retries.ndjson \
     --scan-leads --src-cidr 192.0.2.40

The window contains 13 eligible records on TCP port 443 and 12 different
destination IPs. Repeated records for an IP count once toward the
threshold. When no lead appears, distinguish an empty IP scope, a scope
with no eligible TCP records, and eligible records whose windows all
fall below the threshold. See :doc:`contribution` for the accuracy replay.

Export the same lead's evidence rows to CSV. The ``line`` column points
to the input NDJSON.

.. code-block:: bash

   jonq connections tests/json_test_files/zeek_conn.ndjson \
     --min-destinations 2 --scan-leads --format json > scan-leads.json
   jonq scan-leads.json "select line, dest_ip, details.state from scan_leads[].records[]" \
     --format csv > scan-evidence.csv

Compare With a Baseline
~~~~~~~~~~~~~~~~~~~~~~~

Use a comparable earlier export to put current findings in context.

.. code-block:: bash

   jonq connections tests/json_test_files/zeek_conn.ndjson \
     --baseline tests/json_test_files/zeek_conn_baseline.ndjson \
     --min-destinations 3 --src-cidr 192.0.2.0/24

.. code-block:: text

   Review 192.0.2.10 · 3 distinct destinations
     2023-11-14 22:13:40.750000 UTC to 2023-11-14 22:14:40.750000 UTC
     Baseline peak 2 (+1).
     Input line 1 · 198.51.100.12 · TCP/443 · no reply observed (Zeek S0)
     TCP/443 · 4 records · 2 no reply observed, 2 established
     Destinations 198.51.100.10, 198.51.100.11, 198.51.100.12
     Absent from baseline 198.51.100.12

Open line 1 of the current log to see the record for ``198.51.100.12``.

.. code-block:: bash

   sed -n '1p' tests/json_test_files/zeek_conn.ndjson

The record shows ``proto`` set to ``tcp``, ``id.resp_p`` set to ``443``, and
``conn_state`` set to ``S0``. Zeek observed an attempt with no reply at that
time. Use the recorded protocol, port, and outcome to check what the source
host was expected to contact during the displayed interval.

The command applies the same IP filters and window duration to both
exports. It compares sources that meet the current threshold, including
when their baseline peak was below it. It checks each destination in the
displayed current peak against all baseline records for that source. Outcome
counts describe the current window. The baseline compares peak counts and
destination IPs.

With a complete baseline, the report shows ``Review`` when the peak rises,
a current peak destination is absent, or the source has no baseline records.
``Within reference for breadth and peers`` means the peak is at or below the
baseline and the baseline contains every destination in the displayed peak
for that source.

The report distinguishes zero current connections in scope from connections
that stay below the threshold. If either export is partial or the baseline
has zero in-scope connections, any current threshold findings from valid
records remain visible and the comparison is unavailable. Malformed
records in either export produce line diagnostics and exit status ``1``.

Recover From Field Typos
------------------------

If you mistype a field, jonq validates the query against the payload and prints a copy-pasteable repair suggestion:

.. code-block:: bash

   jonq users.json "select nme"

.. code-block:: text

   Error: Unknown field(s): nme
   Did you mean: nme -> name?
   Available fields: id, name, age, city
   Try: jonq users.json "select name"

This is most useful while exploring unfamiliar payloads where field names are long, nested, or easy to mistype.

Know When to Drop to jq
-----------------------

Use raw jq when you need full jq language control, complex reductions, custom recursive transforms, or jq modules.

Use jonq when the task is common enough to read like:

.. code-block:: text

   select these fields
   from this nested array
   where this condition is true
   sort and limit the rows
   print as table, CSV, JSONL, YAML, JSON, or raw values

That boundary keeps jonq useful without turning it into a second full query language.
