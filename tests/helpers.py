"""Helpers for the tests of the WMS WebControl pro integration."""

from datetime import timedelta

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)

from custom_components.wms_webcontrol_pro.const import STARTUP_POLL_INTERVAL


async def fire_regular_poll(hass: HomeAssistant, config_entry: ConfigEntry) -> None:
    """Let the time of the next regular request of the coordinator pass."""
    interval = config_entry.runtime_data.coordinator.update_interval
    async_fire_time_changed(hass, dt_util.utcnow() + interval + timedelta(seconds=1))
    await hass.async_block_till_done(wait_background_tasks=True)


async def fire_regular_polls(
    hass: HomeAssistant, config_entry: ConfigEntry, count: int
) -> None:
    """Let the times of the next regular requests of the coordinator pass."""
    for _ in range(count):
        await fire_regular_poll(hass, config_entry)


async def read_configuration(config_entry: ConfigEntry) -> None:
    """Run regular requests until the coordinator read the configuration again."""
    coordinator = config_entry.runtime_data.coordinator
    reads = coordinator.configuration_reads
    for _ in range(len(coordinator.hub.dests) + 1):
        await coordinator.async_refresh()
        if coordinator.configuration_reads > reads:
            break


async def run_startup_polls(hass: HomeAssistant, config_entry: ConfigEntry) -> None:
    """Let the coordinator ask every destination once after the setup."""
    coordinator = config_entry.runtime_data.coordinator
    for _ in coordinator.hub.dests:
        if coordinator.update_interval != STARTUP_POLL_INTERVAL:
            break
        await fire_regular_poll(hass, config_entry)


async def setup_config_entry(
    hass: HomeAssistant, config_entry: MockConfigEntry, *, startup_polls: bool = True
) -> bool:
    """Set up a config entry and let the first status of each destination arrive."""
    config_entry.add_to_hass(hass)
    result = await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    if startup_polls and config_entry.state is ConfigEntryState.LOADED:
        await run_startup_polls(hass, config_entry)
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
