import json
from pathlib import Path
import shlex
import subprocess
import sys

import pytest

from jonq.main import main


def run_jonq(*args, data=""):
    return subprocess.run(
        [sys.executable, "-B", "-m", "jonq", *args],
        cwd=Path(__file__).resolve().parents[1],
        input=data, capture_output=True, text=True, timeout=15,
    )


def repair_command(result):
    assert result.returncode == 1
    assert result.stdout == ""
    suggestion = next(line for line in result.stderr.splitlines() if line.startswith("Try: "))
    command, *args = shlex.split(suggestion.removeprefix("Try: "))
    assert command == "jonq"
    return args


def test_typo_repair_preserves_quoted_values_and_aliases():
    data = '[{"city":"cty"},{"city":"city"}]'
    invalid = run_jonq("select cty as cty where cty = 'cty'", data=data)

    args = repair_command(invalid)
    assert args == ["-", "select city as cty where city = 'cty'"]
    repaired = run_jonq(*args, data=data)
    assert repaired.returncode == 0, repaired.stderr
    assert json.loads(repaired.stdout) == [{"cty": "cty"}]


def test_typo_repair_distinguishes_quoted_source_and_field():
    data = '{"api.v1":[{"name":"Alice"}]}'
    invalid = run_jonq('select nmae from "api.v1"', data=data)

    args = repair_command(invalid)
    assert args == ["-", 'select name from "api.v1"']
    repaired = run_jonq(*args, data=data)
    assert repaired.returncode == 0, repaired.stderr
    assert json.loads(repaired.stdout) == [{"name": "Alice"}]


def test_typo_repair_preserves_function_argument_spacing():
    data = '[{"age":10},{"age":30}]'
    invalid = run_jonq("select avg ( ag ) as mean", data=data)
    args = repair_command(invalid)
    assert args == ["-", "select avg ( age ) as mean"]
    repaired = run_jonq(*args, data=data)
    assert repaired.returncode == 0, repaired.stderr
    assert json.loads(repaired.stdout) == {"mean": 20}


def test_stream_schema_validates_fields_that_appear_in_later_chunks(tmp_path):
    source = tmp_path / "rows.json"
    rows = [{"id": i} for i in range(1_050)] + [{"id": 1_050, "score": 9}]
    source.write_text(json.dumps(rows), encoding="utf-8")

    result = run_jonq(str(source), "select id where score > 5", "--stream")
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == [{"id": 1_050}]

    invalid = run_jonq(str(source), "select id where scor > 5", "--stream")
    args = repair_command(invalid)
    assert args == [str(source), "select id where score > 5", "--stream"]


def test_streaming_never_loads_an_entire_json_file(tmp_path, monkeypatch, capsys):
    source = tmp_path / "rows.json"
    source.write_text('[{"active":false}]', encoding="utf-8")

    def fail_on_full_document(*args, **kwargs):
        raise AssertionError("streaming must not call json.load")

    monkeypatch.setattr(json, "load", fail_on_full_document)
    main([str(source), "select active where active = true", "--stream"])

    result = capsys.readouterr()
    assert result.out == "[]\n"
    assert result.err == ""


@pytest.mark.parametrize("output", [False, True])
def test_stream_does_not_publish_partial_rows_on_invalid_input(tmp_path, output):
    source = tmp_path / "rows.json"
    source.write_text(
        json.dumps([{"id": i} for i in range(1_050)]) + "\n[{\"id\":1050}]",
        encoding="utf-8",
    )
    destination = tmp_path / "result.json"
    destination.write_bytes(b"previous result\n")
    flags = ["--out", str(destination)] if output else []

    result = run_jonq(str(source), "select id", "--stream", *flags)

    assert result.returncode == 1
    assert result.stdout == ""
    assert "Invalid JSON" in result.stderr
    assert destination.read_bytes() == b"previous result\n"


@pytest.mark.parametrize("flags", [["--pretty"], ["--format", "jsonl"], ["--raw"]])
def test_streamed_output_matches_batch_across_chunk_boundaries(flags):
    data = json.dumps([{"name": "  A\n"}, {"name": ""}] * 550, ensure_ascii=False)

    batch = run_jonq("-", "select name", "--limit", "1005", *flags, data=data)
    streamed = run_jonq("-", "select name", "--stream", "--limit", "1005", *flags, data=data)

    assert batch.returncode == streamed.returncode == 0, streamed.stderr or batch.stderr
    assert batch.stdout == streamed.stdout
