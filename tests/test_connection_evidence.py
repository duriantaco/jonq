import pytest

from jonq.connection_evidence import ConnectionDetails, connection_details


@pytest.mark.parametrize(("state", "outcome"), [
    ("S0", "no_reply"),
    ("REJ", "rejected"),
    ("SF", "established"),
    ("S1", "established"),
    ("S2", "established"),
    ("S3", "established"),
    ("RSTO", "established"),
    ("RSTR", "unknown"),
    ("RSTOS0", "unknown"),
    ("OTH", "unknown"),
])
def test_zeek_details_normalize_only_supported_tcp_outcomes(state, outcome):
    event = {"proto": "TCP", "id.resp_p": 443, "conn_state": state}

    assert connection_details(event, zeek=True) == ConnectionDetails(
        "tcp", 443, outcome, state,
    )


@pytest.mark.parametrize(("flow", "outcome", "state"), [
    ({"state": "new", "pkts_toclient": 0}, "no_reply", "new"),
    ({"state": "established", "pkts_toclient": 1}, "established", "established"),
    ({"state": "established", "pkts_toclient": 0}, "unknown", "established"),
    ({"state": "closed", "pkts_toclient": 1}, "unknown", "closed"),
    ({"state": "bypassed", "pkts_toclient": 0}, "unknown", "bypassed"),
    ({"pkts_toclient": 0.0}, "unknown", None),
    ({"pkts_toclient": False}, "unknown", None),
    (None, "unknown", None),
])
def test_eve_details_use_tcp_flow_state_and_exact_packet_counts(flow, outcome, state):
    event = {"proto": "TCP", "dest_port": 443, "flow": flow}

    assert connection_details(event, zeek=False) == ConnectionDetails(
        "tcp", 443, outcome, state,
    )


def test_non_tcp_details_keep_valid_metadata_without_inferring_an_outcome():
    assert connection_details(
        {"proto": " UDP ", "id.resp_p": 53, "conn_state": "SF"}, zeek=True,
    ) == ConnectionDetails("udp", 53, "unknown", "SF")
    assert connection_details(
        {"proto": "icmp", "id.resp_p": 134, "conn_state": "OTH"}, zeek=True,
    ) == ConnectionDetails("icmp", None, "unknown", "OTH")
    assert connection_details(
        {"proto": "UDP", "dest_port": 53, "flow": {"pkts_toclient": 0}},
        zeek=False,
    ) == ConnectionDetails("udp", 53, "unknown", None)


@pytest.mark.parametrize("port", [True, "443", 443.0, -1, 65536])
def test_invalid_optional_details_are_omitted(port):
    event = {"proto": "\x1b[31mtcp", "id.resp_p": port, "conn_state": ["SF"]}

    assert connection_details(event, zeek=True) == ConnectionDetails(
        None, None, "unknown", None,
    )
