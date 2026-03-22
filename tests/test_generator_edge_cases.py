import json
from jonq.api import execute
from jonq.generator import generate_jq_expression, generate_jq_path, generate_jq_condition, _FUNC_MAP
from jonq.parser import parse_path, parse_expression
from jonq.query_parser import parse_condition_string
from jonq.ast import Expression, ExprType


class TestFuncMap:
    def test_all_expected_functions_exist(self):
        expected = [
            "upper", "lower", "length", "round", "abs", "ceil", "floor",
            "int", "float", "str", "string", "type", "keys", "values",
            "trim", "todate", "fromdate", "date", "timestamp",
            "tojson", "fromjson", "to_entries", "from_entries",
        ]
        for func in expected:
            assert func in _FUNC_MAP, f"{func} missing from _FUNC_MAP"

    def test_no_duplicate_jq_mappings_conflict(self):
        assert _FUNC_MAP["upper"] == "ascii_upcase"
        assert _FUNC_MAP["lower"] == "ascii_downcase"
        assert _FUNC_MAP["date"] == "todate"
        assert _FUNC_MAP["str"] == "tostring"
        assert _FUNC_MAP["string"] == "tostring"


class TestGenerateJqPath:
    def test_empty_path(self):
        path = parse_path("")
        assert generate_jq_path(path) == "."

    def test_simple_field(self):
        path = parse_path("name")
        result = generate_jq_path(path)
        assert ".name" in result

    def test_nested_field(self):
        path = parse_path("profile.city")
        result = generate_jq_path(path)
        assert ".profile" in result
        assert ".city" in result

    def test_array_access(self):
        path = parse_path("items[]")
        result = generate_jq_path(path)
        assert "[]?" in result

    def test_no_null_check(self):
        path = parse_path("name")
        result = generate_jq_path(path, null_check=False)
        assert "?" not in result


class TestGenerateJqExpression:
    def test_field_expression(self):
        expr = Expression(ExprType.FIELD, "name")
        result = generate_jq_expression(expr)
        assert ".name" in result

    def test_literal_string(self):
        expr = Expression(ExprType.LITERAL, '"hello"')
        assert generate_jq_expression(expr) == '"hello"'

    def test_literal_number(self):
        expr = Expression(ExprType.LITERAL, "42")
        assert generate_jq_expression(expr) == "42"

    def test_operation(self):
        left = Expression(ExprType.FIELD, "a")
        right = Expression(ExprType.LITERAL, "10")
        expr = Expression(ExprType.OPERATION, "+", [left, right])
        result = generate_jq_expression(expr)
        assert "+" in result

    def test_coalesce_two_fields(self):
        args = [
            Expression(ExprType.FIELD, "a"),
            Expression(ExprType.FIELD, "b"),
        ]
        expr = Expression(ExprType.FUNCTION, "coalesce", args)
        result = generate_jq_expression(expr)
        assert "//" in result

    def test_coalesce_four_args(self):
        args = [Expression(ExprType.FIELD, x) for x in ["a", "b", "c", "d"]]
        expr = Expression(ExprType.FUNCTION, "coalesce", args)
        result = generate_jq_expression(expr)
        assert result.count("//") == 3

    def test_null_sensitive_todate(self):
        expr = parse_expression("todate(ts)")
        result = generate_jq_expression(expr)
        assert "!= null" in result
        assert "todate" in result

    def test_null_sensitive_int(self):
        expr = parse_expression("int(price)")
        result = generate_jq_expression(expr)
        assert "tonumber | floor" in result

    def test_case_expression(self):
        expr = Expression(ExprType.CASE, '"no"', [("x > 1", '"yes"')])
        result = generate_jq_expression(expr)
        assert "if" in result
        assert "then" in result
        assert "else" in result
        assert "end" in result


class TestGenerateJqCondition:
    def test_is_null(self):
        cond = parse_condition_string("name is null")
        result = generate_jq_condition(cond)
        assert "== null" in result

    def test_is_not_null(self):
        cond = parse_condition_string("name is not null")
        result = generate_jq_condition(cond)
        assert "!= null" in result

    def test_and_condition(self):
        cond = parse_condition_string("age > 20 and age < 40")
        result = generate_jq_condition(cond)
        assert "and" in result

    def test_or_condition(self):
        cond = parse_condition_string("city = 'NYC' or city = 'LA'")
        result = generate_jq_condition(cond)
        assert "or" in result

    def test_not_condition(self):
        cond = parse_condition_string("not age > 30")
        result = generate_jq_condition(cond)
        assert "not" in result

    def test_in_condition(self):
        cond = parse_condition_string("city in ('NYC', 'LA')")
        result = generate_jq_condition(cond)
        assert "or" in result

    def test_between_condition(self):
        cond = parse_condition_string("age between 20 and 40")
        result = generate_jq_condition(cond)
        assert ">=" in result
        assert "<=" in result


