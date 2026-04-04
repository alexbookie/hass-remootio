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
RECONNECT_COOLDOWN = 5.0
CONNECT_TIMEOUT = 15

# Action ID
ACTION_ID_MAX = 0x7FFFFFFF

# Device info
MANUFACTURER = "Remootio"
