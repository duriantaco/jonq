from __future__ import annotations

from functools import lru_cache
from ipaddress import (
    IPv4Address,
    IPv4Network,
    IPv6Address,
    IPv6Network,
    ip_address,
    ip_network,
)


def parse_networks(values: list[str]) -> tuple[IPv4Network | IPv6Network, ...]:
    """Parse host addresses and CIDRs, rejecting CIDRs with host bits set."""
    return tuple(ip_network(_unscoped_ip_text(value), strict=True) for value in values)


def is_in_networks(address: str, networks: tuple[IPv4Network | IPv6Network, ...]) -> bool:
    """Match any configured network. An empty tuple leaves the address unrestricted."""
    if not networks:
        return True
    try:
        parsed, _ = _parse_ip(_unscoped_ip_text(address))
    except ValueError:
        return False
    return any(parsed in network for network in networks)


def canonical_ip(address: object) -> str:
    """Return the normalized form of an unscoped IP address."""
    _, canonical = _parse_ip(_unscoped_ip_text(address))
    return canonical


@lru_cache(maxsize=4096)
def _parse_ip(address: str) -> tuple[IPv4Address | IPv6Address, str]:
    parsed = ip_address(address)
    return parsed, str(parsed)


def _unscoped_ip_text(value: object) -> str:
    if not isinstance(value, str) or "%" in value:
        raise ValueError(f"Expected an unscoped IP address or CIDR, got {value!r}")
    return value.strip()
