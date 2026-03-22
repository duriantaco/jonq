import json
import os
import pytest
from jonq.main import (
    _slurp_ndjson,
    _concat_glob,
    _type_label,
    _preview_value,
    _json_to_yaml,
    _json_to_yaml_simple,
    _yaml_scalar,
    _yaml_dump,
    _explain_query,
    validate_input_file,
)
from jonq.api import compile_query


class TestSlurpNdjson:
    def test_basic_ndjson(self, tmp_path):
        f = tmp_path / "data.ndjson"
        f.write_text('{"a":1}\n{"a":2}\n{"a":3}\n')
        result = _slurp_ndjson(str(f))
        parsed = json.loads(result)
        assert len(parsed) == 3
        assert parsed[0]["a"] == 1

    def test_empty_lines_skipped(self, tmp_path):
        f = tmp_path / "data.ndjson"
        f.write_text('{"a":1}\n\n{"a":2}\n\n')
        result = _slurp_ndjson(str(f))
        parsed = json.loads(result)
        assert len(parsed) == 2

    def test_single_line(self, tmp_path):
        f = tmp_path / "data.ndjson"
        f.write_text('{"a":1}\n')
        result = _slurp_ndjson(str(f))
        parsed = json.loads(result)
        assert len(parsed) == 1


class TestConcatGlob:
    def test_multiple_files(self, tmp_path):
        for i in range(3):
            f = tmp_path / f"data{i}.json"
            f.write_text(json.dumps([{"x": i}]))
        result_path = _concat_glob(str(tmp_path / "data*.json"))
        try:
            with open(result_path) as f:
                data = json.load(f)
            assert len(data) == 3
        finally:
            os.remove(result_path)

    def test_no_matches_raises(self):
        with pytest.raises(FileNotFoundError, match="No files matched"):
            _concat_glob("/nonexistent/path/*.json")

    def test_mixed_array_and_object(self, tmp_path):
        (tmp_path / "a.json").write_text('[{"x":1}]')
        (tmp_path / "b.json").write_text('{"x":2}')
        result_path = _concat_glob(str(tmp_path / "*.json"))
        try:
            with open(result_path) as f:
                data = json.load(f)
            assert len(data) == 2
        finally:
            os.remove(result_path)


class TestTypeLabel:
    def test_none(self):
        assert _type_label(None) == "null"

    def test_bool(self):
        assert _type_label(True) == "bool"

    def test_int(self):
        assert _type_label(42) == "int"

    def test_float(self):
        assert _type_label(3.14) == "float"

    def test_str(self):
        assert _type_label("hello") == "str"

    def test_list(self):
        assert _type_label([1, 2, 3]) == "array[3]"

    def test_dict(self):
        assert _type_label({"a": 1}) == "object{1}"

    def test_empty_list(self):
        assert _type_label([]) == "array[0]"


class TestPreviewValue:
    def test_string(self):
        assert _preview_value("hello") == '"hello"'

    def test_int(self):
        assert _preview_value(42) == "42"

    def test_none(self):
        assert _preview_value(None) == "null"

    def test_bool(self):
        assert _preview_value(True) == "true"

    def test_nested_dict(self):
        assert _preview_value({"a": 1}) == ""

    def test_simple_list(self):
        result = _preview_value([1, 2, 3])
        assert "1" in result


class TestValidateInputFile:
    def test_nonexistent_file(self):
        with pytest.raises(FileNotFoundError):
            validate_input_file("/nonexistent/file.json")

    def test_directory(self, tmp_path):
        with pytest.raises(FileNotFoundError, match="not a file"):
            validate_input_file(str(tmp_path))

    def test_empty_file(self, tmp_path):
        f = tmp_path / "empty.json"
        f.write_text("")
        with pytest.raises(ValueError, match="empty"):
            validate_input_file(str(f))

    def test_valid_file(self, tmp_path):
        f = tmp_path / "data.json"
        f.write_text('[{"a":1}]')
        validate_input_file(str(f))  # should not raise


class TestYamlScalar:
    def test_none(self):
        assert _yaml_scalar(None) == "null"

    def test_true(self):
        assert _yaml_scalar(True) == "true"

    def test_false(self):
        assert _yaml_scalar(False) == "false"

    def test_int(self):
        assert _yaml_scalar(42) == "42"

    def test_float(self):
        assert _yaml_scalar(3.14) == "3.14"

    def test_simple_string(self):
        assert _yaml_scalar("hello") == "hello"

    def test_string_with_colon(self):
        result = _yaml_scalar("key: value")
        assert result.startswith('"')

    def test_string_with_hash(self):
        result = _yaml_scalar("has # comment")
        assert result.startswith('"')


class TestYamlDump:
    def test_dict(self):
        lines = []
        _yaml_dump({"a": 1, "b": "hello"}, lines, 0)
        assert "a: 1" in lines
        assert "b: hello" in lines

    def test_list_of_scalars(self):
        lines = []
        _yaml_dump([1, 2, 3], lines, 0)
        assert "- 1" in lines
        assert "- 2" in lines

    def test_nested_dict(self):
        lines = []
        _yaml_dump({"outer": {"inner": 42}}, lines, 0)
        assert "outer:" in lines

    def test_list_of_dicts(self):
        lines = []
        _yaml_dump([{"a": 1}, {"a": 2}], lines, 0)
        assert "- a: 1" in lines
        assert "- a: 2" in lines


class TestJsonToYamlSimple:
    def test_basic_object(self):
        result = _json_to_yaml_simple('{"name": "Alice"}')
        assert "name: Alice" in result

    def test_array_of_objects(self):
        result = _json_to_yaml_simple('[{"a": 1}, {"a": 2}]')
        assert "- a: 1" in result
        assert "- a: 2" in result

    def test_invalid_json(self):
        result = _json_to_yaml_simple("not json")
        assert result == "not json"


class TestJsonToYaml:
    def test_empty_array(self):
        result = _json_to_yaml("[]")
        assert result is not None

    def test_deeply_nested(self):
        data = {"a": {"b": {"c": {"d": 1}}}}
        result = _json_to_yaml(json.dumps(data))
        assert "d: 1" in result

    def test_mixed_types_in_list(self):
        result = _json_to_yaml('[1, "two", null, true]')
        assert "1" in result
        assert "two" in result


class TestExplainQuery:
    def test_contains_all_sections(self):
        compiled = compile_query("select name, age if age > 30 sort age desc limit 5")
        output = _explain_query(compiled)
        assert "Query:" in output
        assert "Fields:" in output
        assert "Condition:" in output
        assert "Sort:" in output
        assert "Limit:" in output
        assert "Generated jq:" in output

    def test_distinct_shown(self):
        compiled = compile_query("select distinct city")
        output = _explain_query(compiled)
        assert "Distinct:" in output

    def test_from_shown(self):
        compiled = compile_query("select name from products")
        output = _explain_query(compiled)
        assert "From:" in output

    def test_aggregation_field(self):
        compiled = compile_query("select count(*) as total")
        output = _explain_query(compiled)
        assert "count(*)" in output

    def test_function_field(self):
        compiled = compile_query("select upper(name) as n")
        output = _explain_query(compiled)
        assert "upper(name)" in output

    def test_expression_field(self):
        compiled = compile_query("select age + 10 as older")
        output = _explain_query(compiled)
        assert "older" in output
