import pytest
from jonq.jq_filter import generate_jq_filter

def test_select_all_fields():
    assert generate_jq_filter([('field', '*', '*')], None, None, None, None, None) == '.'

def test_select_specific_fields_no_condition():
    assert generate_jq_filter(
        [('field', 'name', 'name'), ('field', 'age', 'age')],
        None, None, None, None, None
    ) == (
        'if type == "array" then . | map({ "name": (.name? // null), "age": (.age? // null) }) '
        'elif type == "object" then [{ "name": (.name? // null), "age": (.age? // null) }] '
        'elif type == "number" then [{"value": .}] '
        'elif type == "string" then [{"value": .}] '
        'else [] end'
    )

def test_select_specific_fields_with_condition():
    assert generate_jq_filter(
        [('field', 'name', 'name'), ('field', 'age', 'age')],
        '.age > 18', None, None, None, None
    ) == (
        'if type == "array" then . | map(select(.age > 18) | { "name": (.name? // null), "age": (.age? // null) }) '
        'elif type == "object" then [select(.age > 18) | { "name": (.name? // null), "age": (.age? // null) }] '
        'elif type == "number" then if .age > 18 then [{"value": .}] else [] end '
        'elif type == "string" then if .age > 18 then [{"value": .}] else [] end '
        'else [] end'
    )

def test_aggregation_sum():
    assert generate_jq_filter(
        [('aggregation', 'sum', 'items.price', 'total_price')],
        None, None, None, None, None
    ) == (
        '{ "total_price": ([.[] | .items?[] | .price?] | map(select(type == "number")) | add) }'
    )

def test_aggregation_with_condition():
    assert generate_jq_filter(
        [('aggregation', 'sum', 'items.price', 'total_price')],
        '.age > 18', None, None, None, None
    ) == (
        '{ "total_price": ([.[] | select(.age > 18) | .items?[] | .price?] | map(select(type == "number")) | add) }'
    )

def test_mixed_fields_and_aggregations():
    assert generate_jq_filter(
        [('field', 'name', 'name'), ('aggregation', 'count', 'items', 'item_count')],
        None, None, None, None, None
    ) == (
        'if type == "array" then . | map({ "name": (.name? // null), "item_count": (.items? | map(select(. != null)) | length) }) '
        'elif type == "object" then [{ "name": (.name? // null), "item_count": (.items? | map(select(. != null)) | length) }] '
        'elif type == "number" then [{"value": .}] '
        'elif type == "string" then [{"value": .}] '
        'else [] end'
    )

def test_expressions():
    assert generate_jq_filter(
        [('expression', '.age + 10', 'age_plus_10')],
        None, None, None, None, None
    ) == (
        'if type == "array" then . | map({ "age_plus_10": (.age + 10) }) '
        'elif type == "object" then [{ "age_plus_10": (.age + 10) }] '
        'elif type == "number" then [{"value": .}] '
        'elif type == "string" then [{"value": .}] '
        'else [] end'
    )

def test_sorting_and_limiting():
    assert generate_jq_filter(
        [('field', 'name', 'name')],
        None, None, 'name', 'asc', 5
    ) == (
        'if type == "array" then . | map({ "name": (.name? // null) }) '
        'elif type == "object" then [{ "name": (.name? // null) }] '
        'elif type == "number" then [{"value": .}] '
        'elif type == "string" then [{"value": .}] '
        'else [] end | sort_by(.name) | .[0:5]'
    )

def test_field_with_spaces():
    assert generate_jq_filter(
        [('field', 'first name', 'first_name')],
        None, None, None, None, None
    ) == (
        'if type == "array" then . | map({ "first_name": (."first name"? // null) }) '
        'elif type == "object" then [{ "first_name": (."first name"? // null) }] '
        'elif type == "number" then [{"value": .}] '
        'elif type == "string" then [{"value": .}] '
        'else [] end'
    )

def test_expression_with_aggregation():
    assert generate_jq_filter(
        [('expression', 'sum(items.price) * 2', 'double_total')],
        None, None, None, None, None
    ) == (
        'if type == "array" then . | map({ "double_total": ((.items? | map(.price?) | map(select(type == "number"))) | add * 2) }) '
        'elif type == "object" then [{ "double_total": ((.items? | map(.price?) | map(select(type == "number"))) | add * 2) }] '
        'elif type == "number" then [{"value": .}] '
        'elif type == "string" then [{"value": .}] '
        'else [] end'
    )

def test_complex_condition_with_and():
    assert generate_jq_filter(
        [('field', 'name', 'name'), ('field', 'age', 'age')],
        '(.age? > 25 and .city? == "New York")', None, None, None, None
    ) == (
        'if type == "array" then . | map(select((.age? > 25 and .city? == "New York")) | { "name": (.name? // null), "age": (.age? // null) }) '
        'elif type == "object" then [select((.age? > 25 and .city? == "New York")) | { "name": (.name? // null), "age": (.age? // null) }] '
        'elif type == "number" then if (.age? > 25 and .city? == "New York") then [{"value": .}] else [] end '
        'elif type == "string" then if (.age? > 25 and .city? == "New York") then [{"value": .}] else [] end '
        'else [] end'
    )

