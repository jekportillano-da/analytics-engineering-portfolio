with source as (
    select
        trim(org_unit_id) as org_unit_id,
        trim(org_unit_name) as org_unit_name,
        trim(cost_center) as cost_center
    from {{ source('raw', 'org_units') }}
),

with_unknown as (
    select * from source
    union all
    select 'UNKNOWN', 'Unknown organization', 'UNKNOWN'
)

select * from with_unknown
