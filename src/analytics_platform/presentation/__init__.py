"""Deterministic, frontend-safe exports of governed analytical data products."""

from analytics_platform.presentation.contract import (
    PRESENTATION_CONTRACT_ID,
    PRESENTATION_CONTRACT_VERSION,
    validate_artifact_directory,
)
from analytics_platform.presentation.generator import build_presentation_artifacts

__all__ = (
    "PRESENTATION_CONTRACT_ID",
    "PRESENTATION_CONTRACT_VERSION",
    "build_presentation_artifacts",
    "validate_artifact_directory",
)
