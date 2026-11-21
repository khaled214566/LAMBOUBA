# EnergyMind Tunisia — Central Data Dictionary

This document serves as the authoritative, human-readable data dictionary for the **EnergyMind Tunisia** smart-grid monitoring platform, based on the **Sagemcom MS212** single-phase DLMS/COSEM meter operating on the **STEG** low-voltage distribution network.

---

## 1. Domain Catalog Overview

The dataset partitions 33 established parameters into 7 logical domains:

| Domain | File Name | Primary Key | Foreign Key | Cardinality | Purpose |
|---|---|---|---|---|---|
| **Meter Registry** | `meter_registry.csv` | `meter_id` | *None* | 50 rows (1 per meter) | Static physical meter attributes, installation metadata, and LV topology. |
| **Energy Registers** | `energy_registers.csv` | `record_id` | `meter_id` | 504,000 rows | Cumulative active/reactive 4-quadrant energy billing registers. |
| **Electrical Measurements** | `electrical_measurements.csv` | `record_id` | `meter_id` | 504,000 rows | Instantaneous physical measurements (voltage, frequency, neutral current). |
| **Meter Events** | `meter_events.csv` | `record_id` | `meter_id` | 504,000 rows | Tamper switch activations, grid outages, and power quality alerts. |
| **Device Status** | `device_status.csv` | `record_id` | `meter_id` | 504,000 rows | 100A latching relay state, internal DLMS diagnostics, quality flags. |
| **Communications** | `communications.csv` | `record_id` | `meter_id` | 504,000 rows | Transmission protocol and gateway packet reception latency. |
| **Labels** | `labels.csv` | `record_id` | `meter_id` | 504,000 rows | Quarantined ground-truth classification target for AI/ML models. |

---

## 2. Complete 33-Parameter Data Dictionary

