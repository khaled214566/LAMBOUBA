"""
EnergyMind Tunisia — Data Integrity & Schema Validation Suite
=============================================================
Provides:
1. SchemaValidator & validate_dataset: Validates DataFrames against authoritative YAML schemas.
2. DataIntegrityValidator: Performs multi-level validation between raw monolithic
   neighborhood dataset and structured 7-file modular domain architecture.
"""

from dataclasses import dataclass, field
import logging
from pathlib import Path
import re
from typing import Any, Dict, List, Optional, Union

import numpy as np
import pandas as pd

from src.data.config import (
    DOMAIN_CATALOG,
    FALLBACK_RAW_CSV,
    ORIGINAL_COLUMNS,
    PRIMARY_RAW_CSV,
    STRUCTURED_DATA_DIR,
)
from src.data.reconstructor import DatasetReconstructor
from src.data.schema_loader import SchemaLoader, get_schema, get_relationships

logger = logging.getLogger(__name__)


@dataclass
class ValidationErrorDetail:
    domain: str
    column: Optional[str]
    rule: str
    message: str
    sample_records: List[Any] = field(default_factory=list)


@dataclass
class ValidationResult:
    domain: str
    is_valid: bool
    total_records: int
    errors: List[ValidationErrorDetail] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def summary_message(self) -> str:
        status = "PASSED" if self.is_valid else "FAILED"
        msg = f"Validation for domain '{self.domain}' [{status}]: {self.total_records} records evaluated."
        if not self.is_valid:
            msg += f" Found {len(self.errors)} error rule violations:\n"
            for err in self.errors:
                msg += f"  - [{err.rule}] {err.column or 'general'}: {err.message}\n"
        return msg


