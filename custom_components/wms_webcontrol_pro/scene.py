"""Scenes of the WMS WebControl pro integration."""

from typing import Any, override

from homeassistant.components.scene import Scene
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import (
    DeviceInfo,
    async_get_device_id_by_identifier,
)
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from pywmswebcontrolpro.scene import Scene as WMS_Scene

from .const import ATTRIBUTION, DOMAIN, MANUFACTURER, SETTLE_SCENE
from .coordinator import (
    WebControlProConfigEntry,
    WebControlProCoordinator,
    room_identifier,
)
from .entity import async_send_command

# Key of the status requests after a scene, they do not replace those of a drive.
REFRESH_KEY = "scene"

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: WebControlProConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the scenes of a hub."""
    coordinator = entry.runtime_data.coordinator
    known: dict[int, WebControlProScene] = {}
    # Scenes that are gone, with the reading of the configuration that missed them.
    absent: dict[int, int] = {}

    @callback
    def _async_follow_configuration() -> None:
        scenes = coordinator.hub.scenes
        registry = er.async_get(hass)
        for scene_id in known.keys() - scenes.keys():
            entry.async_create_task(hass, known.pop(scene_id).async_remove())
            absent[scene_id] = coordinator.configuration_reads
        for scene_id in absent.keys() & scenes.keys():
            del absent[scene_id]
        # The registry entry goes when a second reading confirms the loss.
        for scene_id, missed in list(absent.items()):
            if coordinator.configuration_reads > missed:
                del absent[scene_id]
                if entity_id := registry.async_get_entity_id(
                    Platform.SCENE, DOMAIN, str(scene_id)
                ):
                    registry.async_remove(entity_id)
        new = scenes.keys() - known.keys()
        if not new:
            return
        via_device_id = async_get_device_id_by_identifier(
            hass, (DOMAIN, entry.entry_id), config_entry_id=entry.entry_id
        )
        for scene_id in new:
            known[scene_id] = WebControlProScene(
                coordinator, scenes[scene_id], via_device_id
            )
        async_add_entities(known[scene_id] for scene_id in new)

    _async_follow_configuration()
    entry.async_on_unload(coordinator.async_add_listener(_async_follow_configuration))


class WebControlProScene(Scene):
    """Representation of a WMS based scene."""

    _attr_attribution = ATTRIBUTION
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: WebControlProCoordinator,
        scene: WMS_Scene,
        via_device_id: str,
    ) -> None:
        """Initialize the entity with the configured scene."""
        self._coordinator = coordinator
        self._scene = scene
        self._attr_name = scene.name
        self._attr_unique_id = str(scene.id)

        # The scene belongs to the device of its room.
        room = scene.room
        if room is not None:
            self._attr_device_info = DeviceInfo(
                identifiers={(DOMAIN, room_identifier(room.id))},
                manufacturer=MANUFACTURER,
                model="Room",
                name=room.name,
                serial_number=str(room.id),
                suggested_area=room.name,
                via_device_id=via_device_id,
                configuration_url=f"http://{scene.host}/control",
            )

    @override
    async def async_activate(self, **kwargs: Any) -> None:
        """Activate the scene and ask every destination for its state later."""
        await async_send_command(self._scene.name, self._scene())
        self._coordinator.async_schedule_refresh_all(SETTLE_SCENE, REFRESH_KEY)
