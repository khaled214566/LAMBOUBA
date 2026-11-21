"""
EnergyMind Tunisia — Relational Database Management Layer
==========================================================
High-performance relational SQLite engine (WAL Mode, ACID compliance)
mirroring the 7 domain schemas with foreign key enforcement, B-Tree indexes,
telemetry views, and incident audit logging.
"""

import logging
from pathlib import Path
import sqlite3
from typing import Any, Dict, List, Optional, Tuple, Union

import pandas as pd

from src.data.config import (
    DATABASE_PATH,
    DOMAIN_CATALOG,
    STRUCTURED_DATA_DIR,
)

logger = logging.getLogger(__name__)


class EnergyMindDatabase:
    """
    Relational SQLite database manager for EnergyMind Tunisia.
    Operates in WAL (Write-Ahead Logging) mode with foreign keys enabled.
    """

    def __init__(
        self,
        db_path: Optional[Path] = None,
        structured_dir: Optional[Path] = None,
    ):
        self.db_path = Path(db_path) if db_path is not None else DATABASE_PATH
        self.structured_dir = Path(structured_dir) if structured_dir is not None else STRUCTURED_DATA_DIR
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    def get_connection(self) -> sqlite3.Connection:
        """
        Creates and configures an optimized SQLite connection.
        """
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.execute("PRAGMA synchronous = NORMAL;")
        conn.execute("PRAGMA cache_size = -64000;")  # 64 MB cache
        return conn

    def create_schema(self) -> None:
        """
        Initializes relational tables, indexes, and views strictly conforming
        to the 7 domain contracts and incident governance specification.
        """
        logger.info(f"Initializing database schema at {self.db_path}...")
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # 1. Meter Registry (Static Metadata)
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS meter_registry (
                meter_id TEXT PRIMARY KEY,
                feeder_id TEXT NOT NULL,
                phase TEXT NOT NULL,
                distance_from_transformer_m REAL NOT NULL,
                household_type TEXT NOT NULL
            );
            """)

            # 2. Energy Registers (Cumulative kWh/kvarh)
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS energy_registers (
                record_id INTEGER PRIMARY KEY,
                meter_id TEXT NOT NULL,
                event_timestamp TEXT NOT NULL,
                active_import_kWh REAL NOT NULL,
                active_export_kWh REAL NOT NULL,
                reactive_Q1_kvarh REAL NOT NULL,
                reactive_Q2_kvarh REAL NOT NULL,
                reactive_Q3_kvarh REAL NOT NULL,
                reactive_Q4_kvarh REAL NOT NULL,
                tariff_register TEXT NOT NULL,
                FOREIGN KEY (meter_id) REFERENCES meter_registry (meter_id) ON DELETE RESTRICT
            );
            """)

            # 3. Electrical Measurements (Instantaneous V, f, In)
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS electrical_measurements (
                record_id INTEGER PRIMARY KEY,
                meter_id TEXT NOT NULL,
                event_timestamp TEXT NOT NULL,
                voltage_V REAL,
                frequency_Hz REAL,
                neutral_current_A REAL,
                FOREIGN KEY (meter_id) REFERENCES meter_registry (meter_id) ON DELETE RESTRICT
            );
            """)

            # 4. Meter Events (Tamper Switches & Power Quality Flags)
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS meter_events (
                record_id INTEGER PRIMARY KEY,
                meter_id TEXT NOT NULL,
                event_timestamp TEXT NOT NULL,
                voltage_interruptions INTEGER NOT NULL,
                voltage_restorations INTEGER NOT NULL,
                power_factor_variation_detected INTEGER NOT NULL,
                magnetic_field_detected INTEGER NOT NULL,
                top_cover_opened INTEGER NOT NULL,
                terminal_cover_opened INTEGER NOT NULL,
                io_swap INTEGER NOT NULL,
                phase_neutral_swap INTEGER NOT NULL,
                mains_power_cut INTEGER NOT NULL,
                neutral_disturbance INTEGER NOT NULL,
                FOREIGN KEY (meter_id) REFERENCES meter_registry (meter_id) ON DELETE RESTRICT
            );
            """)

            # 5. Device Status (Breaker Relay & Diagnostics)
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS device_status (
                record_id INTEGER PRIMARY KEY,
                meter_id TEXT NOT NULL,
                event_timestamp TEXT NOT NULL,
                breaker_state TEXT NOT NULL,
                auto_diagnostic TEXT NOT NULL,
                quality_flags INTEGER NOT NULL,
                FOREIGN KEY (meter_id) REFERENCES meter_registry (meter_id) ON DELETE RESTRICT
            );
            """)

            # 6. Communications (Gateway Ingestion & Protocols)
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS communications (
                record_id INTEGER PRIMARY KEY,
                meter_id TEXT NOT NULL,
                event_timestamp TEXT NOT NULL,
                ingest_timestamp TEXT NOT NULL,
                comm_channel TEXT NOT NULL,
                FOREIGN KEY (meter_id) REFERENCES meter_registry (meter_id) ON DELETE RESTRICT
            );
            """)

            # 7. Labels (Quarantined Ground Truth Target)
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS labels (
                record_id INTEGER PRIMARY KEY,
                meter_id TEXT NOT NULL,
                event_timestamp TEXT NOT NULL,
                label TEXT NOT NULL,
                FOREIGN KEY (meter_id) REFERENCES meter_registry (meter_id) ON DELETE RESTRICT
            );
            """)

            # 8. Forensic Audit & Incident Governance Log
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS incident_audit_log (
                audit_id INTEGER PRIMARY KEY AUTOINCREMENT,
                record_id INTEGER NOT NULL,
                meter_id TEXT NOT NULL,
                incident_timestamp TEXT NOT NULL,
                verdict TEXT NOT NULL,
                confidence REAL NOT NULL,
                status TEXT NOT NULL DEFAULT 'NEW',
                operator_notes TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (record_id) REFERENCES electrical_measurements (record_id),
                FOREIGN KEY (meter_id) REFERENCES meter_registry (meter_id)
            );
            """)

            # ── High-Performance B-Tree Indexes ──────────────────────────────
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_reg_feeder ON meter_registry (feeder_id);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_en_meter_time ON energy_registers (meter_id, event_timestamp);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_elec_meter_time ON electrical_measurements (meter_id, event_timestamp);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_events_meter_time ON meter_events (meter_id, event_timestamp);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_dev_meter_time ON device_status (meter_id, event_timestamp);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_comm_meter_time ON communications (meter_id, event_timestamp);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_lbl_meter_time ON labels (meter_id, event_timestamp);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_lbl_label ON labels (label);")

            # ── Fast Analytical Views ────────────────────────────────────────
            cursor.execute("DROP VIEW IF EXISTS v_active_telemetry;")
            cursor.execute("""
            CREATE VIEW v_active_telemetry AS
            SELECT 
                r.meter_id,
                r.feeder_id,
                r.phase,
                r.distance_from_transformer_m,
                r.household_type,
                e.record_id,
                e.event_timestamp,
                e.voltage_V,
                e.frequency_Hz,
                e.neutral_current_A,
                en.active_import_kWh,
                en.active_export_kWh,
                en.reactive_Q1_kvarh,
                en.reactive_Q4_kvarh,
                en.tariff_register,
                d.breaker_state,
                d.auto_diagnostic,
                d.quality_flags
            FROM electrical_measurements e
            JOIN meter_registry r ON e.meter_id = r.meter_id
            JOIN energy_registers en ON e.record_id = en.record_id
            JOIN device_status d ON e.record_id = d.record_id;
            """)

            cursor.execute("DROP VIEW IF EXISTS v_tamper_incidents;")
            cursor.execute("""
            CREATE VIEW v_tamper_incidents AS
            SELECT 
                ev.record_id,
                ev.meter_id,
                r.feeder_id,
                r.phase,
                ev.event_timestamp,
                ev.magnetic_field_detected,
                ev.top_cover_opened,
                ev.terminal_cover_opened,
                ev.io_swap,
                ev.phase_neutral_swap,
                ev.neutral_disturbance,
                lbl.label
            FROM meter_events ev
            JOIN meter_registry r ON ev.meter_id = r.meter_id
            JOIN labels lbl ON ev.record_id = lbl.record_id
            WHERE ev.magnetic_field_detected = 1
               OR ev.top_cover_opened = 1
               OR ev.terminal_cover_opened = 1
               OR ev.io_swap = 1
               OR ev.phase_neutral_swap = 1
               OR ev.neutral_disturbance = 1;
            """)

            conn.commit()
            logger.info("Database schema, indexes, and views successfully created.")

    def populate_from_csv(self, batch_size: int = 50000, overwrite: bool = False) -> Dict[str, int]:
        """
        Populates database tables from data/realistic/structured/*.csv files
        using high-throughput transactional batch inserts.
        """
        self.create_schema()
        table_counts: Dict[str, int] = {}

        with self.get_connection() as conn:
            # Check if meter_registry already populated
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM meter_registry;")
            existing_count = cursor.fetchone()[0]

            if existing_count > 0 and not overwrite:
                logger.info(f"Database already populated ({existing_count} meters). Skipping insertion.")
                for domain in DOMAIN_CATALOG.keys():
                    cursor.execute(f"SELECT COUNT(*) FROM {domain};")
                    table_counts[domain] = cursor.fetchone()[0]
                return table_counts

            if overwrite:
                logger.info("Overwrite requested. Clearing existing tables...")
                for domain in reversed(list(DOMAIN_CATALOG.keys())):
                    cursor.execute(f"DELETE FROM {domain};")
                conn.commit()

            # 1. Populate meter_registry first (Parent FK table)
            logger.info("Populating meter_registry...")
            reg_meta = DOMAIN_CATALOG["meter_registry"]
            df_reg = pd.read_csv(self.structured_dir / reg_meta["filename"])
            df_reg.to_sql("meter_registry", conn, if_exists="append", index=False)
            table_counts["meter_registry"] = len(df_reg)

            # 2. Populate 6 observation tables
            observation_domains = [
                d for d, m in DOMAIN_CATALOG.items() if m["is_observation_level"]
            ]

            for domain in observation_domains:
                meta = DOMAIN_CATALOG[domain]
                csv_path = self.structured_dir / meta["filename"]
                logger.info(f"Populating table '{domain}' from {csv_path.name}...")

                total_rows = 0
                for chunk in pd.read_csv(csv_path, chunksize=batch_size, low_memory=False):
                    chunk.to_sql(domain, conn, if_exists="append", index=False)
                    total_rows += len(chunk)

                table_counts[domain] = total_rows
                logger.info(f"  ✓ Inserted {total_rows:,} rows into {domain}")

            conn.commit()

        logger.info("Database population complete.")
        return table_counts

    def query(self, sql: str, params: Optional[Tuple] = None) -> pd.DataFrame:
        """
        Executes a SQL query and returns results as a pandas DataFrame.
        """
        with self.get_connection() as conn:
            if params is None:
                return pd.read_sql_query(sql, conn)
            return pd.read_sql_query(sql, conn, params=params)

    def query_meter_telemetry(
        self,
        meter_id: str,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> pd.DataFrame:
        """
        Queries unified telemetry for a single meter over time via v_active_telemetry.
        """
        conditions = ["meter_id = ?"]
        params: List[Any] = [meter_id]

        if start_time is not None:
            conditions.append("event_timestamp >= ?")
            params.append(start_time)
        if end_time is not None:
            conditions.append("event_timestamp <= ?")
            params.append(end_time)

        sql = f"SELECT * FROM v_active_telemetry WHERE {' AND '.join(conditions)} ORDER BY event_timestamp ASC"
        if limit is not None:
            sql += f" LIMIT {int(limit)}"

        return self.query(sql, tuple(params))

    def query_tamper_incidents(
        self,
        feeder_id: Optional[str] = None,
        limit: Optional[int] = 500,
    ) -> pd.DataFrame:
        """
        Queries active physical and wiring tamper events from v_tamper_incidents.
        """
        sql = "SELECT * FROM v_tamper_incidents"
        params: List[Any] = []

        if feeder_id is not None:
            sql += " WHERE feeder_id = ?"
            params.append(feeder_id)

        sql += " ORDER BY event_timestamp DESC"
        if limit is not None:
            sql += f" LIMIT {int(limit)}"

        return self.query(sql, tuple(params) if params else None)

    def log_incident_verdict(
        self,
        record_id: int,
        meter_id: str,
        incident_timestamp: str,
        verdict: str,
        confidence: float,
        status: str = "NEW",
        operator_notes: Optional[str] = None,
    ) -> int:
        """
        Inserts an ACID forensic audit log entry for a detected anomaly.
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO incident_audit_log (
                    record_id, meter_id, incident_timestamp, verdict, confidence, status, operator_notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?);
                """,
                (record_id, meter_id, incident_timestamp, verdict, confidence, status, operator_notes),
            )
            conn.commit()
            return cursor.lastrowid


def build_database(overwrite: bool = False) -> EnergyMindDatabase:
    """CLI / programmatic helper to initialize and populate database."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    db = EnergyMindDatabase()
    db.populate_from_csv(overwrite=overwrite)
    return db


if __name__ == "__main__":
    build_database(overwrite=False)
