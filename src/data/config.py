"""
EnergyMind Tunisia — Data Architecture Configuration
=====================================================
Centralizes paths, domain column schemas, data types, and constants
for the modular neighborhood data architecture.
"""

from pathlib import Path
from typing import Dict, List

# ── Project Directory Paths ──────────────────────────────────────────────────
# Resolves paths relative to project root
SRC_DATA_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SRC_DATA_DIR.parent.parent

DATA_DIR = PROJECT_ROOT / "data" / "realistic"
RAW_DATA_DIR = DATA_DIR / "raw"
STRUCTURED_DATA_DIR = DATA_DIR / "structured"
PROCESSED_DATA_DIR = DATA_DIR / "processed"

# Default raw monolithic dataset path (primary in data/realistic/raw, fallback to root)
PRIMARY_RAW_CSV = RAW_DATA_DIR / "neighborhood_dataset.csv"
FALLBACK_RAW_CSV = PROJECT_ROOT / "neighborhood_dataset.csv"

# ── Complete Established 33-Column Model (In Original Sequence) ──────────────
ORIGINAL_COLUMNS: List[str] = [
    # Identification and Network Topology
    "record_id",
    "meter_id",
    "feeder_id",
    "phase",
    "distance_from_transformer_m",
    "household_type",
    # Timestamps and Communication
    "event_timestamp",
    "ingest_timestamp",
    "comm_channel",
    # Energy Registers
    "active_import_kWh",
    "active_export_kWh",
    "reactive_Q1_kvarh",
    "reactive_Q2_kvarh",
    "reactive_Q3_kvarh",
    "reactive_Q4_kvarh",
    # Electrical Measurements
    "voltage_V",
    "frequency_Hz",
    "neutral_current_A",
    # Events and Operating State
    "voltage_interruptions",
    "voltage_restorations",
    "power_factor_variation_detected",
    "tariff_register",
    "breaker_state",
    # Tampering and Fraud Detection
    "magnetic_field_detected",
    "top_cover_opened",
    "terminal_cover_opened",
    "io_swap",
    "phase_neutral_swap",
    "mains_power_cut",
    "neutral_disturbance",
    # Diagnostics and Classification
    "auto_diagnostic",
    "quality_flags",
    "label",
]

# ── Modular Domain Column Definitions ────────────────────────────────────────

# A. meter_registry.csv — Static meter and network topology metadata
METER_REGISTRY_COLUMNS: List[str] = [
    "meter_id",
    "feeder_id",
    "phase",
    "distance_from_transformer_m",
    "household_type",
]

# B. energy_registers.csv — Energy measurements and billing registers
ENERGY_REGISTERS_COLUMNS: List[str] = [
    "record_id",
    "meter_id",
    "event_timestamp",
    "active_import_kWh",
    "active_export_kWh",
    "reactive_Q1_kvarh",
    "reactive_Q2_kvarh",
    "reactive_Q3_kvarh",
    "reactive_Q4_kvarh",
    "tariff_register",
]

# C. electrical_measurements.csv — Instantaneous electrical measurement time series
ELECTRICAL_MEASUREMENTS_COLUMNS: List[str] = [
    "record_id",
    "meter_id",
    "event_timestamp",
    "voltage_V",
    "frequency_Hz",
    "neutral_current_A",
]

# D. meter_events.csv — Electrical events, tampering, and fraud-related flags
METER_EVENTS_COLUMNS: List[str] = [
    "record_id",
    "meter_id",
    "event_timestamp",
    "voltage_interruptions",
    "voltage_restorations",
    "power_factor_variation_detected",
    "magnetic_field_detected",
    "top_cover_opened",
    "terminal_cover_opened",
    "io_swap",
    "phase_neutral_swap",
    "mains_power_cut",
    "neutral_disturbance",
]

# E. device_status.csv — Meter operating status, relay breaker, and diagnostics
DEVICE_STATUS_COLUMNS: List[str] = [
    "record_id",
    "meter_id",
    "event_timestamp",
    "breaker_state",
    "auto_diagnostic",
    "quality_flags",
]

