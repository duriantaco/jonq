import json
import os
from pathlib import Path
from selectors import DefaultSelector, EVENT_READ
import subprocess
import sys

import pytest


FIXTURES = Path(__file__).resolve().parent / "json_test_files"
pytestmark = pytest.mark.skipif(os.open not in os.supports_dir_fd, reason="MCP uses directory-relative file access")


def request(request_id, method, params=None):
    message = {"jsonrpc": "2.0", "id": request_id, "method": method}
    if params is not None:
        message["params"] = params
    return message


def initialize(version="2025-11-25"):
    return request("init", "initialize", {
        "protocolVersion": version,
        "capabilities": {},
        "clientInfo": {"name": "test-client", "version": "1"},
    })


INITIALIZED = {"jsonrpc": "2.0", "method": "notifications/initialized"}


def call(request_id, name, **arguments):
    return request(request_id, "tools/call", {"name": name, "arguments": arguments})


def run_mcp(root, *messages):
    data = "".join((message if isinstance(message, str) else json.dumps(message)) + "\n" for message in messages)
    proc = subprocess.run(
        [sys.executable, "-B", "-m", "jonq", "mcp", "--log-root", str(root)],
        input=data,
        capture_output=True,
        text=True,
        env={**os.environ, "PATH": ""},
        timeout=10,
    )
    assert proc.returncode == 0, proc.stderr
    assert proc.stderr == ""
    responses = [json.loads(line) for line in proc.stdout.splitlines()]
    return responses


def test_stdio_initializes_lists_tools_and_handles_protocol_errors():
    responses = run_mcp(
        FIXTURES,
        "{",
        {"jsonrpc": "2.0", "method": "ping", "id": None},
        request(1, "ping"),
        request(2, "tools/list"),
        initialize("2099-01-01"),
        request(3, "tools/list"),
        INITIALIZED,
        {"jsonrpc": "2.0", "method": "notifications/cancelled", "params": {"requestId": 999}},
        request(4, "tools/list"),
        request(5, "unknown"),
        call(6, "missing"),
        request(7, "tools/call", {"name": "triage", "arguments": []}),
        request(8, "ping"),
    )

    assert all(response["jsonrpc"] == "2.0" for response in responses)
    assert [response["id"] for response in responses] == [None, None, 1, 2, "init", 3, 4, 5, 6, 7, 8]
    assert [response["error"]["code"] for response in responses if "error" in response] == [
        -32700, -32600, -32000, -32000, -32601, -32602, -32602,
    ]
    by_id = {response["id"]: response for response in responses}
    assert by_id[1]["result"] == by_id[8]["result"] == {}
    handshake = by_id["init"]["result"]
    assert handshake["protocolVersion"] == "2025-11-25"
    assert handshake["serverInfo"]["name"] == "jonq"
    assert handshake["capabilities"] == {"tools": {"listChanged": False}}
    tools = {tool["name"]: tool for tool in by_id[4]["result"]["tools"]}
    assert set(tools) == {"triage", "connections"}
    assert all(tool["annotations"]["readOnlyHint"] for tool in tools.values())
    assert all(tool["inputSchema"]["required"] == ["path"] for tool in tools.values())
    assert tools["connections"]["inputSchema"]["properties"]["src_cidr"]["type"] == "array"


def test_stdio_flushes_each_reply_and_shuts_down_on_eof():
    with subprocess.Popen(
        [sys.executable, "-B", "-m", "jonq", "mcp", "--log-root", str(FIXTURES)],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        env={**os.environ, "PYTHONIOENCODING": "utf-16"},
    ) as process, DefaultSelector() as selector:
        selector.register(process.stdout, EVENT_READ)
        try:
            for message in (initialize(), INITIALIZED, request("next", "ping")):
                process.stdin.write(json.dumps(message) + "\n")
                process.stdin.flush()
                if "id" in message:
                    assert selector.select(timeout=5), "MCP did not flush its response"
                    assert json.loads(process.stdout.readline())["id"] == message["id"]
            process.stdin.close()
            assert process.wait(timeout=5) == 0
            assert process.stdout.read() == process.stderr.read() == ""
        finally:
            if process.poll() is None:
                process.kill()


