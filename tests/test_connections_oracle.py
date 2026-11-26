from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from decimal import Decimal
from ipaddress import ip_address, ip_network
from itertools import combinations_with_replacement, product
import json
import os
from random import Random
import re
import subprocess
import sys

import pytest

from jonq.connections import analyze_connections


@dataclass(frozen=True)
class Observation:
    timestamp: Decimal
    destination: str
    source: str = "192.0.2.1"
    port: int | None = 22
    protocol: str = "tcp"
    state: str | None = "S0"

    def ndjson(self):
        fields = json.dumps({
            "id.orig_h": self.source,
            "id.resp_h": self.destination,
            "id.resp_p": self.port,
            "proto": self.protocol,
            "conn_state": self.state,
        })
        return f'{{"ts":{self.timestamp},{fields[1:]}\n'.encode()

    def expected_outcome(self):
        if self.protocol == "tcp":
            if self.state == "S0":
                return "no_reply"
            if self.state == "REJ":
                return "rejected"
            if self.state in {"SF", "S1", "S2", "S3", "RSTO"}:
                return "established"
        return "unknown"

    def expected_evidence(self, line):
        return {
            "timestamp": self.timestamp,
            "dest_ip": self.destination,
            "line": line,
            "log_format": "zeek",
            "details": {
                "protocol": self.protocol,
                "dest_port": self.port,
                "outcome": self.expected_outcome(),
                "state": self.state,
            },
        }


def _is_candidate(observation):
    return observation.port is not None and observation.expected_outcome() in {"no_reply", "rejected"}


def _oracle_peaks(numbered, *, window_seconds, min_destinations, scan):
    groups = defaultdict(list)
    for line, observation in numbered:
        if not scan or _is_candidate(observation):
            port = observation.port if scan else None
            groups[observation.source, port].append((line, observation))

    peaks = []
    for (source, port), group in groups.items():
        # Try every possible finishing timestamp without carrying counts between windows.
        windows = []
        for end in {observation.timestamp for _, observation in group}:
            rows = [
                (line, row) for line, row in group
                if end - window_seconds <= row.timestamp <= end
            ]
            peers = {row.destination for _, row in rows}
            windows.append((end, peers, rows))
        end, peers, rows = min(windows, key=lambda item: (-len(item[1]), item[0]))
        if len(peers) < min_destinations:
            continue
        peak = {
            "src_ip": source,
            "unique_destinations": len(peers),
            "window_start": min(row.timestamp for _, row in rows),
            "window_end": end,
            "destinations": sorted(peers),
            "records": [row.expected_evidence(line) for line, row in rows],
        }
        if scan:
            peak["dest_port"] = port
            peak["outcomes"] = dict(Counter(row.expected_outcome() for _, row in rows))
        peaks.append(peak)
    return sorted(
        peaks,
        key=lambda peak: (-peak["unique_destinations"], peak["src_ip"], peak.get("dest_port", -1)),
    )


def _assert_peaks_match(report, numbered, *, window_seconds, min_destinations, scan):
    expected = _oracle_peaks(
        numbered, window_seconds=window_seconds, min_destinations=min_destinations, scan=scan,
    )
    if scan:
        assert report["candidate_records"] == sum(_is_candidate(row) for _, row in numbered)
        actual = report["scan_leads"]
    else:
        assert set(report["evidence"]) == {peak["src_ip"] for peak in expected}
        actual = [
            {**peak, "records": report["evidence"][peak["src_ip"]]["records"]}
            for peak in report["fanout"]
        ]
    assert actual == expected
    if not scan:
        for peak in expected:
            services = report["evidence"][peak["src_ip"]]["services"]
            expected_services = defaultdict(Counter)
            for record in peak["records"]:
                details = record["details"]
                expected_services[details["protocol"], details["dest_port"]][details["outcome"]] += 1
            assert len(services) == len(expected_services)
            assert {
                (service["protocol"], service["dest_port"]): service["outcomes"]
                for service in services
            } == expected_services


def _unexpected_error(line, message):
    pytest.fail(f"Unexpected diagnostic on line {line}: {message}")


