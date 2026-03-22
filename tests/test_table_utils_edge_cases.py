import json
from jonq.table_utils import (
    json_to_table,
    render_table,
    _format_value,
    _truncate,
    _collect_headers,
    _rows_to_strings,
    _compute_col_widths,
    _shrink_columns_if_needed,
    _build_row_line,
)


class TestFormatValue:
    def test_none(self):
        assert _format_value(None) == "null"

    def test_true(self):
        assert _format_value(True) == "true"

    def test_false(self):
        assert _format_value(False) == "false"

    def test_int(self):
        assert _format_value(42) == "42"

    def test_float(self):
        assert _format_value(3.14) == "3.14"

    def test_string(self):
        assert _format_value("hello") == "hello"

    def test_list(self):
        assert _format_value([1, 2]) == "[1, 2]"

    def test_dict(self):
        result = _format_value({"a": 1})
        assert '"a"' in result

    def test_zero(self):
        assert _format_value(0) == "0"

    def test_empty_string(self):
        assert _format_value("") == ""


class TestTruncate:
    def test_short_string(self):
        assert _truncate("hi", 10) == "hi"

    def test_exact_width(self):
        assert _truncate("hello", 5) == "hello"

    def test_over_width(self):
        result = _truncate("hello world", 5)
        assert len(result) == 5
        assert result.endswith("\u2026")

    def test_width_one(self):
        result = _truncate("hello", 1)
        assert result == "\u2026"


class TestCollectHeaders:
    def test_single_row(self):
        headers = _collect_headers([{"a": 1, "b": 2}])
        assert headers == ["a", "b"]

    def test_multiple_rows_different_keys(self):
        headers = _collect_headers([{"a": 1}, {"b": 2}, {"a": 3, "c": 4}])
        assert "a" in headers
        assert "b" in headers
        assert "c" in headers

    def test_preserves_order(self):
        headers = _collect_headers([{"z": 1, "a": 2}])
        assert headers == ["z", "a"]

    def test_deduplicates(self):
        headers = _collect_headers([{"a": 1}, {"a": 2}])
        assert headers == ["a"]


class TestRowsToStrings:
    def test_basic(self):
        rows = [{"a": 1, "b": "hi"}]
        result = _rows_to_strings(rows, ["a", "b"])
        assert result == [["1", "hi"]]

    def test_missing_key(self):
        rows = [{"a": 1}]
        result = _rows_to_strings(rows, ["a", "b"])
        assert result == [["1", "null"]]

    def test_bool_values(self):
        rows = [{"a": True, "b": False}]
        result = _rows_to_strings(rows, ["a", "b"])
        assert result == [["true", "false"]]


class TestComputeColWidths:
    def test_header_wider(self):
        widths = _compute_col_widths(["longheader"], [["x"]])
        assert widths == [10]

    def test_cell_wider(self):
        widths = _compute_col_widths(["a"], [["longvalue"]])
        assert widths == [9]

    def test_multiple_rows(self):
        widths = _compute_col_widths(["a"], [["x"], ["longer"]])
        assert widths == [6]


class TestShrinkColumns:
    def test_no_shrink_needed(self):
        widths = _shrink_columns_if_needed([5, 5], 100)
        assert widths == [5, 5]

    def test_single_column_never_shrinks(self):
        widths = _shrink_columns_if_needed([200], 50)
        assert widths == [200]

    def test_shrinks_when_too_wide(self):
        widths = _shrink_columns_if_needed([50, 50, 50], 30)
        for w in widths:
            assert w <= 50


class TestBuildRowLine:
    def test_basic(self):
        line = _build_row_line(["a", "b"], [5, 5])
        assert "|" in line
        assert "a" in line
        assert "b" in line

    def test_truncates_long_cell(self):
        line = _build_row_line(["hello world"], [5])
        assert "\u2026" in line


class TestJsonToTable:
    def test_invalid_json(self):
        assert json_to_table("not json") == "not json"

    def test_scalar_json(self):
        assert json_to_table("42") == "42"

    def test_array_of_scalars(self):
        result = json_to_table("[1, 2, 3]")
        assert result == "[1, 2, 3]"

    def test_empty_object_in_array(self):
        result = json_to_table("[{}]")
        # empty object has no headers, so render_table returns ""
        assert result == ""

    def test_mixed_keys_across_rows(self):
        data = json.dumps([{"a": 1}, {"b": 2}])
        table = json_to_table(data)
        assert "a" in table
        assert "b" in table
        assert "null" in table

    def test_unicode_values(self):
        data = json.dumps([{"name": "caf\u00e9"}])
        table = json_to_table(data)
        assert "caf\u00e9" in table

    def test_wide_column_truncation(self):
        data = json.dumps([{"x": "a" * 200, "y": "b" * 200}])
        table = json_to_table(data, max_width=40)
        assert "\u2026" in table


class TestRenderTable:
    def test_empty_rows(self):
        assert render_table([]) == ""

    def test_color_mode(self):
        table = render_table([{"a": 1}], color=True)
        assert "\033[" in table

    def test_no_color_mode(self):
        table = render_table([{"a": 1}], color=False)
        assert "\033[" not in table

    def test_many_rows(self):
        rows = [{"x": i} for i in range(100)]
        table = render_table(rows)
        lines = table.split("\n")
        # header + separator + 100 rows
        assert len(lines) == 102 
