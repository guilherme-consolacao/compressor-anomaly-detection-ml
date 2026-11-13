from dataclasses import dataclass
from datetime import datetime

SIGNAL_DEFINITION = "api-calibrated-spatial-rms-v1"
PROCESSING_VERSION = "spatial-rms-stats-v1"
FEATURE_NAMES = (
    "temp_media",
    "temp_max",
    "temp_amplitude",
    "temp_desvio_padrao",
    "vib_rms_media",
    "vib_rms_max",
    "vib_rms_amplitude",
    "vib_rms_desvio_padrao",
    "x_media",
    "x_pico_abs",
    "x_amplitude",
    "x_desvio_padrao",
    "y_media",
    "y_pico_abs",
    "y_amplitude",
    "y_desvio_padrao",
    "z_media",
    "z_pico_abs",
    "z_amplitude",
    "z_desvio_padrao",
)


@dataclass(frozen=True)
class Reading:
    reading_id: int
    timestamp: datetime
    temperature_c: float
    vibration_rms_g: float
    axis_x_g: float
    axis_y_g: float
    axis_z_g: float


@dataclass(frozen=True)
class Measurement:
    measurement_id: str
    equipment_id: str
    started_at: datetime
    ended_at: datetime | None
    status: str
    expected_reading_count: int
    readings: tuple[Reading, ...]
    label: int | None = None
    label_source: str | None = None
    group_id: str = ""
    acceleration_unit: str = "unknown"
    signal_definition: str = SIGNAL_DEFINITION


@dataclass(frozen=True)
class FeatureVector:
    values: tuple[float, ...]
    source_fingerprint: str
    reading_count: int
    processing_version: str = PROCESSING_VERSION
    feature_names: tuple[str, ...] = FEATURE_NAMES

    def as_dict(self) -> dict[str, float]:
        return dict(zip(self.feature_names, self.values, strict=True))


@dataclass(frozen=True)
class PredictionResult:
    predicted_class: int
    probability_normal: float
    probability_anomaly: float
