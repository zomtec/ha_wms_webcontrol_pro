"""Tests for the diagnostic entities of the hub and the polling statistics."""

import time
from datetime import timedelta

import pytest
from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.components.scene import DOMAIN as SCENE_DOMAIN
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.wms_webcontrol_pro.const import DOMAIN

from .conftest import ENTRY_ID, FakeGateway
from .helpers import setup_config_entry

DEST_ID = 18894
DESTINATIONS = 6
SCENE_ID = 687471
BUSY = {"errors": [0x50005]}

ROLLER_SETUP = ("config_prod_roller_shutter.json", "status_prod_roller_shutter.json")
SCENE_SETUP = ("config_prod_awning_dimmer.json", "status_prod_dimmer.json")

roller_shutter = pytest.mark.parametrize("gateway", [ROLLER_SETUP], indirect=True)


def _entity_id(hass: HomeAssistant, domain: str, unique_id: str) -> str:
    """Return the entity id of an entity by its unique id."""
    entity_id = er.async_get(hass).async_get_entity_id(domain, DOMAIN, unique_id)
    assert entity_id is not None
    return entity_id


@roller_shutter
@pytest.mark.usefixtures("gateway")
async def test_hub_device_has_enabled_diagnostic_entities(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """The device of the hub shows its connection and the polling statistics."""
    assert await setup_config_entry(hass, mock_config_entry)

    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, ENTRY_ID), ENTRY_ID
    )
    assert device is not None
    entities = er.async_entries_for_device(entity_registry, device.id)
    assert {entity.unique_id for entity in entities} == {
        f"{ENTRY_ID}-connectivity",
        f"{ENTRY_ID}-poll-success-rate",
        f"{ENTRY_ID}-last-successful-poll",
    }
    assert all(hass.states.get(entity.entity_id) for entity in entities)


@roller_shutter
@pytest.mark.usefixtures("gateway")
@pytest.mark.parametrize(
    "key", ["poll-success-rate", "last-successful-poll", "last-answer-time"]
)
async def test_destination_statistics_are_disabled_by_default(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    key: str,
) -> None:
    """The statistics of a destination exist but have to be enabled."""
    assert await setup_config_entry(hass, mock_config_entry)

    entry = entity_registry.async_get(
        _entity_id(hass, SENSOR_DOMAIN, f"{DEST_ID}-{key}")
    )

    assert entry is not None
    assert entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION
    assert hass.states.get(entry.entity_id) is None


@roller_shutter
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_destination_statistics_follow_the_polls(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, gateway: FakeGateway
) -> None:
    """A poll without data lowers the rate and keeps the time of the last one."""
    assert await setup_config_entry(hass, mock_config_entry)
    rate = _entity_id(hass, SENSOR_DOMAIN, f"{DEST_ID}-poll-success-rate")
    last = _entity_id(hass, SENSOR_DOMAIN, f"{DEST_ID}-last-successful-poll")
    dest = mock_config_entry.runtime_data.hub.dests[DEST_ID]
    last_ok = dest.stats.last_ok
    assert last_ok is not None
    assert float(hass.states.get(rate).state) == 100
    assert dt_util.parse_datetime(hass.states.get(last).state) == last_ok.replace(
        microsecond=0
    )

    gateway.queue_status(DEST_ID, BUSY)
    await mock_config_entry.runtime_data.coordinator.async_refresh_destination(DEST_ID)
    await hass.async_block_till_done()

    assert float(hass.states.get(rate).state) == 50
    assert dt_util.parse_datetime(hass.states.get(last).state) == last_ok.replace(
        microsecond=0
    )


@roller_shutter
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_answer_time_is_the_duration_of_the_last_answer(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, gateway: FakeGateway
) -> None:
    """The sensor shows how long the hub took, also for a busy answer."""
    assert await setup_config_entry(hass, mock_config_entry)
    answer_time = _entity_id(hass, SENSOR_DOMAIN, f"{DEST_ID}-last-answer-time")
    dest = mock_config_entry.runtime_data.hub.dests[DEST_ID]
    assert float(hass.states.get(answer_time).state) == pytest.approx(
        dest.stats.last_duration, abs=1e-6
    )

    gateway.queue_status(DEST_ID, BUSY)
    await mock_config_entry.runtime_data.coordinator.async_refresh_destination(DEST_ID)
    await hass.async_block_till_done()
    assert float(hass.states.get(answer_time).state) == pytest.approx(
        dest.stats.last_duration, abs=1e-6
    )

    gateway.stop_answering("getStatus")
    await mock_config_entry.runtime_data.coordinator.async_refresh_destination(DEST_ID)
    await hass.async_block_till_done()

    assert hass.states.get(answer_time).state == STATE_UNKNOWN


