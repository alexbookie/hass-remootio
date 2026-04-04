"""Cover platform for Remootio garage door openers."""

from __future__ import annotations

from typing import Any

from homeassistant.components.cover import CoverDeviceClass, CoverEntity, CoverEntityFeature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER
from .coordinator import RemootioConfigEntry, RemootioCoordinator
from .models import DerivedState, GateState


async def async_setup_entry(
    hass: HomeAssistant,
    entry: RemootioConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Remootio cover from a config entry."""
    coordinator = entry.runtime_data
    async_add_entities([RemootioCover(coordinator)])


class RemootioCover(CoordinatorEntity[RemootioCoordinator], CoverEntity):
    """Representation of a Remootio garage door."""

    _attr_device_class = CoverDeviceClass.GARAGE
    _attr_has_entity_name = True
    _attr_name = None
    _attr_supported_features = CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE | CoverEntityFeature.STOP

    def __init__(self, coordinator: RemootioCoordinator) -> None:  # noqa: D107
        super().__init__(coordinator)
        device = coordinator.device_info_data
        if device is None:
            raise ValueError("Device info not available")
        self._attr_unique_id = f"{device.serial_number}_cover"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device.serial_number)},
            name=f"Remootio {device.serial_number}",
            manufacturer=MANUFACTURER,
            model=device.remootio_version,
            sw_version=f"API v{device.api_version}",
        )

    @property
    def available(self) -> bool:
        """Return True if the device is connected."""
        return self.coordinator.connected

    @property
    def is_closed(self) -> bool | None:
        """Return True if the cover is closed."""
        state = self.coordinator.gate_state
        if state == GateState.CLOSED:
            return True
        if state == GateState.OPEN:
            return False
        if state in (GateState.NO_SENSOR, DerivedState.UNKNOWN):
            return None
        # OPENING or CLOSING — not closed
        return False

    @property
    def is_closing(self) -> bool:
        """Return True if the cover is closing."""
        return self.coordinator.gate_state == DerivedState.CLOSING

    @property
    def is_opening(self) -> bool:
        """Return True if the cover is opening."""
        return self.coordinator.gate_state == DerivedState.OPENING

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the garage door."""
        if self.coordinator.client.has_sensor:
            await self.coordinator.client.open_door()
        else:
            await self.coordinator.client.trigger()

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close the garage door."""
        if self.coordinator.client.has_sensor:
            await self.coordinator.client.close_door()
        else:
            await self.coordinator.client.trigger()

    async def async_stop_cover(self, **kwargs: Any) -> None:
        """Stop the garage door by triggering the relay."""
        await self.coordinator.client.trigger()