class SchemaValidator:
    """
    Validates DataFrames and CSV files directly against the authoritative
    YAML schemas defined in schemas/*.schema.yaml.
    """

    def __init__(self, schema_loader: Optional[SchemaLoader] = None):
        self.loader = schema_loader if schema_loader is not None else SchemaLoader()

    def validate_dataset(
        self,
        dataset_name: str,
        data: Union[pd.DataFrame, List[Dict[str, Any]]],
        registry_data: Optional[pd.DataFrame] = None,
    ) -> ValidationResult:
        """
        Validates a dataset against its YAML schema contract.

        Parameters
        ----------
        dataset_name : str
            Name of domain (e.g. 'electrical_measurements')
        data : pd.DataFrame or list of dicts
            Dataset to validate
        registry_data : pd.DataFrame, optional
            meter_registry DataFrame for foreign key referential integrity checks

        Returns
        -------
        ValidationResult
        """
        schema = self.loader.load_schema(dataset_name)
        fields_schema = schema.get("fields", {})
        primary_keys = schema.get("primary_key", [])
        foreign_keys = schema.get("foreign_keys", [])

        if isinstance(data, list):
            df = pd.DataFrame(data)
        else:
            df = data.copy()

        errors: List[ValidationErrorDetail] = []
        warnings: List[str] = []
        total_records = len(df)

        # 1. Structural Check: Required and unexpected columns
        actual_cols = set(df.columns)
        for col_name, field_def in fields_schema.items():
            if field_def.get("required", True) and col_name not in actual_cols:
                errors.append(
                    ValidationErrorDetail(
                        domain=dataset_name,
                        column=col_name,
                        rule="required_column",
                        message=f"Missing required column '{col_name}'",
                    )
                )

        unexpected_cols = actual_cols - set(fields_schema.keys())
        if unexpected_cols:
            warnings.append(f"Found unexpected columns not in schema: {sorted(unexpected_cols)}")

        # 2. Nullability Check
        for col_name, field_def in fields_schema.items():
            if col_name in df.columns:
                is_nullable = field_def.get("nullable", False)
                null_count = df[col_name].isna().sum()
                if not is_nullable and null_count > 0:
                    sample_ids = []
                    if "record_id" in df.columns:
                        sample_ids = df[df[col_name].isna()]["record_id"].head(5).tolist()
                    elif "meter_id" in df.columns:
                        sample_ids = df[df[col_name].isna()]["meter_id"].head(5).tolist()

                    errors.append(
                        ValidationErrorDetail(
                            domain=dataset_name,
                            column=col_name,
                            rule="nullability",
                            message=f"Column '{col_name}' is non-nullable but contains {null_count} nulls",
                            sample_records=sample_ids,
                        )
                    )

        # 3. Categorical Allowed Values Check
        for col_name, field_def in fields_schema.items():
            if col_name in df.columns and "allowed_values" in field_def:
                allowed = set(field_def["allowed_values"])
                non_null_series = df[col_name].dropna()
                invalid_mask = ~non_null_series.isin(allowed)
                if invalid_mask.any():
                    invalid_vals = non_null_series[invalid_mask].unique()[:5].tolist()
                    errors.append(
                        ValidationErrorDetail(
                            domain=dataset_name,
                            column=col_name,
                            rule="allowed_values",
                            message=f"Column '{col_name}' contains unpermitted values: {invalid_vals}. Allowed: {sorted(allowed)}",
                            sample_records=invalid_vals,
                        )
                    )

        # 4. Range Bounds (min / max) Check
        for col_name, field_def in fields_schema.items():
            if col_name in df.columns:
                c_min = field_def.get("min")
                c_max = field_def.get("max")
                if c_min is not None or c_max is not None:
                    series = pd.to_numeric(df[col_name], errors="coerce").dropna()
                    if c_min is not None:
                        below = series < c_min
                        if below.any():
                            errors.append(
                                ValidationErrorDetail(
                                    domain=dataset_name,
                                    column=col_name,
                                    rule="range_min",
                                    message=f"Column '{col_name}' has values below minimum {c_min} (min observed: {series.min()})",
                                )
                            )
                    if c_max is not None:
                        above = series > c_max
                        if above.any():
                            errors.append(
                                ValidationErrorDetail(
                                    domain=dataset_name,
                                    column=col_name,
                                    rule="range_max",
                                    message=f"Column '{col_name}' has values above maximum {c_max} (max observed: {series.max()})",
                                )
                            )

        # 5. Regex Format Check (e.g. meter_id pattern)
        for col_name, field_def in fields_schema.items():
            if col_name in df.columns and "format" in field_def:
                pattern = field_def["format"]
                if pattern.startswith("MS212"):
                    series = df[col_name].dropna().astype(str)
                    mismatch = ~series.str.match(pattern)
                    if mismatch.any():
                        bad_samples = series[mismatch].head(3).tolist()
                        errors.append(
                            ValidationErrorDetail(
                                domain=dataset_name,
                                column=col_name,
                                rule="format_pattern",
                                message=f"Column '{col_name}' has values not matching pattern '{pattern}': {bad_samples}",
                                sample_records=bad_samples,
                            )
                        )

        # 6. Primary Key Uniqueness Check
        if primary_keys and all(pk in df.columns for pk in primary_keys):
            dup_count = df.duplicated(subset=primary_keys).sum()
            if dup_count > 0:
                dup_samples = df[df.duplicated(subset=primary_keys, keep=False)][primary_keys].head(5).to_dict("records")
                errors.append(
                    ValidationErrorDetail(
                        domain=dataset_name,
                        column=",".join(primary_keys),
                        rule="primary_key_uniqueness",
                        message=f"Primary key {primary_keys} has {dup_count} duplicate records",
                        sample_records=dup_samples,
                    )
                )

        # 7. Foreign Key Referential Integrity Check
        if registry_data is not None and "meter_id" in df.columns and "meter_id" in registry_data.columns:
            valid_meters = set(registry_data["meter_id"])
            obs_meters = set(df["meter_id"].dropna())
            orphans = obs_meters - valid_meters
            if orphans:
                errors.append(
                    ValidationErrorDetail(
                        domain=dataset_name,
                        column="meter_id",
                        rule="referential_integrity",
                        message=f"Foreign key 'meter_id' contains {len(orphans)} orphan meter IDs not in registry",
                        sample_records=sorted(list(orphans))[:5],
                    )
                )

        is_valid = len(errors) == 0
        return ValidationResult(
            domain=dataset_name,
            is_valid=is_valid,
            total_records=total_records,
            errors=errors,
            warnings=warnings,
        )


