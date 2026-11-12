"""Tests for destinations that appear or disappear on the hub."""

import copy
from typing import Any

import pytest
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.wms_webcontrol_pro import async_remove_config_entry_device
from custom_components.wms_webcontrol_pro.const import DOMAIN

from .conftest import ENTRY_ID, FakeGateway
from .helpers import setup_config_entry

DEST_ID = 18894
OTHER_DEST_ID = 116682

pytestmark = pytest.mark.parametrize(
    "gateway",
    [("config_prod_roller_shutter.json", "status_prod_roller_shutter.json")],
    indirect=True,
)


def _without_destination(config: dict[str, Any], dest_id: int) -> dict[str, Any]:
    """Return the configuration of a hub that has no destination with this id."""
    reduced = copy.deepcopy(config)
    reduced["destinations"] = [d for d in reduced["destinations"] if d["id"] != dest_id]
    return reduced


async def test_destination_that_appears_gets_entities(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    gateway: FakeGateway,
    entity_registry: er.EntityRegistry,
) -> None:
    """A destination added to the hub is found by the next regular request."""
    full_config = gateway.config
    gateway.config = _without_destination(full_config, OTHER_DEST_ID)
    assert await setup_config_entry(hass, mock_config_entry)
    before = len(er.async_entries_for_config_entry(entity_registry, ENTRY_ID))

    gateway.config = full_config
    await mock_config_entry.runtime_data.coordinator.async_refresh()
    await hass.async_block_till_done()

    after = er.async_entries_for_config_entry(entity_registry, ENTRY_ID)
    assert len(after) > before


async def test_destination_that_disappears_loses_its_device(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    gateway: FakeGateway,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """The device goes when two readings in a row do not contain the destination."""
    assert await setup_config_entry(hass, mock_config_entry)
    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, str(OTHER_DEST_ID)), mock_config_entry.entry_id
    )
    assert device
    entities = er.async_entries_for_device(entity_registry, device.id)

    gateway.config = _without_destination(gateway.config, OTHER_DEST_ID)
    coordinator = mock_config_entry.runtime_data.coordinator
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    # The first reading only takes the entities away, their settings stay.
    assert device_registry.async_get(device.id)
    assert all(entity_registry.async_get(entity.entity_id) for entity in entities)
    assert all(
        hass.states.get(entity.entity_id).state == STATE_UNAVAILABLE
        for entity in entities
        if not entity.disabled
    )
    assert OTHER_DEST_ID not in coordinator.data

    await coordinator.async_refresh()
    await hass.async_block_till_done()

    assert device_registry.async_get(device.id) is None
    assert not any(entity_registry.async_get(entity.entity_id) for entity in entities)
    assert device_registry.async_get_device_by_identifier(
        (DOMAIN, str(DEST_ID)), mock_config_entry.entry_id
    )


async def test_destination_that_is_missing_once_keeps_its_device(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    gateway: FakeGateway,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """One incomplete answer of the hub does not delete a device."""
    full_config = gateway.config
    assert await setup_config_entry(hass, mock_config_entry)
    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, str(OTHER_DEST_ID)), mock_config_entry.entry_id
    )
    assert device
    entities = er.async_entries_for_device(entity_registry, device.id)
    coordinator = mock_config_entry.runtime_data.coordinator

    gateway.config = _without_destination(full_config, OTHER_DEST_ID)
    await coordinator.async_refresh()
    gateway.config = full_config
    await coordinator.async_refresh()
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    assert device_registry.async_get(device.id)
    assert all(
        hass.states.get(entity.entity_id).state != STATE_UNAVAILABLE
        for entity in entities
        if not entity.disabled
    )
    assert len(er.async_entries_for_device(entity_registry, device.id)) == len(entities)


async def test_device_can_only_be_deleted_when_the_hub_does_not_report_it(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    gateway: FakeGateway,
    device_registry: dr.DeviceRegistry,
) -> None:
    """The user may delete a device that is gone from the hub, not a present one."""
    assert await setup_config_entry(hass, mock_config_entry)
    present = device_registry.async_get_device_by_identifier(
        (DOMAIN, str(DEST_ID)), mock_config_entry.entry_id
    )
    assert present
    stale = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={(DOMAIN, "999")},
    )

    assert not await async_remove_config_entry_device(hass, mock_config_entry, present)
    assert await async_remove_config_entry_device(hass, mock_config_entry, stale)


async def test_destination_that_is_renamed_renames_its_device(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    gateway: FakeGateway,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """A new name on the hub becomes the device name, the entity ids stay."""
    assert await setup_config_entry(hass, mock_config_entry)
    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, str(DEST_ID)), ENTRY_ID
    )
    assert device is not None
    entity_ids = {
        e.entity_id for e in er.async_entries_for_device(entity_registry, device.id)
    }
    renamed = copy.deepcopy(gateway.config)
    for dest in renamed["destinations"]:
        if dest["id"] == DEST_ID:
            dest["names"] = ["Renamed", "", "", ""]
    gateway.config = renamed

    await mock_config_entry.runtime_data.coordinator.async_refresh()
    await hass.async_block_till_done()

    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, str(DEST_ID)), ENTRY_ID
    )
    assert device is not None
    assert device.name == "Renamed"
    assert entity_ids == {
        e.entity_id for e in er.async_entries_for_device(entity_registry, device.id)
    }


async def test_device_name_given_in_home_assistant_stays(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    gateway: FakeGateway,
    device_registry: dr.DeviceRegistry,
) -> None:
    """A name that the user gave to the device is not replaced."""
    assert await setup_config_entry(hass, mock_config_entry)
    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, str(DEST_ID)), ENTRY_ID
    )
    assert device is not None
    device_registry.async_update_device(device.id, name_by_user="My name")
    renamed = copy.deepcopy(gateway.config)
    for dest in renamed["destinations"]:
        if dest["id"] == DEST_ID:
            dest["names"] = ["Renamed", "", "", ""]
    gateway.config = renamed

    await mock_config_entry.runtime_data.coordinator.async_refresh()
    await hass.async_block_till_done()

    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, str(DEST_ID)), ENTRY_ID
    )
    assert device is not None
    assert device.name_by_user == "My name"
    assert device.name == "Renamed"
