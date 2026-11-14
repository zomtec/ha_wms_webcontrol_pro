"""Sensors of the WMS WebControl pro integration."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import override

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, EntityCategory, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from pywmswebcontrolpro.destination import Destination
from pywmswebcontrolpro.refresh import RefreshStats

from .coordinator import WebControlProConfigEntry, WebControlProCoordinator
from .entity import (
    WebControlProEntity,
    WebControlProHubEntity,
    async_setup_destination_entities,
)

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class WebControlProSensorDescription(SensorEntityDescription):
    """Description of a sensor that shows a value of the polling statistics."""

    value_fn: Callable[[RefreshStats], float | datetime | None]


SENSORS: tuple[WebControlProSensorDescription, ...] = (
    WebControlProSensorDescription(
        key="poll-success-rate",
        translation_key="poll-success-rate",
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        value_fn=lambda stats: stats.recent_success_rate,
    ),
    WebControlProSensorDescription(
        key="last-successful-poll",
        translation_key="last-successful-poll",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda stats: stats.last_ok,
    ),
)

# The answer time belongs to one destination, the hub has no value for it.
DESTINATION_SENSORS: tuple[WebControlProSensorDescription, ...] = (
    *SENSORS,
    WebControlProSensorDescription(
        key="last-answer-time",
        translation_key="last-answer-time",
        device_class=SensorDeviceClass.DURATION,
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        value_fn=lambda stats: stats.last_duration,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: WebControlProConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the sensors of a hub and its destinations."""
    coordinator = entry.runtime_data.coordinator
    async_add_entities(
        WebControlProHubSensor(coordinator, description) for description in SENSORS
    )
    async_setup_destination_entities(entry, async_add_entities, _entities)


def _entities(
    coordinator: WebControlProCoordinator, dest: Destination
) -> list[WebControlProDestinationSensor]:
    """Return the sensors of a destination."""
    return [
        WebControlProDestinationSensor(coordinator, dest, description)
        for description in DESTINATION_SENSORS
    ]


class WebControlProHubSensor(WebControlProHubEntity, SensorEntity):
    """Polling statistics of all destinations of the hub together."""

    entity_description: WebControlProSensorDescription

    def __init__(
        self,
        coordinator: WebControlProCoordinator,
        description: WebControlProSensorDescription,
    ) -> None:
        """Initialize the sensor of the hub."""
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    @override
    def native_value(self) -> float | datetime | None:
        """Return the value of the statistics of the library."""
        return self.entity_description.value_fn(self.coordinator.hub.stats)


class WebControlProDestinationSensor(WebControlProEntity, SensorEntity):
    """Polling statistics of one destination.

    Most destinations are polled rarely, so the sensors are only of use to
    look into radio problems and are disabled by default.
    """

    entity_description: WebControlProSensorDescription
    _attr_entity_registry_enabled_default = False

    def __init__(
        self,
        coordinator: WebControlProCoordinator,
        dest: Destination,
        description: WebControlProSensorDescription,
    ) -> None:
        """Initialize the sensor of a destination."""
        super().__init__(coordinator, dest, description.key)
        self.entity_description = description

    @property
    @override
    def available(self) -> bool:
        """Return True, the statistics are known while the hub is silent."""
        return True

    @property
    @override
    def native_value(self) -> float | datetime | None:
        """Return the value of the statistics of the library."""
        return self.entity_description.value_fn(self._dest.stats)
