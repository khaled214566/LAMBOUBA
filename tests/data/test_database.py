"""
Unit and Integration Tests for EnergyMindDatabase
"""

import sqlite3
import pytest
import pandas as pd

from src.data.config import DATABASE_PATH
from src.data.database import EnergyMindDatabase


@pytest.fixture(scope="module")
def test_db(tmp_path_factory):
    """Creates a temporary SQLite test database."""
    tmp_dir = tmp_path_factory.mktemp("db_test")
    db_file = tmp_dir / "test_energymind.db"
    db = EnergyMindDatabase(db_path=db_file)
    db.create_schema()
    return db


def test_database_tables_and_views_created(test_db):
    """Verify all 7 domain tables, audit log, and analytical views exist."""
    with test_db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = {row[0] for row in cursor.fetchall()}

        expected_tables = {
            "meter_registry",
            "energy_registers",
            "electrical_measurements",
            "meter_events",
            "device_status",
            "communications",
            "labels",
            "incident_audit_log",
        }
        assert expected_tables.issubset(tables)

        cursor.execute("SELECT name FROM sqlite_master WHERE type='view';")
        views = {row[0] for row in cursor.fetchall()}
        assert {"v_active_telemetry", "v_tamper_incidents"}.issubset(views)


def test_foreign_key_enforcement(test_db):
    """Verify SQLite rejects orphan observations whose meter_id is not registered."""
    with test_db.get_connection() as conn:
        cursor = conn.cursor()
        with pytest.raises(sqlite3.IntegrityError):
            cursor.execute(
                """
                INSERT INTO electrical_measurements (
                    record_id, meter_id, event_timestamp, voltage_V, frequency_Hz, neutral_current_A
                ) VALUES (999999, 'MS212-TN-UNKNOWN', '2026-11-13T00:00:00+00:00', 230.0, 50.0, 0.5);
                """
            )


def test_insert_and_query_views(test_db):
    """Verify insertion and querying through v_active_telemetry view."""
    with test_db.get_connection() as conn:
        cursor = conn.cursor()
        # 1. Insert parent meter
        cursor.execute(
            """
            INSERT INTO meter_registry (meter_id, feeder_id, phase, distance_from_transformer_m, household_type)
            VALUES ('MS212-TN-0001', 'feeder_01', 'L1', 150.0, 'family_home');
            """
        )
        # 2. Insert child records
        cursor.execute(
            """
            INSERT INTO electrical_measurements (record_id, meter_id, event_timestamp, voltage_V, frequency_Hz, neutral_current_A)
            VALUES (1, 'MS212-TN-0001', '2026-11-13T00:00:00+00:00', 229.5, 50.01, 0.45);
            """
        )
        cursor.execute(
            """
            INSERT INTO energy_registers (record_id, meter_id, event_timestamp, active_import_kWh, active_export_kWh, reactive_Q1_kvarh, reactive_Q2_kvarh, reactive_Q3_kvarh, reactive_Q4_kvarh, tariff_register)
            VALUES (1, 'MS212-TN-0001', '2026-11-13T00:00:00+00:00', 100.5, 0.0, 10.2, 0.0, 0.0, 1.1, 'T1');
            """
        )
        cursor.execute(
            """
            INSERT INTO device_status (record_id, meter_id, event_timestamp, breaker_state, auto_diagnostic, quality_flags)
            VALUES (1, 'MS212-TN-0001', '2026-11-13T00:00:00+00:00', 'CLOSED', 'OK', 0);
            """
        )
        conn.commit()

    # Query view via database API
    df = test_db.query_meter_telemetry("MS212-TN-0001")
    assert len(df) == 1
    assert df.iloc[0]["feeder_id"] == "feeder_01"
    assert df.iloc[0]["voltage_V"] == 229.5
    assert df.iloc[0]["breaker_state"] == "CLOSED"


def test_incident_audit_log(test_db):
    """Verify recording and querying forensic incident audit logs."""
    audit_id = test_db.log_incident_verdict(
        record_id=1,
        meter_id="MS212-TN-0001",
        incident_timestamp="2026-11-13T00:00:00+00:00",
        verdict="tamper_magnetic",
        confidence=0.985,
        status="CONFIRMED",
        operator_notes="Strong magnetic field detected by Hall sensor.",
    )
    assert audit_id > 0

    df_audit = test_db.query("SELECT * FROM incident_audit_log WHERE audit_id = ?", (audit_id,))
    assert len(df_audit) == 1
    assert df_audit.iloc[0]["verdict"] == "tamper_magnetic"
    assert df_audit.iloc[0]["confidence"] == 0.985
