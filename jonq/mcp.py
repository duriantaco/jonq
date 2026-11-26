from __future__ import annotations

import argparse
from contextlib import contextmanager
from dataclasses import asdict
import json
import os
from pathlib import PurePath
import stat
import sys

from jonq.connections import (
    DEFAULT_MIN_DESTINATIONS,
    DEFAULT_WINDOW_SECONDS,
    analyze_connections,
    compare_baseline,
)
from jonq.constants import VERSION
from jonq.networks import parse_networks
from jonq.triage import DEFAULT_MIN_DENIALS, analyze_events


_PROTOCOL_VERSIONS = ("2025-11-25", "2025-06-18", "2025-03-26", "2024-11-05")
_STRUCTURED_VERSIONS = _PROTOCOL_VERSIONS[:2]
_MAX_DIAGNOSTICS = 20
_FILE = {"type": "string", "minLength": 1, "description": "NDJSON file path relative to the log root."}
_CIDRS = {"type": "array", "items": {"type": "string"}, "description": "IPv4/IPv6 host addresses or CIDRs."}


def _tool(name, description, **options):
    return {
        "name": name,
        "description": description,
        "inputSchema": {
            "type": "object",
            "properties": {"path": _FILE, **options},
            "required": ["path"],
            "additionalProperties": False,
        },
        "annotations": {"readOnlyHint": True, "openWorldHint": False},
    }


_TOOLS = {
    "triage": _tool(
        "triage", "Summarize recorded Suricata alerts and repeated firewall denials in a saved NDJSON file.",
        min_denials={"type": "integer", "minimum": 1, "default": DEFAULT_MIN_DENIALS},
    ),
    "connections": _tool(
        "connections", "Review IP conversations and peak destination counts in a saved Zeek or Suricata EVE file.",
        window_seconds={"type": "integer", "minimum": 1, "default": DEFAULT_WINDOW_SECONDS},
        min_destinations={"type": "integer", "minimum": 2, "default": DEFAULT_MIN_DESTINATIONS},
        src_cidr=_CIDRS,
        dst_cidr=_CIDRS,
        baseline=_FILE,
        scan_leads={
            "type": "boolean", "default": False,
            "description": "Summarize same-port TCP rejections and attempts without a reply. Incompatible with baseline.",
        },
    ),
}


@contextmanager
def _open_log(root, value):
    path = PurePath(value)
    if path.is_absolute() or not path.parts or ".." in path.parts or "\x00" in value or "://" in value:
        raise ValueError("Provide a file path relative to the log root.")

    # Hold directory descriptors across lookups so a symlink swap cannot redirect reads.
    directory = os.dup(root)
    try:
        for part in path.parts[:-1]:
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=directory)
            os.close(directory)
            directory = child
        flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK
        descriptor = os.open(path.name, flags, dir_fd=directory)
    except (OSError, UnicodeError):
        raise ValueError("Cannot open this file beneath the log root. Check the path and avoid symlinks.") from None
    finally:
        os.close(directory)

    try:
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            raise ValueError("The input must be a regular file.")
        with os.fdopen(descriptor, "rb", closefd=False) as source:
            yield source
    finally:
        os.close(descriptor)


def _validate_arguments(tool, arguments):
    properties = _TOOLS[tool]["inputSchema"]["properties"]
    unsupported = arguments.keys() - properties.keys()
    if unsupported:
        raise ValueError(f"Unknown argument: {min(unsupported)!r}")
    if "path" not in arguments:
        raise ValueError("Provide the required path argument.")
    for name, value in arguments.items():
        schema = properties[name]
        kind = schema["type"]
        if kind == "integer" and (type(value) is not int or value < schema["minimum"]):
            raise ValueError(f"{name} must be an integer of at least {schema['minimum']}.")
        if kind == "string" and (not isinstance(value, str) or not value):
            raise ValueError(f"{name} must be a nonempty string.")
        if kind == "boolean" and type(value) is not bool:
            raise ValueError(f"{name} must be a boolean.")
        if kind == "array" and (
            not isinstance(value, list) or not all(isinstance(item, str) for item in value)
        ):
            raise ValueError(f"{name} must be a list of IP addresses or CIDRs.")


def _analysis(root, tool, arguments):
    diagnostics = []

    def record_error(line, message, source="input"):
        if len(diagnostics) < _MAX_DIAGNOSTICS:
            diagnostics.append({"source": source, "line": line, "message": message})

    if tool == "triage":
        with _open_log(root, arguments["path"]) as lines:
            report = analyze_events(
                lines, min_denials=arguments.get("min_denials", DEFAULT_MIN_DENIALS),
                report_error=record_error,
            )
        payload = asdict(report)
        invalid_lines = report.invalid_lines
    else:
        scan = arguments.get("scan_leads", False)
        baseline = arguments.get("baseline")
        if scan and baseline is not None:
            raise ValueError("Choose either scan_leads or baseline.")
        scope = {
            "window_seconds": arguments.get("window_seconds", DEFAULT_WINDOW_SECONDS),
            "src_networks": parse_networks(arguments.get("src_cidr", [])),
            "dst_networks": parse_networks(arguments.get("dst_cidr", [])),
        }
        with _open_log(root, arguments["path"]) as lines:
            report = analyze_connections(
                lines, min_destinations=arguments.get("min_destinations", DEFAULT_MIN_DESTINATIONS),
                scan_leads_only=scan, report_error=record_error, **scope,
            )
        payload = asdict(report)
        invalid_lines = report.invalid_lines
        if baseline is not None:
            with _open_log(root, baseline) as lines:
                reference = analyze_connections(
                    lines, min_destinations=1, include_evidence=False,
                    report_error=lambda line, message: record_error(line, message, "baseline"),
                    **scope,
                )
            payload["baseline"] = asdict(compare_baseline(report, reference))
            invalid_lines += reference.invalid_lines

    if diagnostics:
        payload["diagnostics"] = diagnostics
        payload["diagnostics_truncated"] = invalid_lines > len(diagnostics)
    return payload, bool(invalid_lines)


