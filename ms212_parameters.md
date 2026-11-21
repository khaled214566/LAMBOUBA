# MS212 Smart Meter: Parameter Reference

This document explains every column in `ms212_sample_data.csv`. The data model is based on the Sagemcom MS212 single-phase smart energy meter datasheet (120-240 V, 50/60 Hz, 5(60) A, Class 1 active / Class 2 reactive, DLMS/COSEM).

> **Note:** The datasheet lists categories of data, not the full register list. Instantaneous values (voltage, current, frequency) and the exact column names in the CSV are illustrative choices made for classification purposes. Exact COSEM objects and OBIS codes must be confirmed with Sagemcom (the full list is available under NDA).

---

## 1. Identification

| Parameter | Type | Description |
|---|---|---|
| `meter_id` | string | Unique identifier of the meter (serial number or logical device name). Used to group readings per device and to track a meter's history over time. |
| `timestamp` | ISO 8601 datetime | Date and time the reading was captured, from the meter's internal clock. Important for time-of-use billing, load profiles and event sequencing. |

---

## 2. Energy registers (cumulative)

These are running totals that only increase over the life of the meter. Differences between two readings give consumption for the period.

| Parameter | Unit | Description |
|---|---|---|
| `active_import_kWh` | kWh | Total active energy taken from the grid (real energy consumed by the customer). This is the main billing quantity. Accuracy: MID / IEC Class 1. |
| `active_export_kWh` | kWh | Total active energy sent back to the grid (e.g. solar PV injection). Zero for customers without local generation. |
| `reactive_import_kvarh` | kvarh | Total reactive energy associated with inductive loads (motors, transformers). Does not do useful work but loads the network. Accuracy: IEC Class 2. |
| `reactive_export_kvarh` | kvarh | Total reactive energy associated with capacitive behaviour or reactive power fed back to the grid. |
| `quadrant` | Q1-Q4 | Operating quadrant at the time of reading, defined by the direction of active and reactive power (see table below). |

### Quadrant definitions

| Quadrant | Active power | Reactive power | Typical situation |
|---|---|---|---|
| Q1 | Import | Import (inductive) | Normal consumption with motors, appliances |
| Q2 | Export | Import (inductive) | Local generation, with an inductive network |
| Q3 | Export | Export (capacitive) | Local generation with capacitive effect |
| Q4 | Import | Export (capacitive) | Consumption with capacitive loads (e.g. electronics, capacitor banks) |

---

## 3. Instantaneous electrical values

| Parameter | Unit | Normal range | Description |
|---|---|---|---|
| `voltage_V` | V | about 207-253 V for a 230 V supply | RMS supply voltage at the meter terminals. Low values indicate undervoltage or a sag; high values indicate overvoltage. 0 means a power cut. |
| `frequency_Hz` | Hz | 50 or 60 Hz, within ±5% per the datasheet | Grid frequency. Deviations point to grid instability or generator operation. |
| `current_A` | A | 0.25-60 A (5(60) A meter) | Phase (line) current drawn by the load. The meter's maximum metrological current is 60 A and its maximum switching current is 90 A. |
| `neutral_current_A` | A | about equal to `current_A` | Current in the neutral conductor. In a healthy single-phase installation it matches the phase current. A large gap (neutral much lower than phase) suggests current is bypassing the meter, an earth fault or a neutral problem. |
| `power_factor` | 0 to 1 | 0.90-1.00 is good | Ratio of active power to apparent power. Low values mean a large share of reactive power (poor efficiency). Sudden variations are also a fraud indicator. |

---

## 4. Power quality

| Parameter | Type | Description |
|---|---|---|
| `voltage_interruptions` | integer | Count of power-down events (supply loss) in the period. Recorded by the meter's last-gasp function. |
| `voltage_restorations` | integer | Count of power-up events (supply returned) in the period. Normally close to the number of interruptions. |
| `supply_quality_flag` | OK / DEGRADED / FAILED | Overall power supply quality summary derived from voltage, frequency and interruption data. `FAILED` means no supply. |

---

## 5. Tariff and time-based data

