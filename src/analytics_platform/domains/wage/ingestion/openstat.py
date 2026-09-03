"""Secure PSA OpenSTAT acquisition, JSON-stat2 decoding, and V2 provenance."""

from __future__ import annotations

import hashlib
import http.client
import io
import itertools
import json
import math
import socket
import ssl
import time
import csv
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, replace
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from analytics_platform.domains.wage.ingestion.raw import (
    OWSIngestionRunRecord,
    OWSMatrixMetadataRecord,
    OWSObservation,
)
from analytics_platform.platform.ingestion.network_policy import (
    DestinationPolicyError,
    validate_connected_peer,
    validate_resolved_endpoints,
)
from analytics_platform.platform.ingestion.response_policy import (
    DEFAULT_MAX_RESPONSE_BYTES,
    ParsedResponseHeaders,
    ResponsePolicyError,
    parse_response_headers,
    read_bounded_body,
)
from analytics_platform.platform.provenance.artifacts import (
    ArtifactPublicationResult,
    ArtifactPublisher,
)
from analytics_platform.platform.provenance.identifiers import raw_record_id_v2
from analytics_platform.platform.provenance.lifecycle import (
    ArtifactProvenance,
    ExtractionRun,
    RetrievalResponse,
    RetrievalRun,
    complete_retrieval,
    finish_extraction,
    start_extraction,
    start_retrieval,
    utc_now_text,
)


OPENSTAT_BASE_URL = (
    "https://openstat.psa.gov.ph/PXWeb/api/v1/en/DB/1B/OWS/O10/"
)
OPENSTAT_HOST = "openstat.psa.gov.ph"
SOURCE_PUBLISHER = "Philippine Statistics Authority"
REQUESTED_FORMAT = "json-stat"
VALIDATION_FORMAT = "csv"
OUTPUT_CONTRACT_VERSION = "psa-ows-observations-v2"
EXTRACTOR_NAME = "psa_openstat_jsonstat"
EXTRACTOR_VERSION = "2.0.0"
IDENTIFIER_VERSION = "portfolio-v2"
MAX_REQUEST_BYTES = 64 * 1024
CONNECT_TIMEOUT_SECONDS = 15.0
READ_TIMEOUT_SECONDS = 30.0


class OpenSTATError(RuntimeError):
    """Controlled source acquisition or contract failure."""


@dataclass(frozen=True)
class OWSMatrixSpec:
    matrix_id: str
    description: str
    expected_dimensions: tuple[str, ...]
    axis_dimension: str
    measure_dimension: str | None
    benchmark_occupation: str | None = None

    @property
    def endpoint(self) -> str:
        return f"{OPENSTAT_BASE_URL}{self.matrix_id}"

    @property
    def source_id(self) -> str:
        stem = self.matrix_id.removesuffix(".px").lower()
        return f"psa_openstat_ows_{stem}"


MATRIX_SPECS = (
    OWSMatrixSpec(
        "0011B3E2001.px",
        "Pay, allowance, and wage rates by industry",
        ("Industry", "Year", "Item"),
        "Industry",
        "Item",
    ),
    OWSMatrixSpec(
        "0021B3E2002.px",
        "Pay, allowance, and wage rates by region",
        ("Region", "Year", "Item"),
        "Region",
        "Item",
    ),
    OWSMatrixSpec(
        "0051B3E2005.px",
        "General Office Clerks by sex and industry",
        ("Industry", "Year", "Sex"),
        "Industry",
        None,
        "General Office Clerks",
    ),
    OWSMatrixSpec(
        "0071B3E2007.px",
        "Elementary Occupations by sex and industry",
        ("Industry", "Year", "Sex"),
        "Industry",
        None,
        "Elementary Occupations",
    ),
)
MATRIX_SPEC_BY_ID = {spec.matrix_id: spec for spec in MATRIX_SPECS}


@dataclass(frozen=True)
class OpenSTATHTTPResult:
    endpoint: str
    status_code: int
    headers: ParsedResponseHeaders
    body: bytes


@dataclass(frozen=True)
class DimensionMetadata:
    code: str
    label: str
    category_codes: tuple[str, ...]
    category_labels: tuple[str, ...]


@dataclass(frozen=True)
class ParsedMatrixMetadata:
    matrix_id: str
    title: str
    dimensions: tuple[DimensionMetadata, ...]
    document: Mapping[str, Any]

    @property
    def reference_year(self) -> int:
        year = next(item for item in self.dimensions if item.code == "Year")
        if len(year.category_codes) != 1:
            raise OpenSTATError("OWS_METADATA_YEAR_SCOPE_INVALID")
        try:
            value = int(year.category_labels[0])
        except ValueError as exc:
            raise OpenSTATError("OWS_METADATA_YEAR_SCOPE_INVALID") from exc
        if value != 2024:
            raise OpenSTATError("OWS_METADATA_YEAR_SCOPE_INVALID")
        return value


