"""Numbers of the WMS WebControl pro integration."""

from typing import override

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntity,
    NumberMode,
)
from homeassistant.const import EntityCategory, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from pywmswebcontrolpro.const import (
    WMS_WebControl_pro_API_actionDescription as ACTION_DESC,
)
from pywmswebcontrolpro.destination import Destination
from pywmswebcontrolpro.store import TravelDirection

from .const import SETTLE_ROTATION
from .coordinator import WebControlProConfigEntry, WebControlProCoordinator
from .entity import WebControlProEntity, async_setup_destination_entities

PARALLEL_UPDATES = 1

# Longest travel time that can be entered, no drive needs more than this.
MAX_TRAVEL_TIME = 600

# Drive actions that become a cover, the key tells the valance from the awning.
TRAVEL_TIME_DRIVES: tuple[tuple[ACTION_DESC, str], ...] = (
    (ACTION_DESC.AwningDrive, ""),
    (ACTION_DESC.ValanceDrive, "valance-"),
    (ACTION_DESC.RollerShutterBlindDrive, ""),
    (ACTION_DESC.SlatDrive, ""),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: WebControlProConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the numbers of a hub."""
    async_setup_destination_entities(entry, async_add_entities, _entities)


def _entities(
    coordinator: WebControlProCoordinator, dest: Destination
) -> list[WebControlProEntity]:
    """Return the numbers of a destination."""
    entities: list[WebControlProEntity] = [
        WebControlProTravelTime(coordinator, dest, drive, prefix, direction)
        for drive, prefix in TRAVEL_TIME_DRIVES
        if dest.hasAction(drive)
        for direction in TravelDirection
    ]
    if dest.hasAction(ACTION_DESC.SlatRotate):
        entities.append(WebControlProSlatRangeMin(coordinator, dest))
        entities.append(WebControlProSlatRangeMax(coordinator, dest))
        entities.append(WebControlProSlatRotationRaw(coordinator, dest))
        if not dest.hasAction(ACTION_DESC.SlatDrive):
            # Only add the numeric slat rotation if no cover entity exists.
            entities.append(WebControlProSlatRotation(coordinator, dest))
    return entities


class WebControlProTravelTime(WebControlProEntity, NumberEntity):
    """Travel time of a full drive in one direction, 0 means unknown."""

    _attr_device_class = NumberDeviceClass.DURATION
    _attr_entity_category = EntityCategory.CONFIG
    _attr_mode = NumberMode.BOX
    _attr_native_min_value = 0
    _attr_native_max_value = MAX_TRAVEL_TIME
    _attr_native_step = 0.1
    _attr_native_unit_of_measurement = UnitOfTime.SECONDS

    def __init__(
        self,
        coordinator: WebControlProCoordinator,
        dest: Destination,
        drive: ACTION_DESC,
        prefix: str,
        direction: TravelDirection,
    ) -> None:
        """Initialize the travel time of a drive action."""
        self._attr_translation_key = f"{prefix}travel-time-{direction.value}"
        super().__init__(coordinator, dest, self._attr_translation_key)
        self._action = dest.action(drive)
        self._direction = direction

    @property
    @override
    def native_value(self) -> float:
        """Return the stored travel time."""
        return float(self._action.settings.travel_time(self._direction))

    @override
    async def async_set_native_value(self, value: float) -> None:
        """Store the travel time, the library keeps it."""
        await self._action.set_travel_time(self._direction, value)
        self.async_write_ha_state()


class WebControlProSlatRange(WebControlProEntity, NumberEntity):
    """One rotation limit of a slat-based cover, the library keeps it.

    The hub reports wrong limits, see the README. The library replaces them,
    learns from measured rotations and stores what is set here.
    """

    _attr_entity_category = EntityCategory.CONFIG

    # Position of the limit in the rotation range of the library.
    _index: int

    def __init__(
        self, coordinator: WebControlProCoordinator, dest: Destination
    ) -> None:
        """Initialize the range option."""
        super().__init__(coordinator, dest, self.translation_key)
        self._action = dest.action(ACTION_DESC.SlatRotate)

    @property
    @override
    def native_value(self) -> float:
        """Return the limit in use."""
        return float(self._action.rotation_range[self._index])


class WebControlProSlatRangeMin(WebControlProSlatRange):
    """Representation of the minimum rotation range-option for a slat-based cover."""

    _attr_native_max_value = 0
    _attr_translation_key = "rotation-min"
    _index = 0

    @property
    @override
    def native_min_value(self) -> float:
        """Return the minimum that the hub reports."""
        return float(self._action.reported_rotation_range[0])

    @override
    async def async_set_native_value(self, value: float) -> None:
        """Store the minimum in the library."""
        await self._action.set_rotation_range(minimum=value)
        self.coordinator.async_update_listeners()


class WebControlProSlatRangeMax(WebControlProSlatRange):
    """Representation of the maximum rotation range-option for a slat-based cover."""

    _attr_native_min_value = 0
    _attr_translation_key = "rotation-max"
    _index = 1

    @property
    @override
    def native_max_value(self) -> float:
        """Return the maximum that the hub reports."""
        return float(self._action.reported_rotation_range[1])

    @override
    async def async_set_native_value(self, value: float) -> None:
        """Store the maximum in the library."""
        await self._action.set_rotation_range(maximum=value)
        self.coordinator.async_update_listeners()


class WebControlProSlatRotation(WebControlProEntity, NumberEntity):
    """Representation of the WMS based slat-rotation for a slat-based cover."""

    _attr_translation_key = "rotation"

    def __init__(
        self, coordinator: WebControlProCoordinator, dest: Destination
    ) -> None:
        """Initialize the rotation."""
        super().__init__(coordinator, dest, self.translation_key)
        self._action = dest.action(ACTION_DESC.SlatRotate)

    @property
    @override
    def native_min_value(self) -> float:
        """Return the minimum value."""
        return float(self._action.rotation_range[0])

    @property
    @override
    def native_max_value(self) -> float:
        """Return the maximum value."""
        return float(self._action.rotation_range[1])

    @property
    @override
    def native_value(self) -> float | None:
        """Return the current value."""
        rotation = self._action["rotation"]
        return None if rotation is None else float(rotation)

    @override
    async def async_set_native_value(self, value: float) -> None:
        """Send the rotation and check the result later."""
        await self._async_command(self._action(rotation=value))
        self.coordinator.async_schedule_refresh(self._dest.id, SETTLE_ROTATION)


class WebControlProSlatRotationRaw(WebControlProSlatRotation):
    """Representation of the WMS based raw slat-rotation for a slat-based cover."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_enabled_default = False
    _attr_translation_key = "rotation-raw"

    @property
    @override
    def native_min_value(self) -> float:
        """Return the minimum value."""
        return float(self._action.reported_rotation_range[0])

    @property
    @override
    def native_max_value(self) -> float:
        """Return the maximum value."""
        return float(self._action.reported_rotation_range[1])
