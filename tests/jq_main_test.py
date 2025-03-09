import pytest
from unittest.mock import patch
from jonq.main import main

def test_main_success(tmp_path, capsys):
    json_file = tmp_path / "test.json"
    json_file.write_text('{"name": "Alice", "age": 30}')
    with patch("sys.argv", ["jonq", str(json_file), "select name"]):
        with patch("jonq.main.parse_query", return_value=(["name"], None, None, None, None, None)):
            with patch("jonq.main.generate_jq_filter", return_value=".name"):
                with patch("jonq.main.run_jq", return_value=('"Alice"\n', "")):
                    main()
    captured = capsys.readouterr()
    assert '"Alice"' in captured.out
    assert captured.err == ""

def test_main_file_not_found(capsys):
    with patch("sys.argv", ["jonq", "nonexistent.json", "select name"]):
        with pytest.raises(SystemExit) as excinfo:
            main()
        assert excinfo.value.code == 1
    captured = capsys.readouterr()
    assert "File Error: JSON file 'nonexistent.json' not found" in captured.out

def test_main_permission_denied(tmp_path, capsys):
    json_file = tmp_path / "test.json"
    json_file.write_text('{"name": "Alice"}')
    with patch("sys.argv", ["jonq", str(json_file), "select name"]):
        with patch("os.access", return_value=False):
            with pytest.raises(SystemExit) as excinfo:
                main()
            assert excinfo.value.code == 1
    captured = capsys.readouterr()
    assert "Permission Error: Cannot read JSON file" in captured.out

def test_main_empty_file(tmp_path, capsys):
    empty_file = tmp_path / "empty.json"
    empty_file.write_text("")
    with patch("sys.argv", ["jonq", str(empty_file), "select name"]):
        with pytest.raises(SystemExit) as excinfo:
            main()
        assert excinfo.value.code == 1
    captured = capsys.readouterr()
    assert "Query Error: JSON file" in captured.out
    assert "is empty" in captured.out

def test_main_invalid_query(tmp_path, capsys):
    json_file = tmp_path / "test.json"
    json_file.write_text('{"name": "Alice"}')
    with patch("sys.argv", ["jonq", str(json_file), "invalid"]):
        with pytest.raises(SystemExit) as excinfo:
            main()
        assert excinfo.value.code == 1
    captured = capsys.readouterr()
    assert "Query Error:" in captured.out

def test_main_jq_execution_error(tmp_path, capsys):
    json_file = tmp_path / "test.json"
    json_file.write_text('{"name": "Alice"}')
    with patch("sys.argv", ["jonq", str(json_file), "select name"]):
        with patch("jonq.main.parse_query", return_value=(["name"], None, None, None, None, None)):
            with patch("jonq.main.generate_jq_filter", return_value=".name"):
                with patch("jonq.main.run_jq", side_effect=RuntimeError("JQ error")):
                    with pytest.raises(SystemExit) as excinfo:
                        main()
                    assert excinfo.value.code == 1
    captured = capsys.readouterr()
    assert "Execution Error: JQ error" in captured.out