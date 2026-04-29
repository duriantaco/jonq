import json
import os
import tempfile

import pytest

from jonq.api import compile_query, execute, query


def test_count_star_respects_filter():
    data = [{"age": 10}, {"age": 30}, {"age": 40}]

    result = query(data, "select count(*) as over_25 if age > 25")

    assert result == {"over_25": 2}


def test_group_by_respects_filter_before_grouping():
    data = [
        {"city": "New York", "age": 30},
        {"city": "New York", "age": 20},
        {"city": "Chicago", "age": 35},
    ]

    result = query(data, "select city, count(*) as count if age > 25 group by city")

    assert result == [
        {"city": "Chicago", "count": 1},
        {"city": "New York", "count": 1},
    ]


def test_where_alias_matches_if_filter():
    data = [{"name": "Alice", "age": 30}, {"name": "Bob", "age": 20}]

    assert query(data, "select name where age > 25") == [{"name": "Alice"}]


def test_count_star_respects_from_path():
    data = {"products": [{"name": "A"}, {"name": "B"}]}

    result = query(data, "select count(*) as n from products")

    assert result == {"n": 2}


def test_select_requires_field_list():
    with pytest.raises(ValueError, match="Expected field"):
        compile_query("select")


def test_select_rejects_trailing_tokens():
    with pytest.raises(ValueError, match="Unexpected token"):
        compile_query("select name limit 1 junk")


def test_from_requires_path_before_limit():
    with pytest.raises(ValueError, match="Expected path after 'from'"):
        compile_query("select name from limit 1")


def test_arithmetic_precedence_matches_standard_math():
    result = query([{"age": 10}], "select age * 2 + 3 as total")

    assert result == [{"total": 23}]


def test_inline_shared_array_fields_stay_aligned():
    data = {"products": [{"id": 1, "name": "A"}, {"id": 2, "name": "B"}]}

    result = query(data, "select products[].id, products[].name")

    assert result == [{"id": 1, "name": "A"}, {"id": 2, "name": "B"}]


def test_json_string_with_slash_is_not_treated_as_path():
    payload = json.dumps([{"url": "https://example.com", "name": "A"}])

    result = query(payload, "select name")

    assert result == [{"name": "A"}]


def test_api_streaming_rejects_global_queries():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump([{"id": i} for i in range(1005)], f)
        path = f.name

    try:
        with pytest.raises(ValueError, match="Streaming mode does not support"):
            query(path, "select count(*) as n", streaming=True, validate=False)
    finally:
        os.unlink(path)


def test_api_streaming_keeps_simple_select_shape():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump([{"id": i} for i in range(3)], f)
        path = f.name

    try:
        result = query(path, "select id", streaming=True, validate=False)
        assert result == [{"id": 0}, {"id": 1}, {"id": 2}]
    finally:
        os.unlink(path)


def test_jsonl_output_format():
    result = execute([{"name": "A"}, {"name": "B"}], "select name", format="jsonl")

    assert result.output_format == "jsonl"
    assert result.text == '{"name":"A"}\n{"name":"B"}'
    assert result.data is None
