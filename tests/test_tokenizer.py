import pytest
from jonq.tokenizer import tokenize


class TestBasicTokenization:
    def test_simple_select(self):
        tokens = tokenize("select name, age")
        assert tokens == ["select", "name", ",", "age"]

    def test_select_with_condition(self):
        tokens = tokenize("select name if age > 30")
        assert "select" in tokens
        assert "if" in tokens
        assert ">" in tokens

    def test_wildcard(self):
        tokens = tokenize("select *")
        assert tokens == ["select", "*"]

    def test_function_call_star(self):
        tokens = tokenize("select count(*)")
        assert "count" in tokens
        assert "(" in tokens
        assert "*" in tokens
        assert ")" in tokens

    def test_function_call_param(self):
        tokens = tokenize("select sum(age)")
        assert "sum" in tokens
        assert "age" in tokens

    def test_string_single_quotes(self):
        tokens = tokenize("select name if city = 'NYC'")
        assert "'NYC'" in tokens

    def test_string_double_quotes(self):
        tokens = tokenize('select name if city = "NYC"')
        assert '"NYC"' in tokens

    def test_number_int(self):
        tokens = tokenize("select * if age > 30")
        assert "30" in tokens

    def test_number_float(self):
        tokens = tokenize("select * if price > 9.99")
        assert "9.99" in tokens


class TestNewKeywords:
    def test_case_when_then_else_end(self):
        tokens = tokenize('select case when age > 30 then "old" else "young" end')
        assert "case" in tokens
        assert "when" in tokens
        assert "then" in tokens
        assert "else" in tokens
        assert "end" in tokens

    def test_is_null(self):
        tokens = tokenize("select * if name is null")
        assert "is" in tokens
        assert "null" in tokens

    def test_is_not_null(self):
        tokens = tokenize("select * if name is not null")
        assert "is" in tokens
        assert "not" in tokens
        assert "null" in tokens

    def test_coalesce(self):
        tokens = tokenize("select coalesce(a, b)")
        assert "coalesce" in tokens


class TestOperators:
    def test_pipe_concat(self):
        tokens = tokenize('select a || " " || b')
        assert "||" in tokens

    def test_all_comparison_ops(self):
        for op in ["=", "!=", ">=", "<=", ">", "<"]:
            tokens = tokenize(f"select * if x {op} 1")
            assert op in tokens

    def test_arithmetic_ops(self):
        for op in ["+", "*", "/"]:
            tokens = tokenize(f"select x {op} 1 as y")
            assert op in tokens

    def test_minus_op(self):
        tokens = tokenize("select x - 1 as y")
        assert "-" in tokens


class TestEdgeCases:
    def test_empty_query(self):
        tokens = tokenize("")
        assert tokens == []

    def test_whitespace_only(self):
        tokens = tokenize("   ")
        assert tokens == []

    def test_nested_field(self):
        tokens = tokenize("select profile.address.city")
        assert "profile.address.city" in tokens

    def test_array_index(self):
        tokens = tokenize("select items[0].name")
        assert "items[0].name" in tokens

    def test_array_wildcard(self):
        tokens = tokenize("select items[].name")
        assert "items[].name" in tokens

    def test_invalid_character(self):
        with pytest.raises(ValueError, match="Invalid character"):
            tokenize("select @name")

    def test_multiple_commas(self):
        tokens = tokenize("select a, b, c, d")
        assert tokens.count(",") == 3

    def test_deeply_nested_parens(self):
        tokens = tokenize("select count(distinct city)")
        assert "count" in tokens
        assert "distinct" in tokens
        assert "city" in tokens
