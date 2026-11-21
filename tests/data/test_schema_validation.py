"""
Unit and Integration Tests for Schema Validation System
"""

import pandas as pd
import pytest

from src.data.config import STRUCTURED_DATA_DIR
from src.data.validator import (
    SchemaValidator,
    validate_all_datasets,
    validate_dataset,
)


@pytest.fixture(scope="module")
def sample_data():
    """Load sample data slices for testing."""
    return {
        "meter_registry": pd.read_csv(STRUCTURED_DATA_DIR / "meter_registry.csv"),
        "electrical_measurements": pd.read_csv(STRUCTURED_DATA_DIR / "electrical_measurements.csv", nrows=100),
        "device_status": pd.read_csv(STRUCTURED_DATA_DIR / "device_status.csv", nrows=100),
    }


def test_valid_data_passes_validation(sample_data):
    """Verify that real structured data passes schema validation cleanly."""
    res_reg = validate_dataset("meter_registry", sample_data["meter_registry"])
    assert res_reg.is_valid, f"meter_registry failed validation: {res_reg.errors}"

    res_elec = validate_dataset(
        "electrical_measurements",
        sample_data["electrical_measurements"],
        registry_data=sample_data["meter_registry"],
    )
    assert res_elec.is_valid, f"electrical_measurements failed: {res_elec.errors}"


def test_missing_required_column_rejected(sample_data):
    """Verify that missing required column is caught with an error."""
    df_bad = sample_data["electrical_measurements"].drop(columns=["voltage_V"])
    res = validate_dataset("electrical_measurements", df_bad)
    assert not res.is_valid
    rules = [e.rule for e in res.errors]
    assert "required_column" in rules


def test_non_nullable_null_rejected(sample_data):
    """Verify that inserting a null in a non-nullable column fails validation."""
    df_bad = sample_data["device_status"].copy()
    df_bad.loc[0, "breaker_state"] = None
    res = validate_dataset("device_status", df_bad)
    assert not res.is_valid
    assert any(e.rule == "nullability" and e.column == "breaker_state" for e in res.errors)


def test_unpermitted_categorical_value_rejected(sample_data):
    """Verify that unpermitted categorical string is rejected."""
    df_bad = sample_data["device_status"].copy()
    df_bad.loc[0, "breaker_state"] = "PARTIAL_TRIP"
    res = validate_dataset("device_status", df_bad)
    assert not res.is_valid
    assert any(e.rule == "allowed_values" and e.column == "breaker_state" for e in res.errors)


def test_numerical_range_bounds_rejected(sample_data):
    """Verify that out-of-bounds numeric value is rejected."""
    df_bad = sample_data["meter_registry"].copy()
    df_bad.loc[0, "distance_from_transformer_m"] = 5000.0  # max allowed is 1200.0
    res = validate_dataset("meter_registry", df_bad)
    assert not res.is_valid
    assert any(e.rule == "range_max" for e in res.errors)


def test_duplicate_primary_key_rejected(sample_data):
    """Verify that duplicate primary key is caught."""
    df_bad = sample_data["meter_registry"].copy()
    df_bad = pd.concat([df_bad, df_bad.iloc[[0]]], ignore_index=True)
    res = validate_dataset("meter_registry", df_bad)
    assert not res.is_valid
    assert any(e.rule == "primary_key_uniqueness" for e in res.errors)


def test_orphan_foreign_key_rejected(sample_data):
    """Verify that orphan meter_id not in registry is detected."""
    df_bad = sample_data["electrical_measurements"].copy()
    df_bad.loc[0, "meter_id"] = "MS212-TN-9999"
    res = validate_dataset(
        "electrical_measurements",
        df_bad,
        registry_data=sample_data["meter_registry"],
    )
    assert not res.is_valid
    assert any(e.rule == "referential_integrity" for e in res.errors)


def test_validate_all_datasets_sampled():
    """Verify validate_all_datasets succeeds on all 7 structured CSV files."""
    results = validate_all_datasets(sample_size=200)
    assert len(results) == 7
    for domain, res in results.items():
        assert res.is_valid, f"Domain {domain} failed batch validation: {res.errors}"