def test_complex_condition_with_or():
    assert generate_jq_filter(
        [('field', 'name', 'name'), ('field', 'age', 'age')],
        '(.age? > 30 or .city? == "Los Angeles")', None, None, None, None
    ) == (
        'if type == "array" then . | map(select((.age? > 30 or .city? == "Los Angeles")) | { "name": (.name? // null), "age": (.age? // null) }) '
        'elif type == "object" then [select((.age? > 30 or .city? == "Los Angeles")) | { "name": (.name? // null), "age": (.age? // null) }] '
        'elif type == "number" then if (.age? > 30 or .city? == "Los Angeles") then [{"value": .}] else [] end '
        'elif type == "string" then if (.age? > 30 or .city? == "Los Angeles") then [{"value": .}] else [] end '
        'else [] end'
    )

def test_complex_condition_with_nested_parentheses():
    assert generate_jq_filter(
        [('field', 'name', 'name'), ('field', 'age', 'age')],
        '((.age? > 30 and .city? == "Chicago") or (.age? < 30 and .city? == "Los Angeles"))', None, None, None, None
    ) == (
        'if type == "array" then . | map(select(((.age? > 30 and .city? == "Chicago") or (.age? < 30 and .city? == "Los Angeles"))) | { "name": (.name? // null), "age": (.age? // null) }) '
        'elif type == "object" then [select(((.age? > 30 and .city? == "Chicago") or (.age? < 30 and .city? == "Los Angeles"))) | { "name": (.name? // null), "age": (.age? // null) }] '
        'elif type == "number" then if ((.age? > 30 and .city? == "Chicago") or (.age? < 30 and .city? == "Los Angeles")) then [{"value": .}] else [] end '
        'elif type == "string" then if ((.age? > 30 and .city? == "Chicago") or (.age? < 30 and .city? == "Los Angeles")) then [{"value": .}] else [] end '
        'else [] end'
    )

def test_group_by_single_field():
    assert generate_jq_filter(
        [('field', 'city', 'city'), ('aggregation', 'count', '*', 'count')],
        None, ['city'], None, None, None
    ) == '. | map(select(. != null)) | group_by(.city) | map({ "city": .[0].city, "count": length })'

def test_group_by_with_avg_aggregation():
    assert generate_jq_filter(
        [('field', 'city', 'city'), ('aggregation', 'avg', 'age', 'avg_age')],
        None, ['city'], None, None, None
    ) == '. | map(select(. != null)) | group_by(.city) | map({ "city": .[0].city, "avg_age": (map(.age? // null) | map(select(type == "number")) | add / length) })'

def test_group_by_with_multiple_aggregations():
    assert generate_jq_filter(
        [
            ('field', 'city', 'city'),
            ('aggregation', 'count', '*', 'count'),
            ('aggregation', 'avg', 'age', 'avg_age'),
            ('aggregation', 'min', 'age', 'min_age'),
            ('aggregation', 'max', 'age', 'max_age')
        ],
        None, ['city'], None, None, None
    ) == '. | map(select(. != null)) | group_by(.city) | map({ "city": .[0].city, "count": length, "avg_age": (map(.age? // null) | map(select(type == "number")) | add / length), "min_age": (map(.age? // null) | map(select(type == "number")) | min), "max_age": (map(.age? // null) | map(select(type == "number")) | max) })'

def test_group_by_nested_field():
    assert generate_jq_filter(
        [('field', 'profile.address.city', 'city'), ('aggregation', 'count', '*', 'count')],
        None, ['profile.address.city'], None, None, None
    ) == '. | map(select(. != null)) | group_by(.profile.address.city) | map({ "city": .[0].profile.address.city, "count": length })'

def test_arithmetic_expression_with_subtraction():
    assert generate_jq_filter(
        [('expression', 'max(orders.price) - min(orders.price)', 'price_range')],
        None, None, None, None, None
    ) == (
        'if type == "array" then . | map({ "price_range": ((.orders[]? | .price? | select(type == "number") | max) - (.orders[]? | .price? | select(type == "number") | min)) }) '
        'elif type == "object" then [{ "price_range": ((.orders[]? | .price? | select(type == "number") | max) - (.orders[]? | .price? | select(type == "number") | min)) }] '
        'elif type == "number" then [{"value": .}] '
        'elif type == "string" then [{"value": .}] '
        'else [] end'
    )

