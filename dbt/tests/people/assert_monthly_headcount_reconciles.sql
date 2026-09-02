select *
from {{ ref('mart_headcount_reconciliation') }}
where not is_reconciled
