import pytest
from jonq.query_parser import tokenize, parse_query

def test_select_all():
    tokens = tokenize("select *")
    fields, condition, group_by, order_by, sort_direction, limit = parse_query(tokens)
    assert fields == [('field', '*', '*')]
    assert condition is None
    assert group_by is None
    assert order_by is None
    assert sort_direction == 'asc'
    assert limit is None

def test_select_fields():
    tokens = tokenize("select name, age")
    fields, condition, group_by, order_by, sort_direction, limit = parse_query(tokens)
    assert fields == [('field', 'name', 'name'), ('field', 'age', 'age')]
    assert condition is None
    assert group_by is None
    assert order_by is None
    assert sort_direction == 'asc'
    assert limit is None

def test_select_fields_with_condition():
    tokens = tokenize("select name, age if age > 30")
    fields, condition, group_by, order_by, sort_direction, limit = parse_query(tokens)
    assert fields == [('field', 'name', 'name'), ('field', 'age', 'age')]
    assert condition == '.age? > 30'
    assert group_by is None
    assert order_by is None
    assert sort_direction == 'asc'
    assert limit is None

def test_select_fields_with_sorting():
    tokens = tokenize("select name, age sort age desc 5")
    fields, condition, group_by, order_by, sort_direction, limit = parse_query(tokens)
    assert fields == [('field', 'name', 'name'), ('field', 'age', 'age')]
    assert condition is None
    assert group_by is None
    assert order_by == 'age'
    assert sort_direction == 'desc'
    assert limit == '5'

def test_select_with_aggregation():
    tokens = tokenize("select sum(age) as total_age")
    fields, condition, group_by, order_by, sort_direction, limit = parse_query(tokens)
    assert fields == [('aggregation', 'sum', 'age', 'total_age')]
    assert condition is None
    assert group_by is None
    assert order_by is None
    assert sort_direction == 'asc'
    assert limit is None

def test_select_with_nested_fields():
    tokens = tokenize("select name, profile.age, profile.address.city")
    fields, condition, group_by, order_by, sort_direction, limit = parse_query(tokens)
    assert fields == [
        ('field', 'name', 'name'), 
        ('field', 'profile.age', 'age'),
        ('field', 'profile.address.city', 'city')
    ]
    assert condition is None
    assert group_by is None
    assert order_by is None
    assert sort_direction == 'asc'
    assert limit is None

def test_select_with_quotes():
    tokens = tokenize("select 'first name', \"last name\"")
    fields, condition, group_by, order_by, sort_direction, limit = parse_query(tokens)
    assert fields == [('field', 'first name', 'first_name'), ('field', 'last name', 'last_name')]
    assert condition is None
    assert group_by is None
    assert order_by is None
    assert sort_direction == 'asc'
    assert limit is None

def test_select_with_quoted_condition():
    tokens = tokenize("select name if 'first name' = 'Alice'")
    fields, condition, group_by, order_by, sort_direction, limit = parse_query(tokens)
    assert fields == [('field', 'name', 'name')]
    assert condition == '.\"first name\"? == \'Alice\''
    assert group_by is None
    assert order_by is None
    assert sort_direction == 'asc'
    assert limit is None

def test_select_with_expression():
    tokens = tokenize("select sum(items.price) * 2 as double_total")
    fields, condition, group_by, order_by, sort_direction, limit = parse_query(tokens)
    assert fields == [('expression', 'sum ( items.price ) * 2', 'double_total')]
    assert condition is None
    assert group_by is None
    assert order_by is None
    assert sort_direction == 'asc'
    assert limit is None

def test_invalid_query():
    tokens = tokenize("filter name, age")
    with pytest.raises(ValueError) as excinfo:
        parse_query(tokens)
    assert "Query must start with 'select'" in str(excinfo.value)

def test_unexpected_tokens():
    tokens = tokenize("select name, age unexpected tokens")
    with pytest.raises(ValueError) as excinfo:
        parse_query(tokens)
    assert "Unexpected tokens" in str(excinfo.value)

def test_select_with_and_condition():
    tokens = tokenize("select name if age > 25 and city = 'New York'")
    fields, condition, group_by, order_by, sort_direction, limit = parse_query(tokens)
    assert fields == [('field', 'name', 'name')]
    assert condition == "(.age? > 25 and .city? == \"New York\")"
    assert group_by is None
    assert order_by is None
    assert sort_direction == 'asc'
    assert limit is None

def test_select_with_or_condition():
    tokens = tokenize("select name if age > 30 or city = 'Los Angeles'")
    fields, condition, group_by, order_by, sort_direction, limit = parse_query(tokens)
    assert fields == [('field', 'name', 'name')]
    assert condition == "(.age? > 30 or .city? == \"Los Angeles\")"
    assert group_by is None
    assert order_by is None
    assert sort_direction == 'asc'
    assert limit is None

