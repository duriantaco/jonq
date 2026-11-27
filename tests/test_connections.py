import json
import os
from pathlib import Path
import subprocess
import sys

import pytest


ZEEK_FIXTURE = Path(__file__).parent / "json_test_files" / "zeek_conn.ndjson"
BASELINE_FIXTURE = ZEEK_FIXTURE.with_name("zeek_conn_baseline.ndjson")


def run_connections(*args, data=b"", output_format="json"):
    return subprocess.run(
        [sys.executable, "-B", "-m", "jonq", "connections", *args, "--format", output_format],
        input=data,
        capture_output=True,
        env={**os.environ, "PATH": ""},
        timeout=10,
    )


def test_connections_counts_both_directions_and_finds_a_rolling_peak_without_jq():
    result = run_connections(str(ZEEK_FIXTURE), "--window", "60", "--min-destinations", "3")

    assert result.returncode == 0
    assert result.stderr == b""
    report = json.loads(result.stdout)
    assert report["connections"] == 6
    assert report["conversations"][0] == {
        "endpoint_a": "192.0.2.10", "endpoint_b": "198.51.100.10",
        "a_to_b": 2, "b_to_a": 1,
    }
    assert report["fanout"] == [{
        "src_ip": "192.0.2.10",
        "unique_destinations": 3,
        "window_start": 1700000020.75,
        "window_end": 1700000080.75,
        "destinations": ["198.51.100.10", "198.51.100.11", "198.51.100.12"],
    }]


def test_connections_applies_both_network_scopes_before_grouping():
    result = run_connections(
        str(ZEEK_FIXTURE), "--src-cidr", "192.0.2.0/24",
        "--dst-cidr", "198.51.100.10", "--dst-cidr", "198.51.100.11",
        "--min-destinations", "2",
    )

    assert result.returncode == 0
    report = json.loads(result.stdout)
    assert report["connections"] == 3
    assert report["out_of_scope"] == 3
    assert report["conversations"][0]["a_to_b"] == 2
    assert report["conversations"][0]["b_to_a"] == 0
    assert report["fanout"][0]["destinations"] == ["198.51.100.10", "198.51.100.11"]


def test_connections_accepts_eve_start_times_and_preserves_results_on_invalid_rows():
    rows = [
        {"event_type": "alert"},
        {
            "event_type": "flow",
            "src_ip": "2001:0db8::1",
            "dest_ip": "2001:db8::2",
            "flow": {"start": "2024-01-01T02:00:00.000003+0200"},
            "timestamp": "2024-01-01T00:20:00Z",
        },
        {"ts": True, "id.orig_h": "2001:db8::1", "id.resp_h": "2001:db8::3"},
        {
            "event_type": "flow",
            "src_ip": "2001:db8::1",
            "dest_ip": "2001:db8::4",
            "timestamp": "2024-01-01T00:01:00.000003Z",
        },
    ]
    data = b"".join(json.dumps(row).encode("utf-8") + b"\n" for row in rows)

    result = run_connections("-", "--src-cidr", "2001:db8::/32", "--min-destinations", "2", data=data)

    assert result.returncode == 1
    assert b"Line 3: expected a finite Zeek ts" in result.stderr
    report = json.loads(result.stdout)
    assert report["connections"] == 2
    assert report["ignored_records"] == 1
    assert report["invalid_lines"] == 1
    assert report["fanout"][0]["destinations"] == ["2001:db8::2", "2001:db8::4"]


def test_connections_preserves_decimal_precision_at_the_inclusive_boundary():
    data = (
        b'{"ts":1073741820.000003,"id.orig_h":"192.0.2.1","id.resp_h":"198.51.100.1"}\n'
        b'{"ts":1073741880.000003,"id.orig_h":"192.0.2.1","id.resp_h":"198.51.100.2"}\n'
    )

    result = run_connections("--min-destinations", "2", data=data)

    assert result.returncode == 0
    assert json.loads(result.stdout)["fanout"][0]["unique_destinations"] == 2


