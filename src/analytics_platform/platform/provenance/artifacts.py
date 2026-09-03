"""Explicit-root content-addressed artifact storage and immutable publication."""

from __future__ import annotations

import hashlib
import os
import stat
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import BinaryIO, Literal

from analytics_platform.platform.provenance.identifiers import (
    artifact_id_v2,
    validate_retrieval_run_id,
    validate_sha256,
    validate_source_id,
)


class ArtifactPathError(ValueError):
    """Raised when an artifact storage key is unsafe or noncanonical."""


class ArtifactPublicationError(RuntimeError):
    """Raised when staging or no-clobber publication cannot complete safely."""


class ArtifactIntegrityError(ArtifactPublicationError):
    """Raised when staged or existing content conflicts with its identity."""


@dataclass(frozen=True)
class ArtifactFileInfo:
    sha256_checksum: str
    byte_size: int


@dataclass(frozen=True)
class StagedArtifact:
    retrieval_run_id: str
    source_id: str
    staging_path: Path
    sha256_checksum: str
    byte_size: int
    storage_key: str
    artifact_id: str


@dataclass(frozen=True)
class ArtifactPublicationResult:
    outcome: Literal["published", "existing"]
    artifact_id: str
    source_id: str
    sha256_checksum: str
    byte_size: int
    storage_key: str
    artifact_path: Path
    staging_cleanup_pending: bool


def artifact_storage_key(source_id: str, sha256_checksum: str) -> str:
    """Return the canonical relative POSIX storage key for an artifact."""

    validate_source_id(source_id)
    validate_sha256(sha256_checksum, field_name="sha256_checksum")
    return f"artifacts/{source_id}/sha256/{sha256_checksum[:2]}/{sha256_checksum}"


def resolve_storage_key(local_root: Path, storage_key: str) -> Path:
    """Resolve a canonical key below an explicit root without creating anything."""

    if not isinstance(storage_key, str) or storage_key == "":
        raise ArtifactPathError("storage_key must be nonempty text")
    if "\\" in storage_key or ":" in storage_key:
        raise ArtifactPathError("storage_key must use canonical POSIX relative syntax")
    pure_key = PurePosixPath(storage_key)
    parts = pure_key.parts
    if pure_key.is_absolute() or len(parts) != 5:
        raise ArtifactPathError("storage_key must have the canonical five segments")
    if any(part in ("", ".", "..") for part in parts):
        raise ArtifactPathError("storage_key contains an unsafe path segment")
    namespace, source_id, algorithm, checksum_prefix, checksum = parts
    if namespace != "artifacts" or algorithm != "sha256":
        raise ArtifactPathError("storage_key namespace or hash algorithm is invalid")
    try:
        canonical = artifact_storage_key(source_id, checksum)
    except ValueError as exc:
        raise ArtifactPathError(str(exc)) from exc
    if checksum_prefix != checksum[:2] or storage_key != canonical:
        raise ArtifactPathError("storage_key is not canonical")
    try:
        resolved_root = Path(local_root).expanduser().resolve(strict=False)
        if resolved_root.exists() and not resolved_root.is_dir():
            raise ArtifactPathError("configured local root is not a directory")
        unresolved_candidate = resolved_root.joinpath(*parts)
        candidate = unresolved_candidate.resolve(strict=False)
    except OSError as exc:
        raise ArtifactPathError(f"storage_key could not be resolved safely: {exc}") from exc
    if not candidate.is_relative_to(resolved_root):
        raise ArtifactPathError("storage_key resolves outside the configured local root")
    if candidate != unresolved_candidate:
        raise ArtifactPathError("storage_key contains filesystem link indirection")
    return candidate


def artifact_path(local_root: Path, source_id: str, sha256_checksum: str) -> Path:
    return resolve_storage_key(
        local_root, artifact_storage_key(source_id, sha256_checksum)
    )


