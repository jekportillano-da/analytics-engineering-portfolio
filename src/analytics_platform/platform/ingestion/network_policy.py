"""Pure destination-policy checks for numerically pinned transports."""

from __future__ import annotations

import ipaddress
import socket
from collections.abc import Iterable
from dataclasses import dataclass
from typing import TypeAlias


IPAddress: TypeAlias = ipaddress.IPv4Address | ipaddress.IPv6Address
SocketAddress: TypeAlias = tuple[str, int] | tuple[str, int, int, int]

_MAX_DNS_RESULTS = 16
_MAX_CONNECT_ATTEMPTS = 4
_HTTPS_PORT = 443
_IPV6_TRANSITION_NETWORKS = (
    ipaddress.ip_network("64:ff9b::/96"),
    ipaddress.ip_network("64:ff9b:1::/48"),
    ipaddress.ip_network("2001::/32"),
    ipaddress.ip_network("2002::/16"),
)


class DestinationPolicyError(ValueError):
    """Raised when resolution or a connected peer violates destination policy."""


@dataclass(frozen=True)
class ValidatedEndpoint:
    family: int
    socket_type: int
    protocol: int
    socket_address: SocketAddress
    ip_address: IPAddress
    normalized_ip_address: IPAddress
    port: int


@dataclass(frozen=True)
class ValidatedDestinationSet:
    endpoints: tuple[ValidatedEndpoint, ...]
    connection_candidates: tuple[ValidatedEndpoint, ...]


