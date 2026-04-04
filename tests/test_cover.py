"""Tests for the Remootio cover entity."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.remootio.cover import RemootioCover
from custom_components.remootio.models import DerivedState, DeviceInfo, GateState
from homeassistant.components.cover import CoverDeviceClass, CoverEntityFeature


@pytest.fixture
def coordinator() -> MagicMock:
    """Return a mock coordinator."""
    coord = MagicMock()
    coord.connected = True
    coord.gate_state = GateState.CLOSED
    coord.device_info_data = DeviceInfo(
        serial_number="ABC123",
        api_version=3,
        remootio_version="remootio-2",
    )
    coord.client = AsyncMock()
    coord.client.has_sensor = True
    coord.client.trigger = AsyncMock()
    coord.client.open_door = AsyncMock()
    coord.client.close_door = AsyncMock()
    return coord


@pytest.fixture
def cover(coordinator: MagicMock) -> RemootioCover:
    """Return a RemootioCover instance."""
    return RemootioCover(coordinator)


class TestCoverState:
    """Test cover state properties."""

    def test_is_closed_when_closed(self, cover: RemootioCover, coordinator: MagicMock) -> None:
        """Cover should report closed."""
        coordinator.gate_state = GateState.CLOSED
        assert cover.is_closed is True

    def test_is_not_closed_when_open(self, cover: RemootioCover, coordinator: MagicMock) -> None:
        """Cover should report not closed."""
        coordinator.gate_state = GateState.OPEN
        assert cover.is_closed is False

    def test_is_closed_unknown_no_sensor(self, cover: RemootioCover, coordinator: MagicMock) -> None:
        """Cover should report None when no sensor."""
        coordinator.gate_state = GateState.NO_SENSOR
        assert cover.is_closed is None

    def test_is_closed_unknown_initial(self, cover: RemootioCover, coordinator: MagicMock) -> None:
        """Cover should report None on initial unknown state."""
        coordinator.gate_state = DerivedState.UNKNOWN
        assert cover.is_closed is None

    def test_is_opening(self, cover: RemootioCover, coordinator: MagicMock) -> None:
        """Cover should report opening."""
        coordinator.gate_state = DerivedState.OPENING
        assert cover.is_opening is True
        assert cover.is_closing is False
        assert cover.is_closed is False

    def test_is_closing(self, cover: RemootioCover, coordinator: MagicMock) -> None:
        """Cover should report closing."""
        coordinator.gate_state = DerivedState.CLOSING
        assert cover.is_closing is True
        assert cover.is_opening is False
        assert cover.is_closed is False


class TestCoverAvailability:
    """Test cover availability."""

    def test_available_when_connected(self, cover: RemootioCover, coordinator: MagicMock) -> None:
        """Cover should be available when connected."""
        coordinator.connected = True
        assert cover.available is True

    def test_unavailable_when_disconnected(self, cover: RemootioCover, coordinator: MagicMock) -> None:
        """Cover should be unavailable when disconnected."""
        coordinator.connected = False
        assert cover.available is False


class TestCoverCommands:
    """Test cover command methods."""

    async def test_open_with_sensor(self, cover: RemootioCover, coordinator: MagicMock) -> None:
        """Open should use open_door when sensor is available."""
        coordinator.client.has_sensor = True
        await cover.async_open_cover()
        coordinator.client.open_door.assert_awaited_once()
        coordinator.client.trigger.assert_not_awaited()

    async def test_open_without_sensor(self, cover: RemootioCover, coordinator: MagicMock) -> None:
        """Open should fall back to trigger when no sensor."""
        coordinator.client.has_sensor = False
        await cover.async_open_cover()
        coordinator.client.trigger.assert_awaited_once()
        coordinator.client.open_door.assert_not_awaited()

    async def test_close_with_sensor(self, cover: RemootioCover, coordinator: MagicMock) -> None:
        """Close should use close_door when sensor is available."""
        coordinator.client.has_sensor = True
        await cover.async_close_cover()
        coordinator.client.close_door.assert_awaited_once()
        coordinator.client.trigger.assert_not_awaited()

    async def test_close_without_sensor(self, cover: RemootioCover, coordinator: MagicMock) -> None:
        """Close should fall back to trigger when no sensor."""
        coordinator.client.has_sensor = False
        await cover.async_close_cover()
        coordinator.client.trigger.assert_awaited_once()
        coordinator.client.close_door.assert_not_awaited()

    async def test_stop_always_triggers(self, cover: RemootioCover, coordinator: MagicMock) -> None:
        """Stop should always use trigger."""
        await cover.async_stop_cover()
        coordinator.client.trigger.assert_awaited_once()


class TestCoverAttributes:
    """Test cover static attributes."""

    def test_device_class(self, cover: RemootioCover) -> None:
        """Cover should have garage device class."""
        assert cover._attr_device_class == CoverDeviceClass.GARAGE

    def test_supported_features(self, cover: RemootioCover) -> None:
        """Cover should support open, close, and stop."""
        expected = CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE | CoverEntityFeature.STOP
        assert cover._attr_supported_features == expected

    def test_unique_id(self, cover: RemootioCover) -> None:
        """Unique ID should be the serial number."""
        assert cover._attr_unique_id == "ABC123_cover"

    def test_device_info(self, cover: RemootioCover) -> None:
        """Device info should include manufacturer and model."""
        info = cover._attr_device_info
        assert info is not None
        assert ("remootio", "ABC123") in info["identifiers"]
        assert info["manufacturer"] == "Remootio"
        assert info["model"] == "remootio-2"
