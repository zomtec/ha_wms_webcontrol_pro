"""Switches of the WMS WebControl pro integration."""

from typing import Any, override

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from pywmswebcontrolpro.const import (
    WMS_WebControl_pro_API_actionDescription as ACTION_DESC,
    WMS_WebControl_pro_API_responseType,
)

from .const import SETTLE_SWITCH
from .coordinator import WebControlProConfigEntry
from .entity import WebControlProEntity

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: WebControlProConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the switches of a hub."""
    coordinator = entry.runtime_data.coordinator

    async_add_entities(
        WebControlProSwitch(coordinator, dest)
        for dest in entry.runtime_data.hub.dests.values()
        if dest.hasAction(ACTION_DESC.LoadSwitch)
    )


class WebControlProSwitch(WebControlProEntity, SwitchEntity):
    """Representation of a WMS based switch."""

    _attr_name = None

    @property
    @override
    def is_on(self) -> bool | None:
        """Return true if switch is on."""
        state = self._dest.action(ACTION_DESC.LoadSwitch)["onOffState"]
        return None if state is None else bool(state)

    async def _async_switch(self, state: bool) -> None:
        """Switch the load, show the result and check it a moment later."""
        action = self._dest.action(ACTION_DESC.LoadSwitch)
        await action(
            onOffState=state, responseType=WMS_WebControl_pro_API_responseType.Detailed
        )
        action["onOffState"] = state
        self.coordinator.async_schedule_refresh(self._dest.id, SETTLE_SWITCH)
        self.async_write_ha_state()

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        await self._async_switch(True)

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        await self._async_switch(False)
