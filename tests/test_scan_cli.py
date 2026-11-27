from decimal import Decimal
import json
import os
from pathlib import Path
import subprocess
import sys


def run_connections(*args, data=b"", output_format="json"):
    return subprocess.run(
        [sys.executable, "-B", "-m", "jonq", "connections", *args, "--format", output_format],
        input=data,
        capture_output=True,
        env={**os.environ, "PATH": ""},
        timeout=10,
    )


def encode_events(events):
    return b"".join(json.dumps(event).encode("utf-8") + b"\n" for event in events)


def zeek_connection(timestamp, destination, port, state, *, src="192.0.2.10", protocol="tcp"):
    record = {
        "ts": timestamp,
        "id.orig_h": src,
        "id.resp_h": destination,
        "id.resp_p": port,
        "proto": protocol,
    }
    if state is not None:
        record["conn_state"] = state
    return record


def test_scan_leads_use_inclusive_timestamps_and_original_evidence_lines():
    records = [
        zeek_connection(1073741880.000003, "198.51.100.3", 22, "S0"),
        zeek_connection(1073741820.000003, "198.51.100.1", 22, "S0"),
        zeek_connection(1073741840, "198.51.100.2", 22, "REJ"),
        zeek_connection(1073741850, "198.51.100.2", 22, "S0"),
        zeek_connection(1073741880.000004, "198.51.100.4", 22, "REJ"),
        zeek_connection(1073741880.000003, "198.51.100.3", 22, "REJ"),
        zeek_connection(1073741851, "198.51.100.3", 22, "S0", src="192.0.2.11"),
        zeek_connection(1073741852, "203.0.113.9", 22, "S0"),
    ]
    data = encode_events(records[:1]) + b"\n" + encode_events(records[1:])

    args = (
        "-", "--scan-leads", "--window", "60", "--min-destinations", "3",
        "--src-cidr", "192.0.2.10", "--dst-cidr", "198.51.100.0/24",
    )
    result = run_connections(*args, data=data)
    text = run_connections(*args, data=data, output_format="text")

    assert result.returncode == 0, result.stderr
    assert result.stderr == b""
    report = json.loads(result.stdout, parse_float=Decimal)
    assert report["connections"] == 6
    assert report["candidate_records"] == 6
    assert report["out_of_scope"] == 2
    assert report["invalid_lines"] == 0
    lead, = report["scan_leads"]
    assert lead["src_ip"] == "192.0.2.10"
    assert lead["dest_port"] == 22
    assert lead["unique_destinations"] == 3
    assert lead["window_start"] == Decimal("1073741820.000003")
    assert lead["window_end"] == Decimal("1073741880.000003")
    assert lead["destinations"] == ["198.51.100.1", "198.51.100.2", "198.51.100.3"]
    assert lead["outcomes"] == {"no_reply": 3, "rejected": 2}
    assert sorted(record["line"] for record in lead["records"]) == [1, 3, 4, 5, 7]
    assert {record["details"]["state"] for record in lead["records"]} == {"REJ", "S0"}
    assert text.returncode == 0, text.stderr
    assert b"Scan leads to review (1)" in text.stdout
    assert (
        b"192.0.2.10 tried to connect to 3 different addresses on TCP port 22 within 60 seconds."
        in text.stdout
    )
    assert b"Expected activity is unverified." in text.stdout
    assert b"on the same TCP port" in text.stdout
    assert b"Input line 1" in text.stdout
    assert b"no reply observed (Zeek S0)" in text.stdout
    assert text.stdout.index(b"Input line 1") < text.stdout.index(b"Review threshold")
    assert b"sed -n" not in text.stdout