def test_rolling_windows_match_brute_force_for_small_multisets():
    alphabet = [
        Observation(Decimal(time), f"198.51.100.{peer}", state="S0" if peer == 1 else "REJ")
        for time, peer in product(("100", "101", "101.000001"), (1, 2))
    ]
    for size in range(5):
        for multiset in combinations_with_replacement(alphabet, size):
            # Reverse timestamp order to put line order and chronological order in conflict.
            observations = list(reversed(multiset))
            numbered = list(enumerate(observations, 1))
            lines = [observation.ndjson() for observation in observations]
            for scan in (False, True):
                report = analyze_connections(
                    lines, window_seconds=1, min_destinations=2,
                    scan_leads_only=scan, report_error=_unexpected_error,
                )
                _assert_peaks_match(
                    asdict(report), numbered, window_seconds=1, min_destinations=2, scan=scan,
                )


@pytest.mark.parametrize(("seed", "window_seconds", "min_destinations"), [
    (13, 2, 2), (41, 3, 2), (90, 2, 3),
])
def test_seeded_cli_replays_match_oracle_with_noise_and_scope(seed, window_seconds, min_destinations):
    random = Random(seed)
    source_scope = ip_network("192.0.2.0/24")
    dest_scope = ip_network("198.51.100.0/24")
    observations = [
        Observation(Decimal(time), f"198.51.100.{peer}", source, port, state=state)
        for (source, port), (time, peer, state) in product(
            (("192.0.2.1", 22), ("192.0.2.1", 443), ("192.0.2.2", 22)),
            (("110", 1, "S0"), ("112", 2, "REJ"), ("112", 2, "S0")),
        )
    ]
    for _ in range(45):
        observations.append(Observation(
            timestamp=Decimal(random.choice(("100", "101.25", "102", "102.000001", "104.6"))),
            destination=random.choice(("198.51.100.1", "198.51.100.2", "198.51.100.3", "203.0.113.8")),
            source=random.choice(("192.0.2.1", "192.0.2.2", "203.0.113.1")),
            port=random.choice((0, 22, 443, None)),
            protocol=random.choice(("tcp", "tcp", "udp")),
            state=random.choice(("S0", "REJ", "SF", "S2", "RSTO", "RSTR", "OTH", None)),
        ))
    invalid = [
        b"not JSON\n",
        b"\xff\n",
        b"[]\n",
        b'{"id.orig_h":"192.0.2.1","id.resp_h":"198.51.100.1","ts":"wrong"}\n',
    ]
    entries = [*observations, *invalid, b" \t\n", b'{"event_type":"alert"}\n']
    random.shuffle(entries)
    numbered = [
        (line, entry) for line, entry in enumerate(entries, 1)
        if isinstance(entry, Observation)
        and ip_address(entry.source) in source_scope
        and ip_address(entry.destination) in dest_scope
    ]
    invalid_lines = [line for line, entry in enumerate(entries, 1) if entry in invalid]
    data = b"".join(entry.ndjson() if isinstance(entry, Observation) else entry for entry in entries)
    args = [
        sys.executable, "-B", "-m", "jonq", "connections", "-", "--format", "json",
        "--window", str(window_seconds), "--min-destinations", str(min_destinations),
        "--src-cidr", str(source_scope), "--dst-cidr", str(dest_scope),
    ]

    for scan in (False, True):
        result = subprocess.run(
            args + (["--scan-leads"] if scan else []),
            input=data, capture_output=True, env={**os.environ, "PATH": ""}, timeout=10,
        )
        assert result.returncode == 1, result.stderr
        assert [int(line) for line in re.findall(rb"^Line (\d+):", result.stderr, re.M)] == invalid_lines
        report = json.loads(result.stdout, parse_float=Decimal)
        assert report["connections"] == len(numbered)
        assert report["out_of_scope"] == len(observations) - len(numbered)
        assert report["ignored_records"] == 1
        assert report["invalid_lines"] == len(invalid)
        _assert_peaks_match(
            report, numbered, window_seconds=window_seconds, min_destinations=min_destinations, scan=scan,
        )
