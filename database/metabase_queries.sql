-- Read-only examples for the PROPOSED sidecar contract, after approved deployment.
-- Bind :model_id / :measurement_id through your SQL client or replace with
-- Metabase variables; do not interpolate untrusted strings into SQL.

-- A completed measurement and its result for ONE selected model. Missing
-- predictions remain NULL, never an implicit Normal classification.
SELECT m.measurement_id, m.equipment_id, m.started_at, m.ended_at,
       TIMESTAMPDIFF(MICROSECOND, m.started_at, m.ended_at) / 1000000.0 AS duration_s,
       m.expected_reading_count, m.status AS acquisition_status,
       COALESCE(r.status, 'PENDENTE') AS processing_status,
       r.error_code, p.predicted_class, p.probability_normal,
       p.probability_anomaly, p.predicted_at, mo.model_id,
       mo.name AS model_name, mo.version AS model_version,
       p.processing_version, p.source_fingerprint
FROM ml_measurements m
CROSS JOIN ml_models mo
LEFT JOIN ml_processing_runs r
       ON r.measurement_id = m.measurement_id AND r.model_id = mo.model_id
LEFT JOIN ml_predictions p
       ON p.measurement_id = m.measurement_id AND p.model_id = mo.model_id
WHERE mo.model_id = :model_id AND m.measurement_id = :measurement_id;

-- Overall indicators: each prediction is unique per measurement/model. The
-- denominator contains classified measurements only; pending/errors are separate.
-- Keep this question independent from an individual measurement dashboard filter.
SELECT mo.model_id, mo.name, mo.version,
       SUM(CASE WHEN p.predicted_class = 0 THEN 1 ELSE 0 END) AS normal_count,
       SUM(CASE WHEN p.predicted_class = 1 THEN 1 ELSE 0 END) AS anomaly_count,
       100.0 * SUM(CASE WHEN p.predicted_class = 1 THEN 1 ELSE 0 END)
           / NULLIF(COUNT(p.prediction_id), 0) AS anomaly_percent,
       SUM(CASE WHEN p.prediction_id IS NULL AND r.status = 'ERRO' THEN 1 ELSE 0 END) AS error_count,
       SUM(CASE WHEN p.prediction_id IS NULL AND r.status IS NULL THEN 1 ELSE 0 END) AS pending_count
FROM ml_models mo
JOIN ml_measurements m ON m.status = 'FINALIZADA'
LEFT JOIN ml_predictions p
       ON p.measurement_id = m.measurement_id AND p.model_id = mo.model_id
LEFT JOIN ml_processing_runs r
       ON r.measurement_id = m.measurement_id AND r.model_id = mo.model_id
WHERE mo.model_id = :model_id
GROUP BY mo.model_id, mo.name, mo.version;

-- Historical source series: memberships are explicit, not inferred from dates/IDs.
SELECT s.id AS reading_id, s.timestamp, s.temperature, s.rms,
       s.accel_x, s.accel_y, s.accel_z
FROM readings s
JOIN ml_measurement_readings mr ON mr.reading_id = s.id
WHERE mr.measurement_id = :measurement_id
ORDER BY s.timestamp, s.id;

-- Global importances are attached once to a model, independent of a measurement.
SELECT mo.model_id, mo.name, mo.version, i.feature_name, i.importance
FROM ml_feature_importances i
JOIN ml_models mo ON mo.model_id = i.model_id
WHERE mo.model_id = :model_id
ORDER BY i.importance DESC, i.feature_name;

-- Model evaluation / traceability and feature values are stored as JSON.
SELECT model_id, name, version, processing_version,
       JSON_EXTRACT(document, '$.metrics') AS evaluation_metrics,
       JSON_EXTRACT(document, '$.training_info') AS training_info,
       JSON_EXTRACT(document, '$.feature_names') AS ordered_features
FROM ml_models WHERE model_id = :model_id;

SELECT measurement_id, processing_version, feature_names, `values`,
       source_fingerprint, reading_count
FROM ml_features WHERE measurement_id = :measurement_id;
