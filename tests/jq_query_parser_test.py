import pytest
from jonq.query_parser import tokenize, parse_query


def _assert_no_extra(t):
    cond, grp, hav, ob, dir_, lim, src = t
    assert cond is None and grp is None and hav is None and ob is None
    assert dir_ == "asc" and lim is None and src is None


def _extract(q):
    return parse_query(tokenize(q))


def test_select_all():
    fields, *tail = _extract("select *")
    assert fields == [("field", "*", "*")]
    _assert_no_extra(tail)


def test_select_fields():
    fields, *tail = _extract("select name, age")
    assert ("field", "name", "name") in fields and ("field", "age", "age") in fields
    _assert_no_extra(tail)


@pytest.mark.parametrize(
    "q,bits",
    [
        ("select name, age if age > 30", [".age", "> 30"]),
        ("select name if age > 25 and city = 'New York'", [".age", "> 25", "city", "New York"]),
        ("select name if age > 30 or city = 'Los Angeles'", ["or", "Los Angeles"]),
        (
            "select name if (age > 30 and city = 'Chicago') or (age < 30 and city = 'Los Angeles')",
            ["Chicago", "Los Angeles"],
        ),
        ("select name if orders[0].price > 1000", ["orders[0]", "1000"]),
    ],
)
def test_if_conditions(q, bits):
    _, cond, *rest = _extract(q)
    for b in bits:
        assert b in cond


def test_sort_and_limit():
    _, _, _, _, ob, dir_, lim, src = _extract("select name, age sort age desc 5")
    assert (ob, dir_, lim, src) == ("age", "desc", "5", None)


def test_group_by_count():
    f, cond, grp, *_ = _extract("select city, count(*) as count group by city")
    assert ("aggregation", "count", "*", "count") in f and grp == ["city"] and cond is None


def test_group_by_avg():
    f, _, grp, *_ = _extract("select city, avg(age) as avg_age group by city")
    assert ("aggregation", "avg", "age", "avg_age") in f and grp == ["city"]


def test_nested_group_by():
    f, _, grp, *_ = _extract(
        "select profile.address.city, count(*) as count group by profile.address.city"
    )
    assert ("field", "profile.address.city", "city") in f and grp == ["profile.address.city"]


def test_from_simple():
    *_, src = _extract("select type, count(customers) as customer_count from products")
    assert src == "products"


def test_from_with_condition():
    f, cond, *_, src = _extract("select type, price from products if price > 100")
    assert ("field", "price", "price") in f and "price > 100" in cond and src == "products"


def test_from_group_by_having_sort_limit():
    f, cond, grp, hav, ob, dir_, lim, src = _extract(
        "select type, count(customers) as customer_count "
        "from products if launched > 2010 "
        "group by type having customer_count > 2 "
        "sort customer_count desc 5"
    )
    assert ("aggregation", "count", "customers", "customer_count") in f
    assert "launched" in cond and grp == ["type"] and "customer_count" in hav
    assert (ob, dir_, lim, src) == ("customer_count", "desc", "5", "products")


def test_quoted_idents():
    f, *_ = _extract("select 'first name', \"last name\"")
    assert ("field", "first name", "first_name") in f and ("field", "last name", "last_name") in f


def test_hyphen_and_apostrophe_idents():
    f1, *_ = _extract("select first-name as first_name")
    f2, *_ = _extract('select "user\'s name" as username')
    assert f1[0] == ("field", "first-name", "first_name")
    assert f2[0] == ("field", "user's name", "username")


def test_invalid_start_keyword():
    with pytest.raises(ValueError):
        parse_query(tokenize("filter name, age"))


def test_extra_tokens_fail():
    with pytest.raises(ValueError):
        parse_query(tokenize("select name, age unexpected tokens"))
