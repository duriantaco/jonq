from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Literal


Outcome = Literal["no_reply", "rejected", "established", "unknown"]

_PROTOCOL = re.compile(r"[A-Za-z][A-Za-z0-9_-]{0,31}")
_ICMP_PROTOCOLS = {"icmp", "icmpv6", "ipv6-icmp"}
_ZEEK_TCP_OUTCOMES: dict[str, Outcome] = {
    "S0": "no_reply",
    "REJ": "rejected",
    "SF": "established",
    "S1": "established",
    "S2": "established",
    "S3": "established",
    "RSTO": "established",
}
_ZEEK_STATES = _ZEEK_TCP_OUTCOMES.keys() | {
    "RSTR", "RSTOS0", "RSTRH", "SH", "SHR", "OTH",
}
_EVE_STATES = {"new", "established", "closed", "bypassed"}


@dataclass(frozen=True)
class ConnectionDetails:
    protocol: str | None
    dest_port: int | None
    outcome: Outcome
    state: str | None


def connection_details(event: dict, *, zeek: bool) -> ConnectionDetails:
    """Normalize optional evidence from a Zeek connection or EVE flow record."""
    protocol = _protocol_label(event.get("proto"))
    raw_port = event.get("id.resp_p" if zeek else "dest_port")
    dest_port = None
    # Zeek uses the port fields for ICMP message metadata.
    if protocol not in _ICMP_PROTOCOLS and type(raw_port) is int and 0 <= raw_port <= 65535:
        dest_port = raw_port

    outcome: Outcome = "unknown"
    if zeek:
        state = _state_label(event.get("conn_state"), _ZEEK_STATES, uppercase=True)
        if protocol == "tcp" and state is not None:
            outcome = _ZEEK_TCP_OUTCOMES.get(state, "unknown")
    else:
        flow = event.get("flow")
        if not isinstance(flow, dict):
            return ConnectionDetails(protocol, dest_port, outcome, None)
        state = _state_label(flow.get("state"), _EVE_STATES)
        if protocol == "tcp":
            packets = flow.get("pkts_toclient")
            no_reply = type(packets) is int and packets == 0
            if state == "established":
                if not no_reply:
                    outcome = "established"
            elif no_reply and state != "bypassed":
                outcome = "no_reply"

    return ConnectionDetails(protocol, dest_port, outcome, state)


def _protocol_label(value: object) -> str | None:
    if isinstance(value, str):
        label = value.strip()
        if _PROTOCOL.fullmatch(label):
            return label.lower()
    return None


def _state_label(value: object, known: set[str], *, uppercase: bool = False) -> str | None:
    if isinstance(value, str) and value.isascii():
        label = value.strip()
        label = label.upper() if uppercase else label.lower()
        if label in known:
            return label
    return None