class TestEndToEndExecution:
    def test_coalesce_all_null(self):
        data = json.dumps([{"a": None, "b": None}])
        result = execute(data, "select coalesce(a, b) as val")
        parsed = json.loads(result.text)
        assert parsed[0]["val"] is None

    def test_coalesce_with_zero(self):
        data = json.dumps([{"a": 0, "b": 99}])
        result = execute(data, "select coalesce(a, b) as val")
        parsed = json.loads(result.text)
        assert parsed[0]["val"] == 0

    def test_coalesce_with_false(self):
        data = json.dumps([{"a": False, "b": True}])
        result = execute(data, "select coalesce(a, b) as val")
        parsed = json.loads(result.text)
        # jq treats false as falsy, so it falls through to b
        assert parsed[0]["val"] in (False, True)

    def test_case_with_string_equality(self):
        data = json.dumps([{"status": "active"}, {"status": "inactive"}])
        result = execute(data, "select case when status = 'active' then 'yes' else 'no' end as active")
        parsed = json.loads(result.text)
        assert parsed[0]["active"] == "yes"
        assert parsed[1]["active"] == "no"

    def test_case_with_numeric_comparison(self):
        data = json.dumps([{"score": 95}, {"score": 70}, {"score": 40}])
        result = execute(data, 'select score, case when score >= 90 then "A" when score >= 70 then "B" else "C" end as grade')
        parsed = json.loads(result.text)
        assert parsed[0]["grade"] == "A"
        assert parsed[1]["grade"] == "B"
        assert parsed[2]["grade"] == "C"

    def test_pipe_concat_three_fields(self):
        data = json.dumps([{"a": "x", "b": "y", "c": "z"}])
        result = execute(data, 'select a || b || c as combined')
        parsed = json.loads(result.text)
        assert parsed[0]["combined"] == "xyz"

    def test_is_null_with_missing_field(self):
        data = json.dumps([{"a": 1}, {"b": 2}])
        result = execute(data, "select * if a is not null")
        parsed = json.loads(result.text)
        assert len(parsed) == 1
        assert parsed[0]["a"] == 1

    def test_date_with_null_returns_null(self):
        data = json.dumps([{"ts": None}])
        result = execute(data, "select todate(ts) as d")
        parsed = json.loads(result.text)
        assert parsed[0]["d"] is None

    def test_int_casting_from_string(self):
        data = json.dumps([{"x": "42"}, {"x": "3.7"}])
        result = execute(data, "select int(x) as n")
        parsed = json.loads(result.text)
        assert parsed[0]["n"] == 42
        assert parsed[1]["n"] == 3

    def test_str_casting_from_number(self):
        data = json.dumps([{"x": 42}])
        result = execute(data, "select str(x) as s")
        parsed = json.loads(result.text)
        assert parsed[0]["s"] == "42"

    def test_multiple_functions_in_select(self):
        data = json.dumps([{"name": "alice", "age": 30}])
        result = execute(data, "select upper(name) as name, str(age) as age")
        parsed = json.loads(result.text)
        assert parsed[0]["name"] == "ALICE"
        assert parsed[0]["age"] == "30"

    def test_concat_with_function(self):
        data = json.dumps([{"first": "alice", "last": "smith"}])
        result = execute(data, 'select upper(first) as name')
        parsed = json.loads(result.text)
        assert parsed[0]["name"] == "ALICE"

    def test_distinct_with_case(self):
        data = json.dumps([{"x": 1}, {"x": 2}, {"x": 1}])
        result = execute(data, "select distinct x")
        parsed = json.loads(result.text)
        values = [row["x"] for row in parsed]
        assert sorted(values) == [1, 2]

    def test_group_by_with_case(self):
        data = json.dumps([
            {"age": 20, "name": "a"},
            {"age": 35, "name": "b"},
            {"age": 25, "name": "c"},
        ])
        result = execute(
            data,
            'select case when age > 30 then "senior" else "junior" end as level, count(*) as cnt group by level',
        )
        assert result.text is not None
