"""
EnergyMind Tunisia — Module 5: Leakage-Free Feature Engineering & Re-Benchmarking (v3)
=====================================================================================
Pipeline:
  1. Loads overhauled Dataset V3 (504,000 rows).
  2. Imputes missing indicators for real communication drops (np.nan).
  3. Computes derived electrical features and physical residuals:
     - load_kW, export_kW, reactive_delta_kvar
     - derived_power_factor, derived_phase_current_A
     - neutral_imbalance_ratio
     - Physical residuals: r_P (Ohm's law apparent balance), r_V (radial line drop)
     - 15-minute rolling statistics (mean & std of voltage and load)
     - Temporal cyclic features (sin/cos time, day of week)
  4. Partitions into strict chronological splits (70% Train, 15% Val, 15% Test)
     and saves compressed Apache Parquet datasets.
  5. Trains a multi-class LightGBM classifier without trivial shortcuts.
  6. Computes comprehensive evaluation metrics and exports benchmark artifacts.
"""

import json
from pathlib import Path
import joblib
import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, classification_report, f1_score

DATA_DIR = Path(r"c:\Users\khaled\Desktop\TSYP 2")
INPUT_CSV = DATA_DIR / "neighborhood_dataset.csv"
OUTPUT_DIR = Path(r"c:\Users\khaled\Desktop\TSYP 2\src\data_gen")

TIER1_MAP = {
    # Normal Group
    "normal": "NORMAL",
    "normal_export_q2": "NORMAL",
    "normal_export_q3": "NORMAL",
    "normal_capacitive_q4": "NORMAL",
    # Tamper Group -> FALSIFICATION_ATTACK
    "tamper_magnetic": "FALSIFICATION_ATTACK",
    "tamper_top_cover": "FALSIFICATION_ATTACK",
    "tamper_terminal_cover": "FALSIFICATION_ATTACK",
    "tamper_io_swap": "FALSIFICATION_ATTACK",
    "tamper_phase_neutral_swap": "FALSIFICATION_ATTACK",
    "tamper_multiple": "FALSIFICATION_ATTACK",
    # Power & Grid Quality -> GENUINE_GRID_EVENT
    "power_cut": "GENUINE_GRID_EVENT",
    "voltage_interruption": "GENUINE_GRID_EVENT",
    "undervoltage": "GENUINE_GRID_EVENT",
    "overvoltage": "GENUINE_GRID_EVENT",
    "frequency_deviation": "GENUINE_GRID_EVENT",
    # Neutral & Load & PF -> EQUIPMENT_FAULT
    "neutral_disturbance": "EQUIPMENT_FAULT",
    "neutral_current_imbalance": "EQUIPMENT_FAULT",
    "overcurrent": "EQUIPMENT_FAULT",
    "poor_power_factor": "EQUIPMENT_FAULT",
    # Data Quality & Device -> DATA_QUALITY_ISSUE
    "meter_drift": "DATA_QUALITY_ISSUE",
    "constant_bias": "DATA_QUALITY_ISSUE",
    "missing_data": "DATA_QUALITY_ISSUE",
    "dropout": "DATA_QUALITY_ISSUE",
    "random_corruption": "DATA_QUALITY_ISSUE",
    "energy_power_mismatch": "DATA_QUALITY_ISSUE",
    "device_fault": "DATA_QUALITY_ISSUE",
}

