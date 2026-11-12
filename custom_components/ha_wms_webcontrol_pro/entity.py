"""Generic entity for the WMS WebControl pro integration."""

from homeassistant.helpers.device_registry import (
    DeviceInfo,
    async_get_device_id_by_identifier,
)
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from pywmswebcontrolpro.destination import Destination

from .const import ATTRIBUTION, DOMAIN, MANUFACTURER
from .coordinator import WebControlProCoordinator


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
