from __future__ import annotations

import re

import pytest

from analytics_platform.platform.provenance.identifiers import (
    IdentifierError,
    artifact_id_v2,
    extraction_batch_id_v2,
    extraction_issue_id_v2,
    legacy_artifact_id_v1,
    legacy_extraction_batch_id_v1,
    legacy_extraction_issue_id_v1,
    legacy_raw_record_id_v1,
    new_retrieval_run_id,
    raw_record_id_v2,
    validate_retrieval_run_id,
)


SOURCE_ID = "da_amas_ncr_weekly_average_prices"
ARTIFACT_CHECKSUM = "a" * 64
CONFIG_HASH = "b" * 64


def test_legacy_v1_golden_vectors_are_preserved_exactly() -> None:
    artifact = legacy_artifact_id_v1(SOURCE_ID, ARTIFACT_CHECKSUM)
    assert artifact == (
        "artifact_d547967ffc8ef3f96a7bbe3cb49c05f6"
        "d1e203b16684d752e68bb71237f1aa9c"
    )
    extraction = legacy_extraction_batch_id_v1(
        artifact, "da_weekly_pdf", "0.1.0", "0.1", CONFIG_HASH
    )
    assert extraction == (
        "extraction_1188bc77b4e02372127574c80aa76323"
        "8647bee3e4eb4812f9add6fcd9c5db51"
    )
    assert legacy_extraction_issue_id_v1(
        extraction, "MISSING_PRICE", "page:0001/price-row:0001", 1
    ) == (
        "issue_975746304164c9f48f86ec64807c6950"
        "836c8c60fe5cb0a36de525e09f59f2e5"
    )
    assert legacy_raw_record_id_v1(extraction, "page:0001/price-row:0001") == (
        "raw_3447d2f99c0b99c2c0775c30066a0c1"
        "2c7bf3a2b9d002ab6963901fa7c31355a"
    )


def test_v2_is_deterministic_and_explicitly_distinct_from_v1() -> None:
    first = artifact_id_v2(SOURCE_ID, ARTIFACT_CHECKSUM)
    second = artifact_id_v2(SOURCE_ID, ARTIFACT_CHECKSUM)
    assert first == second
    assert first != legacy_artifact_id_v1(SOURCE_ID, ARTIFACT_CHECKSUM)
    extraction = extraction_batch_id_v2(
        first, "generic_extractor", "1.0", "records-v1", CONFIG_HASH
    )
    assert extraction == extraction_batch_id_v2(
        first, "generic_extractor", "1.0", "records-v1", CONFIG_HASH
    )
    assert extraction_issue_id_v2(extraction, "INVALID_ROW", None, 1).startswith(
        "issue_"
    )
    assert raw_record_id_v2(extraction, "row:0001").startswith("raw_")


def test_canonical_encoding_distinguishes_component_boundaries_and_unicode() -> None:
    checksum = "c" * 64
    assert artifact_id_v2("source_one", checksum) != artifact_id_v2(
        "source_two", checksum
    )
    artifact = artifact_id_v2("source_one", checksum)
    assert extraction_batch_id_v2(
        artifact, "ab", "c", "contract", CONFIG_HASH
    ) != extraction_batch_id_v2(artifact, "a", "bc", "contract", CONFIG_HASH)
    extraction = extraction_batch_id_v2(
        artifact, "extractor", "1", "contract", CONFIG_HASH
    )
    assert extraction_issue_id_v2(extraction, "ISSUE", None, 1) != (
        extraction_issue_id_v2(extraction, "ISSUE", "row:0001", 1)
    )
    assert raw_record_id_v2(extraction, "café") != raw_record_id_v2(
        extraction, "cafe"
    )


def test_identifier_validation_rejects_noncanonical_inputs() -> None:
    with pytest.raises(IdentifierError):
        artifact_id_v2("Bad-Source", ARTIFACT_CHECKSUM)
    with pytest.raises(IdentifierError):
        artifact_id_v2("valid_source", "A" * 64)
    with pytest.raises(IdentifierError):
        extraction_issue_id_v2("extraction_" + "a" * 64, "bad-code", None, 1)


def test_retrieval_run_ids_are_canonical_uuid4_values() -> None:
    first = new_retrieval_run_id()
    second = new_retrieval_run_id()
    assert first != second
    assert re.fullmatch(r"retrieval_[0-9a-f-]{36}", first)
    assert validate_retrieval_run_id(first) == first
