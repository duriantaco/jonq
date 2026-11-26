import pytest

from jonq.networks import canonical_ip, is_in_networks, parse_networks


def test_host_and_cidr_scopes_match_both_ip_families():
    networks = parse_networks([" 192.0.2.1 ", "198.51.100.0/24", "2001:db8::/48"])

    assert [str(network) for network in networks] == [
        "192.0.2.1/32",
        "198.51.100.0/24",
        "2001:db8::/48",
    ]
    assert is_in_networks("192.0.2.1", networks)
    assert is_in_networks("198.51.100.255", networks)
    assert is_in_networks("2001:0db8:0:1234::7", networks)
    assert not is_in_networks("192.0.2.2", networks)
    assert not is_in_networks("2001:db8:1::7", networks)
    assert not is_in_networks("::ffff:192.0.2.1", networks)


@pytest.mark.parametrize("value", ["bad-address", "192.0.2.1/24", "fe80::1%en0"])
def test_invalid_scope_raises_value_error(value):
    with pytest.raises(ValueError):
        parse_networks([value])


@pytest.mark.parametrize("address", ["invalid", "fe80::1%en0", None, 1])
def test_membership_rejects_invalid_addresses_when_scoped(address):
    assert not is_in_networks(address, parse_networks(["0.0.0.0/0", "::/0"]))
    assert is_in_networks(address, parse_networks([]))

    with pytest.raises(ValueError):
        canonical_ip(address)


def test_canonical_ip_normalizes_address_spellings():
    assert canonical_ip(" 2001:0DB8:0:0:0:0:0:1 ") == "2001:db8::1"
