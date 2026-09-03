from __future__ import annotations

import io

from analytics_platform.platform.provenance.artifacts import ArtifactPublisher
from analytics_platform.platform.provenance.identifiers import new_retrieval_run_id
from analytics_platform.platform.provenance.lifecycle import ArtifactProvenance
from analytics_platform.platform.provenance.reconciliation import reconcile_artifacts


SOURCE_ID = "public_example_source"
PAYLOAD = b"reconciliation artifact bytes\n" * 16
RETRIEVED_AT = "2026-08-10T01:02:04.000000Z"


def _publish_and_describe(local_root):
    retrieval_id = new_retrieval_run_id()
    result = ArtifactPublisher(local_root).publish(
        ArtifactPublisher(local_root).stage(
            retrieval_id, SOURCE_ID, io.BytesIO(PAYLOAD)
        )
    )
    record = ArtifactProvenance(
        artifact_id=result.artifact_id,
        source_id=result.source_id,
        sha256_checksum=result.sha256_checksum,
        byte_size=result.byte_size,
        storage_key=result.storage_key,
        first_retrieval_run_id=retrieval_id,
        first_retrieved_at=RETRIEVED_AT,
    )
    return result, record


def test_matching_metadata_and_file_are_clean(tmp_path) -> None:
    result, record = _publish_and_describe(tmp_path)
    report = reconcile_artifacts(tmp_path, [record])
    assert report.is_clean
    assert report.metadata_artifacts_scanned == 1
    assert report.artifact_files_scanned == 1
    assert result.artifact_path.read_bytes() == PAYLOAD


def test_orphan_and_staging_entries_are_reported_without_mutation(tmp_path) -> None:
    result, _ = _publish_and_describe(tmp_path)
    publisher = ArtifactPublisher(tmp_path)
    staged = publisher.stage(
        new_retrieval_run_id(), SOURCE_ID, io.BytesIO(b"operator review")
    )
    before = sorted(path.relative_to(tmp_path) for path in tmp_path.rglob("*"))
    report = reconcile_artifacts(tmp_path, [])
    after = sorted(path.relative_to(tmp_path) for path in tmp_path.rglob("*"))
    codes = {finding.code for finding in report.findings}
    assert {"ORPHAN_ARTIFACT_FILE", "STAGING_FILE_PRESENT"} <= codes
    assert before == after
    assert result.artifact_path.read_bytes() == PAYLOAD
    assert staged.staging_path.read_bytes() == b"operator review"


def test_missing_and_corrupt_artifacts_are_detected(tmp_path) -> None:
    result, record = _publish_and_describe(tmp_path)
    result.artifact_path.write_bytes(b"x" * result.byte_size)
    codes = {
        finding.code for finding in reconcile_artifacts(tmp_path, [record]).findings
    }
    assert "ARTIFACT_CHECKSUM_MISMATCH" in codes
    result.artifact_path.unlink()
    codes = {
        finding.code for finding in reconcile_artifacts(tmp_path, [record]).findings
    }
    assert "METADATA_ARTIFACT_MISSING" in codes
