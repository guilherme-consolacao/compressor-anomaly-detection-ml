-- Additive research schema, MariaDB 10.4+. Original sensor data are not changed.
-- DATETIME values below are UTC. Immutable versions preserve previous results.
CREATE TABLE study_schema_versions (
    version VARCHAR(64) NOT NULL PRIMARY KEY,
    schema_sha256 CHAR(64) NOT NULL,
    applied_at DATETIME(6) NOT NULL
) ENGINE=InnoDB;

CREATE TABLE study_sources (
    source_id VARCHAR(64) NOT NULL,
    source_version VARCHAR(64) NOT NULL,
    data_origin VARCHAR(32) NOT NULL,
    title VARCHAR(255) NOT NULL,
    primary_url TEXT NOT NULL,
    license_name VARCHAR(128),
    inspection_status VARCHAR(32) NOT NULL,
    metadata_json JSON NOT NULL,
    created_at DATETIME(6) NOT NULL,
    PRIMARY KEY (source_id, source_version),
    CONSTRAINT ck_study_source_origin CHECK (data_origin IN
        ('public_measured','public_synthetic','public_reference','ulisses_external')),
    CHECK (inspection_status IN ('candidate','inspected','eligible','ineligible','pending_evidence'))
) ENGINE=InnoDB;

CREATE TABLE study_artifacts (
    artifact_id CHAR(64) NOT NULL PRIMARY KEY,
    source_id VARCHAR(64) NOT NULL,
    source_version VARCHAR(64) NOT NULL,
    artifact_kind VARCHAR(32) NOT NULL,
    relative_path TEXT NOT NULL,
    content_sha256 CHAR(64) NOT NULL,
    byte_size BIGINT NOT NULL,
    metadata_json JSON NOT NULL,
    created_at DATETIME(6) NOT NULL,
    FOREIGN KEY (source_id,source_version) REFERENCES study_sources(source_id,source_version),
    CHECK (byte_size >= 0),
    INDEX ix_study_artifact_hash (content_sha256)
) ENGINE=InnoDB;

CREATE TABLE study_runs (
    run_id VARCHAR(64) NOT NULL PRIMARY KEY,
    stage VARCHAR(32) NOT NULL,
    data_scope VARCHAR(16) NOT NULL,
    status VARCHAR(16) NOT NULL,
    started_at DATETIME(6) NOT NULL,
    ended_at DATETIME(6),
    configuration_json JSON NOT NULL,
    input_manifest_json JSON NOT NULL,
    code_fingerprint VARCHAR(64),
    error_message TEXT,
    CHECK (data_scope IN ('public','external','synthetic_test')),
    CHECK (status IN ('running','completed','failed','blocked')),
    CHECK (ended_at IS NULL OR ended_at >= started_at),
    INDEX ix_study_run_stage_status (stage,status,started_at)
) ENGINE=InnoDB;

CREATE TABLE study_observations (
    observation_id VARCHAR(128) NOT NULL PRIMARY KEY,
    source_id VARCHAR(64) NOT NULL,
    source_version VARCHAR(64) NOT NULL,
    original_id VARCHAR(255) NOT NULL,
    analysis_unit VARCHAR(32) NOT NULL,
    dependency_group_id VARCHAR(128) NOT NULL,
    equipment_id VARCHAR(128),
    started_at DATETIME(6),
    ended_at DATETIME(6),
    quality_status VARCHAR(16) NOT NULL,
    condition_json JSON NOT NULL,
    provenance_json JSON NOT NULL,
    created_at DATETIME(6) NOT NULL,
    FOREIGN KEY (source_id,source_version) REFERENCES study_sources(source_id,source_version),
    UNIQUE (source_id,source_version,original_id),
    CHECK (quality_status IN ('valid','quarantined','rejected')),
    CHECK (ended_at IS NULL OR started_at IS NULL OR ended_at >= started_at),
    INDEX ix_study_observation_group (source_id,source_version,dependency_group_id)
) ENGINE=InnoDB;

