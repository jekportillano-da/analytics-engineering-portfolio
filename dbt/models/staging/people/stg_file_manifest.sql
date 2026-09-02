select
    cast(file_name as varchar) as file_name,
    cast(sha256 as varchar) as sha256,
    cast(row_count as bigint) as row_count,
    cast(loaded_at as timestamp) as loaded_at
from {{ source('raw', 'file_manifest') }}
