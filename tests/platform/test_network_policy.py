from __future__ import annotations

import socket

import pytest

from analytics_platform.platform.ingestion.network_policy import (
    DestinationPolicyError,
    validate_connected_peer,
    validate_resolved_endpoints,
)


def _ipv4(address: str, port: int = 443):
    return (socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", (address, port))


def _ipv6(address: str, port: int = 443):
    return (
        socket.AF_INET6,
        socket.SOCK_STREAM,
        socket.IPPROTO_TCP,
        "",
        (address, port, 0, 0),
    )


def test_global_destinations_are_deduplicated_and_connection_attempts_are_bounded() -> None:
    results = [_ipv4("8.8.8.8"), _ipv4("8.8.8.8")]
    results.extend(_ipv4(address) for address in ("1.1.1.1", "9.9.9.9", "8.8.4.4", "1.0.0.1"))
    validated = validate_resolved_endpoints(results)
    assert len(validated.endpoints) == 5
    assert len(validated.connection_candidates) == 4
    endpoint = validated.endpoints[0]
    assert validate_connected_peer(endpoint, ("8.8.8.8", 443)) == endpoint.ip_address


@pytest.mark.parametrize(
    "row",
    [
        _ipv4("127.0.0.1"),
        _ipv4("10.0.0.1"),
        _ipv4("100.64.0.1"),
        _ipv4("192.0.2.1"),
        _ipv6("2001:db8::1"),
        _ipv6("::ffff:127.0.0.1"),
        _ipv6("2002:0808:0808::1"),
    ],
)
def test_non_global_or_transition_destinations_are_rejected(row) -> None:
    with pytest.raises(DestinationPolicyError):
        validate_resolved_endpoints([row])


def test_all_dns_answers_must_be_safe_and_peer_must_match() -> None:
    with pytest.raises(DestinationPolicyError):
        validate_resolved_endpoints([_ipv4("8.8.8.8"), _ipv4("127.0.0.1")])
    endpoint = validate_resolved_endpoints([_ipv4("8.8.8.8")]).endpoints[0]
    with pytest.raises(DestinationPolicyError):
        validate_connected_peer(endpoint, ("1.1.1.1", 443))


def test_dns_result_count_and_destination_port_are_bounded() -> None:
    with pytest.raises(DestinationPolicyError):
        validate_resolved_endpoints([_ipv4("8.8.8.8")] * 17)
    with pytest.raises(DestinationPolicyError):
        validate_resolved_endpoints([_ipv4("8.8.8.8", 80)])