def test_scan_leads_require_distinct_failed_peers_on_the_same_tcp_port(tmp_path):
    source = tmp_path / "connections.ndjson"
    source.write_bytes(encode_events([
        *[zeek_connection(100, f"198.51.100.{peer}", 443, "SF") for peer in range(1, 7)],
        zeek_connection(100, "198.51.100.1", 22, "S0"),
        zeek_connection(101, "198.51.100.1", 22, "S0"),
        zeek_connection(102, "198.51.100.2", 22, "REJ"),
        zeek_connection(103, "198.51.100.3", 80, "REJ"),
        zeek_connection(104, "198.51.100.4", 80, "S0"),
        zeek_connection(105, "198.51.100.3", 22, "OTH"),
        zeek_connection(106, "198.51.100.4", 22, None),
        zeek_connection(107, "198.51.100.5", 22, "S0", protocol="udp"),
        zeek_connection(108, "198.51.100.6", None, "REJ"),
    ]))

    result = run_connections(str(source), "--scan-leads", "--min-destinations", "3")
    default = run_connections(str(source), "--min-destinations", "3")

    assert result.returncode == default.returncode == 0
    assert result.stderr == default.stderr == b""
    report = json.loads(result.stdout)
    assert report["connections"] == 15
    assert report["candidate_records"] == 5
    assert report["scan_leads"] == []
    default_report = json.loads(default.stdout)
    assert default_report["fanout"][0]["unique_destinations"] == 6
    assert "scan_leads" not in default_report


def test_scan_text_distinguishes_no_connections_no_candidates_and_below_threshold():
    established = encode_events([zeek_connection(100, "198.51.100.1", 22, "SF")])
    unanswered = encode_events([zeek_connection(100, "198.51.100.1", 22, "S0")])
    cases = [
        (b"", b"No in-scope connections to assess."),
        (established, b"No TCP records with a destination port and either a rejection or no observed reply."),
        (unanswered, b"No scan leads reached 2 distinct destinations on the same TCP port within 1 second"),
    ]
    for data, message in cases:
        result = run_connections(
            "--scan-leads", "--min-destinations", "2", "--window", "1", data=data, output_format="text",
        )
        assert result.returncode == 0, result.stderr
        assert message in result.stdout
        assert b"sed -n" not in result.stdout


def test_benign_retry_scan_text_explains_what_to_check():
    source = Path(__file__).parent / "json_test_files" / "benign_health_check_retries.ndjson"
    result = run_connections(str(source), "--scan-leads", output_format="text")

    assert result.returncode == 0, result.stderr
    assert b"192.0.2.40 tried to connect to 12 different addresses on TCP port 443 within 60 seconds." in result.stdout
    assert b"Expected activity is unverified." in result.stdout
    assert b"Input line 3" in result.stdout
    if os.name == "posix":
        assert b"sed -n '3p' < " in result.stdout


def test_scan_leads_keep_valid_evidence_when_an_input_line_is_malformed():
    records = [
        zeek_connection(1704067200, "198.51.100.1", 22, "REJ"),
        {
            "event_type": "flow",
            "src_ip": "192.0.2.10",
            "dest_ip": "198.51.100.2",
            "dest_port": 22,
            "proto": "TCP",
            "flow": {"start": "2024-01-01T00:00:01.000000+0000", "pkts_toclient": 0, "state": "new"},
        },
    ]
    data = encode_events(records[:1]) + b"invalid JSON\n" + encode_events(records[1:])

    result = run_connections("--scan-leads", "--min-destinations", "2", data=data)

    assert result.returncode == 1
    assert b"Line 2: invalid JSON" in result.stderr
    report = json.loads(result.stdout)
    assert report["connections"] == 2
    assert report["candidate_records"] == 2
    assert report["invalid_lines"] == 1
    lead, = report["scan_leads"]
    assert lead["outcomes"] == {"no_reply": 1, "rejected": 1}
    assert {record["line"]: record["log_format"] for record in lead["records"]} == {
        1: "zeek", 3: "eve",
    }


def test_scan_leads_and_baseline_are_mutually_exclusive(tmp_path):
    result = run_connections("--scan-leads", "--baseline", str(tmp_path / "baseline.ndjson"))

    assert result.returncode == 2
    assert result.stdout == b""
    assert b"--scan-leads" in result.stderr
    assert b"--baseline" in result.stderr
