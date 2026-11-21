"""
Unit and Integration Tests for NeighborhoodDataLoader
"""

import pytest
import pandas as pd

from src.data.config import DOMAIN_CATALOG
from src.data.loader import NeighborhoodDataLoader


@pytest.fixture(scope="module")
def loader():
    return NeighborhoodDataLoader()


def test_load_meter_registry(loader):
    """Test loading the meter registry."""
    df = loader.load_meter_registry()
    assert len(df) == 50
    assert "meter_id" in df.columns
    assert "feeder_id" in df.columns


def test_load_domain_electrical(loader):
    """Test loading electrical_measurements with column projection and meter filtering."""
    meter = "MS212-TN-0001"
    df = loader.load_domain(
        "electrical_measurements",
        meter_ids=meter,
        columns=["voltage_V", "frequency_Hz"],
    )
    assert len(df) > 0
    assert (df["meter_id"] == meter).all()
    assert "voltage_V" in df.columns
    assert "frequency_Hz" in df.columns
    assert "neutral_current_A" not in df.columns


def test_load_domain_feeder_filter(loader):
    """Test filtering by feeder."""
    feeder = "FEEDER-01"
    df = loader.load_domain("energy_registers", feeder_ids=feeder)
    # Check that loaded meters are all in FEEDER-01
    meters_in_feeder = loader.get_meters_by_feeder(feeder)
    assert set(df["meter_id"].unique()).issubset(set(meters_in_feeder))


def test_load_domains_multi_join(loader):
    """Test loading multiple domains merged on record_id."""
    df = loader.load_domains(
        domain_names=["electrical_measurements", "energy_registers"],
        include_registry=True,
        meter_ids="MS212-TN-0001",
    )
    assert "voltage_V" in df.columns
    assert "active_import_kWh" in df.columns
    assert "feeder_id" in df.columns  # from registry
    assert (df["meter_id"] == "MS212-TN-0001").all()


def test_ml_presets(loader):
    """Test ML preset loader methods."""
    # Tampering preset
    df_tamper = loader.load_for_tampering_detection(
        meter_ids=["MS212-TN-0001"],
        include_status=True,
    )
    assert "voltage_V" in df_tamper.columns
    assert "active_import_kWh" in df_tamper.columns
    assert "magnetic_field_detected" in df_tamper.columns
    assert "breaker_state" in df_tamper.columns

    # Device health preset
    df_health = loader.load_for_device_health(meter_ids=["MS212-TN-0002"])
    assert "breaker_state" in df_health.columns
    assert "comm_channel" in df_health.columns