CREATE TABLE study_feature_values (
    observation_id VARCHAR(128) NOT NULL,
    feature_contract_version VARCHAR(64) NOT NULL,
    feature_name VARCHAR(128) NOT NULL,
    numeric_value DOUBLE,
    unit VARCHAR(32),
    value_status VARCHAR(16) NOT NULL,
    definition_json JSON NOT NULL,
    run_id VARCHAR(64) NOT NULL,
    PRIMARY KEY (observation_id,feature_contract_version,feature_name),
    FOREIGN KEY (observation_id) REFERENCES study_observations(observation_id),
    FOREIGN KEY (run_id) REFERENCES study_runs(run_id),
    CHECK (value_status IN ('observed','derived','missing')),
    CHECK ((value_status = 'missing' AND numeric_value IS NULL) OR
           (value_status <> 'missing' AND numeric_value IS NOT NULL)),
    INDEX ix_study_feature_chart (feature_contract_version,feature_name,numeric_value)
) ENGINE=InnoDB;

CREATE TABLE study_labels (
    label_id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    observation_id VARCHAR(128) NOT NULL,
    label_version VARCHAR(64) NOT NULL,
    original_label VARCHAR(255),
    target_label SMALLINT,
    label_status VARCHAR(16) NOT NULL,
    method VARCHAR(255) NOT NULL,
    confidence DOUBLE,
    evidence_artifact_id CHAR(64),
    evidence_json JSON NOT NULL,
    recorded_at DATETIME(6) NOT NULL,
    FOREIGN KEY (observation_id) REFERENCES study_observations(observation_id),
    FOREIGN KEY (evidence_artifact_id) REFERENCES study_artifacts(artifact_id),
    UNIQUE (observation_id,label_version),
    UNIQUE (observation_id,label_id),
    CHECK (target_label IS NULL OR target_label IN (0,1)),
    CHECK (label_status IN ('reference','derived','indeterminate')),
    CHECK ((label_status = 'indeterminate' AND target_label IS NULL) OR
           (label_status <> 'indeterminate' AND target_label IS NOT NULL)),
    CHECK (confidence IS NULL OR (confidence >= 0 AND confidence <= 1)),
    INDEX ix_study_label_chart (label_version,label_status,target_label)
) ENGINE=InnoDB;

CREATE TABLE study_datasets (
    dataset_version VARCHAR(64) NOT NULL PRIMARY KEY,
    status VARCHAR(16) NOT NULL,
    manifest_sha256 CHAR(64) NOT NULL,
    feature_contract_json JSON NOT NULL,
    manifest_json JSON NOT NULL,
    run_id VARCHAR(64) NOT NULL,
    created_at DATETIME(6) NOT NULL,
    FOREIGN KEY (run_id) REFERENCES study_runs(run_id),
    CHECK (status IN ('research','frozen','retired'))
) ENGINE=InnoDB;

CREATE TABLE study_dataset_members (
    dataset_version VARCHAR(64) NOT NULL,
    observation_id VARCHAR(128) NOT NULL,
    label_id BIGINT,
    partition_name VARCHAR(16) NOT NULL,
    dependency_group_id VARCHAR(128) NOT NULL,
    PRIMARY KEY (dataset_version,observation_id),
    FOREIGN KEY (dataset_version) REFERENCES study_datasets(dataset_version),
    FOREIGN KEY (observation_id) REFERENCES study_observations(observation_id),
    FOREIGN KEY (observation_id,label_id) REFERENCES study_labels(observation_id,label_id),
    CHECK (partition_name IN ('discovery','train','validation','test')),
    INDEX ix_study_dataset_split (dataset_version,partition_name,dependency_group_id)
) ENGINE=InnoDB;

CREATE TABLE study_statistics (
    statistic_id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    run_id VARCHAR(64) NOT NULL,
    statistic_key VARCHAR(255) NOT NULL,
    source_id VARCHAR(64),
    source_version VARCHAR(64),
    statistic_name VARCHAR(64) NOT NULL,
    feature_name VARCHAR(128),
    other_feature_name VARCHAR(128),
    numeric_value DOUBLE,
    sample_count BIGINT NOT NULL,
    group_count BIGINT,
    dimensions_json JSON NOT NULL,
    FOREIGN KEY (run_id) REFERENCES study_runs(run_id),
    FOREIGN KEY (source_id,source_version) REFERENCES study_sources(source_id,source_version),
    UNIQUE (run_id,statistic_key),
    CHECK (sample_count >= 0),
    CHECK (group_count IS NULL OR group_count >= 0),
    INDEX ix_study_statistic_chart (statistic_name,feature_name)
) ENGINE=InnoDB;

