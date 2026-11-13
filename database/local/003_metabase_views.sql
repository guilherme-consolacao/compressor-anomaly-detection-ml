-- Views expose typed columns and retain source/version/model/label provenance.
-- SQL SECURITY INVOKER avoids dependence on the setup account's privileges.
CREATE SQL SECURITY INVOKER VIEW mb_study_inventory AS
SELECT s.source_id,s.source_version,s.data_origin,s.title,s.license_name,s.inspection_status,
       COALESCE(o.observation_count,0) AS observation_count,
       COALESCE(o.group_count,0) AS dependency_group_count
FROM study_sources s LEFT JOIN (
    SELECT source_id,source_version,COUNT(*) AS observation_count,
           COUNT(DISTINCT dependency_group_id) AS group_count
    FROM study_observations GROUP BY source_id,source_version
) o ON o.source_id=s.source_id AND o.source_version=s.source_version;

CREATE SQL SECURITY INVOKER VIEW mb_study_feature_values AS
SELECT o.observation_id,o.source_id,o.source_version,s.data_origin,
       o.analysis_unit,o.dependency_group_id,o.equipment_id,o.started_at,o.quality_status,
       f.feature_contract_version,f.feature_name,f.numeric_value,f.unit,f.value_status,f.run_id
FROM study_feature_values f JOIN study_observations o ON o.observation_id=f.observation_id
JOIN study_sources s ON s.source_id=o.source_id AND s.source_version=o.source_version;

CREATE SQL SECURITY INVOKER VIEW mb_study_labels AS
SELECT o.observation_id,o.source_id,o.source_version,s.data_origin,o.dependency_group_id,
       l.label_id,l.label_version,l.original_label,l.target_label,l.label_status,
       l.method,l.confidence,l.recorded_at
FROM study_labels l JOIN study_observations o ON o.observation_id=l.observation_id
JOIN study_sources s ON s.source_id=o.source_id AND s.source_version=o.source_version;

CREATE SQL SECURITY INVOKER VIEW mb_study_statistics AS
SELECT r.stage,r.data_scope,r.status AS run_status,r.started_at,t.run_id,
       t.source_id,t.source_version,t.statistic_name,t.feature_name,t.other_feature_name,
       t.numeric_value,t.sample_count,t.group_count,t.dimensions_json
FROM study_statistics t JOIN study_runs r ON r.run_id=t.run_id;

CREATE SQL SECURITY INVOKER VIEW mb_study_clusters AS
SELECT c.run_id,o.source_id,o.source_version,s.data_origin,o.observation_id,
       o.dependency_group_id,c.cluster_label,c.is_noise,c.outlier_score
FROM study_clusters c JOIN study_observations o ON o.observation_id=c.observation_id
JOIN study_sources s ON s.source_id=o.source_id AND s.source_version=o.source_version;

CREATE SQL SECURITY INVOKER VIEW mb_study_dataset_members AS
SELECT d.dataset_version,d.status AS dataset_status,m.partition_name,m.dependency_group_id,
       o.observation_id,o.source_id,o.source_version,s.data_origin,
       l.label_id,l.label_version,l.target_label,l.label_status
FROM study_dataset_members m JOIN study_datasets d ON d.dataset_version=m.dataset_version
JOIN study_observations o ON o.observation_id=m.observation_id
JOIN study_sources s ON s.source_id=o.source_id AND s.source_version=o.source_version
LEFT JOIN study_labels l ON l.label_id=m.label_id AND l.observation_id=m.observation_id;

CREATE SQL SECURITY INVOKER VIEW mb_ml_models AS
SELECT model_id,name,version,processing_version,
       JSON_UNQUOTE(JSON_EXTRACT(document,'$.training_info.dataset_version')) AS dataset_version,
       JSON_UNQUOTE(JSON_EXTRACT(document,'$.release_status')) AS release_status,
       JSON_UNQUOTE(JSON_EXTRACT(document,'$.training_info.synthetic')) AS synthetic,
       CAST(NULLIF(JSON_UNQUOTE(JSON_EXTRACT(document,'$.metrics.accuracy')),'null') AS DECIMAL(14,10)) AS accuracy,
       CAST(NULLIF(JSON_UNQUOTE(JSON_EXTRACT(document,'$.metrics.precision')),'null') AS DECIMAL(14,10)) AS `precision`,
       CAST(NULLIF(JSON_UNQUOTE(JSON_EXTRACT(document,'$.metrics.recall')),'null') AS DECIMAL(14,10)) AS recall,
       CAST(NULLIF(JSON_UNQUOTE(JSON_EXTRACT(document,'$.metrics.f1')),'null') AS DECIMAL(14,10)) AS f1
FROM ml_models;

CREATE SQL SECURITY INVOKER VIEW mb_external_predictions AS
SELECT c.campaign_id,p.external_case_id,p.model_id,mo.version AS model_version,p.run_id,
       p.truth_version,g.reference_status,g.target_label,p.prediction_status,p.predicted_class,
       p.probability_anomaly,p.predicted_at,p.rejection_reason,
       CASE WHEN p.prediction_status='classified' AND g.reference_status='confirmed'
            THEN 1 ELSE 0 END AS evaluation_eligible,
       CASE WHEN p.prediction_status='classified' AND g.reference_status='confirmed'
            THEN (p.predicted_class=g.target_label) ELSE NULL END AS is_correct
FROM study_external_predictions p
JOIN study_external_cases c ON c.external_case_id=p.external_case_id
JOIN ml_models mo ON mo.model_id=p.model_id
LEFT JOIN study_external_ground_truth g
 ON g.external_case_id=p.external_case_id AND g.truth_version=p.truth_version;

CREATE SQL SECURITY INVOKER VIEW mb_external_metrics AS
SELECT campaign_id,model_id,model_version,truth_version,COUNT(*) AS processed_count,
       SUM(prediction_status='classified') AS classified_count,
       SUM(evaluation_eligible) AS evaluated_count,
       SUM(CASE WHEN evaluation_eligible=1 AND target_label=1 AND predicted_class=1 THEN 1 ELSE 0 END) AS tp,
       SUM(CASE WHEN evaluation_eligible=1 AND target_label=0 AND predicted_class=0 THEN 1 ELSE 0 END) AS tn,
       SUM(CASE WHEN evaluation_eligible=1 AND target_label=0 AND predicted_class=1 THEN 1 ELSE 0 END) AS fp,
       SUM(CASE WHEN evaluation_eligible=1 AND target_label=1 AND predicted_class=0 THEN 1 ELSE 0 END) AS fn,
       1.0*SUM(is_correct)/NULLIF(SUM(evaluation_eligible),0) AS accuracy,
       1.0*SUM(prediction_status='classified')/NULLIF(COUNT(*),0) AS classification_coverage
FROM mb_external_predictions GROUP BY campaign_id,model_id,model_version,truth_version;
