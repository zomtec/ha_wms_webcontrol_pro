"""Generic entity for the WMS WebControl pro integration."""

import logging
from collections.abc import Awaitable, Callable, Iterable
from typing import Any

from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import (
    DeviceInfo,
    async_get_device_id_by_identifier,
)
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from pywmswebcontrolpro.destination import Destination
from pywmswebcontrolpro.exceptions import WebControlProCommandError, WebControlProError

from .const import ATTRIBUTION, DOMAIN, MANUFACTURER
from .coordinator import WebControlProConfigEntry, WebControlProCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_send_command(name: str, command: Awaitable[Any]) -> None:
    """Send a command to the hub and report a failure to the caller."""
    try:
        await command
    except WebControlProCommandError as err:
        _LOGGER.debug("Hub rejected a command for %s: %s", name, err.errors)
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="command_rejected",
            translation_placeholders={"name": name},
        ) from err
    except WebControlProError as err:
        _LOGGER.debug("Command for %s failed: %s", name, err)
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="command_failed",
            translation_placeholders={"name": name},
        ) from err


@callback
def async_setup_destination_entities(
    entry: WebControlProConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
    factory: Callable[[WebControlProCoordinator, Destination], Iterable[Entity]],
) -> None:
    """Add the entities of all destinations and follow the configuration.

    The factory creates the entities of one destination. A destination that
    is new after the coordinator read the configuration again gets them too,
    and the entities of a destination that is gone are removed. Their
    registry entries stay until the coordinator removes the device.
    """
    coordinator = entry.runtime_data.coordinator
    known: dict[int, list[Entity]] = {}

    @callback
    def _async_follow_configuration() -> None:
        dests = coordinator.hub.dests
        for dest_id in known.keys() - dests.keys():
            for entity in known.pop(dest_id):
                # An entity that is disabled was not added and has no hass.
                if entity.hass is not None:
                    entry.async_create_task(coordinator.hass, entity.async_remove())
        new: list[Entity] = []
        for dest_id in dests.keys() - known.keys():
            known[dest_id] = list(factory(coordinator, dests[dest_id]))
            new.extend(known[dest_id])
        if new:
            async_add_entities(new)

    _async_follow_configuration()
    entry.async_on_unload(coordinator.async_add_listener(_async_follow_configuration))


class WebControlProEntity(CoordinatorEntity[WebControlProCoordinator]):
    """Foundation of all entities of a WMS destination."""

    _attr_attribution = ATTRIBUTION
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: WebControlProCoordinator,
        dest: Destination,
        key: str | None = None,
    ) -> None:
        """Initialize the entity of a destination, key tells entities apart."""
        super().__init__(coordinator)
        self._dest = dest
        dest_id = str(dest.id)
        self._attr_unique_id = f"{dest_id}-{key}" if key else dest_id
        room = dest.room
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, dest_id)},
            manufacturer=MANUFACTURER,
            model=dest.animationType.name,
            name=dest.name,
            serial_number=dest_id,
            suggested_area=room.name if room else None,
            via_device_id=async_get_device_id_by_identifier(
                coordinator.hass,
                (DOMAIN, coordinator.config_entry.entry_id),
                config_entry_id=coordinator.config_entry.entry_id,
            ),
            configuration_url=f"http://{dest.host}/control",
        )

    @property
    def available(self) -> bool:
        """Return if the destination is reachable."""
        return super().available and self._dest.available

    async def _async_command(self, command: Awaitable[Any]) -> None:
        """Send a command for the destination to the hub."""
        await async_send_command(str(self._dest), command)


class WebControlProHubEntity(CoordinatorEntity[WebControlProCoordinator]):
    """Foundation of the entities of the hub itself.

    They show what the integration knows about the hub, so they stay
    available while the hub does not answer.
    """

    _attr_attribution = ATTRIBUTION
    _attr_has_entity_name = True

    def __init__(self, coordinator: WebControlProCoordinator, key: str) -> None:
        """Initialize the entity of the hub, key tells entities apart."""
        super().__init__(coordinator)
        entry_id = coordinator.config_entry.entry_id
        self._attr_unique_id = f"{entry_id}-{key}"
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, entry_id)})

    @property
    def available(self) -> bool:
        """Return True, the values do not come from the hub."""
        return True
