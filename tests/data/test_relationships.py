"""
Unit and Integration Tests for Cross-Domain Relationships
"""

import pandas as pd
import pytest

from src.data.config import STRUCTURED_DATA_DIR
from src.data.schema_loader import get_relationships


def test_relationships_contract_rules():
    """Verify cross-domain foreign key referential integrity from relationships.yaml."""
    rel = get_relationships()
    reg_df = pd.read_csv(STRUCTURED_DATA_DIR / "meter_registry.csv")
    registered_meters = set(reg_df["meter_id"])

    # Test each observation domain declared in relationships.yaml
    fk_spec = rel["foreign_keys"][0]
    source_domains = fk_spec["source_domains"]

    for domain in source_domains:
        csv_path = STRUCTURED_DATA_DIR / f"{domain}.csv"
        assert csv_path.exists()
        # Sample first 2000 rows
        obs_df = pd.read_csv(csv_path, nrows=2000, usecols=["meter_id", "record_id"])
        obs_meters = set(obs_df["meter_id"])
        orphans = obs_meters - registered_meters
        assert len(orphans) == 0, f"Domain {domain} has orphan meters: {orphans}"


def test_synchronous_record_id_alignment():
    """Verify record_id and event_timestamp alignment across observation domains."""
    elec_df = pd.read_csv(STRUCTURED_DATA_DIR / "electrical_measurements.csv", nrows=100)
    en_df = pd.read_csv(STRUCTURED_DATA_DIR / "energy_registers.csv", nrows=100)

    assert (elec_df["record_id"] == en_df["record_id"]).all()
    assert (elec_df["meter_id"] == en_df["meter_id"]).all()
    assert (elec_df["event_timestamp"] == en_df["event_timestamp"]).all()
