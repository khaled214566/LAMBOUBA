"""
Unit and Integration Tests for DatasetReconstructor
"""

import pytest
import pandas as pd

from src.data.config import ORIGINAL_COLUMNS
from src.data.reconstructor import DatasetReconstructor


def test_reconstruction_shape_and_columns():
    """Verify that reconstructed dataset has 504,000 rows and 33 columns in exact order."""
    reconstructor = DatasetReconstructor()
    df_recon = reconstructor.reconstruct()

    assert df_recon.shape == (504000, 33)
    assert list(df_recon.columns) == ORIGINAL_COLUMNS
    assert df_recon["record_id"].is_monotonic_increasing
