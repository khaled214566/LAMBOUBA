"""
Unit and Integration Tests for Pydantic Data Contract Models
"""

import pytest
from pydantic import ValidationError

from src.data.models import (
    DOMAIN_MODELS,
    DeviceStatusRecord,
    ElectricalMeasurementsRecord,
    MeterEventsRecord,
    MeterRegistryRecord,
)


def test_meter_registry_valid_instantiation():
    """Verify MeterRegistryRecord accepts valid attributes."""
    record = MeterRegistryRecord(
        meter_id="MS212-TN-0001",
        feeder_id="feeder_01",
        phase="L1",
        distance_from_transformer_m=120.5,
        household_type="family_home",
    )
    assert record.meter_id == "MS212-TN-0001"
    assert record.feeder_id == "feeder_01"


def test_meter_registry_invalid_meter_id_pattern():
    """Verify MeterRegistryRecord enforces meter_id regex pattern."""
    with pytest.raises(ValidationError):
        MeterRegistryRecord(
            meter_id="INVALID_ID_123",
            feeder_id="feeder_01",
            phase="L1",
            distance_from_transformer_m=120.5,
            household_type="family_home",
        )


def test_meter_registry_invalid_feeder():
    """Verify MeterRegistryRecord enforces permitted feeder enum."""
    with pytest.raises(ValidationError):
        MeterRegistryRecord(
            meter_id="MS212-TN-0001",
            feeder_id="feeder_99",
            phase="L1",
            distance_from_transformer_m=120.5,
            household_type="family_home",
        )


def test_electrical_measurements_nullable_handling():
    """Verify ElectricalMeasurementsRecord allows None for voltage during missing_data."""
    record = ElectricalMeasurementsRecord(
        record_id=1,
        meter_id="MS212-TN-0001",
        event_timestamp="2026-11-13T00:00:00+00:00",
        voltage_V=None,
        frequency_Hz=None,
        neutral_current_A=None,
    )
    assert record.voltage_V is None
    assert record.record_id == 1


def test_device_status_invalid_breaker_state():
    """Verify DeviceStatusRecord rejects unpermitted breaker states."""
    with pytest.raises(ValidationError):
        DeviceStatusRecord(
            record_id=1,
            meter_id="MS212-TN-0001",
            event_timestamp="2026-11-13T00:00:00+00:00",
            breaker_state="TRIPPED",  # only CLOSED or OPEN allowed
            auto_diagnostic="OK",
            quality_flags=0,
        )


def test_all_domains_have_pydantic_model():
    """Verify all 7 domains have registered Pydantic models."""
    assert len(DOMAIN_MODELS) == 7
    expected = [
        "meter_registry",
        "energy_registers",
        "electrical_measurements",
        "meter_events",
        "device_status",
        "communications",
        "labels",
    ]
    for d in expected:
        assert d in DOMAIN_MODELS
