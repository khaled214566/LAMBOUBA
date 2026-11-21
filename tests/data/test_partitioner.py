"""
Unit and Integration Tests for DatasetPartitioner & Rule-Based Split Loader
"""

import json
from pathlib import Path
import pandas as pd
import pytest

from src.data.config import (
    FEATURE_MANIFEST_PATH,
    HELD_OUT_METERS,
    PROCESSED_DATA_DIR,
    SPLITS_DIR,
    SPLITS_MANIFEST_PATH,
    TEST_CUTOFF_TIMESTAMP,
    VAL_CUTOFF_TIMESTAMP,
)
from src.data.loader import NeighborhoodDataLoader
from src.data.partitioner import DatasetPartitioner


@pytest.fixture(scope="module")
def partitioner_manifest():
    """Ensure partitioner manifest and matrices are up to date."""
    partitioner = DatasetPartitioner()
    manifest = partitioner.generate_splits_manifest()
    parquet_paths = partitioner.build_processed_ml_matrices()
    return manifest, parquet_paths


def test_stratified_meter_selection():
    """Verify that exactly 10 meters are held out and cover all 3 feeders and phases."""
    partitioner = DatasetPartitioner()
    meters = partitioner.select_held_out_meters()
    assert len(meters) == 10
    assert len(set(meters)) == 10
    assert meters == HELD_OUT_METERS

    reg = partitioner.loader.load_meter_registry()
    held_df = reg[reg["meter_id"].isin(meters)]
    assert set(held_df["feeder_id"]) == {"feeder_01", "feeder_02", "feeder_03"}
    assert set(held_df["phase"]) == {"L1", "L2", "L3"}


def test_splits_manifest_counts(partitioner_manifest):
    """Verify manifest records exact expected row counts and zero loss."""
    manifest, _ = partitioner_manifest

    assert SPLITS_MANIFEST_PATH.exists()
    assert manifest["total_records"] == 504000
    assert manifest["meters"]["held_out_meters_count"] == 10
    assert manifest["meters"]["training_meters_count"] == 40

    counts = manifest["split_counts"]
    assert counts["train"] == 288000
    assert counts["val"] == 57600
    assert counts["test_temporal"] == 57600
    assert counts["test_spatial"] == 100800
    assert sum(counts.values()) == 504000


def test_rule_based_loader_split_row_counts():
    """Verify NeighborhoodDataLoader.load_split correctly returns exact row counts via in-memory rules."""
    loader = NeighborhoodDataLoader()

    df_train = loader.load_split("train", domain_names=["communications"])
    assert len(df_train) == 288000
    assert not df_train["meter_id"].isin(set(HELD_OUT_METERS)).any()
    assert (df_train["event_timestamp"] < VAL_CUTOFF_TIMESTAMP).all()

    df_val = loader.load_split("val", domain_names=["communications"])
    assert len(df_val) == 57600
    assert not df_val["meter_id"].isin(set(HELD_OUT_METERS)).any()
    assert (df_val["event_timestamp"] >= VAL_CUTOFF_TIMESTAMP).all()
    assert (df_val["event_timestamp"] < TEST_CUTOFF_TIMESTAMP).all()

    df_test_temp = loader.load_split("test_temporal", domain_names=["communications"])
    assert len(df_test_temp) == 57600
    assert not df_test_temp["meter_id"].isin(set(HELD_OUT_METERS)).any()
    assert (df_test_temp["event_timestamp"] >= TEST_CUTOFF_TIMESTAMP).all()

    df_test_spat = loader.load_split("test_spatial", domain_names=["communications"])
    assert len(df_test_spat) == 100800
    assert set(df_test_spat["meter_id"].unique()) == set(HELD_OUT_METERS)


def test_zero_leakage_between_train_and_test():
    """Verify strictly zero overlap between train and test_spatial meters, and zero temporal lookahead."""
    loader = NeighborhoodDataLoader()
    df_train = loader.load_split("train", domain_names=["communications"])
    df_val = loader.load_split("val", domain_names=["communications"])
    df_test_t = loader.load_split("test_temporal", domain_names=["communications"])
    df_test_s = loader.load_split("test_spatial", domain_names=["communications"])

    # Spatial isolation: held-out meters NEVER appear in train or val
    train_meters = set(df_train["meter_id"])
    spatial_meters = set(df_test_s["meter_id"])
    assert len(train_meters.intersection(spatial_meters)) == 0

    # Temporal isolation: train timestamps strictly precede val and test_temporal
    assert df_train["event_timestamp"].max() < df_val["event_timestamp"].min()
    assert df_val["event_timestamp"].max() < df_test_t["event_timestamp"].min()


def test_processed_parquet_matrices_and_dual_targets(partitioner_manifest):
    """Verify all 4 Parquet matrices exist with correct columns, dual targets, and non-empty features."""
    _, parquet_paths = partitioner_manifest
    assert len(parquet_paths) == 4

    loader = NeighborhoodDataLoader()
    for sp in ["train", "val", "test_temporal", "test_spatial"]:
        df_p = loader.load_processed_split(sp)
        assert len(df_p) > 0
        assert "label_25" in df_p.columns
        assert "label_tier1" in df_p.columns
        assert "derived_load_kW" in df_p.columns
        assert "derived_power_factor" in df_p.columns
        assert "residual_voltage_V" in df_p.columns
        assert "residual_power_kW" in df_p.columns
        assert "voltage_roll_mean_15m" in df_p.columns

        # Verify no unknown tier1 labels
        assert not (df_p["label_tier1"] == "UNKNOWN").any()

    assert FEATURE_MANIFEST_PATH.exists()
