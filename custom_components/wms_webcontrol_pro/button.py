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
from .entity import WebControlProEntity, async_setup_destination_entities

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: WebControlProConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the buttons of a hub."""
    async_setup_destination_entities(entry, async_add_entities, _entities)


def _entities(
    coordinator: WebControlProCoordinator, dest: Destination
) -> list[WebControlProEntity]:
    """Return the buttons of a destination."""
    entities: list[WebControlProEntity] = []
    if dest.hasAction(ACTION_DESC.Identify):
        entities.append(WebControlProIdentifyButton(coordinator, dest))
    if dest.hasAction(ACTION_DESC.SlatRotate):
        entities.append(WebControlProRotationResetButton(coordinator, dest))
    return entities


class WebControlProIdentifyButton(WebControlProEntity, ButtonEntity):
    """Representation of a WMS based identify button."""

    _attr_device_class = ButtonDeviceClass.IDENTIFY

    @override
    async def async_press(self) -> None:
        """Handle the button press to identify the device."""
        await self._async_command(self._dest.action(ACTION_DESC.Identify)())


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
        """Reset the rotation range to the default of the library."""
        await self._dest.action(ACTION_DESC.SlatRotate).reset_rotation_range()
        self.coordinator.async_update_listeners()
