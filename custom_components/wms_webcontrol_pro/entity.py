"""Generic entity for the WMS WebControl pro integration."""

from collections.abc import Callable, Iterable

from homeassistant.core import callback
from homeassistant.helpers.device_registry import (
    DeviceInfo,
    async_get_device_id_by_identifier,
)
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from pywmswebcontrolpro.destination import Destination

from .const import ATTRIBUTION, DOMAIN, MANUFACTURER
from .coordinator import WebControlProConfigEntry, WebControlProCoordinator


@callback
def async_setup_destination_entities(
    entry: WebControlProConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
    factory: Callable[[WebControlProCoordinator, Destination], Iterable[Entity]],
) -> None:
    """Add the entities of all destinations, also of those that appear later.

    The factory creates the entities of one destination, a destination that
    is new after the coordinator read the configuration again gets them too.
    """
    coordinator = entry.runtime_data.coordinator
    known: set[int] = set()

    @callback
    def _async_add_new() -> None:
        new = [
            dest
            for dest_id, dest in coordinator.hub.dests.items()
            if dest_id not in known
        ]
        known.update(dest.id for dest in new)
        async_add_entities(
            entity for dest in new for entity in factory(coordinator, dest)
        )

    _async_add_new()
    entry.async_on_unload(coordinator.async_add_listener(_async_add_new))


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