def _validate_port(value: object, field_name: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise DestinationPolicyError(f"{field_name} must be an integer")
    if not 1 <= value <= 65535:
        raise DestinationPolicyError(f"{field_name} is outside the valid range")
    return value


def _normalized_address(address: IPAddress) -> IPAddress:
    if isinstance(address, ipaddress.IPv6Address) and address.ipv4_mapped is not None:
        return address.ipv4_mapped
    return address


def _validate_global_address(value: object) -> tuple[IPAddress, IPAddress]:
    if not isinstance(value, str) or value == "" or "%" in value:
        raise DestinationPolicyError("destination address is malformed or scoped")
    try:
        address = ipaddress.ip_address(value)
    except ValueError as exc:
        raise DestinationPolicyError("destination address is malformed") from exc
    normalized = _normalized_address(address)
    prohibited_properties = (
        "is_unspecified",
        "is_loopback",
        "is_private",
        "is_link_local",
        "is_multicast",
        "is_reserved",
    )
    if (
        not address.is_global
        or not normalized.is_global
        or any(getattr(address, name) for name in prohibited_properties)
        or any(getattr(normalized, name) for name in prohibited_properties)
    ):
        raise DestinationPolicyError(
            "every resolved and connected destination must be globally reachable"
        )
    if isinstance(address, ipaddress.IPv6Address) and any(
        address in network for network in _IPV6_TRANSITION_NETWORKS
    ):
        raise DestinationPolicyError(
            "IPv6 transition and translation destinations are not approved"
        )
    return address, normalized


def _parse_socket_address(
    family: int,
    value: object,
    *,
    expected_port: int,
) -> tuple[SocketAddress, IPAddress, IPAddress]:
    if not isinstance(value, tuple):
        raise DestinationPolicyError("socket address must be a tuple")
    if family == socket.AF_INET:
        if len(value) != 2:
            raise DestinationPolicyError("IPv4 socket address shape is invalid")
        host, port = value
        _validate_port(port, "resolved port")
        if port != expected_port:
            raise DestinationPolicyError("resolved port does not match source policy")
        address, normalized = _validate_global_address(host)
        if not isinstance(address, ipaddress.IPv4Address):
            raise DestinationPolicyError("IPv4 family returned a non-IPv4 address")
        return (str(address), port), address, normalized
    if family == socket.AF_INET6:
        if len(value) != 4:
            raise DestinationPolicyError("IPv6 socket address shape is invalid")
        host, port, flowinfo, scope_id = value
        _validate_port(port, "resolved port")
        if port != expected_port:
            raise DestinationPolicyError("resolved port does not match source policy")
        if (
            not isinstance(flowinfo, int)
            or isinstance(flowinfo, bool)
            or not 0 <= flowinfo <= 1_048_575
        ):
            raise DestinationPolicyError("IPv6 flow information is invalid")
        if not isinstance(scope_id, int) or isinstance(scope_id, bool) or scope_id != 0:
            raise DestinationPolicyError("scoped IPv6 destinations are not approved")
        address, normalized = _validate_global_address(host)
        if not isinstance(address, ipaddress.IPv6Address):
            raise DestinationPolicyError("IPv6 family returned a non-IPv6 address")
        return (str(address), port, flowinfo, scope_id), address, normalized
    raise DestinationPolicyError("only IPv4 and IPv6 destination families are approved")


def validate_resolved_endpoints(
    results: Iterable[object],
    *,
    expected_port: int = _HTTPS_PORT,
) -> ValidatedDestinationSet:
    """Validate every getaddrinfo-shaped result before any connection attempt."""

    expected_port = _validate_port(expected_port, "expected port")
    if isinstance(results, (str, bytes, bytearray)):
        raise DestinationPolicyError("DNS results must be an iterable of address rows")
    endpoints: list[ValidatedEndpoint] = []
    seen: set[tuple[int, SocketAddress]] = set()
    result_count = 0
    try:
        iterator = iter(results)
    except TypeError as exc:
        raise DestinationPolicyError(
            "DNS results must be an iterable of address rows"
        ) from exc
    for raw_result in iterator:
        result_count += 1
        if result_count > _MAX_DNS_RESULTS:
            raise DestinationPolicyError("DNS answer exceeds the approved result limit")
        if not isinstance(raw_result, tuple) or len(raw_result) != 5:
            raise DestinationPolicyError("DNS result row shape is invalid")
        family, socket_type, protocol, canonical_name, socket_address = raw_result
        if (
            not isinstance(family, int)
            or isinstance(family, bool)
            or family not in (socket.AF_INET, socket.AF_INET6)
        ):
            raise DestinationPolicyError("DNS result family is not approved")
        if (
            not isinstance(socket_type, int)
            or isinstance(socket_type, bool)
            or socket_type != socket.SOCK_STREAM
        ):
            raise DestinationPolicyError("DNS result is not a stream endpoint")
        if (
            not isinstance(protocol, int)
            or isinstance(protocol, bool)
            or protocol not in (0, socket.IPPROTO_TCP)
        ):
            raise DestinationPolicyError("DNS result protocol is not TCP")
        if (
            not isinstance(canonical_name, str)
            or len(canonical_name) > 255
            or any(
                ord(character) < 32 or ord(character) == 127
                for character in canonical_name
            )
        ):
            raise DestinationPolicyError("DNS canonical name is malformed")
        canonical_socket_address, address, normalized = _parse_socket_address(
            family, socket_address, expected_port=expected_port
        )
        key = (family, canonical_socket_address)
        if key in seen:
            continue
        seen.add(key)
        endpoints.append(
            ValidatedEndpoint(
                family=family,
                socket_type=socket_type,
                protocol=protocol,
                socket_address=canonical_socket_address,
                ip_address=address,
                normalized_ip_address=normalized,
                port=expected_port,
            )
        )
    if result_count == 0 or not endpoints:
        raise DestinationPolicyError("DNS answer contains no approved destination")
    ordered = tuple(endpoints)
    return ValidatedDestinationSet(
        endpoints=ordered,
        connection_candidates=ordered[:_MAX_CONNECT_ATTEMPTS],
    )


def validate_connected_peer(
    endpoint: ValidatedEndpoint,
    peer_socket_address: object,
) -> IPAddress:
    """Require the connected peer to equal the selected validated endpoint."""

    if not isinstance(endpoint, ValidatedEndpoint):
        raise DestinationPolicyError("selected endpoint is invalid")
    _, _, normalized_peer = _parse_socket_address(
        endpoint.family,
        peer_socket_address,
        expected_port=endpoint.port,
    )
    if normalized_peer != endpoint.normalized_ip_address:
        raise DestinationPolicyError(
            "connected peer does not match the selected validated destination"
        )
    return normalized_peer
