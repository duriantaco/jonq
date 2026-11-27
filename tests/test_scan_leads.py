from decimal import Decimal

import pytest

from jonq.connection_evidence import ConnectionDetails
from jonq.connections import ConnectionRecord
from jonq.scan_leads import find_scan_leads, is_scan_observation


def connection(timestamp, destination, line, *, port=443, protocol="tcp", outcome="no_reply"):
    return ConnectionRecord(
        Decimal(timestamp),
        f"198.51.100.{destination}",
        line,
        "zeek",
        ConnectionDetails(protocol, port, outcome, None),
    )


@pytest.mark.parametrize(("protocol", "port", "outcome", "expected"), [
    ("tcp", 443, "no_reply", True),
    ("tcp", 0, "rejected", True),
    ("tcp", 443, "established", False),
    ("tcp", 443, "unknown", False),
    ("tcp", None, "no_reply", False),
    ("udp", 443, "rejected", False),
    (None, 443, "no_reply", False),
])
def test_scan_observation_requires_tcp_port_and_failure_evidence(protocol, port, outcome, expected):
    assert is_scan_observation(ConnectionDetails(protocol, port, outcome, None)) is expected


def test_scan_lead_keeps_earliest_inclusive_peak_and_duplicate_evidence():
    source = "192.0.2.1"
    records = [
        connection("61.000007", 2, 1, outcome="rejected"),
        connection("1.000007", 1, 2),
        connection("61.000007", 3, 3),
        connection("61.000007", 2, 4),
        connection("31", 5, 5, outcome="established"),
        connection("61.000008", 4, 6),
        connection("61.000007", 6, 7, protocol="udp"),
        connection("61.000007", 7, 8, port=None),
    ]

    lead, = find_scan_leads({source: records}, window_seconds=60, min_destinations=3)

    assert (lead.src_ip, lead.dest_port) == (source, 443)
    assert lead.unique_destinations == 3
    assert (lead.window_start, lead.window_end) == (Decimal("1.000007"), Decimal("61.000007"))
    assert lead.destinations == [f"198.51.100.{item}" for item in (1, 2, 3)]
    assert lead.outcomes == {"rejected": 1, "no_reply": 3}
    assert lead.records == records[:4]


def test_scan_leads_are_separate_by_source_and_port_and_sort_by_breadth():
    sources = {
        "192.0.2.3": [connection("10", peer, peer, port=22) for peer in (1, 2)],
        "192.0.2.1": [
            connection("10", 1, 3, port=443),
            connection("10", 2, 4, port=443),
            connection("10", 1, 5, port=80),
            connection("10", 2, 6, port=80),
            connection("10", 3, 7, port=445),
            connection("10", 3, 8, port=445),
        ],
        "192.0.2.2": [connection("10", peer, peer + 8, port=22) for peer in (1, 2, 3)],
    }

    leads = find_scan_leads(sources, window_seconds=60, min_destinations=2)

    assert [(lead.src_ip, lead.dest_port, lead.unique_destinations) for lead in leads] == [
        ("192.0.2.2", 22, 3),
        ("192.0.2.1", 80, 2),
        ("192.0.2.1", 443, 2),
        ("192.0.2.3", 22, 2),
    ]