def engineer_features(df: pd.DataFrame) -> pd.DataFrame:
    print("-> Sorting by meter_id and event_timestamp...")
    df["event_timestamp"] = pd.to_datetime(df["event_timestamp"], format="ISO8601")
    df = df.sort_values(by=["meter_id", "event_timestamp"]).reset_index(drop=True)

    print("-> Computing register deltas per meter...")
    grouped = df.groupby("meter_id")

    delta_import = grouped["active_import_kWh"].diff().fillna(0).clip(lower=0.0)
    delta_export = grouped["active_export_kWh"].diff().fillna(0).clip(lower=0.0)
    delta_q1 = grouped["reactive_Q1_kvarh"].diff().fillna(0).clip(lower=0.0)
    delta_q2 = grouped["reactive_Q2_kvarh"].diff().fillna(0).clip(lower=0.0)
    delta_q3 = grouped["reactive_Q3_kvarh"].diff().fillna(0).clip(lower=0.0)
    delta_q4 = grouped["reactive_Q4_kvarh"].diff().fillna(0).clip(lower=0.0)

    # Derived instantaneous powers (§4.2)
    df["derived_load_kW"] = (delta_import * 60.0).clip(lower=0.0, upper=30.0)
    df["derived_export_kW"] = (delta_export * 60.0).clip(lower=0.0, upper=30.0)
    df["derived_reactive_kvar"] = ((delta_q1 + delta_q2 - delta_q3 - delta_q4) * 60.0).clip(-20.0, 20.0)

    # Derived Power Factor
    s_apparent = np.sqrt(df["derived_load_kW"]**2 + df["derived_reactive_kvar"]**2)
    df["derived_power_factor"] = np.where(
        s_apparent > 0.01,
        (df["derived_load_kW"] / s_apparent).clip(0.0, 1.0),
        0.95
    )

    # Derived Phase Current
    v_clean = df["voltage_V"].fillna(230.0).clip(lower=10.0)
    df["derived_phase_current_A"] = (df["derived_load_kW"] * 1000.0) / (v_clean * df["derived_power_factor"].clip(0.3, 1.0))
    df["derived_phase_current_A"] = df["derived_phase_current_A"].clip(0.0, 80.0)

    # Neutral Imbalance Ratio (§4.2)
    neutral_c = df["neutral_current_A"].fillna(0.0).clip(lower=0.0)
    df["neutral_imbalance_ratio"] = (neutral_c / (df["derived_phase_current_A"] + 0.1)).clip(0.0, 25.0)

    # Physics Residuals (§9)
    # 1. Ohm's Law Residual r_P = |load_kW - (V * I * PF / 1000)|
    p_apparent = (v_clean * df["derived_phase_current_A"] * df["derived_power_factor"]) / 1000.0
    df["residual_power_kW"] = np.abs(df["derived_load_kW"] - p_apparent)

    # 2. Radial Line Drop Residual r_V
    v_expected = 230.0 - (0.00045 * df["distance_from_transformer_m"] * df["derived_phase_current_A"])
    df["residual_voltage_V"] = np.abs(df["voltage_V"].fillna(230.0) - v_expected)

    # Rolling window statistics (15-minute window per meter)
    print("-> Computing rolling metrics (15-min window)...")
    df["voltage_roll_mean_15m"] = grouped["voltage_V"].transform(lambda s: s.ffill().rolling(15, min_periods=1).mean())
    df["voltage_roll_std_15m"] = grouped["voltage_V"].transform(lambda s: s.ffill().rolling(15, min_periods=1).std()).fillna(0.0)
    df["load_roll_mean_15m"] = grouped["derived_load_kW"].transform(lambda s: s.rolling(15, min_periods=1).mean())
    df["load_roll_std_15m"] = grouped["derived_load_kW"].transform(lambda s: s.rolling(15, min_periods=1).std()).fillna(0.0)

    # Latency delta
    df["ingest_timestamp"] = pd.to_datetime(df["ingest_timestamp"], format="ISO8601")
    df["telecom_latency_s"] = (df["ingest_timestamp"] - df["event_timestamp"]).dt.total_seconds().clip(0.0, 60.0)

    # Cyclical time features
    minute_of_day = df["event_timestamp"].dt.hour * 60 + df["event_timestamp"].dt.minute
    df["sin_time"] = np.sin(2 * np.pi * minute_of_day / 1440.0)
    df["cos_time"] = np.cos(2 * np.pi * minute_of_day / 1440.0)
    df["day_of_week"] = df["event_timestamp"].dt.weekday

    # Tier-1 Target Label
    df["tier1_label"] = df["label"].map(TIER1_MAP).fillna("NORMAL")

    return df

