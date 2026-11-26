import json
import os
from pathlib import Path
import re
import subprocess
import sys

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
    assert json.loads(result.stdout) == {
        "events": 8,
        "invalid_lines": 0,
        "min_denials": 5,
        "denied_events": 0,
        "alerts": [
            {"signature_id": 900001, "signature": "Synthetic policy alert", "count": 2},
            {"signature_id": 900002, "signature": "Synthetic protocol alert", "count": 1},
        ],
        "repeated_denials": [],
    }


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
        {"signature_id": None, "signature": "Policy alert", "count": 1}
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
    messages = result.stderr.decode("utf-8").splitlines()
    assert [message.split(":")[0] for message in messages] == [
        "Line 3", "Line 4", "Line 5", "Line 6", "Line 7", "Line 8"
    ]


def test_triage_escapes_terminal_control_characters_in_alert_labels():
    events = [{"event_type": "alert", "alert": {"signature": "\x1b[2Jexample"}}]

    result = run_triage(data=encode_ndjson(events))

    assert result.returncode == 0
    assert b"\x1b" not in result.stdout
    assert b'"\\u001b[2Jexample"' in result.stdout


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

    assert plain.startswith("jonq // triage\n4 valid events, 1 invalid line\n")
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
