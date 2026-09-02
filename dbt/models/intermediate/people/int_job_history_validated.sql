with history as (
    select * from {{ ref('stg_job_history') }}
),

employment as (
    select * from {{ ref('int_employment_spells_validated') }}
),

workers as (
    select worker_id from {{ ref('stg_workers') }}
),

jobs as (
    select job_id from {{ ref('stg_jobs') }} where job_id != 'UNKNOWN'
),

org_units as (
    select org_unit_id from {{ ref('stg_org_units') }} where org_unit_id != 'UNKNOWN'
),

locations as (
    select location_id from {{ ref('stg_locations') }} where location_id != 'UNKNOWN'
)

select
    history.*,
    employment.employment_id is not null as has_valid_employment,
    jobs.job_id is not null as has_valid_job,
    org_units.org_unit_id is not null as has_valid_org_unit,
    locations.location_id is not null as has_valid_location,
    (
        history.manager_worker_id is null
        or managers.worker_id is not null
    ) as has_valid_manager,
    (
        history.effective_start_date is not null
        and (
            history.effective_end_date is null
            or history.effective_end_date > history.effective_start_date
        )
    ) as has_valid_date_range,
    (
        employment.hire_date is not null
        and history.effective_start_date >= employment.hire_date
    ) as starts_within_employment,
    (
        employment.termination_date is null
        or (
            history.effective_end_date is not null
            and history.effective_end_date <= employment.termination_date
        )
    ) as ends_within_employment,
    case when jobs.job_id is null then 'UNKNOWN' else history.job_id end as resolved_job_id,
    case
        when org_units.org_unit_id is null then 'UNKNOWN'
        else history.org_unit_id
    end as resolved_org_unit_id,
    case
        when locations.location_id is null then 'UNKNOWN'
        else history.location_id
    end as resolved_location_id,
    (
        employment.is_usable
        and history.effective_start_date is not null
        and (
            history.effective_end_date is null
            or history.effective_end_date > history.effective_start_date
        )
        and history.effective_start_date >= employment.hire_date
        and (
            employment.termination_date is null
            or (
                history.effective_end_date is not null
                and history.effective_end_date <= employment.termination_date
            )
        )
    ) as is_usable
from history
left join employment using (employment_id)
left join workers as managers on history.manager_worker_id = managers.worker_id
left join jobs using (job_id)
left join org_units using (org_unit_id)
left join locations using (location_id)
