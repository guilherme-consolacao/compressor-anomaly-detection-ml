"""Additive ML schema; ``readings`` is owned by the acquisition application.

Declaring that table here only describes the read contract and resolves foreign
keys. Production code never calls ``create_all``.
"""

from datetime import datetime

from sqlalchemy import (
    JSON,
    BigInteger,
    CheckConstraint,
    Column,
    DateTime,
    Float,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    Numeric,
    String,
    Table,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.mysql import BIGINT, DATETIME, TIMESTAMP
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


READING_ID = (
    BigInteger().with_variant(Integer(), "sqlite").with_variant(BIGINT(unsigned=True), "mysql")
)
ML_TIMESTAMP = DateTime().with_variant(DATETIME(fsp=6), "mysql")
SOURCE_READINGS = Table(
    "readings",
    Base.metadata,
    Column("id", READING_ID, primary_key=True, autoincrement=True),
    Column("temperature", Numeric(12, 6), nullable=False),
    Column("accel_x", Numeric(12, 6), nullable=False),
    Column("accel_y", Numeric(12, 6), nullable=False),
    Column("accel_z", Numeric(12, 6), nullable=False),
    Column("rms", Numeric(12, 6), nullable=False),
    Column(
        "timestamp",
        DateTime().with_variant(TIMESTAMP(), "mysql"),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    ),
    Index("idx_timestamp", "timestamp"),
)


class MeasurementRow(Base):
    __tablename__ = "ml_measurements"
    __table_args__ = (
        CheckConstraint("status IN ('ABERTA', 'FINALIZADA')", name="ck_ml_measurement_status"),
        CheckConstraint("label IS NULL OR label IN (0, 1)", name="ck_ml_measurement_label"),
        CheckConstraint("expected_reading_count >= 0", name="ck_ml_measurement_count"),
        Index("ix_ml_measurements_status_label", "status", "label"),
    )

    measurement_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    equipment_id: Mapped[str] = mapped_column(String(64), nullable=False)
    started_at: Mapped[datetime] = mapped_column(ML_TIMESTAMP, nullable=False)
    ended_at: Mapped[datetime | None] = mapped_column(ML_TIMESTAMP, nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    expected_reading_count: Mapped[int] = mapped_column(Integer(), nullable=False)
    label: Mapped[int | None] = mapped_column(Integer(), nullable=True)
    label_source: Mapped[str | None] = mapped_column(String(255), nullable=True)
    group_id: Mapped[str] = mapped_column(String(128), nullable=False)
    acceleration_unit: Mapped[str] = mapped_column(String(16), nullable=False)
    signal_definition: Mapped[str] = mapped_column(String(64), nullable=False)


class MeasurementReadingRow(Base):
    __tablename__ = "ml_measurement_readings"

    reading_id: Mapped[int] = mapped_column(
        READING_ID, ForeignKey("readings.id", ondelete="RESTRICT"), primary_key=True
    )
    measurement_id: Mapped[str] = mapped_column(
        ForeignKey("ml_measurements.measurement_id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )


class FeatureRow(Base):
    __tablename__ = "ml_features"
    __table_args__ = (CheckConstraint("reading_count >= 2", name="ck_ml_features_count"),)

    measurement_id: Mapped[str] = mapped_column(
        ForeignKey("ml_measurements.measurement_id", ondelete="RESTRICT"), primary_key=True
    )
    processing_version: Mapped[str] = mapped_column(String(64), primary_key=True)
    feature_names: Mapped[list] = mapped_column(JSON(), nullable=False)
    values: Mapped[list] = mapped_column(JSON(), nullable=False)
    source_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    reading_count: Mapped[int] = mapped_column(Integer(), nullable=False)


class ModelRow(Base):
    __tablename__ = "ml_models"
    __table_args__ = (UniqueConstraint("name", "version", name="uq_ml_model_version"),)

    model_id: Mapped[int] = mapped_column(Integer(), primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    version: Mapped[str] = mapped_column(String(128), nullable=False)
    processing_version: Mapped[str] = mapped_column(String(64), nullable=False)
    document: Mapped[dict] = mapped_column(JSON(), nullable=False)


class PredictionRow(Base):
    __tablename__ = "ml_predictions"
    __table_args__ = (
        UniqueConstraint("measurement_id", "model_id", name="uq_ml_prediction"),
        ForeignKeyConstraint(
            ["measurement_id", "processing_version"],
            ["ml_features.measurement_id", "ml_features.processing_version"],
            name="fk_ml_prediction_features",
            ondelete="RESTRICT",
        ),
        CheckConstraint("predicted_class IN (0, 1)", name="ck_ml_prediction_class"),
        CheckConstraint(
            "probability_normal >= 0 AND probability_normal <= 1",
            name="ck_ml_probability_normal",
        ),
        CheckConstraint(
            "probability_anomaly >= 0 AND probability_anomaly <= 1",
            name="ck_ml_probability_anomaly",
        ),
        Index("ix_ml_predictions_model_time", "model_id", "predicted_at"),
    )

    prediction_id: Mapped[int] = mapped_column(Integer(), primary_key=True, autoincrement=True)
    measurement_id: Mapped[str] = mapped_column(
        ForeignKey("ml_measurements.measurement_id", ondelete="RESTRICT"), nullable=False
    )
    model_id: Mapped[int] = mapped_column(
        ForeignKey("ml_models.model_id", ondelete="RESTRICT"), nullable=False
    )
    processing_version: Mapped[str] = mapped_column(String(64), nullable=False)
    source_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    predicted_class: Mapped[int] = mapped_column(Integer(), nullable=False)
    probability_normal: Mapped[float] = mapped_column(Float(), nullable=False)
    probability_anomaly: Mapped[float] = mapped_column(Float(), nullable=False)
    predicted_at: Mapped[datetime] = mapped_column(ML_TIMESTAMP, nullable=False)


class ProcessingRunRow(Base):
    __tablename__ = "ml_processing_runs"
    __table_args__ = (
        CheckConstraint("status IN ('PROCESSADA', 'ERRO')", name="ck_ml_processing_status"),
    )

    measurement_id: Mapped[str] = mapped_column(
        ForeignKey("ml_measurements.measurement_id", ondelete="RESTRICT"), primary_key=True
    )
    model_id: Mapped[int] = mapped_column(
        ForeignKey("ml_models.model_id", ondelete="RESTRICT"), primary_key=True
    )
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text(), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(ML_TIMESTAMP, nullable=False)


class FeatureImportanceRow(Base):
    __tablename__ = "ml_feature_importances"
    __table_args__ = (CheckConstraint("importance >= 0", name="ck_ml_importance"),)

    model_id: Mapped[int] = mapped_column(
        ForeignKey("ml_models.model_id", ondelete="RESTRICT"), primary_key=True
    )
    feature_name: Mapped[str] = mapped_column(String(64), primary_key=True)
    importance: Mapped[float] = mapped_column(Float(), nullable=False)


ML_TABLES = [table for table in Base.metadata.sorted_tables if table.name != "readings"]
