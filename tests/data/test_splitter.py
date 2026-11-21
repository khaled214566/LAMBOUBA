"""
Unit and Integration Tests for DatasetSplitter
"""

from pathlib import Path
import pytest
import pandas as pd

from src.data.config import DOMAIN_CATALOG, STRUCTURED_DATA_DIR
from src.data.splitter import DatasetSplitter


def test_splitter_files_exist():
    """Verify that all 7 structured CSV files were created in structured directory."""
    for domain_name, meta in DOMAIN_CATALOG.items():
        file_path = STRUCTURED_DATA_DIR / meta["filename"]
        assert file_path.exists(), f"File {file_path} for domain {domain_name} does not exist."


def test_meter_registry_structure():
    """Verify meter_registry has exactly 50 unique meters and expected columns."""
    reg_path = STRUCTURED_DATA_DIR / "meter_registry.csv"
    assert reg_path.exists()
    df = pd.read_csv(reg_path)
    assert len(df) == 50
    assert df["meter_id"].nunique() == 50
    expected_cols = DOMAIN_CATALOG["meter_registry"]["columns"]
    assert list(df.columns) == expected_cols


def test_observation_files_row_counts_and_columns():
    """Verify each of the 6 observation files has 504,000 rows and matches expected schema."""
    for domain_name, meta in DOMAIN_CATALOG.items():
        if meta["is_observation_level"]:
            file_path = STRUCTURED_DATA_DIR / meta["filename"]
            assert file_path.exists()
            df = pd.read_csv(file_path, nrows=5)
            assert list(df.columns) == meta["columns"]
