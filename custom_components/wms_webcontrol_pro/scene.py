"""Scenes of the WMS WebControl pro integration."""

from typing import Any, override

from homeassistant.components.scene import Scene
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import (
    DeviceInfo,
    async_get_device_id_by_identifier,
)
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from pywmswebcontrolpro.scene import Scene as WMS_Scene

from .const import ATTRIBUTION, DOMAIN, MANUFACTURER
from .coordinator import WebControlProConfigEntry

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: WebControlProConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the scenes of a hub."""
    coordinator = entry.runtime_data.coordinator
    known: set[int] = set()

    @callback
    def _async_add_new() -> None:
        new = [
            scene
            for scene_id, scene in coordinator.hub.scenes.items()
            if scene_id not in known
        ]
        known.update(scene.id for scene in new)
        via_device_id = async_get_device_id_by_identifier(
            hass, (DOMAIN, entry.entry_id), config_entry_id=entry.entry_id
        )
        async_add_entities(WebControlProScene(scene, via_device_id) for scene in new)

    _async_add_new()
    entry.async_on_unload(coordinator.async_add_listener(_async_add_new))


class WebControlProScene(Scene):
    """Representation of a WMS based scene."""

    _attr_attribution = ATTRIBUTION
    _attr_has_entity_name = True

    def __init__(self, scene: WMS_Scene, via_device_id: str | None) -> None:
        """Initialize the entity with the configured scene."""
        self._scene = scene
        self._attr_name = scene.name
        self._attr_unique_id = str(scene.id)

        # The scene belongs to the device of its room.
        room = scene.room
        if room is not None:
            room_id = str(room.id)
            self._attr_device_info = DeviceInfo(
                identifiers={(DOMAIN, room_id)},
                manufacturer=MANUFACTURER,
                model="Room",
                name=room.name,
                serial_number=room_id,
                suggested_area=room.name,
                configuration_url=f"http://{scene.host}/control",
            )
            if via_device_id is not None:
                self._attr_device_info["via_device_id"] = via_device_id

    @override
    async def async_activate(self, **kwargs: Any) -> None:
        """Activate the scene, the entities follow with their next status."""
        await self._scene()