def _serialize(value):
    # Match the CLI's JSON representation for Decimal connection timestamps.
    return json.dumps(value, default=float, allow_nan=False, separators=(",", ":"))


def _tool_result(text, *, is_error=False):
    return {"content": [{"type": "text", "text": text}], "isError": is_error}


def _result(request_id, result):
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def _error(request_id, code, message):
    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}


class _Session:
    def __init__(self, root):
        self.root = root
        self.protocol = None
        self.ready = False

    def receive(self, message):
        if self.protocol == "2025-03-26" and isinstance(message, list) and message:
            responses = [self._message(item) for item in message]
            return [response for response in responses if response is not None] or None
        return self._message(message)

    def _message(self, message):
        if not isinstance(message, dict):
            return _error(None, -32600, "Invalid request")
        request_id = message.get("id")
        is_request = "id" in message
        valid_id = type(request_id) in (int, str)
        method = message.get("method")
        params = message.get("params", {})
        if message.get("jsonrpc") != "2.0" or not isinstance(method, str) or (is_request and not valid_id):
            return _error(request_id if valid_id else None, -32600, "Invalid request")
        if not is_request:
            if method == "notifications/initialized" and self.protocol and isinstance(params, dict):
                self.ready = True
            return None
        if not isinstance(params, dict):
            return _error(request_id, -32602, "Request params must be an object")
        if method == "ping":
            return _result(request_id, {})
        if method == "initialize":
            return self._initialize(request_id, params)
        if not self.ready:
            return _error(request_id, -32000, "Complete initialization before using tools")
        if method == "tools/list":
            if "cursor" in params:
                return _error(request_id, -32602, "Invalid tools cursor")
            return _result(request_id, {"tools": list(_TOOLS.values())})
        if method == "tools/call":
            return self._call(request_id, params)
        return _error(request_id, -32601, "Method not found")

    def _initialize(self, request_id, params):
        offered = params.get("protocolVersion")
        client = params.get("clientInfo")
        if self.protocol is not None:
            return _error(request_id, -32600, "Session is already initialized")
        if (
            not isinstance(offered, str) or not offered or not isinstance(params.get("capabilities"), dict)
            or not isinstance(client, dict) or not isinstance(client.get("name"), str)
            or not isinstance(client.get("version"), str)
        ):
            return _error(request_id, -32602, "Provide protocolVersion, capabilities, and clientInfo")
        self.protocol = offered if offered in _PROTOCOL_VERSIONS else _PROTOCOL_VERSIONS[0]
        return _result(request_id, {
            "protocolVersion": self.protocol,
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": {"name": "jonq", "version": VERSION},
        })

    def _call(self, request_id, params):
        name = params.get("name")
        arguments = params.get("arguments", {})
        if not isinstance(name, str) or not isinstance(arguments, dict):
            return _error(request_id, -32602, "Provide a tool name and an arguments object")
        if name not in _TOOLS:
            return _error(request_id, -32602, f"Unknown tool: {name!r}")
        try:
            _validate_arguments(name, arguments)
            payload, partial = _analysis(self.root, name, arguments)
            result = _tool_result(_serialize(payload), is_error=partial)
        except ValueError as exc:
            result = _tool_result(str(exc), is_error=True)
        except OSError:
            result = _tool_result("Could not read the selected log file.", is_error=True)
        else:
            if self.protocol in _STRUCTURED_VERSIONS:
                result["structuredContent"] = payload
        return _result(request_id, result)


def _reject_constant(constant):
    raise ValueError(f"Invalid JSON number: {constant}")


def run_mcp(argv):
    parser = argparse.ArgumentParser(
        prog="jonq mcp", description="Serve read-only network log tools over MCP stdio.",
    )
    parser.add_argument("--log-root", required=True, help="Directory containing the logs clients may read")
    args = parser.parse_args(argv)
    if os.open not in os.supports_dir_fd or not hasattr(os, "O_NOFOLLOW"):
        parser.error("MCP requires a platform with directory-relative, no-follow file access")

    try:
        root = os.open(args.log_root, os.O_RDONLY | os.O_DIRECTORY)
    except OSError:
        parser.error("--log-root must be an accessible directory")
    try:
        session = _Session(root)
        for line in sys.stdin.buffer:
            try:
                message = json.loads(line.decode("utf-8"), parse_constant=_reject_constant)
            except (ValueError, RecursionError):
                response = _error(None, -32700, "Parse error")
            else:
                response = session.receive(message)
            if response is not None:
                sys.stdout.buffer.write((_serialize(response) + "\n").encode("utf-8"))
                sys.stdout.buffer.flush()
    finally:
        os.close(root)
