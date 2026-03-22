"""Tests for parser.py edge cases — expressions, conditions, paths."""

import pytest
from jonq.parser import parse_expression, parse_path, _split_args, _parse_case_expression
from jonq.ast import ExprType, PathType


class TestParsePath:
    def test_empty_path(self):
        path = parse_path("")
        assert path.elements == []

    def test_wildcard(self):
        path = parse_path("*")
        assert path.elements == []

    def test_simple_field(self):
        path = parse_path("name")
        assert len(path.elements) == 1
        assert path.elements[0].type == PathType.FIELD
        assert path.elements[0].value == "name"

    def test_dotted_path(self):
        path = parse_path("profile.address.city")
        assert len(path.elements) == 3
        assert path.elements[0].value == "profile"
        assert path.elements[1].value == "address"
        assert path.elements[2].value == "city"

    def test_array_wildcard(self):
        path = parse_path("orders[]")
        assert len(path.elements) == 1
        assert path.elements[0].type == PathType.ARRAY
        assert path.elements[0].value == "orders"

    def test_array_index(self):
        path = parse_path("items[0]")
        assert len(path.elements) == 2
        assert path.elements[0].type == PathType.FIELD
        assert path.elements[0].value == "items"
        assert path.elements[1].type == PathType.ARRAY_INDEX
        assert path.elements[1].value == "0"

    def test_nested_array_field(self):
        path = parse_path("orders[].item")
        assert len(path.elements) == 2
        assert path.elements[0].type == PathType.ARRAY
        assert path.elements[0].value == "orders"

    def test_leading_dot(self):
        path = parse_path(".name")
        assert len(path.elements) == 1
        assert path.elements[0].value == "name"


class TestParseExpression:
    def test_field(self):
        expr = parse_expression("name")
        assert expr.type == ExprType.FIELD
        assert expr.value == "name"

    def test_string_literal(self):
        expr = parse_expression('"hello"')
        assert expr.type == ExprType.LITERAL
        assert expr.value == '"hello"'

    def test_number_literal_int(self):
        expr = parse_expression("42")
        assert expr.type == ExprType.LITERAL

    def test_number_literal_float(self):
        expr = parse_expression("3.14")
        assert expr.type == ExprType.LITERAL

    def test_addition(self):
        expr = parse_expression("a + b")
        assert expr.type == ExprType.OPERATION
        assert expr.value == "+"

    def test_subtraction(self):
        expr = parse_expression("a - b")
        assert expr.type == ExprType.OPERATION
        assert expr.value == "-"

    def test_multiplication(self):
        expr = parse_expression("a * b")
        assert expr.type == ExprType.OPERATION
        assert expr.value == "*"

    def test_division(self):
        expr = parse_expression("a / b")
        assert expr.type == ExprType.OPERATION
        assert expr.value == "/"

    def test_pipe_concat(self):
        expr = parse_expression('a || " " || b')
        assert expr.type == ExprType.OPERATION
        assert expr.value == "+"  # mapped to jq +

    def test_aggregation_sum(self):
        expr = parse_expression("sum(price)")
        assert expr.type == ExprType.AGGREGATION
        assert expr.value == "sum"

    def test_aggregation_count(self):
        expr = parse_expression("count(*)")
        assert expr.type == ExprType.AGGREGATION
        assert expr.value == "count"

    def test_scalar_function_upper(self):
        expr = parse_expression("upper(name)")
        assert expr.type == ExprType.FUNCTION
        assert expr.value == "upper"

    def test_scalar_function_todate(self):
        expr = parse_expression("todate(ts)")
        assert expr.type == ExprType.FUNCTION
        assert expr.value == "todate"

    def test_coalesce_two_args(self):
        expr = parse_expression("coalesce(a, b)")
        assert expr.type == ExprType.FUNCTION
        assert expr.value == "coalesce"
        assert len(expr.args) == 2

    def test_coalesce_nested_function(self):
        expr = parse_expression('coalesce(todate(ts), "unknown")')
        assert expr.type == ExprType.FUNCTION
        assert expr.value == "coalesce"
        assert expr.args[0].type == ExprType.FUNCTION
        assert expr.args[0].value == "todate"

    def test_case_expression(self):
        expr = parse_expression('case when x > 1 then "big" else "small" end')
        assert expr.type == ExprType.CASE


class TestSplitArgs:
    def test_simple(self):
        result = _split_args("a, b, c")
        assert result == ["a", "b", "c"]

    def test_nested_parens(self):
        result = _split_args('todate(ts), "unknown"')
        assert result == ["todate(ts)", '"unknown"']

    def test_single_arg(self):
        result = _split_args("a")
        assert result == ["a"]

    def test_empty(self):
        result = _split_args("")
        assert result == [] or result == [""]

    def test_quoted_comma(self):
        result = _split_args('"a,b", c')
        assert len(result) == 2
        assert result[0] == '"a,b"'

    def test_deeply_nested(self):
        result = _split_args("f(g(x)), y")
        assert len(result) == 2
        assert result[0] == "f(g(x))"


class TestParseCaseExpression:
    def test_single_when(self):
        expr = _parse_case_expression('case when x > 1 then "yes" end')
        assert expr.type == ExprType.CASE
        assert len(expr.args) == 1
        assert expr.value is None  # no else

    def test_with_else(self):
        expr = _parse_case_expression('case when x > 1 then "yes" else "no" end')
        assert expr.value == '"no"'

    def test_multiple_whens(self):
        expr = _parse_case_expression('case when x > 10 then "big" when x > 5 then "mid" else "small" end')
        assert len(expr.args) == 2
        assert expr.value == '"small"'
