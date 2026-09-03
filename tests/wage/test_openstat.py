from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from analytics_platform.domains.wage.ingestion.openstat import (
    MATRIX_SPEC_BY_ID,
    OpenSTATError,
    OpenSTATHTTPResult,
    acquire_matrix,
    canonical_request,
    decode_jsonstat,
    decode_jsonstat2,
    parse_matrix_metadata,
    request_id,
)
from analytics_platform.platform.ingestion.response_policy import ParsedResponseHeaders


FIXTURES = Path(__file__).parent / "fixtures"
PAY_SPEC = MATRIX_SPEC_BY_ID["0011B3E2001.px"]
BENCHMARK_SPEC = MATRIX_SPEC_BY_ID["0051B3E2005.px"]


def _fixture(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


def _clock():
    second = 0
    while True:
        yield f"2026-09-03T00:00:{second:02d}.000000Z"
        second += 1


class FixtureClient:
    def __init__(self, metadata: bytes, response: bytes, csv_response: bytes) -> None:
        self.metadata = metadata
        self.response = response
        self.csv_response = csv_response
        self.requests: list[tuple[str, str, bytes | None, tuple[str, ...]]] = []

    def request(
        self,
        method: str,
        endpoint: str,
        *,
        body: bytes | None = None,
        accepted_content_types: tuple[str, ...] = ("application/json",),
    ) -> OpenSTATHTTPResult:
        self.requests.append((method, endpoint, body, accepted_content_types))
        payload = (
            self.metadata
            if method == "GET"
            else self.csv_response
            if accepted_content_types == ("text/csv",)
            else self.response
        )
        content_type = (
            "text/csv" if accepted_content_types == ("text/csv",) else "application/json"
        )
        headers = ParsedResponseHeaders(
            content_type, len(payload), None, None, None, False
        )
        return OpenSTATHTTPResult(endpoint, 200, headers, payload)


def _decode(body: bytes, *, artifact: str = "a", extraction: str = "b"):
    metadata = parse_matrix_metadata(PAY_SPEC, _fixture("metadata_pay.json"))
    return decode_jsonstat(
        PAY_SPEC,
        metadata,
        body,
        artifact_id="artifact_" + artifact * 64,
        retrieval_id="retrieval_00000000-0000-4000-8000-000000000001",
        extraction_id="extraction_" + extraction * 64,
        request_identity="request_" + "c" * 64,
        loaded_at="2026-09-03T00:00:00.000000Z",
    )


def test_metadata_parsing_and_request_canonicalization_are_explicit() -> None:
    metadata = parse_matrix_metadata(PAY_SPEC, _fixture("metadata_pay.json"))
    first = canonical_request(metadata)
    second = canonical_request(metadata)

    assert [item.code for item in metadata.dimensions] == [
        "Industry",
        "Year",
        "Item",
    ]
    assert '"filter":"item"' in first
    assert '"values":["00","I"]' in first
    assert '"format":"json-stat"' in first
    assert first == second
    assert request_id(PAY_SPEC.endpoint, first) == request_id(
        PAY_SPEC.endpoint, second
    )


def test_metadata_rejects_dimension_shape_drift() -> None:
    with pytest.raises(OpenSTATError, match="OWS_METADATA_DIMENSIONS_UNEXPECTED"):
        parse_matrix_metadata(BENCHMARK_SPEC, _fixture("metadata_pay.json"))


def test_jsonstat_decoder_uses_dimension_metadata_and_retains_null_status() -> None:
    observations = _decode(_fixture("jsonstat_pay.json"))

    assert len(observations) == 4
    assert observations[0].industry_code == "00"
    assert observations[0].industry_name == "ALL INDUSTRIES"
    assert observations[0].measure_code == "WAGE"
    assert observations[0].observation_value == 21_543.64778619867
    assert observations[0].source_unit == '{"label":"Philippine peso"}'
    assert observations[1].observation_value is None
    assert observations[1].observation_status == "u"
    assert len({item.source_record_id for item in observations}) == 4
    assert len({item.logical_observation_id for item in observations}) == 4
    assert len({item.semantic_dataset_id for item in observations}) == 1


def test_benchmark_matrix_retains_sex_and_source_occupation_identity() -> None:
    metadata = parse_matrix_metadata(
        BENCHMARK_SPEC, _fixture("metadata_benchmark.json")
    )
    observations = decode_jsonstat(
        BENCHMARK_SPEC,
        metadata,
        _fixture("jsonstat_benchmark.json"),
        artifact_id="artifact_" + "a" * 64,
        retrieval_id="retrieval_00000000-0000-4000-8000-000000000001",
        extraction_id="extraction_" + "b" * 64,
        request_identity="request_" + "c" * 64,
        loaded_at="2026-09-03T00:00:00.000000Z",
    )

    assert len(observations) == 3
    assert [item.sex for item in observations] == ["BOTH SEXES", "MALE", "FEMALE"]
    assert all(item.occupation_code is None for item in observations)
    assert all(
        item.occupation_name == "General Office Clerks" for item in observations
    )
    assert all(item.measure == metadata.title for item in observations)


def test_observed_broken_jsonstat2_cardinality_is_rejected() -> None:
    metadata = parse_matrix_metadata(PAY_SPEC, _fixture("metadata_pay.json"))
    with pytest.raises(OpenSTATError, match="OWS_JSONSTAT_VALUES_INVALID"):
        decode_jsonstat2(
            PAY_SPEC,
            metadata,
            _fixture("broken_jsonstat2.json"),
            artifact_id="artifact_" + "a" * 64,
            retrieval_id="retrieval_00000000-0000-4000-8000-000000000001",
            extraction_id="extraction_" + "b" * 64,
            request_identity="request_" + "c" * 64,
            loaded_at="2026-09-03T00:00:00.000000Z",
        )


def test_semantic_identity_ignores_volatile_updated_metadata() -> None:
    original = _fixture("jsonstat_pay.json")
    changed_document = json.loads(original)
    changed_document["dataset"]["updated"] = "2026-09-03T14:07:09+08:00"
    changed = json.dumps(changed_document, separators=(",", ":")).encode()

    first = _decode(original, artifact="a", extraction="b")
    second = _decode(changed, artifact="d", extraction="e")

    assert hashlib.sha256(original).hexdigest() != hashlib.sha256(changed).hexdigest()
    assert first[0].source_record_id != second[0].source_record_id
    assert first[0].semantic_dataset_id == second[0].semantic_dataset_id
    assert [item.logical_observation_id for item in first] == [
        item.logical_observation_id for item in second
    ]


def test_acquisition_uses_v2_provenance_and_immutable_artifacts(tmp_path: Path) -> None:
    client = FixtureClient(
        _fixture("metadata_pay.json"),
        _fixture("jsonstat_pay.json"),
        _fixture("pay.csv"),
    )
    ticks = _clock()
    first = acquire_matrix(PAY_SPEC, tmp_path, client=client, clock=lambda: next(ticks))
    second = acquire_matrix(PAY_SPEC, tmp_path, client=client, clock=lambda: next(ticks))

    expected_hash = hashlib.sha256(_fixture("jsonstat_pay.json")).hexdigest()
    assert first.artifact.sha256_checksum == expected_hash
    assert first.artifact.identifier_version == "portfolio-v2"
    assert first.artifact_publication.outcome == "published"
    assert second.artifact_publication.outcome == "existing"
    assert first.request_id == second.request_id
    assert first.artifact.artifact_id == second.artifact.artifact_id
    assert first.extraction.extraction_batch_id == second.extraction.extraction_batch_id
    assert first.observations[0].semantic_dataset_id == second.observations[0].semantic_dataset_id
    assert [item.source_record_id for item in first.observations] == [
        item.source_record_id for item in second.observations
    ]
    assert first.retrieval.retrieval_run_id != second.retrieval.retrieval_run_id
    assert [item[0] for item in client.requests[:3]] == ["GET", "POST", "POST"]
    assert client.requests[1][2] == first.canonical_request.encode("utf-8")
    assert client.requests[2][3] == ("text/csv",)
    assert first.artifact_publication.artifact_path.read_bytes() == _fixture(
        "jsonstat_pay.json"
    )


def test_csv_disagreement_stops_acquisition(tmp_path: Path) -> None:
    client = FixtureClient(
        _fixture("metadata_pay.json"),
        _fixture("jsonstat_pay.json"),
        _fixture("pay.csv").replace(b"21544", b"99999", 1),
    )
    ticks = _clock()

    with pytest.raises(OpenSTATError, match="OWS_CROSSCHECK_VALUE_MISMATCH"):
        acquire_matrix(PAY_SPEC, tmp_path, client=client, clock=lambda: next(ticks))
