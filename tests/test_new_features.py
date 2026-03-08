import pytest
import json
import os
import tempfile
from jonq.query_parser import tokenize_query, parse_query
from jonq.jq_filter import generate_jq_filter
from jonq.error_handler import _edit_distance, _fuzzy_suggest, validate_query_against_schema
from jonq.main import _looks_like_ndjson, _colorize_json, _type_label


def _parse(q):
    return parse_query(tokenize_query(q))


def _filter(q):
    fields, condition, group_by, having, order_by, sort_direction, limit, from_path, distinct = _parse(q)
    return generate_jq_filter(fields, condition, group_by, having, order_by, sort_direction, limit, from_path, distinct)



class TestDistinct:
    def test_parse_distinct_flag(self):
        *_, distinct = _parse("select distinct name, age")
        assert distinct is True

    def test_parse_no_distinct(self):
        *_, distinct = _parse("select name, age")
        assert distinct is False

    def test_distinct_generates_unique(self):
        jq = _filter("select distinct city")
        assert "unique" in jq

    def test_distinct_wildcard(self):
        jq = _filter("select distinct *")
        assert "unique" in jq



class TestCountDistinct:
    def test_parse_count_distinct(self):
        fields, *_ = _parse("select count(distinct city) as unique_cities")
        assert ("count_distinct", "city", "unique_cities") in fields

    def test_count_distinct_generates_unique_length(self):
        jq = _filter("select count(distinct city) as unique_cities")
        assert "unique" in jq
        assert "length" in jq



class TestLimit:
    def test_parse_standalone_limit(self):
        _, _, _, _, _, _, limit, _, _ = _parse("select name, age limit 5")
        assert limit == "5"

    def test_standalone_limit_generates_slice(self):
        jq = _filter("select name, age limit 5")
        assert ".[0:5]" in jq

    def test_limit_with_condition(self):
        jq = _filter("select name, age if age > 20 limit 3")
        assert ".[0:3]" in jq

    def test_limit_wildcard(self):
        jq = _filter("select * limit 2")
        assert ".[0:2]" in jq

    def test_limit_with_group_by(self):
        jq = _filter("select city, count(*) as cnt group by city limit 2")
        assert ".[0:2]" in jq


class TestInOperator:
    def test_parse_in_condition(self):
        _, cond, *_ = _parse("select * if city in ('New York', 'Chicago')")
        assert '"New York"' in cond
        assert '"Chicago"' in cond
        assert " or " in cond

    def test_in_generates_or_chain(self):
        jq = _filter("select name if city in ('New York', 'Chicago')")
        assert '"New York"' in jq or "New York" in jq
        assert '"Chicago"' in jq or "Chicago" in jq



class TestNotOperator:
    def test_parse_not_condition(self):
        _, cond, *_ = _parse("select * if not age > 30")
        assert "not" in cond

    def test_not_generates_pipe_not(self):
        jq = _filter("select name if not age > 30")
        assert "| not)" in jq



class TestLikeOperator:
    def test_like_startswith(self):
        jq = _filter("select * if name like 'Al%'")
        assert "startswith" in jq
        assert '"Al"' in jq

    def test_like_endswith(self):
        jq = _filter("select * if name like '%ice'")
        assert "endswith" in jq
        assert '"ice"' in jq

    def test_like_contains(self):
        jq = _filter("select * if name like '%li%'")
        assert "test" in jq
        assert '"li"' in jq

    def test_like_exact(self):
        jq = _filter("select * if name like 'Alice'")
        assert "test" in jq
        assert '"Alice"' in jq



class TestStringFunctions:
    def test_upper_function(self):
        fields, *_ = _parse("select upper(name) as name_upper")
        assert ("function", "upper", "name", "name_upper") in fields

    def test_upper_generates_upcase(self):
        jq = _filter("select upper(name) as name_upper")
        assert "ascii_upcase" in jq

    def test_lower_function(self):
        jq = _filter("select lower(name) as name_lower")
        assert "ascii_downcase" in jq

    def test_length_function(self):
        jq = _filter("select length(name) as name_len")
        assert "length" in jq



class TestMathFunctions:
    def test_round_function(self):
        fields, *_ = _parse("select round(age) as rounded_age")
        assert ("function", "round", "age", "rounded_age") in fields

    def test_round_generates_jq(self):
        jq = _filter("select round(age) as rounded_age")
        assert "round" in jq

    def test_floor_function(self):
        jq = _filter("select floor(age) as floor_age")
        assert "floor" in jq

    def test_ceil_function(self):
        jq = _filter("select ceil(age) as ceil_age")
        assert "ceil" in jq

    def test_abs_function(self):
        jq = _filter("select abs(age) as abs_age")
        assert "fabs" in jq