def test_tool_results_match_saved_logs_and_preserve_original_line_evidence():
    responses = run_mcp(
        FIXTURES,
        initialize("2025-06-18"),
        INITIALIZED,
        call(1, "triage", path="suricata_eve.ndjson", min_denials=2),
        call(2, "connections", path="zeek_conn.ndjson", scan_leads=True, min_destinations=2),
        call(
            3, "connections", path="zeek_conn.ndjson", baseline="zeek_conn_baseline.ndjson",
            src_cidr=["192.0.2.0/24"], dst_cidr=["198.51.100.0/24"],
            min_destinations=3, window_seconds=60,
        ),
    )
    assert responses[0]["result"]["protocolVersion"] == "2025-06-18"
    results = [response["result"] for response in responses[1:]]
    for result in results:
        assert result["isError"] is False
        assert json.loads(result["content"][0]["text"]) == result["structuredContent"]
    alerts, scans, comparison = [result["structuredContent"] for result in results]
    assert alerts["events"] == 8
    assert alerts["min_denials"] == 2
    examples = alerts["alerts"][0]["examples"]
    assert [example["line"] for example in examples] == [6, 7]
    source = (FIXTURES / "suricata_eve.ndjson").read_text().splitlines()
    for example in examples:
        event = json.loads(source[example["line"] - 1])
        assert event["alert"]["signature_id"] == alerts["alerts"][0]["signature_id"]
        assert event["timestamp"] == example["timestamp"]
    lead = scans["scan_leads"][0]
    assert lead["src_ip"] == "192.0.2.10"
    assert lead["dest_port"] == 443
    assert [row["line"] for row in lead["records"]] == [1, 3]
    finding = comparison["baseline"]["findings"][0]
    assert finding["status"] == "changed"
    assert finding["new_destinations"] == ["198.51.100.12"]


def test_tools_cannot_read_outside_root_or_open_special_files(tmp_path):
    root = tmp_path / "logs"
    child = root / "nested"
    child.mkdir(parents=True)
    good = child / "eve.ndjson"
    good.write_bytes((FIXTURES / "suricata_eve.ndjson").read_bytes())
    outside = tmp_path / "outside.ndjson"
    outside.write_bytes(good.read_bytes())
    (root / "linked-file").symlink_to(outside)
    (root / "linked-dir").symlink_to(tmp_path, target_is_directory=True)
    os.mkfifo(root / "pipe")
    paths = [str(outside), "../outside.ndjson", "linked-file", "linked-dir/outside.ndjson",
             "nested", "pipe", "https://example.test/eve.ndjson", "\0"]
    responses = run_mcp(
        root,
        initialize(), INITIALIZED,
        *(call(number, "triage", path=path) for number, path in enumerate(paths)),
        call(20, "connections", path="nested/eve.ndjson", baseline="../outside.ndjson"),
        call(21, "triage", path="nested/eve.ndjson"),
    )[1:]

    for response in responses[:-1]:
        assert response["result"]["isError"] is True
        assert "structuredContent" not in response["result"]
        assert str(tmp_path) not in response["result"]["content"][0]["text"]
    assert responses[-1]["result"]["structuredContent"]["events"] == 8


def test_legacy_client_receives_text_results_and_partial_diagnostics(tmp_path):
    (tmp_path / "events.ndjson").write_bytes(
        b'{"event_type":"alert","alert":{"signature_id":42}}\n' + b'bad line\n' * 25
    )
    response = run_mcp(
        tmp_path, initialize("2024-11-05"), INITIALIZED, call(1, "triage", path="events.ndjson")
    )
    assert response[0]["result"]["protocolVersion"] == "2024-11-05"
    result = response[1]["result"]
    assert "structuredContent" not in result
    assert result["isError"] is True
    report = json.loads(result["content"][0]["text"])
    assert report["events"] == 1
    assert report["alerts"][0]["examples"] == [{"line": 1, "timestamp": None}]
    assert report["invalid_lines"] == 25
    assert len(report["diagnostics"]) == 20
    assert report["diagnostics"][0]["source"] == "input"
    assert report["diagnostics"][0]["line"] == 2
    assert report["diagnostics_truncated"] is True


def test_march_2025_protocol_supports_json_rpc_batches():
    ping = {"jsonrpc": "2.0", "id": 1, "result": {}}
    responses = run_mcp(FIXTURES, initialize("2025-03-26"), INITIALIZED, [
        request(1, "ping"),
        {"jsonrpc": "2.0", "method": "notifications/cancelled", "params": {"requestId": 999}},
    ])

    assert responses[0]["result"]["protocolVersion"] == "2025-03-26"
    assert responses[1:] == [[ping]]


def test_invalid_tool_arguments_leave_session_usable():
    responses = run_mcp(
        FIXTURES,
        initialize(), INITIALIZED,
        call(1, "triage", path="suricata_eve.ndjson", min_denials=True),
        call(2, "connections", path="zeek_conn.ndjson", src_cidr="192.0.2.0/24"),
        call(3, "connections", path="zeek_conn.ndjson", src_cidr=["not a network"]),
        call(4, "connections", path="zeek_conn.ndjson", scan_leads=True, baseline="test"),
        call(5, "triage", path="suricata_eve.ndjson", tool="unknown"),
        call(6, "triage"),
        request(7, "ping"),
    )[1:]
    assert all(response["result"]["isError"] is True for response in responses[:-1])
    assert responses[-1]["result"] == {}