# F. communications.csv — Communication telemetry and network latency tracking
COMMUNICATIONS_COLUMNS: List[str] = [
    "record_id",
    "meter_id",
    "event_timestamp",
    "ingest_timestamp",
    "comm_channel",
]

# G. labels.csv — Ground-truth classification labels (quarantined from features)
LABELS_COLUMNS: List[str] = [
    "record_id",
    "meter_id",
    "event_timestamp",
    "label",
]

# Domain catalog mapping domain name -> (filename, columns, is_observation_level)
DOMAIN_CATALOG: Dict[str, Dict[str, any]] = {
    "meter_registry": {
        "filename": "meter_registry.csv",
        "columns": METER_REGISTRY_COLUMNS,
        "primary_key": ["meter_id"],
        "is_observation_level": False,
        "description": "Static meter and low-voltage network topology metadata",
    },
    "energy_registers": {
        "filename": "energy_registers.csv",
        "columns": ENERGY_REGISTERS_COLUMNS,
        "primary_key": ["record_id"],
        "is_observation_level": True,
        "description": "Cumulative energy measurements and billing registers (kWh/kvarh)",
    },
    "electrical_measurements": {
        "filename": "electrical_measurements.csv",
        "columns": ELECTRICAL_MEASUREMENTS_COLUMNS,
        "primary_key": ["record_id"],
        "is_observation_level": True,
        "description": "Instantaneous electrical values (voltage, frequency, neutral current)",
    },
    "meter_events": {
        "filename": "meter_events.csv",
        "columns": METER_EVENTS_COLUMNS,
        "primary_key": ["record_id"],
        "is_observation_level": True,
        "description": "Tampering flags, grid interruptions, and power quality event logs",
    },
    "device_status": {
        "filename": "device_status.csv",
        "columns": DEVICE_STATUS_COLUMNS,
        "primary_key": ["record_id"],
        "is_observation_level": True,
        "description": "Meter breaker state, auto-diagnostic checks, and data quality bitmask",
    },
    "communications": {
        "filename": "communications.csv",
        "columns": COMMUNICATIONS_COLUMNS,
        "primary_key": ["record_id"],
        "is_observation_level": True,
        "description": "Communication channel protocols and gateway ingestion timestamps",
    },
    "labels": {
        "filename": "labels.csv",
        "columns": LABELS_COLUMNS,
        "primary_key": ["record_id"],
        "is_observation_level": True,
        "description": "Ground-truth classification target labels (quarantined)",
    },
}

# ── Standard Column Dtypes for Exact Type Preservation ──────────────────────
COLUMN_DTYPES: Dict[str, str] = {
    "record_id": "int64",
    "meter_id": "string",
    "feeder_id": "string",
    "phase": "string",
    "distance_from_transformer_m": "float64",
    "household_type": "string",
    "event_timestamp": "string",
    "ingest_timestamp": "string",
    "comm_channel": "string",
    "active_import_kWh": "float64",
    "active_export_kWh": "float64",
    "reactive_Q1_kvarh": "float64",
    "reactive_Q2_kvarh": "float64",
    "reactive_Q3_kvarh": "float64",
    "reactive_Q4_kvarh": "float64",
    "voltage_V": "float64",
    "frequency_Hz": "float64",
    "neutral_current_A": "float64",
    "voltage_interruptions": "int64",
    "voltage_restorations": "int64",
    "power_factor_variation_detected": "int64",
    "tariff_register": "string",
    "breaker_state": "string",
    "magnetic_field_detected": "int64",
    "top_cover_opened": "int64",
    "terminal_cover_opened": "int64",
    "io_swap": "int64",
    "phase_neutral_swap": "int64",
    "mains_power_cut": "int64",
    "neutral_disturbance": "int64",
    "auto_diagnostic": "string",
    "quality_flags": "int64",
    "label": "string",
}
