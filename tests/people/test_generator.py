from __future__ import annotations

import csv
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Any

from analytics_platform.domains.people.config import load_scenario
from analytics_platform.domains.people.generator import generate_dataset

EXPECTED_FILES = (
    "workers.csv",
    "employment_spells.csv",
    "job_history.csv",
    "jobs.csv",
    "org_units.csv",
    "locations.csv",
)


def _read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def _latest_rows(rows: list[dict[str, str]], key: str) -> dict[str, dict[str, str]]:
    latest: dict[str, dict[str, str]] = {}
    for row in rows:
        business_key = row[key]
        if (
            business_key not in latest
            or row["source_updated_at"] > latest[business_key]["source_updated_at"]
        ):
            latest[business_key] = row
    return latest


def test_generation_is_deterministic(tmp_path: Path, scenario_path: Path) -> None:
    config = load_scenario(scenario_path)
    first_dir = tmp_path / "first"
    second_dir = tmp_path / "second"

    first = generate_dataset(config, first_dir)
    second = generate_dataset(config, second_dir)

    assert first.row_counts == second.row_counts
    for filename in EXPECTED_FILES:
        assert (first_dir / filename).read_bytes() == (second_dir / filename).read_bytes()


def test_generation_includes_configured_quality_fixtures(
    tmp_path: Path, scenario_path: Path
) -> None:
    config = load_scenario(scenario_path)
    output_dir = tmp_path / "raw"

    generate_dataset(config, output_dir)

    employment_data = (output_dir / "employment_spells.csv").read_text(encoding="utf-8")
    job_history_data = (output_dir / "job_history.csv").read_text(encoding="utf-8")
    assert "EMP-QA-DATE-01" in employment_data
    assert "ORG-NOT-FOUND" in job_history_data
    assert "JH-QA-OVERLAP-01-A" in job_history_data
    assert "JH-QA-OVERLAP-01-B" in job_history_data


def test_generated_lifecycles_are_contiguous(tmp_path: Path, scenario_path: Path) -> None:
    config = load_scenario(scenario_path)
    output_dir = tmp_path / "raw"
    generate_dataset(config, output_dir)

    workers = _latest_rows(_read_rows(output_dir / "workers.csv"), "worker_id")
    employment = _latest_rows(_read_rows(output_dir / "employment_spells.csv"), "employment_id")
    history = _latest_rows(_read_rows(output_dir / "job_history.csv"), "job_history_id")
    job_ids = {row["job_id"] for row in _read_rows(output_dir / "jobs.csv")}
    org_ids = {row["org_unit_id"] for row in _read_rows(output_dir / "org_units.csv")}
    location_ids = {row["location_id"] for row in _read_rows(output_dir / "locations.csv")}

    history_by_employment: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in history.values():
        if not row["job_history_id"].startswith("JH-QA-"):
            history_by_employment[row["employment_id"]].append(row)

    employment_by_worker: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for employment_id, row in employment.items():
        if employment_id.startswith("EMP-QA-"):
            continue
        hire_date = date.fromisoformat(row["hire_date"])
        termination_date = (
            date.fromisoformat(row["termination_date"]) if row["termination_date"] else None
        )
        assert row["worker_id"] in workers
        assert termination_date is None or termination_date > hire_date
        employment_by_worker[row["worker_id"]].append(
            {"hire_date": hire_date, "termination_date": termination_date}
        )

        assignments = sorted(
            history_by_employment[employment_id],
            key=lambda assignment: assignment["effective_start_date"],
        )
        assert assignments
        assert assignments[0]["effective_start_date"] == row["hire_date"]
        for previous, current in zip(assignments, assignments[1:], strict=False):
            assert previous["effective_end_date"] == current["effective_start_date"]
        assert assignments[-1]["effective_end_date"] == row["termination_date"]

        for assignment in assignments:
            assert assignment["job_id"] in job_ids
            assert assignment["org_unit_id"] in org_ids
            assert assignment["location_id"] in location_ids
            assert not assignment["manager_worker_id"] or assignment["manager_worker_id"] in workers

    for spells in employment_by_worker.values():
        ordered = sorted(spells, key=lambda spell: spell["hire_date"])
        for previous, current in zip(ordered, ordered[1:], strict=False):
            assert previous["termination_date"] is not None
            assert current["hire_date"] > previous["termination_date"]
