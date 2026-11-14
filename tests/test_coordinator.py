"""Tests for the status polling of the WMS WebControl pro integration."""

from datetime import timedelta

import pytest
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)

from custom_components.wms_webcontrol_pro.const import (
    BASE_POLL_INTERVAL,
    DOMAIN,
    MIN_POLL_INTERVAL,
    RETRY_AFTER_FAILURE,
    STARTUP_POLL_INTERVAL,
)
from pywmswebcontrolpro.refresh import RefreshCause, RefreshResult
from pywmswebcontrolpro.travel import CoverModel

from .conftest import FakeGateway
from .helpers import (
    fire_regular_poll,
    fire_regular_polls,
    read_configuration,
    setup_config_entry,
    unload_config_entry,
)

DEST_ID = 18894
ENTITY_ID = "cover.wohnbereich_wohnebene_alle"
OTHER_DEST_ID = 116682
DEST_IDS = [18894, 116682, 172555, 230952, 284942, 328518]
# The hub and six destinations share the base interval.
TARGETS = len(DEST_IDS) + 1
BUSY = {"errors": [0x50005]}


def _asked(gateway: FakeGateway) -> list[int | str]:
    """Return the targets of the regular requests in the order they were sent."""
    return [
        c["destinations"][0] if c["command"] == "getStatus" else "hub"
        for c in gateway.commands
        if c["command"] in ("getStatus", "getConfiguration")
    ]


pytestmark = pytest.mark.parametrize(
    "gateway",
    [("config_prod_roller_shutter.json", "status_prod_roller_shutter.json")],
    indirect=True,
)


async def test_setup_reads_the_configuration_and_no_status(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, gateway: FakeGateway
) -> None:
    """The setup does not wait for the radio, the destinations are asked after it."""
    assert await setup_config_entry(hass, mock_config_entry, startup_polls=False)

    coordinator = mock_config_entry.runtime_data.coordinator

    assert _asked(gateway) == ["hub"]
    assert coordinator.data == {}
    assert coordinator.update_interval == STARTUP_POLL_INTERVAL


async def test_startup_asks_each_destination_once_in_quick_succession(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, gateway: FakeGateway
) -> None:
    """After the setup every destination is asked once, one request at a time."""
    assert await setup_config_entry(hass, mock_config_entry)

    coordinator = mock_config_entry.runtime_data.coordinator

    assert _asked(gateway) == ["hub", *DEST_IDS]
    assert coordinator.data[DEST_ID].result is RefreshResult.OK
    assert coordinator.data[OTHER_DEST_ID].result is RefreshResult.EMPTY
    assert len(coordinator.data) == len(DEST_IDS)
    assert coordinator.update_interval == BASE_POLL_INTERVAL / TARGETS


async def test_regular_requests_ask_one_target_in_turn(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, gateway: FakeGateway
) -> None:
    """Each interval asks one target, the hub and every destination in turn."""
    assert await setup_config_entry(hass, mock_config_entry)
    gateway.commands.clear()

    await fire_regular_poll(hass, mock_config_entry)
    assert _asked(gateway) == ["hub"]

    await fire_regular_polls(hass, mock_config_entry, TARGETS)

    assert _asked(gateway) == ["hub", *DEST_IDS, "hub"]
    stats = mock_config_entry.runtime_data.hub.dests[DEST_ID].stats
    assert stats.causes == {RefreshCause.SCHEDULED: {RefreshResult.OK: 2}}


async def test_busy_destination_is_not_retried_and_keeps_its_turn(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, gateway: FakeGateway
) -> None:
    """A busy answer is counted, the destination is asked again one round later."""
    assert await setup_config_entry(hass, mock_config_entry)
    gateway.commands.clear()
    gateway.queue_status(DEST_ID, BUSY)
    coordinator = mock_config_entry.runtime_data.coordinator

    await fire_regular_polls(hass, mock_config_entry, 2)

    assert _asked(gateway) == ["hub", DEST_ID]
    assert coordinator.last_update_success
    assert coordinator.data[DEST_ID].result is RefreshResult.BUSY
    assert mock_config_entry.runtime_data.hub.dests[DEST_ID].stats.busy == 1

    await fire_regular_polls(hass, mock_config_entry, TARGETS)

    assert _asked(gateway) == ["hub", *DEST_IDS, "hub", DEST_ID]


