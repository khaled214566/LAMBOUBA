# Sagemcom MS212 Neighborhood Telemetry Dataset — Executive Guide
**EnergyMind Tunisia (STEG Smart Grid — IEEE TSYP 14)**

> **Document Target:** `DATASET_EXECUTIVE_GUIDE.md`  
> **Audience:** Data Scientists, ML Engineers, Grid Operators  
> **Source Data:** `neighborhood_dataset.csv` (504,000 rows, 50 meters, 7 days, 1-min intervals, 33 columns)  
> **Meter Target:** Sagemcom MS212 Single-Phase 230V, 5(80)A, 50 Hz, DLMS/COSEM  

---

## 1. Voltage Parameters in This Dataset

| Metric | Nominal / Ideal | Actual Normal in Data | Operating Limits (EN 50160) | Notes & Circuit Physics |
|---|:---:|:---:|:---:|---|
| **Nominal Voltage** | **230.0 V** | — | $230\text{V} \pm 10\%$ ($207.0\text{V} - 253.0\text{V}$) | Grid reference standard for Tunisia (STEG). |
| **Normal Mean** | — | **221.0 V** | $215.0\text{V} - 228.0\text{V}$ | Accounts for natural feeder line drop ($\Delta V = R \cdot d \cdot I$). |
| **Normal Median (50%)** | — | **222.3 V** | — | Central tendency under standard residential loads. |
| **Normal Range (Min–Max)**| — | **205.0 V – 230.8 V**| Compliant | Voltage sags slightly at distant trunk nodes (up to 800m). |
| **Outage Voltage** | — | **0.0 V** | — | Blackouts (`power_cut`, `device_fault`, `dropout`). |
| **Undervoltage Fault** | — | **175.0 V – 204.0 V** | Mean: 189.4 V | Severe grid drop / overloaded distribution transformer. |
| **Overvoltage Fault** | — | **254.0 V – 268.0 V** | Mean: 261.2 V | Voltage swell / tap changer failure. |
| **Corrupted ADC Spikes** | — | **750.0 V – 999.0 V** | Impossible | Memory bitflip / SPI bus error (`random_corruption`). |

---

## 2. All Possible Problems in the Data (22 Problem Classes)

The dataset contains **3 normal operating states** and **22 distinct problems** grouped into 5 macro categories:

```
Total Records: 504,000
├── Normal Operations:   406,622 rows (80.7%)
└── Injected Problems:    97,378 rows (19.3%)
```

### Problem Classification Matrix

| Category | Problem Label | Rows | Electrical Signature & Detection Clue | Triggered Flags / Registers |
|---|---|:---:|---|---|
| **1. Grid Events** | `power_cut` | 1,582 | $V = 0.0\text{V}$, $f = 0.0\text{Hz}$, $I = 0.0\text{A}$, energy accumulator frozen ($\Delta E = 0$). | `breaker_state=OPEN`, `mains_power_cut=1` |
| | `undervoltage` | 2,365 | Voltage depressed below legal threshold ($175\text{V} - 204\text{V}$). | `quality_flags` (bit 1: `OUT_OF_BOUNDS`) |
| | `overvoltage` | 697 | Voltage swells above safe threshold ($254\text{V} - 268\text{V}$). | `quality_flags` (bit 1: `OUT_OF_BOUNDS`) |
| | `frequency_deviation` | 3,500 | Transmission frequency shifts ($47.8\text{Hz} - 52.2\text{Hz}$). Synchronous across feeders. | — |
| **2. Tampering & Theft** | `tamper_magnetic` | 5,299 | External magnet saturates CT core; phase current & power drop by 65–80% ($r_P > 1.2\text{kW}$). | `magnetic_field_detected` (65% unshielded, 35% stealth) |
| | `tamper_phase_neutral_swap`| 5,520 | Neutral bypassed to ground; $I_{\text{neutral}}$ collapses to $< 0.15\text{A}$ while $I_{\text{phase}}$ stays active. | Neutral imbalance ratio ($I_{\text{neutral}}/I_{\text{phase}} < 0.02$) |
| | `tamper_io_swap` | 4,831 | Input/output cables reversed; active power accumulates in export register (`active_export_kWh`). | `io_swap=1`, `active_import_kWh` frozen |
| | `tamper_top_cover` | 5,051 | Ultrasonic meter enclosure breached; wiring exposed. | `top_cover_opened=1` |
| | `tamper_terminal_cover`| 5,851 | Terminal block cover removed. | `terminal_cover_opened=1` |
| | `tamper_multiple` | 5,354 | Compound attack (magnetic CT suppression + neutral shunting + cover breach). | Multiple tamper flags active |
| **3. Equipment Faults** | `neutral_disturbance` | 5,155 | Loose neutral / terminal oxidation; neutral current fluctuates ($0.01\text{A} - 1.2\text{A}$). | `neutral_disturbance=1` |
| | `neutral_current_imbalance`| 5,723 | Earth fault / leakage; $I_{\text{neutral}}$ is $2.5\times - 4.5\times$ higher than phase current. | Imbalance ratio $> 2.5$ |
| | `overcurrent` | 5,474 | Demand exceeds meter rating ($72\text{A} - 85\text{A}$ on 80A hardware). Risk of fire. | Thermal threshold alert |
| | `poor_power_factor` | 5,033 | Inductive motor breakdown; power factor collapses ($0.45 - 0.60$), reactive kvar surges. | `power_factor_variation_detected=1` |
| **4. Data Quality** | `missing_data` | 4,977 | Communication packet loss; telemetry channels are true `NaN` values. | `quality_flags` (bit 0: `MISSING_VALUE`) |
| | `dropout` | 4,888 | ADC sensor bus collapse; $V=0, I=0$, but breaker remains `CLOSED`. | `quality_flags` (bit 1: `OUT_OF_BOUNDS`) |
| | `random_corruption` | 5,408 | Microcontroller bitflip; voltage registers impossible values ($750\text{V} - 999\text{V}$). | `quality_flags` (bit 1: `OUT_OF_BOUNDS`) |
| | `meter_drift` | 5,049 | Slow transducer wear; measured power drifts upward linearly by 5–25%. | Gradual divergence from baseline |
| | `constant_bias` | 5,696 | Transducer scale calibration offset; power scaled by constant factor ($\pm 25\%$). | Static scaling residual |
| | `energy_power_mismatch`| 4,652 | Firmware register tampering; energy accumulation delta diverges from power ($\Delta E \ne P/60$). | Discrete step residual $r_E > 0.005$ |
| **5. Device Fault** | `device_fault` | 5,273 | Hardware failure / DSP lockup; all channels zero, registers frozen. | `auto_diagnostic=ERROR` |