| Field | Domain | Data Type | Unit | Nullable | Permitted Values / Range | Description |
|---|---|---|:---:|:---:|---|---|
| `record_id` | *All Observation Domains* | `int64` | — | No | $1 \le \text{id} \le 504000$ | Unique sequential observation identifier across all 1-minute time-series tables. |
| `meter_id` | *All Domains* | `string` | — | No | Pattern: `MS212-TN-\d{4}` | Sagemcom MS212 unique meter hardware identifier (e.g., `MS212-TN-0001`). |
| `feeder_id` | `meter_registry` | `string` | — | No | `feeder_01`, `feeder_02`, `feeder_03` | MV/LV distribution transformer outgoing feeder circuit identifier. |
| `phase` | `meter_registry` | `string` | — | No | `L1`, `L2`, `L3` | Distribution grid phase connection for single-phase installation. |
| `distance_from_transformer_m` | `meter_registry` | `float64` | `m` | No | $10.0 \dots 1200.0$ | Radial cable length from secondary transformer substation in meters. |
| `household_type` | `meter_registry` | `string` | — | No | `family_home`, `high_usage_home`, `small_flat` | STEG residential consumer load profile category. |
| `event_timestamp` | *All Observation Domains* | `string` (ISO8601) | — | No | ISO8601 UTC | Meter clock sampling timestamp (1-minute fixed interval). |
| `ingest_timestamp` | `communications` | `string` (ISO8601) | — | No | ISO8601 UTC | Timestamp when packet was ingested by STEG head-end AMI server. |
| `comm_channel` | `communications` | `string` | — | No | `Cellular-4G`, `G3-PLC`, `W-Mbus` | Active communication uplink protocol used by meter. |
| `active_import_kWh` | `energy_registers` | `float64` | `kWh` | No | $\ge 0.0$ | Cumulative active forward energy imported from grid. |
| `active_export_kWh` | `energy_registers` | `float64` | `kWh` | No | $\ge 0.0$ | Cumulative active reverse energy exported to grid (e.g., rooftop solar PV). |
| `reactive_Q1_kvarh` | `energy_registers` | `float64` | `kvarh` | No | $\ge 0.0$ | Cumulative reactive energy Q1 (active +, reactive +: inductive import). |
| `reactive_Q2_kvarh` | `energy_registers` | `float64` | `kvarh` | No | $\ge 0.0$ | Cumulative reactive energy Q2 (active -, reactive +: capacitive export). |
| `reactive_Q3_kvarh` | `energy_registers` | `float64` | `kvarh` | No | $\ge 0.0$ | Cumulative reactive energy Q3 (active -, reactive -: inductive export). |
| `reactive_Q4_kvarh` | `energy_registers` | `float64` | `kvarh` | No | $\ge 0.0$ | Cumulative reactive energy Q4 (active +, reactive -: capacitive import). |
| `tariff_register` | `energy_registers` | `string` | — | No | `T1`, `T2`, `T3` | Active STEG time-of-use tariff register. |
| `voltage_V` | `electrical_measurements` | `float64` | `V` | **Yes** | $0.0 \dots 1200.0$ | Instantaneous RMS voltage (nominal 230 V). Null during `missing_data`. |
| `frequency_Hz` | `electrical_measurements` | `float64` | `Hz` | **Yes** | $45.0 \dots 55.0$ | Instantaneous grid frequency (nominal 50.0 Hz). Null during `missing_data`. |
| `neutral_current_A` | `electrical_measurements` | `float64` | `A` | **Yes** | $0.0 \dots 150.0$ | Instantaneous neutral conductor RMS current. Null during `missing_data`. |
| `voltage_interruptions` | `meter_events` | `int64` | count | No | $\ge 0$ | Cumulative count of voltage interruption / deep sag events. |
| `voltage_restorations` | `meter_events` | `int64` | count | No | $\ge 0$ | Cumulative count of voltage restoration events after outage. |
| `power_factor_variation_detected` | `meter_events` | `int64` | flag | No | `0`, `1` | Binary flag: rapid or abnormal power factor degradation. |
| `breaker_state` | `device_status` | `string` | — | No | `CLOSED`, `OPEN` | Physical latching relay contact position (`CLOSED` = energized). |
| `magnetic_field_detected` | `meter_events` | `int64` | flag | No | `0`, `1` | Binary flag: internal Hall sensor detected external magnet tamper (>300 mT). |
| `top_cover_opened` | `meter_events` | `int64` | flag | No | `0`, `1` | Binary flag: main enclosure top cover microswitch triggered. |
| `terminal_cover_opened` | `meter_events` | `int64` | flag | No | `0`, `1` | Binary flag: terminal connection block cover microswitch triggered. |
| `io_swap` | `meter_events` | `int64` | flag | No | `0`, `1` | Binary flag: current sensor input/output inversion detected. |
| `phase_neutral_swap` | `meter_events` | `int64` | flag | No | `0`, `1` | Binary flag: phase and neutral wiring reversed at meter terminals. |
| `mains_power_cut` | `meter_events` | `int64` | flag | No | `0`, `1` | Binary flag: upstream grid outage (last gasp transmission). |
| `neutral_disturbance` | `meter_events` | `int64` | flag | No | `0`, `1` | Binary flag: neutral disconnection, ground return bypass, or tampering. |
| `auto_diagnostic` | `device_status` | `string` | — | No | `OK`, `WARNING`, `ERROR`, `ALARM` | DLMS/COSEM meter internal health status register. |
| `quality_flags` | `device_status` | `int64` | bitmask | No | $\ge 0$ | Bitmask encoding measurement validation flags. |
| `label` | `labels` | `string` | — | No | 25 discrete classes | Supervised ground-truth classification target label. |

---

## 3. Missing-Value Conventions

- In this dataset, exactly 3 columns can contain null values: `voltage_V`, `frequency_Hz`, and `neutral_current_A`.
- Nulls occur synchronously across these three fields (4,977 occurrences) specifically when `label == "missing_data"`.
- This represents packet loss or telemetry sensor failure during transmission.
- All other 30 parameters are strictly non-nullable (`nullable: false`).

---

## 4. Ground-Truth Label Catalog

The `labels.csv` domain contains 25 distinct ground-truth classes:

1. **Normal Grid Operation:** `normal`, `normal_capacitive_q4`, `normal_export_q2`, `normal_export_q3`.
2. **Power Quality & Grid Disturbances:** `frequency_deviation`, `neutral_current_imbalance`, `overcurrent`, `overvoltage`, `undervoltage`, `poor_power_factor`, `power_cut`.
3. **Meter Faults & Sensor Degradation:** `constant_bias`, `device_fault`, `dropout`, `energy_power_mismatch`, `meter_drift`, `missing_data`, `random_corruption`.
4. **Non-Technical Losses & Fraud:** `tamper_io_swap`, `tamper_magnetic`, `tamper_phase_neutral_swap`, `tamper_terminal_cover`, `tamper_top_cover`, `tamper_multiple`, `neutral_disturbance`.

> [!IMPORTANT]
> The `labels.csv` domain is strictly quarantined from model input features during unsupervised anomaly detection and production inference.