def test_select_with_nested_parentheses():
    tokens = tokenize("select name if (age > 30 and city = 'Chicago') or (age < 30 and city = 'Los Angeles')")
    fields, condition, group_by, order_by, sort_direction, limit = parse_query(tokens)
    assert fields == [('field', 'name', 'name')]
    assert condition == "((.age? > 30 and .city? == \"Chicago\") or (.age? < 30 and .city? == \"Los Angeles\"))"
    assert group_by is None
    assert order_by is None
    assert sort_direction == 'asc'
    assert limit is None

def test_select_with_group_by():
    tokens = tokenize("select city, count(*) as count group by city")
    fields, condition, group_by, order_by, sort_direction, limit = parse_query(tokens)
    assert fields == [('field', 'city', 'city'), ('aggregation', 'count', '*', 'count')]
    assert condition is None
    assert group_by == ['city']
    assert order_by is None
    assert sort_direction == 'asc'
    assert limit is None

def test_select_with_group_by_and_aggregation():
    tokens = tokenize("select city, avg(age) as avg_age group by city")
    fields, condition, group_by, order_by, sort_direction, limit = parse_query(tokens)
    assert fields == [('field', 'city', 'city'), ('aggregation', 'avg', 'age', 'avg_age')]
    assert condition is None
    assert group_by == ['city']
    assert order_by is None
    assert sort_direction == 'asc'
    assert limit is None

def test_select_with_nested_group_by():
    tokens = tokenize("select profile.address.city, count(*) as count group by profile.address.city")
    fields, condition, group_by, order_by, sort_direction, limit = parse_query(tokens)
    assert fields == [('field', 'profile.address.city', 'city'), ('aggregation', 'count', '*', 'count')]
    assert condition is None
    assert group_by == ['profile.address.city']
    assert order_by is None
    assert sort_direction == 'asc'
    assert limit is None

def test_select_with_arithmetic_expression():
    tokens = tokenize("select name, age + 10 as age_plus_10")
    fields, condition, group_by, order_by, sort_direction, limit = parse_query(tokens)
    assert fields == [('field', 'name', 'name'), ('expression', 'age + 10', 'age_plus_10')]
    assert condition is None
    assert group_by is None
    assert order_by is None
    assert sort_direction == 'asc'
    assert limit is None

def test_select_with_min_max_subtraction():
    tokens = tokenize("select name, max(orders.price) - min(orders.price) as price_range")
    fields, condition, group_by, order_by, sort_direction, limit = parse_query(tokens)
    assert fields == [('field', 'name', 'name'), ('expression', 'max ( orders.price ) - min ( orders.price )', 'price_range')]
    assert condition is None
    assert group_by is None
    assert order_by is None
    assert sort_direction == 'asc'
    assert limit is None

def test_select_with_array_index():
    tokens = tokenize("select name, orders[0].item as first_item")
    fields, condition, group_by, order_by, sort_direction, limit = parse_query(tokens)
    assert fields == [('field', 'name', 'name'), ('field', 'orders[0].item', 'first_item')]
    assert condition is None
    assert group_by is None
    assert order_by is None
    assert sort_direction == 'asc'
    assert limit is None

def test_select_with_array_condition():
    tokens = tokenize("select name if orders[0].price > 1000")
    fields, condition, group_by, order_by, sort_direction, limit = parse_query(tokens)
    assert fields == [('field', 'name', 'name')]
    assert condition == ".orders[0]?.price? > 1000"
    assert group_by is None
    assert order_by is None
    assert sort_direction == 'asc'
    assert limit is None

def test_select_with_hyphenated_field():
    tokens = tokenize("select first-name as first_name")
    fields, condition, group_by, order_by, sort_direction, limit = parse_query(tokens)
    assert fields == [('field', 'first-name', 'first_name')]
    assert condition is None
    assert group_by is None
    assert order_by is None
    assert sort_direction == 'asc'
    assert limit is None

def test_select_with_apostrophe_in_field():
    tokens = tokenize("select \"user's name\" as username")
    fields, condition, group_by, order_by, sort_direction, limit = parse_query(tokens)
    assert fields == [('field', "user's name", 'username')]
    assert condition is None
    assert group_by is None
    assert order_by is None
    assert sort_direction == 'asc'
    assert limit is None

def test_complex_query_with_multiple_features():
    tokens = tokenize("select name, profile.age, count(orders) as order_count if profile.age > 25 group by profile.address.city sort order_count desc 5")
    fields, condition, group_by, order_by, sort_direction, limit = parse_query(tokens)
    assert fields == [
        ('field', 'name', 'name'), 
        ('field', 'profile.age', 'age'),
        ('aggregation', 'count', 'orders', 'order_count')
    ]
    assert condition == ".profile?.age? > 25"
    assert group_by == ['profile.address.city']
    assert order_by == 'order_count'
    assert sort_direction == 'desc'
    assert limit == '5'