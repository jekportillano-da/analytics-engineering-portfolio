{{ config(enabled=target.type == 'bigquery', materialized='view') }}

select
    'v1' as metric_contract_version,
    wage_observation_id,
    reference_year,
    matrix_id,
    matrix_scope,
    wage_measure_id,
    governed_measure_name as wage_measure_name,
    observation_value as measure_value,
    wage_industry_id,
    industry_code,
    industry_name,
    wage_region_id,
    geography_code as region_code,
    geography_name as region_name,
    benchmark_occupation_id,
    occupation_name as benchmark_occupation_name,
    sex_code,
    sex,
    source_measure_code,
    source_measure_name,
    source_artifact_id,
    retrieval_id,
    extraction_id,
    loaded_at
from {{ ref('fct_wage_observations') }}
