"""The WMS WebControl pro integration."""

import shutil
from pathlib import Path

from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv, device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.storage import STORAGE_DIR
from homeassistant.helpers.typing import UNDEFINED, ConfigType

from pywmswebcontrolpro.exceptions import WebControlProError
from pywmswebcontrolpro.webcontrol import WebControlPro

from .const import DOMAIN, MANUFACTURER, STATUS_REQUEST_SPACING
from .coordinator import (
    WebControlProConfigEntry,
    WebControlProCoordinator,
    WebControlProData,
)
from .services import async_setup_services

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.COVER,
    Platform.LIGHT,
    Platform.NUMBER,
    Platform.SCENE,
    Platform.SENSOR,
    Platform.SWITCH,
]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


def _storage_dir(hass: HomeAssistant, entry: WebControlProConfigEntry) -> Path:
    """Return the directory for the stored data of a config entry."""
    return Path(hass.config.path(STORAGE_DIR, f"{DOMAIN}-{entry.entry_id}"))


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the integration."""
    async_setup_services(hass)
    return True


async def async_setup_entry(
    hass: HomeAssistant, entry: WebControlProConfigEntry
) -> bool:
    """Set up a hub from a config entry."""
    host = entry.data[CONF_HOST]
    hub = WebControlPro(
        host,
        async_get_clientsession(hass),
        str(_storage_dir(hass, entry)),
        request_spacing=STATUS_REQUEST_SPACING,
    )

    try:
        answers = await hub.ping()
    except WebControlProError as err:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="cannot_connect",
            translation_placeholders={"host": host},
        ) from err
    if not answers:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="cannot_connect",
            translation_placeholders={"host": host},
        )

    dr.async_get(hass).async_get_or_create(
        config_entry_id=entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, entry.unique_id)}
        if entry.unique_id
        else UNDEFINED,
        identifiers={(DOMAIN, entry.entry_id)},
        manufacturer=MANUFACTURER,
        model="WMS WebControl pro",
        configuration_url=f"http://{hub.host}/system",
    )

    coordinator = WebControlProCoordinator(hass, entry, hub)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = WebControlProData(hub, coordinator)
    entry.async_on_unload(coordinator.async_stop)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: WebControlProConfigEntry
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_remove_config_entry_device(
    hass: HomeAssistant,
    entry: WebControlProConfigEntry,
    device_entry: dr.DeviceEntry,
) -> bool:
    """Allow to remove a device that the hub does not report any more."""
    valid = entry.runtime_data.coordinator.async_valid_identifiers()
    return all(
        identifier not in valid
        for domain, identifier in device_entry.identifiers
        if domain == DOMAIN
    )


async def async_remove_entry(
    hass: HomeAssistant, entry: WebControlProConfigEntry
) -> None:
    """Remove the stored data of a config entry."""
    directory = _storage_dir(hass, entry)
    if await hass.async_add_executor_job(directory.is_dir):
        await hass.async_add_executor_job(shutil.rmtree, directory)
