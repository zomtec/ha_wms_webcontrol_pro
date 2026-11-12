"""Lights of the WMS WebControl pro integration."""

from typing import Any, override

from homeassistant.components.light import LightEntity
from homeassistant.components.light.const import ATTR_BRIGHTNESS, ColorMode
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util.color import brightness_to_value, value_to_brightness

from pywmswebcontrolpro.const import (
    WMS_WebControl_pro_API_actionDescription as ACTION_DESC,
    WMS_WebControl_pro_API_responseType,
)
from pywmswebcontrolpro.destination import Destination

from .const import BRIGHTNESS_SCALE, SETTLE_SWITCH
from .coordinator import WebControlProConfigEntry, WebControlProCoordinator
from .entity import WebControlProEntity

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: WebControlProConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the lights of a hub."""
    coordinator = entry.runtime_data.coordinator

    entities: list[WebControlProLight] = []
    for dest in entry.runtime_data.hub.dests.values():
        if dest.hasAction(ACTION_DESC.LightDimming):
            entities.append(WebControlProDimmer(coordinator, dest))
        elif dest.hasAction(ACTION_DESC.LightSwitch):
            entities.append(WebControlProLight(coordinator, dest))

    async_add_entities(entities)


class WebControlProLight(WebControlProEntity, LightEntity):
    """Representation of a WMS based light."""

    _attr_color_mode = ColorMode.ONOFF
    _attr_name = None

    def __init__(
        self, coordinator: WebControlProCoordinator, dest: Destination
    ) -> None:
        """Initialize the light."""
        super().__init__(coordinator, dest)
        self._attr_supported_color_modes = {self._attr_color_mode}

    @property
    @override
    def is_on(self) -> bool | None:
        """Return true if light is on."""
        state = self._dest.action(ACTION_DESC.LightSwitch)["onOffState"]
        return None if state is None else bool(state)

    async def _async_switch(self, state: bool) -> None:
        """Switch the light, show the result and check it a moment later."""
        action = self._dest.action(ACTION_DESC.LightSwitch)
        await action(
            onOffState=state, responseType=WMS_WebControl_pro_API_responseType.Detailed
        )
        action["onOffState"] = state
        self.coordinator.async_schedule_refresh(self._dest.id, SETTLE_SWITCH)
        self.async_write_ha_state()

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the light on."""
        await self._async_switch(True)

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the light off."""
        await self._async_switch(False)


class WebControlProDimmer(WebControlProLight):
    """Representation of a WMS-based dimmable light."""

    _attr_color_mode = ColorMode.BRIGHTNESS

    @property
    @override
    def brightness(self) -> int | None:
        """Return the brightness of this light between 1..255."""
        percentage = self._dest.action(ACTION_DESC.LightDimming)["percentage"]
        if percentage is None:
            return None
        return value_to_brightness(BRIGHTNESS_SCALE, percentage)

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the dimmer on."""
        if ATTR_BRIGHTNESS not in kwargs:
            await super().async_turn_on(**kwargs)
            return

        action = self._dest.action(ACTION_DESC.LightDimming)
        percentage = brightness_to_value(BRIGHTNESS_SCALE, kwargs[ATTR_BRIGHTNESS])
        await action(
            percentage=percentage,
            responseType=WMS_WebControl_pro_API_responseType.Detailed,
        )
        action["percentage"] = percentage
        self._dest.action(ACTION_DESC.LightSwitch)["onOffState"] = True
        self.coordinator.async_schedule_refresh(self._dest.id, SETTLE_SWITCH)
        self.async_write_ha_state()
