"""Push-based DataUpdateCoordinator for Remootio."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import TYPE_CHECKING

from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .api import RemootioClient
from .const import DOMAIN, LOGGER, RECONNECT_COOLDOWN
from .models import DerivedState, DeviceInfo, GateState, RemootioAuthError, RemootioConnectionError

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry

type RemootioConfigEntry = ConfigEntry[RemootioCoordinator]


class RemootioCoordinator(DataUpdateCoordinator[None]):
    """Coordinator for Remootio WebSocket push updates.

    No polling — data arrives via WebSocket push. Entities are notified
    via async_set_updated_data(None) and read state from the client.
    """

    config_entry: RemootioConfigEntry

    def __init__(  # noqa: D107
        self,
        hass: HomeAssistant,
        config_entry: RemootioConfigEntry,
        client: RemootioClient,
    ) -> None:
        super().__init__(
            hass,
            LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
        )
        self.client = client
        self._connect_lock = asyncio.Lock()
        self._unregister_listener: Callable[[], None] | None = None
        self._reconnect_debouncer = Debouncer(
            hass,
            LOGGER,
            cooldown=RECONNECT_COOLDOWN,
            immediate=False,
            function=self._async_reconnect,
        )
        config_entry.async_on_unload(self._reconnect_debouncer.async_shutdown)

    @property
    def connected(self) -> bool:
        """Return True when WebSocket is connected and authenticated."""
        return self.client.connected

    @property
    def gate_state(self) -> GateState | DerivedState:
        """Return current gate state."""
        return self.client.gate_state

    @property
    def device_info_data(self) -> DeviceInfo | None:
        """Return device info from the API."""
        return self.client.device_info

    async def _async_setup(self) -> None:
        """Connect WebSocket during first refresh."""
        try:
            await self._async_connect()
        except RemootioAuthError as err:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="auth_failed",
            ) from err
        except RemootioConnectionError as err:
            raise ConfigEntryNotReady(
                translation_domain=DOMAIN,
                translation_key="connection_failed",
            ) from err

    async def _async_update_data(self) -> None:
        """No-op — data arrives via WebSocket push."""
        return

    async def _async_connect(self) -> None:
        """Connect the WebSocket client and register state listener."""
        async with self._connect_lock:
            await self.client.connect()
            self._unregister_listener = self.client.register_listener(self._on_state_update)

    @callback
    def _on_state_update(self) -> None:
        """Called by the WebSocket client when state changes or disconnects."""
        if not self.client.connected:
            self.config_entry.async_create_background_task(
                self.hass,
                self._reconnect_debouncer.async_call(),
                "remootio_reconnect",
            )
        self.async_set_updated_data(None)

    async def _async_reconnect(self) -> None:
        """Attempt to reconnect after disconnect."""
        if self.client.connected:
            return

        if self._unregister_listener is not None:
            self._unregister_listener()
            self._unregister_listener = None

        try:
            await self._async_connect()
            LOGGER.info("Reconnected to Remootio device")
            self.async_set_updated_data(None)
        except RemootioAuthError as err:
            LOGGER.error("Authentication failed during reconnect")
            self.config_entry.async_start_reauth(self.hass)
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="auth_failed",
            ) from err
        except RemootioConnectionError:
            LOGGER.debug("Reconnection failed, will retry")
            await self._reconnect_debouncer.async_call()

    async def async_shutdown(self) -> None:
        """Disconnect on unload."""
        if self._unregister_listener is not None:
            self._unregister_listener()
            self._unregister_listener = None
        await self.client.disconnect()
        await super().async_shutdown()