CREATE TABLE study_clusters (
    run_id VARCHAR(64) NOT NULL,
    observation_id VARCHAR(128) NOT NULL,
    cluster_label VARCHAR(64),
    is_noise BOOLEAN NOT NULL,
    outlier_score DOUBLE,
    metadata_json JSON NOT NULL,
    PRIMARY KEY (run_id,observation_id),
    FOREIGN KEY (run_id) REFERENCES study_runs(run_id),
    FOREIGN KEY (observation_id) REFERENCES study_observations(observation_id),
    CHECK (is_noise IN (0,1)),
    INDEX ix_study_cluster_chart (run_id,cluster_label,is_noise)
) ENGINE=InnoDB;

CREATE TABLE study_external_cases (
    external_case_id VARCHAR(128) NOT NULL PRIMARY KEY,
    observation_id VARCHAR(128) NOT NULL UNIQUE,
    campaign_id VARCHAR(64) NOT NULL,
    protocol_sha256 CHAR(64) NOT NULL,
    metadata_json JSON NOT NULL,
    FOREIGN KEY (observation_id) REFERENCES study_observations(observation_id),
    INDEX ix_study_external_campaign (campaign_id)
) ENGINE=InnoDB;

CREATE TABLE study_external_case_readings (
    external_case_id VARCHAR(128) NOT NULL,
    reading_id BIGINT UNSIGNED NOT NULL,
    PRIMARY KEY (external_case_id,reading_id),
    FOREIGN KEY (external_case_id) REFERENCES study_external_cases(external_case_id),
    FOREIGN KEY (reading_id) REFERENCES readings(id)
) ENGINE=InnoDB;

CREATE TABLE study_external_ground_truth (
    external_case_id VARCHAR(128) NOT NULL,
    truth_version VARCHAR(64) NOT NULL,
    target_label SMALLINT,
    reference_status VARCHAR(16) NOT NULL,
    observer_name VARCHAR(128) NOT NULL,
    observed_at DATETIME(6) NOT NULL,
    evidence_json JSON NOT NULL,
    PRIMARY KEY (external_case_id,truth_version),
    FOREIGN KEY (external_case_id) REFERENCES study_external_cases(external_case_id),
    CHECK (reference_status IN ('confirmed','indeterminate')),
    CHECK ((reference_status = 'confirmed' AND target_label IN (0,1) AND target_label IS NOT NULL)
        OR (reference_status = 'indeterminate' AND target_label IS NULL))
) ENGINE=InnoDB;

CREATE TABLE study_external_predictions (
    external_case_id VARCHAR(128) NOT NULL,
    model_id INTEGER NOT NULL,
    run_id VARCHAR(64) NOT NULL,
    truth_version VARCHAR(64),
    prediction_status VARCHAR(32) NOT NULL,
    predicted_class SMALLINT,
    probability_anomaly DOUBLE,
    input_sha256 CHAR(64) NOT NULL,
    predicted_at DATETIME(6) NOT NULL,
    rejection_reason TEXT,
    PRIMARY KEY (external_case_id,model_id),
    FOREIGN KEY (external_case_id) REFERENCES study_external_cases(external_case_id),
    FOREIGN KEY (model_id) REFERENCES ml_models(model_id),
    FOREIGN KEY (run_id) REFERENCES study_runs(run_id),
    FOREIGN KEY (external_case_id,truth_version)
        REFERENCES study_external_ground_truth(external_case_id,truth_version),
    CHECK (prediction_status IN ('classified','invalid_input','unsupported_signal')),
    CHECK ((prediction_status = 'classified' AND predicted_class IS NOT NULL
            AND predicted_class IN (0,1) AND probability_anomaly IS NOT NULL
            AND probability_anomaly >= 0 AND probability_anomaly <= 1)
        OR (prediction_status <> 'classified' AND predicted_class IS NULL
            AND probability_anomaly IS NULL AND rejection_reason IS NOT NULL)),
    INDEX ix_study_external_model (model_id,predicted_at)
) ENGINE=InnoDB;
