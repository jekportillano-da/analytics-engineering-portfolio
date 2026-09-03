from __future__ import annotations

import io

import pytest

from analytics_platform.platform.ingestion.response_policy import (
    ResponsePolicyError,
    parse_response_headers,
    read_bounded_body,
)


def test_response_headers_are_canonicalized_without_source_semantics() -> None:
    parsed = parse_response_headers(
        [
            ("Content-Type", "Text/CSV; charset=utf-8"),
            ("Content-Length", "4"),
            ("ETag", '"abc"'),
            ("Last-Modified", "Mon, 10 Aug 2026 01:00:00 GMT"),
        ]
    )
    assert parsed.content_type == "text/csv"
    assert parsed.content_length == 4
    assert parsed.etag == '"abc"'
    assert not parsed.is_chunked


@pytest.mark.parametrize(
    "headers",
    [
        [("Content-Length", "4"), ("Content-Length", "4")],
        [("Content-Length", "04")],
        [("Transfer-Encoding", "gzip")],
        [("Transfer-Encoding", "chunked"), ("Content-Length", "4")],
        [("Content-Encoding", "gzip")],
        [("Bad Header", "value")],
        [("X-Test", "value\r\ninjected")],
    ],
)
def test_unsafe_or_ambiguous_response_headers_are_rejected(headers) -> None:
    with pytest.raises(ResponsePolicyError) as error:
        parse_response_headers(headers)
    assert error.value.error_code == "RESPONSE_HEADERS_INVALID"


def test_header_and_body_size_limits_are_enforced() -> None:
    with pytest.raises(ResponsePolicyError) as error:
        parse_response_headers([("Content-Length", "5")], max_response_bytes=4)
    assert error.value.error_code == "RESPONSE_TOO_LARGE"
    with pytest.raises(ResponsePolicyError) as error:
        read_bounded_body(io.BytesIO(b"12345"), max_response_bytes=4)
    assert error.value.error_code == "RESPONSE_TOO_LARGE"


def test_body_length_is_verified_and_binary_data_is_returned() -> None:
    assert read_bounded_body(
        io.BytesIO(b"1234"), content_length=4, max_response_bytes=4, chunk_size=2
    ) == b"1234"
    with pytest.raises(ResponsePolicyError) as error:
        read_bounded_body(io.BytesIO(b"123"), content_length=4)
    assert error.value.error_code == "RESPONSE_LENGTH_MISMATCH"
    with pytest.raises(ResponsePolicyError) as error:
        read_bounded_body(io.BytesIO(b"12345"), content_length=4)
    assert error.value.error_code == "RESPONSE_LENGTH_MISMATCH"
