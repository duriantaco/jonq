import re
import pytest
from jonq.jq_filter import generate_jq_filter


def _has(txt: str, parts: list[str]) -> None:
    for p in parts:
        assert p in txt


def test_select_all():
    assert generate_jq_filter([("field", "*", "*")], None, None, None, None, None) == "."


def test_select_two_fields():
    r = generate_jq_filter(
        [("field", "name", "name"), ("field", "age", "age")], None, None, None, None, None
    )
    _has(r, ['map({', '"name"', '"age"'])


def test_select_two_fields_with_condition():
    r = generate_jq_filter(
        [("field", "name", "name"), ("field", "age", "age")],
        ".age > 18",
        None,
        None,
        None,
        None,
    )
    _has(r, ["select(.age > 18)", '"name"', '"age"'])


def test_sum_aggregation():
    r = generate_jq_filter(
        [("aggregation", "sum", "items.price", "total_price")],
        None,
        None,
        None,
        None,
        None,
    )
    _has(r, ['"total_price"', "add"])


def test_sum_with_condition():
    r = generate_jq_filter(
        [("aggregation", "sum", "items.price", "total_price")],
        ".age > 18",
        None,
        None,
        None,
        None,
    )
    _has(r, ['"total_price"', "select(.age > 18)", "add"])


def test_mixed_field_and_count():
    r = generate_jq_filter(
        [("field", "name", "name"), ("aggregation", "count", "items", "item_count")],
        None,
        None,
        None,
        None,
        None,
    )
    _has(r, ['"name"', '"item_count"', "length"])


def test_simple_expression():
    r = generate_jq_filter([("expression", ".age + 10", "age_plus_10")], None, None, None, None, None)
    _has(r, ['"age_plus_10"', "+ 10"])


def test_sort_limit():
    r = generate_jq_filter([("field", "name", "name")], None, None, "name", "asc", 5)
    _has(r, ["sort_by(.name)", ".[0:5]"])


def test_field_with_space():
    r = generate_jq_filter([("field", "first name", "first_name")], None, None, None, None, None)
    _has(r, ['"first_name"', '"first name"'])


def test_expression_with_inner_sum():
    r = generate_jq_filter(
        [("expression", "sum(items.price) * 2", "double_total")], None, None, None, None, None
    )
    _has(r, ['"double_total"', "sum", "* 2"])


@pytest.mark.parametrize(
    "cond",
    [
        '(.age? > 25 and .city? == "New York")',
        '(.age? > 30 or .city? == "Los Angeles")',
        '((.age? > 30 and .city? == "Chicago") or (.age? < 30 and .city? == "Los Angeles"))',
    ],
)
def test_complex_conditions(cond):
    r = generate_jq_filter(
        [("field", "name", "name"), ("field", "age", "age")], cond, None, None, None, None
    )
    _has(r, ["select(", '"name"', '"age"'])


def test_group_by_count():
    r = generate_jq_filter(
        [("field", "city", "city"), ("aggregation", "count", "*", "count")],
        None,
        ["city"],
        None,
        None,
        None,
    )
    _has(r, ["group_by(.city)", '"count": length'])


def test_group_by_avg():
    r = generate_jq_filter(
        [("field", "city", "city"), ("aggregation", "avg", "age", "avg_age")],
        None,
        ["city"],
        None,
        None,
        None,
    )
    _has(r, ["group_by(.city)", '"avg_age"'])


def test_group_by_nested_field():
    r = generate_jq_filter(
        [("field", "profile.address.city", "city"), ("aggregation", "count", "*", "count")],
        None,
        ["profile.address.city"],
        None,
        None,
        None,
    )
    _has(r, ["group_by(.profile.address.city)", '"count": length'])


def test_arithmetic_subtraction():
    r = generate_jq_filter(
        [("expression", "max(orders.price) - min(orders.price)", "price_range")],
        None,
        None,
        None,
        None,
        None,
    )
    _has(r, ['"price_range"', "-", "max", "min"])


def test_arithmetic_addition():
    r = generate_jq_filter([("expression", ".age + 10", "age_plus_10")], None, None, None, None, None)
    _has(r, ['"age_plus_10"', "+ 10"])


def test_count_star():
    assert '{ "total_count": length }' == generate_jq_filter(
        [("aggregation", "count", "*", "total_count")], None, None, None, None, None
    )


def test_count_star_with_condition():
    r = generate_jq_filter(
        [("aggregation", "count", "*", "adult_count")], ".age? > 18", None, None, None, None
    )
    _has(r, ['"adult_count"', "length"])


def test_deep_nested_fields():
    r = generate_jq_filter(
        [
            ("field", "profile.address.city", "city"),
            ("field", "profile.address.zip", "zip"),
        ],
        None,
        None,
        None,
        None,
        None,
    )
    _has(r, ['"city"', '"zip"', ".profile?.address?.city?"])


def test_array_index_field():
    r = generate_jq_filter([("field", "orders[0].item", "first_item")], None, None, None, None, None)
    _has(r, ['"first_item"', "orders[0]"])


def test_hyphen_and_quote_fields():
    r1 = generate_jq_filter([("field", "first-name", "first_name")], None, None, None, None, None)
    r2 = generate_jq_filter([("field", "user's name", "username")], None, None, None, None, None)
    _has(r1, ['"first_name"', '"first-name"'])
    _has(r2, ['"username"', '"user\'s name"'])


def test_nested_condition_and_group_by():
    r = generate_jq_filter(
        [
            ("field", "profile.address.city", "city"),
            ("aggregation", "count", "orders", "order_count"),
            ("aggregation", "avg", "orders.price", "avg_price"),
        ],
        None,
        ["profile.address.city"],
        None,
        None,
        None,
    )
    _has(
        r,
        [
            "group_by(.profile.address.city)",
            '"order_count"',
            '"avg_price"',
            "orders",
            "price",
        ],
    )

def test_order_by_multiple():
    r = generate_jq_filter(
        [("field", "name", "name"), ("field", "age", "age")], None, None, "age", "desc", 3
    )
    _has(r, ["sort_by(.age)", "reverse", ".[0:3]"])
