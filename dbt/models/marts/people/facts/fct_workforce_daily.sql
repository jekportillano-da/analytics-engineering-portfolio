with active_employment as (
    select * from {{ ref('int_active_employment_daily') }}
),

matched_job_history as (
    select
        active.snapshot_date,
        active.employment_id,
        active.worker_id,
        active.hire_date,
        active.termination_date,
        history.job_history_id,
        coalesce(history.resolved_job_id, 'UNKNOWN') as job_id,
        coalesce(history.resolved_org_unit_id, 'UNKNOWN') as org_unit_id,
        coalesce(history.resolved_location_id, 'UNKNOWN') as location_id,
        history.manager_worker_id,
        history.employment_type,
        history.job_history_id is not null as has_job_assignment,
        row_number() over (
            partition by active.snapshot_date, active.employment_id
            order by
                history.effective_start_date desc nulls last,
                history.source_updated_at desc nulls last,
                history.job_history_id desc nulls last
        ) as job_assignment_rank
    from active_employment as active
    left join {{ ref('int_job_history_validated') }} as history
        on active.employment_id = history.employment_id
        and history.is_usable
        and active.snapshot_date >= history.effective_start_date
        and (
            history.effective_end_date is null
            or active.snapshot_date < history.effective_end_date
        )
)

select
    snapshot_date::varchar || '|' || employment_id as workforce_daily_id,
    snapshot_date,
    employment_id,
    worker_id,
    hire_date,
    termination_date,
    job_history_id,
    job_id,
    org_unit_id,
    location_id,
    manager_worker_id,
    employment_type,
    has_job_assignment
from matched_job_history
where job_assignment_rank = 1
