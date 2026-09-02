from __future__ import annotations

from pathlib import Path

import pytest
import yaml


@pytest.fixture
def scenario_path(tmp_path: Path) -> Path:
    scenario = {
        "version": 1,
        "name": "test",
        "seed": 42,
        "analysis": {
            "source_history_start_date": "2021-01-01",
            "start_date": "2023-01-01",
            "end_date": "2025-12-31",
        },
        "population": {
            "worker_count": 30,
            "termination_rate": 0.3,
            "rehire_rate": 0.1,
            "mobility_rate": 0.4,
            "duplicate_sync_rate": 0.1,
        },
        "quality_scenarios": {
            "invalid_employment_dates": 1,
            "missing_org_references": 1,
            "overlapping_job_history": 1,
        },
    }
    path = tmp_path / "scenario.yml"
    path.write_text(yaml.safe_dump(scenario, sort_keys=False), encoding="utf-8")
    return path
