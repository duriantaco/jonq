import json

import pytest

from jonq import compile_query, query


def test_project_and_filter_boolean_literals(tmp_path):
    source = tmp_path / "input.json"
    source.write_text(json.dumps([{"id": 1, "active": False}, {"id": 2, "active": True}]))

    assert query(source, "select id, active where active = false") == [{"id": 1, "active": False}]
    assert query(source, "select id where active = true") == [{"id": 2}]
    assert query(source, "select active") == [{"active": False}, {"active": True}]


def test_null_fallbacks_preserve_false():
    assert query(
        [{"active": False}, {"active": None}, {}],
        "select coalesce(active, true) as coalesced, if_null(active, true) as replaced",
    ) == [
        {"coalesced": False, "replaced": False},
        {"coalesced": True, "replaced": True},
        {"coalesced": True, "replaced": True},
    ]


def test_quoted_dotted_path_selects_literal_key(tmp_path):
    source = tmp_path / "input.json"
    source.write_text(json.dumps([{"id.orig_h": "192.0.2.1", "id": {"orig_h": "192.0.2.2"}}]))

    assert query(source, 'select "id.orig_h" as source, id.orig_h as nested') == [
        {"source": "192.0.2.1", "nested": "192.0.2.2"}
    ]


def test_quoted_path_segments_work_in_sources_and_predicates():
    row = {"arr.key": [{"is-active": True, "x[0]": "kept"}, {"is-active": False, "x[0]": "ignored"}]}

    assert query(
        [row], 'select "x[0]" as value from []."arr.key" where "is-active" = true'
    ) == [{"value": "kept"}]


def test_filtered_nested_projection_keeps_rows_aligned(tmp_path):
    source = tmp_path / "input.json"
    source.write_text(json.dumps({"orders": [{"id": "A", "total": 50}, {"id": "B", "total": 200}]}))

    assert query(
        source, "select orders[].id, orders[].total where orders[].total > 100"
    ) == [{"id": "B", "total": 200}]


def test_nested_projection_can_filter_on_outer_and_inner_values():
    row = {"active": True, "orders": [{"id": "A", "total": 50}, {"id": "B", "total": 200}]}
    expression = "select orders[].id where active = true and orders[].total > 100"

    assert query(row, expression) == [{"id": "B"}]
    assert query({**row, "active": False}, expression) == []


@pytest.mark.parametrize("root_array", [False, True])
def test_implicit_parent_and_child_projection_requires_an_explicit_row_source(root_array):
    record = {"owner": "A", "items": [{"price": 10}, {"price": 30}]}
    data = [record] if root_array else record

    with pytest.raises(ValueError, match=r"[Ff][Rr][Oo][Mm] .*items"):
        query(data, "select owner, items[].price where items[].price > 20")


def test_explicit_parent_scope_can_expand_one_child_column():
    data = [{"owner": "A", "items": [{"price": 10}, {"price": 30}]}]

    assert query(data, "select owner, items[].price from [] where owner = 'A'") == [
        {"owner": "A", "price": 10}, {"owner": "A", "price": 30},
    ]
    with pytest.raises(ValueError, match=r"[Ff][Rr][Oo][Mm] \[\]\.items"):
        query(data, "select owner, items[].price from [] where items[].price > 20")


@pytest.mark.parametrize("source", ["", " from []"])
def test_independent_array_projections_require_one_row_source(source):
    clause = f"select orders[].id as order_id, refunds[].id as refund_id{source}"

    with pytest.raises(ValueError, match=r"one row source"):
        compile_query(clause)


def test_equivalent_quoted_array_paths_share_typed_scope():
    data = {"items": [{"id": "A", "price": 10}, {"id": "B", "price": 30}]}

    assert query(data, 'select items[].id, "items"[].price where "items"[].price > 20') == [
        {"id": "B", "price": 30},
    ]


@pytest.mark.parametrize("query_text", [
    "select items[].id, items[].price where items[].price > -3.5e2",
    "select items[].id, items[].price from [] where items[].price > -3.5e2",
    "select id, price from [].items where price > -3.5e2",
])
def test_filtered_nested_projection_keeps_rows_aligned_across_array_parents(tmp_path, query_text):
    source = tmp_path / "input.json"
    source.write_text(json.dumps([
        {"items": [{"id": "A", "price": 10}, {"id": "missing"}, {"id": "C", "price": -350}]},
        {"items": None},
        {},
        {"items": [{"id": "D", "price": 55}, {"id": "E", "price": -500}]},
    ]))

    assert query(source, query_text) == [{"id": "A", "price": 10}, {"id": "D", "price": 55}]


