-- REVIEW ONLY: no migration is executed by the application.
-- Requires approval, backup and comparison with INFORMATION_SCHEMA first.
-- Acquisition owns readings; it is intentionally not created or altered here.
-- Requires an existing InnoDB readings(id BIGINT UNSIGNED primary key).
-- All ML DATETIME values are UTC; SET time_zone on each connection.
-- MySQL DDL auto-commits: schedule migration separately from acquisition.

CREATE TABLE ml_measurements (
	measurement_id VARCHAR(64) NOT NULL,
	equipment_id VARCHAR(64) NOT NULL,
	started_at DATETIME(6) NOT NULL,
	ended_at DATETIME(6),
	status VARCHAR(16) NOT NULL,
	expected_reading_count INTEGER NOT NULL,
	label INTEGER,
	label_source VARCHAR(255),
	group_id VARCHAR(128) NOT NULL,
	acceleration_unit VARCHAR(16) NOT NULL,
	signal_definition VARCHAR(64) NOT NULL,
	PRIMARY KEY (measurement_id),
	CONSTRAINT ck_ml_measurement_status CHECK (status IN ('ABERTA', 'FINALIZADA')),
	CONSTRAINT ck_ml_measurement_label CHECK (label IS NULL OR label IN (0, 1)),
	CONSTRAINT ck_ml_measurement_count CHECK (expected_reading_count >= 0)
) ENGINE=InnoDB;
CREATE INDEX ix_ml_measurements_status_label ON ml_measurements (status, label);

CREATE TABLE ml_models (
	model_id INTEGER NOT NULL AUTO_INCREMENT,
	name VARCHAR(128) NOT NULL,
	version VARCHAR(128) NOT NULL,
	processing_version VARCHAR(64) NOT NULL,
	document JSON NOT NULL,
	PRIMARY KEY (model_id),
	CONSTRAINT uq_ml_model_version UNIQUE (name, version)
) ENGINE=InnoDB;


CREATE TABLE ml_feature_importances (
	model_id INTEGER NOT NULL,
	feature_name VARCHAR(64) NOT NULL,
	importance FLOAT NOT NULL,
	PRIMARY KEY (model_id, feature_name),
	CONSTRAINT ck_ml_importance CHECK (importance >= 0),
	FOREIGN KEY(model_id) REFERENCES ml_models (model_id) ON DELETE RESTRICT
) ENGINE=InnoDB;


CREATE TABLE ml_features (
	measurement_id VARCHAR(64) NOT NULL,
	processing_version VARCHAR(64) NOT NULL,
	feature_names JSON NOT NULL,
	`values` JSON NOT NULL,
	source_fingerprint VARCHAR(64) NOT NULL,
	reading_count INTEGER NOT NULL,
	PRIMARY KEY (measurement_id, processing_version),
	CONSTRAINT ck_ml_features_count CHECK (reading_count >= 2),
	FOREIGN KEY(measurement_id) REFERENCES ml_measurements (measurement_id) ON DELETE RESTRICT
) ENGINE=InnoDB;


CREATE TABLE ml_measurement_readings (
	reading_id BIGINT UNSIGNED NOT NULL,
	measurement_id VARCHAR(64) NOT NULL,
	PRIMARY KEY (reading_id),
	FOREIGN KEY(reading_id) REFERENCES readings (id) ON DELETE RESTRICT,
	FOREIGN KEY(measurement_id) REFERENCES ml_measurements (measurement_id) ON DELETE RESTRICT
) ENGINE=InnoDB;
CREATE INDEX ix_ml_measurement_readings_measurement_id ON ml_measurement_readings (measurement_id);

CREATE TABLE ml_processing_runs (
	measurement_id VARCHAR(64) NOT NULL,
	model_id INTEGER NOT NULL,
	status VARCHAR(16) NOT NULL,
	error_code VARCHAR(64),
	error_message TEXT,
	updated_at DATETIME(6) NOT NULL,
	PRIMARY KEY (measurement_id, model_id),
	CONSTRAINT ck_ml_processing_status CHECK (status IN ('PROCESSADA', 'ERRO')),
	FOREIGN KEY(measurement_id) REFERENCES ml_measurements (measurement_id) ON DELETE RESTRICT,
	FOREIGN KEY(model_id) REFERENCES ml_models (model_id) ON DELETE RESTRICT
) ENGINE=InnoDB;


CREATE TABLE ml_predictions (
	prediction_id INTEGER NOT NULL AUTO_INCREMENT,
	measurement_id VARCHAR(64) NOT NULL,
	model_id INTEGER NOT NULL,
	processing_version VARCHAR(64) NOT NULL,
	source_fingerprint VARCHAR(64) NOT NULL,
	predicted_class INTEGER NOT NULL,
	probability_normal FLOAT NOT NULL,
	probability_anomaly FLOAT NOT NULL,
	predicted_at DATETIME(6) NOT NULL,
	PRIMARY KEY (prediction_id),
	CONSTRAINT uq_ml_prediction UNIQUE (measurement_id, model_id),
	CONSTRAINT fk_ml_prediction_features FOREIGN KEY(measurement_id, processing_version) REFERENCES ml_features (measurement_id, processing_version) ON DELETE RESTRICT,
	CONSTRAINT ck_ml_prediction_class CHECK (predicted_class IN (0, 1)),
	CONSTRAINT ck_ml_probability_normal CHECK (probability_normal >= 0 AND probability_normal <= 1),
	CONSTRAINT ck_ml_probability_anomaly CHECK (probability_anomaly >= 0 AND probability_anomaly <= 1),
	FOREIGN KEY(measurement_id) REFERENCES ml_measurements (measurement_id) ON DELETE RESTRICT,
	FOREIGN KEY(model_id) REFERENCES ml_models (model_id) ON DELETE RESTRICT
) ENGINE=InnoDB;
CREATE INDEX ix_ml_predictions_model_time ON ml_predictions (model_id, predicted_at);
