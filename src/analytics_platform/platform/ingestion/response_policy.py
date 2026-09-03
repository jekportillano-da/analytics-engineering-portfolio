"""Bounded, source-neutral HTTP response metadata and body validation."""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from typing import BinaryIO


MAX_RESPONSE_HEADER_FIELDS = 100
MAX_RESPONSE_HEADER_BYTES = 64 * 1024
DEFAULT_MAX_RESPONSE_BYTES = 8 * 1024 * 1024

_HEADER_NAME = re.compile(r"^[!#$%&'*+.^_`|~0-9A-Za-z-]+$")
_MEDIA_TYPE = re.compile(
    r"^[!#$%&'*+.^_`|~0-9A-Za-z-]+/[!#$%&'*+.^_`|~0-9A-Za-z-]+$"
)
_CANONICAL_CONTENT_LENGTH = re.compile(r"^(?:0|[1-9][0-9]*)$")
_SINGLETON_HEADERS = frozenset(
    {
        "content-encoding",
        "content-length",
        "content-type",
        "etag",
        "last-modified",
        "location",
        "transfer-encoding",
    }
)


class ResponsePolicyError(RuntimeError):
    """Controlled response-policy failure with no untrusted diagnostic text."""

    def __init__(self, error_code: str) -> None:
        super().__init__(error_code)
        self.error_code = error_code


@dataclass(frozen=True)
class ParsedResponseHeaders:
    content_type: str | None
    content_length: int | None
    etag: str | None
    last_modified: str | None
    location: str | None
    is_chunked: bool


def _positive_limit(value: int, field_name: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise ValueError(f"{field_name} must be a positive integer")
    return value


def parse_response_headers(
    raw_headers: Iterable[tuple[object, object]],
    *,
    max_response_bytes: int = DEFAULT_MAX_RESPONSE_BYTES,
) -> ParsedResponseHeaders:
    """Apply bounded syntax, singleton, coding, and framing policy."""

    max_response_bytes = _positive_limit(max_response_bytes, "max_response_bytes")
    fields: dict[str, list[str]] = {}
    aggregate_size = 0
    count = 0
    try:
        iterator = iter(raw_headers)
    except TypeError as exc:
        raise ResponsePolicyError("RESPONSE_HEADERS_INVALID") from exc
    for item in iterator:
        count += 1
        if count > MAX_RESPONSE_HEADER_FIELDS:
            raise ResponsePolicyError("RESPONSE_HEADERS_INVALID")
        if not isinstance(item, tuple) or len(item) != 2:
            raise ResponsePolicyError("RESPONSE_HEADERS_INVALID")
        name, value = item
        if (
            not isinstance(name, str)
            or _HEADER_NAME.fullmatch(name) is None
            or not isinstance(value, str)
            or value == ""
            or any(ord(character) < 32 or ord(character) == 127 for character in value)
        ):
            raise ResponsePolicyError("RESPONSE_HEADERS_INVALID")
        aggregate_size += len(name.encode("ascii")) + len(value.encode("utf-8")) + 4
        if aggregate_size > MAX_RESPONSE_HEADER_BYTES:
            raise ResponsePolicyError("RESPONSE_HEADERS_INVALID")
        fields.setdefault(name.lower(), []).append(value)
    for name in _SINGLETON_HEADERS:
        if len(fields.get(name, ())) > 1:
            raise ResponsePolicyError("RESPONSE_HEADERS_INVALID")
    if any(len(values) > 1 and len(set(values)) > 1 for values in fields.values()):
        raise ResponsePolicyError("RESPONSE_HEADERS_INVALID")

    def singleton(name: str) -> str | None:
        values = fields.get(name, ())
        return values[0] if values else None

    raw_content_type = singleton("content-type")
    content_type = None
    if raw_content_type is not None:
        if len(raw_content_type) > 255:
            raise ResponsePolicyError("RESPONSE_HEADERS_INVALID")
        media_type = raw_content_type.split(";", 1)[0].strip().lower()
        if _MEDIA_TYPE.fullmatch(media_type) is None:
            raise ResponsePolicyError("RESPONSE_HEADERS_INVALID")
        content_type = media_type
    content_encoding = singleton("content-encoding")
    if content_encoding is not None and content_encoding.strip().lower() != "identity":
        raise ResponsePolicyError("RESPONSE_HEADERS_INVALID")
    transfer_encoding = singleton("transfer-encoding")
    is_chunked = False
    if transfer_encoding is not None:
        if transfer_encoding.strip().lower() != "chunked":
            raise ResponsePolicyError("RESPONSE_HEADERS_INVALID")
        is_chunked = True
    raw_content_length = singleton("content-length")
    content_length = None
    if raw_content_length is not None:
        if _CANONICAL_CONTENT_LENGTH.fullmatch(raw_content_length) is None:
            raise ResponsePolicyError("RESPONSE_HEADERS_INVALID")
        content_length = int(raw_content_length)
        if content_length > max_response_bytes:
            raise ResponsePolicyError("RESPONSE_TOO_LARGE")
    if is_chunked and content_length is not None:
        raise ResponsePolicyError("RESPONSE_HEADERS_INVALID")
    etag = singleton("etag")
    last_modified = singleton("last-modified")
    location = singleton("location")
    if any(value is not None and len(value) > 2048 for value in (etag, last_modified, location)):
        raise ResponsePolicyError("RESPONSE_HEADERS_INVALID")
    return ParsedResponseHeaders(
        content_type,
        content_length,
        etag,
        last_modified,
        location,
        is_chunked,
    )


def read_bounded_body(
    source: BinaryIO,
    *,
    content_length: int | None = None,
    max_response_bytes: int = DEFAULT_MAX_RESPONSE_BYTES,
    chunk_size: int = 64 * 1024,
) -> bytes:
    """Read a body with strict declared-length and absolute-size enforcement."""

    max_response_bytes = _positive_limit(max_response_bytes, "max_response_bytes")
    chunk_size = _positive_limit(chunk_size, "chunk_size")
    if content_length is not None and (
        not isinstance(content_length, int)
        or isinstance(content_length, bool)
        or content_length < 0
    ):
        raise ValueError("content_length must be a nonnegative integer or None")
    if content_length is not None and content_length > max_response_bytes:
        raise ResponsePolicyError("RESPONSE_TOO_LARGE")
    body = bytearray()
    while True:
        chunk = source.read(min(chunk_size, max_response_bytes - len(body) + 1))
        if chunk == b"":
            break
        if not isinstance(chunk, bytes):
            raise ResponsePolicyError("RESPONSE_BODY_INVALID")
        body.extend(chunk)
        if len(body) > max_response_bytes:
            raise ResponsePolicyError("RESPONSE_TOO_LARGE")
        if content_length is not None and len(body) > content_length:
            raise ResponsePolicyError("RESPONSE_LENGTH_MISMATCH")
    if content_length is not None and len(body) != content_length:
        raise ResponsePolicyError("RESPONSE_LENGTH_MISMATCH")
    return bytes(body)