def test_explicit_from_skips_missing_null_or_wrong_shape_arrays(tmp_path):
    source = tmp_path / "input.json"
    source.write_text(json.dumps([
        {"orders": [{"id": 1}]}, {"orders": None}, {}, {"orders": {"id": 2}},
        {"orders": [{"id": 3}]},
    ]))

    assert query(source, "select id from [].orders") == [{"id": 1}, {"id": 3}]


def test_expression_only_projection_applies_filter_sort_and_limit():
    assert query(
        [{"age": 10}, {"age": 42}, {"age": 30}],
        "select age * 2 as score where age > 25 sort score desc limit 1",
    ) == [{"score": 84}]


def test_aggregate_calculation_uses_filtered_rows():
    data = [{"age": 10}, {"age": 20}, {"age": 42}, {"age": "unknown"}]
    assert query(data, "select max(age) - min(age) as age_range") == {"age_range": 32}
    assert query(
        data, "select max(age) - min(age) as age_range, count(*) as total where age > 10"
    ) == {"age_range": 22, "total": 2}


def test_aggregate_calculation_respects_from_and_handles_no_numeric_values():
    data = {"orders": [{"price": None}, {"price": 12}, {"price": 18}]}
    assert query(data, "select max(price) - min(price) as spread from orders") == {"spread": 6}
    assert query(
        data, "select max(price) - min(price) as spread from orders where price > 30"
    ) == {"spread": None}


def test_aggregate_calculation_can_share_a_nested_path_with_a_direct_aggregate():
    data = {"orders": [{"price": 12}, {"price": 18}]}
    assert query(
        data, "select max(orders[].price) - min(orders[].price) as spread, sum(orders[].price) as total"
    ) == {"spread": 6, "total": 30}


def test_count_collection_with_projected_fields_is_per_record():
    data = [{"name": "Alice", "orders": [1, 2]}, {"name": "Bob", "orders": [3]}, {"name": "Eve"}]
    assert query(data, "select name, count(orders) as order_count") == [
        {"name": "Alice", "order_count": 2},
        {"name": "Bob", "order_count": 1},
        {"name": "Eve", "order_count": 0},
    ]


def test_nested_array_aggregates_with_row_fields_use_each_rows_values():
    data = [
        {"name": "Alice", "orders": [{"price": 10}, {"price": 90}]},
        {"name": "Bob", "orders": [{"price": 30}]},
    ]
    assert query(
        data, "select name, min(orders[].price) as low, max(orders[].price) as high, avg(orders[].price) as average"
    ) == [
        {"name": "Alice", "low": 10, "high": 90, "average": 50},
        {"name": "Bob", "low": 30, "high": 30, "average": 30},
    ]


def test_having_can_compare_an_arithmetic_expression_of_selected_aliases():
    data = [{"city": "A", "age": 10}, {"city": "A", "age": 32}, {"city": "B", "age": 50}]
    assert query(
        data, "select city, max(age) as high, min(age) as low group by city having high - low > 5"
    ) == [{"city": "A", "high": 32, "low": 10}]


def test_sort_can_use_an_unselected_source_field():
    assert query(
        [{"id": "A", "age": 30}, {"id": "B", "age": 10}, {"id": "C", "age": 20}],
        "select id sort age limit 2",
    ) == [{"id": "B"}, {"id": "C"}]


@pytest.mark.parametrize(("comparison", "expected"), [("age < 30", 1), ("age > 30", 2)])
def test_numeric_ordering_excludes_missing_null_and_string_values(comparison, expected):
    rows = [{"id": 1, "age": 17}, {"id": 2, "age": 42}, {"id": 3},
            {"id": 4, "age": None}, {"id": 5, "age": "unknown"}]
    assert query(rows, f"select id where {comparison}") == [{"id": expected}]


@pytest.mark.parametrize("clause", ["where", "where age >", "sort", "group by age,"])
def test_incomplete_query_clauses_fail_during_compilation(clause):
    with pytest.raises(ValueError):
        compile_query(f"select age {clause}")


def test_adjacent_field_paths_require_a_comma():
    with pytest.raises(ValueError, match="comma"):
        compile_query("select name profile.age")


@pytest.mark.parametrize("condition", ["profile.age * 2 > 50", "count(orders) > 1"])
def test_where_rejects_unsupported_unquoted_calculations(condition):
    with pytest.raises(ValueError, match="field path or literal"):
        compile_query(f"select name where {condition}")
