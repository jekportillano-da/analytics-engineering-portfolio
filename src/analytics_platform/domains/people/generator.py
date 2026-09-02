from __future__ import annotations

import csv
import random
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Any

from analytics_platform.domains.people.config import ScenarioConfig

ORG_UNITS = (
    ("ORG-ENG", "Engineering", "CC-100"),
    ("ORG-SALES", "Sales", "CC-200"),
    ("ORG-SUPPORT", "Customer Support", "CC-300"),
    ("ORG-OPS", "Operations", "CC-400"),
    ("ORG-PEOPLE", "People", "CC-500"),
    ("ORG-FIN", "Finance", "CC-600"),
)

LOCATIONS = (
    ("LOC-MNL", "Manila", "PH"),
    ("LOC-CEB", "Cebu", "PH"),
    ("LOC-AUS", "Austin", "US"),
    ("LOC-AMS", "Amsterdam", "NL"),
)

JOB_FAMILIES = {
    "ORG-ENG": "Engineering",
    "ORG-SALES": "Sales",
    "ORG-SUPPORT": "Customer Support",
    "ORG-OPS": "Operations",
    "ORG-PEOPLE": "People Operations",
    "ORG-FIN": "Finance",
}

LEVEL_TITLES = {
    1: "Associate",
    2: "Specialist",
    3: "Senior Specialist",
    4: "Manager",
    5: "Director",
}

VOLUNTARY_REASONS = ("career_move", "personal_reasons", "relocation", "education")
INVOLUNTARY_REASONS = ("performance", "position_elimination", "end_of_contract")
EMPLOYMENT_TYPES = ("full_time", "full_time", "full_time", "part_time", "contractor")


@dataclass(frozen=True)
class GenerationSummary:
    scenario_name: str
    output_dir: Path
    row_counts: dict[str, int]


def _random_date(rng: random.Random, start: date, end: date) -> date:
    if end < start:
        raise ValueError(f"Cannot choose a date between {start} and {end}")
    return start + timedelta(days=rng.randint(0, (end - start).days))


def _timestamp(day: date, offset_seconds: int = 0) -> str:
    value = datetime.combine(day, time(12, 0)) + timedelta(seconds=offset_seconds)
    return value.isoformat(timespec="seconds")


def _write_csv(path: Path, rows: list[dict[str, Any]], fields: Iterable[str]) -> None:
    fieldnames = list(fields)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _jobs() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for org_id, family in JOB_FAMILIES.items():
        prefix = org_id.removeprefix("ORG-")
        for level, level_title in LEVEL_TITLES.items():
            rows.append(
                {
                    "job_id": f"JOB-{prefix}-{level}",
                    "job_name": f"{level_title}, {family}",
                    "job_family": family,
                    "job_level": level,
                }
            )
    return rows


def _choose_manager(
    rng: random.Random,
    manager_ids_by_org: dict[str, list[str]],
    org_id: str,
    worker_id: str,
) -> str:
    choices = [candidate for candidate in manager_ids_by_org[org_id] if candidate != worker_id]
    return rng.choice(choices) if choices else ""


def _job_id(org_id: str, level: int) -> str:
    return f"JOB-{org_id.removeprefix('ORG-')}-{max(1, min(level, 5))}"


def _source_row(
    business_id: str,
    version: int,
    row: dict[str, Any],
    updated_at: str,
) -> dict[str, Any]:
    return {
        "source_record_id": f"SRC-{business_id}-{version}",
        **row,
        "source_updated_at": updated_at,
    }


