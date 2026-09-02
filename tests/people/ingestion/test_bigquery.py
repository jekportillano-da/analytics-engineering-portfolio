from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from google.api_core.exceptions import NotFound
from google.cloud import bigquery

from analytics_platform.domains.people.config import load_scenario
from analytics_platform.domains.people.generator import generate_dataset
from analytics_platform.domains.people.ingestion.bigquery import (
    load_raw_dataset,
    verify_raw_dataset,
)
from analytics_platform.domains.people.ingestion.raw import RAW_TABLES, sha256_file

PROJECT_ID = "analytics-portfolio-101416"
DATASET_ID = "analytics_portfolio_people_raw"
LOCATION = "US"


def _job_with_rows(rows: list[dict[str, object]]) -> SimpleNamespace:
    return SimpleNamespace(result=lambda: iter(rows))


def test_loader_preserves_source_strings_and_adds_metadata(
    tmp_path: Path, scenario_path: Path
) -> None:
    raw_dir = tmp_path / "raw"
    generation = generate_dataset(load_scenario(scenario_path), raw_dir)
    client = MagicMock(spec=bigquery.Client)
    client.project = PROJECT_ID
    client.get_dataset.side_effect = NotFound("dataset does not exist")
    client.create_dataset.side_effect = lambda dataset: dataset
    client.load_table_from_json.return_value.result.return_value = None
    expected_counts = [
        generation.row_counts[filename] for filename in RAW_TABLES
    ] + [len(RAW_TABLES)]
    client.get_table.side_effect = [
        SimpleNamespace(num_rows=row_count) for row_count in expected_counts
    ]

    summary = load_raw_dataset(
        raw_dir,
        PROJECT_ID,
        DATASET_ID,
        LOCATION,
        replace=True,
        client=client,
    )

    assert summary.dataset_created is True
    assert summary.row_counts == {
        table_name: generation.row_counts[filename]
        for filename, table_name in RAW_TABLES.items()
    }
    assert summary.manifest_count == len(RAW_TABLES)
    assert client.load_table_from_json.call_count == len(RAW_TABLES) + 1
    first_rows = client.load_table_from_json.call_args_list[0].args[0]
    first_config = client.load_table_from_json.call_args_list[0].kwargs["job_config"]
    assert first_rows
    source_columns = [field.name for field in first_config.schema[:-2]]
    assert all(isinstance(first_rows[0][column], str) for column in source_columns)
    assert first_rows[0]["_source_file"] == "workers.csv"
    assert isinstance(first_rows[0]["_loaded_at"], str)
    assert first_config.write_disposition == bigquery.WriteDisposition.WRITE_TRUNCATE


def test_loader_rejects_existing_dataset_in_another_location(
    tmp_path: Path, scenario_path: Path
) -> None:
    raw_dir = tmp_path / "raw"
    generate_dataset(load_scenario(scenario_path), raw_dir)
    client = MagicMock(spec=bigquery.Client)
    client.project = PROJECT_ID
    client.get_dataset.return_value = SimpleNamespace(location="EU")

    with pytest.raises(ValueError, match="configured location US"):
        load_raw_dataset(
            raw_dir,
            PROJECT_ID,
            DATASET_ID,
            LOCATION,
            client=client,
        )

    client.load_table_from_json.assert_not_called()


def test_verifier_checks_manifest_counts_and_source_metadata(
    tmp_path: Path, scenario_path: Path
) -> None:
    raw_dir = tmp_path / "raw"
    generation = generate_dataset(load_scenario(scenario_path), raw_dir)
    client = MagicMock(spec=bigquery.Client)
    client.project = PROJECT_ID
    client.get_dataset.return_value = SimpleNamespace(location=LOCATION)
    manifest_rows = [
        {
            "file_name": filename,
            "sha256": sha256_file(raw_dir / filename),
            "row_count": generation.row_counts[filename],
            "loaded_at": object(),
        }
        for filename in RAW_TABLES
    ]
    validation_rows: Iterator[list[dict[str, int]]] = iter(
        [
            [
                {
                    "row_count": generation.row_counts[filename],
                    "invalid_load_metadata": 0,
                    "missing_source_metadata": 0,
                }
            ]
            for filename in RAW_TABLES
        ]
    )

    def query(sql: str, **_: object) -> SimpleNamespace:
        if "from `analytics-portfolio-101416.analytics_portfolio_people_raw.file_manifest`" in sql:
            return _job_with_rows(manifest_rows)
        return _job_with_rows(next(validation_rows))

    client.query.side_effect = query

    summary = verify_raw_dataset(
        raw_dir,
        PROJECT_ID,
        DATASET_ID,
        LOCATION,
        client=client,
    )

    assert summary.manifest_count == len(RAW_TABLES)
    assert summary.row_counts == {
        table_name: generation.row_counts[filename]
        for filename, table_name in RAW_TABLES.items()
    }


def test_verifier_does_not_create_a_missing_dataset(tmp_path: Path) -> None:
    client = MagicMock(spec=bigquery.Client)
    client.project = PROJECT_ID
    client.get_dataset.side_effect = NotFound("dataset does not exist")

    with pytest.raises(ValueError, match="does not exist"):
        verify_raw_dataset(
            tmp_path,
            PROJECT_ID,
            DATASET_ID,
            LOCATION,
            client=client,
        )

    client.create_dataset.assert_not_called()
