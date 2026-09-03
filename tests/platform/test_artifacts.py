from __future__ import annotations

import hashlib
import io

import pytest

from analytics_platform.platform.provenance.artifacts import (
    ArtifactIntegrityError,
    ArtifactPathError,
    ArtifactPublisher,
    artifact_storage_key,
    inspect_artifact_file,
    resolve_storage_key,
)
from analytics_platform.platform.provenance.identifiers import new_retrieval_run_id


SOURCE_ID = "public_example_source"
PAYLOAD = b"stable source artifact\n" * 32


def test_storage_key_is_content_addressed_and_root_neutral(tmp_path) -> None:
    checksum = hashlib.sha256(PAYLOAD).hexdigest()
    key = artifact_storage_key(SOURCE_ID, checksum)
    assert key == f"artifacts/{SOURCE_ID}/sha256/{checksum[:2]}/{checksum}"
    first = resolve_storage_key(tmp_path / "first", key)
    second = resolve_storage_key(tmp_path / "second", key)
    assert first.relative_to(tmp_path / "first").as_posix() == key
    assert second.relative_to(tmp_path / "second").as_posix() == key
    assert not first.exists()
    assert not second.exists()


@pytest.mark.parametrize(
    "key",
    [
        "../artifacts/source/sha256/aa/" + "a" * 64,
        "C:/artifacts/source/sha256/aa/" + "a" * 64,
        "artifacts\\source\\sha256\\aa\\" + "a" * 64,
        "artifacts/source/md5/aa/" + "a" * 64,
    ],
)
def test_storage_key_rejects_unsafe_or_noncanonical_paths(tmp_path, key) -> None:
    with pytest.raises(ArtifactPathError):
        resolve_storage_key(tmp_path, key)


def test_publication_is_hash_verified_immutable_and_idempotent(tmp_path) -> None:
    publisher = ArtifactPublisher(tmp_path)
    first = publisher.publish(
        publisher.stage(new_retrieval_run_id(), SOURCE_ID, io.BytesIO(PAYLOAD))
    )
    initial_stat = first.artifact_path.stat()
    second = publisher.publish(
        publisher.stage(new_retrieval_run_id(), SOURCE_ID, io.BytesIO(PAYLOAD))
    )
    final_stat = first.artifact_path.stat()
    assert first.outcome == "published"
    assert second.outcome == "existing"
    assert first.artifact_id == second.artifact_id
    assert first.artifact_path.read_bytes() == PAYLOAD
    assert initial_stat.st_mtime_ns == final_stat.st_mtime_ns
    assert initial_stat.st_ino == final_stat.st_ino
    assert not second.staging_cleanup_pending


def test_publication_rejects_staging_tampering(tmp_path) -> None:
    publisher = ArtifactPublisher(tmp_path)
    staged = publisher.stage(
        new_retrieval_run_id(), SOURCE_ID, io.BytesIO(PAYLOAD)
    )
    staged.staging_path.write_bytes(b"tampered")
    with pytest.raises(ArtifactIntegrityError):
        publisher.publish(staged)


def test_publication_never_overwrites_conflicting_target(tmp_path) -> None:
    publisher = ArtifactPublisher(tmp_path)
    published = publisher.publish(
        publisher.stage(new_retrieval_run_id(), SOURCE_ID, io.BytesIO(PAYLOAD))
    )
    published.artifact_path.write_bytes(b"x" * published.byte_size)
    staged = publisher.stage(
        new_retrieval_run_id(), SOURCE_ID, io.BytesIO(PAYLOAD)
    )
    with pytest.raises(ArtifactIntegrityError):
        publisher.publish(staged)
    assert published.artifact_path.read_bytes() == b"x" * published.byte_size
    assert staged.staging_path.read_bytes() == PAYLOAD


def test_file_inspection_reports_full_content_identity(tmp_path) -> None:
    path = tmp_path / "artifact.bin"
    path.write_bytes(PAYLOAD)
    info = inspect_artifact_file(path, chunk_size=7)
    assert info.sha256_checksum == hashlib.sha256(PAYLOAD).hexdigest()
    assert info.byte_size == len(PAYLOAD)