def validate_dataset(
    dataset_name: str,
    data: Union[pd.DataFrame, List[Dict[str, Any]]],
    registry_data: Optional[pd.DataFrame] = None,
) -> ValidationResult:
    """Helper function to validate a single dataset against its YAML contract."""
    validator = SchemaValidator()
    return validator.validate_dataset(dataset_name, data, registry_data=registry_data)


def validate_all_datasets(
    structured_dir: Optional[Path] = None,
    sample_size: Optional[int] = None,
) -> Dict[str, ValidationResult]:
    """
    Validates all 7 structured CSV domain files against their respective YAML schemas.
    """
    target_dir = Path(structured_dir) if structured_dir is not None else STRUCTURED_DATA_DIR
    validator = SchemaValidator()
    results: Dict[str, ValidationResult] = {}

    reg_path = target_dir / "meter_registry.csv"
    reg_df = pd.read_csv(reg_path) if reg_path.exists() else None

    domains = [
        "meter_registry",
        "energy_registers",
        "electrical_measurements",
        "meter_events",
        "device_status",
        "communications",
        "labels",
    ]

    for domain in domains:
        meta = DOMAIN_CATALOG[domain]
        csv_file = target_dir / meta["filename"]
        if not csv_file.exists():
            results[domain] = ValidationResult(
                domain=domain,
                is_valid=False,
                total_records=0,
                errors=[
                    ValidationErrorDetail(
                        domain=domain,
                        column=None,
                        rule="file_exists",
                        message=f"CSV file {csv_file} does not exist",
                    )
                ],
            )
            continue

        if sample_size is not None and meta["is_observation_level"]:
            df = pd.read_csv(csv_file, nrows=sample_size, low_memory=False)
        else:
            df = pd.read_csv(csv_file, low_memory=False)

        res = validator.validate_dataset(
            dataset_name=domain,
            data=df,
            registry_data=reg_df if domain != "meter_registry" else None,
        )
        results[domain] = res

    return results


