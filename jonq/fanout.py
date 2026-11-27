from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class FanoutPeak:
    src_ip: str
    unique_destinations: int
    window_start: Decimal
    window_end: Decimal
    destinations: list[str]


def find_fanout(
    by_source: Mapping[str, Iterable[tuple[Decimal, str]]],
    *,
    window_seconds: int,
    min_destinations: int,
) -> list[FanoutPeak]:
    """Find the earliest peak of distinct destinations per source in an inclusive window."""
    peaks = []
    for src_ip, connections in by_source.items():
        ordered = sorted(connections)
        destination_counts: Counter[str] = Counter()
        left = 0
        best_count = min_destinations - 1
        best_bounds = None

        for right, (timestamp, destination) in enumerate(ordered):
            while timestamp - ordered[left][0] > window_seconds:
                expired_destination = ordered[left][1]
                destination_counts[expired_destination] -= 1
                if destination_counts[expired_destination] == 0:
                    del destination_counts[expired_destination]
                left += 1

            destination_counts[destination] += 1
            if len(destination_counts) > best_count:
                best_count = len(destination_counts)
                best_bounds = left, right

        if best_bounds is None:
            continue

        start, end = best_bounds
        destinations = sorted({destination for _, destination in ordered[start : end + 1]})
        peaks.append(
            FanoutPeak(
                src_ip=src_ip,
                unique_destinations=best_count,
                window_start=ordered[start][0],
                window_end=ordered[end][0],
                destinations=destinations,
            )
        )

    return sorted(peaks, key=lambda peak: (-peak.unique_destinations, peak.src_ip))
