"""
EnergyMind Tunisia — Pydantic Data Contract Models
==================================================
Strict Python models representing records across all 7 domains,
aligned 1:1 with authoritative YAML schemas in schemas/*.schema.yaml.
"""

from datetime import datetime
from typing import Dict, Literal, Optional, Type
from pydantic import BaseModel, Field, field_validator


# ── 1. Meter Registry Model ──────────────────────────────────────────────────
class MeterRegistryRecord(BaseModel):
    """Data contract for meter_registry.csv static metadata."""
    meter_id: str = Field(
        ...,
        pattern=r"^MS212-TN-\d{4}$",
        description="Sagemcom MS212 smart meter hardware ID",
    )
    feeder_id: Literal["feeder_01", "feeder_02", "feeder_03"] = Field(
        ..., description="Distribution transformer LV outgoing feeder line"
    )
    phase: Literal["L1", "L2", "L3"] = Field(
        ..., description="Grid phase connection"
    )
    distance_from_transformer_m: float = Field(
        ..., ge=10.0, le=1200.0, description="Cable distance from secondary substation in meters"
    )
    household_type: Literal["family_home", "high_usage_home", "small_flat"] = Field(
        ..., description="STEG residential consumer category"
    )


# ── 2. Energy Registers Model ────────────────────────────────────────────────
class EnergyRegistersRecord(BaseModel):
    """Data contract for energy_registers.csv cumulative registers."""
    record_id: int = Field(..., ge=1, description="Observation primary key")
    meter_id: str = Field(..., pattern=r"^MS212-TN-\d{4}$", description="Meter ID")
    event_timestamp: str = Field(..., description="ISO8601 sampling timestamp")
    active_import_kWh: float = Field(..., ge=0.0, description="Active energy import (kWh)")
    active_export_kWh: float = Field(..., ge=0.0, description="Active energy export (kWh)")
    reactive_Q1_kvarh: float = Field(..., ge=0.0, description="Reactive Q1 inductive import (kvarh)")
    reactive_Q2_kvarh: float = Field(..., ge=0.0, description="Reactive Q2 capacitive export (kvarh)")
    reactive_Q3_kvarh: float = Field(..., ge=0.0, description="Reactive Q3 inductive export (kvarh)")
    reactive_Q4_kvarh: float = Field(..., ge=0.0, description="Reactive Q4 capacitive import (kvarh)")
    tariff_register: Literal["T1", "T2", "T3"] = Field(..., description="Active STEG tariff register")


# ── 3. Electrical Measurements Model ─────────────────────────────────────────
class ElectricalMeasurementsRecord(BaseModel):
    """Data contract for electrical_measurements.csv instantaneous parameters."""
    record_id: int = Field(..., ge=1, description="Observation primary key")
    meter_id: str = Field(..., pattern=r"^MS212-TN-\d{4}$", description="Meter ID")
    event_timestamp: str = Field(..., description="ISO8601 sampling timestamp")
    voltage_V: Optional[float] = Field(
        default=None, ge=0.0, le=1200.0, description="RMS voltage (V). Null during missing_data."
    )
    frequency_Hz: Optional[float] = Field(
        default=None, ge=45.0, le=55.0, description="Grid frequency (Hz). Null during missing_data."
    )
    neutral_current_A: Optional[float] = Field(
        default=None, ge=0.0, le=150.0, description="Neutral current (A). Null during missing_data."
    )


