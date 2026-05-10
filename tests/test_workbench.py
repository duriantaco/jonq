import json
from unittest.mock import patch

import pytest

from jonq.main import main
from jonq.workbench import (
    build_profile,
    compare_profiles,
    parse_config_text,
    run_profile_check,
)


def test_profile_tracks_missing_null_and_type_conflicts(tmp_path):
    source = tmp_path / "users.json"
    source.write_text(
        json.dumps(
            [
                {"id": 1, "email": "a@example.com", "age": 30},
                {"id": 2, "email": None},
                {"id": 3, "age": "unknown"},
            ]
        )
    )

    profile = build_profile(str(source))

    assert profile.records == 3
    assert profile.fields["email"].present == 2
    assert profile.fields["email"].null == 1
    assert profile.fields["email"].missing(profile.records) == 1
    assert set(profile.fields["age"].types) == {"number", "string"}


def test_profile_diff_reports_added_removed_and_type_changes(tmp_path):
    old = tmp_path / "old.json"
    new = tmp_path / "new.json"
    old.write_text(json.dumps([{"id": 1, "gone": True}]))
    new.write_text(json.dumps([{"id": "1", "email": "a@example.com"}]))

    diff = compare_profiles(build_profile(str(old)), build_profile(str(new)))

    assert diff.has_changes()
    assert diff.added == ["email"]
    assert diff.removed == ["gone"]
    assert diff.type_changed == [("id", {"number"}, {"string"})]


def test_check_reports_contract_failures(tmp_path):
    source = tmp_path / "users.json"
    source.write_text(json.dumps([{"id": 1, "email": None}, {"id": 2}]))

    profile = build_profile(str(source))
    result = run_profile_check(
        profile,
        {
            "require": ["id", "email"],
            "types": {"id": "string"},
            "no_null": ["email"],
        },
        "user_contract",
    )

    assert not result.ok
    assert "Required field 'email' is missing" in "\n".join(result.failures)
    assert "expected type string" in "\n".join(result.failures)
    assert "is null" in "\n".join(result.failures)


def test_parse_simple_jonq_yaml_config():
    config = parse_config_text(
        """
queries:
  users:
    source: users.json
    query: select id, email
    format: table
checks:
  user_contract:
    source: users.json
    require:
      - id
      - email
    types:
      id: number
      email: string
    no_null: [id, email]
    min_count: 1
"""
    )

    assert config["queries"]["users"]["query"] == "select id, email"
    assert config["checks"]["user_contract"]["require"] == ["id", "email"]
    assert config["checks"]["user_contract"]["types"]["id"] == "number"
    assert config["checks"]["user_contract"]["no_null"] == ["id", "email"]


def test_cli_profile_command_outputs_profile(tmp_path, capsys):
    source = tmp_path / "users.json"
    source.write_text(json.dumps([{"id": 1, "email": "a@example.com"}]))

    with patch("sys.argv", ["jonq", "profile", str(source)]):
        main()

    captured = capsys.readouterr()
    assert "Root: array (1 record)" in captured.out
    assert "email" in captured.out
    assert "string" in captured.out


def test_cli_named_check_uses_relative_config_paths(tmp_path, capsys):
    source = tmp_path / "users.json"
    config = tmp_path / "jonq.yaml"
    source.write_text(json.dumps([{"id": 1, "email": "a@example.com"}]))
    config.write_text(
        """
checks:
  user_contract:
    source: users.json
    require:
      - id
      - email
    types:
      id: number
      email: string
    no_null:
      - id
      - email
"""
    )

    with patch("sys.argv", ["jonq", "check", "user_contract", "--config", str(config)]):
        main()

    captured = capsys.readouterr()
    assert "Check user_contract: PASS" in captured.out
    assert str(source) in captured.out


def test_cli_run_named_query_from_config(tmp_path, capsys):
    source = tmp_path / "users.json"
    config = tmp_path / "jonq.yaml"
    source.write_text(
        json.dumps(
            [
                {"id": 1, "email": "a@example.com"},
                {"id": 2, "email": "b@example.com"},
            ]
        )
    )
    config.write_text(
        """
queries:
  emails:
    source: users.json
    query: select email
    format: json
"""
    )

    with patch("sys.argv", ["jonq", "run", "emails", "--config", str(config), "-r"]):
        main()

    captured = capsys.readouterr()
    assert captured.out == "a@example.com\nb@example.com\n"


def test_cli_inline_check_exits_nonzero_on_failure(tmp_path, capsys):
    source = tmp_path / "users.json"
    source.write_text(json.dumps([{"id": 1}]))

    with patch("sys.argv", ["jonq", "check", str(source), "--require", "email"]):
        with pytest.raises(SystemExit) as excinfo:
            main()

    assert excinfo.value.code == 1
    captured = capsys.readouterr()
    assert "Check inline: FAIL" in captured.out
    assert "Required field 'email' was not found." in captured.out
