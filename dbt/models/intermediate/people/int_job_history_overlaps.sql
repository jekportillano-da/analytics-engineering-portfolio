with usable_history as (
    select
        *,
        max(coalesce(effective_end_date, date '9999-12-31')) over (
            partition by employment_id
            order by effective_start_date, job_history_id
            rows between unbounded preceding and 1 preceding
        ) as prior_max_end_date
    from {{ ref('int_job_history_validated') }}
    where is_usable
)

select
    employment_id,
    job_history_id,
    effective_start_date,
    effective_end_date,
    prior_max_end_date
from usable_history
where effective_start_date < prior_max_end_date
