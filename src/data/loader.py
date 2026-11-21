"""
EnergyMind Tunisia — Centralized Data Access Layer
===================================================
High-performance, selective domain loader supporting column projection,
timestamp filtering, meter filtering, feeder queries, and ML preset domains.
"""

import logging
from pathlib import Path
from typing import Dict, List, Optional, Union

import pandas as pd

from src.data.config import (
    DOMAIN_CATALOG,
    METER_REGISTRY_COLUMNS,
    STRUCTURED_DATA_DIR,
)

logger = logging.getLogger(__name__)


class NeighborhoodDataLoader:
    """
    Centralized data access layer for EnergyMind Tunisia.
    Provides selective, performant loading of domain-specific CSV files,
    avoiding the memory overhead of loading all 33 columns simultaneously.
    """

    def __init__(self, structured_dir: Optional[Path] = None):
        """
        Initializes loader with the directory containing the structured CSV files.
        """
        self.structured_dir = (
            Path(structured_dir) if structured_dir is not None else STRUCTURED_DATA_DIR
        )
        if not self.structured_dir.exists():
            raise FileNotFoundError(
                f"Structured data directory does not exist: {self.structured_dir}"
            )
        self._registry_cache: Optional[pd.DataFrame] = None

    def load_meter_registry(self, force_reload: bool = False) -> pd.DataFrame:
        """
        Loads static meter and network topology metadata.
        Caches in memory for fast subsequent queries.

        Returns
        -------
        pd.DataFrame
            50-row dataframe containing meter_id, feeder_id, phase, distance, household_type.
        """
        if self._registry_cache is None or force_reload:
            path = self.structured_dir / DOMAIN_CATALOG["meter_registry"]["filename"]
            self._registry_cache = pd.read_csv(path, low_memory=False)
        return self._registry_cache.copy()

    def get_meters_by_feeder(self, feeder_id: Union[str, List[str]]) -> List[str]:
        """
        Retrieves list of meter_ids belonging to specific feeder(s).
        """
        reg = self.load_meter_registry()
        if isinstance(feeder_id, str):
            feeder_list = [feeder_id]
        else:
            feeder_list = list(feeder_id)
        return reg[reg["feeder_id"].isin(feeder_list)]["meter_id"].tolist()

    def load_domain(
        self,
        domain_name: str,
        meter_ids: Optional[Union[str, List[str]]] = None,
        feeder_ids: Optional[Union[str, List[str]]] = None,
        start_time: Optional[Union[str, pd.Timestamp]] = None,
        end_time: Optional[Union[str, pd.Timestamp]] = None,
        columns: Optional[List[str]] = None,
    ) -> pd.DataFrame:
        """
        Loads a single data domain with optional filtering and column projection.

        Parameters
        ----------
        domain_name : str
            Domain name key from DOMAIN_CATALOG (e.g. 'electrical_measurements')
        meter_ids : str or list of str, optional
            Filter for specific meter ID(s)
        feeder_ids : str or list of str, optional
            Filter for meters on specific feeder(s)
        start_time : str or Timestamp, optional
            Filter records where event_timestamp >= start_time (ISO format string)
        end_time : str or Timestamp, optional
            Filter records where event_timestamp <= end_time (ISO format string)
        columns : list of str, optional
            Subset of columns to project. Mandatory keys (record_id, meter_id)
            are preserved if present in domain.

        Returns
        -------
        pd.DataFrame
            Filtered domain DataFrame.
        """
        if domain_name not in DOMAIN_CATALOG:
            raise KeyError(
                f"Unknown domain: '{domain_name}'. Valid domains: {list(DOMAIN_CATALOG.keys())}"
            )

        meta = DOMAIN_CATALOG[domain_name]
        file_path = self.structured_dir / meta["filename"]
        if not file_path.exists():
            raise FileNotFoundError(f"Domain file not found: {file_path}")

        # Determine columns to load
        valid_cols = meta["columns"]
        load_cols = None
        if columns is not None:
            # Ensure requested columns exist in domain
            unknown_cols = set(columns) - set(valid_cols)
            if unknown_cols:
                raise ValueError(
                    f"Columns {unknown_cols} do not exist in domain '{domain_name}'. Available: {valid_cols}"
                )
            load_cols = list(columns)
            # Ensure essential keys are present if in domain
            for key in ["record_id", "meter_id", "event_timestamp"]:
                if key in valid_cols and key not in load_cols:
                    load_cols.insert(0, key)

        # Resolve meter filtering (either via feeder_ids or direct meter_ids)
        target_meters = None
        if feeder_ids is not None:
            target_meters = set(self.get_meters_by_feeder(feeder_ids))

        if meter_ids is not None:
            direct_meters = {meter_ids} if isinstance(meter_ids, str) else set(meter_ids)
            if target_meters is not None:
                target_meters = target_meters.intersection(direct_meters)
            else:
                target_meters = direct_meters

        df = pd.read_csv(file_path, usecols=load_cols, low_memory=False)

        # Apply meter filtering
        if target_meters is not None and "meter_id" in df.columns:
            df = df[df["meter_id"].isin(target_meters)]

        # Apply timestamp filtering (lexicographical ISO comparison works reliably on ISO8601 strings)
        if "event_timestamp" in df.columns:
            if start_time is not None:
                st_str = str(start_time)
                df = df[df["event_timestamp"] >= st_str]
            if end_time is not None:
                et_str = str(end_time)
                df = df[df["event_timestamp"] <= et_str]

        return df.reset_index(drop=True)

    def load_domains(
        self,
        domain_names: List[str],
        include_registry: bool = False,
        meter_ids: Optional[Union[str, List[str]]] = None,
        feeder_ids: Optional[Union[str, List[str]]] = None,
        start_time: Optional[Union[str, pd.Timestamp]] = None,
        end_time: Optional[Union[str, pd.Timestamp]] = None,
        columns: Optional[List[str]] = None,
    ) -> pd.DataFrame:
        """
        Loads multiple observation domains and joins them seamlessly on 'record_id'.
        Optionally joins meter_registry metadata on 'meter_id'.
        """
        if not domain_names:
            raise ValueError("domain_names list cannot be empty.")

        dfs: List[pd.DataFrame] = []
        for d in domain_names:
            if d == "meter_registry":
                continue
            df = self.load_domain(
                domain_name=d,
                meter_ids=meter_ids,
                feeder_ids=feeder_ids,
                start_time=start_time,
                end_time=end_time,
            )
            dfs.append(df)

        if not dfs:
            if include_registry or "meter_registry" in domain_names:
                return self.load_meter_registry()
            return pd.DataFrame()

        # Merge observation tables on record_id
        base_df = dfs[0]
        for df in dfs[1:]:
            shared_keys = {"record_id", "meter_id", "event_timestamp"}
            unique_cols = [c for c in df.columns if c not in shared_keys]
            merge_cols = ["record_id"] + unique_cols
            base_df = base_df.merge(df[merge_cols], on="record_id", how="inner")

        # Optionally join meter_registry
        if include_registry or "meter_registry" in domain_names:
            reg_df = self.load_meter_registry()
            reg_unique = [c for c in METER_REGISTRY_COLUMNS if c != "meter_id"]
            base_df = base_df.merge(
                reg_df[["meter_id"] + reg_unique], on="meter_id", how="left"
            )

        # Apply final column projection if requested
        if columns is not None:
            available_cols = [c for c in columns if c in base_df.columns]
            base_df = base_df[available_cols]

        return base_df.reset_index(drop=True)

    # ── Machine Learning Domain Presets ──────────────────────────────────────

    def load_for_energy_monitoring(
        self,
        include_registry: bool = True,
        meter_ids: Optional[Union[str, List[str]]] = None,
        feeder_ids: Optional[Union[str, List[str]]] = None,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
    ) -> pd.DataFrame:
        """Loads energy_registers (+ optionally meter_registry) for forecasting & loss estimation."""
        return self.load_domains(
            domain_names=["energy_registers"],
            include_registry=include_registry,
            meter_ids=meter_ids,
            feeder_ids=feeder_ids,
            start_time=start_time,
            end_time=end_time,
        )

    def load_for_electrical_anomaly_monitoring(
        self,
        include_energy: bool = True,
        meter_ids: Optional[Union[str, List[str]]] = None,
        feeder_ids: Optional[Union[str, List[str]]] = None,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
    ) -> pd.DataFrame:
        """Loads electrical_measurements (+ optionally energy_registers) for power quality & SAG/SWELL detection."""
        domains = ["electrical_measurements"]
        if include_energy:
            domains.append("energy_registers")
        return self.load_domains(
            domain_names=domains,
            include_registry=False,
            meter_ids=meter_ids,
            feeder_ids=feeder_ids,
            start_time=start_time,
            end_time=end_time,
        )

    def load_for_tampering_detection(
        self,
        include_status: bool = True,
        include_labels: bool = False,
        meter_ids: Optional[Union[str, List[str]]] = None,
        feeder_ids: Optional[Union[str, List[str]]] = None,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
    ) -> pd.DataFrame:
        """Loads electrical_measurements, energy_registers, meter_events (+ optionally device_status & labels) for theft & tamper ML."""
        domains = ["electrical_measurements", "energy_registers", "meter_events"]
        if include_status:
            domains.append("device_status")
        if include_labels:
            domains.append("labels")
        return self.load_domains(
            domain_names=domains,
            include_registry=True,
            meter_ids=meter_ids,
            feeder_ids=feeder_ids,
            start_time=start_time,
            end_time=end_time,
        )

    def load_for_device_health(
        self,
        meter_ids: Optional[Union[str, List[str]]] = None,
        feeder_ids: Optional[Union[str, List[str]]] = None,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
    ) -> pd.DataFrame:
        """Loads device_status and communications for predictive maintenance."""
        return self.load_domains(
            domain_names=["device_status", "communications"],
            include_registry=True,
            meter_ids=meter_ids,
            feeder_ids=feeder_ids,
            start_time=start_time,
            end_time=end_time,
        )

    def load_for_communication_reliability(
        self,
        meter_ids: Optional[Union[str, List[str]]] = None,
        feeder_ids: Optional[Union[str, List[str]]] = None,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
    ) -> pd.DataFrame:
        """Loads communications domain (+ optionally device_status) for SLA and PLC/GPRS packet drop analysis."""
        return self.load_domains(
            domain_names=["communications"],
            include_registry=True,
            meter_ids=meter_ids,
            feeder_ids=feeder_ids,
            start_time=start_time,
            end_time=end_time,
        )
