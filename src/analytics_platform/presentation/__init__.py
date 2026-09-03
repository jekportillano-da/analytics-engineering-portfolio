"""Deterministic, frontend-safe exports of governed analytical data products."""

from analytics_platform.presentation.contract import (
    PRESENTATION_CONTRACT_ID,
    PRESENTATION_CONTRACT_VERSION,
    validate_artifact_directory,
)
from analytics_platform.presentation.generator import build_presentation_artifacts
from analytics_platform.presentation.insights import (
    INSIGHT_CONTRACT_ID,
    INSIGHT_CONTRACT_VERSION,
    validate_insight_artifact,
)

__all__ = (
    "PRESENTATION_CONTRACT_ID",
    "PRESENTATION_CONTRACT_VERSION",
    "INSIGHT_CONTRACT_ID",
    "INSIGHT_CONTRACT_VERSION",
    "build_presentation_artifacts",
    "validate_artifact_directory",
    "validate_insight_artifact",
)
