import pytest
from jonq.query_parser import tokenize_query, parse_query, parse_condition_string, is_balanced


class TestTokenizeQuery:
    def test_non_string_raises(self):
        with pytest.raises(ValueError, match="must be a string"):
            tokenize_query(123)

    def test_unbalanced_parens_raises(self):
        with pytest.raises(ValueError, match="Unbalanced"):
            tokenize_query("select count(")


class TestIsBalanced:
    def test_balanced(self):
        assert is_balanced(["(", "a", ")"]) is True

    def test_empty(self):
        assert is_balanced([]) is True

    def test_unbalanced_open(self):
        assert is_balanced(["("]) is False

    def test_unbalanced_close(self):
        assert is_balanced([")"]) is False

    def test_nested_balanced(self):
        assert is_balanced(["(", "(", ")", ")"]) is True


class TestParseQueryCaseWhen:
    def test_case_basic(self):
        tokens = tokenize_query('select case when age > 30 then "old" end as label')
        fields, *_ = parse_query(tokens)
        assert fields[0][0] == "expression"
        assert "case" in fields[0][1]

    def test_case_with_alias(self):
        tokens = tokenize_query('select case when x > 1 then "yes" else "no" end as flag')
        fields, *_ = parse_query(tokens)
        assert fields[0][-1] == "flag"

    def test_case_auto_alias(self):
        tokens = tokenize_query('select case when x > 1 then "yes" end')
        fields, *_ = parse_query(tokens)
        assert "case_" in fields[0][-1]

    def test_case_with_other_fields(self):
        tokens = tokenize_query('select name, case when age > 30 then "old" else "young" end as label')
        fields, *_ = parse_query(tokens)
        assert len(fields) == 2
        assert fields[0][0] == "field"
        assert fields[1][0] == "expression"


class TestParseQueryMultiArgFunctions:
    def test_coalesce_parsed_as_expression(self):
        tokens = tokenize_query("select coalesce(a, b) as val")
        fields, *_ = parse_query(tokens)
        assert fields[0][0] == "expression"
        assert "coalesce" in fields[0][1]


class TestParseConditionIsNull:
    def test_is_null(self):
        cond = parse_condition_string("name is null")
        from jonq.ast import Condition
        assert isinstance(cond, Condition)

    def test_is_not_null(self):
        cond = parse_condition_string("email is not null")
        from jonq.ast import Condition
        assert isinstance(cond, Condition)

    def test_is_null_case_insensitive(self):
        cond = parse_condition_string("name IS NULL")
        from jonq.ast import Condition
        assert isinstance(cond, Condition)

    def test_is_not_null_case_insensitive(self):
        cond = parse_condition_string("name IS NOT NULL")
        from jonq.ast import Condition
        assert isinstance(cond, Condition)

    def test_nested_field_is_null(self):
        cond = parse_condition_string("profile.email is null")
        from jonq.ast import Condition
        assert isinstance(cond, Condition)


class TestParseQueryEdgeCases:
    def test_no_select_raises(self):
        tokens = tokenize_query("name age")
        with pytest.raises(ValueError, match="must start with 'select'"):
            parse_query(tokens)

    def test_select_star_limit(self):
        tokens = tokenize_query("select * limit 5")
        fields, cond, group_by, having, order_by, sort_dir, limit, from_path, distinct = parse_query(tokens)
        assert fields == [("field", "*", "*")]
        assert limit == "5"

    def test_select_distinct(self):
        tokens = tokenize_query("select distinct city")
        *_, distinct = parse_query(tokens)
        assert distinct is True

    def test_sort_asc(self):
        tokens = tokenize_query("select name sort name asc")
        _, _, _, _, order_by, sort_dir, *_ = parse_query(tokens)
        assert order_by == "name"
        assert sort_dir == "asc"

    def test_sort_desc(self):
        tokens = tokenize_query("select name sort name desc")
        _, _, _, _, order_by, sort_dir, *_ = parse_query(tokens)
        assert sort_dir == "desc"

    def test_group_by_multiple(self):
        tokens = tokenize_query("select city, state, count(*) as cnt group by city, state")
        _, _, group_by, *_ = parse_query(tokens)
        assert group_by == ["city", "state"]

    def test_having_requires_group_by(self):
        tokens = tokenize_query("select name having name > 1")
        with pytest.raises(ValueError, match="HAVING.*GROUP BY"):
            parse_query(tokens)

    def test_from_clause(self):
        tokens = tokenize_query("select name from products")
        *_, from_path, _ = parse_query(tokens)
        assert from_path == "products"

    def test_count_distinct(self):
        tokens = tokenize_query("select count(distinct city) as n")
        fields, *_ = parse_query(tokens)
        assert fields[0][0] == "count_distinct"

    def test_multiple_scalar_functions(self):
        tokens = tokenize_query("select upper(name) as n, lower(city) as c")
        fields, *_ = parse_query(tokens)
        assert fields[0][0] == "function"
        assert fields[0][1] == "upper"
        assert fields[1][0] == "function"
        assert fields[1][1] == "lower"
