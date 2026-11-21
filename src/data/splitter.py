"""
EnergyMind Tunisia — Dataset Splitter
=====================================
Transforms the monolithic 33-column neighborhood CSV into 7 domain-specific
modular CSV files adhering strictly to STEG / Sagemcom MS212 data specifications.
"""

import logging
from pathlib import Path
from typing import Dict, Optional

import pandas as pd

from src.data.config import (
    DOMAIN_CATALOG,
    FALLBACK_RAW_CSV,
    METER_REGISTRY_COLUMNS,
    ORIGINAL_COLUMNS,
    PRIMARY_RAW_CSV,
    STRUCTURED_DATA_DIR,
)

logger = logging.getLogger(__name__)


class DatasetSplitter:
    """
    Splits monolithic neighborhood dataset into 7 domain-specific CSV files:
    1. meter_registry.csv (static metadata, 1 row per meter)
    2. energy_registers.csv (observation-level energy measurements)
    3. electrical_measurements.csv (observation-level electrical parameters)
    4. meter_events.csv (observation-level tamper/fault flags)
    5. device_status.csv (observation-level diagnostics and relays)
    6. communications.csv (observation-level transmission telemetry)
    7. labels.csv (ground-truth classification targets)
    """

    def __init__(
        self,
        raw_csv_path: Optional[Path] = None,
        output_dir: Optional[Path] = None,
    ):
        """
        Initializes splitter with source raw CSV path and target structured directory.
        """
        if raw_csv_path is not None:
            self.raw_csv_path = Path(raw_csv_path)
        elif PRIMARY_RAW_CSV.exists():
            self.raw_csv_path = PRIMARY_RAW_CSV
        elif FALLBACK_RAW_CSV.exists():
            self.raw_csv_path = FALLBACK_RAW_CSV
        else:
            raise FileNotFoundError(
                f"Raw dataset not found at {PRIMARY_RAW_CSV} or {FALLBACK_RAW_CSV}"
            )

        self.output_dir = Path(output_dir) if output_dir is not None else STRUCTURED_DATA_DIR
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def split(self, chunksize: Optional[int] = None) -> Dict[str, Path]:
        """
        Splits the raw dataset into the 7 domain files.

        Parameters
        ----------
        chunksize : int, optional
            If provided, processes file in streaming chunks (useful for low memory).
            Defaults to None (in-memory processing for 504k rows).

        Returns
        -------
        Dict[str, Path]
            Mapping of domain name to created CSV file path.
        """
        logger.info(f"Loading raw dataset from {self.raw_csv_path}...")
        df_raw = pd.read_csv(self.raw_csv_path, low_memory=False)

        # Validate presence of all 33 established columns
        missing_cols = set(ORIGINAL_COLUMNS) - set(df_raw.columns)
        if missing_cols:
            raise ValueError(f"Raw dataset is missing expected columns: {missing_cols}")

        results: Dict[str, Path] = {}

        # 1. Generate meter_registry.csv (1 record per meter)
        logger.info("Extracting meter_registry...")
        registry_df = df_raw[METER_REGISTRY_COLUMNS].drop_duplicates(subset=["meter_id"])
        registry_path = self.output_dir / DOMAIN_CATALOG["meter_registry"]["filename"]
        registry_df.to_csv(registry_path, index=False)
        results["meter_registry"] = registry_path
        logger.info(f"Saved meter_registry: {len(registry_df)} meters to {registry_path}")

        # 2. Generate the 6 observation-level files
        observation_domains = [
            d for d, meta in DOMAIN_CATALOG.items() if meta["is_observation_level"]
        ]

        for domain in observation_domains:
            meta = DOMAIN_CATALOG[domain]
            cols = meta["columns"]
            out_file = self.output_dir / meta["filename"]

            logger.info(f"Extracting domain '{domain}' ({len(cols)} columns)...")
            domain_df = df_raw[cols]
            domain_df.to_csv(out_file, index=False)
            results[domain] = out_file
            logger.info(f"Saved {domain}: {len(domain_df)} rows to {out_file}")

        logger.info(f"Dataset successfully split into {len(results)} files in {self.output_dir}")
        return results


def run_split() -> Dict[str, Path]:
    """CLI / programmatic helper to run splitter."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    splitter = DatasetSplitter()
    return splitter.split()


if __name__ == "__main__":
    run_split()
