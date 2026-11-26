import csv
import io
import json
from pathlib import Path
import shlex
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
PEOPLE = [{"name": "Alice", "age": 32}, {"name": "Bob", "age": 25}]
PEOPLE_JSON = json.dumps(PEOPLE)
PEOPLE_NDJSON = "\n".join(map(json.dumps, PEOPLE)) + "\n"


def run_jonq(*arguments, stdin=""):
    return subprocess.run(
        [sys.executable, "-B", "-m", "jonq", *arguments],
        cwd=ROOT,
        input=stdin,
        text=True,
        capture_output=True,
        timeout=10,
    )


@pytest.mark.parametrize("source", [(), ("-",)])
def test_inspect_piped_json_without_a_query(source):
    result = run_jonq(*source, stdin=PEOPLE_JSON)

    assert result.returncode == 0, result.stderr
    assert result.stderr == ""
    assert "Root:" in result.stdout
    assert "name" in result.stdout
    assert "Alice" in result.stdout


@pytest.mark.parametrize("source", [(), ("-",)])
def test_query_ndjson_on_stdin(source):
    result = run_jonq("--ndjson", *source, "select name", stdin=PEOPLE_NDJSON)

    assert result.returncode == 0, result.stderr
    assert result.stderr == ""
    assert json.loads(result.stdout) == [{"name": "Alice"}, {"name": "Bob"}]


def test_inspect_ndjson_file_without_a_query(tmp_path):
    source = tmp_path / "people.ndjson"
    source.write_text(PEOPLE_NDJSON, encoding="utf-8")

    result = run_jonq(str(source))

    assert result.returncode == 0, result.stderr
    assert result.stderr == ""
    assert "Root:" in result.stdout
    assert "name" in result.stdout
    assert "Alice" in result.stdout


def test_missing_file_keeps_the_user_supplied_path_in_the_error(tmp_path):
    source = tmp_path / "missing.json"

    result = run_jonq(str(source))

    assert result.returncode == 1
    assert str(source) in result.stderr
    assert result.stdout == ""


def test_stdin_typo_suggestion_can_be_run_with_the_same_input():
    result = run_jonq("select nmae", stdin=PEOPLE_JSON)

    assert result.returncode == 1
    assert result.stdout == ""
    assert "nmae" in result.stderr
    commands = [line.removeprefix("Try: ") for line in result.stderr.splitlines() if line.startswith("Try: ")]
    assert len(commands) == 1, result.stderr
    command, *arguments = shlex.split(commands[0])
    assert command == "jonq"

    repaired = run_jonq(*arguments, stdin=PEOPLE_JSON)

    assert repaired.returncode == 0, repaired.stderr
    assert json.loads(repaired.stdout) == [{"name": "Alice"}, {"name": "Bob"}]


@pytest.mark.parametrize(
    ("data", "source_clause", "condition", "typo", "repair"),
    [
        (
            [{"name": "A", "orders": [{"price": 9}]}, {"name": "B", "orders": [{"price": 2}]}],
            "",
            "orders[0].price > 5",
            "orders[0].prcie",
            "orders[0].price",
        ),
        (
            [{"name": "A", "matrix": [[{"value": 4, "comparison": 3}]]}, {"name": "B", "matrix": []}],
            "",
            "matrix[0][0].value > matrix[0][0].comparison",
            "matrix[0][0].compariosn",
            "matrix[0][0].comparison",
        ),
        (
            {"products": [
                {"name": "A", "versions": [{"pricing": {"monthly": 900}}]},
                {"name": "B", "versions": [{"pricing": {"monthly": 20}}]},
            ]},
            " from products[]",
            "versions[].pricing.monthly > 200",
            "versions[].pricing.montly",
            "versions[].pricing.monthly",
        ),
    ],
)
def test_array_paths_in_filters_validate_and_get_runnable_typo_repairs(
    data, source_clause, condition, typo, repair
):
    source = json.dumps(data)
    query = f"select name{source_clause} where {condition}"
    result = run_jonq(query, stdin=source)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == [{"name": "A"}]

    invalid = run_jonq(query.replace(repair, typo), stdin=source)
    assert invalid.returncode == 1
    assert invalid.stdout == ""
    assert f"Unknown field(s): {typo}" in invalid.stderr
    assert f"{typo} -> {repair}" in invalid.stderr
    suggestion = next(line for line in invalid.stderr.splitlines() if line.startswith("Try: "))
    _, *arguments = shlex.split(suggestion.removeprefix("Try: "))
    fixed = run_jonq(*arguments, stdin=source)
    assert fixed.returncode == 0, fixed.stderr
    assert json.loads(fixed.stdout) == [{"name": "A"}]


