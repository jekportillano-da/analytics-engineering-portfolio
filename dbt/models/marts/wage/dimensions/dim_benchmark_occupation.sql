{{ config(enabled=target.type == 'bigquery') }}

select
    benchmark_occupation_id,
    max(occupation_name) as benchmark_occupation_name,
    max(matrix_id) as source_matrix_id,
    cast(null as string) as source_occupation_code
from {{ ref('int_benchmark_occupation_wages') }}
group by benchmark_occupation_id
