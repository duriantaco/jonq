import pytest
from unittest.mock import patch, AsyncMock
from jonq.main import main
from jonq.constants import VERSION


def test_main_success(tmp_path, capsys):
    json_file = tmp_path / "test.json"
    json_file.write_text('[{"name": "Alice", "age": 30}]')
    with patch("sys.argv", ["jonq", str(json_file), "select name"]):
        main()
    captured = capsys.readouterr()
    assert "Alice" in captured.out


def test_main_with_from_clause(tmp_path, capsys):
    json_file = tmp_path / "test.json"
    json_file.write_text('{"products": [{"type": "Software", "customers": [1, 2, 3]}]}')
    with patch("sys.argv", ["jonq", str(json_file), "select type from products"]):
        main()
    captured = capsys.readouterr()
    assert "Software" in captured.out


def test_main_file_not_found(capsys):
    with patch("sys.argv", ["jonq", "nonexistent.json", "select name"]):
        with pytest.raises(SystemExit) as excinfo:
            main()
        assert excinfo.value.code == 1
    captured = capsys.readouterr()
    assert "not found" in captured.out or "not a file" in captured.out


def test_main_empty_file(tmp_path, capsys):
    empty_file = tmp_path / "empty.json"
    empty_file.write_text("")
    with patch("sys.argv", ["jonq", str(empty_file), "select name"]):
        with pytest.raises(SystemExit) as excinfo:
            main()
        assert excinfo.value.code == 1
    captured = capsys.readouterr()
    assert "empty" in captured.out


def test_main_invalid_query(tmp_path, capsys):
    json_file = tmp_path / "test.json"
    json_file.write_text('{"name": "Alice"}')
    with patch("sys.argv", ["jonq", str(json_file), "invalid"]):
        with pytest.raises(SystemExit) as excinfo:
            main()
        assert excinfo.value.code == 1
    captured = capsys.readouterr()
    assert "select" in captured.out.lower()


def test_main_jq_execution_error(tmp_path, capsys):
    json_file = tmp_path / "test.json"
    json_file.write_text('{"name": "Alice"}')
    with patch("sys.argv", ["jonq", str(json_file), "select name"]):
        with patch("jonq.main.execute_async", new_callable=AsyncMock, side_effect=RuntimeError("JQ error")):
            with pytest.raises(SystemExit) as excinfo:
                main()
            assert excinfo.value.code == 1
    captured = capsys.readouterr()
    assert "error" in captured.out.lower() or "Error" in captured.out


def test_main_version(capsys):
    with pytest.raises(SystemExit) as excinfo:
        main(["--version"])
    assert excinfo.value.code == 0

    captured = capsys.readouterr()
    assert VERSION in captured.out


def test_main_schema_preview_shows_nested_paths(tmp_path, capsys):
    json_file = tmp_path / "nested.json"
    json_file.write_text(
        '{"user":{"name":"Alice","address":{"city":"New York"}},"orders":[{"id":1,"price":1200}]}'
    )

    with patch("sys.argv", ["jonq", str(json_file)]):
        main()

    captured = capsys.readouterr()
    assert "Paths:" in captured.out
    assert "user.name" in captured.out
    assert "user.address.city" in captured.out
    assert "orders[]" in captured.out
    assert "orders[].price" in captured.out