# ── 4. Meter Events Model ────────────────────────────────────────────────────
class MeterEventsRecord(BaseModel):
    """Data contract for meter_events.csv power quality and fraud flags."""
    record_id: int = Field(..., ge=1, description="Observation primary key")
    meter_id: str = Field(..., pattern=r"^MS212-TN-\d{4}$", description="Meter ID")
    event_timestamp: str = Field(..., description="ISO8601 sampling timestamp")
    voltage_interruptions: int = Field(..., ge=0, description="Voltage interruption counter")
    voltage_restorations: int = Field(..., ge=0, description="Voltage restoration counter")
    power_factor_variation_detected: Literal[0, 1] = Field(..., description="PF threshold variation flag")
    magnetic_field_detected: Literal[0, 1] = Field(..., description="Hall-effect magnetic tamper flag")
    top_cover_opened: Literal[0, 1] = Field(..., description="Top cover breach flag")
    terminal_cover_opened: Literal[0, 1] = Field(..., description="Terminal block cover breach flag")
    io_swap: Literal[0, 1] = Field(..., description="Current sensor inversion fraud flag")
    phase_neutral_swap: Literal[0, 1] = Field(..., description="Phase/neutral swap fraud flag")
    mains_power_cut: Literal[0, 1] = Field(..., description="Mains power cut alert")
    neutral_disturbance: Literal[0, 1] = Field(..., description="Neutral disturbance fraud flag")


# ── 5. Device Status Model ───────────────────────────────────────────────────
class DeviceStatusRecord(BaseModel):
    """Data contract for device_status.csv diagnostics and breaker relay."""
    record_id: int = Field(..., ge=1, description="Observation primary key")
    meter_id: str = Field(..., pattern=r"^MS212-TN-\d{4}$", description="Meter ID")
    event_timestamp: str = Field(..., description="ISO8601 sampling timestamp")
    breaker_state: Literal["CLOSED", "OPEN"] = Field(..., description="Latching relay state")
    auto_diagnostic: Literal["OK", "WARNING", "ERROR", "ALARM"] = Field(
        ..., description="DLMS diagnostic health code"
    )
    quality_flags: int = Field(..., ge=0, description="Data quality bitmask")


# ── 6. Communications Model ──────────────────────────────────────────────────
class CommunicationsRecord(BaseModel):
    """Data contract for communications.csv telemetry."""
    record_id: int = Field(..., ge=1, description="Observation primary key")
    meter_id: str = Field(..., pattern=r"^MS212-TN-\d{4}$", description="Meter ID")
    event_timestamp: str = Field(..., description="ISO8601 sampling timestamp")
    ingest_timestamp: str = Field(..., description="Gateway ingestion timestamp")
    comm_channel: Literal["Cellular-4G", "G3-PLC", "W-Mbus"] = Field(
        ..., description="Communication protocol"
    )


# ── 7. Labels Model ──────────────────────────────────────────────────────────
LabelLiteral = Literal[
    "constant_bias",
    "device_fault",
    "dropout",
    "energy_power_mismatch",
    "frequency_deviation",
    "meter_drift",
    "missing_data",
    "neutral_current_imbalance",
    "neutral_disturbance",
    "normal",
    "normal_capacitive_q4",
    "normal_export_q2",
    "normal_export_q3",
    "overcurrent",
    "overvoltage",
    "poor_power_factor",
    "power_cut",
    "random_corruption",
    "tamper_io_swap",
    "tamper_magnetic",
    "tamper_multiple",
    "tamper_phase_neutral_swap",
    "tamper_terminal_cover",
    "tamper_top_cover",
    "undervoltage",
]

class LabelsRecord(BaseModel):
    """Data contract for labels.csv quarantined ground-truth target."""
    record_id: int = Field(..., ge=1, description="Observation primary key")
    meter_id: str = Field(..., pattern=r"^MS212-TN-\d{4}$", description="Meter ID")
    event_timestamp: str = Field(..., description="ISO8601 sampling timestamp")
    label: LabelLiteral = Field(..., description="Supervised ground truth class")


# Domain to Model Registry
DOMAIN_MODELS: Dict[str, Type[BaseModel]] = {
    "meter_registry": MeterRegistryRecord,
    "energy_registers": EnergyRegistersRecord,
    "electrical_measurements": ElectricalMeasurementsRecord,
    "meter_events": MeterEventsRecord,
    "device_status": DeviceStatusRecord,
    "communications": CommunicationsRecord,
    "labels": LabelsRecord,
}