def inspect_artifact_file(path: Path, *, chunk_size: int = 1024 * 1024) -> ArtifactFileInfo:
    """Hash one non-symlink regular file and reject concurrent replacement."""

    if not isinstance(chunk_size, int) or isinstance(chunk_size, bool) or chunk_size <= 0:
        raise ArtifactPathError("chunk_size must be positive")
    candidate = Path(path)
    try:
        before = candidate.lstat()
    except OSError as exc:
        raise ArtifactPathError(f"artifact file cannot be inspected: {candidate}") from exc
    if not stat.S_ISREG(before.st_mode):
        raise ArtifactPathError(f"artifact path is not a regular file: {candidate}")
    digest = hashlib.sha256()
    byte_size = 0
    try:
        with candidate.open("rb") as artifact_file:
            while chunk := artifact_file.read(chunk_size):
                digest.update(chunk)
                byte_size += len(chunk)
        after = candidate.lstat()
    except OSError as exc:
        raise ArtifactPathError(f"artifact file cannot be inspected: {candidate}") from exc
    stable_fields = ("st_dev", "st_ino", "st_size", "st_mtime_ns", "st_ctime_ns")
    if any(getattr(before, field) != getattr(after, field) for field in stable_fields):
        raise ArtifactPathError(f"artifact file changed during inspection: {candidate}")
    if byte_size != after.st_size:
        raise ArtifactPathError(f"artifact file size changed during inspection: {candidate}")
    return ArtifactFileInfo(digest.hexdigest(), byte_size)


