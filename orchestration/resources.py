"""Environment-driven Dagster resources and the authoritative dbt CLI boundary."""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence

from dagster import ConfigurableResource


class DbtExecutionError(RuntimeError):
    """Raised when dbt returns a non-zero exit code."""


@dataclass(frozen=True)
class DbtCommandResult:
    command: tuple[str, ...]
    output: str


class PortfolioConfigResource(ConfigurableResource):
    """Configuration shared by domain ingestion and dbt orchestration assets."""

    project_id: str
    people_raw_dataset: str
    wage_raw_dataset: str
    dbt_base_dataset: str
    location: str
    people_scenario_path: str
    people_raw_dir: str
    wage_local_root: str

    @classmethod
    def from_environment(cls, project_root: Path) -> "PortfolioConfigResource":
        scenario_default = (
            project_root
            / "src"
            / "analytics_platform"
            / "domains"
            / "people"
            / "scenarios"
            / "baseline.yml"
        )
        return cls(
            project_id=os.environ.get("BIGQUERY_PROJECT", ""),
            people_raw_dataset=os.environ.get("PEOPLE_BIGQUERY_RAW_DATASET", ""),
            wage_raw_dataset=os.environ.get("WAGE_BIGQUERY_RAW_DATASET", ""),
            dbt_base_dataset=os.environ.get("DBT_BIGQUERY_DATASET", ""),
            location=os.environ.get("BIGQUERY_LOCATION", ""),
            people_scenario_path=os.environ.get(
                "PEOPLE_SCENARIO_PATH", str(scenario_default)
            ),
            people_raw_dir=os.environ.get(
                "PEOPLE_ORCHESTRATION_RAW_DIR",
                str(project_root / ".local" / "dagster" / "people" / "raw"),
            ),
            wage_local_root=os.environ.get(
                "WAGE_OPENSTAT_LOCAL_ROOT",
                str(project_root / ".local" / "wage" / "openstat"),
            ),
        )

    def validate_cloud(self) -> None:
        required = {
            "BIGQUERY_PROJECT": self.project_id,
            "PEOPLE_BIGQUERY_RAW_DATASET": self.people_raw_dataset,
            "WAGE_BIGQUERY_RAW_DATASET": self.wage_raw_dataset,
            "DBT_BIGQUERY_DATASET": self.dbt_base_dataset,
            "BIGQUERY_LOCATION": self.location,
        }
        missing = [name for name, value in required.items() if not value.strip()]
        if missing:
            raise ValueError(
                "Missing required orchestration environment configuration: "
                + ", ".join(missing)
            )

    def dbt_environment(self) -> dict[str, str]:
        self.validate_cloud()
        return {
            "BIGQUERY_PROJECT": self.project_id,
            "PEOPLE_BIGQUERY_RAW_DATASET": self.people_raw_dataset,
            "WAGE_BIGQUERY_RAW_DATASET": self.wage_raw_dataset,
            "DBT_BIGQUERY_DATASET": self.dbt_base_dataset,
            "BIGQUERY_LOCATION": self.location,
        }


class DbtCliResource(ConfigurableResource):
    """Runs the repository's pinned dbt CLI without reimplementing its graph."""

    executable: str
    project_dir: str
    profiles_dir: str
    target: str = "bigquery"

    def validate_project(self) -> tuple[str, Path, Path]:
        project_dir = Path(self.project_dir).resolve()
        profiles_dir = Path(self.profiles_dir).resolve()
        if not (project_dir / "dbt_project.yml").is_file():
            raise FileNotFoundError(f"dbt project not found at {project_dir}")
        if not (profiles_dir / "profiles.yml").is_file():
            raise FileNotFoundError(f"dbt profiles not found at {profiles_dir}")

        executable_path = Path(self.executable)
        resolved_executable = (
            str(executable_path.resolve())
            if executable_path.is_file()
            else shutil.which(self.executable)
        )
        if not resolved_executable:
            raise FileNotFoundError(f"dbt executable not found: {self.executable}")
        return resolved_executable, project_dir, profiles_dir

    def run(
        self,
        arguments: Sequence[str],
        environment: Mapping[str, str],
    ) -> DbtCommandResult:
        executable, project_dir, profiles_dir = self.validate_project()
        command = (
            executable,
            *arguments,
            "--project-dir",
            str(project_dir),
            "--profiles-dir",
            str(profiles_dir),
            "--target",
            self.target,
            "--no-partial-parse",
        )
        process_environment = os.environ.copy()
        process_environment.update(environment)
        completed = subprocess.run(
            command,
            cwd=project_dir.parent,
            env=process_environment,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if completed.returncode:
            output_tail = completed.stdout[-8_000:]
            raise DbtExecutionError(
                f"dbt exited with code {completed.returncode}: {' '.join(arguments)}\n"
                f"{output_tail}"
            )
        return DbtCommandResult(command=tuple(command), output=completed.stdout)
