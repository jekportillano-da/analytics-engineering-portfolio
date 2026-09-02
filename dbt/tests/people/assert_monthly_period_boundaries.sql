select *
from {{ ref('mart_workforce_monthly') }}
where
    period_end != least(
        last_day(period_start),
        date '{{ var("analysis_end_date") }}'
    )
    or calendar_days != {{ portable_date_diff(
        'day',
        "greatest(period_start, date '" ~ var('analysis_start_date') ~ "')",
        'period_end'
    ) }} + 1
