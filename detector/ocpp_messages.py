"""Typed schemas for the four OCPP 1.6 message types the detector consumes.

Field names follow the anonymized CMS export columns (see data/sql/*.sql), not
the raw OCPP 1.6 wire format: charge box ids arrive pre-hashed and customer/RFID
fields were dropped at export time.
"""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel


class ChargePointStatus(str, Enum):
    AVAILABLE = "Available"
    PREPARING = "Preparing"
    CHARGING = "Charging"
    SUSPENDED_EVSE = "SuspendedEVSE"
    SUSPENDED_EV = "SuspendedEV"
    FINISHING = "Finishing"
    RESERVED = "Reserved"
    UNAVAILABLE = "Unavailable"
    FAULTED = "Faulted"
    # Non-standard statuses observed in the export:
    REMOTE_START_REQUESTED = "RemoteStartRequested"
    REMOTE_STOP_REQUESTED = "RemoteStopRequested"


class StatusNotification(BaseModel):
    connector_pk: int
    status: ChargePointStatus
    # Free text, not an enum: alongside OCPP codes (NoError, OtherError,
    # EVCommunicationError, PowerMeterFailure, UnderVoltage...) the export
    # contains vendor strings like "Transaction Stopped" and
    # "Available after Finishing Status", plus system-err1051 / system-err1024.
    error_code: str
    # Real fleet streams carry the system-err* codes HERE with
    # error_code=OtherError (fixtures had them in error_code — schema
    # difference found on the real sequence export, audit flag 23).
    vendor_error_code: str | None = None
    timestamp: datetime


class MeterValues(BaseModel):
    transaction_pk: int
    connector_pk: int
    meter_reading_wh: float
    timestamp: datetime


class StartTransaction(BaseModel):
    transaction_pk: int
    connector_pk: int
    start_timestamp: datetime


class StopTransaction(BaseModel):
    transaction_pk: int
    connector_pk: int
    stop_timestamp: datetime
    stop_reason: str
