"""Versioned presentation envelope, canonical JSON, and safety validation."""

from __future__ import annotations

import json
import math
import os
import re
from pathlib import Path
from typing import Mapping


PRESENTATION_CONTRACT_VERSION = 1
PRESENTATION_CONTRACT_ID = "analytics-portfolio-presentation-v1"
ARTIFACT_TYPES = ("insights", "lineage", "people", "platform", "quality", "wage")
ARTIFACT_FILENAMES = tuple(f"{name}.json" for name in ARTIFACT_TYPES)

_FORBIDDEN_KEY = re.compile(
    r"(?:^|_)(?:api_key|client_secret|credential|password|private_key|refresh_token|secret)(?:$|_)"
)
_WINDOWS_ABSOLUTE_PATH = re.compile(r"^[A-Za-z]:[\\/]")
_PRIVATE_KEY_MARKER = re.compile(r"BEGIN [A-Z ]*PRIVATE KEY")


class PresentationContractError(ValueError):
    """Raised when a presentation snapshot or artifact violates the contract."""


def canonical_json(value: object) -> str:
    """Return the only accepted on-disk JSON representation."""

    return (
        json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            indent=2,
        )
        + "\n"
    )


def load_json(path: Path) -> dict[str, object]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PresentationContractError(f"cannot load presentation JSON: {path}") from exc
    if not isinstance(value, dict):
        raise PresentationContractError(f"presentation JSON must be an object: {path}")
    return value


def _validate_frontend_safe(value: object, location: str = "root") -> None:
    if value is None or isinstance(value, (bool, int)):
        return
    if isinstance(value, float):
        if not math.isfinite(value):
            raise PresentationContractError(f"non-finite number at {location}")
        return
    if isinstance(value, str):
        if "\x00" in value or "\r" in value:
            raise PresentationContractError(f"noncanonical text at {location}")
        if _WINDOWS_ABSOLUTE_PATH.match(value) or value.startswith(("/Users/", "/home/")):
            raise PresentationContractError(f"machine-specific path at {location}")
        if _PRIVATE_KEY_MARKER.search(value):
            raise PresentationContractError(f"credential material at {location}")
        return
    if isinstance(value, list):
        for index, item in enumerate(value):
            _validate_frontend_safe(item, f"{location}[{index}]")
        return
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str) or not key:
                raise PresentationContractError(f"invalid object key at {location}")
            if _FORBIDDEN_KEY.search(key.lower()):
                raise PresentationContractError(f"forbidden field {key!r} at {location}")
            _validate_frontend_safe(item, f"{location}.{key}")
        return
    raise PresentationContractError(
        f"unsupported frontend value {type(value).__name__} at {location}"
    )


def validate_artifact(artifact: Mapping[str, object], artifact_type: str) -> None:
    if artifact_type not in ARTIFACT_TYPES:
        raise PresentationContractError(f"unknown presentation artifact: {artifact_type}")
    if set(artifact) != {
        "artifact_id",
        "artifact_type",
        "contract_id",
        "contract_version",
        "data",
    }:
        raise PresentationContractError(f"invalid {artifact_type} artifact envelope")
    if artifact["contract_version"] != PRESENTATION_CONTRACT_VERSION:
        raise PresentationContractError("unsupported presentation contract version")
    if artifact["contract_id"] != PRESENTATION_CONTRACT_ID:
        raise PresentationContractError("unexpected presentation contract ID")
    if artifact["artifact_type"] != artifact_type:
        raise PresentationContractError("artifact type does not match its filename")
    if artifact["artifact_id"] != f"presentation.{artifact_type}.v1":
        raise PresentationContractError("artifact ID is not the stable V1 identity")
    if not isinstance(artifact["data"], dict):
        raise PresentationContractError("artifact data must be an object")
    _validate_frontend_safe(dict(artifact))


def validate_artifact_directory(output_dir: Path) -> dict[str, dict[str, object]]:
    observed = {path.name for path in output_dir.glob("*.json")}
    expected = set(ARTIFACT_FILENAMES)
    if observed != expected:
        raise PresentationContractError(
            f"presentation artifact set differs: expected {sorted(expected)}, got {sorted(observed)}"
        )
    artifacts: dict[str, dict[str, object]] = {}
    for artifact_type in ARTIFACT_TYPES:
        path = output_dir / f"{artifact_type}.json"
        artifact = load_json(path)
        validate_artifact(artifact, artifact_type)
        if path.read_text(encoding="utf-8") != canonical_json(artifact):
            raise PresentationContractError(f"artifact is not canonical JSON: {path.name}")
        artifacts[artifact_type] = artifact
    from analytics_platform.presentation.insights import validate_insight_artifact

    validate_insight_artifact(artifacts["insights"], artifacts)
    return artifacts


def write_artifacts(
    output_dir: Path, artifacts: Mapping[str, Mapping[str, object]]
) -> None:
    if set(artifacts) != set(ARTIFACT_TYPES):
        raise PresentationContractError("generator did not produce the complete artifact set")
    for artifact_type, artifact in artifacts.items():
        validate_artifact(artifact, artifact_type)
    from analytics_platform.presentation.insights import validate_insight_artifact

    validate_insight_artifact(artifacts["insights"], artifacts)

    output_dir.mkdir(parents=True, exist_ok=True)
    staged_paths: list[Path] = []
    try:
        for artifact_type in ARTIFACT_TYPES:
            staged = output_dir / f".{artifact_type}.json.tmp"
            staged.write_text(
                canonical_json(dict(artifacts[artifact_type])), encoding="utf-8"
            )
            staged_paths.append(staged)
        for artifact_type, staged in zip(ARTIFACT_TYPES, staged_paths, strict=True):
            os.replace(staged, output_dir / f"{artifact_type}.json")
    finally:
        for staged in staged_paths:
            staged.unlink(missing_ok=True)
    validate_artifact_directory(output_dir)
