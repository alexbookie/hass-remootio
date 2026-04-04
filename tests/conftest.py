"""Shared fixtures for Remootio integration tests."""

from __future__ import annotations

from collections.abc import Generator
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.remootio.api import RemootioClient
from custom_components.remootio.const import CONF_API_AUTH_KEY, CONF_API_SECRET_KEY, DOMAIN
from custom_components.remootio.models import DeviceInfo, GateState

# Test API keys (64-char hex strings)
TEST_API_AUTH_KEY = "a" * 64
TEST_API_SECRET_KEY = "b" * 64
TEST_HOST = "192.168.1.100"
TEST_SERIAL = "ABC123DEF456"


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Enable custom integrations for all tests."""


@pytest.fixture
def device_info() -> DeviceInfo:
    """Return test device info."""
    return DeviceInfo(
        serial_number=TEST_SERIAL,
        api_version=3,
        remootio_version="remootio-2",
    )


@pytest.fixture
def mock_client(device_info: DeviceInfo) -> Generator[AsyncMock]:
    """Return a mocked RemootioClient."""
    with (
        patch("custom_components.remootio.config_flow.RemootioClient") as mock_flow,
        patch("custom_components.remootio.RemootioClient") as mock_init,
        patch("custom_components.remootio.async_get_clientsession"),
    ):
        client = AsyncMock(spec=RemootioClient)
        client.connected = True
        client.gate_state = GateState.CLOSED
        client.device_info = device_info
        client.has_sensor = True

        # connect() succeeds by default
        client.connect = AsyncMock()
        client.disconnect = AsyncMock()
        client.trigger = AsyncMock()
        client.open_door = AsyncMock()
        client.close_door = AsyncMock()

        # register_listener returns an unregister callable
        _listeners: list = []

        def register_listener(callback):
            _listeners.append(callback)
            return lambda: _listeners.remove(callback)

        client.register_listener = MagicMock(side_effect=register_listener)
        client._listeners = _listeners

        mock_flow.return_value = client
        mock_init.return_value = client
        yield client


@pytest.fixture
def config_entry_data() -> dict[str, Any]:
    """Return test config entry data."""
    return {
        "host": TEST_HOST,
        CONF_API_AUTH_KEY: TEST_API_AUTH_KEY,
        CONF_API_SECRET_KEY: TEST_API_SECRET_KEY,
    }


@pytest.fixture
def mock_config_entry(config_entry_data: dict[str, Any]) -> MagicMock:
    """Return a mock config entry."""
    from unittest.mock import PropertyMock

    entry = MagicMock()
    entry.entry_id = "test_entry_id"
    entry.domain = DOMAIN
    entry.data = config_entry_data
    entry.options = {}
    entry.unique_id = TEST_SERIAL
    entry.title = f"Remootio {TEST_SERIAL}"
    type(entry).runtime_data = PropertyMock(return_value=None)
    return entry


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry to prevent full setup during config flow tests."""
    with patch(
        "custom_components.remootio.async_setup_entry",
        return_value=True,
    ) as mock:
        yield mock
