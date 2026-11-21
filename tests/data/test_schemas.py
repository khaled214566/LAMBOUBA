"""
Unit and Integration Tests for YAML Schemas
"""

from pathlib import Path
import pytest
import yaml

from src.data.config import DOMAIN_CATALOG, PROJECT_ROOT
from src.data.schema_loader import SchemaLoader, get_all_schemas, get_relationships, get_version_info

SCHEMAS_DIR = PROJECT_ROOT / "schemas"


def test_schema_files_exist():
    """Verify that all 7 domain schemas, relationships, and version files exist."""
    expected_files = [
        "schema_version.yaml",
        "relationships.yaml",
        "meter_registry.schema.yaml",
        "energy_registers.schema.yaml",
        "electrical_measurements.schema.yaml",
        "meter_events.schema.yaml",
        "device_status.schema.yaml",
        "communications.schema.yaml",
        "labels.schema.yaml",
    ]
    for filename in expected_files:
        p = SCHEMAS_DIR / filename
        assert p.exists(), f"Expected schema file {p} does not exist."


def test_schema_loader_load_all():
    """Verify SchemaLoader successfully parses all 7 domain schemas with valid metadata."""
    loader = SchemaLoader()
    schemas = loader.load_all_schemas()
    assert len(schemas) == 7

    for name, schema in schemas.items():
        assert "schema_name" in schema
        assert "schema_version" in schema
        assert "description" in schema
        assert "owner" in schema
        assert "primary_key" in schema
        assert "fields" in schema
        assert len(schema["fields"]) > 0


def test_schema_columns_match_domain_catalog():
    """Verify that columns in YAML schemas match columns in DOMAIN_CATALOG exactly."""
    loader = SchemaLoader()
    for domain_name, meta in DOMAIN_CATALOG.items():
        schema = loader.load_schema(domain_name)
        schema_fields = list(schema["fields"].keys())
        expected_cols = meta["columns"]
        assert schema_fields == expected_cols, (
            f"Schema fields for '{domain_name}' do not match DOMAIN_CATALOG: "
            f"{schema_fields} != {expected_cols}"
        )


def test_relationships_and_version_syntax():
    """Verify relationships.yaml and schema_version.yaml syntax and mandatory fields."""
    rel = get_relationships()
    assert "version" in rel
    assert "primary_keys" in rel
    assert "foreign_keys" in rel
    assert "quarantine_rules" in rel

    ver = get_version_info()
    assert "version" in ver
    assert "semver_policy" in ver
    assert "domains" in ver
    assert len(ver["domains"]) == 7
