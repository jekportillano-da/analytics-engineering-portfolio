select
    date_spine.calendar_date as snapshot_date,
    employment.employment_id,
    employment.worker_id,
    employment.hire_date,
    employment.termination_date
from {{ ref('int_date_spine') }} as date_spine
inner join {{ ref('int_employment_spells_validated') }} as employment
    on date_spine.calendar_date >= employment.hire_date
    and (
        employment.termination_date is null
        or date_spine.calendar_date < employment.termination_date
    )
where employment.is_usable