# ── Preserved Original DataIntegrityValidator ────────────────────────────────
class DataIntegrityValidator:
    """
    Executes 8 core validation protocols:
    1. Row counts across all files
    2. Column schemas and ordering
    3. record_id uniqueness across observation tables
    4. meter_id referential integrity against meter_registry
    5. Missing-value preservation (null counts parity)
    6. Value-by-value equality between raw and reconstructed datasets
    7. No unexpected duplicate records
    8. Timestamp alignment across observation domains
    """

    def __init__(
        self,
        raw_csv_path: Optional[Path] = None,
        structured_dir: Optional[Path] = None,
    ):
        if raw_csv_path is not None:
            self.raw_csv_path = Path(raw_csv_path)
        elif PRIMARY_RAW_CSV.exists():
            self.raw_csv_path = PRIMARY_RAW_CSV
        elif FALLBACK_RAW_CSV.exists():
            self.raw_csv_path = FALLBACK_RAW_CSV
        else:
            raise FileNotFoundError("Raw dataset not found.")

        self.structured_dir = (
            Path(structured_dir) if structured_dir is not None else STRUCTURED_DATA_DIR
        )

    def validate_all(self) -> Dict[str, Any]:
        """
        Executes all 8 integrity checks and returns a detailed report.
        """
        report: Dict[str, Any] = {
            "checks": {},
            "all_passed": True,
            "summary": [],
        }

        logger.info(f"Loading raw data for validation: {self.raw_csv_path}")
        df_raw = pd.read_csv(self.raw_csv_path, low_memory=False)
        raw_rows, raw_cols = df_raw.shape

        reconstructor = DatasetReconstructor(self.structured_dir)
        df_recon = reconstructor.reconstruct()

        domain_dfs: Dict[str, pd.DataFrame] = {}
        for d, meta in DOMAIN_CATALOG.items():
            path = self.structured_dir / meta["filename"]
            domain_dfs[d] = pd.read_csv(path, low_memory=False)

        # ── 1. Row Counts Check ───────────────────────────────────────────────
        row_counts_pass = True
        row_counts_detail = {
            "raw_rows": raw_rows,
            "reconstructed_rows": len(df_recon),
            "registry_rows": len(domain_dfs["meter_registry"]),
            "expected_registry_rows": len(df_raw["meter_id"].unique()),
        }

        if len(df_recon) != raw_rows:
            row_counts_pass = False
        if len(domain_dfs["meter_registry"]) != len(df_raw["meter_id"].unique()):
            row_counts_pass = False

        for d, meta in DOMAIN_CATALOG.items():
            if meta["is_observation_level"]:
                count = len(domain_dfs[d])
                row_counts_detail[f"{d}_rows"] = count
                if count != raw_rows:
                    row_counts_pass = False

        report["checks"]["1_row_counts"] = {
            "passed": row_counts_pass,
            "details": row_counts_detail,
        }

        # ── 2. Column Schemas & Ordering Check ────────────────────────────────
        schema_pass = True
        schema_detail = {}

        cols_match = list(df_recon.columns) == ORIGINAL_COLUMNS
        schema_detail["reconstructed_columns_exact_match"] = cols_match
        if not cols_match:
            schema_pass = False

        for d, meta in DOMAIN_CATALOG.items():
            actual_cols = list(domain_dfs[d].columns)
            expected_cols = meta["columns"]
            match = actual_cols == expected_cols
            schema_detail[f"{d}_columns_match"] = match
            if not match:
                schema_pass = False

        report["checks"]["2_column_schemas"] = {
            "passed": schema_pass,
            "details": schema_detail,
        }

        # ── 3. record_id Uniqueness Check ─────────────────────────────────────
        record_id_pass = True
        record_id_detail = {}

        for d, meta in DOMAIN_CATALOG.items():
            if meta["is_observation_level"]:
                df = domain_dfs[d]
                total = len(df)
                unique = df["record_id"].nunique()
                is_unique = (total == unique)
                record_id_detail[f"{d}_unique"] = is_unique
                if not is_unique:
                    record_id_pass = False

        report["checks"]["3_record_id_uniqueness"] = {
            "passed": record_id_pass,
            "details": record_id_detail,
        }

        # ── 4. meter_id Referential Integrity ─────────────────────────────────
        ref_pass = True
        registry_meters = set(domain_dfs["meter_registry"]["meter_id"])
        ref_detail = {"registered_meters_count": len(registry_meters)}

        for d, meta in DOMAIN_CATALOG.items():
            if meta["is_observation_level"]:
                obs_meters = set(domain_dfs[d]["meter_id"])
                orphans = obs_meters - registry_meters
                is_valid = len(orphans) == 0
                ref_detail[f"{d}_orphans"] = len(orphans)
                if not is_valid:
                    ref_pass = False

        report["checks"]["4_referential_integrity"] = {
            "passed": ref_pass,
            "details": ref_detail,
        }

        # ── 5. Missing-Value Preservation Check ───────────────────────────────
        null_pass = True
        null_detail = {}

        raw_nulls = df_raw.isna().sum().to_dict()
        recon_nulls = df_recon.isna().sum().to_dict()

        null_parity = (raw_nulls == recon_nulls)
        null_detail["raw_recon_null_parity"] = null_parity
        if not null_parity:
            null_pass = False

        for d, meta in DOMAIN_CATALOG.items():
            df = domain_dfs[d]
            for col in meta["columns"]:
                raw_col_nulls = df_raw[col].isna().sum() if col in df_raw.columns else 0
                if meta["is_observation_level"]:
                    domain_col_nulls = df[col].isna().sum()
                    if raw_col_nulls != domain_col_nulls:
                        null_pass = False
                        null_detail[f"{d}.{col}_null_mismatch"] = (raw_col_nulls, domain_col_nulls)

        null_detail["total_raw_nulls"] = int(df_raw.isna().sum().sum())
        null_detail["total_recon_nulls"] = int(df_recon.isna().sum().sum())
        report["checks"]["5_null_preservation"] = {
            "passed": null_pass,
            "details": null_detail,
        }

        # ── 6. Value-by-Value Equality Check ──────────────────────────────────
        equality_pass = True
        equality_detail = {}

        for col in ORIGINAL_COLUMNS:
            s_raw = df_raw[col]
            s_recon = df_recon[col]

            if pd.api.types.is_numeric_dtype(s_raw) or pd.api.types.is_numeric_dtype(s_recon):
                diff = np.abs(pd.to_numeric(s_raw, errors="coerce") - pd.to_numeric(s_recon, errors="coerce"))
                max_diff = float(np.nanmax(diff)) if not diff.isna().all() else 0.0
                nans_match = (s_raw.isna() == s_recon.isna()).all()
                matches = (max_diff < 1e-9) and bool(nans_match)
                if not matches:
                    equality_pass = False
                    equality_detail[col] = f"Numeric mismatch: max_diff={max_diff}, nans_match={nans_match}"
            else:
                matches = ((s_raw == s_recon) | (s_raw.isna() & s_recon.isna())).all()
                if not matches:
                    equality_pass = False
                    equality_detail[col] = "Categorical / string mismatch detected"

        equality_detail["all_33_columns_identical"] = equality_pass
        report["checks"]["6_value_equality"] = {
            "passed": equality_pass,
            "details": equality_detail,
        }

        # ── 7. Duplicate Records Check ────────────────────────────────────────
        dup_pass = True
        dup_detail = {}

        for d, df in domain_dfs.items():
            if d == "meter_registry":
                dups = df.duplicated(subset=["meter_id"]).sum()
            else:
                dups = df.duplicated(subset=["record_id"]).sum()
            dup_detail[f"{d}_duplicates"] = int(dups)
            if dups > 0:
                dup_pass = False

        report["checks"]["7_duplicate_detection"] = {
            "passed": dup_pass,
            "details": dup_detail,
        }

        # ── 8. Timestamp Consistency Check ────────────────────────────────────
        ts_pass = True
        ts_detail = {}
        ref_ts = domain_dfs["energy_registers"]["event_timestamp"]

        for d, meta in domain_dfs.items():
            if DOMAIN_CATALOG[d]["is_observation_level"]:
                cur_ts = domain_dfs[d]["event_timestamp"]
                match = (cur_ts == ref_ts).all()
                ts_detail[f"{d}_timestamp_match"] = bool(match)
                if not match:
                    ts_pass = False

        report["checks"]["8_timestamp_alignment"] = {
            "passed": ts_pass,
            "details": ts_detail,
        }

        all_passed = all(c["passed"] for c in report["checks"].values())
        report["all_passed"] = all_passed
        return report

    def generate_markdown_report(self) -> str:
        """
        Runs validation and returns a formatted Markdown report.
        """
        res = self.validate_all()
        status_symbol = "PASSED (ALL VERIFIED)" if res["all_passed"] else "FAILED"

        lines = [
            "# EnergyMind Tunisia — Data Architecture Integrity Report",
            f"**Overall Status:** {status_symbol}\n",
            "| Check ID | Integrity Check Description | Status | Details |",
            "|---|---|---|---|",
        ]

        check_titles = {
            "1_row_counts": "1. Row Counts Verification",
            "2_column_schemas": "2. Column Schemas & Sequence",
            "3_record_id_uniqueness": "3. Primary Key (record_id) Uniqueness",
            "4_referential_integrity": "4. Foreign Key (meter_id) Referential Integrity",
            "5_null_preservation": "5. Missing Value & Null Parity",
            "6_value_equality": "6. Exact Value-by-Value Equality",
            "7_duplicate_detection": "7. Duplicate Record Detection",
            "8_timestamp_alignment": "8. Cross-Domain Timestamp Alignment",
        }

        for k, info in res["checks"].items():
            status = "PASS" if info["passed"] else "**FAIL**"
            title = check_titles.get(k, k)
            details = ", ".join(f"{dk}: {dv}" for dk, dv in list(info["details"].items())[:4])
            lines.append(f"| {k} | {title} | {status} | {details} |")

        return "\n".join(lines)