async def test_request_after_a_command_moves_the_destination_to_the_end(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, gateway: FakeGateway
) -> None:
    """A destination that was just asked after a command is asked last."""
    assert await setup_config_entry(hass, mock_config_entry)
    coordinator = mock_config_entry.runtime_data.coordinator
    await coordinator.async_refresh_destination(DEST_ID)
    gateway.commands.clear()

    await fire_regular_polls(hass, mock_config_entry, TARGETS)

    assert _asked(gateway) == ["hub", *DEST_IDS[1:], DEST_ID]
    stats = mock_config_entry.runtime_data.hub.dests[DEST_ID].stats
    assert stats.causes[RefreshCause.COMMAND] == {RefreshResult.OK: 1}


async def test_regular_requests_skip_a_destination_with_a_pending_refresh(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, gateway: FakeGateway
) -> None:
    """A destination that is about to be asked gives its turn to the next one."""
    assert await setup_config_entry(hass, mock_config_entry)
    coordinator = mock_config_entry.runtime_data.coordinator
    coordinator.async_schedule_refresh(DEST_ID, 3600)
    gateway.commands.clear()

    await fire_regular_polls(hass, mock_config_entry, 3)

    assert _asked(gateway) == ["hub", *DEST_IDS[1:3]]


async def test_regular_requests_skip_destinations_with_a_calculated_drive(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    gateway: FakeGateway,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A cover that is driving by calculation is not asked."""
    assert await setup_config_entry(hass, mock_config_entry)
    monkeypatch.setattr(
        CoverModel, "is_travelling", property(lambda self: True), raising=True
    )
    gateway.commands.clear()

    await fire_regular_polls(hass, mock_config_entry, 3)

    assert _asked(gateway) == ["hub", "hub", "hub"]


async def test_disabled_device_is_not_asked(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    gateway: FakeGateway,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Nobody sees the status of a disabled device, so it is not requested."""
    assert await setup_config_entry(hass, mock_config_entry)
    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, str(DEST_ID)), mock_config_entry.entry_id
    )
    assert device is not None
    device_registry.async_update_device(
        device.id, disabled_by=dr.DeviceEntryDisabler.USER
    )
    await hass.async_block_till_done()
    coordinator = mock_config_entry.runtime_data.coordinator
    gateway.commands.clear()

    await coordinator.async_refresh()
    await coordinator.async_refresh()
    coordinator.async_schedule_refresh_all(5, "scene")
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=6))
    await hass.async_block_till_done(wait_background_tasks=True)

    assert DEST_ID not in _asked(gateway)
    assert _asked(gateway)[:2] == ["hub", OTHER_DEST_ID]
    assert coordinator.update_interval == BASE_POLL_INTERVAL / (TARGETS - 1)


async def test_new_destination_is_asked_with_the_next_request(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, gateway: FakeGateway
) -> None:
    """A destination that appears on the hub does not wait for a whole round."""
    full_config = gateway.config
    gateway.config = {
        **full_config,
        "destinations": [
            d for d in full_config["destinations"] if d["id"] != OTHER_DEST_ID
        ],
    }
    assert await setup_config_entry(hass, mock_config_entry)
    coordinator = mock_config_entry.runtime_data.coordinator
    assert coordinator.update_interval == BASE_POLL_INTERVAL / (TARGETS - 1)
    gateway.config = full_config
    gateway.commands.clear()

    await read_configuration(mock_config_entry)
    assert coordinator.update_interval == STARTUP_POLL_INTERVAL
    await fire_regular_poll(hass, mock_config_entry)

    assert _asked(gateway) == ["hub", OTHER_DEST_ID]
    assert coordinator.update_interval == BASE_POLL_INTERVAL / TARGETS


