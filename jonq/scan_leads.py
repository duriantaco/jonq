from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING

from jonq.connection_evidence import ConnectionDetails
from jonq.fanout import find_fanout

if TYPE_CHECKING:
    from jonq.connections import ConnectionRecord


@dataclass(frozen=True)
class ScanLead:
    src_ip: str
    dest_port: int
    unique_destinations: int
    window_start: Decimal
    window_end: Decimal
    destinations: list[str]
    outcomes: dict[str, int]
    records: list[ConnectionRecord]


def is_scan_observation(details: ConnectionDetails) -> bool:
    return _scan_port(details) is not None


def _scan_port(details: ConnectionDetails) -> int | None:
    if details.protocol == "tcp" and details.outcome in {"no_reply", "rejected"}:
        return details.dest_port
    return None


def find_scan_leads(
    by_source: Mapping[str, list[ConnectionRecord]],
    *,
    window_seconds: int,
    min_destinations: int,
) -> list[ScanLead]:
    """Find the earliest peak of recorded TCP failures for each source and port."""
    leads = []
    for source, records in by_source.items():
        by_port: dict[int, list[ConnectionRecord]] = defaultdict(list)
        for record in records:
            port = _scan_port(record.details)
            if port is not None:
                by_port[port].append(record)

        for port, observations in by_port.items():
            peaks = find_fanout(
                {source: ((row.timestamp, row.dest_ip) for row in observations)},
                window_seconds=window_seconds,
                min_destinations=min_destinations,
            )
            if not peaks:
                continue
            peak = peaks[0]
            evidence = [
                row for row in observations
                if peak.window_start <= row.timestamp <= peak.window_end
            ]
            leads.append(ScanLead(
                src_ip=source,
                dest_port=port,
                unique_destinations=peak.unique_destinations,
                window_start=peak.window_start,
                window_end=peak.window_end,
                destinations=peak.destinations,
                outcomes=dict(Counter(row.details.outcome for row in evidence)),
                records=evidence,
            ))

    return sorted(leads, key=lambda lead: (-lead.unique_destinations, lead.src_ip, lead.dest_port))