def test_connections_evidence_keeps_original_lines_and_exact_window_bounds():
    data = (
        b'{"ts":1073741700,"id.orig_h":"192.0.2.1","id.resp_h":"198.51.100.3","proto":"tcp","id.resp_p":443,"conn_state":"S0"}\n'
        b'\n'
        b'{"ts":1073741820.000003,"id.orig_h":"192.0.2.1","id.resp_h":"198.51.100.1","proto":"tcp","id.resp_p":443,"conn_state":"REJ"}\n'
        b'{"ts":1073741880.000003,"id.orig_h":"192.0.2.1","id.resp_h":"198.51.100.2","proto":"tcp","id.resp_p":443,"conn_state":"S0"}\n'
        b'{"ts":1073741880.000003,"id.orig_h":"192.0.2.1","id.resp_h":"198.51.100.2","proto":"tcp","id.resp_p":443,"conn_state":"SF"}\n'
        b'{"ts":1073741880.000003001,"id.orig_h":"192.0.2.1","id.resp_h":"198.51.100.2","proto":"tcp","id.resp_p":443,"conn_state":"REJ"}\n'
    )

    result = run_connections("--min-destinations", "2", data=data)

    assert result.returncode == 0
    evidence = json.loads(result.stdout)["evidence"]["192.0.2.1"]
    assert evidence["services"] == [{
        "protocol": "tcp",
        "dest_port": 443,
        "outcomes": {"rejected": 1, "no_reply": 1, "established": 1},
    }]
    assert [record["line"] for record in evidence["records"]] == [3, 4, 5]
    assert [record["details"]["state"] for record in evidence["records"]] == ["REJ", "S0", "SF"]
    assert all(record["log_format"] == "zeek" for record in evidence["records"])


def test_connections_compares_below_threshold_baseline_and_puts_evidence_first():
    args = (
        str(ZEEK_FIXTURE), "--baseline", str(BASELINE_FIXTURE),
        "--src-cidr", "192.0.2.0/24", "--min-destinations", "3",
    )
    result = run_connections(*args)

    assert result.returncode == 0
    assert json.loads(result.stdout)["baseline"] == {
        "connections": 2,
        "invalid_lines": 0,
        "available": True,
        "findings": [{
            "src_ip": "192.0.2.10",
            "status": "changed",
            "baseline_peak": 2,
            "new_destinations": ["198.51.100.12"],
        }],
    }

    result = run_connections(*args, output_format="text")
    output = result.stdout.decode("utf-8")
    assert result.returncode == 0
    assert "2023-11-14 22:13:40.750000 UTC" in output
    assert "Baseline peak 2 (+1)" in output
    assert "TCP/443 · 4 records · 2 no reply observed, 2 established" in output
    assert "Input line 1 · 198.51.100.12 · TCP/443 · no reply observed (Zeek S0)" in output
    assert output.index("Sources to review (1)") < output.index("IP conversations")


@pytest.mark.parametrize("include_peer_outside_peak", [True, False])
def test_connections_checks_peers_across_the_entire_baseline(tmp_path, include_peer_outside_peak):
    reference = tmp_path / "reference.ndjson"
    records = (
        BASELINE_FIXTURE.read_bytes()
        + b'{"ts":1699913630,"id.orig_h":"192.0.2.10","id.resp_h":"198.51.100.13"}\n'
    )
    if include_peer_outside_peak:
        records += b'{"ts":1699913000,"id.orig_h":"192.0.2.10","id.resp_h":"198.51.100.12"}\n'
    reference.write_bytes(records)

    result = run_connections(
        str(ZEEK_FIXTURE), "--baseline", str(reference), "--min-destinations", "3"
    )

    assert result.returncode == 0
    assert json.loads(result.stdout)["baseline"]["findings"] == [{
        "src_ip": "192.0.2.10",
        "status": "within_baseline" if include_peer_outside_peak else "changed",
        "baseline_peak": 3,
        "new_destinations": [] if include_peer_outside_peak else ["198.51.100.12"],
    }]


