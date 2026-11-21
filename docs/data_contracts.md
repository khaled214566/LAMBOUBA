# EnergyMind Tunisia — Developer Guide: Data Contracts & Schemas

Welcome to the **EnergyMind Tunisia** data schema and contract system. This guide enables developers, data engineers, and ML researchers to understand, query, validate, and extend smart-grid telemetry data.

---

## 1. What is a Data Contract in EnergyMind?

A **Data Contract** in EnergyMind is an authoritative agreement between telemetry generation/ingestion and downstream consumers (monitoring dashboards, ML models, billing engines). 

Contracts are version-controlled in `schemas/` as declarative YAML files:
- **Single Source of Truth:** `schemas/*.schema.yaml` defines the exact fields, data types, physical units, allowed values, nullability, and keys.
- **Python Models:** `src/data/models.py` provides Pydantic V2 models derived from these schemas.
- **Validation Engine:** `src/data/validator.py` enforces contract compliance on any DataFrame or CSV file.

---

## 2. Where are Schemas Located?

```
schemas/
├── schema_version.yaml              <- Project versioning policy & active versions
├── relationships.yaml               <- Cross-domain topology & foreign key rules
├── meter_registry.schema.yaml       <- 50-meter static topology metadata
├── energy_registers.schema.yaml     <- 4-quadrant cumulative energy & tariffs
├── electrical_measurements.schema.yaml <- Instantaneous V, f, neutral current
├── meter_events.schema.yaml         <- Tamper switches, grid outage, PF flags
├── device_status.schema.yaml        <- Breaker relay & DLMS health diagnostics
├── communications.schema.yaml       <- Telemetry uplink channels & latency
└── labels.schema.yaml               <- Ground-truth supervised fault classes
```

---

## 3. How to Discover Field Definitions Programmatically

You can inspect contracts directly in Python without digging through CSV files:

```python
from src.data.schema_loader import get_schema, SchemaLoader

# 1. Load schema for electrical measurements
schema = get_schema("electrical_measurements")
print(f"Domain Owner: {schema['owner']}")
print(f"Primary Key: {schema['primary_key']}")

# 2. Inspect a specific column's contract
loader = SchemaLoader()
voltage_field = loader.get_field_definition("electrical_measurements", "voltage_V")
print(voltage_field)
# Output:
# {
#   'type': 'float',
#   'unit': 'V',
#   'required': True,
#   'nullable': True,
#   'min': 0.0,
#   'max': 1200.0,
#   'description': 'RMS voltage at meter terminals (STEG nominal 230 V)...'
# }
```

---

## 4. How to Validate a Dataset Against Its Contract

Use `validate_dataset` to ensure any new dataframe complies with the contract before passing it to ML models:

```python
import pandas as pd
from src.data.validator import validate_dataset

# Load some data to test
df_sample = pd.read_csv("data/realistic/structured/electrical_measurements.csv", nrows=500)

# Validate
result = validate_dataset("electrical_measurements", df_sample)

if result.is_valid:
    print(f"Success! {result.total_records} records are 100% compliant.")
else:
    print("Contract violations detected:")
    for err in result.errors:
        print(f"  - [{err.rule}] Field '{err.column}': {err.message}")
```

To validate all 7 domains in one command:
```python
from src.data.validator import validate_all_datasets

results = validate_all_datasets(sample_size=1000)
for domain, res in results.items():
    print(res.summary_message())
```

---

## 5. How to Load Data Selectively for Machine Learning

Do not load all 33 columns simultaneously. Use the `NeighborhoodDataLoader`:

```python
from src.data.loader import NeighborhoodDataLoader

loader = NeighborhoodDataLoader()

# Example A: Power Quality Anomaly Detection
# Loads only voltage, frequency, neutral current, and energy deltas
df_pq = loader.load_for_electrical_anomaly_monitoring(
    meter_ids=["MS212-TN-0001", "MS212-TN-0002"]
)

# Example B: Energy Forecasting for a specific Feeder
df_energy = loader.load_for_energy_monitoring(
    feeder_ids=["feeder_01"],
    start_time="2026-11-13T00:00:00",
    end_time="2026-11-15T23:59:59"
)

# Example C: Non-Technical Loss (Theft) Detection
# Automatically quaratines labels unless explicitly requested
df_theft = loader.load_for_tampering_detection(
    include_status=True,
    include_labels=False
)
```

---

## 6. How to Add a New Field or Domain

When updating the data contract:
1. **Edit Schema YAML:** Add the field definition to `schemas/<domain>.schema.yaml` with description, data type, unit, and constraints.
2. **Update Pydantic Model:** Add the field to the corresponding model class in `src/data/models.py`.
3. **Bump Version:** Update `schemas/schema_version.yaml` adhering to `docs/schema_versioning.md`.
4. **Run Tests:** Verify with `pytest tests/data/ -v`.
