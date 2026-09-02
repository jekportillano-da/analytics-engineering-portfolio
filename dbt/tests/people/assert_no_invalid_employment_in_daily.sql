select daily.*
from {{ ref('fct_workforce_daily') }} as daily
inner join {{ ref('int_employment_spells_validated') }} as employment
    using (employment_id)
where not employment.is_usable
