{{ config(enabled=target.type == 'bigquery') }}

with normalized_observations as (
    select * from {{ ref('int_wage_industry_measures') }}

    union all

    select * from {{ ref('int_wage_regional_measures') }}

    union all

    select * from {{ ref('int_benchmark_occupation_wages') }}
)

select
    logical_observation_id as wage_observation_id,
    logical_observation_id,
    source_record_id,
    semantic_dataset_id,
    matrix_id,
    matrix_title,
    matrix_scope,
    reference_year,
    industry_code as wage_industry_id,
    geography_code as wage_region_id,
    benchmark_occupation_id,
    wage_measure_id,
    industry_code,
    industry_name,
    source_industry_name,
    geography_type,
    geography_code,
    geography_name,
    occupation_name,
    sex_code,
    sex,
    source_measure_code,
    source_measure_name,
    governed_measure_name,
    observation_value,
    observation_status,
    source_unit,
    source_publisher,
    source_updated_at,
    source_artifact_id,
    retrieval_id,
    extraction_id,
    request_id,
    source_record_locator,
    identifier_version,
    matrix_metadata_id,
    canonical_endpoint,
    requested_format,
    sha256_checksum,
    storage_key,
    first_retrieved_at,
    retrieval_started_at,
    retrieval_completed_at,
    loaded_at
from normalized_observations
