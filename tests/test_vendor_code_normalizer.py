"""Vendor code normalization rules."""

import pickle

from vendor_code_normalizer import (
    FAMILY_TABLE,
    HEX_TABLE,
    normalize,
    rule_family,
)


def test_freeform_prefixes_route_by_shape():
    assert normalize("SignalWeak:11/JIO 4G Jio/FDD LTE/0", "OtherError") == "WeakSignal"
    assert normalize("WeakSignal detected", None) == "WeakSignal"
    assert normalize("GroundFailure trip", "OtherError") == "GroundFailure"
    assert normalize("OverVoltage L2", None) == "OverVoltage"


def test_system_err_codes_keep_the_export_category():
    assert normalize("system-err1051", "system-err1051") == "system-err1051"
    assert normalize("system-err1024", "EVCommunicationError") == "EVCommunicationError"


def test_hex_codes_fall_back_until_taxonomy_lands_then_route():
    assert normalize("0x3A21", "GroundFailure") == "GroundFailure"  # empty table -> fallback
    HEX_TABLE["0x3a21"] = "GroundFailure"
    try:
        assert normalize("0x3A21", "OtherError") == "GroundFailure"  # table wins
    finally:
        HEX_TABLE.clear()


def test_structured_families_recognized_and_fall_back():
    for code, family in [("ER104", "er_num"), ("C42", "c_num"),
                         ("12-345", "num_num"), ("Alarm3-Err7", "alarm_err"),
                         ("0xDEAD", "hex")]:
        assert rule_family(code) == family
    assert normalize("ER104", "UnderVoltage") == "UnderVoltage"
    FAMILY_TABLE["ER104"] = "OverVoltage"
    try:
        assert normalize("ER104", "UnderVoltage") == "OverVoltage"
    finally:
        FAMILY_TABLE.clear()


def test_voltage_reading_uses_error_code_direction():
    assert normalize("R:63.9V", "UnderVoltage") == "UnderVoltage"
    assert normalize("R:263.9V", "OverVoltage") == "OverVoltage"
    assert normalize("R:63.9V", "OtherError") == "OtherError"  # directionless


def test_empty_inputs_and_fallbacks():
    assert normalize(None, None) == "OtherError"
    assert normalize("", "PowerMeterFailure") == "PowerMeterFailure"
    assert normalize("odd string nobody mapped", "InternalError") == "InternalError"
    assert rule_family("odd string nobody mapped") == "freeform-unrouted"
