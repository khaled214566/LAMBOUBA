# EnergyMind Tunisia — Training & Testing Dataset Partitioning Architecture

## 1. Executive Overview

The **EnergyMind Tunisia** platform requires robust machine learning models capable of operating in production across the STEG low-voltage distribution network. In real-world smart grids:
1. **Future Forecasting & Triage:** Models must detect anomalies forward in time on already-monitored smart meters without temporal lookahead bias.
2. **Cross-Meter Generalization:** Models must detect power quality events, meter failures, and theft on newly deployed or previously unseen meters without overfitting to individual meter baseline load patterns.

To satisfy both criteria simultaneously without data leakage, the 504,000 neighborhood observations (50 meters over 7 days at 1-minute cadence) are partitioned using a **Spatio-Temporal Hybrid Strategy**.

---

## 2. Partitioning Blueprint & Dataset Allocations

```mermaid
flowchart TD
    subgraph Neighborhood ["Neighborhood Telemetry (504,000 Observations / 50 Meters / 7 Days)"]
        direction TB
        M40["40 Training & Tuning Meters (80%)"]
        M10["10 Held-out Test Meters (20% Stratified)"]
    end

    subgraph Splits ["Spatio-Temporal Hybrid Partitions"]
        direction TB
        M40 -->|Days 1 - 5 (Nov 13-17)| Train["TRAIN Split (288,000 rows)<br/>40 meters × 5 days × 1,440 min"]
        M40 -->|Day 6 (Nov 18)| Val["VALIDATION Split (57,600 rows)<br/>40 meters × 1 day × 1,440 min"]
        M40 -->|Day 7 (Nov 19)| TestTemp["TEST_TEMPORAL Split (57,600 rows)<br/>40 meters × 1 day × 1,440 min"]
        M10 -->|Days 1 - 7 (Nov 13-19)| TestSpat["TEST_SPATIAL Split (100,800 rows)<br/>10 unseen meters × 7 days × 1,440 min"]
    end
```

| Partition | Scope | Meters | Time Period | Observation Count | Percentage | Primary ML Objective |
|---|---|:---:|:---:|:---:|:---:|---|
| **`train`** | In-sample tuning | 40 | Days 1–5 | **288,000** | 57.1% | Model fitting, parameter learning, baseline profiling |
| **`val`** | Early stopping & threshold tuning | 40 | Day 6 | **57,600** | 11.4% | Hyperparameter optimization, anomaly threshold calibration |
| **`test_temporal`** | Future prediction (Known meters) | 40 | Day 7 | **57,600** | 11.4% | Evaluates forward-in-time forecasting & anomaly triage |
| **`test_spatial`** | Zero-shot generalization (Unseen meters) | 10 | Days 1–7 | **100,800** | 20.0% | Evaluates detection on new meters without historical baselines |
| **Total** | **Full Neighborhood** | **50** | **7 Days** | **504,000** | **100.0%** | Zero lost records |

---

## 3. Held-Out Meters Topological Stratification (10 Meters)

To ensure the 10 spatial test meters represent the full heterogeneity of the STEG low-voltage network, meters are stratified across:
- **Feeders:** 3 meters from `feeder_01` (Phase L1, small flats), 4 meters from `feeder_02` (Phase L2, family homes), 3 meters from `feeder_03` (Phase L3, high-usage homes).
- **Phases:** 3 on `L1`, 4 on `L2`, 3 on `L3`.
- **Cable Distance:** Near ($<200\text{ m}$), medium ($200\dots500\text{ m}$), and feeder-tail ($>500\text{ m}$).

The 10 designated held-out meters in `HELD_OUT_METERS`:
- `MS212-TN-0008`, `MS212-TN-0010`, `MS212-TN-0012`, `MS212-TN-0013`, `MS212-TN-0014`
- `MS212-TN-0015`, `MS212-TN-0016`, `MS212-TN-0029`, `MS212-TN-0033`, `MS212-TN-0035`

---

## 4. Dual Target Label Hierarchy Contract

Every observation record provides dual classification targets:
1. **Granular Target (`label_25`):** All 25 original ground-truth classes.
2. **Tier-1 Macro Target (`label_tier1`):** 5 operational macro categories:
   - `NORMAL`: `normal`, `normal_export_q2`, `normal_export_q3`, `normal_capacitive_q4`.
   - `FALSIFICATION_ATTACK`: `tamper_magnetic`, `tamper_top_cover`, `tamper_terminal_cover`, `tamper_io_swap`, `tamper_phase_neutral_swap`, `tamper_multiple`, `neutral_disturbance`.
   - `GENUINE_GRID_EVENT`: `power_cut`, `voltage_interruption`, `undervoltage`, `overvoltage`, `frequency_deviation`.
   - `EQUIPMENT_FAULT`: `neutral_current_imbalance`, `overcurrent`, `poor_power_factor`, `device_fault`.
   - `DATA_QUALITY_ISSUE`: `constant_bias`, `meter_drift`, `missing_data`, `dropout`, `random_corruption`, `energy_power_mismatch`.

---

## 5. Lightweight Rule-Based Slicing (Zero Index Overhead)

Rather than storing a redundant 504,000-row `split_index.csv` file on disk, `NeighborhoodDataLoader.load_split` executes in-memory vectorized boolean masking based on:
1. `meter_id.isin(HELD_OUT_METERS)`
2. `event_timestamp` vs `VAL_CUTOFF_TIMESTAMP` (`2026-11-18`) and `TEST_CUTOFF_TIMESTAMP` (`2026-11-19`).

```python
from src.data.loader import NeighborhoodDataLoader

loader = NeighborhoodDataLoader()

# In-memory instant slicing without disk overhead
df_train = loader.load_split("train", domain_names=["electrical_measurements", "meter_events"])
```

### Precomputed ML Matrices
For immediate high-throughput model training, compressed Apache Parquet feature matrices are available in `data/realistic/processed/`:
- `train.parquet` (288,000 rows)
- `val.parquet` (57,600 rows)
- `test_temporal.parquet` (57,600 rows)
- `test_spatial.parquet` (100,800 rows)
- `feature_manifest.json`

```python
df_test_spatial = loader.load_processed_split("test_spatial")
```
