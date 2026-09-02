select daily.*
from {{ ref('fct_workforce_daily') }} as daily
where
    daily.termination_date is not null
    and daily.snapshot_date >= daily.termination_date
