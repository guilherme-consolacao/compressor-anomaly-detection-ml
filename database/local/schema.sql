-- Schema only; restore into a NEW EMPTY database. No users or data.

/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!40101 SET NAMES utf8mb4 */;
/*!40103 SET @OLD_TIME_ZONE=@@TIME_ZONE */;
/*!40103 SET TIME_ZONE='+00:00' */;
/*!40014 SET @OLD_UNIQUE_CHECKS=@@UNIQUE_CHECKS, UNIQUE_CHECKS=0 */;
/*!40014 SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0 */;
/*!40101 SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO' */;
/*!40111 SET @OLD_SQL_NOTES=@@SQL_NOTES, SQL_NOTES=0 */;
SET @saved_cs_client     = @@character_set_client;
SET character_set_client = utf8;
/*!50001 CREATE TABLE `mb_external_metrics` (
  `campaign_id` tinyint NOT NULL,
  `model_id` tinyint NOT NULL,
  `model_version` tinyint NOT NULL,
  `truth_version` tinyint NOT NULL,
  `processed_count` tinyint NOT NULL,
  `classified_count` tinyint NOT NULL,
  `evaluated_count` tinyint NOT NULL,
  `tp` tinyint NOT NULL,
  `tn` tinyint NOT NULL,
  `fp` tinyint NOT NULL,
  `fn` tinyint NOT NULL,
  `accuracy` tinyint NOT NULL,
  `classification_coverage` tinyint NOT NULL
) ENGINE=MyISAM */;
SET character_set_client = @saved_cs_client;
SET @saved_cs_client     = @@character_set_client;
SET character_set_client = utf8;
/*!50001 CREATE TABLE `mb_external_predictions` (
  `campaign_id` tinyint NOT NULL,
  `external_case_id` tinyint NOT NULL,
  `model_id` tinyint NOT NULL,
  `model_version` tinyint NOT NULL,
  `run_id` tinyint NOT NULL,
  `truth_version` tinyint NOT NULL,
  `reference_status` tinyint NOT NULL,
  `target_label` tinyint NOT NULL,
  `prediction_status` tinyint NOT NULL,
  `predicted_class` tinyint NOT NULL,
  `probability_anomaly` tinyint NOT NULL,
  `predicted_at` tinyint NOT NULL,
  `rejection_reason` tinyint NOT NULL,
  `evaluation_eligible` tinyint NOT NULL,
  `is_correct` tinyint NOT NULL
) ENGINE=MyISAM */;
SET character_set_client = @saved_cs_client;
SET @saved_cs_client     = @@character_set_client;
SET character_set_client = utf8;
/*!50001 CREATE TABLE `mb_ml_models` (
  `model_id` tinyint NOT NULL,
  `name` tinyint NOT NULL,
  `version` tinyint NOT NULL,
  `processing_version` tinyint NOT NULL,
  `dataset_version` tinyint NOT NULL,
  `release_status` tinyint NOT NULL,
  `synthetic` tinyint NOT NULL,
  `accuracy` tinyint NOT NULL,
  `precision` tinyint NOT NULL,
  `recall` tinyint NOT NULL,
  `f1` tinyint NOT NULL
) ENGINE=MyISAM */;
SET character_set_client = @saved_cs_client;
SET @saved_cs_client     = @@character_set_client;
SET character_set_client = utf8;
/*!50001 CREATE TABLE `mb_study_clusters` (
  `run_id` tinyint NOT NULL,
  `source_id` tinyint NOT NULL,
  `source_version` tinyint NOT NULL,
  `data_origin` tinyint NOT NULL,
  `observation_id` tinyint NOT NULL,
  `dependency_group_id` tinyint NOT NULL,
  `cluster_label` tinyint NOT NULL,
  `is_noise` tinyint NOT NULL,
  `outlier_score` tinyint NOT NULL
) ENGINE=MyISAM */;
SET character_set_client = @saved_cs_client;
SET @saved_cs_client     = @@character_set_client;
SET character_set_client = utf8;
/*!50001 CREATE TABLE `mb_study_dataset_members` (
  `dataset_version` tinyint NOT NULL,
  `dataset_status` tinyint NOT NULL,
  `partition_name` tinyint NOT NULL,
  `dependency_group_id` tinyint NOT NULL,
  `observation_id` tinyint NOT NULL,
  `source_id` tinyint NOT NULL,
  `source_version` tinyint NOT NULL,
  `data_origin` tinyint NOT NULL,
  `label_id` tinyint NOT NULL,
  `label_version` tinyint NOT NULL,
  `target_label` tinyint NOT NULL,
  `label_status` tinyint NOT NULL
) ENGINE=MyISAM */;
SET character_set_client = @saved_cs_client;
SET @saved_cs_client     = @@character_set_client;
SET character_set_client = utf8;
/*!50001 CREATE TABLE `mb_study_feature_values` (
  `observation_id` tinyint NOT NULL,
  `source_id` tinyint NOT NULL,
  `source_version` tinyint NOT NULL,
  `data_origin` tinyint NOT NULL,
  `analysis_unit` tinyint NOT NULL,
  `dependency_group_id` tinyint NOT NULL,
  `equipment_id` tinyint NOT NULL,
  `started_at` tinyint NOT NULL,
  `quality_status` tinyint NOT NULL,
  `feature_contract_version` tinyint NOT NULL,
  `feature_name` tinyint NOT NULL,
  `numeric_value` tinyint NOT NULL,
  `unit` tinyint NOT NULL,
  `value_status` tinyint NOT NULL,
  `run_id` tinyint NOT NULL
) ENGINE=MyISAM */;
SET character_set_client = @saved_cs_client;
SET @saved_cs_client     = @@character_set_client;
SET character_set_client = utf8;
/*!50001 CREATE TABLE `mb_study_inventory` (
  `source_id` tinyint NOT NULL,
  `source_version` tinyint NOT NULL,
  `data_origin` tinyint NOT NULL,
  `title` tinyint NOT NULL,
  `license_name` tinyint NOT NULL,
  `inspection_status` tinyint NOT NULL,
  `observation_count` tinyint NOT NULL,
  `dependency_group_count` tinyint NOT NULL
) ENGINE=MyISAM */;
SET character_set_client = @saved_cs_client;
SET @saved_cs_client     = @@character_set_client;
SET character_set_client = utf8;
/*!50001 CREATE TABLE `mb_study_labels` (
  `observation_id` tinyint NOT NULL,
  `source_id` tinyint NOT NULL,
  `source_version` tinyint NOT NULL,
  `data_origin` tinyint NOT NULL,
  `dependency_group_id` tinyint NOT NULL,
  `label_id` tinyint NOT NULL,
  `label_version` tinyint NOT NULL,
  `original_label` tinyint NOT NULL,
  `target_label` tinyint NOT NULL,
  `label_status` tinyint NOT NULL,
  `method` tinyint NOT NULL,
  `confidence` tinyint NOT NULL,
  `recorded_at` tinyint NOT NULL
) ENGINE=MyISAM */;
SET character_set_client = @saved_cs_client;
SET @saved_cs_client     = @@character_set_client;
SET character_set_client = utf8;
/*!50001 CREATE TABLE `mb_study_statistics` (
  `stage` tinyint NOT NULL,
  `data_scope` tinyint NOT NULL,
  `run_status` tinyint NOT NULL,
  `started_at` tinyint NOT NULL,
  `run_id` tinyint NOT NULL,
  `source_id` tinyint NOT NULL,
  `source_version` tinyint NOT NULL,
  `statistic_name` tinyint NOT NULL,
  `feature_name` tinyint NOT NULL,
  `other_feature_name` tinyint NOT NULL,
  `numeric_value` tinyint NOT NULL,
  `sample_count` tinyint NOT NULL,
  `group_count` tinyint NOT NULL,
  `dimensions_json` tinyint NOT NULL
) ENGINE=MyISAM */;
SET character_set_client = @saved_cs_client;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `ml_feature_importances` (
  `model_id` int(11) NOT NULL,
  `feature_name` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL,
  `importance` float NOT NULL,
  PRIMARY KEY (`model_id`,`feature_name`),
  CONSTRAINT `ml_feature_importances_ibfk_1` FOREIGN KEY (`model_id`) REFERENCES `ml_models` (`model_id`),
  CONSTRAINT `ck_ml_importance` CHECK (`importance` >= 0)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `ml_features` (
  `measurement_id` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL,
  `processing_version` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL,
  `feature_names` longtext CHARACTER SET utf8mb4 COLLATE utf8mb4_bin NOT NULL CHECK (json_valid(`feature_names`)),
  `values` longtext CHARACTER SET utf8mb4 COLLATE utf8mb4_bin NOT NULL CHECK (json_valid(`values`)),
  `source_fingerprint` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL,
  `reading_count` int(11) NOT NULL,
  PRIMARY KEY (`measurement_id`,`processing_version`),
  CONSTRAINT `ml_features_ibfk_1` FOREIGN KEY (`measurement_id`) REFERENCES `ml_measurements` (`measurement_id`),
  CONSTRAINT `ck_ml_features_count` CHECK (`reading_count` >= 2)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `ml_measurement_readings` (
  `reading_id` bigint(20) unsigned NOT NULL,
  `measurement_id` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL,
  PRIMARY KEY (`reading_id`),
  KEY `ix_ml_measurement_readings_measurement_id` (`measurement_id`),
  CONSTRAINT `ml_measurement_readings_ibfk_1` FOREIGN KEY (`reading_id`) REFERENCES `readings` (`id`),
  CONSTRAINT `ml_measurement_readings_ibfk_2` FOREIGN KEY (`measurement_id`) REFERENCES `ml_measurements` (`measurement_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `ml_measurements` (
  `measurement_id` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL,
  `equipment_id` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL,
  `started_at` datetime(6) NOT NULL,
  `ended_at` datetime(6) DEFAULT NULL,
  `status` varchar(16) COLLATE utf8mb4_unicode_ci NOT NULL,
  `expected_reading_count` int(11) NOT NULL,
  `label` int(11) DEFAULT NULL,
  `label_source` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `group_id` varchar(128) COLLATE utf8mb4_unicode_ci NOT NULL,
  `acceleration_unit` varchar(16) COLLATE utf8mb4_unicode_ci NOT NULL,
  `signal_definition` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL,
  PRIMARY KEY (`measurement_id`),
  KEY `ix_ml_measurements_status_label` (`status`,`label`),
  CONSTRAINT `ck_ml_measurement_status` CHECK (`status` in ('ABERTA','FINALIZADA')),
  CONSTRAINT `ck_ml_measurement_label` CHECK (`label` is null or `label` in (0,1)),
  CONSTRAINT `ck_ml_measurement_count` CHECK (`expected_reading_count` >= 0)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `ml_models` (
  `model_id` int(11) NOT NULL AUTO_INCREMENT,
  `name` varchar(128) COLLATE utf8mb4_unicode_ci NOT NULL,
  `version` varchar(128) COLLATE utf8mb4_unicode_ci NOT NULL,
  `processing_version` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL,
  `document` longtext CHARACTER SET utf8mb4 COLLATE utf8mb4_bin NOT NULL CHECK (json_valid(`document`)),
  PRIMARY KEY (`model_id`),
  UNIQUE KEY `uq_ml_model_version` (`name`,`version`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `ml_predictions` (
  `prediction_id` int(11) NOT NULL AUTO_INCREMENT,
  `measurement_id` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL,
  `model_id` int(11) NOT NULL,
  `processing_version` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL,
  `source_fingerprint` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL,
  `predicted_class` int(11) NOT NULL,
  `probability_normal` float NOT NULL,
  `probability_anomaly` float NOT NULL,
  `predicted_at` datetime(6) NOT NULL,
  PRIMARY KEY (`prediction_id`),
  UNIQUE KEY `uq_ml_prediction` (`measurement_id`,`model_id`),
  KEY `fk_ml_prediction_features` (`measurement_id`,`processing_version`),
  KEY `ix_ml_predictions_model_time` (`model_id`,`predicted_at`),
  CONSTRAINT `fk_ml_prediction_features` FOREIGN KEY (`measurement_id`, `processing_version`) REFERENCES `ml_features` (`measurement_id`, `processing_version`),
  CONSTRAINT `ml_predictions_ibfk_1` FOREIGN KEY (`measurement_id`) REFERENCES `ml_measurements` (`measurement_id`),
  CONSTRAINT `ml_predictions_ibfk_2` FOREIGN KEY (`model_id`) REFERENCES `ml_models` (`model_id`),
  CONSTRAINT `ck_ml_prediction_class` CHECK (`predicted_class` in (0,1)),
  CONSTRAINT `ck_ml_probability_normal` CHECK (`probability_normal` >= 0 and `probability_normal` <= 1),
  CONSTRAINT `ck_ml_probability_anomaly` CHECK (`probability_anomaly` >= 0 and `probability_anomaly` <= 1)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `ml_processing_runs` (
  `measurement_id` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL,
  `model_id` int(11) NOT NULL,
  `status` varchar(16) COLLATE utf8mb4_unicode_ci NOT NULL,
  `error_code` varchar(64) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `error_message` text COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `updated_at` datetime(6) NOT NULL,
  PRIMARY KEY (`measurement_id`,`model_id`),
  KEY `model_id` (`model_id`),
  CONSTRAINT `ml_processing_runs_ibfk_1` FOREIGN KEY (`measurement_id`) REFERENCES `ml_measurements` (`measurement_id`),
  CONSTRAINT `ml_processing_runs_ibfk_2` FOREIGN KEY (`model_id`) REFERENCES `ml_models` (`model_id`),
  CONSTRAINT `ck_ml_processing_status` CHECK (`status` in ('PROCESSADA','ERRO'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `readings` (
  `id` bigint(20) unsigned NOT NULL AUTO_INCREMENT,
  `temperature` decimal(12,6) NOT NULL,
  `accel_x` decimal(12,6) NOT NULL,
  `accel_y` decimal(12,6) NOT NULL,
  `accel_z` decimal(12,6) NOT NULL,
  `rms` decimal(12,6) NOT NULL,
  `timestamp` timestamp NOT NULL DEFAULT current_timestamp(),
  PRIMARY KEY (`id`),
  KEY `idx_readings_timestamp` (`timestamp`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `study_artifacts` (
  `artifact_id` char(64) COLLATE utf8mb4_unicode_ci NOT NULL,
  `source_id` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL,
  `source_version` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL,
  `artifact_kind` varchar(32) COLLATE utf8mb4_unicode_ci NOT NULL,
  `relative_path` text COLLATE utf8mb4_unicode_ci NOT NULL,
  `content_sha256` char(64) COLLATE utf8mb4_unicode_ci NOT NULL,
  `byte_size` bigint(20) NOT NULL,
  `metadata_json` longtext CHARACTER SET utf8mb4 COLLATE utf8mb4_bin NOT NULL CHECK (json_valid(`metadata_json`)),
  `created_at` datetime(6) NOT NULL,
  PRIMARY KEY (`artifact_id`),
  KEY `source_id` (`source_id`,`source_version`),
  KEY `ix_study_artifact_hash` (`content_sha256`),
  CONSTRAINT `study_artifacts_ibfk_1` FOREIGN KEY (`source_id`, `source_version`) REFERENCES `study_sources` (`source_id`, `source_version`),
  CONSTRAINT `CONSTRAINT_1` CHECK (`byte_size` >= 0)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `study_clusters` (
  `run_id` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL,
  `observation_id` varchar(128) COLLATE utf8mb4_unicode_ci NOT NULL,
  `cluster_label` varchar(64) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `is_noise` tinyint(1) NOT NULL,
  `outlier_score` double DEFAULT NULL,
  `metadata_json` longtext CHARACTER SET utf8mb4 COLLATE utf8mb4_bin NOT NULL CHECK (json_valid(`metadata_json`)),
  PRIMARY KEY (`run_id`,`observation_id`),
  KEY `observation_id` (`observation_id`),
  KEY `ix_study_cluster_chart` (`run_id`,`cluster_label`,`is_noise`),
  CONSTRAINT `study_clusters_ibfk_1` FOREIGN KEY (`run_id`) REFERENCES `study_runs` (`run_id`),
  CONSTRAINT `study_clusters_ibfk_2` FOREIGN KEY (`observation_id`) REFERENCES `study_observations` (`observation_id`),
  CONSTRAINT `CONSTRAINT_1` CHECK (`is_noise` in (0,1))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `study_dataset_members` (
  `dataset_version` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL,
  `observation_id` varchar(128) COLLATE utf8mb4_unicode_ci NOT NULL,
  `label_id` bigint(20) DEFAULT NULL,
  `partition_name` varchar(16) COLLATE utf8mb4_unicode_ci NOT NULL,
  `dependency_group_id` varchar(128) COLLATE utf8mb4_unicode_ci NOT NULL,
  PRIMARY KEY (`dataset_version`,`observation_id`),
  KEY `observation_id` (`observation_id`,`label_id`),
  KEY `ix_study_dataset_split` (`dataset_version`,`partition_name`,`dependency_group_id`),
  CONSTRAINT `study_dataset_members_ibfk_1` FOREIGN KEY (`dataset_version`) REFERENCES `study_datasets` (`dataset_version`),
  CONSTRAINT `study_dataset_members_ibfk_2` FOREIGN KEY (`observation_id`) REFERENCES `study_observations` (`observation_id`),
  CONSTRAINT `study_dataset_members_ibfk_3` FOREIGN KEY (`observation_id`, `label_id`) REFERENCES `study_labels` (`observation_id`, `label_id`),
  CONSTRAINT `CONSTRAINT_1` CHECK (`partition_name` in ('discovery','train','validation','test'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `study_datasets` (
  `dataset_version` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL,
  `status` varchar(16) COLLATE utf8mb4_unicode_ci NOT NULL,
  `manifest_sha256` char(64) COLLATE utf8mb4_unicode_ci NOT NULL,
  `feature_contract_json` longtext CHARACTER SET utf8mb4 COLLATE utf8mb4_bin NOT NULL CHECK (json_valid(`feature_contract_json`)),
  `manifest_json` longtext CHARACTER SET utf8mb4 COLLATE utf8mb4_bin NOT NULL CHECK (json_valid(`manifest_json`)),
  `run_id` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL,
  `created_at` datetime(6) NOT NULL,
  PRIMARY KEY (`dataset_version`),
  KEY `run_id` (`run_id`),
  CONSTRAINT `study_datasets_ibfk_1` FOREIGN KEY (`run_id`) REFERENCES `study_runs` (`run_id`),
  CONSTRAINT `CONSTRAINT_1` CHECK (`status` in ('research','frozen','retired'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `study_external_case_readings` (
  `external_case_id` varchar(128) COLLATE utf8mb4_unicode_ci NOT NULL,
  `reading_id` bigint(20) unsigned NOT NULL,
  PRIMARY KEY (`external_case_id`,`reading_id`),
  KEY `reading_id` (`reading_id`),
  CONSTRAINT `study_external_case_readings_ibfk_1` FOREIGN KEY (`external_case_id`) REFERENCES `study_external_cases` (`external_case_id`),
  CONSTRAINT `study_external_case_readings_ibfk_2` FOREIGN KEY (`reading_id`) REFERENCES `readings` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `study_external_cases` (
  `external_case_id` varchar(128) COLLATE utf8mb4_unicode_ci NOT NULL,
  `observation_id` varchar(128) COLLATE utf8mb4_unicode_ci NOT NULL,
  `campaign_id` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL,
  `protocol_sha256` char(64) COLLATE utf8mb4_unicode_ci NOT NULL,
  `metadata_json` longtext CHARACTER SET utf8mb4 COLLATE utf8mb4_bin NOT NULL CHECK (json_valid(`metadata_json`)),
  PRIMARY KEY (`external_case_id`),
  UNIQUE KEY `observation_id` (`observation_id`),
  KEY `ix_study_external_campaign` (`campaign_id`),
  CONSTRAINT `study_external_cases_ibfk_1` FOREIGN KEY (`observation_id`) REFERENCES `study_observations` (`observation_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `study_external_ground_truth` (
  `external_case_id` varchar(128) COLLATE utf8mb4_unicode_ci NOT NULL,
  `truth_version` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL,
  `target_label` smallint(6) DEFAULT NULL,
  `reference_status` varchar(16) COLLATE utf8mb4_unicode_ci NOT NULL,
  `observer_name` varchar(128) COLLATE utf8mb4_unicode_ci NOT NULL,
  `observed_at` datetime(6) NOT NULL,
  `evidence_json` longtext CHARACTER SET utf8mb4 COLLATE utf8mb4_bin NOT NULL CHECK (json_valid(`evidence_json`)),
  PRIMARY KEY (`external_case_id`,`truth_version`),
  CONSTRAINT `study_external_ground_truth_ibfk_1` FOREIGN KEY (`external_case_id`) REFERENCES `study_external_cases` (`external_case_id`),
  CONSTRAINT `CONSTRAINT_1` CHECK (`reference_status` in ('confirmed','indeterminate')),
  CONSTRAINT `CONSTRAINT_2` CHECK (`reference_status` = 'confirmed' and `target_label` in (0,1) and `target_label` is not null or `reference_status` = 'indeterminate' and `target_label` is null)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `study_external_predictions` (
  `external_case_id` varchar(128) COLLATE utf8mb4_unicode_ci NOT NULL,
  `model_id` int(11) NOT NULL,
  `run_id` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL,
  `truth_version` varchar(64) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `prediction_status` varchar(32) COLLATE utf8mb4_unicode_ci NOT NULL,
  `predicted_class` smallint(6) DEFAULT NULL,
  `probability_anomaly` double DEFAULT NULL,
  `input_sha256` char(64) COLLATE utf8mb4_unicode_ci NOT NULL,
  `predicted_at` datetime(6) NOT NULL,
  `rejection_reason` text COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  PRIMARY KEY (`external_case_id`,`model_id`),
  KEY `run_id` (`run_id`),
  KEY `external_case_id` (`external_case_id`,`truth_version`),
  KEY `ix_study_external_model` (`model_id`,`predicted_at`),
  CONSTRAINT `study_external_predictions_ibfk_1` FOREIGN KEY (`external_case_id`) REFERENCES `study_external_cases` (`external_case_id`),
  CONSTRAINT `study_external_predictions_ibfk_2` FOREIGN KEY (`model_id`) REFERENCES `ml_models` (`model_id`),
  CONSTRAINT `study_external_predictions_ibfk_3` FOREIGN KEY (`run_id`) REFERENCES `study_runs` (`run_id`),
  CONSTRAINT `study_external_predictions_ibfk_4` FOREIGN KEY (`external_case_id`, `truth_version`) REFERENCES `study_external_ground_truth` (`external_case_id`, `truth_version`),
  CONSTRAINT `CONSTRAINT_1` CHECK (`prediction_status` in ('classified','invalid_input','unsupported_signal')),
  CONSTRAINT `CONSTRAINT_2` CHECK (`prediction_status` = 'classified' and `predicted_class` is not null and `predicted_class` in (0,1) and `probability_anomaly` is not null and `probability_anomaly` >= 0 and `probability_anomaly` <= 1 or `prediction_status` <> 'classified' and `predicted_class` is null and `probability_anomaly` is null and `rejection_reason` is not null)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `study_feature_values` (
  `observation_id` varchar(128) COLLATE utf8mb4_unicode_ci NOT NULL,
  `feature_contract_version` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL,
  `feature_name` varchar(128) COLLATE utf8mb4_unicode_ci NOT NULL,
  `numeric_value` double DEFAULT NULL,
  `unit` varchar(32) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `value_status` varchar(16) COLLATE utf8mb4_unicode_ci NOT NULL,
  `definition_json` longtext CHARACTER SET utf8mb4 COLLATE utf8mb4_bin NOT NULL CHECK (json_valid(`definition_json`)),
  `run_id` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL,
  PRIMARY KEY (`observation_id`,`feature_contract_version`,`feature_name`),
  KEY `run_id` (`run_id`),
  KEY `ix_study_feature_chart` (`feature_contract_version`,`feature_name`,`numeric_value`),
  CONSTRAINT `study_feature_values_ibfk_1` FOREIGN KEY (`observation_id`) REFERENCES `study_observations` (`observation_id`),
  CONSTRAINT `study_feature_values_ibfk_2` FOREIGN KEY (`run_id`) REFERENCES `study_runs` (`run_id`),
  CONSTRAINT `CONSTRAINT_1` CHECK (`value_status` in ('observed','derived','missing')),
  CONSTRAINT `CONSTRAINT_2` CHECK (`value_status` = 'missing' and `numeric_value` is null or `value_status` <> 'missing' and `numeric_value` is not null)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `study_labels` (
  `label_id` bigint(20) NOT NULL AUTO_INCREMENT,
  `observation_id` varchar(128) COLLATE utf8mb4_unicode_ci NOT NULL,
  `label_version` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL,
  `original_label` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `target_label` smallint(6) DEFAULT NULL,
  `label_status` varchar(16) COLLATE utf8mb4_unicode_ci NOT NULL,
  `method` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL,
  `confidence` double DEFAULT NULL,
  `evidence_artifact_id` char(64) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `evidence_json` longtext CHARACTER SET utf8mb4 COLLATE utf8mb4_bin NOT NULL CHECK (json_valid(`evidence_json`)),
  `recorded_at` datetime(6) NOT NULL,
  PRIMARY KEY (`label_id`),
  UNIQUE KEY `observation_id` (`observation_id`,`label_version`),
  UNIQUE KEY `observation_id_2` (`observation_id`,`label_id`),
  KEY `evidence_artifact_id` (`evidence_artifact_id`),
  KEY `ix_study_label_chart` (`label_version`,`label_status`,`target_label`),
  CONSTRAINT `study_labels_ibfk_1` FOREIGN KEY (`observation_id`) REFERENCES `study_observations` (`observation_id`),
  CONSTRAINT `study_labels_ibfk_2` FOREIGN KEY (`evidence_artifact_id`) REFERENCES `study_artifacts` (`artifact_id`),
  CONSTRAINT `CONSTRAINT_1` CHECK (`target_label` is null or `target_label` in (0,1)),
  CONSTRAINT `CONSTRAINT_2` CHECK (`label_status` in ('reference','derived','indeterminate')),
  CONSTRAINT `CONSTRAINT_3` CHECK (`label_status` = 'indeterminate' and `target_label` is null or `label_status` <> 'indeterminate' and `target_label` is not null),
  CONSTRAINT `CONSTRAINT_4` CHECK (`confidence` is null or `confidence` >= 0 and `confidence` <= 1)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `study_observations` (
  `observation_id` varchar(128) COLLATE utf8mb4_unicode_ci NOT NULL,
  `source_id` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL,
  `source_version` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL,
  `original_id` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL,
  `analysis_unit` varchar(32) COLLATE utf8mb4_unicode_ci NOT NULL,
  `dependency_group_id` varchar(128) COLLATE utf8mb4_unicode_ci NOT NULL,
  `equipment_id` varchar(128) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `started_at` datetime(6) DEFAULT NULL,
  `ended_at` datetime(6) DEFAULT NULL,
  `quality_status` varchar(16) COLLATE utf8mb4_unicode_ci NOT NULL,
  `condition_json` longtext CHARACTER SET utf8mb4 COLLATE utf8mb4_bin NOT NULL CHECK (json_valid(`condition_json`)),
  `provenance_json` longtext CHARACTER SET utf8mb4 COLLATE utf8mb4_bin NOT NULL CHECK (json_valid(`provenance_json`)),
  `created_at` datetime(6) NOT NULL,
  PRIMARY KEY (`observation_id`),
  UNIQUE KEY `source_id` (`source_id`,`source_version`,`original_id`),
  KEY `ix_study_observation_group` (`source_id`,`source_version`,`dependency_group_id`),
  CONSTRAINT `study_observations_ibfk_1` FOREIGN KEY (`source_id`, `source_version`) REFERENCES `study_sources` (`source_id`, `source_version`),
  CONSTRAINT `CONSTRAINT_1` CHECK (`quality_status` in ('valid','quarantined','rejected')),
  CONSTRAINT `CONSTRAINT_2` CHECK (`ended_at` is null or `started_at` is null or `ended_at` >= `started_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `study_runs` (
  `run_id` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL,
  `stage` varchar(32) COLLATE utf8mb4_unicode_ci NOT NULL,
  `data_scope` varchar(16) COLLATE utf8mb4_unicode_ci NOT NULL,
  `status` varchar(16) COLLATE utf8mb4_unicode_ci NOT NULL,
  `started_at` datetime(6) NOT NULL,
  `ended_at` datetime(6) DEFAULT NULL,
  `configuration_json` longtext CHARACTER SET utf8mb4 COLLATE utf8mb4_bin NOT NULL CHECK (json_valid(`configuration_json`)),
  `input_manifest_json` longtext CHARACTER SET utf8mb4 COLLATE utf8mb4_bin NOT NULL CHECK (json_valid(`input_manifest_json`)),
  `code_fingerprint` varchar(64) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `error_message` text COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  PRIMARY KEY (`run_id`),
  KEY `ix_study_run_stage_status` (`stage`,`status`,`started_at`),
  CONSTRAINT `CONSTRAINT_1` CHECK (`data_scope` in ('public','external','synthetic_test')),
  CONSTRAINT `CONSTRAINT_2` CHECK (`status` in ('running','completed','failed','blocked')),
  CONSTRAINT `CONSTRAINT_3` CHECK (`ended_at` is null or `ended_at` >= `started_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `study_schema_versions` (
  `version` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL,
  `schema_sha256` char(64) COLLATE utf8mb4_unicode_ci NOT NULL,
  `applied_at` datetime(6) NOT NULL,
  PRIMARY KEY (`version`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `study_sources` (
  `source_id` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL,
  `source_version` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL,
  `data_origin` varchar(32) COLLATE utf8mb4_unicode_ci NOT NULL,
  `title` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL,
  `primary_url` text COLLATE utf8mb4_unicode_ci NOT NULL,
  `license_name` varchar(128) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `inspection_status` varchar(32) COLLATE utf8mb4_unicode_ci NOT NULL,
  `metadata_json` longtext CHARACTER SET utf8mb4 COLLATE utf8mb4_bin NOT NULL CHECK (json_valid(`metadata_json`)),
  `created_at` datetime(6) NOT NULL,
  PRIMARY KEY (`source_id`,`source_version`),
  CONSTRAINT `CONSTRAINT_2` CHECK (`inspection_status` in ('candidate','inspected','eligible','ineligible','pending_evidence')),
  CONSTRAINT `ck_study_source_origin` CHECK (`data_origin` in ('public_measured','public_synthetic','public_reference','ulisses_external'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE `study_statistics` (
  `statistic_id` bigint(20) NOT NULL AUTO_INCREMENT,
  `run_id` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL,
  `statistic_key` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL,
  `source_id` varchar(64) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `source_version` varchar(64) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `statistic_name` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL,
  `feature_name` varchar(128) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `other_feature_name` varchar(128) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `numeric_value` double DEFAULT NULL,
  `sample_count` bigint(20) NOT NULL,
  `group_count` bigint(20) DEFAULT NULL,
  `dimensions_json` longtext CHARACTER SET utf8mb4 COLLATE utf8mb4_bin NOT NULL CHECK (json_valid(`dimensions_json`)),
  PRIMARY KEY (`statistic_id`),
  UNIQUE KEY `run_id` (`run_id`,`statistic_key`),
  KEY `source_id` (`source_id`,`source_version`),
  KEY `ix_study_statistic_chart` (`statistic_name`,`feature_name`),
  CONSTRAINT `study_statistics_ibfk_1` FOREIGN KEY (`run_id`) REFERENCES `study_runs` (`run_id`),
  CONSTRAINT `study_statistics_ibfk_2` FOREIGN KEY (`source_id`, `source_version`) REFERENCES `study_sources` (`source_id`, `source_version`),
  CONSTRAINT `CONSTRAINT_1` CHECK (`sample_count` >= 0),
  CONSTRAINT `CONSTRAINT_2` CHECK (`group_count` is null or `group_count` >= 0)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!50001 DROP TABLE IF EXISTS `mb_external_metrics`*/;
/*!50001 SET @saved_cs_client          = @@character_set_client */;
/*!50001 SET @saved_cs_results         = @@character_set_results */;
/*!50001 SET @saved_col_connection     = @@collation_connection */;
/*!50001 SET character_set_client      = utf8mb4 */;
/*!50001 SET character_set_results     = utf8mb4 */;
/*!50001 SET collation_connection      = utf8mb4_general_ci */;
/*!50001 CREATE ALGORITHM=UNDEFINED */
/*!50013 SQL SECURITY INVOKER */
/*!50001 VIEW `mb_external_metrics` AS select `mb_external_predictions`.`campaign_id` AS `campaign_id`,`mb_external_predictions`.`model_id` AS `model_id`,`mb_external_predictions`.`model_version` AS `model_version`,`mb_external_predictions`.`truth_version` AS `truth_version`,count(0) AS `processed_count`,sum(`mb_external_predictions`.`prediction_status` = 'classified') AS `classified_count`,sum(`mb_external_predictions`.`evaluation_eligible`) AS `evaluated_count`,sum(case when `mb_external_predictions`.`evaluation_eligible` = 1 and `mb_external_predictions`.`target_label` = 1 and `mb_external_predictions`.`predicted_class` = 1 then 1 else 0 end) AS `tp`,sum(case when `mb_external_predictions`.`evaluation_eligible` = 1 and `mb_external_predictions`.`target_label` = 0 and `mb_external_predictions`.`predicted_class` = 0 then 1 else 0 end) AS `tn`,sum(case when `mb_external_predictions`.`evaluation_eligible` = 1 and `mb_external_predictions`.`target_label` = 0 and `mb_external_predictions`.`predicted_class` = 1 then 1 else 0 end) AS `fp`,sum(case when `mb_external_predictions`.`evaluation_eligible` = 1 and `mb_external_predictions`.`target_label` = 1 and `mb_external_predictions`.`predicted_class` = 0 then 1 else 0 end) AS `fn`,1.0 * sum(`mb_external_predictions`.`is_correct`) / nullif(sum(`mb_external_predictions`.`evaluation_eligible`),0) AS `accuracy`,1.0 * sum(`mb_external_predictions`.`prediction_status` = 'classified') / nullif(count(0),0) AS `classification_coverage` from `mb_external_predictions` group by `mb_external_predictions`.`campaign_id`,`mb_external_predictions`.`model_id`,`mb_external_predictions`.`model_version`,`mb_external_predictions`.`truth_version` */;
/*!50001 SET character_set_client      = @saved_cs_client */;
/*!50001 SET character_set_results     = @saved_cs_results */;
/*!50001 SET collation_connection      = @saved_col_connection */;
/*!50001 DROP TABLE IF EXISTS `mb_external_predictions`*/;
/*!50001 SET @saved_cs_client          = @@character_set_client */;
/*!50001 SET @saved_cs_results         = @@character_set_results */;
/*!50001 SET @saved_col_connection     = @@collation_connection */;
/*!50001 SET character_set_client      = utf8mb4 */;
/*!50001 SET character_set_results     = utf8mb4 */;
/*!50001 SET collation_connection      = utf8mb4_general_ci */;
/*!50001 CREATE ALGORITHM=UNDEFINED */
/*!50013 SQL SECURITY INVOKER */
/*!50001 VIEW `mb_external_predictions` AS select `c`.`campaign_id` AS `campaign_id`,`p`.`external_case_id` AS `external_case_id`,`p`.`model_id` AS `model_id`,`mo`.`version` AS `model_version`,`p`.`run_id` AS `run_id`,`p`.`truth_version` AS `truth_version`,`g`.`reference_status` AS `reference_status`,`g`.`target_label` AS `target_label`,`p`.`prediction_status` AS `prediction_status`,`p`.`predicted_class` AS `predicted_class`,`p`.`probability_anomaly` AS `probability_anomaly`,`p`.`predicted_at` AS `predicted_at`,`p`.`rejection_reason` AS `rejection_reason`,case when `p`.`prediction_status` = 'classified' and `g`.`reference_status` = 'confirmed' then 1 else 0 end AS `evaluation_eligible`,case when `p`.`prediction_status` = 'classified' and `g`.`reference_status` = 'confirmed' then `p`.`predicted_class` = `g`.`target_label` else NULL end AS `is_correct` from (((`study_external_predictions` `p` join `study_external_cases` `c` on(`c`.`external_case_id` = `p`.`external_case_id`)) join `ml_models` `mo` on(`mo`.`model_id` = `p`.`model_id`)) left join `study_external_ground_truth` `g` on(`g`.`external_case_id` = `p`.`external_case_id` and `g`.`truth_version` = `p`.`truth_version`)) */;
/*!50001 SET character_set_client      = @saved_cs_client */;
/*!50001 SET character_set_results     = @saved_cs_results */;
/*!50001 SET collation_connection      = @saved_col_connection */;
/*!50001 DROP TABLE IF EXISTS `mb_ml_models`*/;
/*!50001 SET @saved_cs_client          = @@character_set_client */;
/*!50001 SET @saved_cs_results         = @@character_set_results */;
/*!50001 SET @saved_col_connection     = @@collation_connection */;
/*!50001 SET character_set_client      = utf8mb4 */;
/*!50001 SET character_set_results     = utf8mb4 */;
/*!50001 SET collation_connection      = utf8mb4_general_ci */;
/*!50001 CREATE ALGORITHM=UNDEFINED */
/*!50013 SQL SECURITY INVOKER */
/*!50001 VIEW `mb_ml_models` AS select `ml_models`.`model_id` AS `model_id`,`ml_models`.`name` AS `name`,`ml_models`.`version` AS `version`,`ml_models`.`processing_version` AS `processing_version`,json_unquote(json_extract(`ml_models`.`document`,'$.training_info.dataset_version')) AS `dataset_version`,json_unquote(json_extract(`ml_models`.`document`,'$.release_status')) AS `release_status`,json_unquote(json_extract(`ml_models`.`document`,'$.training_info.synthetic')) AS `synthetic`,cast(nullif(json_unquote(json_extract(`ml_models`.`document`,'$.metrics.accuracy')),'null') as decimal(14,10)) AS `accuracy`,cast(nullif(json_unquote(json_extract(`ml_models`.`document`,'$.metrics.precision')),'null') as decimal(14,10)) AS `precision`,cast(nullif(json_unquote(json_extract(`ml_models`.`document`,'$.metrics.recall')),'null') as decimal(14,10)) AS `recall`,cast(nullif(json_unquote(json_extract(`ml_models`.`document`,'$.metrics.f1')),'null') as decimal(14,10)) AS `f1` from `ml_models` */;
/*!50001 SET character_set_client      = @saved_cs_client */;
/*!50001 SET character_set_results     = @saved_cs_results */;
/*!50001 SET collation_connection      = @saved_col_connection */;
/*!50001 DROP TABLE IF EXISTS `mb_study_clusters`*/;
/*!50001 SET @saved_cs_client          = @@character_set_client */;
/*!50001 SET @saved_cs_results         = @@character_set_results */;
/*!50001 SET @saved_col_connection     = @@collation_connection */;
/*!50001 SET character_set_client      = utf8mb4 */;
/*!50001 SET character_set_results     = utf8mb4 */;
/*!50001 SET collation_connection      = utf8mb4_general_ci */;
/*!50001 CREATE ALGORITHM=UNDEFINED */
/*!50013 SQL SECURITY INVOKER */
/*!50001 VIEW `mb_study_clusters` AS select `c`.`run_id` AS `run_id`,`o`.`source_id` AS `source_id`,`o`.`source_version` AS `source_version`,`s`.`data_origin` AS `data_origin`,`o`.`observation_id` AS `observation_id`,`o`.`dependency_group_id` AS `dependency_group_id`,`c`.`cluster_label` AS `cluster_label`,`c`.`is_noise` AS `is_noise`,`c`.`outlier_score` AS `outlier_score` from ((`study_clusters` `c` join `study_observations` `o` on(`o`.`observation_id` = `c`.`observation_id`)) join `study_sources` `s` on(`s`.`source_id` = `o`.`source_id` and `s`.`source_version` = `o`.`source_version`)) */;
/*!50001 SET character_set_client      = @saved_cs_client */;
/*!50001 SET character_set_results     = @saved_cs_results */;
/*!50001 SET collation_connection      = @saved_col_connection */;
/*!50001 DROP TABLE IF EXISTS `mb_study_dataset_members`*/;
/*!50001 SET @saved_cs_client          = @@character_set_client */;
/*!50001 SET @saved_cs_results         = @@character_set_results */;
/*!50001 SET @saved_col_connection     = @@collation_connection */;
/*!50001 SET character_set_client      = utf8mb4 */;
/*!50001 SET character_set_results     = utf8mb4 */;
/*!50001 SET collation_connection      = utf8mb4_general_ci */;
/*!50001 CREATE ALGORITHM=UNDEFINED */
/*!50013 SQL SECURITY INVOKER */
/*!50001 VIEW `mb_study_dataset_members` AS select `d`.`dataset_version` AS `dataset_version`,`d`.`status` AS `dataset_status`,`m`.`partition_name` AS `partition_name`,`m`.`dependency_group_id` AS `dependency_group_id`,`o`.`observation_id` AS `observation_id`,`o`.`source_id` AS `source_id`,`o`.`source_version` AS `source_version`,`s`.`data_origin` AS `data_origin`,`l`.`label_id` AS `label_id`,`l`.`label_version` AS `label_version`,`l`.`target_label` AS `target_label`,`l`.`label_status` AS `label_status` from ((((`study_dataset_members` `m` join `study_datasets` `d` on(`d`.`dataset_version` = `m`.`dataset_version`)) join `study_observations` `o` on(`o`.`observation_id` = `m`.`observation_id`)) join `study_sources` `s` on(`s`.`source_id` = `o`.`source_id` and `s`.`source_version` = `o`.`source_version`)) left join `study_labels` `l` on(`l`.`label_id` = `m`.`label_id` and `l`.`observation_id` = `m`.`observation_id`)) */;
/*!50001 SET character_set_client      = @saved_cs_client */;
/*!50001 SET character_set_results     = @saved_cs_results */;
/*!50001 SET collation_connection      = @saved_col_connection */;
/*!50001 DROP TABLE IF EXISTS `mb_study_feature_values`*/;
/*!50001 SET @saved_cs_client          = @@character_set_client */;
/*!50001 SET @saved_cs_results         = @@character_set_results */;
/*!50001 SET @saved_col_connection     = @@collation_connection */;
/*!50001 SET character_set_client      = utf8mb4 */;
/*!50001 SET character_set_results     = utf8mb4 */;
/*!50001 SET collation_connection      = utf8mb4_general_ci */;
/*!50001 CREATE ALGORITHM=UNDEFINED */
/*!50013 SQL SECURITY INVOKER */
/*!50001 VIEW `mb_study_feature_values` AS select `o`.`observation_id` AS `observation_id`,`o`.`source_id` AS `source_id`,`o`.`source_version` AS `source_version`,`s`.`data_origin` AS `data_origin`,`o`.`analysis_unit` AS `analysis_unit`,`o`.`dependency_group_id` AS `dependency_group_id`,`o`.`equipment_id` AS `equipment_id`,`o`.`started_at` AS `started_at`,`o`.`quality_status` AS `quality_status`,`f`.`feature_contract_version` AS `feature_contract_version`,`f`.`feature_name` AS `feature_name`,`f`.`numeric_value` AS `numeric_value`,`f`.`unit` AS `unit`,`f`.`value_status` AS `value_status`,`f`.`run_id` AS `run_id` from ((`study_feature_values` `f` join `study_observations` `o` on(`o`.`observation_id` = `f`.`observation_id`)) join `study_sources` `s` on(`s`.`source_id` = `o`.`source_id` and `s`.`source_version` = `o`.`source_version`)) */;
/*!50001 SET character_set_client      = @saved_cs_client */;
/*!50001 SET character_set_results     = @saved_cs_results */;
/*!50001 SET collation_connection      = @saved_col_connection */;
/*!50001 DROP TABLE IF EXISTS `mb_study_inventory`*/;
/*!50001 SET @saved_cs_client          = @@character_set_client */;
/*!50001 SET @saved_cs_results         = @@character_set_results */;
/*!50001 SET @saved_col_connection     = @@collation_connection */;
/*!50001 SET character_set_client      = utf8mb4 */;
/*!50001 SET character_set_results     = utf8mb4 */;
/*!50001 SET collation_connection      = utf8mb4_general_ci */;
/*!50001 CREATE ALGORITHM=UNDEFINED */
/*!50013 SQL SECURITY INVOKER */
/*!50001 VIEW `mb_study_inventory` AS select `s`.`source_id` AS `source_id`,`s`.`source_version` AS `source_version`,`s`.`data_origin` AS `data_origin`,`s`.`title` AS `title`,`s`.`license_name` AS `license_name`,`s`.`inspection_status` AS `inspection_status`,coalesce(`o`.`observation_count`,0) AS `observation_count`,coalesce(`o`.`group_count`,0) AS `dependency_group_count` from (`study_sources` `s` left join (select `study_observations`.`source_id` AS `source_id`,`study_observations`.`source_version` AS `source_version`,count(0) AS `observation_count`,count(distinct `study_observations`.`dependency_group_id`) AS `group_count` from `study_observations` group by `study_observations`.`source_id`,`study_observations`.`source_version`) `o` on(`o`.`source_id` = `s`.`source_id` and `o`.`source_version` = `s`.`source_version`)) */;
/*!50001 SET character_set_client      = @saved_cs_client */;
/*!50001 SET character_set_results     = @saved_cs_results */;
/*!50001 SET collation_connection      = @saved_col_connection */;
/*!50001 DROP TABLE IF EXISTS `mb_study_labels`*/;
/*!50001 SET @saved_cs_client          = @@character_set_client */;
/*!50001 SET @saved_cs_results         = @@character_set_results */;
/*!50001 SET @saved_col_connection     = @@collation_connection */;
/*!50001 SET character_set_client      = utf8mb4 */;
/*!50001 SET character_set_results     = utf8mb4 */;
/*!50001 SET collation_connection      = utf8mb4_general_ci */;
/*!50001 CREATE ALGORITHM=UNDEFINED */
/*!50013 SQL SECURITY INVOKER */
/*!50001 VIEW `mb_study_labels` AS select `o`.`observation_id` AS `observation_id`,`o`.`source_id` AS `source_id`,`o`.`source_version` AS `source_version`,`s`.`data_origin` AS `data_origin`,`o`.`dependency_group_id` AS `dependency_group_id`,`l`.`label_id` AS `label_id`,`l`.`label_version` AS `label_version`,`l`.`original_label` AS `original_label`,`l`.`target_label` AS `target_label`,`l`.`label_status` AS `label_status`,`l`.`method` AS `method`,`l`.`confidence` AS `confidence`,`l`.`recorded_at` AS `recorded_at` from ((`study_labels` `l` join `study_observations` `o` on(`o`.`observation_id` = `l`.`observation_id`)) join `study_sources` `s` on(`s`.`source_id` = `o`.`source_id` and `s`.`source_version` = `o`.`source_version`)) */;
/*!50001 SET character_set_client      = @saved_cs_client */;
/*!50001 SET character_set_results     = @saved_cs_results */;
/*!50001 SET collation_connection      = @saved_col_connection */;
/*!50001 DROP TABLE IF EXISTS `mb_study_statistics`*/;
/*!50001 SET @saved_cs_client          = @@character_set_client */;
/*!50001 SET @saved_cs_results         = @@character_set_results */;
/*!50001 SET @saved_col_connection     = @@collation_connection */;
/*!50001 SET character_set_client      = utf8mb4 */;
/*!50001 SET character_set_results     = utf8mb4 */;
/*!50001 SET collation_connection      = utf8mb4_general_ci */;
/*!50001 CREATE ALGORITHM=UNDEFINED */
/*!50013 SQL SECURITY INVOKER */
/*!50001 VIEW `mb_study_statistics` AS select `r`.`stage` AS `stage`,`r`.`data_scope` AS `data_scope`,`r`.`status` AS `run_status`,`r`.`started_at` AS `started_at`,`t`.`run_id` AS `run_id`,`t`.`source_id` AS `source_id`,`t`.`source_version` AS `source_version`,`t`.`statistic_name` AS `statistic_name`,`t`.`feature_name` AS `feature_name`,`t`.`other_feature_name` AS `other_feature_name`,`t`.`numeric_value` AS `numeric_value`,`t`.`sample_count` AS `sample_count`,`t`.`group_count` AS `group_count`,`t`.`dimensions_json` AS `dimensions_json` from (`study_statistics` `t` join `study_runs` `r` on(`r`.`run_id` = `t`.`run_id`)) */;
/*!50001 SET character_set_client      = @saved_cs_client */;
/*!50001 SET character_set_results     = @saved_cs_results */;
/*!50001 SET collation_connection      = @saved_col_connection */;
/*!40103 SET TIME_ZONE=@OLD_TIME_ZONE */;

/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
/*!40111 SET SQL_NOTES=@OLD_SQL_NOTES */;

