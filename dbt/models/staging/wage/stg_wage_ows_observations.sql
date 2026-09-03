{{ config(enabled=target.type == 'bigquery') }}

with observations as (
    select * from {{ source('wage_raw', 'ows_observations') }}
),

matrix_metadata as (
    select * from {{ source('wage_raw', 'ows_matrix_metadata') }}
),

ingestion_runs as (
    select * from {{ source('wage_raw', 'ows_ingestion_runs') }}
)

select
    observations.logical_observation_id,
    observations.source_record_id,
    observations.semantic_dataset_id,
    observations.matrix_id,
    nullif(trim(observations.matrix_title), '') as matrix_title,
    cast(observations.reference_year as int64) as reference_year,
    nullif(trim(observations.geography_type), '') as geography_type,
    nullif(trim(observations.geography_code), '') as geography_code,
    nullif(trim(observations.geography_name), '') as geography_name,
    nullif(trim(observations.industry_code), '') as industry_code,
    nullif(trim(observations.industry_name), '') as industry_name,
    nullif(trim(observations.occupation_code), '') as occupation_code,
    nullif(trim(observations.occupation_name), '') as occupation_name,
    nullif(trim(observations.sex_code), '') as sex_code,
    nullif(trim(observations.sex), '') as sex,
    nullif(trim(observations.measure_code), '') as measure_code,
    nullif(trim(observations.measure), '') as source_measure_name,
    cast(observations.observation_value as float64) as observation_value,
    nullif(trim(observations.observation_status), '') as observation_status,
    nullif(trim(observations.source_unit), '') as source_unit,
    observations.source_publisher,
    safe_cast(nullif(trim(observations.source_updated_at), '') as timestamp)
        as source_updated_at,
    observations.source_artifact_id,
    observations.retrieval_id,
    observations.extraction_id,
    observations.request_id,
    observations.source_record_locator,
    observations.identifier_version,
    matrix_metadata.matrix_metadata_id,
    matrix_metadata.canonical_endpoint,
    matrix_metadata.requested_format,
    matrix_metadata.sha256_checksum,
    matrix_metadata.storage_key,
    matrix_metadata.first_retrieved_at,
    ingestion_runs.retrieval_started_at,
    ingestion_runs.retrieval_completed_at,
    observations.loaded_at
from observations
left join matrix_metadata
    on observations.extraction_id = matrix_metadata.extraction_id
    and observations.matrix_id = matrix_metadata.matrix_id
    and observations.source_artifact_id = matrix_metadata.source_artifact_id
left join ingestion_runs
    on observations.retrieval_id = ingestion_runs.retrieval_id
    and observations.matrix_id = ingestion_runs.matrix_id