class ArtifactPublisher:
    """Stage and exclusively publish artifacts below one explicit local root."""

    def __init__(
        self,
        local_root: Path,
        *,
        artifact_identifier: Callable[[str, str], str] = artifact_id_v2,
    ) -> None:
        self.local_root = Path(local_root).expanduser().resolve(strict=False)
        self._artifact_identifier = artifact_identifier
        if self.local_root.exists() and not self.local_root.is_dir():
            raise ArtifactPublicationError("configured local root is not a directory")

    def _staging_path(self, retrieval_run_id: str) -> Path:
        try:
            validate_retrieval_run_id(retrieval_run_id)
        except ValueError as exc:
            raise ArtifactPublicationError(str(exc)) from exc
        unresolved = self.local_root / "tmp" / "artifacts" / f"{retrieval_run_id}.part"
        candidate = unresolved.resolve(strict=False)
        if not candidate.is_relative_to(self.local_root):
            raise ArtifactPublicationError("staging path escapes the configured local root")
        if candidate != unresolved:
            raise ArtifactPublicationError("staging path contains filesystem link indirection")
        return candidate

    def _ensure_staging_parent(self, staging_path: Path) -> None:
        try:
            self.local_root.mkdir(parents=True, exist_ok=True)
            staging_path.parent.mkdir(parents=True, exist_ok=True)
            resolved = staging_path.resolve(strict=False)
        except OSError as exc:
            raise ArtifactPublicationError("staging directory could not be created") from exc
        if resolved != staging_path or not resolved.is_relative_to(self.local_root):
            raise ArtifactPublicationError("staging directory resolves outside local root")

    def stage(
        self,
        retrieval_run_id: str,
        source_id: str,
        source: BinaryIO,
        *,
        chunk_size: int = 1024 * 1024,
    ) -> StagedArtifact:
        try:
            validate_retrieval_run_id(retrieval_run_id)
            validate_source_id(source_id)
        except ValueError as exc:
            raise ArtifactPublicationError(str(exc)) from exc
        if not isinstance(chunk_size, int) or isinstance(chunk_size, bool) or chunk_size <= 0:
            raise ArtifactPublicationError("chunk_size must be positive")
        staging_path = self._staging_path(retrieval_run_id)
        self._ensure_staging_parent(staging_path)
        digest = hashlib.sha256()
        byte_size = 0
        try:
            with staging_path.open("xb") as staged_file:
                while True:
                    chunk = source.read(chunk_size)
                    if chunk == b"":
                        break
                    if not isinstance(chunk, bytes):
                        raise ArtifactPublicationError("artifact source must return bytes")
                    staged_file.write(chunk)
                    digest.update(chunk)
                    byte_size += len(chunk)
                staged_file.flush()
                os.fsync(staged_file.fileno())
        except FileExistsError as exc:
            raise ArtifactPublicationError(
                f"staging file already exists for retrieval {retrieval_run_id}"
            ) from exc
        except ArtifactPublicationError:
            raise
        except Exception as exc:
            raise ArtifactPublicationError("artifact staging failed") from exc
        if byte_size <= 0:
            raise ArtifactPublicationError("empty content cannot become an artifact")
        checksum = digest.hexdigest()
        return StagedArtifact(
            retrieval_run_id=retrieval_run_id,
            source_id=source_id,
            staging_path=staging_path,
            sha256_checksum=checksum,
            byte_size=byte_size,
            storage_key=artifact_storage_key(source_id, checksum),
            artifact_id=self._artifact_identifier(source_id, checksum),
        )

    def _verify_staged(self, staged: StagedArtifact) -> None:
        try:
            expected_path = self._staging_path(staged.retrieval_run_id)
            expected_key = artifact_storage_key(staged.source_id, staged.sha256_checksum)
            expected_id = self._artifact_identifier(
                staged.source_id, staged.sha256_checksum
            )
        except ValueError as exc:
            raise ArtifactIntegrityError(str(exc)) from exc
        if staged.staging_path.resolve(strict=False) != expected_path:
            raise ArtifactIntegrityError("staged artifact does not belong to this publisher")
        if staged.storage_key != expected_key:
            raise ArtifactIntegrityError("staged artifact storage key is inconsistent")
        if staged.artifact_id != expected_id:
            raise ArtifactIntegrityError("staged artifact identifier is inconsistent")
        try:
            inspected = inspect_artifact_file(staged.staging_path)
        except ArtifactPathError as exc:
            raise ArtifactIntegrityError(str(exc)) from exc
        if (
            inspected.sha256_checksum != staged.sha256_checksum
            or inspected.byte_size != staged.byte_size
        ):
            raise ArtifactIntegrityError("staged artifact changed after synchronization")

    def verify_staged(self, staged: StagedArtifact) -> None:
        self._verify_staged(staged)

    def _ensure_target_parent(self, staged: StagedArtifact) -> Path:
        try:
            target = artifact_path(
                self.local_root, staged.source_id, staged.sha256_checksum
            )
            target.parent.mkdir(parents=True, exist_ok=True)
            resolved_again = artifact_path(
                self.local_root, staged.source_id, staged.sha256_checksum
            )
        except (ArtifactPathError, OSError, ValueError) as exc:
            raise ArtifactPublicationError(
                "canonical artifact directory could not be created safely"
            ) from exc
        if target != resolved_again:
            raise ArtifactPublicationError("canonical artifact path changed during creation")
        return target

    @staticmethod
    def _verify_target(target: Path, staged: StagedArtifact) -> None:
        try:
            inspected = inspect_artifact_file(target)
        except ArtifactPathError as exc:
            raise ArtifactIntegrityError(str(exc)) from exc
        if inspected.byte_size != staged.byte_size:
            raise ArtifactIntegrityError(
                "existing canonical artifact has a conflicting byte size"
            )
        if inspected.sha256_checksum != staged.sha256_checksum:
            raise ArtifactIntegrityError(
                "existing canonical artifact has a conflicting SHA-256 checksum"
            )

    @staticmethod
    def _cleanup_staging(staging_path: Path) -> bool:
        try:
            staging_path.unlink()
        except FileNotFoundError:
            return False
        except OSError:
            return True
        return False

    @staticmethod
    def _synchronize_directory(directory: Path) -> None:
        if os.name == "nt":
            return
        flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
        try:
            descriptor = os.open(directory, flags)
            try:
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
        except OSError as exc:
            raise ArtifactPublicationError(
                f"artifact directory could not be synchronized: {directory}"
            ) from exc

    def publish(self, staged: StagedArtifact) -> ArtifactPublicationResult:
        """Publish by atomic hard link, or verify an existing canonical target."""

        self._verify_staged(staged)
        target = self._ensure_target_parent(staged)
        outcome: Literal["published", "existing"]
        try:
            os.link(staged.staging_path, target, follow_symlinks=False)
            outcome = "published"
        except FileExistsError:
            outcome = "existing"
        except OSError as exc:
            raise ArtifactPublicationError(
                "exclusive artifact publication requires same-filesystem hard-link support"
            ) from exc
        self._verify_target(target, staged)
        if outcome == "published":
            self._synchronize_directory(target.parent)
        cleanup_pending = self._cleanup_staging(staged.staging_path)
        if not cleanup_pending:
            self._synchronize_directory(staged.staging_path.parent)
        return ArtifactPublicationResult(
            outcome=outcome,
            artifact_id=staged.artifact_id,
            source_id=staged.source_id,
            sha256_checksum=staged.sha256_checksum,
            byte_size=staged.byte_size,
            storage_key=staged.storage_key,
            artifact_path=target,
            staging_cleanup_pending=cleanup_pending,
        )
