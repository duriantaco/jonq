import asyncio

import pytest

from jonq import CompiledQuery, QueryResult, compile_query, execute, query, query_async


def test_compile_query_returns_structured_result():
    compiled = compile_query("select name if age > 25")

    assert isinstance(compiled, CompiledQuery)
    assert compiled.query == "select name if age > 25"
    assert compiled.sort_direction == "asc"
    assert "select(.age" in compiled.jq_filter


def test_query_accepts_python_objects():
    data = [
        {"name": "Alice", "age": 30},
        {"name": "Bob", "age": 20},
    ]

    result = query(data, "select name if age > 25")

    assert result == [{"name": "Alice"}]


def test_execute_returns_csv_result_object():
    result = execute(
        [{"name": "Alice", "age": 30}],
        "select name, age",
        format="csv",
    )

    assert isinstance(result, QueryResult)
    assert result.output_format == "csv"
    header, row = result.text.strip().splitlines()
    assert set(header.split(",")) == {"name", "age"}
    assert "Alice" in row
    assert "30" in row
    assert result.data is None


def test_query_async_supports_compiled_queries():
    compiled = compile_query("select name")

    result = asyncio.run(query_async([{"name": "Alice"}], compiled))

    assert result == [{"name": "Alice"}]


def test_streaming_requires_file_path():
    with pytest.raises(ValueError, match="filesystem path"):
        query([{"name": "Alice"}], "select name", streaming=True)
