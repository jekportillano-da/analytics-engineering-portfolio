{{ config(enabled=target.type == 'bigquery') }}

select
    geography_code as wage_region_id,
    geography_code as region_code,
    max(geography_name) as region_name,
    max(geography_type) as geography_type
from {{ ref('int_wage_regional_measures') }}
group by geography_code