@roller_shutter
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_success_rate_looks_back_a_day(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    gateway: FakeGateway,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A poll that is older than 24 hours does not count for the rate."""
    assert await setup_config_entry(hass, mock_config_entry)
    rate = _entity_id(hass, SENSOR_DOMAIN, f"{DEST_ID}-poll-success-rate")
    coordinator = mock_config_entry.runtime_data.coordinator
    gateway.queue_status(DEST_ID, BUSY)
    await coordinator.async_refresh_destination(DEST_ID)
    await hass.async_block_till_done()
    assert float(hass.states.get(rate).state) == 50

    later = time.monotonic() + timedelta(hours=25).total_seconds()
    monkeypatch.setattr("pywmswebcontrolpro.destination.time.monotonic", lambda: later)
    monkeypatch.setattr("pywmswebcontrolpro.refresh.time.monotonic", lambda: later)
    await coordinator.async_refresh_destination(DEST_ID)
    await hass.async_block_till_done()

    assert float(hass.states.get(rate).state) == 0


@roller_shutter
@pytest.mark.usefixtures("gateway", "entity_registry_enabled_by_default")
async def test_destination_without_a_successful_poll_has_no_time(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """A destination that never delivered data has a rate of 0 and no time."""
    assert await setup_config_entry(hass, mock_config_entry)
    dest_id = 116682

    rate = hass.states.get(
        _entity_id(hass, SENSOR_DOMAIN, f"{dest_id}-poll-success-rate")
    )
    last = hass.states.get(
        _entity_id(hass, SENSOR_DOMAIN, f"{dest_id}-last-successful-poll")
    )

    assert float(rate.state) == 0
    assert last.state == STATE_UNKNOWN


@roller_shutter
@pytest.mark.usefixtures("gateway")
async def test_hub_statistics_combine_all_destinations(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """The hub shows the rate over all destinations and the latest poll with data."""
    assert await setup_config_entry(hass, mock_config_entry)
    hub = mock_config_entry.runtime_data.hub
    last_ok = hub.dests[DEST_ID].stats.last_ok
    assert last_ok is not None

    rate = hass.states.get(
        _entity_id(hass, SENSOR_DOMAIN, f"{ENTRY_ID}-poll-success-rate")
    )
    last = hass.states.get(
        _entity_id(hass, SENSOR_DOMAIN, f"{ENTRY_ID}-last-successful-poll")
    )

    assert float(rate.state) == pytest.approx(100 / DESTINATIONS)
    assert dt_util.parse_datetime(last.state) == last_ok.replace(microsecond=0)


@roller_shutter
async def test_connectivity_follows_the_answers_of_the_hub(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, gateway: FakeGateway
) -> None:
    """The entities of the hub stay available and show that it is silent."""
    assert await setup_config_entry(hass, mock_config_entry)
    connectivity = _entity_id(hass, BINARY_SENSOR_DOMAIN, f"{ENTRY_ID}-connectivity")
    rate = _entity_id(hass, SENSOR_DOMAIN, f"{ENTRY_ID}-poll-success-rate")
    assert hass.states.get(connectivity).state == STATE_ON

    gateway.stop_answering("getConfiguration", "ping", "getStatus")
    await mock_config_entry.runtime_data.coordinator.async_refresh()
    await hass.async_block_till_done()

    assert hass.states.get(connectivity).state == STATE_OFF
    assert float(hass.states.get(rate).state) == pytest.approx(100 / DESTINATIONS)


@pytest.mark.parametrize("gateway", [SCENE_SETUP], indirect=True)
async def test_scene_without_a_room_belongs_to_the_hub(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    gateway: FakeGateway,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """A scene that the hub lists in no room is an entity of the hub device."""
    gateway.config = {
        **gateway.config,
        "rooms": [{**room, "scenes": []} for room in gateway.config["rooms"]],
    }
    assert await setup_config_entry(hass, mock_config_entry)

    entry = entity_registry.async_get(_entity_id(hass, SCENE_DOMAIN, str(SCENE_ID)))
    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, ENTRY_ID), ENTRY_ID
    )

    assert entry is not None
    assert device is not None
    assert entry.device_id == device.id