def generate_dataset(config: ScenarioConfig, output_dir: Path) -> GenerationSummary:
    rng = random.Random(config.seed)
    output_dir.mkdir(parents=True, exist_ok=True)

    org_ids = [row[0] for row in ORG_UNITS]
    location_ids = [row[0] for row in LOCATIONS]
    worker_ids = [f"WRK-{index:04d}" for index in range(1, config.population.worker_count + 1)]

    manager_ids_by_org: dict[str, list[str]] = {org_id: [] for org_id in org_ids}
    worker_home_org: dict[str, str] = {}
    worker_initial_level: dict[str, int] = {}
    for index, worker_id in enumerate(worker_ids):
        if index < len(org_ids) * 2:
            org_id = org_ids[index % len(org_ids)]
            manager_ids_by_org[org_id].append(worker_id)
            level = 5 if index < len(org_ids) else 4
        else:
            org_id = rng.choices(org_ids, weights=(25, 17, 22, 20, 9, 7), k=1)[0]
            level = rng.choices((1, 2, 3), weights=(45, 40, 15), k=1)[0]
        worker_home_org[worker_id] = org_id
        worker_initial_level[worker_id] = level

    worker_rows: list[dict[str, Any]] = []
    employment_rows: list[dict[str, Any]] = []
    job_history_rows: list[dict[str, Any]] = []
    load_day = config.analysis.end_date + timedelta(days=1)

    for worker_index, worker_id in enumerate(worker_ids, start=1):
        is_seed_manager = worker_index <= len(org_ids) * 2
        latest_hire = max(
            config.analysis.source_history_start_date,
            config.analysis.end_date - timedelta(days=45),
        )
        if is_seed_manager:
            first_hire_end = min(
                latest_hire,
                max(
                    config.analysis.source_history_start_date,
                    config.analysis.start_date - timedelta(days=180),
                ),
            )
        else:
            first_hire_end = latest_hire
        first_hire = _random_date(
            rng,
            config.analysis.source_history_start_date,
            first_hire_end,
        )

        worker_base = {
            "worker_id": worker_id,
            "source_created_at": _timestamp(first_hire),
        }
        if rng.random() < config.population.duplicate_sync_rate:
            worker_rows.append(
                _source_row(
                    worker_id,
                    1,
                    worker_base,
                    _timestamp(load_day - timedelta(days=1), worker_index),
                )
            )
            worker_version = 2
        else:
            worker_version = 1
        worker_rows.append(
            _source_row(
                worker_id,
                worker_version,
                worker_base,
                _timestamp(load_day, worker_index),
            )
        )

        spells: list[tuple[date, date | None]] = []
        first_termination: date | None = None
        can_terminate = first_hire <= config.analysis.end_date - timedelta(days=120)
        if can_terminate and rng.random() < config.population.termination_rate:
            first_termination = _random_date(
                rng,
                first_hire + timedelta(days=90),
                config.analysis.end_date - timedelta(days=15),
            )
        spells.append((first_hire, first_termination))

        if first_termination and rng.random() < config.population.rehire_rate:
            earliest_rehire = first_termination + timedelta(days=45)
            latest_rehire = config.analysis.end_date - timedelta(days=45)
            if earliest_rehire <= latest_rehire:
                rehire_date = _random_date(rng, earliest_rehire, latest_rehire)
                second_termination: date | None = None
                if (
                    rehire_date <= config.analysis.end_date - timedelta(days=150)
                    and rng.random() < config.population.termination_rate / 2
                ):
                    second_termination = _random_date(
                        rng,
                        rehire_date + timedelta(days=90),
                        config.analysis.end_date - timedelta(days=15),
                    )
                spells.append((rehire_date, second_termination))

        for spell_index, (hire_date, termination_date) in enumerate(spells, start=1):
            employment_id = f"EMP-{worker_index:04d}-{spell_index:02d}"
            if termination_date:
                termination_category = "voluntary" if rng.random() < 0.7 else "involuntary"
                reason_pool = (
                    VOLUNTARY_REASONS
                    if termination_category == "voluntary"
                    else INVOLUNTARY_REASONS
                )
                termination_reason = rng.choice(reason_pool)
            else:
                termination_category = ""
                termination_reason = ""

            employment_base = {
                "employment_id": employment_id,
                "worker_id": worker_id,
                "hire_date": hire_date.isoformat(),
                "termination_date": termination_date.isoformat() if termination_date else "",
                "termination_category": termination_category,
                "termination_reason": termination_reason,
            }
            if rng.random() < config.population.duplicate_sync_rate:
                stale_row = {
                    **employment_base,
                    "termination_date": (
                        "" if termination_date else employment_base["termination_date"]
                    ),
                    "termination_category": "" if termination_date else termination_category,
                    "termination_reason": "" if termination_date else termination_reason,
                }
                employment_rows.append(
                    _source_row(
                        employment_id,
                        1,
                        stale_row,
                        _timestamp(load_day - timedelta(days=1), worker_index),
                    )
                )
                employment_version = 2
            else:
                employment_version = 1
            employment_rows.append(
                _source_row(
                    employment_id,
                    employment_version,
                    employment_base,
                    _timestamp(load_day, worker_index + spell_index),
                )
            )

            assignment_end = termination_date or (config.analysis.end_date + timedelta(days=1))
            duration_days = (assignment_end - hire_date).days
            change_dates: list[date] = []
            if duration_days >= 300 and rng.random() < config.population.mobility_rate:
                change_dates.append(
                    _random_date(
                        rng,
                        hire_date + timedelta(days=150),
                        assignment_end - timedelta(days=90),
                    )
                )
            if (
                duration_days >= 700
                and change_dates
                and rng.random() < config.population.mobility_rate / 2
            ):
                second_start = max(
                    change_dates[-1] + timedelta(days=150),
                    hire_date + timedelta(days=300),
                )
                second_end = assignment_end - timedelta(days=90)
                if second_start <= second_end:
                    change_dates.append(_random_date(rng, second_start, second_end))
            change_dates = sorted(set(change_dates))

            current_org = worker_home_org[worker_id]
            current_level = worker_initial_level[worker_id]
            current_location = rng.choices(location_ids, weights=(55, 18, 17, 10), k=1)[0]
            current_employment_type = rng.choice(EMPLOYMENT_TYPES)
            segment_starts = [hire_date, *change_dates]
            segment_ends = [*change_dates, assignment_end]

            for segment_index, (segment_start, segment_end) in enumerate(
                zip(segment_starts, segment_ends, strict=True),
                start=1,
            ):
                if segment_index > 1:
                    change_type = rng.choices(
                        ("promotion", "transfer", "manager_change"),
                        weights=(45, 30, 25),
                        k=1,
                    )[0]
                    if change_type == "promotion":
                        current_level = min(5, current_level + 1)
                    elif change_type == "transfer":
                        current_org = rng.choice([org for org in org_ids if org != current_org])
                        current_level = min(current_level, 3)
                    if rng.random() < 0.2:
                        current_location = rng.choice(location_ids)

                history_id = f"JH-{worker_index:04d}-{spell_index:02d}-{segment_index:02d}"
                manager_id = (
                    ""
                    if current_level >= 5
                    else _choose_manager(rng, manager_ids_by_org, current_org, worker_id)
                )
                history_base = {
                    "job_history_id": history_id,
                    "employment_id": employment_id,
                    "effective_start_date": segment_start.isoformat(),
                    "effective_end_date": (
                        segment_end.isoformat()
                        if termination_date or segment_index < len(segment_starts)
                        else ""
                    ),
                    "job_id": _job_id(current_org, current_level),
                    "org_unit_id": current_org,
                    "location_id": current_location,
                    "manager_worker_id": manager_id,
                    "employment_type": current_employment_type,
                }
                if rng.random() < config.population.duplicate_sync_rate:
                    stale_history = {
                        **history_base,
                        "manager_worker_id": "",
                    }
                    job_history_rows.append(
                        _source_row(
                            history_id,
                            1,
                            stale_history,
                            _timestamp(load_day - timedelta(days=1), worker_index),
                        )
                    )
                    history_version = 2
                else:
                    history_version = 1
                job_history_rows.append(
                    _source_row(
                        history_id,
                        history_version,
                        history_base,
                        _timestamp(load_day, worker_index + segment_index),
                    )
                )

    _add_quality_scenarios(
        config=config,
        worker_rows=worker_rows,
        employment_rows=employment_rows,
        job_history_rows=job_history_rows,
        load_day=load_day,
    )

    jobs_rows = _jobs()
    org_rows = [
        {"org_unit_id": org_id, "org_unit_name": name, "cost_center": cost_center}
        for org_id, name, cost_center in ORG_UNITS
    ]
    location_rows = [
        {"location_id": location_id, "location_name": name, "country_code": country}
        for location_id, name, country in LOCATIONS
    ]

    datasets: dict[str, tuple[list[dict[str, Any]], tuple[str, ...]]] = {
        "workers.csv": (
            sorted(worker_rows, key=lambda row: (row["worker_id"], row["source_updated_at"])),
            ("source_record_id", "worker_id", "source_created_at", "source_updated_at"),
        ),
        "employment_spells.csv": (
            sorted(
                employment_rows,
                key=lambda row: (row["employment_id"], row["source_updated_at"]),
            ),
            (
                "source_record_id",
                "employment_id",
                "worker_id",
                "hire_date",
                "termination_date",
                "termination_category",
                "termination_reason",
                "source_updated_at",
            ),
        ),
        "job_history.csv": (
            sorted(
                job_history_rows,
                key=lambda row: (row["job_history_id"], row["source_updated_at"]),
            ),
            (
                "source_record_id",
                "job_history_id",
                "employment_id",
                "effective_start_date",
                "effective_end_date",
                "job_id",
                "org_unit_id",
                "location_id",
                "manager_worker_id",
                "employment_type",
                "source_updated_at",
            ),
        ),
        "jobs.csv": (
            jobs_rows,
            ("job_id", "job_name", "job_family", "job_level"),
        ),
        "org_units.csv": (
            org_rows,
            ("org_unit_id", "org_unit_name", "cost_center"),
        ),
        "locations.csv": (
            location_rows,
            ("location_id", "location_name", "country_code"),
        ),
    }

    row_counts: dict[str, int] = {}
    for filename, (rows, fields) in datasets.items():
        _write_csv(output_dir / filename, rows, fields)
        row_counts[filename] = len(rows)

    return GenerationSummary(
        scenario_name=config.name,
        output_dir=output_dir,
        row_counts=row_counts,
    )


