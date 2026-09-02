from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import duckdb

from analytics_platform.domains.people.ingestion.raw import (
    RAW_TABLES,
    VERSIONED_RAW_TABLES,
    sha256_file,
)


@dataclass(frozen=True)
class LoadSummary:
    database_path: Path
    row_counts: dict[str, int]


@dataclass(frozen=True)
class RawVerificationSummary:
    database_path: Path
    row_counts: dict[str, int]
    manifest_count: int


def _sql_string(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def load_raw_dataset(raw_dir: Path, database_path: Path, reset: bool = False) -> LoadSummary:
    missing = [filename for filename in RAW_TABLES if not (raw_dir / filename).is_file()]
    if missing:
        missing_list = ", ".join(missing)
        raise FileNotFoundError(f"Missing generated source files: {missing_list}")

    database_path.parent.mkdir(parents=True, exist_ok=True)
    if reset:
        database_path.unlink(missing_ok=True)
        database_path.with_suffix(database_path.suffix + ".wal").unlink(missing_ok=True)

    loaded_at = datetime.now(UTC).replace(tzinfo=None)
    loaded_at_sql = _sql_string(loaded_at.isoformat(sep=" "))
    connection = duckdb.connect(str(database_path))
    row_counts: dict[str, int] = {}
    manifest_rows: list[tuple[str, str, int, datetime]] = []
    try:
        connection.execute("drop schema if exists raw cascade")
        connection.execute("create schema raw")

        for filename, table_name in RAW_TABLES.items():
            file_path = (raw_dir / filename).resolve()
            connection.execute(
                f"""
                create table raw.{table_name} as
                select
                    *,
                    {_sql_string(filename)}::varchar as _source_file,
                    {loaded_at_sql}::timestamp as _loaded_at
                from read_csv(
                    {_sql_string(file_path.as_posix())},
                    header = true,
                    all_varchar = true,
                    null_padding = true
                )
                """
            )
            row_count = connection.execute(f"select count(*) from raw.{table_name}").fetchone()[0]
            row_counts[table_name] = row_count
            manifest_rows.append((filename, sha256_file(file_path), row_count, loaded_at))

        connection.execute(
            """
            create table raw.file_manifest (
                file_name varchar not null,
                sha256 varchar not null,
                row_count bigint not null,
                loaded_at timestamp not null
            )
            """
        )
        connection.executemany(
            "insert into raw.file_manifest values (?, ?, ?, ?)",
            manifest_rows,
        )
    finally:
        connection.close()

    return LoadSummary(database_path=database_path, row_counts=row_counts)


def verify_raw_dataset(raw_dir: Path, database_path: Path) -> RawVerificationSummary:
    connection = duckdb.connect(str(database_path), read_only=True)
    row_counts: dict[str, int] = {}
    try:
        manifest_rows = connection.execute(
            "select file_name, sha256, row_count, loaded_at from raw.file_manifest"
        ).fetchall()
        manifest = {row[0]: row[1:] for row in manifest_rows}
        if len(manifest) != len(manifest_rows) or set(manifest) != set(RAW_TABLES):
            raise ValueError("Raw file manifest does not match the expected source files")

        for filename, table_name in RAW_TABLES.items():
            source_path = (raw_dir / filename).resolve()
            manifest_sha256, manifest_row_count, loaded_at = manifest[filename]
            row_count = connection.execute(f"select count(*) from raw.{table_name}").fetchone()[0]
            invalid_load_metadata = connection.execute(
                f"""
                select count(*)
                from raw.{table_name}
                where _source_file != ? or _loaded_at is null
                """,
                [filename],
            ).fetchone()[0]

            if manifest_sha256 != sha256_file(source_path):
                raise ValueError(f"SHA-256 mismatch for {filename}")
            if manifest_row_count != row_count:
                raise ValueError(f"Row-count mismatch for {filename}")
            if loaded_at is None or invalid_load_metadata:
                raise ValueError(f"Incomplete load metadata for {filename}")

            if table_name in VERSIONED_RAW_TABLES:
                missing_source_metadata = connection.execute(
                    f"""
                    select count(*)
                    from raw.{table_name}
                    where coalesce(source_record_id, '') = ''
                       or coalesce(source_updated_at, '') = ''
                    """
                ).fetchone()[0]
                if missing_source_metadata:
                    raise ValueError(f"Incomplete source metadata for {filename}")

            row_counts[table_name] = row_count
    finally:
        connection.close()

    return RawVerificationSummary(
        database_path=database_path,
        row_counts=row_counts,
        manifest_count=len(manifest_rows),
    )
