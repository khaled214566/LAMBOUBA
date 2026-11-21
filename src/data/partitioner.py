"""
EnergyMind Tunisia — Dataset Partitioner
========================================
Implements the spatio-temporal hybrid partitioning architecture:
1. 10 meters held out via topological stratification -> test_spatial (100,800 rows)
2. 40 meters split chronologically:
   - Days 1–5: train (288,000 rows)
   - Day 6: val (57,600 rows)
   - Day 7: test_temporal (57,600 rows)

Generates:
- data/realistic/splits/splits_manifest.json
- data/realistic/splits/split_index.csv
- data/realistic/processed/*.parquet (ML-ready feature matrices with dual targets)
- data/realistic/processed/feature_manifest.json
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from src.data.config import (
    DOMAIN_CATALOG,
    FEATURE_MANIFEST_PATH,
    HELD_OUT_METERS,
    PROCESSED_DATA_DIR,
    SPLITS_DIR,
    SPLITS_MANIFEST_PATH,
    STRUCTURED_DATA_DIR,
    TEST_CUTOFF_TIMESTAMP,
    TIER1_TARGET_MAP,
    VAL_CUTOFF_TIMESTAMP,
)
from src.data.loader import NeighborhoodDataLoader

logger = logging.getLogger(__name__)


class DatasetPartitioner:
    """
    Orchestrates leak-free spatio-temporal partitioning across the 504,000 observations.
    """

    def __init__(
        self,
        structured_dir: Optional[Path] = None,
        splits_dir: Optional[Path] = None,
        processed_dir: Optional[Path] = None,
    ):
        self.structured_dir = Path(structured_dir) if structured_dir is not None else STRUCTURED_DATA_DIR
        self.splits_dir = Path(splits_dir) if splits_dir is not None else SPLITS_DIR
        self.processed_dir = Path(processed_dir) if processed_dir is not None else PROCESSED_DATA_DIR

        self.splits_dir.mkdir(parents=True, exist_ok=True)
        self.processed_dir.mkdir(parents=True, exist_ok=True)
        self.loader = NeighborhoodDataLoader(self.structured_dir)

    def select_held_out_meters(self) -> List[str]:
        """
        Selects exactly 10 meters stratified across all 3 feeders, 3 phases, and distance ranges:
        - feeder_01 (Phase L1, small_flat): 3 meters (near, mid, far)
        - feeder_02 (Phase L2, family_home): 4 meters (near, 2 mid, far)
        - feeder_03 (Phase L3, high_usage_home): 3 meters (near, mid, far)
        """
        reg = self.loader.load_meter_registry()
        held_out: List[str] = []

        # Allocation per feeder
        targets = {
            "feeder_01": [0.15, 0.50, 0.85],           # 3 meters
            "feeder_02": [0.10, 0.40, 0.70, 0.90],     # 4 meters
            "feeder_03": [0.15, 0.50, 0.85],           # 3 meters
        }

        for feeder, quantiles in targets.items():
            f_df = reg[reg["feeder_id"] == feeder].sort_values("distance_from_transformer_m").reset_index(drop=True)
            n_meters = len(f_df)
            selected_indices = set()
            for q in quantiles:
                idx = min(int(round(q * (n_meters - 1))), n_meters - 1)
                # Ensure no duplicates if n_meters is small
                while idx in selected_indices and idx < n_meters - 1:
                    idx += 1
                while idx in selected_indices and idx > 0:
                    idx -= 1
                selected_indices.add(idx)
                held_out.append(f_df.iloc[idx]["meter_id"])

        logger.info(f"Selected 10 stratified held-out meters: {held_out}")
        return sorted(held_out)

    def generate_splits_manifest(self) -> Dict[str, Any]:
        """
        Builds and saves splits_manifest.json with zero redundant index file overhead.
        """
        logger.info("Generating splits manifest...")
        held_out_meters = HELD_OUT_METERS
        spatial_set = set(held_out_meters)

        # Load reference timestamps and meter IDs
        comm_meta = DOMAIN_CATALOG["communications"]
        df_obs = pd.read_csv(
            self.structured_dir / comm_meta["filename"],
            usecols=["record_id", "meter_id", "event_timestamp"],
            low_memory=False,
        )

        conditions = [
            df_obs["meter_id"].isin(spatial_set),
            (~df_obs["meter_id"].isin(spatial_set)) & (df_obs["event_timestamp"] < VAL_CUTOFF_TIMESTAMP),
            (~df_obs["meter_id"].isin(spatial_set))
            & (df_obs["event_timestamp"] >= VAL_CUTOFF_TIMESTAMP)
            & (df_obs["event_timestamp"] < TEST_CUTOFF_TIMESTAMP),
            (~df_obs["meter_id"].isin(spatial_set)) & (df_obs["event_timestamp"] >= TEST_CUTOFF_TIMESTAMP),
        ]
        choices = ["test_spatial", "train", "val", "test_temporal"]

        df_obs["split"] = np.select(conditions, choices, default="unknown")
        counts = df_obs["split"].value_counts().to_dict()

        all_meters = sorted(df_obs["meter_id"].unique().tolist())
        train_meters = sorted(list(set(all_meters) - spatial_set))

        manifest = {
            "version": "1.0.0",
            "created_at": "2026-11-21",
            "strategy": "spatio-temporal-hybrid",
            "total_records": len(df_obs),
            "split_counts": counts,
            "meters": {
                "total_count": len(all_meters),
                "training_meters_count": len(train_meters),
                "held_out_meters_count": len(held_out_meters),
                "training_meters": train_meters,
                "held_out_meters": held_out_meters,
            },
            "temporal_cutoffs": {
                "val_start": VAL_CUTOFF_TIMESTAMP,
                "test_start": TEST_CUTOFF_TIMESTAMP,
            },
            "split_descriptions": {
                "train": "Days 1-5 (Nov 13-17) across 40 meters. Used for training and baseline learning.",
                "val": "Day 6 (Nov 18) across 40 meters. Used for early stopping and threshold tuning.",
                "test_temporal": "Day 7 (Nov 19) across 40 meters. Tests forward-time detection on known meters.",
                "test_spatial": "Days 1-7 (Nov 13-19) across 10 unseen held-out meters. Tests zero-shot generalization.",
            },
        }

        with open(SPLITS_MANIFEST_PATH, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)
        logger.info(f"Saved splits manifest to {SPLITS_MANIFEST_PATH}")

        return manifest

    def build_processed_ml_matrices(self) -> Dict[str, Path]:
        """
        Extracts full physics-informed feature set and dual target labels,
        then partitions and exports compressed Parquet datasets into data/realistic/processed/.
        """
        logger.info("Loading unified observation dataset for feature processing...")

        # Load all domains
        df_all = self.loader.load_domains(
            domain_names=[
                "energy_registers",
                "electrical_measurements",
                "meter_events",
                "device_status",
                "communications",
                "labels",
            ],
            include_registry=True,
        )

        logger.info("Computing physics-informed electrical features...")
        # Sort deterministically by meter_id and event_timestamp/record_id
        df_all = df_all.sort_values(["meter_id", "record_id"]).reset_index(drop=True)
        grp = df_all.groupby("meter_id")

        # 1. Active & Reactive Power deltas (1-minute cadence -> * 60)
        delta_p = grp["active_import_kWh"].diff().clip(lower=0.0).fillna(0.0)
        df_all["derived_load_kW"] = delta_p * 60.0

        delta_export = grp["active_export_kWh"].diff().clip(lower=0.0).fillna(0.0)
        df_all["derived_export_kW"] = delta_export * 60.0

        q_sum = (
            df_all["reactive_Q1_kvarh"]
            + df_all["reactive_Q2_kvarh"]
            + df_all["reactive_Q3_kvarh"]
            + df_all["reactive_Q4_kvarh"]
        )
        df_all["reactive_total_kvarh"] = q_sum
        delta_q = grp["reactive_total_kvarh"].diff().clip(lower=0.0).fillna(0.0)
        df_all["derived_reactive_kvar"] = delta_q * 60.0

        # Apparent power & Power Factor
        df_all["derived_apparent_kVA"] = np.sqrt(
            df_all["derived_load_kW"] ** 2 + df_all["derived_reactive_kvar"] ** 2
        )
        df_all["derived_power_factor"] = np.where(
            df_all["derived_apparent_kVA"] > 1e-4,
            df_all["derived_load_kW"] / df_all["derived_apparent_kVA"],
            1.0,
        ).clip(0.0, 1.0)

        # 2. Derived Phase Current & Neutral Imbalance Ratio
        denom = df_all["voltage_V"].fillna(230.0) * df_all["derived_power_factor"]
        df_all["derived_phase_current_A"] = np.where(
            denom > 1.0,
            (df_all["derived_load_kW"] * 1000.0) / denom,
            0.0,
        )
        df_all["neutral_imbalance_ratio"] = df_all["neutral_current_A"].fillna(0.0) / np.maximum(
            df_all["derived_phase_current_A"], 0.1
        )

        # 3. Physical Residuals
        # Radial line drop estimation: V_drop = (distance * 0.0003) * I_phase
        approx_v_drop = (df_all["distance_from_transformer_m"] * 0.0003) * df_all["derived_phase_current_A"]
        expected_v = 230.0 - approx_v_drop
        df_all["residual_voltage_V"] = df_all["voltage_V"].fillna(230.0) - expected_v

        # Apparent power balance residual
        apparent_calc = (df_all["voltage_V"].fillna(230.0) * df_all["derived_phase_current_A"]) / 1000.0
        df_all["residual_power_kW"] = df_all["derived_load_kW"] - apparent_calc

        # 4. Multi-Scale 15-Minute Rolling Stats (15 observations per meter)
        df_all["voltage_roll_mean_15m"] = (
            grp["voltage_V"].rolling(window=15, min_periods=1).mean().reset_index(drop=True)
        )
        df_all["voltage_roll_std_15m"] = (
            grp["voltage_V"].rolling(window=15, min_periods=1).std().fillna(0.0).reset_index(drop=True)
        )
        df_all["load_roll_mean_15m"] = (
            grp["derived_load_kW"].rolling(window=15, min_periods=1).mean().reset_index(drop=True)
        )
        df_all["load_roll_std_15m"] = (
            grp["derived_load_kW"].rolling(window=15, min_periods=1).std().fillna(0.0).reset_index(drop=True)
        )

        # 5. Cyclic Time & Latency
        ts = pd.to_datetime(df_all["event_timestamp"], format="ISO8601")
        hour_frac = ts.dt.hour + ts.dt.minute / 60.0
        df_all["sin_time"] = np.sin(2 * np.pi * hour_frac / 24.0)
        df_all["cos_time"] = np.cos(2 * np.pi * hour_frac / 24.0)
        df_all["day_of_week"] = ts.dt.dayofweek

        # Ingestion latency in seconds
        ts_ingest = pd.to_datetime(df_all["ingest_timestamp"], format="ISO8601")
        df_all["telecom_latency_s"] = (ts_ingest - ts).dt.total_seconds().clip(lower=0.0)

        # 6. Dual Target Labels
        df_all["label_25"] = df_all["label"]
        df_all["label_tier1"] = df_all["label"].map(TIER1_TARGET_MAP).fillna("UNKNOWN")

        # 7. Direct Rule-Based Split Assignment (Zero CSV index overhead)
        spatial_set = set(HELD_OUT_METERS)
        conditions = [
            df_all["meter_id"].isin(spatial_set),
            (~df_all["meter_id"].isin(spatial_set)) & (df_all["event_timestamp"] < VAL_CUTOFF_TIMESTAMP),
            (~df_all["meter_id"].isin(spatial_set))
            & (df_all["event_timestamp"] >= VAL_CUTOFF_TIMESTAMP)
            & (df_all["event_timestamp"] < TEST_CUTOFF_TIMESTAMP),
            (~df_all["meter_id"].isin(spatial_set)) & (df_all["event_timestamp"] >= TEST_CUTOFF_TIMESTAMP),
        ]
        choices = ["test_spatial", "train", "val", "test_temporal"]
        df_all["split"] = np.select(conditions, choices, default="unknown")

        # Columns to export in ML processed datasets
        feature_columns = [
            "record_id",
            "meter_id",
            "event_timestamp",
            "feeder_id",
            "phase",
            "distance_from_transformer_m",
            "household_type",
            "voltage_V",
            "frequency_Hz",
            "neutral_current_A",
            "derived_load_kW",
            "derived_export_kW",
            "derived_reactive_kvar",
            "derived_apparent_kVA",
            "derived_power_factor",
            "derived_phase_current_A",
            "neutral_imbalance_ratio",
            "residual_voltage_V",
            "residual_power_kW",
            "voltage_roll_mean_15m",
            "voltage_roll_std_15m",
            "load_roll_mean_15m",
            "load_roll_std_15m",
            "telecom_latency_s",
            "sin_time",
            "cos_time",
            "day_of_week",
            "voltage_interruptions",
            "voltage_restorations",
            "power_factor_variation_detected",
            "magnetic_field_detected",
            "top_cover_opened",
            "terminal_cover_opened",
            "io_swap",
            "phase_neutral_swap",
            "mains_power_cut",
            "neutral_disturbance",
            "breaker_state",
            "auto_diagnostic",
            "quality_flags",
            "label_25",
            "label_tier1",
        ]

        # Export split files
        splits = ["train", "val", "test_temporal", "test_spatial"]
        results: Dict[str, Path] = {}

        for sp in splits:
            sp_df = df_all[df_all["split"] == sp][feature_columns].reset_index(drop=True)
            out_file = self.processed_dir / f"{sp}.parquet"
            sp_df.to_parquet(out_file, index=False)
            results[sp] = out_file
            logger.info(f"Exported {sp}: {len(sp_df)} rows to {out_file}")

        # Feature manifest
        manifest_meta = {
            "total_features": len(feature_columns) - 4,  # minus keys & targets
            "feature_columns": [c for c in feature_columns if c not in ["record_id", "meter_id", "event_timestamp", "label_25", "label_tier1"]],
            "target_columns": ["label_25", "label_tier1"],
            "tier1_classes": sorted(list(set(TIER1_TARGET_MAP.values()))),
            "tier2_classes_count": len(TIER1_TARGET_MAP),
        }
        with open(FEATURE_MANIFEST_PATH, "w", encoding="utf-8") as f:
            json.dump(manifest_meta, f, indent=2)

        return results


def run_partitioning() -> Tuple[Dict[str, Any], Dict[str, Path]]:
    """CLI / programmatic helper to run partitioner."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    partitioner = DatasetPartitioner()
    manifest = partitioner.generate_splits_manifest()
    parquet_paths = partitioner.build_processed_ml_matrices()
    return manifest, parquet_paths


if __name__ == "__main__":
    run_partitioning()
