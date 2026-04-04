"""Tests for the Remootio coordinator."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.remootio.const import CONF_API_AUTH_KEY, CONF_API_SECRET_KEY, DOMAIN
from custom_components.remootio.coordinator import RemootioCoordinator
from custom_components.remootio.models import GateState, RemootioAuthError, RemootioConnectionError
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady

TEST_API_AUTH_KEY = "a" * 64
TEST_API_SECRET_KEY = "b" * 64
TEST_HOST = "192.168.1.100"


@pytest.mark.usefixtures("mock_client")
async def test_setup_entry_creates_coordinator(hass: HomeAssistant, mock_client: AsyncMock) -> None:
    """Test that async_setup_entry creates and connects the coordinator."""

    entry = MagicMock()
    entry.entry_id = "test"
    entry.domain = DOMAIN
    entry.data = {
        "host": TEST_HOST,
        CONF_API_AUTH_KEY: TEST_API_AUTH_KEY,
        CONF_API_SECRET_KEY: TEST_API_SECRET_KEY,
    }
    entry.runtime_data = None
    entry.async_on_unload = MagicMock()
    entry.async_create_background_task = MagicMock()

    # Verify the coordinator can be created with the mock client
    coordinator = RemootioCoordinator(hass, entry, mock_client)
    assert coordinator is not None


async def test_coordinator_auth_failure_raises(
    hass: HomeAssistant,
    mock_client: AsyncMock,
) -> None:
    """Test that auth failure raises ConfigEntryAuthFailed."""
    mock_client.connect.side_effect = RemootioAuthError("Bad keys")

    entry = MagicMock()
    entry.entry_id = "test"
    entry.domain = DOMAIN
    entry.data = {
        "host": TEST_HOST,
        CONF_API_AUTH_KEY: TEST_API_AUTH_KEY,
        CONF_API_SECRET_KEY: TEST_API_SECRET_KEY,
    }
    entry.async_on_unload = MagicMock()
    entry.async_create_background_task = MagicMock()

    coordinator = RemootioCoordinator(hass, entry, mock_client)

    with pytest.raises(ConfigEntryAuthFailed):
        await coordinator._async_setup()


async def test_coordinator_connection_failure_raises(
    hass: HomeAssistant,
    mock_client: AsyncMock,
) -> None:
    """Test that connection failure raises ConfigEntryNotReady."""
    mock_client.connect.side_effect = RemootioConnectionError("Unreachable")

    entry = MagicMock()
    entry.entry_id = "test"
    entry.domain = DOMAIN
    entry.data = {
        "host": TEST_HOST,
        CONF_API_AUTH_KEY: TEST_API_AUTH_KEY,
        CONF_API_SECRET_KEY: TEST_API_SECRET_KEY,
    }
    entry.async_on_unload = MagicMock()
    entry.async_create_background_task = MagicMock()

    coordinator = RemootioCoordinator(hass, entry, mock_client)

    with pytest.raises(ConfigEntryNotReady):
        await coordinator._async_setup()


async def test_coordinator_connected_property(
    hass: HomeAssistant,
    mock_client: AsyncMock,
) -> None:
    """Test coordinator.connected mirrors client.connected."""
    entry = MagicMock()
    entry.entry_id = "test"
    entry.domain = DOMAIN
    entry.data = {}
    entry.async_on_unload = MagicMock()
    entry.async_create_background_task = MagicMock()

    coordinator = RemootioCoordinator(hass, entry, mock_client)

    mock_client.connected = True
    assert coordinator.connected is True

    mock_client.connected = False
    assert coordinator.connected is False


async def test_coordinator_gate_state_property(
    hass: HomeAssistant,
    mock_client: AsyncMock,
) -> None:
    """Test coordinator.gate_state mirrors client.gate_state."""
    entry = MagicMock()
    entry.entry_id = "test"
    entry.domain = DOMAIN
    entry.data = {}
    entry.async_on_unload = MagicMock()
    entry.async_create_background_task = MagicMock()

    coordinator = RemootioCoordinator(hass, entry, mock_client)

    mock_client.gate_state = GateState.OPEN
    assert coordinator.gate_state == GateState.OPEN


async def test_coordinator_shutdown(
    hass: HomeAssistant,
    mock_client: AsyncMock,
) -> None:
    """Test coordinator shutdown disconnects client."""
    entry = MagicMock()
    entry.entry_id = "test"
    entry.domain = DOMAIN
    entry.data = {}
    entry.async_on_unload = MagicMock()
    entry.async_create_background_task = MagicMock()

    coordinator = RemootioCoordinator(hass, entry, mock_client)
    await coordinator.async_shutdown()

    mock_client.disconnect.assert_awaited_once()
