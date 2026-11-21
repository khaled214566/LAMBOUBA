"""
EnergyMind Tunisia — Feature Engineering Module
===============================================
Extracts physical, statistical, and domain-informed electrical features
ONLY when explicitly requested by downstream ML pipelines.
"""

import logging
from typing import Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class FeatureEngineer:
    """
    Computes domain-specific electrical features without modifying the raw established schema:
    - Active power estimate: P_kW = delta(active_import_kWh) * 60
    - Export power estimate: P_export_kW = delta(active_export_kWh) * 60
    - Reactive power estimate: Q_kvar = delta(sum(Q1..Q4)) * 60
    - Apparent power: S_kVA = sqrt(P^2 + Q^2)
    - Power factor: cos_phi = P / S
    - Physical residual: r_P = P - (V * I_phase * cos_phi)
    - Voltage deviation: delta_V = V - 230.0
    - Rolling 15-minute moving stats (mean, std) for voltage & power
    """

    @staticmethod
    def extract_electrical_features(df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculates physical electrical features from energy and electrical measurement data.
        Requires active_import_kWh and voltage_V to be present.
        """
        feat_df = df.copy()

        # Sort per meter by timestamp/record_id to compute deltas
        if "meter_id" in feat_df.columns:
            feat_df = feat_df.sort_values(["meter_id", "record_id"]).reset_index(drop=True)
            group = feat_df.groupby("meter_id")
        else:
            feat_df = feat_df.sort_values("record_id").reset_index(drop=True)
            group = feat_df

        # 1. Active power from energy register deltas (1-minute sampling -> * 60)
        if "active_import_kWh" in feat_df.columns:
            if "meter_id" in feat_df.columns:
                delta_e = group["active_import_kWh"].diff().clip(lower=0.0).fillna(0.0)
            else:
                delta_e = feat_df["active_import_kWh"].diff().clip(lower=0.0).fillna(0.0)
            feat_df["active_power_kW"] = delta_e * 60.0

        # 2. Voltage deviation from STEG nominal (230 V)
        if "voltage_V" in feat_df.columns:
            feat_df["voltage_deviation_V"] = feat_df["voltage_V"] - 230.0
            feat_df["voltage_pu"] = feat_df["voltage_V"] / 230.0

        # 3. Reactive energy sum
        reactive_cols = [
            c for c in ["reactive_Q1_kvarh", "reactive_Q2_kvarh", "reactive_Q3_kvarh", "reactive_Q4_kvarh"]
            if c in feat_df.columns
        ]
        if reactive_cols:
            feat_df["reactive_total_kvarh"] = feat_df[reactive_cols].sum(axis=1)
            if "meter_id" in feat_df.columns:
                delta_q = group["reactive_total_kvarh"].diff().clip(lower=0.0).fillna(0.0)
            else:
                delta_q = feat_df["reactive_total_kvarh"].diff().clip(lower=0.0).fillna(0.0)
            feat_df["reactive_power_kvar"] = delta_q * 60.0

        # 4. Apparent power and Power Factor
        if "active_power_kW" in feat_df.columns and "reactive_power_kvar" in feat_df.columns:
            feat_df["apparent_power_kVA"] = np.sqrt(
                feat_df["active_power_kW"] ** 2 + feat_df["reactive_power_kvar"] ** 2
            )
            # Safe division
            feat_df["derived_power_factor"] = np.where(
                feat_df["apparent_power_kVA"] > 1e-4,
                feat_df["active_power_kW"] / feat_df["apparent_power_kVA"],
                1.0,
            ).clip(0.0, 1.0)

        # 5. Phase current estimate: I = P / (V * cos_phi)
        if (
            "active_power_kW" in feat_df.columns
            and "voltage_V" in feat_df.columns
            and "derived_power_factor" in feat_df.columns
        ):
            denom = feat_df["voltage_V"] * feat_df["derived_power_factor"]
            feat_df["derived_phase_current_A"] = np.where(
                denom > 1.0,
                (feat_df["active_power_kW"] * 1000.0) / denom,
                0.0,
            )

        # 6. Neutral current imbalance ratio: I_N / max(I_phase, 0.1)
        if "neutral_current_A" in feat_df.columns and "derived_phase_current_A" in feat_df.columns:
            feat_df["neutral_imbalance_ratio"] = feat_df["neutral_current_A"] / np.maximum(
                feat_df["derived_phase_current_A"], 0.1
            )

        # 7. 15-minute rolling statistics (15 rows per meter)
        if "voltage_V" in feat_df.columns and "meter_id" in feat_df.columns:
            feat_df["voltage_rolling_mean_15m"] = (
                group["voltage_V"].rolling(window=15, min_periods=1).mean().reset_index(drop=True)
            )
            feat_df["voltage_rolling_std_15m"] = (
                group["voltage_V"].rolling(window=15, min_periods=1).std().fillna(0.0).reset_index(drop=True)
            )

        return feat_df
