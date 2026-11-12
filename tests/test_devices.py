"""Tests for destinations that appear or disappear on the hub."""

import copy
from typing import Any

import pytest
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
) -> None:
    """A destination removed from the hub is removed from the device registry."""
    assert await setup_config_entry(hass, mock_config_entry)
    assert device_registry.async_get_device_by_identifier(
        (DOMAIN, str(OTHER_DEST_ID)), mock_config_entry.entry_id
    )

    gateway.config = _without_destination(gateway.config, OTHER_DEST_ID)
    coordinator = mock_config_entry.runtime_data.coordinator
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    assert (
        device_registry.async_get_device_by_identifier(
            (DOMAIN, str(OTHER_DEST_ID)), mock_config_entry.entry_id
        )
        is None
    )
    assert device_registry.async_get_device_by_identifier(
        (DOMAIN, str(DEST_ID)), mock_config_entry.entry_id
    )
    assert OTHER_DEST_ID not in coordinator.data


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