def test_interactive_mode_runs_the_first_query(tmp_path):
    source = tmp_path / "people.json"
    source.write_text(PEOPLE_JSON, encoding="utf-8")

    # Exercise the CLI without loading or writing the developer's readline history.
    script = "import runpy, sys; sys.modules['readline'] = None; runpy.run_module('jonq', run_name='__main__')"
    result = subprocess.run(
        [sys.executable, "-B", "-c", script, "-i", str(source)],
        cwd=ROOT,
        input="select name\nquit\n",
        text=True,
        capture_output=True,
        timeout=10,
    )

    assert result.returncode == 0, result.stderr
    assert result.stderr == ""
    assert "Alice" in result.stdout
    assert "Bob" in result.stdout


def test_raw_output_preserves_value_whitespace():
    data = json.dumps([{"name": "  Alice"}, {"name": "Bob  "}])

    result = run_jonq("select name", "-r", stdin=data)

    assert result.returncode == 0, result.stderr
    assert result.stdout == "  Alice\nBob  \n"


def test_raw_output_keeps_empty_values_and_trailing_newlines():
    data = json.dumps([{"name": "Alice\n"}, {"name": ""}])

    result = run_jonq("select name", "-r", stdin=data)

    assert result.returncode == 0, result.stderr
    assert result.stdout == "Alice\n\n\n"


def test_follow_csv_writes_one_header_and_reports_invalid_lines():
    data = '{"name":"Alice","age":32}\n{},{}\n{"name":"Bob","age":25}\n'

    result = run_jonq("--follow", "select name, age", "--format", "csv", stdin=data)

    assert result.returncode == 1
    assert "Line 2" in result.stderr
    assert list(csv.reader(io.StringIO(result.stdout))) == [
        ["age", "name"], ["32", "Alice"], ["25", "Bob"],
    ]


def test_follow_rejects_aggregate_expressions():
    result = run_jonq("--follow", "select max(age) - min(age) as age_range", stdin=PEOPLE_NDJSON)

    assert result.returncode == 1
    assert result.stdout == ""
    assert "row-wise query" in result.stderr


def test_inspect_ndjson_only_reads_the_sample(tmp_path):
    source = tmp_path / "events.ndjson"
    source.write_text('{"name":"Alice"}\n' * 30 + 'invalid line\n', encoding="utf-8")

    inspected = run_jonq(str(source))
    queried = run_jonq(str(source), "select name")

    assert inspected.returncode == 0, inspected.stderr
    assert "sampled 25 items" in inspected.stdout
    assert queried.returncode == 1
    assert queried.stdout == ""
    assert "Invalid NDJSON at line 31" in queried.stderr


@pytest.mark.parametrize("preexisting", [False, True])
def test_successful_empty_csv_writes_the_requested_output_file(tmp_path, preexisting):
    output = tmp_path / "result.csv"
    if preexisting:
        output.write_text("stale\n", encoding="utf-8")

    result = run_jonq("select name where age > 100", "--format", "csv", "--out", str(output), stdin=PEOPLE_JSON)

    assert result.returncode == 0, result.stderr
    assert result.stdout == ""
    assert output.read_bytes() == b""


def inspect_commands(source):
    result = run_jonq(str(source))
    assert result.returncode == 0, result.stderr
    commands = [
        shlex.split(line.strip())
        for line in result.stdout.splitlines()
        if line.strip().startswith("jonq ")
    ]
    assert commands, result.stdout
    return commands


def test_inspect_prioritizes_a_runnable_query_for_wrapped_rows(tmp_path):
    source = tmp_path / "api response.json"
    source.write_text(json.dumps({"meta": {"total": 2}, "users": PEOPLE}), encoding="utf-8")

    first, *_ = inspect_commands(source)

    assert any("from users" in argument for argument in first), first
    result = run_jonq(*first[1:])
    assert result.returncode == 0, result.stderr
    assert "Alice" in result.stdout
    assert "Bob" in result.stdout


def test_inspect_suggestion_queries_literal_dotted_keys(tmp_path):
    source = tmp_path / "record.json"
    source.write_text(
        json.dumps([{"id.orig_h": "192.0.2.10", "id.resp_h": "198.51.100.12"}]),
        encoding="utf-8",
    )

    first, *_ = inspect_commands(source)
    result = run_jonq(*first[1:])

    assert result.returncode == 0, result.stderr
    assert "192.0.2.10" in result.stdout
    assert "198.51.100.12" in result.stdout


def test_inspect_boolean_filter_suggestion_handles_quoted_keys(tmp_path):
    source = tmp_path / "people.json"
    source.write_text(
        json.dumps([
            {"display name": "Alice", "is-active": True},
            {"display name": "Bob", "is-active": False},
        ]),
        encoding="utf-8",
    )

    filtered = [command for command in inspect_commands(source) if any(" where " in value for value in command)]
    assert len(filtered) == 1, filtered
    result = run_jonq(*filtered[0][1:])

    assert result.returncode == 0, result.stderr
    assert "Alice" in result.stdout
    assert "Bob" not in result.stdout
