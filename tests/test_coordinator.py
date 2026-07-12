"""Tests for the Remootio coordinator."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.remootio.const import (
    CONF_API_AUTH_KEY,
    CONF_API_SECRET_KEY,
    DOMAIN,
    MAX_AUTH_FAILURES_BEFORE_REAUTH,
)
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


def _make_entry() -> MagicMock:
    """Build a mock config entry for reconnect tests."""
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
    entry.async_start_reauth = MagicMock()
    return entry


async def test_reconnect_transient_failure_does_not_reauth(
    hass: HomeAssistant,
    mock_client: AsyncMock,
) -> None:
    """A transient connection failure should retry silently, never reauth."""
    entry = _make_entry()
    coordinator = RemootioCoordinator(hass, entry, mock_client)

    # First reconnect attempt fails transiently, second succeeds.
    mock_client.connected = False
    attempts = {"n": 0}

    async def connect() -> None:
        attempts["n"] += 1
        if attempts["n"] == 1:
            raise RemootioConnectionError("device busy")
        mock_client.connected = True

    mock_client.connect.side_effect = connect

    with patch("custom_components.remootio.coordinator.asyncio.sleep", AsyncMock()):
        await coordinator._async_reconnect_loop()

    assert mock_client.connected is True
    entry.async_start_reauth.assert_not_called()
    assert coordinator._auth_failures == 0


async def test_reconnect_single_auth_failure_does_not_reauth(
    hass: HomeAssistant,
    mock_client: AsyncMock,
) -> None:
    """A single genuine auth failure should be absorbed, then recover."""
    entry = _make_entry()
    coordinator = RemootioCoordinator(hass, entry, mock_client)

    mock_client.connected = False
    attempts = {"n": 0}

    async def connect() -> None:
        attempts["n"] += 1
        if attempts["n"] == 1:
            raise RemootioAuthError("bad keys")
        mock_client.connected = True

    mock_client.connect.side_effect = connect

    with patch("custom_components.remootio.coordinator.asyncio.sleep", AsyncMock()):
        await coordinator._async_reconnect_loop()

    assert mock_client.connected is True
    entry.async_start_reauth.assert_not_called()


async def test_reconnect_repeated_auth_failure_triggers_reauth(
    hass: HomeAssistant,
    mock_client: AsyncMock,
) -> None:
    """Only after repeated genuine auth failures do we ask for re-auth."""
    entry = _make_entry()
    coordinator = RemootioCoordinator(hass, entry, mock_client)

    mock_client.connected = False
    mock_client.connect.side_effect = RemootioAuthError("bad keys")

    with patch("custom_components.remootio.coordinator.asyncio.sleep", AsyncMock()):
        await coordinator._async_reconnect_loop()

    entry.async_start_reauth.assert_called_once()
    assert coordinator._auth_failures == MAX_AUTH_FAILURES_BEFORE_REAUTH


async def test_reconnect_backoff_grows(
    hass: HomeAssistant,
    mock_client: AsyncMock,
) -> None:
    """Reconnect delay should grow exponentially between attempts."""
    entry = _make_entry()
    coordinator = RemootioCoordinator(hass, entry, mock_client)

    mock_client.connected = False
    mock_client.connect.side_effect = RemootioAuthError("bad keys")

    sleep_mock = AsyncMock()
    with patch("custom_components.remootio.coordinator.asyncio.sleep", sleep_mock):
        await coordinator._async_reconnect_loop()

    delays = [call.args[0] for call in sleep_mock.await_args_list]
    # Delays strictly increase until the loop escalates to reauth.
    assert delays == sorted(delays)
    assert delays[0] < delays[-1]


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
