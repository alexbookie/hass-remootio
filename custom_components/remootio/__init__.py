"""The Remootio integration."""

from __future__ import annotations

from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import RemootioClient
from .const import CONF_API_AUTH_KEY, CONF_API_SECRET_KEY, PLATFORMS
from .coordinator import RemootioConfigEntry, RemootioCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: RemootioConfigEntry,
) -> bool:
    """Set up Remootio from a config entry."""
    session = async_get_clientsession(hass)
    client = RemootioClient(
        host=entry.data[CONF_HOST],
        api_auth_key=entry.data[CONF_API_AUTH_KEY],
        api_secret_key=entry.data[CONF_API_SECRET_KEY],
        session=session,
    )

    coordinator = RemootioCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(
    hass: HomeAssistant,
    entry: RemootioConfigEntry,
) -> bool:
    """Unload a Remootio config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        await entry.runtime_data.async_shutdown()
    return unload_ok
