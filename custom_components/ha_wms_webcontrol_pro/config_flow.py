"""Config flow for the WMS WebControl pro integration."""

import ipaddress
import logging
from typing import Any, override

import aiohttp
import probatio
from homeassistant.config_entries import (
    SOURCE_DHCP,
    SOURCE_IGNORE,
    ConfigFlow,
    ConfigFlowResult,
)
from homeassistant.const import CONF_HOST
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo

from pywmswebcontrolpro.webcontrol import WebControlPro

from .const import DOMAIN, SUGGESTED_HOST

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = probatio.Schema({probatio.Required(CONF_HOST): str})


class WebControlProConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for a WMS WebControl pro hub."""

    VERSION = 1

    @override
    async def async_step_dhcp(
        self, discovery_info: DhcpServiceInfo
    ) -> ConfigFlowResult:
        """Handle the DHCP discovery step."""
        unique_id = format_mac(discovery_info.macaddress)
        await self.async_set_unique_id(unique_id)

        entry = self.hass.config_entries.async_entry_for_domain_unique_id(
            DOMAIN, unique_id
        )
        if entry:
            if entry.source == SOURCE_IGNORE:
                return self.async_abort(reason="already_configured")
            try:
                ipaddress.ip_address(entry.data[CONF_HOST])
            except ValueError:
                # A name-based host stays as it is.
                return self.async_abort(reason="already_configured")
            self._abort_if_unique_id_configured(updates={CONF_HOST: discovery_info.ip})

        for entry in self.hass.config_entries.async_entries(DOMAIN):
            if not entry.unique_id and entry.data[CONF_HOST] in (
                discovery_info.hostname,
                discovery_info.ip,
            ):
                self.hass.config_entries.async_update_entry(entry, unique_id=unique_id)
                return self.async_abort(reason="already_configured")

        return await self.async_step_user()

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the user-based step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            self._async_abort_entries_match(user_input)
            host = user_input[CONF_HOST]
            hub = WebControlPro(host, async_get_clientsession(self.hass))
            try:
                pong = await hub.ping()
                if pong:
                    await hub.refresh()
            except aiohttp.ClientError, TimeoutError:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                if not pong:
                    errors["base"] = "cannot_connect"
                elif self._is_configured_hub(set(hub.rooms)):
                    return self.async_abort(reason="already_configured")
                else:
                    return self.async_create_entry(title=host, data=user_input)

        if self.source == SOURCE_DHCP:
            discovery_info: DhcpServiceInfo = self.init_data
            data_values = {CONF_HOST: discovery_info.ip}
        else:
            data_values = {CONF_HOST: SUGGESTED_HOST}

        self.context["title_placeholders"] = data_values
        data_schema = self.add_suggested_values_to_schema(
            STEP_USER_DATA_SCHEMA, data_values
        )
        return self.async_show_form(
            step_id="user", data_schema=data_schema, errors=errors
        )

    def _is_configured_hub(self, rooms: set[int]) -> bool:
        """Return True if a loaded entry belongs to a hub with the same rooms."""
        return any(
            entry.runtime_data and set(entry.runtime_data.hub.rooms) == rooms
            for entry in self.hass.config_entries.async_loaded_entries(DOMAIN)
        )