async def test_interval_has_a_lower_limit(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    gateway: FakeGateway,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A hub with many destinations is not asked without a pause."""
    monkeypatch.setattr(
        "custom_components.wms_webcontrol_pro.coordinator.BASE_POLL_INTERVAL",
        timedelta(seconds=14),
    )
    assert await setup_config_entry(hass, mock_config_entry)

    coordinator = mock_config_entry.runtime_data.coordinator

    assert coordinator.update_interval == MIN_POLL_INTERVAL


async def test_failed_configuration_request_keeps_the_entities_available(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    gateway: FakeGateway,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """One request without an answer is no reason to mark the hub as gone."""
    assert await setup_config_entry(hass, mock_config_entry)
    coordinator = mock_config_entry.runtime_data.coordinator
    gateway.stop_answering("getConfiguration")
    gateway.commands.clear()

    await fire_regular_polls(hass, mock_config_entry, 2 * TARGETS)

    assert coordinator.last_update_success
    assert hass.states.get(ENTITY_ID).state != STATE_UNAVAILABLE
    assert _asked(gateway) == ["hub", *DEST_IDS, "hub", *DEST_IDS]
    assert caplog.text.count("keeping the known one") == 1


async def test_failed_status_request_keeps_the_entities_available(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, gateway: FakeGateway
) -> None:
    """A status request without an answer is counted while the hub answers a ping."""
    assert await setup_config_entry(hass, mock_config_entry)
    coordinator = mock_config_entry.runtime_data.coordinator
    gateway.stop_answering("getStatus")

    await fire_regular_polls(hass, mock_config_entry, 2)

    assert coordinator.last_update_success
    assert coordinator.data[DEST_ID].result is RefreshResult.ERROR
    assert hass.states.get(ENTITY_ID).state != STATE_UNAVAILABLE


async def test_hub_that_stops_answering_is_noticed_by_the_next_status_request(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, gateway: FakeGateway
) -> None:
    """A silent hub is noticed without waiting for the next configuration read."""
    assert await setup_config_entry(hass, mock_config_entry)
    coordinator = mock_config_entry.runtime_data.coordinator
    await fire_regular_poll(hass, mock_config_entry)
    gateway.stop_answering("getConfiguration", "ping", "getStatus")
    gateway.commands.clear()

    await fire_regular_poll(hass, mock_config_entry)

    assert _asked(gateway) == [DEST_ID]
    assert not coordinator.last_update_success
    assert hass.states.get(ENTITY_ID).state == STATE_UNAVAILABLE


async def test_hub_that_does_not_answer_is_asked_again_soon(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, gateway: FakeGateway
) -> None:
    """A hub that answers nothing is asked again after a minute, the hub first."""
    assert await setup_config_entry(hass, mock_config_entry)
    coordinator = mock_config_entry.runtime_data.coordinator
    gateway.stop_answering("getConfiguration", "ping", "getStatus")

    await fire_regular_poll(hass, mock_config_entry)
    assert not coordinator.last_update_success
    assert hass.states.get(ENTITY_ID).state == STATE_UNAVAILABLE
    gateway.commands.clear()

    async_fire_time_changed(
        hass, dt_util.utcnow() + timedelta(seconds=RETRY_AFTER_FAILURE + 1)
    )
    await hass.async_block_till_done(wait_background_tasks=True)
    assert _asked(gateway) == ["hub"]
    assert not coordinator.last_update_success

    gateway.stop_answering()
    async_fire_time_changed(
        hass, dt_util.utcnow() + timedelta(seconds=RETRY_AFTER_FAILURE + 1)
    )
    await hass.async_block_till_done(wait_background_tasks=True)

    assert _asked(gateway) == ["hub", "hub"]
    assert coordinator.last_update_success
    assert hass.states.get(ENTITY_ID).state != STATE_UNAVAILABLE
    assert coordinator.update_interval == BASE_POLL_INTERVAL / TARGETS


async def test_request_after_a_command_notices_a_hub_that_stopped_answering(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, gateway: FakeGateway
) -> None:
    """The request after a command marks the entities of a silent hub."""
    assert await setup_config_entry(hass, mock_config_entry)
    coordinator = mock_config_entry.runtime_data.coordinator
    gateway.stop_answering("ping", "getStatus")

    outcome = await coordinator.async_refresh_destination(DEST_ID)
    await hass.async_block_till_done()

    assert outcome is None
    assert not coordinator.last_update_success
    assert hass.states.get(ENTITY_ID).state == STATE_UNAVAILABLE


async def test_scheduled_refresh_asks_only_one_destination(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, gateway: FakeGateway
) -> None:
    """A scheduled refresh sends one request after its delay and updates the data."""
    assert await setup_config_entry(hass, mock_config_entry)
    coordinator = mock_config_entry.runtime_data.coordinator
    gateway.commands.clear()

    coordinator.async_schedule_refresh(DEST_ID, 5)
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=4))
    await hass.async_block_till_done(wait_background_tasks=True)
    assert not gateway.commands

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=6))
    await hass.async_block_till_done(wait_background_tasks=True)

    assert [c["destinations"] for c in gateway.commands_named("getStatus")] == [
        [DEST_ID]
    ]


async def test_new_schedule_replaces_the_pending_one(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, gateway: FakeGateway
) -> None:
    """Only the latest scheduled refresh of a destination runs."""
    assert await setup_config_entry(hass, mock_config_entry)
    coordinator = mock_config_entry.runtime_data.coordinator
    gateway.commands.clear()

    coordinator.async_schedule_refresh(DEST_ID, 2)
    coordinator.async_schedule_refresh(DEST_ID, 5)
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=3))
    await hass.async_block_till_done(wait_background_tasks=True)
    assert not gateway.commands

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=6))
    await hass.async_block_till_done(wait_background_tasks=True)

    assert len(gateway.commands_named("getStatus")) == 1


async def test_listeners_are_notified_by_a_scheduled_refresh(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, gateway: FakeGateway
) -> None:
    """The entities are told when a single destination was refreshed."""
    assert await setup_config_entry(hass, mock_config_entry)
    coordinator = mock_config_entry.runtime_data.coordinator
    calls: list[int] = []
    coordinator.async_add_listener(lambda: calls.append(1))

    outcome = await coordinator.async_refresh_destination(DEST_ID)

    assert outcome.result is RefreshResult.OK
    assert calls == [1]
    assert coordinator.data[DEST_ID] is outcome


async def test_pending_refresh_is_cancelled_on_unload(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, gateway: FakeGateway
) -> None:
    """Unloading the entry cancels scheduled refreshes."""
    assert await setup_config_entry(hass, mock_config_entry)
    mock_config_entry.runtime_data.coordinator.async_schedule_refresh(DEST_ID, 5)
    gateway.commands.clear()

    assert await unload_config_entry(hass, mock_config_entry)
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=10))
    await hass.async_block_till_done(wait_background_tasks=True)

    assert not gateway.commands


async def test_configuration_that_is_not_understood_keeps_the_known_one(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, gateway: FakeGateway
) -> None:
    """A broken configuration does not remove destinations or devices."""
    assert await setup_config_entry(hass, mock_config_entry)
    coordinator = mock_config_entry.runtime_data.coordinator
    gateway.config = {"rooms": [], "scenes": []}

    await coordinator.async_refresh()
    await hass.async_block_till_done()

    assert coordinator.last_update_success
    assert len(coordinator.hub.dests) == 6
    assert hass.states.get(ENTITY_ID).state != STATE_UNAVAILABLE


async def test_requests_with_different_keys_do_not_replace_each_other(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, gateway: FakeGateway
) -> None:
    """Two drives of one destination each keep their own request."""
    assert await setup_config_entry(hass, mock_config_entry)
    coordinator = mock_config_entry.runtime_data.coordinator
    gateway.commands.clear()

    coordinator.async_schedule_refresh(DEST_ID, 5, "first")
    coordinator.async_schedule_refresh(DEST_ID, 10, "second")
    coordinator.async_schedule_refresh(DEST_ID, 20, "second")
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=12))
    await hass.async_block_till_done(wait_background_tasks=True)
    assert len(gateway.commands_named("getStatus")) == 1

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=22))
    await hass.async_block_till_done(wait_background_tasks=True)
    assert len(gateway.commands_named("getStatus")) == 2
