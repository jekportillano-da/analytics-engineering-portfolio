with employment_summary as (
    select
        worker_id,
        min(hire_date) as first_hire_date,
        max(hire_date) as latest_hire_date,
        max(termination_date) as latest_termination_date,
        count(*) as employment_spell_count,
        max(
            case
                when hire_date <= date '{{ var("analysis_end_date") }}'
                    and (
                        termination_date is null
                        or termination_date > date '{{ var("analysis_end_date") }}'
                    )
                    then 1
                else 0
            end
        ) = 1 as is_active_at_analysis_end
    from {{ ref('int_employment_spells_validated') }}
    where is_usable
    group by worker_id
)

select
    workers.worker_id,
    summary.first_hire_date,
    summary.latest_hire_date,
    summary.latest_termination_date,
    coalesce(summary.employment_spell_count, 0) as employment_spell_count,
    coalesce(summary.is_active_at_analysis_end, false) as is_active_at_analysis_end
from {{ ref('stg_workers') }} as workers
left join employment_summary as summary using (worker_id)
