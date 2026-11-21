"""
Integrity Verification Tests
"""

import pytest
from src.data.validator import DataIntegrityValidator


def test_full_data_integrity():
    """Execute all 8 integrity checks and assert 100% pass."""
    validator = DataIntegrityValidator()
    report = validator.validate_all()

    for check_name, info in report["checks"].items():
        assert info["passed"], f"Integrity check {check_name} failed: {info['details']}"

    assert report["all_passed"] is True