---

## 3. Dataset Architecture & Schema Reference

### 3.1 Column Dictionary (33 Columns)

```
[Identifiers & Topology]
1. record_id                     : Unique sequential integer primary key
2. meter_id                      : Sagemcom serial (MS212-TN-0001 to MS212-TN-0050)
3. feeder_id                     : Feeder association (feeder_01, feeder_02, feeder_03)
4. phase                         : Radial phase allocation (L1, L2, L3)
5. distance_from_transformer_m   : Cable trunk distance from substation (60m to 800m)
6. household_type                : Premise archetype (small_flat, family_home, high_usage_home)
7. event_timestamp               : Meter RTC event time (ISO 8601 UTC)
8. ingest_timestamp              : Gateway broker arrival time (includes network latency)
9. comm_channel                  : Media protocol (Cellular-4G: ~1.4s, W-Mbus: ~5.0s, G3-PLC: ~8.5s)

[Cumulative Energy Registers — kWh / kvarh (Monotonically Non-Decreasing)]
10. active_import_kWh            : Real billing consumption register
11. active_export_kWh            : Solar injection / reverse energy register
12. reactive_Q1_kvarh            : Inductive import (motors, standard appliances)
13. reactive_Q2_kvarh            : Inductive export (solar PV on inductive grid)
14. reactive_Q3_kvarh            : Capacitive export (solar inverter capacitive support)
15. reactive_Q4_kvarh            : Capacitive import (electronics, capacitor banks)

[Instantaneous Electrical Channels]
16. voltage_V                    : RMS terminal voltage (V)
17. frequency_Hz                 : Fundamental grid frequency (Hz)
18. neutral_current_A            : Neutral conductor current (CT measurement)

[Event Counters & Status]
19. voltage_interruptions        : Lifetime cumulative power-down counter
20. voltage_restorations         : Lifetime cumulative power-up counter
21. power_factor_variation_detected: Event flag for significant PF changes (0 or 1)
22. tariff_register              : Time-of-Use window (T1: off-peak, T2: normal, T3: peak)
23. breaker_state                : Built-in latching disconnect relay (CLOSED / OPEN)

[Hardware Tamper Registers (0 = Normal, 1 = Detected)]
24. magnetic_field_detected      : Magnetic sensor flag (65% unshielded, 35% shielded stealth)
25. top_cover_opened             : Main meter enclosure switch
26. terminal_cover_opened        : Terminal block cover switch
27. io_swap                      : Supply / load reversed wiring flag
28. phase_neutral_swap           : Phase / neutral reversed wiring flag
29. mains_power_cut              : Grid voltage loss flag
30. neutral_disturbance          : Neutral circuit disturbance flag

[Diagnostics & Labels]
31. auto_diagnostic              : Meter internal self-test (OK, WARNING, ERROR, ALARM)
32. quality_flags                : 7-bit validation bitmask (0: VALID, 1: MISSING, 2: OOB, 4: PF_INVALID, 32: IMPEDANCE)
33. label                        : Ground truth classification target (26 distinct classes)
```

---

## 4. Key Rules for Machine Learning Practitioners

1. **Avoid Trivial Shortcut Leakage:**
   * Do NOT use raw tamper flags (`top_cover_opened`, `io_swap`, etc.) as raw predictors if training models to detect **stealth theft**. 35% of magnetic attacks and bypass attacks have flags set to `0` and must be caught via electrical features (`neutral_imbalance_ratio`, $r_P$, $r_V$).
2. **Top Predictive Features:**
   * `neutral_imbalance_ratio` ($I_{\text{neutral}} / I_{\text{phase}}$) is the #1 feature for current diversion and neutral tamper.
   * `sin_time` & `cos_time` capture diurnal baseline expectations.
   * `voltage_roll_mean_15m` and `residual_voltage_V` isolate local faults from feeder-wide sags.
3. **Use Chronological Splits Only:**
   * Partition strictly by `event_timestamp` (e.g. 70% Train, 15% Val, 15% Test). Random k-fold splits leak temporal rolling states and autocorrelation across meters.