def _add_quality_scenarios(
    config: ScenarioConfig,
    worker_rows: list[dict[str, Any]],
    employment_rows: list[dict[str, Any]],
    job_history_rows: list[dict[str, Any]],
    load_day: date,
) -> None:
    update_timestamp = _timestamp(load_day, 900_000)

    for index in range(1, config.quality_scenarios.invalid_employment_dates + 1):
        worker_id = f"WRK-QA-DATE-{index:02d}"
        employment_id = f"EMP-QA-DATE-{index:02d}"
        worker_rows.append(
            _source_row(
                worker_id,
                1,
                {"worker_id": worker_id, "source_created_at": "2025-06-01T12:00:00"},
                update_timestamp,
            )
        )
        employment_rows.append(
            _source_row(
                employment_id,
                1,
                {
                    "employment_id": employment_id,
                    "worker_id": worker_id,
                    "hire_date": "2025-06-01",
                    "termination_date": "2025-05-15",
                    "termination_category": "voluntary",
                    "termination_reason": "career_move",
                },
                update_timestamp,
            )
        )
        job_history_rows.append(
            _source_row(
                f"JH-QA-DATE-{index:02d}",
                1,
                {
                    "job_history_id": f"JH-QA-DATE-{index:02d}",
                    "employment_id": employment_id,
                    "effective_start_date": "2025-06-01",
                    "effective_end_date": "",
                    "job_id": "JOB-OPS-1",
                    "org_unit_id": "ORG-OPS",
                    "location_id": "LOC-MNL",
                    "manager_worker_id": "",
                    "employment_type": "full_time",
                },
                update_timestamp,
            )
        )

    for index in range(1, config.quality_scenarios.missing_org_references + 1):
        worker_id = f"WRK-QA-ORG-{index:02d}"
        employment_id = f"EMP-QA-ORG-{index:02d}"
        worker_rows.append(
            _source_row(
                worker_id,
                1,
                {"worker_id": worker_id, "source_created_at": "2024-01-15T12:00:00"},
                update_timestamp,
            )
        )
        employment_rows.append(
            _source_row(
                employment_id,
                1,
                {
                    "employment_id": employment_id,
                    "worker_id": worker_id,
                    "hire_date": "2024-01-15",
                    "termination_date": "",
                    "termination_category": "",
                    "termination_reason": "",
                },
                update_timestamp,
            )
        )
        job_history_rows.append(
            _source_row(
                f"JH-QA-ORG-{index:02d}",
                1,
                {
                    "job_history_id": f"JH-QA-ORG-{index:02d}",
                    "employment_id": employment_id,
                    "effective_start_date": "2024-01-15",
                    "effective_end_date": "",
                    "job_id": "JOB-OPS-1",
                    "org_unit_id": "ORG-NOT-FOUND",
                    "location_id": "LOC-MNL",
                    "manager_worker_id": "",
                    "employment_type": "full_time",
                },
                update_timestamp,
            )
        )

    for index in range(1, config.quality_scenarios.overlapping_job_history + 1):
        worker_id = f"WRK-QA-OVERLAP-{index:02d}"
        employment_id = f"EMP-QA-OVERLAP-{index:02d}"
        worker_rows.append(
            _source_row(
                worker_id,
                1,
                {"worker_id": worker_id, "source_created_at": "2024-01-01T12:00:00"},
                update_timestamp,
            )
        )
        employment_rows.append(
            _source_row(
                employment_id,
                1,
                {
                    "employment_id": employment_id,
                    "worker_id": worker_id,
                    "hire_date": "2024-01-01",
                    "termination_date": "",
                    "termination_category": "",
                    "termination_reason": "",
                },
                update_timestamp,
            )
        )
        for history_suffix, start_date, end_date, job_id in (
            ("A", "2024-01-01", "2025-01-01", "JOB-SUPPORT-1"),
            ("B", "2024-10-01", "", "JOB-SUPPORT-2"),
        ):
            history_id = f"JH-QA-OVERLAP-{index:02d}-{history_suffix}"
            job_history_rows.append(
                _source_row(
                    history_id,
                    1,
                    {
                        "job_history_id": history_id,
                        "employment_id": employment_id,
                        "effective_start_date": start_date,
                        "effective_end_date": end_date,
                        "job_id": job_id,
                        "org_unit_id": "ORG-SUPPORT",
                        "location_id": "LOC-MNL",
                        "manager_worker_id": "",
                        "employment_type": "full_time",
                    },
                    update_timestamp,
                )
            )
