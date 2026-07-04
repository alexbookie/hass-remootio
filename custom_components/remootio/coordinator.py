"""Push-based DataUpdateCoordinator for Remootio."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import TYPE_CHECKING

from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .api import RemootioClient
from .const import DOMAIN, LOGGER, MAX_AUTH_FAILURES_BEFORE_REAUTH, RECONNECT_BACKOFF_BASE, RECONNECT_BACKOFF_MAX
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
        self._reconnect_task: asyncio.Task[None] | None = None
        self._auth_failures = 0
        config_entry.async_on_unload(self._cancel_reconnect)

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
            self._schedule_reconnect()
        self.async_set_updated_data(None)

    @callback
    def _schedule_reconnect(self) -> None:
        """Start the reconnect loop if one isn't already running."""
        if self._reconnect_task is not None and not self._reconnect_task.done():
            return
        self._reconnect_task = self.config_entry.async_create_background_task(
            self.hass,
            self._async_reconnect_loop(),
            "remootio_reconnect",
        )

    async def _async_reconnect_loop(self) -> None:
        """Reconnect with exponential backoff until connected.

        Transient failures (device busy, network blip, stale connection) are
        retried silently. Only after several *consecutive* genuine auth failures
        do we surface a re-auth prompt, so a single race doesn't nag the user to
        re-enter credentials that never actually changed.
        """
        attempt = 0
        while not self.client.connected:
            attempt += 1

            if self._unregister_listener is not None:
                self._unregister_listener()
                self._unregister_listener = None

            try:
                await self._async_connect()
            except RemootioAuthError:
                self._auth_failures += 1
                if self._auth_failures >= MAX_AUTH_FAILURES_BEFORE_REAUTH:
                    LOGGER.error(
                        "Authentication failed %d times during reconnect; requesting re-authentication",
                        self._auth_failures,
                    )
                    self.config_entry.async_start_reauth(self.hass)
                    return
                LOGGER.warning(
                    "Authentication failed during reconnect (%d/%d), will retry",
                    self._auth_failures,
                    MAX_AUTH_FAILURES_BEFORE_REAUTH,
                )
            except RemootioConnectionError:
                LOGGER.debug("Reconnect attempt %d failed, backing off", attempt)
            else:
                self._auth_failures = 0
                LOGGER.info("Reconnected to Remootio device after %d attempt(s)", attempt)
                self.async_set_updated_data(None)
                return

            delay = min(
                RECONNECT_BACKOFF_BASE * 2 ** (attempt - 1),
                RECONNECT_BACKOFF_MAX,
            )
            await asyncio.sleep(delay)

    @callback
    def _cancel_reconnect(self) -> None:
        """Cancel any in-flight reconnect loop (called on unload)."""
        if self._reconnect_task is not None:
            self._reconnect_task.cancel()
            self._reconnect_task = None

    async def async_shutdown(self) -> None:
        """Disconnect on unload."""
        self._cancel_reconnect()
        if self._unregister_listener is not None:
            self._unregister_listener()
            self._unregister_listener = None
        await self.client.disconnect()
        await super().async_shutdown()
