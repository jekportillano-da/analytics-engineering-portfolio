"""Read-only reconciliation of provenance metadata and local artifact files."""

from __future__ import annotations

import os
import stat
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, TypeAlias

from analytics_platform.platform.provenance.artifacts import (
    ArtifactPathError,
    inspect_artifact_file,
    resolve_storage_key,
)
from analytics_platform.platform.provenance.lifecycle import ArtifactProvenance


FindingSeverity: TypeAlias = Literal["error", "warning"]


class ReconciliationError(RuntimeError):
    """Raised when a read-only reconciliation inventory cannot be completed."""


@dataclass(frozen=True)
class ReconciliationFinding:
    code: str
    severity: FindingSeverity
    relative_path: str | None
    artifact_id: str | None
    message: str


@dataclass(frozen=True)
class ReconciliationReport:
    metadata_artifacts_scanned: int
    artifact_files_scanned: int
    staging_entries_scanned: int
    findings: tuple[ReconciliationFinding, ...]

    @property
    def is_clean(self) -> bool:
        return not self.findings


def _relative_path(local_root: Path, path: Path) -> str:
    try:
        return path.relative_to(local_root).as_posix()
    except ValueError:
        return path.name


def _walk_entries(root: Path) -> tuple[list[Path], list[Path], list[str]]:
    files: list[Path] = []
    unsafe: list[Path] = []
    errors: list[str] = []
    if not root.exists() and not root.is_symlink():
        return files, unsafe, errors
    try:
        root_status = root.lstat()
    except OSError as exc:
        return files, unsafe, [str(exc)]
    if not stat.S_ISDIR(root_status.st_mode):
        return files, [root], errors
    pending = [root]
    while pending:
        directory = pending.pop()
        try:
            with os.scandir(directory) as entries:
                ordered_entries = sorted(entries, key=lambda entry: entry.name)
        except OSError as exc:
            errors.append(str(exc))
            continue
        for entry in ordered_entries:
            path = Path(entry.path)
            try:
                if entry.is_symlink():
                    unsafe.append(path)
                elif entry.is_dir(follow_symlinks=False):
                    pending.append(path)
                elif entry.is_file(follow_symlinks=False):
                    files.append(path)
                else:
                    unsafe.append(path)
            except OSError as exc:
                errors.append(str(exc))
    return files, unsafe, errors


def reconcile_artifacts(
    local_root: Path,
    expected_artifacts: Iterable[ArtifactProvenance],
) -> ReconciliationReport:
    """Compare explicit metadata with local files without changing either input."""

    root = Path(local_root).expanduser().resolve(strict=False)
    try:
        expected = tuple(expected_artifacts)
    except TypeError as exc:
        raise ReconciliationError("expected_artifacts must be iterable") from exc
    if any(not isinstance(item, ArtifactProvenance) for item in expected):
        raise ReconciliationError("expected_artifacts must contain ArtifactProvenance")
    metadata: dict[str, ArtifactProvenance] = {}
    for item in expected:
        if item.storage_key in metadata:
            raise ReconciliationError("duplicate artifact storage_key in metadata")
        metadata[item.storage_key] = item

    observed_keys: set[str] = set()
    findings: list[ReconciliationFinding] = []
    artifact_files, unsafe_artifacts, artifact_scan_errors = _walk_entries(
        root / "artifacts"
    )
    for path in unsafe_artifacts:
        findings.append(
            ReconciliationFinding(
                "UNSAFE_ARTIFACT_ENTRY",
                "error",
                _relative_path(root, path),
                None,
                "artifact entry is a symlink or unsupported filesystem object",
            )
        )
    for error in artifact_scan_errors:
        findings.append(
            ReconciliationFinding(
                "ARTIFACT_SCAN_ERROR", "error", "artifacts", None, error
            )
        )

    for path in sorted(artifact_files):
        relative = _relative_path(root, path)
        try:
            resolved = resolve_storage_key(root, relative)
        except ArtifactPathError as exc:
            findings.append(
                ReconciliationFinding(
                    "NONCANONICAL_ARTIFACT_ENTRY",
                    "error",
                    relative,
                    None,
                    str(exc),
                )
            )
            continue
        if resolved != path.resolve(strict=False):
            findings.append(
                ReconciliationFinding(
                    "NONCANONICAL_ARTIFACT_ENTRY",
                    "error",
                    relative,
                    None,
                    "artifact entry does not resolve to its canonical path",
                )
            )
            continue
        observed_keys.add(relative)
        record = metadata.get(relative)
        artifact_identifier = None if record is None else record.artifact_id
        try:
            inspected = inspect_artifact_file(path)
        except ArtifactPathError as exc:
            findings.append(
                ReconciliationFinding(
                    "ARTIFACT_INSPECTION_ERROR",
                    "error",
                    relative,
                    artifact_identifier,
                    str(exc),
                )
            )
            continue
        canonical_checksum = relative.rsplit("/", maxsplit=1)[-1]
        if inspected.sha256_checksum != canonical_checksum:
            findings.append(
                ReconciliationFinding(
                    "ARTIFACT_CHECKSUM_MISMATCH",
                    "error",
                    relative,
                    artifact_identifier,
                    "file checksum does not match its canonical storage key",
                )
            )
        if record is not None and inspected.byte_size != record.byte_size:
            findings.append(
                ReconciliationFinding(
                    "ARTIFACT_SIZE_MISMATCH",
                    "error",
                    relative,
                    artifact_identifier,
                    "file byte size does not match provenance metadata",
                )
            )
        if record is None:
            findings.append(
                ReconciliationFinding(
                    "ORPHAN_ARTIFACT_FILE",
                    "warning",
                    relative,
                    None,
                    "canonical artifact file has no provenance metadata",
                )
            )

    for storage_key, record in metadata.items():
        if storage_key in observed_keys:
            continue
        try:
            expected_path = resolve_storage_key(root, storage_key)
            expected_path.lstat()
        except FileNotFoundError:
            findings.append(
                ReconciliationFinding(
                    "METADATA_ARTIFACT_MISSING",
                    "error",
                    storage_key,
                    record.artifact_id,
                    "provenance metadata points to a missing artifact file",
                )
            )
        except (ArtifactPathError, OSError) as exc:
            findings.append(
                ReconciliationFinding(
                    "METADATA_ARTIFACT_UNSAFE",
                    "error",
                    storage_key,
                    record.artifact_id,
                    str(exc),
                )
            )

    staging_files, unsafe_staging, staging_scan_errors = _walk_entries(
        root / "tmp" / "artifacts"
    )
    for path in sorted(staging_files):
        findings.append(
            ReconciliationFinding(
                "STAGING_FILE_PRESENT",
                "warning",
                _relative_path(root, path),
                None,
                "staging file remains for operator review",
            )
        )
    for path in unsafe_staging:
        findings.append(
            ReconciliationFinding(
                "UNSAFE_STAGING_ENTRY",
                "error",
                _relative_path(root, path),
                None,
                "staging entry is a symlink or unsupported filesystem object",
            )
        )
    for error in staging_scan_errors:
        findings.append(
            ReconciliationFinding(
                "STAGING_SCAN_ERROR", "error", "tmp/artifacts", None, error
            )
        )
    findings.sort(
        key=lambda finding: (
            finding.code,
            finding.relative_path or "",
            finding.artifact_id or "",
        )
    )
    return ReconciliationReport(
        metadata_artifacts_scanned=len(expected),
        artifact_files_scanned=len(artifact_files),
        staging_entries_scanned=len(staging_files) + len(unsafe_staging),
        findings=tuple(findings),
    )
