import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

import pytest

from jonq.triage import AlertGroup, DenialGroup, TriageReport, format_triage


def run_triage(*args, data=b""):
    return subprocess.run(
        [sys.executable, "-B", "-m", "jonq", "triage", *args],
        input=data,
        capture_output=True,
        env={**os.environ, "PATH": ""},
        timeout=10,
    )


def encode_ndjson(events):
    return b"".join(json.dumps(event).encode("utf-8") + b"\n" for event in events)


def test_triage_summarizes_recorded_alerts_without_jq():
    source = Path(__file__).parent / "json_test_files" / "suricata_eve.ndjson"

    result = run_triage(str(source), "--format", "json")

    assert result.returncode == 0
    assert result.stderr == b""
    report = json.loads(result.stdout)
    assert report == {
        "events": 8,
        "invalid_lines": 0,
        "min_denials": 5,
        "denied_events": 0,
        "alerts": [
            {
                "signature_id": 900001, "signature": "Synthetic policy alert", "count": 2,
                "examples": [
                    {"line": 6, "timestamp": "2026-01-01T12:00:06.000000+0000"},
                    {"line": 7, "timestamp": "2026-01-01T12:00:07.000000+0000"},
                ],
            },
            {
                "signature_id": 900002, "signature": "Synthetic protocol alert", "count": 1,
                "examples": [{"line": 8, "timestamp": "2026-01-01T12:00:08.000000+0000"}],
            },
        ],
        "repeated_denials": [],
    }
    source_lines = source.read_text(encoding="utf-8").splitlines()
    for group in report["alerts"]:
        for example in group["examples"]:
            event = json.loads(source_lines[example["line"] - 1])
            assert event["alert"]["signature_id"] == group["signature_id"]
            assert event["timestamp"] == example["timestamp"]

    text = run_triage(str(source))

    assert text.returncode == 0
    output = text.stdout.decode("utf-8")
    assert "3 recorded alert events across 2 alert types" in output
    assert output.index("3 recorded alert events") < output.index("Input line 6") < output.index("8 valid events")
    assert "Input line 6 · 2026-01-01T12:00:06.000000+0000" in output
    assert "Input line 7" not in output
    assert "Input line 8 · 2026-01-01T12:00:08.000000+0000" in output


@pytest.mark.skipif(os.name != "posix" or shutil.which("sed") is None, reason="POSIX evidence command")
def test_terminal_evidence_command_opens_a_quoted_input_file(tmp_path):
    source = tmp_path / "named log with ' quote and dollar $.ndjson"
    source.write_bytes(encode_ndjson([
        {"event_type": "flow"},
        {"event_type": "alert", "alert": {"signature_id": 42}},
    ]))
    result = run_triage(str(source))

    assert result.returncode == 0, result.stderr
    output = result.stdout.decode("utf-8")
    assert "1 recorded alert event across 1 alert type" in output
    command, = (line.strip() for line in output.splitlines() if line.strip().startswith("sed -n "))
    evidence = subprocess.run(["/bin/sh", "-c", command], capture_output=True, check=True, timeout=5)
    assert evidence.stdout == source.read_bytes().splitlines(keepends=True)[1]


def test_triage_counts_repeated_firewall_denials_by_source_from_stdin():
    events = [
        {"event_type": "firewall", "action": "deny", "src_ip": "2001:0db8::1"},
        {"event_type": "firewall", "action": "DROP", "src_ip": "2001:db8::1"},
        {"event_type": "firewall", "action": "allow", "src_ip": "2001:db8::1"},
        {"event_type": "firewall", "action": "reject", "src_ip": "192.0.2.1"},
        {
            "event_type": "alert",
            "src_ip": "192.0.2.1",
            "alert": {"action": "blocked", "signature": "Policy alert"},
        },
    ]

    result = run_triage("--min-denials", "2", "-f", "json", data=encode_ndjson(events))

    assert result.returncode == 0
    assert result.stderr == b""
    report = json.loads(result.stdout)
    assert report["events"] == 5
    assert report["denied_events"] == 3
    assert report["repeated_denials"] == [{"src_ip": "2001:db8::1", "count": 2}]
    assert report["alerts"] == [
        {
            "signature_id": None, "signature": "Policy alert", "count": 1,
            "examples": [{"line": 5, "timestamp": None}],
        }
    ]