class TestDynamicHaving:
    def test_having_with_custom_alias(self):
        jq = _filter("select city, count(*) as city_count group by city having city_count > 2")
        assert ".city_count" in jq
        assert "> 2" in jq

    def test_having_with_standard_alias(self):
        jq = _filter("select city, avg(age) as avg_age group by city having avg_age > 25")
        assert ".avg_age" in jq
        assert "> 25" in jq

    def test_having_and_condition(self):
        jq = _filter("select city, count(*) as cnt, avg(age) as avg_age group by city having cnt > 1 and avg_age > 25")
        assert ".cnt" in jq
        assert ".avg_age" in jq



class TestNoComments:
    def test_sum_no_comment(self):
        jq = _filter("select sum(age) as total_age")
        assert "#" not in jq



class TestFuzzySuggestions:
    def test_edit_distance_identical(self):
        assert _edit_distance("name", "name") == 0

    def test_edit_distance_one_char(self):
        assert _edit_distance("nme", "name") == 1

    def test_edit_distance_two_chars(self):
        assert _edit_distance("agge", "age") == 1

    def test_fuzzy_suggest_finds_close_match(self):
        result = _fuzzy_suggest("nme", ["name", "age", "city"])
        assert "name" in result

    def test_fuzzy_suggest_no_match_when_too_far(self):
        result = _fuzzy_suggest("xyz", ["name", "age", "city"], max_dist=1)
        assert result == []

    def test_fuzzy_suggest_max_3_results(self):
        result = _fuzzy_suggest("a", ["ab", "ac", "ad", "ae", "af"])
        assert len(result) <= 3

    def test_validate_schema_suggests_fields(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump([{"name": "Alice", "age": 30}], f)
            tmp = f.name
        try:
            result = validate_query_against_schema(tmp, "select nme")
            assert result is not None
            assert "Did you mean" in result
            assert "name" in result
        finally:
            os.unlink(tmp)

    def test_validate_schema_ok_for_valid_fields(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump([{"name": "Alice", "age": 30}], f)
            tmp = f.name
        try:
            result = validate_query_against_schema(tmp, "select name, age")
            assert result is None
        finally:
            os.unlink(tmp)

    def test_validate_schema_distinct_not_flagged(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump([{"name": "Alice", "city": "NY"}], f)
            tmp = f.name
        try:
            result = validate_query_against_schema(tmp, "select distinct city")
            assert result is None
        finally:
            os.unlink(tmp)



class TestNdjsonDetect:
    def test_detects_ndjson(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write('{"a":1}\n{"a":2}\n{"a":3}\n')
            tmp = f.name
        try:
            assert _looks_like_ndjson(tmp) is True
        finally:
            os.unlink(tmp)

    def test_rejects_array_json(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump([{"a": 1}, {"a": 2}], f)
            tmp = f.name
        try:
            assert _looks_like_ndjson(tmp) is False
        finally:
            os.unlink(tmp)

    def test_rejects_single_object(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({"a": 1}, f)
            tmp = f.name
        try:
            assert _looks_like_ndjson(tmp) is False
        finally:
            os.unlink(tmp)

    def test_rejects_nonexistent(self):
        assert _looks_like_ndjson("/tmp/nonexistent_jonq_test.json") is False



class TestColorizeJson:
    def test_colorize_adds_ansi(self):
        raw = '{"name": "Alice", "age": 30}'
        colored = _colorize_json(raw)
        assert "\033[" in colored  # has ANSI codes

    def test_colorize_preserves_content(self):
        raw = '{"name": "Alice"}'
        colored = _colorize_json(raw)
        assert "name" in colored
        assert "Alice" in colored



class TestTypeLabel:
    def test_int(self):
        assert _type_label(42) == "int"

    def test_str(self):
        assert _type_label("hello") == "str"

    def test_list(self):
        assert _type_label([1, 2, 3]) == "array[3]"

    def test_dict(self):
        assert _type_label({"a": 1}) == "object{1}"

    def test_null(self):
        assert _type_label(None) == "null"

    def test_bool(self):
        assert _type_label(True) == "bool"

    def test_float(self):
        assert _type_label(3.14) == "float"
