"""
EnergyMind Tunisia — Module 2: Stateful Cumulative Register Integrator & Anomaly Physics (v3)
============================================================================================
Key updates:
  - Comprehensive physical metrology perturbations for ALL anomaly classes:
      * tamper_phase_neutral_swap: Neutral current collapses to near-zero (0.02 - 0.15A)
        while phase current continues, generating physical neutral imbalance ratio > 15.0.
      * tamper_magnetic: Phase current & measured active power suppressed by 65-80%
        (core saturation), providing genuine electrical signal even when magnetic flag is shielded!
      * tamper_io_swap: Active energy reverses flow into active_export_kWh while active_import_kWh stops.
      * missing_data: Telemetry channels set to np.nan (activating bit 0 MISSING_VALUE).
      * dropout: Voltage & neutral current drop to 0.0 with breaker CLOSED and no power cut flag.
      * random_corruption: Voltage bitflip (750V - 999V), activating bit 1 OUT_OF_BOUNDS.
      * poor_power_factor: Power factor collapses to 0.45 - 0.60, inflating reactive Q registers.
  - Decoupled auto_diagnostic: Stochastic realistic watchdog/self-test states (not 1:1 leaked).
  - Strict non-decreasing cumulative register integration (0 negative decrements).
"""

from dataclasses import dataclass
from typing import Dict, Optional, Tuple
import math
import numpy as np

MAX_STEP_DELTA_KWH = 0.310  # 18.4 kW fuse capacity (80A * 230V) / 60 min

@dataclass
class MeterState:
    meter_id: str
    cum_import_kWh: float
    cum_export_kWh: float
    cum_q1_kvarh: float
    cum_q2_kvarh: float
    cum_q3_kvarh: float
    cum_q4_kvarh: float
    voltage_interruptions: int = 0
    voltage_restorations: int = 0
    is_in_outage: bool = False
    episode_active: bool = False
    episode_label: Optional[str] = None
    episode_start_step: int = 0
    episode_duration: int = 0
    drift_rate: float = 0.0
    bias_scale: float = 1.0


