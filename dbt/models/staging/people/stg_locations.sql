with source as (
    select
        trim(location_id) as location_id,
        trim(location_name) as location_name,
        upper(trim(country_code)) as country_code
    from {{ source('raw', 'locations') }}
),

with_unknown as (
    select * from source
    union all
    select 'UNKNOWN', 'Unknown location', 'XX'
)

select * from with_unknown
