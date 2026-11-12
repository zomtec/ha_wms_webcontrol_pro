"""Helpers for the tests of the WMS WebControl pro integration."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry


async def setup_config_entry(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> bool:
    """Set up a config entry."""
    config_entry.add_to_hass(hass)
    result = await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    return result


async def unload_config_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    result = await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()
    return result


async def remove_config_entry(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> dict[str, bool]:
    """Remove a config entry."""
    result = await hass.config_entries.async_remove(config_entry.entry_id)
    await hass.async_block_till_done()
    return result
