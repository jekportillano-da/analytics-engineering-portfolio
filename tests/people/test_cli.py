from __future__ import annotations

from pathlib import Path

import duckdb

from analytics_platform.domains.people.cli import main


def test_local_demo_generates_loads_and_verifies(
    tmp_path: Path,
    scenario_path: Path,
    capsys,
) -> None:
    raw_dir = tmp_path / "raw"
    database_path = tmp_path / "people.duckdb"

    result = main(
        [
            "--scenario",
            str(scenario_path),
            "--raw-dir",
            str(raw_dir),
            "--database",
            str(database_path),
        ]
    )

    assert result == 0
    assert database_path.is_file()
    connection = duckdb.connect(str(database_path), read_only=True)
    try:
        assert connection.execute("select count(*) from raw.file_manifest").fetchone()[0] == 6
    finally:
        connection.close()

    output = capsys.readouterr().out
    assert "Loaded raw sources" in output
    assert "Verified raw sources" in output
    assert "People local ingestion demo completed successfully." in output
