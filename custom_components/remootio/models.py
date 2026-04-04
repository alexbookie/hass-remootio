"""Data models for the Remootio WebSocket API."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class GateState(StrEnum):
    """Gate states reported by the Remootio API."""

    OPEN = "open"
    CLOSED = "closed"
    NO_SENSOR = "no sensor"


class DerivedState(StrEnum):
    """Client-side derived states (never sent by the API directly)."""

    OPENING = "opening"
    CLOSING = "closing"
    UNKNOWN = "unknown"


class ActionType(StrEnum):
    """Action types that can be sent to the device."""

    QUERY = "QUERY"
    TRIGGER = "TRIGGER"
    OPEN = "OPEN"
    CLOSE = "CLOSE"


class EventType(StrEnum):
    """Event types pushed by the device."""

    STATE_CHANGE = "StateChange"
    RELAY_TRIGGER = "RelayTrigger"
    SECONDARY_RELAY_TRIGGER = "SecondaryRelayTrigger"
    LEFT_OPEN = "LeftOpen"
    RESTART = "Restart"
    MANUAL_BUTTON_PUSHED = "ManualButtonPushed"
    DOORBELL_PUSHED = "DoorbellPushed"
    SENSOR_ENABLED = "SensorEnabled"
    SENSOR_DISABLED = "SensorDisabled"
    SENSOR_FLIPPED = "SensorFlipped"


class FrameType(StrEnum):
    """WebSocket frame types."""

    AUTH = "AUTH"
    ENCRYPTED = "ENCRYPTED"
    HELLO = "HELLO"
    SERVER_HELLO = "SERVER_HELLO"
    PING = "PING"
    PONG = "PONG"
    ERROR = "ERROR"


@dataclass(frozen=True, kw_only=True)
class DeviceInfo:
    """Device information from the SERVER_HELLO frame."""

    serial_number: str
    api_version: int
    remootio_version: str  # "remootio-1" or "remootio-2"


@dataclass(frozen=True, kw_only=True)
class ActionResponse:
    """Parsed action response from the device."""

    type: ActionType
    id: int
    success: bool
    state: GateState | None
    relay_triggered: bool
    error_code: str


@dataclass(frozen=True, kw_only=True)
class Event:
    """Parsed push event from the device."""

    cnt: int
    type: EventType
    state: GateState | None
    t100ms: int
    data: dict[str, Any] | None = field(default=None)


@dataclass(frozen=True, kw_only=True)
class SessionData:
    """Authentication session data from the CHALLENGE frame."""

    session_key: bytes
    initial_action_id: int


# Exceptions


class RemootioError(Exception):
    """Base exception for Remootio errors."""


class RemootioConnectionError(RemootioError):
    """Cannot connect to the device."""


class RemootioAuthError(RemootioError):
    """Authentication failed (bad API keys)."""


class RemootioNoSensorError(RemootioError):
    """OPEN/CLOSE action requires a sensor but none is installed."""
