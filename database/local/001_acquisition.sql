-- Local structural copy only. Never run against the acquisition server.
CREATE TABLE readings (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    temperature DECIMAL(12,6) NOT NULL,
    accel_x DECIMAL(12,6) NOT NULL,
    accel_y DECIMAL(12,6) NOT NULL,
    accel_z DECIMAL(12,6) NOT NULL,
    rms DECIMAL(12,6) NOT NULL,
    timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_readings_timestamp (timestamp)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
