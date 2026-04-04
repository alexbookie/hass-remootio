"""Tests for the Remootio config flow."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from custom_components.remootio.const import CONF_API_AUTH_KEY, CONF_API_SECRET_KEY, DOMAIN
from custom_components.remootio.models import RemootioAuthError, RemootioConnectionError
from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

TEST_API_AUTH_KEY = "a" * 64
TEST_API_SECRET_KEY = "b" * 64
TEST_HOST = "192.168.1.100"
TEST_SERIAL = "ABC123DEF456"

USER_INPUT = {
    "host": TEST_HOST,
    CONF_API_AUTH_KEY: TEST_API_AUTH_KEY,
    CONF_API_SECRET_KEY: TEST_API_SECRET_KEY,
}


@pytest.mark.usefixtures("mock_client", "mock_setup_entry")
async def test_user_flow_success(hass: HomeAssistant) -> None:
    """Test successful user config flow."""
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        USER_INPUT,
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == f"Remootio {TEST_SERIAL}"
    assert result["data"] == USER_INPUT
    assert result["result"].unique_id == TEST_SERIAL


@pytest.mark.usefixtures("mock_setup_entry")
async def test_user_flow_auth_error(hass: HomeAssistant, mock_client: AsyncMock) -> None:
    """Test config flow with authentication error."""
    mock_client.connect.side_effect = RemootioAuthError("Bad keys")

    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        USER_INPUT,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "auth"}


@pytest.mark.usefixtures("mock_setup_entry")
async def test_user_flow_connection_error(hass: HomeAssistant, mock_client: AsyncMock) -> None:
    """Test config flow with connection error."""
    mock_client.connect.side_effect = RemootioConnectionError("Unreachable")

    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        USER_INPUT,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "connection"}


@pytest.mark.usefixtures("mock_setup_entry")
async def test_user_flow_unknown_error(hass: HomeAssistant, mock_client: AsyncMock) -> None:
    """Test config flow with unexpected error."""
    mock_client.connect.side_effect = RuntimeError("Unexpected")

    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        USER_INPUT,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "unknown"}


@pytest.mark.usefixtures("mock_client", "mock_setup_entry")
async def test_user_flow_duplicate_device(hass: HomeAssistant) -> None:
    """Test config flow aborts on duplicate device."""
    # First entry succeeds
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        USER_INPUT,
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY

    # Second entry with same serial should abort
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        USER_INPUT,
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
