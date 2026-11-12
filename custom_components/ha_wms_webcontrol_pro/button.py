"""Buttons of the WMS WebControl pro integration."""

from typing import override

from homeassistant.components.button import ButtonEntity
from homeassistant.components.button.const import ButtonDeviceClass
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from pywmswebcontrolpro.const import (
    WMS_WebControl_pro_API_actionDescription as ACTION_DESC,
)
from pywmswebcontrolpro.destination import Destination

from .coordinator import WebControlProConfigEntry, WebControlProCoordinator
from .entity import WebControlProEntity

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: WebControlProConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the buttons of a hub."""
    coordinator = entry.runtime_data.coordinator

    entities: list[WebControlProEntity] = []
    for dest in entry.runtime_data.hub.dests.values():
        if dest.hasAction(ACTION_DESC.Identify):
            entities.append(WebControlProIdentifyButton(coordinator, dest))
        if dest.hasAction(ACTION_DESC.SlatRotate):
            entities.append(WebControlProRotationResetButton(coordinator, dest))

    async_add_entities(entities)


class WebControlProIdentifyButton(WebControlProEntity, ButtonEntity):
    """Representation of a WMS based identify button."""

    _attr_device_class = ButtonDeviceClass.IDENTIFY

    @override
    async def async_press(self) -> None:
        """Handle the button press to identify the device."""
        await self._dest.action(ACTION_DESC.Identify)()


class WebControlProRotationResetButton(WebControlProEntity, ButtonEntity):
    """Representation of a WMS based reset rotation button."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_translation_key = "rotation-reset"

    def __init__(
        self, coordinator: WebControlProCoordinator, dest: Destination
    ) -> None:
        """Initialize the reset button."""
        super().__init__(coordinator, dest, self.translation_key)

    @override
    async def async_press(self) -> None:
        """Reset the rotation range to the default."""
        action = self._dest.action(ACTION_DESC.SlatRotate)
        # Deleting the overwrites restores the range of the hub.
        del action["minValue"]
        del action["maxValue"]
        await action.sync()
        self.coordinator.async_update_listeners()
