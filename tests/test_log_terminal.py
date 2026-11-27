import json
from pathlib import Path
import sys

import pytest

from jonq.main import main


FIXTURES = Path(__file__).parent / "json_test_files"
CONNECTIONS = ["connections", str(FIXTURES / "zeek_conn.ndjson")]
TRIAGE = ["triage", str(FIXTURES / "suricata_eve.ndjson")]


@pytest.mark.parametrize(("argv", "phrases"), [
    (["--help"], ("jonq triage eve.ndjson", "jonq connections conn.ndjson --scan-leads")),
    (
        ["triage", "--help"],
        ("event_type=alert", "alert.signature_id", "event_type=firewall", "piped stdin by default"),
    ),
    (
        ["connections", "--help"],
        (
            "Zeek conn.log in JSON mode",
            "event_type=flow",
            "dest_ip",
            "default: 60",
            "sed -n '1p' tests/json_test_files/zeek_conn.ndjson",
        ),
    ),
])
def test_log_help_shows_input_formats_and_examples(argv, phrases, capsys):
    with pytest.raises(SystemExit) as exit_info:
        main(argv)

    captured = capsys.readouterr()
    assert exit_info.value.code == 0
    assert captured.err == ""
    text = " ".join(captured.out.split())
    for phrase in phrases:
        assert phrase in text


def simulate_terminal(monkeypatch):
    monkeypatch.setattr(sys.stdout, "isatty", lambda: True)
    monkeypatch.setenv("TERM", "xterm-256color")
    monkeypatch.delenv("NO_COLOR", raising=False)


@pytest.mark.parametrize("argv", [CONNECTIONS, [*CONNECTIONS, "--scan-leads"], TRIAGE])
def test_log_reports_use_color_in_a_terminal(argv, capsys, monkeypatch):
    simulate_terminal(monkeypatch)

    main(argv)

    assert "\x1b[" in capsys.readouterr().out


@pytest.mark.parametrize("reason", ["flag", "environment", "dumb terminal", "redirected"])
def test_log_reports_honor_plain_text_settings(reason, capsys, monkeypatch):
    simulate_terminal(monkeypatch)
    flags = []
    if reason == "flag":
        flags.append("--no-color")
    elif reason == "environment":
        monkeypatch.setenv("NO_COLOR", "1")
    elif reason == "dumb terminal":
        monkeypatch.setenv("TERM", "dumb")
    else:
        monkeypatch.setattr(sys.stdout, "isatty", lambda: False)

    main([*CONNECTIONS, *flags])

    output = capsys.readouterr().out
    assert "IP conversations" in output
    assert "\x1b[" not in output


def test_log_report_json_stays_machine_readable_in_a_terminal(capsys, monkeypatch):
    simulate_terminal(monkeypatch)

    main([*TRIAGE, "--format", "json"])

    output = capsys.readouterr().out
    assert "\x1b[" not in output
    assert json.loads(output)["events"] == 8