| Parameter | Unit | Description |
|---|---|---|
| `tariff_id` | T1, T2, T3... | Active Time-of-Use tariff register (for example peak, off-peak, night), selected by the meter's programmable calendar. Tariffs can also drive the built-in output relay. |
| `load_profile_kW` | kW | Average power during the capture interval from the programmable load profile. Positive means import and negative means export (the sign convention used in this file). |
| `billing_period_kWh` | kWh | Energy accumulated in the current billing period from the programmable billing profile. Resets at each billing date. |

---

## 6. Tamper and fraud detection flags

All flags are binary: `0` = not detected, `1` = detected.

| Parameter | Description |
|---|---|
| `magnetic_field_detected` | A strong external magnetic field was detected. Magnets can disturb current measurement, so this is a classic tamper method. |
| `top_cover_opened` | The meter's top cover was opened or closed. The top and bottom covers are ultrasonically welded, so this indicates an attempt to access the internals. |
| `terminal_cover_opened` | The terminal block cover was opened or closed. This cover is sealed with a dedicated screw and metal ferrule, and opening it exposes the wiring. |
| `io_swap` | Input and output terminals are swapped (supply and load reversed). This can cause energy to be registered in the wrong direction. |
| `phase_neutral_swap` | Phase and neutral conductors are swapped. This can allow loads to be powered without being measured correctly. |
| `mains_power_cut` | A mains power cut was detected. Can be legitimate (grid outage) or part of a tamper pattern when combined with other flags. |
| `neutral_disturbance` | Abnormal neutral behaviour was detected (for example, tampering with the neutral connection or injected disturbance). |

---

## 7. Device health

| Parameter | Values | Description |
|---|---|---|
| `diagnostic_status` | OK / WARNING / ALARM / ERROR | Result of the meter's auto-diagnostic and data integrity checks. `WARNING` and `ALARM` usually accompany tamper or quality events; `ERROR` indicates an internal meter fault. |

---

## 8. Target label (for classification)

| Parameter | Description |
|---|---|
| `label` | The class the record belongs to. Include it for training and drop it for prediction. |

### Label meanings

| Group | Label | Meaning |
|---|---|---|
| Normal | `normal` | Typical import consumption in Q1 |
| | `normal_export_q2` | Legitimate export (e.g. solar), quadrant Q2 |
| | `normal_export_q3` | Legitimate export, quadrant Q3 |
| | `normal_capacitive_q4` | Normal consumption with capacitive load, quadrant Q4 |
| Tamper | `tamper_magnetic` | Magnetic interference |
| | `tamper_top_cover` | Top cover opening |
| | `tamper_terminal_cover` | Terminal cover opening |
| | `tamper_io_swap` | Input/output swapped |
| | `tamper_phase_neutral_swap` | Phase/neutral swapped |
| | `tamper_multiple` | Several tamper flags at once |
| Supply and power quality | `power_cut` | Supply lost |
| | `voltage_interruption` | Repeated short interruptions |
| | `undervoltage` | Voltage well below nominal |
| | `overvoltage` | Voltage well above nominal |
| | `frequency_deviation` | Frequency outside normal range |
| | `poor_power_factor` | Very low power factor |
| Neutral and load | `neutral_disturbance` | Neutral anomaly flagged |
| | `neutral_current_imbalance` | Neutral current far from phase current (possible bypass or earth fault) |
| | `overcurrent` | Current near or above the rated maximum |
| Device | `device_fault` | Meter internal error (all-zero registers, ERROR status) |

---

## 9. Data access

The meter's data can be read through:

- the **optical port** (IEC 62056-21 local access, with DLMS password authentication),
- the **P1 DSMR port**,
- remotely over **G3-PLC RF Hybrid** or the **cellular module** (2G/4G LTE, NB-IoT),

using **DLMS/COSEM** with security suites 0 and 1 (ready for suite 2).

---

## 10. Practical tips for the classification model

- **Scale numeric features** (voltage, current, energy) before training. Their ranges differ widely.
- **Treat flags as categorical/binary**, and encode `quadrant`, `tariff_id`, `supply_quality_flag` and `diagnostic_status` with one-hot encoding.
- **Use differences, not raw cumulative registers**, when possible. Energy registers always grow, so the change per period carries the real signal.
- **Engineer ratios**, for example `neutral_current_A / current_A`, which is a strong indicator for bypass and swap faults.
- **Balance classes.** Tamper and fault events are rare in real data, so consider oversampling or class weights.