def test_triage_caps_examples_by_signature_and_preserves_physical_input_order():
    alert = {"event_type": "alert", "alert": {"signature": "An alert without an ID"}}
    events = [
        {**alert, "timestamp": "2026-01-01T12:00:03Z"},
        {"event_type": "flow"},
        {**alert, "timestamp": "2026-01-01T07:00:02.123-05:00"},
        {**alert, "timestamp": "2026-01-01T12:00:01+0000"},
    ]
    data = b"\n" + encode_ndjson(events)

    result = run_triage("-f", "json", data=data)

    assert result.returncode == 0
    assert result.stderr == b""
    assert json.loads(result.stdout)["alerts"] == [{
        "signature_id": None, "signature": "An alert without an ID", "count": 3,
        "examples": [
            {"line": 2, "timestamp": "2026-01-01T12:00:03Z"},
            {"line": 4, "timestamp": "2026-01-01T07:00:02.123-05:00"},
        ],
    }]


def test_triage_keeps_alerts_when_example_timestamp_is_unavailable():
    timestamps = ["2026-02-30T12:00:00Z", "2026-01-01T12:00:00+0099", "2026-01-01T12:00:00", 123]
    events = [
        {"event_type": "alert", "alert": {"signature_id": number}, "timestamp": timestamp}
        for number, timestamp in enumerate(timestamps, start=1)
    ]

    result = run_triage("-f", "json", data=encode_ndjson(events))

    assert result.returncode == 0
    assert result.stderr == b""
    report = json.loads(result.stdout)
    assert report["invalid_lines"] == 0
    assert report["events"] == 4
    assert report["alerts"] == [
        {
            "signature_id": number, "signature": None, "count": 1,
            "examples": [{"line": number, "timestamp": None}],
        }
        for number in range(1, 5)
    ]


def test_triage_keeps_valid_events_and_reports_invalid_line_numbers():
    data = (
        b'{"event_type":"flow"}\n'
        b'\n'
        b'{"broken"\n'
        b'[]\n'
        b'\xff\n'
        b'{"event_type":"firewall","action":"denied","src_ip":"oops"}\n'
        b'{"event_type":"alert","alert":{}}\n'
        b'{"event_type":"flow","value":NaN}\n'
        b'{"event_type":"alert","alert":{"signature_id":42}}'
    )

    result = run_triage("-", "-f", "json", data=data)

    assert result.returncode == 1
    report = json.loads(result.stdout)
    assert report["events"] == 2
    assert report["invalid_lines"] == 6
    assert report["alerts"][0]["signature_id"] == 42
    assert report["alerts"][0]["examples"] == [{"line": 9, "timestamp": None}]
    messages = result.stderr.decode("utf-8").splitlines()
    assert [message.split(":")[0] for message in messages] == [
        "Line 3", "Line 4", "Line 5", "Line 6", "Line 7", "Line 8"
    ]


def test_triage_escapes_terminal_control_characters_in_alert_labels():
    events = [{
        "event_type": "alert",
        "alert": {"signature": "\x1b[2Jexample"},
        "timestamp": "2026-01-01T12:00:00Z\x1b[2J\n",
    }]

    result = run_triage(data=encode_ndjson(events))

    assert result.returncode == 0
    assert b"\x1b" not in result.stdout
    assert b'"\\u001b[2Jexample"' in result.stdout
    assert "Input line 1 · timestamp unavailable" in result.stdout.decode("utf-8")


def test_triage_text_labels_counts_and_keeps_color_optional():
    signature = "Policy alert with a longer label that identifies the exact rule that fired"
    report = TriageReport(
        events=4,
        invalid_lines=1,
        min_denials=2,
        denied_events=2,
        alerts=[AlertGroup(42, signature, 2)],
        repeated_denials=[DenialGroup("192.0.2.1", 2)],
    )

    plain = format_triage(report)
    colored = format_triage(report, color=True)

    assert plain.startswith("jonq // triage\nPartial report.")
    assert plain.endswith("4 valid events, 1 invalid line")
    assert "Partial report" in plain
    assert "Count" in plain and "Signature ID" in plain and json.dumps(signature) in plain
    assert "2 total denials" in plain and "review threshold 2 per source" in plain
    assert "Source IP" in plain and "192.0.2.1" in plain
    assert "\x1b" not in plain
    assert "\x1b[36m" in colored and "\x1b[1;33m" in colored
    assert re.sub(r"\x1b\[[0-9;]+m", "", colored) == plain


def test_triage_rejects_nonpositive_denial_threshold():
    result = run_triage("--min-denials", "0")

    assert result.returncode == 2
    assert b"--min-denials must be positive" in result.stderr
