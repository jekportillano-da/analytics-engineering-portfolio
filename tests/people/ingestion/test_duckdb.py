from __future__ import annotations

from pathlib import Path

import duckdb

from analytics_platform.domains.people.config import load_scenario
from analytics_platform.domains.people.generator import generate_dataset
from analytics_platform.domains.people.ingestion.duckdb import (
    RAW_TABLES,
    load_raw_dataset,
    verify_raw_dataset,
)


def test_loader_preserves_every_source_file(tmp_path: Path, scenario_path: Path) -> None:
    config = load_scenario(scenario_path)
    raw_dir = tmp_path / "raw"
    database_path = tmp_path / "warehouse.duckdb"
    generation = generate_dataset(config, raw_dir)

    loaded = load_raw_dataset(raw_dir, database_path, reset=True)
    verified = verify_raw_dataset(raw_dir, database_path)

    assert set(loaded.row_counts) == set(RAW_TABLES.values())
    assert verified.row_counts == loaded.row_counts
    assert verified.manifest_count == len(RAW_TABLES)
    connection = duckdb.connect(str(database_path), read_only=True)
    try:
        manifest_count = connection.execute("select count(*) from raw.file_manifest").fetchone()[0]
        invalid_fixture_count = connection.execute(
            """
            select count(*)
            from raw.employment_spells
            where employment_id like 'EMP-QA-DATE-%'
            """
        ).fetchone()[0]
    finally:
        connection.close()

    assert manifest_count == len(RAW_TABLES)
    assert invalid_fixture_count == 1
    assert generation.row_counts["workers.csv"] == loaded.row_counts["workers"]