class StatefulRegisterIntegrator:
    """Maintains stateful meter registers across simulation steps with complete physical distortions."""

    def __init__(self, initial_states: Dict[str, MeterState]):
        self.states = initial_states

    def step(
        self,
        meter_id: str,
        step_idx: int,
        p_data: Dict[str, float],
        flow_data: Dict[str, float],
        anomaly_label: Optional[str] = None,
        breaker_state: str = "CLOSED"
    ) -> Dict[str, any]:
        st = self.states[meter_id]
        v_terminal = flow_data["voltage_V"]
        p_import = p_data["p_import_kW"]
        p_export = p_data["p_export_kW"]
        q1 = p_data["q1_kvar"]
        q2 = p_data["q2_kvar"]
        q3 = p_data["q3_kvar"]
        q4 = p_data["q4_kvar"]
        pf_val = p_data["power_factor"]

        # Track episode start
        if anomaly_label and not st.episode_active:
            st.episode_active = True
            st.episode_label = anomaly_label
            st.episode_start_step = step_idx
            st.drift_rate = float(np.random.uniform(0.05, 0.25))
            st.bias_scale = float(np.random.choice([0.70, 0.80, 1.25, 1.35]))
        elif not anomaly_label and st.episode_active:
            st.episode_active = False
            st.episode_label = None

        # ── 1. Evaluate Outage Transitions & Event Counters ──────────────────
        is_blackout = (anomaly_label == "power_cut") or (v_terminal < 50.0) or (breaker_state == "OPEN")

        if is_blackout and not st.is_in_outage:
            st.is_in_outage = True
            st.voltage_interruptions += 1
        elif not is_blackout and st.is_in_outage:
            st.is_in_outage = False
            st.voltage_restorations += 1

        # ── 2. Apply Physical Power-Domain & Metrology Distortions ────────────
        p_imp_meas = p_import
        p_exp_meas = p_export
        v_meas = v_terminal
        freq_meas = 50.0 + float(np.random.normal(0, 0.02))
        i_phase_meas = flow_data["phase_current_A"]
        i_neutral_meas = flow_data["neutral_current_A"]
        pf_meas = pf_val

        # Realistic stochastic auto-diagnostic base
        auto_diag = "OK" if np.random.random() > 0.002 else "WARNING"

        if anomaly_label == "power_cut":
            p_imp_meas = 0.0
            p_exp_meas = 0.0
            v_meas = 0.0
            freq_meas = 0.0
            i_phase_meas = 0.0
            i_neutral_meas = 0.0
            breaker_state = "OPEN"
            auto_diag = "ERROR" if np.random.random() < 0.90 else "WARNING"

        elif anomaly_label == "device_fault":
            v_meas = 0.0
            p_imp_meas = 0.0
            p_exp_meas = 0.0
            i_phase_meas = 0.0
            i_neutral_meas = 0.0
            auto_diag = "ERROR"

        elif anomaly_label == "tamper_phase_neutral_swap":
            # Real physical bypass: neutral current collapses to near-zero (shunted to earth ground)
            i_neutral_meas = float(np.random.uniform(0.01, 0.15))
            # Phase current remains active powering the load
            i_phase_meas = flow_data["phase_current_A"]
            if np.random.random() < 0.40:
                auto_diag = "WARNING"

        elif anomaly_label == "tamper_magnetic":
            # Neodymium magnet saturates CT core: measured current drops 65% - 85%
            suppression = float(np.random.uniform(0.18, 0.35))
            p_imp_meas = p_import * suppression
            i_phase_meas = flow_data["phase_current_A"] * suppression
            i_neutral_meas = flow_data["neutral_current_A"] * suppression
            if np.random.random() < 0.45:
                auto_diag = "WARNING"

        elif anomaly_label == "tamper_io_swap":
            # Swapped supply and load terminals: active power registered as export!
            p_exp_meas = p_import
            p_imp_meas = 0.0
            if np.random.random() < 0.50:
                auto_diag = "WARNING"

        elif anomaly_label == "tamper_multiple":
            # Compound attack: magnetic suppression + neutral shunting
            suppression = float(np.random.uniform(0.20, 0.35))
            p_imp_meas = p_import * suppression
            i_phase_meas = flow_data["phase_current_A"] * suppression
            i_neutral_meas = float(np.random.uniform(0.02, 0.15))
            auto_diag = "ALARM" if np.random.random() < 0.70 else "WARNING"

        elif anomaly_label == "missing_data":
            # Real communication dropout: channels become NaN
            v_meas = np.nan
            i_neutral_meas = np.nan
            freq_meas = np.nan

        elif anomaly_label == "dropout":
            # Total sensor collapse: voltage & current collapse while breaker remains CLOSED
            v_meas = 0.0
            i_neutral_meas = 0.0
            p_imp_meas = 0.0
            p_exp_meas = 0.0

        elif anomaly_label == "random_corruption":
            # ADC SPI bitflip: voltage registers extreme reading
            v_meas = float(np.random.uniform(750.0, 999.0))
            auto_diag = "ERROR" if np.random.random() < 0.85 else "WARNING"

        elif anomaly_label == "poor_power_factor":
            # Heavy inductive breakdown: PF collapses to 0.45 - 0.60
            pf_meas = float(np.random.uniform(0.45, 0.60))
            q_surge_ratio = math.sqrt(1.0 - pf_meas**2) / pf_meas
            q1 = p_imp_meas * q_surge_ratio  # reactive power surges
            if np.random.random() < 0.35:
                auto_diag = "WARNING"

        elif anomaly_label == "meter_drift":
            elapsed = step_idx - st.episode_start_step
            slope = 1.0 + st.drift_rate * min(1.0, elapsed / 30.0)
            p_imp_meas = p_import * slope
            if slope > 1.15 and np.random.random() < 0.30:
                auto_diag = "WARNING"

        elif anomaly_label == "constant_bias":
            p_imp_meas = p_import * st.bias_scale
            if np.random.random() < 0.30:
                auto_diag = "WARNING"

        elif anomaly_label == "undervoltage":
            v_meas = float(np.random.uniform(175.0, 204.0))

        elif anomaly_label == "overvoltage":
            v_meas = float(np.random.uniform(254.0, 268.0))

        elif anomaly_label == "frequency_deviation":
            sign = np.random.choice([-1, 1])
            freq_meas = 50.0 + sign * float(np.random.uniform(0.6, 2.2))

        elif anomaly_label == "neutral_disturbance":
            i_neutral_meas = float(np.random.uniform(0.01, 1.2))
            if np.random.random() < 0.60:
                auto_diag = "WARNING"

        elif anomaly_label == "neutral_current_imbalance":
            i_neutral_meas = i_phase_meas * float(np.random.uniform(2.5, 4.5))
            if np.random.random() < 0.60:
                auto_diag = "WARNING"

        elif anomaly_label == "overcurrent":
            i_phase_meas = float(np.random.uniform(72.0, 85.0))
            i_neutral_meas = i_phase_meas * float(np.random.uniform(0.98, 1.02))
            auto_diag = "WARNING"

        # ── 3. Stateful Monotonic Quadrature Integration ──────────────────────
        if is_blackout or anomaly_label in ["device_fault", "dropout"]:
            delta_import = 0.000
            delta_export = 0.000
            delta_q1 = 0.000
            delta_q2 = 0.000
            delta_q3 = 0.000
            delta_q4 = 0.000
        elif anomaly_label == "energy_power_mismatch":
            delta_import = (p_imp_meas * 0.50) / 60.0
            delta_export = (p_exp_meas) / 60.0
            delta_q1 = q1 / 60.0
            delta_q2 = q2 / 60.0
            delta_q3 = q3 / 60.0
            delta_q4 = q4 / 60.0
        else:
            delta_import = p_imp_meas / 60.0
            delta_export = p_exp_meas / 60.0
            delta_q1 = q1 / 60.0
            delta_q2 = q2 / 60.0
            delta_q3 = q3 / 60.0
            delta_q4 = q4 / 60.0

        # Physical safety clamp: enforce positive deltas & fuse limit
        delta_import = float(np.clip(delta_import, 0.0, MAX_STEP_DELTA_KWH))
        delta_export = float(np.clip(delta_export, 0.0, MAX_STEP_DELTA_KWH))
        delta_q1 = float(np.clip(delta_q1, 0.0, MAX_STEP_DELTA_KWH))
        delta_q2 = float(np.clip(delta_q2, 0.0, MAX_STEP_DELTA_KWH))
        delta_q3 = float(np.clip(delta_q3, 0.0, MAX_STEP_DELTA_KWH))
        delta_q4 = float(np.clip(delta_q4, 0.0, MAX_STEP_DELTA_KWH))

        st.cum_import_kWh += delta_import
        st.cum_export_kWh += delta_export
        st.cum_q1_kvarh += delta_q1
        st.cum_q2_kvarh += delta_q2
        st.cum_q3_kvarh += delta_q3
        st.cum_q4_kvarh += delta_q4

        return {
            "active_import_kWh": round(st.cum_import_kWh, 3),
            "active_export_kWh": round(st.cum_export_kWh, 3),
            "reactive_Q1_kvarh": round(st.cum_q1_kvarh, 3),
            "reactive_Q2_kvarh": round(st.cum_q2_kvarh, 3),
            "reactive_Q3_kvarh": round(st.cum_q3_kvarh, 3),
            "reactive_Q4_kvarh": round(st.cum_q4_kvarh, 3),
            "delta_import_kWh": round(delta_import, 4),
            "voltage_V": round(v_meas, 1) if not np.isnan(v_meas) else np.nan,
            "frequency_Hz": round(freq_meas, 2) if not np.isnan(freq_meas) else np.nan,
            "neutral_current_A": round(i_neutral_meas, 2) if not np.isnan(i_neutral_meas) else np.nan,
            "phase_current_A": round(i_phase_meas, 2),
            "derived_power_factor": round(pf_meas, 2),
            "voltage_interruptions": st.voltage_interruptions,
            "voltage_restorations": st.voltage_restorations,
            "breaker_state": breaker_state,
            "auto_diagnostic": auto_diag,
        }
