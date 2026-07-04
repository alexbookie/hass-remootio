"""Constants for the Remootio integration."""

from __future__ import annotations

from logging import Logger, getLogger

from homeassistant.const import Platform

LOGGER: Logger = getLogger(__package__)

DOMAIN = "remootio"
PLATFORMS: list[Platform] = [Platform.COVER]

# Config entry data keys
CONF_API_AUTH_KEY = "api_auth_key"
CONF_API_SECRET_KEY = "api_secret_key"

# WebSocket
WS_PORT = 8080

# Timing (seconds)
PING_INTERVAL = 60
CONNECT_TIMEOUT = 15

# Reconnect backoff (seconds). The device can hold a stale connection for up to
# 120s after a drop (single-connection limit), so retries must back off toward
# that window rather than hammer the device and race into ERROR frames.
RECONNECT_BACKOFF_BASE = 5.0
RECONNECT_BACKOFF_MAX = 120.0

# Number of consecutive *genuine* auth failures during reconnect before we give
# up and ask the user to re-enter credentials. A single failure is usually a
# transient race (e.g. the device is still tearing down the previous socket),
# not actually rotated keys, so we absorb a few before nagging.
MAX_AUTH_FAILURES_BEFORE_REAUTH = 3

# Action ID
ACTION_ID_MAX = 0x7FFFFFFF

# Device info
MANUFACTURER = "Remootio"
