"""
EnergyMind Tunisia — Schema Loader Module
=========================================
Authoritative loader and cache for centralized YAML schemas, data contracts,
relationships, and schema versioning.
"""

from functools import lru_cache
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional
import yaml

from src.data.config import PROJECT_ROOT

logger = logging.getLogger(__name__)

SCHEMAS_DIR = PROJECT_ROOT / "schemas"


class SchemaNotFoundError(Exception):
    """Raised when a requested domain schema YAML file does not exist."""
    pass


class SchemaLoader:
    """
    Centralized loader for domain YAML contracts and relationships.
    Caches parsed schemas in memory.
    """

    def __init__(self, schemas_dir: Optional[Path] = None):
        self.schemas_dir = Path(schemas_dir) if schemas_dir is not None else SCHEMAS_DIR
        if not self.schemas_dir.exists():
            raise FileNotFoundError(f"Schemas directory not found at {self.schemas_dir}")

    @lru_cache(maxsize=32)
    def load_schema(self, domain_name: str) -> Dict[str, Any]:
        """
        Loads and returns the YAML schema definition for a specific domain.

        Parameters
        ----------
        domain_name : str
            Name of domain (e.g. 'electrical_measurements', 'meter_registry')

        Returns
        -------
        Dict[str, Any]
            Parsed schema dictionary.
        """
        # Handle filename variations (.schema.yaml)
        candidate = self.schemas_dir / f"{domain_name}.schema.yaml"
        if not candidate.exists():
            candidate = self.schemas_dir / f"{domain_name}.yaml"
            if not candidate.exists():
                raise SchemaNotFoundError(
                    f"No schema found for '{domain_name}' in {self.schemas_dir}. "
                    f"Expected {domain_name}.schema.yaml"
                )

        with open(candidate, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)

    def load_all_schemas(self) -> Dict[str, Dict[str, Any]]:
        """
        Loads all 7 domain schemas into a dictionary keyed by schema_name.
        """
        schemas = {}
        for yml_path in self.schemas_dir.glob("*.schema.yaml"):
            with open(yml_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
                name = data.get("schema_name", yml_path.stem.replace(".schema", ""))
                schemas[name] = data
        return schemas

    @lru_cache(maxsize=1)
    def get_relationships(self) -> Dict[str, Any]:
        """Loads relationships.yaml."""
        rel_file = self.schemas_dir / "relationships.yaml"
        if not rel_file.exists():
            raise FileNotFoundError(f"Relationships contract not found at {rel_file}")
        with open(rel_file, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)

    @lru_cache(maxsize=1)
    def get_version_info(self) -> Dict[str, Any]:
        """Loads schema_version.yaml."""
        ver_file = self.schemas_dir / "schema_version.yaml"
        if not ver_file.exists():
            raise FileNotFoundError(f"Schema version file not found at {ver_file}")
        with open(ver_file, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)

    def list_domains(self) -> List[str]:
        """Returns list of domain names found in schemas directory."""
        return sorted([
            p.stem.replace(".schema", "") for p in self.schemas_dir.glob("*.schema.yaml")
        ])

    def get_field_definition(self, domain_name: str, field_name: str) -> Optional[Dict[str, Any]]:
        """Returns the specific field contract dictionary for a given domain and column."""
        schema = self.load_schema(domain_name)
        return schema.get("fields", {}).get(field_name)


# Global default instance
_default_loader = SchemaLoader()

def get_schema(domain_name: str) -> Dict[str, Any]:
    """Helper function to load a schema."""
    return _default_loader.load_schema(domain_name)

def get_all_schemas() -> Dict[str, Dict[str, Any]]:
    """Helper function to load all schemas."""
    return _default_loader.load_all_schemas()

def get_relationships() -> Dict[str, Any]:
    """Helper function to load relationships."""
    return _default_loader.get_relationships()

def get_version_info() -> Dict[str, Any]:
    """Helper function to load schema version info."""
    return _default_loader.get_version_info()
