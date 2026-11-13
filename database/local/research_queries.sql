-- Read-only examples. Filter the dataset/contract/run shown in the execution report.
-- Counting all label revisions or all feature contracts as new examples is incorrect.

SELECT source_id, source_version, data_origin, title, license_name, inspection_status
FROM study_sources
ORDER BY source_id;

SELECT o.source_id, l.label_version, l.label_status, l.target_label,
       COUNT(*) AS observations,
       COUNT(DISTINCT o.dependency_group_id) AS initial_dependency_groups
FROM study_observations o
JOIN study_labels l ON l.observation_id = o.observation_id
GROUP BY o.source_id, l.label_version, l.label_status, l.target_label;

SELECT m.dataset_version, o.source_id, m.partition_name,
       l.label_status, l.target_label, COUNT(*) AS observations,
       COUNT(DISTINCT m.dependency_group_id) AS frozen_dependency_groups
FROM study_dataset_members m
JOIN study_observations o ON o.observation_id = m.observation_id
JOIN study_labels l ON l.observation_id = m.observation_id AND l.label_id = m.label_id
GROUP BY m.dataset_version, o.source_id, m.partition_name, l.label_status, l.target_label;

SELECT run_id, source_id, statistic_name, feature_name, other_feature_name,
       numeric_value, sample_count, group_count,
       JSON_UNQUOTE(JSON_EXTRACT(dimensions_json,'$.partition')) AS partition_name,
       JSON_UNQUOTE(JSON_EXTRACT(dimensions_json,'$.training')) AS training_comparison
FROM study_statistics
WHERE statistic_name IN ('pearson','spearman','balanced_accuracy','recall','precision','average_precision')
ORDER BY run_id, source_id, statistic_name;

SELECT c.run_id, o.source_id, r.configuration_json,
       c.cluster_label, c.is_noise, COUNT(*) AS observations,
       AVG(c.outlier_score) AS mean_outlier_score
FROM study_clusters c
JOIN study_observations o ON o.observation_id = c.observation_id
JOIN study_runs r ON r.run_id = c.run_id
WHERE r.status = 'completed'
GROUP BY c.run_id, o.source_id, r.configuration_json, c.cluster_label, c.is_noise;

-- Experimental predictions are derived outputs. Do not feed them into model training.
SELECT v.run_id, o.source_id, v.observation_id, v.feature_contract_version,
       v.feature_name, v.numeric_value, v.definition_json
FROM study_feature_values v
JOIN study_observations o ON o.observation_id = v.observation_id
JOIN study_runs r ON r.run_id = v.run_id
WHERE r.stage = 'public_eda_and_feasibility' AND r.status = 'completed'
ORDER BY v.run_id, o.source_id, v.observation_id, v.feature_name;

-- ULT raw local clock, explicitly NOT asserted UTC. JSON contains a scalar, not an array.
SELECT o.equipment_id,
       CAST(REPLACE(JSON_UNQUOTE(JSON_EXTRACT(o.condition_json,'$.local_timestamp')),'T',' ')
            AS DATETIME) AS source_local_time,
       'unknown timezone, raw controller clock' AS time_semantics,
       v.feature_contract_version, v.feature_name, v.numeric_value, v.unit
FROM study_observations o
JOIN study_feature_values v ON v.observation_id = o.observation_id
WHERE o.source_id = 'ult_freezers'
ORDER BY o.equipment_id, source_local_time, v.feature_name;

-- New multibase experiments: metrics, comparisons and support stay scalar.
SELECT run_id, statistic_name, feature_name, numeric_value, sample_count, group_count,
       dimensions_json
FROM study_statistics
WHERE statistic_name IN ('normality_reference_ablation','nested_temporal_confirmation',
                         'frozen_public_cycle_test')
ORDER BY run_id, statistic_key;

-- Canonical experimental outputs for charts. Filter ONE contract/model before counting cases.
-- These scores are NOT physical-failure probabilities or new measured training features.
SELECT v.run_id, v.feature_contract_version, o.source_id, v.observation_id,
       JSON_UNQUOTE(JSON_EXTRACT(v.definition_json,'$.parent_run')) AS parent_run,
       JSON_UNQUOTE(JSON_EXTRACT(v.definition_json,'$.model_id')) AS comparison_id,
       v.numeric_value AS uncalibrated_reference_score
FROM study_feature_values v
JOIN study_observations o ON o.observation_id = v.observation_id
JOIN study_runs r ON r.run_id = v.run_id
WHERE r.stage = 'public_research_scores' AND r.status = 'completed'
ORDER BY v.run_id, comparison_id, v.observation_id;

-- Actual frozen training composition; labels join by exact revision, without feature fan-out.
SELECT m.dataset_version, o.source_id, l.target_label, COUNT(*) AS cases
FROM study_dataset_members m
JOIN study_observations o ON o.observation_id = m.observation_id
JOIN study_labels l ON l.observation_id = m.observation_id AND l.label_id = m.label_id
WHERE m.dataset_version = 'cycle-reference-8af6bb44817d037a836c'
GROUP BY m.dataset_version, o.source_id, l.target_label;

-- Frozen public-test outputs only. This is NOT the external Ulisses campaign.
SELECT o.source_id, v.observation_id, v.feature_name, v.numeric_value,
       JSON_UNQUOTE(JSON_EXTRACT(v.definition_json,'$.model_version')) AS model_version
FROM study_feature_values v
JOIN study_observations o ON o.observation_id = v.observation_id
WHERE v.feature_contract_version = 'frozen-test-score-de6dbc24bcab646d'
ORDER BY o.source_id, v.observation_id, v.feature_name;
