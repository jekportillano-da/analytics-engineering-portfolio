select cast(calendar_date as date) as calendar_date
from generate_series(
    date '{{ var("analysis_start_date") }}',
    date '{{ var("analysis_end_date") }}',
    interval 1 day
) as generated(calendar_date)