@dataclass(frozen=True)
class AcquiredMatrix:
    spec: OWSMatrixSpec
    metadata: ParsedMatrixMetadata
    canonical_request: str
    request_id: str
    retrieval: RetrievalRun
    artifact: ArtifactProvenance
    artifact_publication: ArtifactPublicationResult
    extraction: ExtractionRun
    observations: tuple[OWSObservation, ...]
    matrix_metadata: OWSMatrixMetadataRecord
    ingestion_run: OWSIngestionRunRecord


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise OpenSTATError("OWS_JSON_DUPLICATE_KEY")
        value[key] = item
    return value


def _reject_constant(_: str) -> None:
    raise OpenSTATError("OWS_JSON_NONFINITE_NUMBER")


def parse_json_document(body: bytes) -> Mapping[str, Any]:
    try:
        value = json.loads(
            body.decode("utf-8-sig"),
            object_pairs_hook=_unique_object,
            parse_constant=_reject_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise OpenSTATError("OWS_JSON_INVALID") from exc
    if not isinstance(value, dict):
        raise OpenSTATError("OWS_JSON_ROOT_INVALID")
    return value


def canonical_json(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def parse_matrix_metadata(spec: OWSMatrixSpec, body: bytes) -> ParsedMatrixMetadata:
    document = parse_json_document(body)
    title = document.get("title")
    variables = document.get("variables")
    if not isinstance(title, str) or not title.strip() or not isinstance(variables, list):
        raise OpenSTATError("OWS_METADATA_INVALID")
    dimensions: list[DimensionMetadata] = []
    seen: set[str] = set()
    for variable in variables:
        if not isinstance(variable, dict):
            raise OpenSTATError("OWS_METADATA_INVALID")
        code = variable.get("code")
        label = variable.get("text")
        codes = variable.get("values")
        labels = variable.get("valueTexts")
        if (
            not isinstance(code, str)
            or not code
            or code in seen
            or not isinstance(label, str)
            or not label
            or not isinstance(codes, list)
            or not isinstance(labels, list)
            or len(codes) != len(labels)
            or not codes
            or any(not isinstance(item, str) or not item for item in codes)
            or any(not isinstance(item, str) or not item for item in labels)
            or len(set(codes)) != len(codes)
        ):
            raise OpenSTATError("OWS_METADATA_INVALID")
        seen.add(code)
        dimensions.append(
            DimensionMetadata(code, label, tuple(codes), tuple(labels))
        )
    observed_codes = tuple(item.code for item in dimensions)
    if observed_codes != spec.expected_dimensions:
        raise OpenSTATError("OWS_METADATA_DIMENSIONS_UNEXPECTED")
    parsed = ParsedMatrixMetadata(spec.matrix_id, title, tuple(dimensions), document)
    parsed.reference_year
    return parsed


def build_explicit_request(
    metadata: ParsedMatrixMetadata, response_format: str = REQUESTED_FORMAT
) -> dict[str, object]:
    return {
        "query": [
            {
                "code": dimension.code,
                "selection": {
                    "filter": "item",
                    "values": list(dimension.category_codes),
                },
            }
            for dimension in metadata.dimensions
        ],
        "response": {"format": response_format},
    }


def canonical_request(metadata: ParsedMatrixMetadata) -> str:
    return canonical_json(build_explicit_request(metadata))


def request_id(endpoint: str, canonical_request_text: str) -> str:
    payload = f"{endpoint}\n{canonical_request_text}".encode("utf-8")
    return f"request_{hashlib.sha256(payload).hexdigest()}"


def _validated_request_target(endpoint: str) -> str:
    parsed = urlsplit(endpoint)
    expected_prefix = "/PXWeb/api/v1/en/DB/1B/OWS/O10/"
    if (
        parsed.scheme != "https"
        or parsed.hostname != OPENSTAT_HOST
        or parsed.port not in (None, 443)
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
        or not parsed.path.startswith(expected_prefix)
        or parsed.path.count("/") != expected_prefix.count("/")
        or parsed.path.rsplit("/", 1)[-1] not in MATRIX_SPEC_BY_ID
    ):
        raise OpenSTATError("OWS_ENDPOINT_REJECTED")
    return parsed.path


class OpenSTATHTTPClient:
    """Proxy-free HTTPS client with validated DNS, peer, TLS, and response bounds."""

    def __init__(
        self,
        *,
        resolver: Callable[..., list[object]] | None = None,
        socket_factory: Callable[..., socket.socket] | None = None,
        context_factory: Callable[[], ssl.SSLContext] | None = None,
        monotonic: Callable[[], float] = time.monotonic,
        sleeper: Callable[[float], None] = time.sleep,
        minimum_request_interval_seconds: float = 1.05,
    ) -> None:
        self._resolver = resolver or socket.getaddrinfo
        self._socket_factory = socket_factory or socket.socket
        self._context_factory = context_factory or ssl.create_default_context
        self._monotonic = monotonic
        self._sleeper = sleeper
        self._minimum_request_interval_seconds = minimum_request_interval_seconds
        self._last_request_started: float | None = None

    def _respect_rate_limit(self) -> None:
        if self._minimum_request_interval_seconds < 0:
            raise OpenSTATError("OWS_RATE_LIMIT_CONFIGURATION_INVALID")
        now = self._monotonic()
        if self._last_request_started is not None:
            remaining = (
                self._minimum_request_interval_seconds
                - (now - self._last_request_started)
            )
            if remaining > 0:
                self._sleeper(remaining)
                now = self._monotonic()
        self._last_request_started = now

    def _connect(self) -> socket.socket:
        try:
            resolved = self._resolver(
                OPENSTAT_HOST,
                443,
                family=socket.AF_UNSPEC,
                type=socket.SOCK_STREAM,
                proto=socket.IPPROTO_TCP,
            )
            destinations = validate_resolved_endpoints(resolved, expected_port=443)
        except (OSError, DestinationPolicyError) as exc:
            raise OpenSTATError("OWS_DESTINATION_REJECTED") from exc

        for endpoint in destinations.connection_candidates:
            raw_socket: socket.socket | None = None
            tls_socket: socket.socket | None = None
            try:
                raw_socket = self._socket_factory(
                    endpoint.family, endpoint.socket_type, endpoint.protocol
                )
                raw_socket.settimeout(CONNECT_TIMEOUT_SECONDS)
                raw_socket.connect(endpoint.socket_address)
                validate_connected_peer(endpoint, raw_socket.getpeername())
                context = self._context_factory()
                context.minimum_version = ssl.TLSVersion.TLSv1_2
                if not context.check_hostname or context.verify_mode != ssl.CERT_REQUIRED:
                    raise OpenSTATError("OWS_TLS_VERIFICATION_FAILED")
                tls_socket = context.wrap_socket(
                    raw_socket, server_hostname=OPENSTAT_HOST
                )
                raw_socket = None
                validate_connected_peer(endpoint, tls_socket.getpeername())
                tls_socket.settimeout(READ_TIMEOUT_SECONDS)
                return tls_socket
            except OpenSTATError:
                if tls_socket is not None:
                    tls_socket.close()
                if raw_socket is not None:
                    raw_socket.close()
                raise
            except (OSError, ssl.SSLError, DestinationPolicyError):
                if tls_socket is not None:
                    tls_socket.close()
                if raw_socket is not None:
                    raw_socket.close()
        raise OpenSTATError("OWS_CONNECTION_FAILED")

    def request(
        self,
        method: str,
        endpoint: str,
        *,
        body: bytes | None = None,
        accepted_content_types: tuple[str, ...] = ("application/json",),
    ) -> OpenSTATHTTPResult:
        if method not in ("GET", "POST"):
            raise OpenSTATError("OWS_METHOD_REJECTED")
        request_target = _validated_request_target(endpoint)
        if method == "GET" and body is not None:
            raise OpenSTATError("OWS_REQUEST_INVALID")
        if method == "POST" and (body is None or len(body) > MAX_REQUEST_BYTES):
            raise OpenSTATError("OWS_REQUEST_INVALID")

        if not accepted_content_types:
            raise OpenSTATError("OWS_MEDIA_TYPE_REJECTED")
        self._respect_rate_limit()
        tls_socket = self._connect()
        connection = http.client.HTTPConnection(OPENSTAT_HOST, 443)
        connection.sock = tls_socket
        response: http.client.HTTPResponse | None = None
        try:
            connection.putrequest(
                method, request_target, skip_host=True, skip_accept_encoding=True
            )
            connection.putheader("Host", OPENSTAT_HOST)
            connection.putheader("Accept", ", ".join(accepted_content_types))
            connection.putheader("Accept-Encoding", "identity")
            connection.putheader("Connection", "close")
            connection.putheader(
                "User-Agent", "AnalyticsEngineeringPortfolio/0.1 PSA-OpenSTAT"
            )
            if body is not None:
                connection.putheader("Content-Type", "application/json; charset=utf-8")
                connection.putheader("Content-Length", str(len(body)))
            connection.endheaders(body)
            response = connection.getresponse()
            parsed_headers = parse_response_headers(
                tuple(response.headers.raw_items()),
                max_response_bytes=DEFAULT_MAX_RESPONSE_BYTES,
            )
            response_body = read_bounded_body(
                response,
                content_length=parsed_headers.content_length,
                max_response_bytes=DEFAULT_MAX_RESPONSE_BYTES,
            )
            if response.status != 200:
                raise OpenSTATError("OWS_RESPONSE_STATUS")
            if parsed_headers.location is not None:
                raise OpenSTATError("OWS_REDIRECT_REJECTED")
            if parsed_headers.content_type not in accepted_content_types:
                raise OpenSTATError("OWS_MEDIA_TYPE_REJECTED")
            if not response_body:
                raise OpenSTATError("OWS_EMPTY_RESPONSE")
            return OpenSTATHTTPResult(
                endpoint, response.status, parsed_headers, response_body
            )
        except OpenSTATError:
            raise
        except (OSError, http.client.HTTPException, ResponsePolicyError) as exc:
            raise OpenSTATError("OWS_RESPONSE_INVALID") from exc
        finally:
            if response is not None:
                response.close()
            connection.close()


def _ordered_category_codes(
    dimension: Mapping[str, Any], expected_size: int
) -> tuple[str, ...]:
    category = dimension.get("category")
    if not isinstance(category, dict):
        raise OpenSTATError("OWS_JSONSTAT_DIMENSION_INVALID")
    index = category.get("index")
    if isinstance(index, list):
        codes = tuple(index)
    elif isinstance(index, dict):
        ordered: list[str | None] = [None] * expected_size
        for code, position in index.items():
            if (
                not isinstance(code, str)
                or not isinstance(position, int)
                or isinstance(position, bool)
                or not 0 <= position < expected_size
                or ordered[position] is not None
            ):
                raise OpenSTATError("OWS_JSONSTAT_DIMENSION_INVALID")
            ordered[position] = code
        if any(code is None for code in ordered):
            raise OpenSTATError("OWS_JSONSTAT_DIMENSION_INVALID")
        codes = tuple(code for code in ordered if code is not None)
    else:
        raise OpenSTATError("OWS_JSONSTAT_DIMENSION_INVALID")
    if (
        len(codes) != expected_size
        or len(set(codes)) != len(codes)
        or any(not isinstance(code, str) or not code for code in codes)
    ):
        raise OpenSTATError("OWS_JSONSTAT_DIMENSION_INVALID")
    return codes


def _category_label(dimension: Mapping[str, Any], code: str) -> str | None:
    category = dimension.get("category")
    labels = category.get("label") if isinstance(category, dict) else None
    if labels is None:
        return None
    if not isinstance(labels, dict):
        raise OpenSTATError("OWS_JSONSTAT_DIMENSION_INVALID")
    label = labels.get(code)
    if label is not None and not isinstance(label, str):
        raise OpenSTATError("OWS_JSONSTAT_DIMENSION_INVALID")
    return label


def _source_unit(dimension: Mapping[str, Any], code: str) -> str | None:
    category = dimension.get("category")
    units = category.get("unit") if isinstance(category, dict) else None
    if units is None:
        return None
    if not isinstance(units, dict):
        raise OpenSTATError("OWS_JSONSTAT_DIMENSION_INVALID")
    unit = units.get(code)
    if unit is None:
        return None
    return unit if isinstance(unit, str) else canonical_json(unit)


def _indexed_value(value: object, ordinal: int, total: int) -> object:
    if isinstance(value, list):
        if len(value) != total:
            raise OpenSTATError("OWS_JSONSTAT_VALUES_INVALID")
        return value[ordinal]
    if isinstance(value, dict):
        return value.get(str(ordinal))
    raise OpenSTATError("OWS_JSONSTAT_VALUES_INVALID")


def _observation_value(value: object) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise OpenSTATError("OWS_JSONSTAT_VALUE_INVALID")
    converted = float(value)
    if not math.isfinite(converted):
        raise OpenSTATError("OWS_JSONSTAT_VALUE_INVALID")
    return converted


def _semantic_dataset_identity(observations: Sequence[OWSObservation]) -> str:
    semantic_rows = [
        {
            "geography_code": item.geography_code,
            "geography_name": item.geography_name,
            "geography_type": item.geography_type,
            "industry_code": item.industry_code,
            "industry_name": item.industry_name,
            "matrix_id": item.matrix_id,
            "measure": item.measure,
            "measure_code": item.measure_code,
            "observation_status": item.observation_status,
            "observation_value": item.observation_value,
            "occupation_code": item.occupation_code,
            "occupation_name": item.occupation_name,
            "reference_year": item.reference_year,
            "sex": item.sex,
            "sex_code": item.sex_code,
            "source_publisher": item.source_publisher,
            "source_record_locator": item.source_record_locator,
            "source_unit": item.source_unit,
        }
        for item in sorted(observations, key=lambda row: row.source_record_locator)
    ]
    digest = hashlib.sha256(canonical_json(semantic_rows).encode("utf-8")).hexdigest()
    return f"semantic_{digest}"


def _logical_observation_identity(
    semantic_dataset_id: str, source_record_locator: str
) -> str:
    payload = f"{semantic_dataset_id}\n{source_record_locator}".encode("utf-8")
    return f"observation_{hashlib.sha256(payload).hexdigest()}"


def _decode_dimensional_dataset(
    spec: OWSMatrixSpec,
    metadata: ParsedMatrixMetadata,
    dataset: Mapping[str, Any],
    dimension_ids: object,
    sizes: object,
    dimensions: object,
    *,
    artifact_id: str,
    retrieval_id: str,
    extraction_id: str,
    request_identity: str,
    loaded_at: str,
) -> tuple[OWSObservation, ...]:
    values = dataset.get("value")
    if (
        not isinstance(dimension_ids, list)
        or tuple(dimension_ids) != spec.expected_dimensions
        or not isinstance(sizes, list)
        or len(sizes) != len(dimension_ids)
        or any(
            not isinstance(size, int) or isinstance(size, bool) or size <= 0
            for size in sizes
        )
        or not isinstance(dimensions, dict)
    ):
        raise OpenSTATError("OWS_JSONSTAT_STRUCTURE_INVALID")
    publisher = dataset.get("source")
    if publisher != SOURCE_PUBLISHER:
        raise OpenSTATError("OWS_JSONSTAT_SOURCE_INVALID")
    title = dataset.get("label")
    if not isinstance(title, str) or not title:
        title = metadata.title
    source_updated_at = dataset.get("updated")
    if source_updated_at is not None and not isinstance(source_updated_at, str):
        raise OpenSTATError("OWS_JSONSTAT_STRUCTURE_INVALID")

    dimension_codes: list[tuple[str, ...]] = []
    for dimension_id, size in zip(dimension_ids, sizes, strict=True):
        dimension = dimensions.get(dimension_id)
        if not isinstance(dimension, dict):
            raise OpenSTATError("OWS_JSONSTAT_DIMENSION_INVALID")
        dimension_codes.append(_ordered_category_codes(dimension, size))
    total = math.prod(sizes)
    if not isinstance(values, (list, dict)):
        raise OpenSTATError("OWS_JSONSTAT_VALUES_INVALID")
    statuses = dataset.get("status", {})
    if not isinstance(statuses, (list, dict)):
        raise OpenSTATError("OWS_JSONSTAT_STATUS_INVALID")

    observations: list[OWSObservation] = []
    for ordinal, category_codes in enumerate(itertools.product(*dimension_codes)):
        selected = dict(zip(dimension_ids, category_codes, strict=True))
        category_labels = {
            dimension_id: _category_label(dimensions[dimension_id], code)
            for dimension_id, code in selected.items()
        }
        year_code = selected.get("Year")
        year_label = category_labels.get("Year")
        try:
            reference_year = int(year_label or year_code or "")
        except ValueError as exc:
            raise OpenSTATError("OWS_JSONSTAT_YEAR_INVALID") from exc
        if reference_year != metadata.reference_year:
            raise OpenSTATError("OWS_JSONSTAT_YEAR_INVALID")

        measure_code = (
            selected.get(spec.measure_dimension) if spec.measure_dimension else None
        )
        measure = (
            category_labels.get(spec.measure_dimension)
            if spec.measure_dimension
            else title
        )
        if not isinstance(measure, str) or not measure:
            raise OpenSTATError("OWS_JSONSTAT_MEASURE_INVALID")
        source_unit = (
            _source_unit(dimensions[spec.measure_dimension], measure_code)
            if spec.measure_dimension and measure_code is not None
            else None
        )
        status_value = _indexed_value(statuses, ordinal, total)
        if status_value is not None and not isinstance(status_value, str):
            raise OpenSTATError("OWS_JSONSTAT_STATUS_INVALID")
        locator = canonical_json(
            {
                "dimensions": [
                    {"code": selected[item], "id": item} for item in dimension_ids
                ],
                "matrix_id": spec.matrix_id,
            }
        )
        observations.append(
            OWSObservation(
                source_record_id=raw_record_id_v2(extraction_id, locator),
                logical_observation_id="",
                semantic_dataset_id="",
                matrix_id=spec.matrix_id,
                matrix_title=title,
                reference_year=reference_year,
                geography_type="region" if spec.axis_dimension == "Region" else None,
                geography_code=selected.get("Region"),
                geography_name=category_labels.get("Region"),
                industry_code=selected.get("Industry"),
                industry_name=category_labels.get("Industry"),
                occupation_code=None,
                occupation_name=spec.benchmark_occupation,
                sex_code=selected.get("Sex"),
                sex=category_labels.get("Sex"),
                measure_code=measure_code,
                measure=measure,
                observation_value=_observation_value(
                    _indexed_value(values, ordinal, total)
                ),
                observation_status=status_value,
                source_unit=source_unit,
                source_publisher=publisher,
                source_updated_at=source_updated_at,
                source_artifact_id=artifact_id,
                retrieval_id=retrieval_id,
                extraction_id=extraction_id,
                request_id=request_identity,
                source_record_locator=locator,
                identifier_version=IDENTIFIER_VERSION,
                loaded_at=loaded_at,
            )
        )
    if len(observations) != total:
        raise OpenSTATError("OWS_JSONSTAT_ROW_COUNT_MISMATCH")
    semantic_identity = _semantic_dataset_identity(observations)
    return tuple(
        replace(
            item,
            semantic_dataset_id=semantic_identity,
            logical_observation_id=_logical_observation_identity(
                semantic_identity, item.source_record_locator
            ),
        )
        for item in observations
    )


def decode_jsonstat(
    spec: OWSMatrixSpec,
    metadata: ParsedMatrixMetadata,
    body: bytes,
    **context: str,
) -> tuple[OWSObservation, ...]:
    document = parse_json_document(body)
    dataset = document.get("dataset")
    if not isinstance(dataset, dict):
        raise OpenSTATError("OWS_JSONSTAT_STRUCTURE_INVALID")
    dimensions = dataset.get("dimension")
    if not isinstance(dimensions, dict):
        raise OpenSTATError("OWS_JSONSTAT_STRUCTURE_INVALID")
    return _decode_dimensional_dataset(
        spec,
        metadata,
        dataset,
        dimensions.get("id"),
        dimensions.get("size"),
        dimensions,
        **context,
    )


def decode_jsonstat2(
    spec: OWSMatrixSpec,
    metadata: ParsedMatrixMetadata,
    body: bytes,
    **context: str,
) -> tuple[OWSObservation, ...]:
    dataset = parse_json_document(body)
    if dataset.get("class") != "dataset" or dataset.get("version") != "2.0":
        raise OpenSTATError("OWS_JSONSTAT_STRUCTURE_INVALID")
    return _decode_dimensional_dataset(
        spec,
        metadata,
        dataset,
        dataset.get("id"),
        dataset.get("size"),
        dataset.get("dimension"),
        **context,
    )


def decode_source_response(
    response_format: str,
    spec: OWSMatrixSpec,
    metadata: ParsedMatrixMetadata,
    body: bytes,
    **context: str,
) -> tuple[OWSObservation, ...]:
    decoders = {"json-stat": decode_jsonstat, "json-stat2": decode_jsonstat2}
    try:
        decoder = decoders[response_format]
    except KeyError as exc:
        raise OpenSTATError("OWS_FORMAT_NOT_SUPPORTED") from exc
    return decoder(spec, metadata, body, **context)


def _source_dataset_document(response_format: str, body: bytes) -> Mapping[str, Any]:
    document = parse_json_document(body)
    if response_format == "json-stat":
        dataset = document.get("dataset")
        if not isinstance(dataset, dict):
            raise OpenSTATError("OWS_JSONSTAT_STRUCTURE_INVALID")
        return dataset
    if response_format == "json-stat2":
        return document
    raise OpenSTATError("OWS_FORMAT_NOT_SUPPORTED")


def _decode_csv_crosscheck(
    spec: OWSMatrixSpec,
    metadata: ParsedMatrixMetadata,
    body: bytes,
) -> dict[tuple[str, ...], tuple[Decimal | None, bool]]:
    try:
        text = body.decode("utf-8-sig")
    except UnicodeDecodeError:
        try:
            text = body.decode("cp1252")
        except UnicodeDecodeError as exc:
            raise OpenSTATError("OWS_CSV_ENCODING_INVALID") from exc
    rows = list(csv.reader(io.StringIO(text, newline="")))
    if len(rows) < 2:
        raise OpenSTATError("OWS_CSV_STRUCTURE_INVALID")
    axis = next(
        (item for item in metadata.dimensions if item.code == spec.axis_dimension),
        None,
    )
    if axis is None or len(set(axis.category_labels)) != len(axis.category_labels):
        raise OpenSTATError("OWS_CSV_STRUCTURE_INVALID")
    other_dimensions = tuple(
        item for item in metadata.dimensions if item.code != spec.axis_dimension
    )
    other_combinations = tuple(
        itertools.product(*(item.category_codes for item in other_dimensions))
    )
    label_maps = {
        item.code: dict(zip(item.category_codes, item.category_labels, strict=True))
        for item in metadata.dimensions
    }
    expected_headers = [
        " ".join(
            label_maps[dimension.code][code]
            for dimension, code in zip(other_dimensions, combination, strict=True)
        )
        for combination in other_combinations
    ]
    if rows[0] != [axis.label, *expected_headers]:
        raise OpenSTATError("OWS_CSV_HEADERS_MISMATCH")
    axis_codes = dict(zip(axis.category_labels, axis.category_codes, strict=True))
    if len(rows[1:]) != len(axis.category_codes):
        raise OpenSTATError("OWS_CSV_CARDINALITY_MISMATCH")
    decoded: dict[tuple[str, ...], tuple[Decimal | None, bool]] = {}
    for row in rows[1:]:
        if len(row) != len(rows[0]) or row[0] not in axis_codes:
            raise OpenSTATError("OWS_CSV_STRUCTURE_INVALID")
        axis_code = axis_codes[row[0]]
        for combination, raw_value in zip(other_combinations, row[1:], strict=True):
            is_rounded_integer = False
            if raw_value.strip() in ("", "..", "...", "-"):
                value = None
            else:
                try:
                    value = Decimal(raw_value.strip())
                except InvalidOperation as exc:
                    raise OpenSTATError("OWS_CSV_VALUE_INVALID") from exc
                is_rounded_integer = all(
                    marker not in raw_value.lower() for marker in (".", "e")
                )
            selected = {spec.axis_dimension: axis_code}
            selected.update(
                {
                    dimension.code: code
                    for dimension, code in zip(
                        other_dimensions, combination, strict=True
                    )
                }
            )
            key = tuple(selected[item.code] for item in metadata.dimensions)
            if key in decoded:
                raise OpenSTATError("OWS_CSV_DUPLICATE_OBSERVATION")
            decoded[key] = (value, is_rounded_integer)
    expected_count = math.prod(len(item.category_codes) for item in metadata.dimensions)
    if len(decoded) != expected_count:
        raise OpenSTATError("OWS_CSV_CARDINALITY_MISMATCH")
    return decoded


def validate_csv_crosscheck(
    spec: OWSMatrixSpec,
    metadata: ParsedMatrixMetadata,
    observations: Sequence[OWSObservation],
    body: bytes,
) -> None:
    csv_values = _decode_csv_crosscheck(spec, metadata, body)
    label_to_code = {
        item.code: dict(zip(item.category_labels, item.category_codes, strict=True))
        for item in metadata.dimensions
    }
    if len(csv_values) != len(observations):
        raise OpenSTATError("OWS_CROSSCHECK_CARDINALITY_MISMATCH")
    observed_keys: set[tuple[str, ...]] = set()
    for observation in observations:
        selected = {
            "Industry": observation.industry_code,
            "Region": observation.geography_code,
            "Year": label_to_code["Year"].get(str(observation.reference_year)),
            "Item": observation.measure_code,
            "Sex": observation.sex_code,
        }
        key = tuple(selected[item.code] for item in metadata.dimensions)
        if any(value is None for value in key) or key in observed_keys:
            raise OpenSTATError("OWS_CROSSCHECK_IDENTITY_MISMATCH")
        observed_keys.add(key)
        csv_value, is_rounded_integer = csv_values[key]
        if observation.observation_value is None:
            if csv_value is not None:
                raise OpenSTATError("OWS_CROSSCHECK_VALUE_MISMATCH")
            continue
        if csv_value is None:
            raise OpenSTATError("OWS_CROSSCHECK_VALUE_MISMATCH")
        json_value = Decimal(str(observation.observation_value))
        if is_rounded_integer:
            matches = json_value.quantize(Decimal("1"), rounding=ROUND_HALF_UP) == csv_value
        else:
            matches = abs(json_value - csv_value) <= Decimal("0.000000001")
        if not matches:
            raise OpenSTATError("OWS_CROSSCHECK_VALUE_MISMATCH")


def _extraction_config_hash(spec: OWSMatrixSpec) -> str:
    config = canonical_json(
        {
            "benchmark_occupation": spec.benchmark_occupation,
            "expected_dimensions": spec.expected_dimensions,
            "extractor_name": EXTRACTOR_NAME,
            "extractor_version": EXTRACTOR_VERSION,
            "matrix_id": spec.matrix_id,
            "output_contract_version": OUTPUT_CONTRACT_VERSION,
        }
    )
    return hashlib.sha256(config.encode("utf-8")).hexdigest()


def _matrix_metadata_id(extraction_id: str) -> str:
    return raw_record_id_v2(extraction_id, "matrix-metadata")


def acquire_matrix(
    spec: OWSMatrixSpec,
    local_root: Path,
    *,
    client: OpenSTATHTTPClient | Any | None = None,
    clock: Callable[[], str] = utc_now_text,
) -> AcquiredMatrix:
    if MATRIX_SPEC_BY_ID.get(spec.matrix_id) != spec:
        raise OpenSTATError("OWS_MATRIX_NOT_APPROVED")
    http_client = client or OpenSTATHTTPClient()
    metadata_result = http_client.request("GET", spec.endpoint)
    metadata = parse_matrix_metadata(spec, metadata_result.body)
    request_text = canonical_request(metadata)
    request_body = request_text.encode("utf-8")
    request_identity = request_id(spec.endpoint, request_text)

    retrieval = start_retrieval(
        spec.source_id,
        spec.endpoint,
        retrieval_started_at=clock(),
        request_method="POST",
    )
    data_result = http_client.request("POST", spec.endpoint, body=request_body)
    publisher = ArtifactPublisher(local_root)
    publication = publisher.publish(
        publisher.stage(
            retrieval.retrieval_run_id,
            spec.source_id,
            io.BytesIO(data_result.body),
        )
    )
    completed_at = clock()
    response = RetrievalResponse(
        resolved_location=spec.endpoint,
        status_code=data_result.status_code,
        content_type=data_result.headers.content_type,
        content_length=data_result.headers.content_length,
        bytes_received=len(data_result.body),
        etag=data_result.headers.etag,
        last_modified=data_result.headers.last_modified,
    )
    retrieval = complete_retrieval(
        retrieval,
        content_outcome=(
            "new_artifact" if publication.outcome == "published" else "known_artifact"
        ),
        response=response,
        retrieval_completed_at=completed_at,
        artifact_id=publication.artifact_id,
    )
    artifact = ArtifactProvenance(
        artifact_id=publication.artifact_id,
        source_id=publication.source_id,
        sha256_checksum=publication.sha256_checksum,
        byte_size=publication.byte_size,
        storage_key=publication.storage_key,
        first_retrieval_run_id=retrieval.retrieval_run_id,
        first_retrieved_at=completed_at,
        content_type=data_result.headers.content_type,
    )
    extraction = start_extraction(
        spec.source_id,
        publication.artifact_id,
        EXTRACTOR_NAME,
        EXTRACTOR_VERSION,
        OUTPUT_CONTRACT_VERSION,
        _extraction_config_hash(spec),
        extraction_started_at=clock(),
    )
    loaded_at = clock()
    observations = decode_source_response(
        REQUESTED_FORMAT,
        spec,
        metadata,
        data_result.body,
        artifact_id=publication.artifact_id,
        retrieval_id=retrieval.retrieval_run_id,
        extraction_id=extraction.extraction_batch_id,
        request_identity=request_identity,
        loaded_at=loaded_at,
    )
    csv_request = canonical_json(build_explicit_request(metadata, VALIDATION_FORMAT))
    csv_result = http_client.request(
        "POST",
        spec.endpoint,
        body=csv_request.encode("utf-8"),
        accepted_content_types=("text/csv",),
    )
    validate_csv_crosscheck(spec, metadata, observations, csv_result.body)
    extraction = finish_extraction(
        extraction,
        status="succeeded",
        extraction_completed_at=clock(),
        records_emitted=len(observations),
        issues_emitted=0,
    )
    dataset_document = _source_dataset_document(REQUESTED_FORMAT, data_result.body)
    source_updated_at = dataset_document.get("updated")
    semantic_identity = observations[0].semantic_dataset_id
    matrix_metadata = OWSMatrixMetadataRecord(
        matrix_metadata_id=_matrix_metadata_id(extraction.extraction_batch_id),
        semantic_dataset_id=semantic_identity,
        matrix_id=spec.matrix_id,
        matrix_title=metadata.title,
        canonical_endpoint=spec.endpoint,
        canonical_request=request_text,
        request_id=request_identity,
        requested_format=REQUESTED_FORMAT,
        source_id=spec.source_id,
        source_publisher=SOURCE_PUBLISHER,
        reference_year=metadata.reference_year,
        dimension_ids_json=canonical_json(
            [dimension.code for dimension in metadata.dimensions]
        ),
        source_metadata_json=canonical_json(metadata.document),
        source_artifact_id=publication.artifact_id,
        sha256_checksum=publication.sha256_checksum,
        byte_size=publication.byte_size,
        storage_key=publication.storage_key,
        first_retrieval_id=retrieval.retrieval_run_id,
        first_retrieved_at=completed_at,
        extraction_id=extraction.extraction_batch_id,
        identifier_version=IDENTIFIER_VERSION,
        source_updated_at=(
            source_updated_at if isinstance(source_updated_at, str) else None
        ),
        loaded_at=loaded_at,
    )
    ingestion_run = OWSIngestionRunRecord(
        retrieval_id=retrieval.retrieval_run_id,
        semantic_dataset_id=semantic_identity,
        matrix_id=spec.matrix_id,
        source_id=spec.source_id,
        request_id=request_identity,
        canonical_endpoint=spec.endpoint,
        canonical_request=request_text,
        requested_format=REQUESTED_FORMAT,
        request_method=retrieval.request_method,
        retrieval_status=retrieval.retrieval_status,
        content_outcome=retrieval.content_outcome or "",
        retrieval_started_at=retrieval.retrieval_started_at,
        retrieval_completed_at=retrieval.retrieval_completed_at or "",
        http_status_code=data_result.status_code,
        response_content_type=response.content_type,
        response_content_length=response.content_length,
        response_bytes_received=len(data_result.body),
        response_etag=response.etag,
        response_last_modified=response.last_modified,
        source_artifact_id=publication.artifact_id,
        sha256_checksum=publication.sha256_checksum,
        extraction_id=extraction.extraction_batch_id,
        extraction_status=extraction.extraction_status,
        records_emitted=extraction.records_emitted,
        issues_emitted=extraction.issues_emitted,
        identifier_version=IDENTIFIER_VERSION,
        loaded_at=loaded_at,
    )
    return AcquiredMatrix(
        spec,
        metadata,
        request_text,
        request_identity,
        retrieval,
        artifact,
        publication,
        extraction,
        observations,
        matrix_metadata,
        ingestion_run,
    )


def validate_representative_values(acquisitions: Sequence[AcquiredMatrix]) -> None:
    """Fail closed if stable headline observations do not match PSA's release."""

    expected = {
        "0011B3E2001.px": ("ALL INDUSTRIES", None, 21_544.0),
        "0021B3E2002.px": ("PHILIPPINES", None, 21_544.0),
        "0051B3E2005.px": ("ALL INDUSTRIES", "BOTH SEXES", 19_721.0),
        "0071B3E2007.px": ("ALL INDUSTRIES", "BOTH SEXES", 13_506.0),
    }
    acquired_by_id = {item.spec.matrix_id: item for item in acquisitions}
    if set(acquired_by_id) != set(expected):
        raise OpenSTATError("OWS_REPRESENTATIVE_SCOPE_INVALID")
    for matrix_id, (axis_name, sex_name, expected_value) in expected.items():
        candidates = []
        for observation in acquired_by_id[matrix_id].observations:
            observed_axis = observation.industry_name or observation.geography_name
            if observed_axis is None or observed_axis.upper() != axis_name:
                continue
            if sex_name is not None and (
                observation.sex is None or observation.sex.upper() != sex_name
            ):
                continue
            if sex_name is None and "WAGE RATE" not in observation.measure.upper():
                continue
            candidates.append(observation)
        if len(candidates) != 1 or candidates[0].observation_value is None:
            raise OpenSTATError("OWS_REPRESENTATIVE_VALUE_MISMATCH")
        rounded = Decimal(str(candidates[0].observation_value)).quantize(
            Decimal("1"), rounding=ROUND_HALF_UP
        )
        if rounded != Decimal(str(expected_value)):
            raise OpenSTATError("OWS_REPRESENTATIVE_VALUE_MISMATCH")
