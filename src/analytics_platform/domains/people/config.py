from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class AnalysisConfig:
    source_history_start_date: date
    start_date: date
    end_date: date


@dataclass(frozen=True)
class PopulationConfig:
    worker_count: int
    termination_rate: float
    rehire_rate: float
    mobility_rate: float
    duplicate_sync_rate: float


@dataclass(frozen=True)
class QualityScenarioConfig:
    invalid_employment_dates: int
    missing_org_references: int
    overlapping_job_history: int


@dataclass(frozen=True)
class ScenarioConfig:
    version: int
    name: str
    seed: int
    analysis: AnalysisConfig
    population: PopulationConfig
    quality_scenarios: QualityScenarioConfig


def _as_date(value: Any, field_name: str) -> date:
    try:
        return date.fromisoformat(str(value))
    except ValueError as exc:
        raise ValueError(f"{field_name} must be an ISO date, received {value!r}") from exc


def _as_probability(value: Any, field_name: str) -> float:
    probability = float(value)
    if not 0 <= probability <= 1:
        raise ValueError(f"{field_name} must be between 0 and 1")
    return probability


def _as_non_negative_int(value: Any, field_name: str) -> int:
    integer = int(value)
    if integer < 0:
        raise ValueError(f"{field_name} must be zero or greater")
    return integer


def load_scenario(path: Path) -> ScenarioConfig:
    with path.open(encoding="utf-8") as stream:
        raw = yaml.safe_load(stream)

    if not isinstance(raw, dict):
        raise ValueError("Scenario configuration must be a mapping")

    version = int(raw.get("version", 0))
    if version != 1:
        raise ValueError(f"Unsupported scenario version {version}; expected 1")

    analysis_raw = raw["analysis"]
    population_raw = raw["population"]
    quality_raw = raw.get("quality_scenarios", {})

    analysis = AnalysisConfig(
        source_history_start_date=_as_date(
            analysis_raw["source_history_start_date"],
            "analysis.source_history_start_date",
        ),
        start_date=_as_date(analysis_raw["start_date"], "analysis.start_date"),
        end_date=_as_date(analysis_raw["end_date"], "analysis.end_date"),
    )
    if not (analysis.source_history_start_date <= analysis.start_date <= analysis.end_date):
        raise ValueError("Dates must satisfy source_history_start_date <= start_date <= end_date")

    worker_count = int(population_raw["worker_count"])
    if worker_count < 25:
        raise ValueError("population.worker_count must be at least 25")

    population = PopulationConfig(
        worker_count=worker_count,
        termination_rate=_as_probability(
            population_raw["termination_rate"], "population.termination_rate"
        ),
        rehire_rate=_as_probability(population_raw["rehire_rate"], "population.rehire_rate"),
        mobility_rate=_as_probability(population_raw["mobility_rate"], "population.mobility_rate"),
        duplicate_sync_rate=_as_probability(
            population_raw["duplicate_sync_rate"], "population.duplicate_sync_rate"
        ),
    )

    quality = QualityScenarioConfig(
        invalid_employment_dates=_as_non_negative_int(
            quality_raw.get("invalid_employment_dates", 0),
            "quality_scenarios.invalid_employment_dates",
        ),
        missing_org_references=_as_non_negative_int(
            quality_raw.get("missing_org_references", 0),
            "quality_scenarios.missing_org_references",
        ),
        overlapping_job_history=_as_non_negative_int(
            quality_raw.get("overlapping_job_history", 0),
            "quality_scenarios.overlapping_job_history",
        ),
    )

    return ScenarioConfig(
        version=version,
        name=str(raw["name"]),
        seed=int(raw["seed"]),
        analysis=analysis,
        population=population,
        quality_scenarios=quality,
    )