def test_arithmetic_expression_with_addition():
    assert generate_jq_filter(
        [('expression', '.age + 10', 'age_plus_10')],
        None, None, None, None, None
    ) == (
        'if type == "array" then . | map({ "age_plus_10": (.age + 10) }) '
        'elif type == "object" then [{ "age_plus_10": (.age + 10) }] '
        'elif type == "number" then [{"value": .}] '
        'elif type == "string" then [{"value": .}] '
        'else [] end'
    )

def test_count_star():
    assert generate_jq_filter(
        [('aggregation', 'count', '*', 'total_count')],
        None, None, None, None, None
    ) == '{ "total_count": length }'

def test_count_star_with_condition():
    assert generate_jq_filter(
        [('aggregation', 'count', '*', 'adult_count')],
        '.age? > 18', None, None, None, None
    ) == '{ "adult_count": length }'

def test_deeply_nested_field_access():
    assert generate_jq_filter(
        [('field', 'profile.address.city', 'city'), ('field', 'profile.address.zip', 'zip')],
        None, None, None, None, None
    ) == (
        'if type == "array" then . | map({ "city": (.profile?.address?.city? // null), "zip": (.profile?.address?.zip? // null) }) '
        'elif type == "object" then [{ "city": (.profile?.address?.city? // null), "zip": (.profile?.address?.zip? // null) }] '
        'elif type == "number" then [{"value": .}] '
        'elif type == "string" then [{"value": .}] '
        'else [] end'
    )

def test_array_index_access():
    assert generate_jq_filter(
        [('field', 'orders[0].item', 'first_item')],
        None, None, None, None, None
    ) == (
        'if type == "array" then . | map({ "first_item": (.orders[0]?.item? // null) }) '
        'elif type == "object" then [{ "first_item": (.orders[0]?.item? // null) }] '
        'elif type == "number" then [{"value": .}] '
        'elif type == "string" then [{"value": .}] '
        'else [] end'
    )

def test_field_with_special_characters():
    assert generate_jq_filter(
        [('field', 'first-name', 'first_name')],
        None, None, None, None, None
    ) == (
        'if type == "array" then . | map({ "first_name": (."first-name"? // null) }) '
        'elif type == "object" then [{ "first_name": (."first-name"? // null) }] '
        'elif type == "number" then [{"value": .}] '
        'elif type == "string" then [{"value": .}] '
        'else [] end'
    )

def test_field_with_quoted_names():
    assert generate_jq_filter(
        [('field', "user's name", 'username')],
        None, None, None, None, None
    ) == (
        'if type == "array" then . | map({ "username": (."user\'s name"? // null) }) '
        'elif type == "object" then [{ "username": (."user\'s name"? // null) }] '
        'elif type == "number" then [{"value": .}] '
        'elif type == "string" then [{"value": .}] '
        'else [] end'
    )

def test_complex_query_with_nested_fields_and_conditions():
    assert generate_jq_filter(
        [('field', 'name', 'name'), ('field', 'profile.age', 'age')],
        '(.profile?.age? > 25 and .profile?.address?.city? == "New York")', None, None, None, None
    ) == (
        'if type == "array" then . | map(select((.profile?.age? > 25 and .profile?.address?.city? == "New York")) | { "name": (.name? // null), "age": (.profile?.age? // null) }) '
        'elif type == "object" then [select((.profile?.age? > 25 and .profile?.address?.city? == "New York")) | { "name": (.name? // null), "age": (.profile?.age? // null) }] '
        'elif type == "number" then if (.profile?.age? > 25 and .profile?.address?.city? == "New York") then [{"value": .}] else [] end '
        'elif type == "string" then if (.profile?.age? > 25 and .profile?.address?.city? == "New York") then [{"value": .}] else [] end '
        'else [] end'
    )

def test_complex_group_by_with_nested_fields_and_array_aggregation():
    assert generate_jq_filter(
        [
            ('field', 'profile.address.city', 'city'),
            ('aggregation', 'count', 'orders', 'order_count'),
            ('aggregation', 'avg', 'orders.price', 'avg_price')
        ],
        None, ['profile.address.city'], None, None, None
    ) == '. | map(select(. != null)) | group_by(.profile.address.city) | map({ "city": .[0].profile.address.city, "order_count": (map(.orders? | select(. != null) | length) | add), "avg_price": (map(.orders[]? | .price? | select(type == "number")) | if length > 0 then add / length else null end) })'

def test_query_with_multiple_order_by():
    assert generate_jq_filter(
        [('field', 'name', 'name'), ('field', 'age', 'age')],
        None, None, 'age', 'desc', 3
    ) == (
        'if type == "array" then . | map({ "name": (.name? // null), "age": (.age? // null) }) '
        'elif type == "object" then [{ "name": (.name? // null), "age": (.age? // null) }] '
        'elif type == "number" then [{"value": .}] '
        'elif type == "string" then [{"value": .}] '
        'else [] end | sort_by(.age) | reverse | .[0:3]'
    )