def test_connections_distinguishes_an_unseen_source_from_an_empty_baseline_scope(tmp_path):
    reference = tmp_path / "reference.ndjson"
    reference.write_text(
        '{"ts":1000,"id.orig_h":"198.51.100.12","id.resp_h":"192.0.2.10"}\n',
        encoding="utf-8",
    )
    args = (str(ZEEK_FIXTURE), "--baseline", str(reference), "--min-destinations", "3")

    result = run_connections(*args)
    assert result.returncode == 0
    finding = json.loads(result.stdout)["baseline"]["findings"][0]
    assert finding["status"] == "unseen_source"
    assert finding["baseline_peak"] is None
    assert finding["new_destinations"] == ["198.51.100.10", "198.51.100.11", "198.51.100.12"]

    result = run_connections(*args, "--src-cidr", "192.0.2.0/24")
    assert result.returncode == 0
    assert json.loads(result.stdout)["baseline"]["available"] is False


@pytest.mark.parametrize("malformed_input", ["current", "baseline"])
def test_connections_keeps_peak_but_skips_comparison_for_partial_input(tmp_path, malformed_input):
    broken = tmp_path / "broken.ndjson"
    fixture = ZEEK_FIXTURE if malformed_input == "current" else BASELINE_FIXTURE
    broken.write_bytes(fixture.read_bytes() + b"invalid JSON\n")

    current = broken if malformed_input == "current" else ZEEK_FIXTURE
    reference = broken if malformed_input == "baseline" else BASELINE_FIXTURE
    result = run_connections(
        str(current), "--baseline", str(reference), "--min-destinations", "3"
    )

    assert result.returncode == 1
    report = json.loads(result.stdout)
    assert report["fanout"][0]["unique_destinations"] == 3
    assert report["baseline"]["available"] is False
    assert report["baseline"]["findings"] == []
    if malformed_input == "baseline":
        assert b"Baseline line 3:" in result.stderr


def test_connections_explains_empty_scope_and_no_qualifying_peak():
    empty = run_connections(
        str(ZEEK_FIXTURE), "--src-cidr", "203.0.113.0/24", output_format="text"
    )
    below_cutoff = run_connections(str(ZEEK_FIXTURE), output_format="text")

    assert empty.returncode == below_cutoff.returncode == 0
    assert b"No in-scope connections to assess" in empty.stdout
    assert b"No source reached 10 distinct destinations in 60 seconds" in below_cutoff.stdout


def test_connections_limits_text_preview_and_keeps_all_json_evidence():
    data = b"".join(
        json.dumps({"ts": 42, "id.orig_h": "192.0.2.1", "id.resp_h": f"198.51.100.{i}"}).encode()
        + b"\n"
        for i in range(1, 15)
    )

    text = run_connections("--min-destinations", "2", data=data, output_format="text")
    result = run_connections("--min-destinations", "2", data=data)

    assert text.returncode == result.returncode == 0
    assert b"(+6 more in --format json)" in text.stdout
    assert b"2 more conversations in --format json" in text.stdout
    report = json.loads(result.stdout)
    assert len(report["fanout"][0]["destinations"]) == 14
    assert len(report["evidence"]["192.0.2.1"]["records"]) == 14
    assert len(report["conversations"]) == 14


@pytest.mark.parametrize(("flag", "value", "message"), [
    ("--window", "0", b"--window must be a positive"),
    ("--min-destinations", "1", b"--min-destinations must be at least 2"),
    ("--src-cidr", "192.0.2.1/24", b"invalid IP or CIDR filter"),
    ("--baseline", "-", b"--baseline requires a local NDJSON file"),
])
def test_connections_rejects_invalid_options(flag, value, message):
    result = run_connections(flag, value)

    assert result.returncode == 2
    assert message in result.stderr
