from __future__ import annotations

import hashlib
from pathlib import Path

RAW_TABLES = {
    "workers.csv": "workers",
    "employment_spells.csv": "employment_spells",
    "job_history.csv": "job_history",
    "jobs.csv": "jobs",
    "org_units.csv": "org_units",
    "locations.csv": "locations",
}

VERSIONED_RAW_TABLES = ("workers", "employment_spells", "job_history")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
