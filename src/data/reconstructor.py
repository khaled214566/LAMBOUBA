"""
EnergyMind Tunisia — Dataset Reconstructor
===========================================
Reconstructs the original monolithic 33-column dataset from the 7 modular
domain CSV files with exact mathematical and value-by-value equivalence.
"""

import logging
from pathlib import Path
from typing import Optional

import pandas as pd

from src.data.config import (
    DOMAIN_CATALOG,
    METER_REGISTRY_COLUMNS,
    ORIGINAL_COLUMNS,
    STRUCTURED_DATA_DIR,
)

logger = logging.getLogger(__name__)


class DatasetReconstructor:
    """
    Reconstructs the original 504,000-row, 33-column neighborhood dataset
    from the 7 structured CSV files.
    """

    def __init__(self, structured_dir: Optional[Path] = None):
        """
        Initializes reconstructor with path to structured data directory.
        """
        self.structured_dir = (
            Path(structured_dir) if structured_dir is not None else STRUCTURED_DATA_DIR
        )
        if not self.structured_dir.exists():
            raise FileNotFoundError(
                f"Structured data directory does not exist: {self.structured_dir}"
            )

    def reconstruct(self) -> pd.DataFrame:
        """
        Deterministically merges the 7 CSV files to recreate the monolithic dataset.

        Returns
        -------
        pd.DataFrame
            Reconstructed DataFrame with all 33 original columns in exact sequence.
        """
        logger.info("Loading domain CSV files for deterministic reconstruction...")

        # Load meter registry
        reg_meta = DOMAIN_CATALOG["meter_registry"]
        reg_path = self.structured_dir / reg_meta["filename"]
        if not reg_path.exists():
            raise FileNotFoundError(f"Missing file: {reg_path}")
        df_registry = pd.read_csv(reg_path, low_memory=False)

        # Load observation-level files
        obs_domains = [
            "energy_registers",
            "electrical_measurements",
            "meter_events",
            "device_status",
            "communications",
            "labels",
        ]

        obs_dfs = {}
        for d in obs_domains:
            file_path = self.structured_dir / DOMAIN_CATALOG[d]["filename"]
            if not file_path.exists():
                raise FileNotFoundError(f"Missing domain file: {file_path}")
            obs_dfs[d] = pd.read_csv(file_path, low_memory=False)

        # Start merge with energy_registers as anchor
        base_df = obs_dfs["energy_registers"].copy()

        # Successively merge remaining observation domains on 'record_id'
        for d in obs_domains[1:]:
            df = obs_dfs[d]
            # Identify columns unique to this domain (excluding shared keys record_id, meter_id, event_timestamp)
            shared_keys = {"record_id", "meter_id", "event_timestamp"}
            unique_cols = [c for c in df.columns if c not in shared_keys]
            merge_cols = ["record_id"] + unique_cols

            base_df = base_df.merge(df[merge_cols], on="record_id", how="inner")

        # Merge meter_registry metadata on 'meter_id'
        # Unique registry columns (excluding meter_id)
        reg_unique = [c for c in METER_REGISTRY_COLUMNS if c != "meter_id"]
        reconstructed = base_df.merge(
            df_registry[["meter_id"] + reg_unique], on="meter_id", how="left"
        )

        # Enforce exact original column ordering
        reconstructed = reconstructed[ORIGINAL_COLUMNS]

        # Sort deterministically by record_id
        reconstructed = reconstructed.sort_values("record_id").reset_index(drop=True)

        logger.info(
            f"Reconstruction complete: {len(reconstructed)} rows, {len(reconstructed.columns)} columns."
        )
        return reconstructed

    def save(self, output_path: Path) -> Path:
        """
        Reconstructs and saves the dataset to specified path.
        """
        df = self.reconstruct()
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(out, index=False)
        logger.info(f"Saved reconstructed dataset to {out}")
        return out


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    reconstructor = DatasetReconstructor()
    df_recon = reconstructor.reconstruct()
    print("Reconstructed shape:", df_recon.shape)
