{{ config(enabled=target.type == 'bigquery') }}

select
    wage_observation_id as benchmark_wage_mart_id,
    reference_year,
    matrix_id as source_matrix_id,
    benchmark_occupation_id,
    occupation_name as benchmark_occupation_name,
    wage_industry_id,
    industry_code,
    industry_name,
    sex_code,
    sex,
    observation_value as average_monthly_wage_rate,
    source_measure_name,
    source_artifact_id,
    retrieval_id,
    extraction_id,
    loaded_at,
    1 as source_observation_count
from {{ ref('fct_wage_observations') }}
where matrix_scope = 'benchmark_occupation_wages'
