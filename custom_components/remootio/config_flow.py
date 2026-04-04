"""Config flow for the Remootio integration."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.const import CONF_HOST
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_create_clientsession

from .api import RemootioClient
from .const import CONF_API_AUTH_KEY, CONF_API_SECRET_KEY, DOMAIN, LOGGER
from .models import DeviceInfo, RemootioAuthError, RemootioConnectionError

USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_API_AUTH_KEY): str,
        vol.Required(CONF_API_SECRET_KEY): str,
    }
)


class RemootioConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Remootio."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> RemootioOptionsFlow:
        """Return the options flow handler."""
        return RemootioOptionsFlow()

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                info = await self._validate_and_get_info(user_input)
            except RemootioAuthError:
                errors["base"] = "auth"
            except RemootioConnectionError:
                errors["base"] = "connection"
            except Exception:  # noqa: BLE001
                LOGGER.exception("Unexpected error in config flow")
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(info.serial_number)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=f"Remootio {info.serial_number}",
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=USER_SCHEMA,
            errors=errors,
        )

    async def async_step_reauth(self, entry_data: dict[str, Any]) -> ConfigFlowResult:
        """Handle re-authentication."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Handle re-authentication confirmation."""
        errors: dict[str, str] = {}

        if user_input is not None:
            reauth_entry = self._get_reauth_entry()
            new_data = {**reauth_entry.data, **user_input}
            try:
                await self._validate_and_get_info(new_data)
            except RemootioAuthError:
                errors["base"] = "auth"
            except RemootioConnectionError:
                errors["base"] = "connection"
            except Exception:  # noqa: BLE001
                LOGGER.exception("Unexpected error in reauth flow")
                errors["base"] = "unknown"
            else:
                return self.async_update_reload_and_abort(reauth_entry, data=new_data)

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_API_AUTH_KEY): str,
                    vol.Required(CONF_API_SECRET_KEY): str,
                }
            ),
            errors=errors,
        )

    async def async_step_reconfigure(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Handle reconfiguration."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                await self._validate_and_get_info(user_input)
            except RemootioAuthError:
                errors["base"] = "auth"
            except RemootioConnectionError:
                errors["base"] = "connection"
            except Exception:  # noqa: BLE001
                LOGGER.exception("Unexpected error in reconfigure flow")
                errors["base"] = "unknown"
            else:
                return self.async_update_reload_and_abort(self._get_reconfigure_entry(), data=user_input)

        reconfigure_entry = self._get_reconfigure_entry()
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST, default=reconfigure_entry.data.get(CONF_HOST)): str,
                    vol.Required(CONF_API_AUTH_KEY): str,
                    vol.Required(CONF_API_SECRET_KEY): str,
                }
            ),
            errors=errors,
        )

    async def _validate_and_get_info(self, data: dict[str, Any]) -> DeviceInfo:
        """Connect to device, authenticate, get device info, disconnect."""
        session = async_create_clientsession(self.hass)
        client = RemootioClient(
            host=data[CONF_HOST],
            api_auth_key=data[CONF_API_AUTH_KEY],
            api_secret_key=data[CONF_API_SECRET_KEY],
            session=session,
        )
        try:
            await client.connect()
            if client.device_info is None:
                raise RemootioConnectionError("No device info received")
            return client.device_info
        finally:
            await client.disconnect()


class RemootioOptionsFlow(OptionsFlow):
    """Handle options for Remootio."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Handle options step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            new_data = {**self.config_entry.data, **user_input}
            session = async_create_clientsession(self.hass)
            client = RemootioClient(
                host=new_data[CONF_HOST],
                api_auth_key=new_data[CONF_API_AUTH_KEY],
                api_secret_key=new_data[CONF_API_SECRET_KEY],
                session=session,
            )
            try:
                await client.connect()
            except RemootioAuthError:
                errors["base"] = "auth"
            except RemootioConnectionError:
                errors["base"] = "connection"
            except Exception:  # noqa: BLE001
                LOGGER.exception("Unexpected error in options flow")
                errors["base"] = "unknown"
            else:
                self.hass.config_entries.async_update_entry(self.config_entry, data=new_data)
                await self.hass.config_entries.async_reload(self.config_entry.entry_id)
                return self.async_create_entry(data={})
            finally:
                await client.disconnect()

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_API_AUTH_KEY): str,
                    vol.Required(CONF_API_SECRET_KEY): str,
                }
            ),
            errors=errors,
        )
