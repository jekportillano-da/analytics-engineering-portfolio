with employment as (
    select * from {{ ref('stg_employment_spells') }}
),

workers as (
    select worker_id from {{ ref('stg_workers') }}
)

select
    employment.*,
    workers.worker_id is not null as has_valid_worker,
    employment.hire_date is not null as has_hire_date,
    (
        employment.termination_date is null
        or employment.termination_date > employment.hire_date
    ) as has_valid_date_range,
    (
        workers.worker_id is not null
        and employment.hire_date is not null
        and (
            employment.termination_date is null
            or employment.termination_date > employment.hire_date
        )
    ) as is_usable
from employment
left join workers using (worker_id)
