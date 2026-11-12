"""Tests for the status polling of the WMS WebControl pro integration."""

from datetime import timedelta

import pytest
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)

from custom_components.wms_webcontrol_pro.const import (
    BASE_POLL_INTERVAL,
    RETRY_AFTER_FAILURE,
)
from pywmswebcontrolpro.refresh import RefreshResult
from pywmswebcontrolpro.travel import CoverModel

from .conftest import FakeGateway
from .helpers import setup_config_entry, unload_config_entry

DEST_ID = 18894
ENTITY_ID = "cover.wohnbereich_wohnebene_alle"
OTHER_DEST_ID = 116682
BUSY = {"errors": [0x50005]}

pytestmark = pytest.mark.parametrize(
    "gateway",
    [("config_prod_roller_shutter.json", "status_prod_roller_shutter.json")],
    indirect=True,
)


async def test_first_refresh_stores_the_outcome_of_every_destination(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, gateway: FakeGateway
) -> None:
    """The data of the coordinator holds one outcome per destination."""
    assert await setup_config_entry(hass, mock_config_entry)

    data = mock_config_entry.runtime_data.coordinator.data

    assert data[DEST_ID].result is RefreshResult.OK
    assert data[OTHER_DEST_ID].result is RefreshResult.EMPTY
    assert len(data) == 6


async def test_regular_interval_is_long(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, gateway: FakeGateway
) -> None:
    """The hub is asked rarely, commands trigger the extra requests."""
    assert await setup_config_entry(hass, mock_config_entry)

    coordinator = mock_config_entry.runtime_data.coordinator

    assert coordinator.update_interval == BASE_POLL_INTERVAL == timedelta(minutes=30)


async def test_regular_poll_asks_each_destination_once_without_retry(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, gateway: FakeGateway
) -> None:
    """A busy hub is counted, not retried and not treated as a failed update."""
    assert await setup_config_entry(hass, mock_config_entry)
    gateway.commands.clear()
    gateway.queue_status(DEST_ID, BUSY)

    coordinator = mock_config_entry.runtime_data.coordinator
    await coordinator.async_refresh()

    assert len(gateway.commands_named("getStatus")) == 6
    assert coordinator.last_update_success
    assert coordinator.data[DEST_ID].result is RefreshResult.BUSY
    dest = mock_config_entry.runtime_data.hub.dests[DEST_ID]
    assert dest.stats.busy == 1


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


async def test_regular_poll_skips_destinations_with_a_pending_refresh(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, gateway: FakeGateway
) -> None:
    """A destination that is about to be polled is not polled by the cycle."""
    assert await setup_config_entry(hass, mock_config_entry)
    coordinator = mock_config_entry.runtime_data.coordinator
    coordinator.async_schedule_refresh(DEST_ID, 120)
    gateway.commands.clear()

    await coordinator.async_refresh()

    asked = [c["destinations"][0] for c in gateway.commands_named("getStatus")]
    assert DEST_ID not in asked
    assert len(asked) == 5


async def test_regular_poll_skips_destinations_with_a_calculated_drive(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    gateway: FakeGateway,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A cover that is driving by calculation is not asked by the cycle."""
    assert await setup_config_entry(hass, mock_config_entry)
    hub = mock_config_entry.runtime_data.hub
    monkeypatch.setattr(
        CoverModel, "is_travelling", property(lambda self: True), raising=True
    )
    gateway.commands.clear()

    await mock_config_entry.runtime_data.coordinator.async_refresh()

    assert not gateway.commands_named("getStatus")
    assert hub.dests[DEST_ID].stats.ok == 1


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

    await coordinator.async_refresh()
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    assert coordinator.last_update_success
    assert hass.states.get(ENTITY_ID).state != STATE_UNAVAILABLE
    assert len(gateway.commands_named("getStatus")) == 12
    assert caplog.text.count("keeping the known one") == 1


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


async def test_hub_that_does_not_answer_is_unavailable_and_asked_again_soon(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, gateway: FakeGateway
) -> None:
    """A hub that answers nothing is asked again after a minute, not after 30."""
    assert await setup_config_entry(hass, mock_config_entry)
    coordinator = mock_config_entry.runtime_data.coordinator
    gateway.stop_answering("getConfiguration", "ping", "getStatus")

    await coordinator.async_refresh()
    await hass.async_block_till_done()
    assert not coordinator.last_update_success
    assert hass.states.get(ENTITY_ID).state == STATE_UNAVAILABLE

    gateway.stop_answering()
    async_fire_time_changed(
        hass, dt_util.utcnow() + timedelta(seconds=RETRY_AFTER_FAILURE + 1)
    )
    await hass.async_block_till_done(wait_background_tasks=True)

    assert coordinator.last_update_success
    assert hass.states.get(ENTITY_ID).state != STATE_UNAVAILABLE
    assert coordinator.update_interval == BASE_POLL_INTERVAL


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
