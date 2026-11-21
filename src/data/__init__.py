"""
EnergyMind Tunisia — Data Architecture & Contract Module
========================================================
Modular, domain-based data architecture and schema contract system for
Sagemcom MS212 smart meter telemetry on the STEG Tunisia distribution network.
"""

from src.data.config import (
    COLUMN_DTYPES,
    COMMUNICATIONS_COLUMNS,
    DEVICE_STATUS_COLUMNS,
    DOMAIN_CATALOG,
    ELECTRICAL_MEASUREMENTS_COLUMNS,
    ENERGY_REGISTERS_COLUMNS,
    FALLBACK_RAW_CSV,
    LABELS_COLUMNS,
    METER_EVENTS_COLUMNS,
    METER_REGISTRY_COLUMNS,
    ORIGINAL_COLUMNS,
    PRIMARY_RAW_CSV,
    PROJECT_ROOT,
    RAW_DATA_DIR,
    STRUCTURED_DATA_DIR,
)
from src.data.splitter import DatasetSplitter
from src.data.reconstructor import DatasetReconstructor
from src.data.validator import (
    DataIntegrityValidator,
    SchemaValidator,
    ValidationErrorDetail,
    ValidationResult,
    validate_all_datasets,
    validate_dataset,
)
from src.data.loader import NeighborhoodDataLoader
from src.data.feature_engineering import FeatureEngineer
from src.data.schema_loader import (
    SchemaLoader,
    get_all_schemas,
    get_relationships,
    get_schema,
    get_version_info,
)
from src.data.models import (
    DOMAIN_MODELS,
    CommunicationsRecord,
    DeviceStatusRecord,
    ElectricalMeasurementsRecord,
    EnergyRegistersRecord,
    LabelsRecord,
    MeterEventsRecord,
    MeterRegistryRecord,
)

__all__ = [
    "DatasetSplitter",
    "NeighborhoodDataLoader",
    "DatasetReconstructor",
    "DataIntegrityValidator",
    "SchemaValidator",
    "ValidationResult",
    "ValidationErrorDetail",
    "validate_dataset",
    "validate_all_datasets",
    "FeatureEngineer",
    "SchemaLoader",
    "get_schema",
    "get_all_schemas",
    "get_relationships",
    "get_version_info",
    "MeterRegistryRecord",
    "EnergyRegistersRecord",
    "ElectricalMeasurementsRecord",
    "MeterEventsRecord",
    "DeviceStatusRecord",
    "CommunicationsRecord",
    "LabelsRecord",
    "DOMAIN_MODELS",
    "DOMAIN_CATALOG",
    "ORIGINAL_COLUMNS",
    "METER_REGISTRY_COLUMNS",
    "ENERGY_REGISTERS_COLUMNS",
    "ELECTRICAL_MEASUREMENTS_COLUMNS",
    "METER_EVENTS_COLUMNS",
    "DEVICE_STATUS_COLUMNS",
    "COMMUNICATIONS_COLUMNS",
    "LABELS_COLUMNS",
    "COLUMN_DTYPES",
    "PRIMARY_RAW_CSV",
    "FALLBACK_RAW_CSV",
    "RAW_DATA_DIR",
    "STRUCTURED_DATA_DIR",
    "PROJECT_ROOT",
]
