"""Binary sensors of the WMS WebControl pro integration."""

from typing import override

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.components.binary_sensor.const import BinarySensorDeviceClass
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import WebControlProConfigEntry, WebControlProCoordinator
from .entity import WebControlProHubEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: WebControlProConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the binary sensors of a hub."""
    async_add_entities([WebControlProConnectivity(entry.runtime_data.coordinator)])


class WebControlProConnectivity(WebControlProHubEntity, BinarySensorEntity):
    """Tells if the hub answered the last regular request."""

    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: WebControlProCoordinator) -> None:
        """Initialize the binary sensor of the hub."""
        super().__init__(coordinator, "connectivity")

    @property
    @override
    def is_on(self) -> bool:
        """Return True if the hub answered."""
        return self.coordinator.last_update_success