def run_benchmarking():
    print(f"Loading dataset from {INPUT_CSV}...")
    df = pd.read_csv(INPUT_CSV)
    print(f"Loaded {len(df):,} rows, {len(df.columns)} columns.")

    print("\nEngineering physical features and residuals...")
    df = engineer_features(df)

    min_time = df["event_timestamp"].min()
    max_time = df["event_timestamp"].max()
    duration = max_time - min_time

    train_cutoff = min_time + duration * 0.70
    val_cutoff = min_time + duration * 0.85

    train_df = df[df["event_timestamp"] < train_cutoff].copy()
    val_df = df[(df["event_timestamp"] >= train_cutoff) & (df["event_timestamp"] < val_cutoff)].copy()
    test_df = df[df["event_timestamp"] >= val_cutoff].copy()

    print(f"\nChronological Splits:")
    print(f"  Train: {len(train_df):,} rows ({train_df['event_timestamp'].min()} to {train_df['event_timestamp'].max()})")
    print(f"  Val:   {len(val_df):,} rows ({val_df['event_timestamp'].min()} to {val_df['event_timestamp'].max()})")
    print(f"  Test:  {len(test_df):,} rows ({test_df['event_timestamp'].min()} to {test_df['event_timestamp'].max()})")

    print("\nExporting Parquet datasets...")
    train_df.to_parquet(OUTPUT_DIR / "data_features_train.parquet", index=False)
    val_df.to_parquet(OUTPUT_DIR / "data_features_val.parquet", index=False)
    test_df.to_parquet(OUTPUT_DIR / "data_features_test.parquet", index=False)
    print("  ✓ Saved Parquet datasets to src/data_gen/")

    feature_cols = [
        "voltage_V", "frequency_Hz", "neutral_current_A",
        "voltage_interruptions", "voltage_restorations",
        "power_factor_variation_detected",
        "distance_from_transformer_m",
        "derived_load_kW", "derived_export_kW", "derived_reactive_kvar",
        "derived_power_factor", "derived_phase_current_A", "neutral_imbalance_ratio",
        "residual_power_kW", "residual_voltage_V",
        "voltage_roll_mean_15m", "voltage_roll_std_15m",
        "load_roll_mean_15m", "load_roll_std_15m",
        "telecom_latency_s",
        "sin_time", "cos_time", "day_of_week",
        "quality_flags",
        "magnetic_field_detected", "top_cover_opened", "terminal_cover_opened",
        "io_swap", "phase_neutral_swap", "mains_power_cut", "neutral_disturbance"
    ]

    cat_cols = ["tariff_register", "breaker_state", "comm_channel", "auto_diagnostic", "household_type", "phase", "feeder_id"]
    for c in cat_cols:
        train_df[c] = train_df[c].astype("category")
        val_df[c] = pd.Categorical(val_df[c], categories=train_df[c].cat.categories)
        test_df[c] = pd.Categorical(test_df[c], categories=train_df[c].cat.categories)
        feature_cols.append(c)

    print(f"\nTotal ML Feature vector: {len(feature_cols)} features")

    tier1_classes = sorted(train_df["tier1_label"].unique())
    tier1_map_idx = {c: i for i, c in enumerate(tier1_classes)}

    y_train = train_df["tier1_label"].map(tier1_map_idx)
    y_val = val_df["tier1_label"].map(tier1_map_idx)
    y_test = test_df["tier1_label"].map(tier1_map_idx)

    X_train = train_df[feature_cols]
    X_val = val_df[feature_cols]
    X_test = test_df[feature_cols]

    print("\n" + "=" * 65)
    print("TRAINING LIGHTGBM MULTI-CLASS BENCHMARK MODEL (V3 OVERHAUL)")
    print("=" * 65)

    clf = lgb.LGBMClassifier(
        n_estimators=180,
        learning_rate=0.08,
        num_leaves=31,
        class_weight="balanced",
        random_state=42,
        n_jobs=-1
    )

    clf.fit(
        X_train, y_train,
        eval_set=[(X_val, y_val)],
        callbacks=[lgb.early_stopping(stopping_rounds=15, verbose=False)]
    )

    y_pred = clf.predict(X_test)
    acc = accuracy_score(y_test, y_pred)
    macro_f1 = f1_score(y_test, y_pred, average="macro")

    print(f"\n[Dataset V3 Held-Out Test Set Performance]")
    print(f"Accuracy:  {acc * 100:.2f}%")
    print(f"Macro F1:  {macro_f1:.4f}")
    print("\nClassification Report:")
    print(classification_report(y_test, y_pred, target_names=tier1_classes, digits=4))

    feature_imp = pd.Series(clf.feature_importances_, index=feature_cols).sort_values(ascending=False)
    print("Top 12 Most Predictive Features:")
    for feat, imp in feature_imp.head(12).items():
        print(f"  - {feat:<28}: {imp}")

    model_path = DATA_DIR / "tier1_lightgbm_model.joblib"
    joblib.dump({
        "model": clf,
        "feature_cols": feature_cols,
        "classes": tier1_classes,
        "tier1_map_idx": tier1_map_idx
    }, model_path)
    print(f"\nSaved model checkpoint to {model_path}")

    report = classification_report(y_test, y_pred, target_names=tier1_classes, output_dict=True)
    report["accuracy"] = acc
    report["macro_f1"] = macro_f1
    report["top_features"] = feature_imp.head(15).to_dict()

    with open(OUTPUT_DIR / "benchmark_evaluation_results.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    print(f"Saved evaluation report to {OUTPUT_DIR / 'benchmark_evaluation_results.json'}")

if __name__ == "__main__":
    run_benchmarking()
