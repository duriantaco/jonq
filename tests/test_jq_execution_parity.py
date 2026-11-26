import asyncio
import csv
import io
import json
import subprocess
import sys

import pytest

from jonq import execute, query, query_async, run_jq, run_jq_async


def test_select_all_matches_in_memory_file_and_stream(tmp_path):
    source = [1, False, None, {"key": "value"}, [2, "three"]] * 205
    path = tmp_path / "source.json"
    path.write_text(json.dumps(source), encoding="utf-8")

    assert query(source, "select *") == source
    assert query(path, "select *", streaming=True) == source
    assert asyncio.run(query_async(source, "select *")) == source
    assert asyncio.run(query_async(path, "select *", streaming=True)) == source


def test_async_jq_reads_large_values_with_and_without_streaming(tmp_path):
    source = [{"text": "x" * 70_000}]
    path = tmp_path / "large.json"
    path.write_text(json.dumps(source), encoding="utf-8")

    assert asyncio.run(query_async(path, "select text")) == source
    assert asyncio.run(query_async(path, "select text", streaming=True)) == source


def test_raw_jq_returns_every_value_in_order_without_leaking_between_queries():
    expected = ('"first"\n"second"', ""), ('"third"', "")
    assert (
        run_jq(".[]", '["first","second"]'), run_jq(".[]", '["third"]')
    ) == expected

    async def run():
        return (
            await run_jq_async(".[]", '["first","second"]'),
            await run_jq_async(".[]", '["third"]'),
        )

    assert asyncio.run(run()) == expected


def test_raw_jq_checks_status_even_after_emitting_output():
    jq_filter = '., error("reject this row")'

    for stdout, stderr in (run_jq(jq_filter, "1"), asyncio.run(run_jq_async(jq_filter, "1"))):
        assert stdout == ""
        assert "reject this row" in stderr


def test_raw_jq_finishes_when_filter_emits_nothing():
    result = subprocess.run(
        [
            sys.executable, "-B", "-c",
            "import asyncio; from jonq import run_jq, run_jq_async; "
            "assert run_jq('empty', 'null') == ('', ''); "
            "assert asyncio.run(run_jq_async('empty', 'null')) == ('', '')",
        ],
        capture_output=True,
        timeout=3,
    )
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("limit", [0, 1])
def test_csv_limit_counts_records_with_embedded_newlines(limit):
    result = execute(
        [{"name": "top\nbottom"}, {"name": "next"}],
        "select name",
        format="csv",
        limit=limit,
    )

    rows = list(csv.reader(io.StringIO(result.text), strict=True))
    assert rows == [["name"], *([["top\nbottom"]] if limit else [])]
