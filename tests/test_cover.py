"""Tests for the covers of the WMS WebControl pro integration."""

from datetime import timedelta
from typing import Any

import pytest
from homeassistant.components.cover import (
    ATTR_CURRENT_POSITION,
    ATTR_CURRENT_TILT_POSITION,
    ATTR_POSITION,
    ATTR_TILT_POSITION,
    DOMAIN as COVER_DOMAIN,
    SERVICE_CLOSE_COVER,
    SERVICE_OPEN_COVER,
    SERVICE_SET_COVER_POSITION,
    SERVICE_SET_COVER_TILT_POSITION,
    SERVICE_STOP_COVER,
)
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)
from pytest_homeassistant_custom_component.test_util.aiohttp import (
    AiohttpClientMocker,
)

from custom_components.wms_webcontrol_pro.const import (
    ATTR_POSITION_SOURCE,
    DOMAIN,
    FOLLOW_UP_POLL_DELAY,
    SERVICE_SET_COVER_POSITION_AND_TILT,
)
from pywmswebcontrolpro.const import (
    WMS_WebControl_pro_API_actionDescription as ACTION_DESC,
)
from pywmswebcontrolpro.store import TravelDirection

from .conftest import COMMAND_URL, FakeGateway
from .helpers import setup_config_entry

ROLLER = "cover.wohnbereich_wohnebene_alle"
ROLLER_ID = 18894
SLAT = "cover.zonwering_begane_grond_keuken_alle"
SLAT_ID = 413716
AWNING = "cover.raum_0_markise"
VALANCE = "cover.raum_0_markise_2"
AWNING_ID = 58717

ROLLER_SETUP = ("config_prod_roller_shutter.json", "status_prod_roller_shutter.json")
SLAT_SETUP = ("config_prod_slat_rotate.json", "status_prod_slat_rotate.json")
AWNING_SETUP = ("config_prod_awning_valance.json", "status_prod_valance.json")


class FakeClock:
    """Replace the monotonic clock used by the covers."""

    def __init__(self) -> None:
        """Start at a fixed time."""
        self.now = 1000.0

    def __call__(self) -> float:
        """Return the current time."""
        return self.now


@pytest.fixture
def clock(monkeypatch: pytest.MonkeyPatch) -> FakeClock:
    """Control the time of the calculated drives."""
    fake = FakeClock()
    monkeypatch.setattr("custom_components.wms_webcontrol_pro.cover.monotonic", fake)
    return fake


def _drive_commands(gateway: FakeGateway) -> list[dict[str, Any]]:
    """Return the action requests sent to the hub."""
    return [c for c in gateway.commands if c["command"] == "action"]


def _parameters(command: dict[str, Any]) -> list[dict[str, Any]]:
    """Return the parameters of every action of a request."""
    return [a["parameters"] for a in command["actions"]]


async def _call(hass: HomeAssistant, service: str, entity_id: str, **data: Any) -> None:
    """Call a cover service and wait for the state."""
    await hass.services.async_call(
        COVER_DOMAIN, service, {ATTR_ENTITY_ID: entity_id, **data}, blocking=True
    )


@pytest.mark.parametrize(
    ("gateway", "entity_id", "state", "position"),
    [
        (ROLLER_SETUP, ROLLER, "closed", 0),
        (AWNING_SETUP, AWNING, "closed", 0),
        (AWNING_SETUP, VALANCE, "closed", 0),
        (SLAT_SETUP, SLAT, "closed", 0),
    ],
    indirect=["gateway"],
)
@pytest.mark.usefixtures("gateway")
async def test_cover_shows_the_measured_position(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_id: str,
    state: str,
    position: int,
) -> None:
    """The setup poll fills the position, the source is the measurement."""
    assert await setup_config_entry(hass, mock_config_entry)

    cover = hass.states.get(entity_id)

    assert cover is not None
    assert cover.state == state
    assert cover.attributes[ATTR_CURRENT_POSITION] == position
    assert cover.attributes[ATTR_POSITION_SOURCE] == "measured"


@pytest.mark.parametrize("gateway", [AWNING_SETUP], indirect=True)
@pytest.mark.usefixtures("gateway")
async def test_awning_and_valance_are_separate_covers(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Both covers of one destination keep their own unique id."""
    assert await setup_config_entry(hass, mock_config_entry)

    registry = er.async_get(hass)

    assert registry.async_get(AWNING).unique_id == str(AWNING_ID)
    assert registry.async_get(VALANCE).unique_id == f"{AWNING_ID}-valance"


@pytest.mark.parametrize("gateway", [SLAT_SETUP], indirect=True)
@pytest.mark.usefixtures("gateway")
async def test_slat_cover_shows_the_measured_tilt(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """The rotation of the setup poll becomes the tilt position."""
    assert await setup_config_entry(hass, mock_config_entry)

    cover = hass.states.get(SLAT)

    assert cover is not None
    assert cover.attributes[ATTR_CURRENT_TILT_POSITION] == 50


@pytest.mark.parametrize("gateway", [ROLLER_SETUP], indirect=True)
@pytest.mark.parametrize(
    ("service", "data", "percentage"),
    [
        (SERVICE_OPEN_COVER, {}, 0),
        (SERVICE_CLOSE_COVER, {}, 100),
        (SERVICE_SET_COVER_POSITION, {ATTR_POSITION: 30}, 70),
    ],
)
async def test_drive_command_uses_the_wms_scale(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    gateway: FakeGateway,
    service: str,
    data: dict[str, Any],
    percentage: int,
) -> None:
    """The hub scale is 0 open and 100 closed, Home Assistant is the reverse."""
    assert await setup_config_entry(hass, mock_config_entry)
    gateway.commands.clear()

    await _call(hass, service, ROLLER, **data)

    (command,) = _drive_commands(gateway)
    assert command["actions"][0]["destinationId"] == ROLLER_ID
    assert _parameters(command) == [{"percentage": percentage}]


@pytest.mark.parametrize("gateway", [ROLLER_SETUP], indirect=True)
@pytest.mark.usefixtures("clock")
async def test_unknown_travel_time_jumps_to_the_target(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, gateway: FakeGateway
) -> None:
    """Without travel times the target is shown at once and calculated."""
    assert await setup_config_entry(hass, mock_config_entry)

    await _call(hass, SERVICE_OPEN_COVER, ROLLER)

    cover = hass.states.get(ROLLER)
    assert cover is not None
    assert cover.state == "open"
    assert cover.attributes[ATTR_CURRENT_POSITION] == 100
    assert cover.attributes[ATTR_POSITION_SOURCE] == "calculated"


@pytest.mark.parametrize("gateway", [ROLLER_SETUP], indirect=True)
async def test_known_travel_time_interpolates_the_position(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    gateway: FakeGateway,
    clock: FakeClock,
) -> None:
    """A drive with a travel time shows opening and moves the position."""
    assert await setup_config_entry(hass, mock_config_entry)
    dest = mock_config_entry.runtime_data.hub.dests[ROLLER_ID]
    await dest.action(ACTION_DESC.RollerShutterBlindDrive).set_travel_time(
        TravelDirection.OPEN, 20
    )

    await _call(hass, SERVICE_OPEN_COVER, ROLLER)
    assert hass.states.get(ROLLER).state == "opening"

    clock.now += 10
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=2))
    await hass.async_block_till_done(wait_background_tasks=True)
    assert hass.states.get(ROLLER).attributes[ATTR_CURRENT_POSITION] == 50

    clock.now += 10
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=4))
    await hass.async_block_till_done(wait_background_tasks=True)
    cover = hass.states.get(ROLLER)
    assert cover.state == "open"
    assert cover.attributes[ATTR_CURRENT_POSITION] == 100


@pytest.mark.parametrize("gateway", [ROLLER_SETUP], indirect=True)
@pytest.mark.usefixtures("clock")
async def test_command_requests_the_state_afterwards(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, gateway: FakeGateway
) -> None:
    """The settle poll asks only the moved destination and shows the result."""
    assert await setup_config_entry(hass, mock_config_entry)
    gateway.queue_status(
        ROLLER_ID,
        {
            "details": [
                {
                    "destinationId": ROLLER_ID,
                    "data": {
                        "productData": [{"actionId": 0, "value": {"percentage": 0}}]
                    },
                }
            ]
        },
    )
    await _call(hass, SERVICE_OPEN_COVER, ROLLER)
    gateway.commands.clear()

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=130))
    await hass.async_block_till_done(wait_background_tasks=True)

    assert [c["destinations"] for c in gateway.commands_named("getStatus")] == [
        [ROLLER_ID]
    ]
    cover = hass.states.get(ROLLER)
    assert cover.attributes[ATTR_CURRENT_POSITION] == 100
    assert cover.attributes[ATTR_POSITION_SOURCE] == "measured"


@pytest.mark.parametrize("gateway", [ROLLER_SETUP], indirect=True)
@pytest.mark.usefixtures("clock")
async def test_stop_sends_the_stop_command_and_freezes_the_drive(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, gateway: FakeGateway
) -> None:
    """Stop is a manual command of the destination and ends the calculation."""
    assert await setup_config_entry(hass, mock_config_entry)
    dest = mock_config_entry.runtime_data.hub.dests[ROLLER_ID]
    await dest.action(ACTION_DESC.RollerShutterBlindDrive).set_travel_time(
        TravelDirection.OPEN, 20
    )
    await _call(hass, SERVICE_OPEN_COVER, ROLLER)
    gateway.commands.clear()

    await _call(hass, SERVICE_STOP_COVER, ROLLER)

    (command,) = _drive_commands(gateway)
    assert command["actions"][0]["destinationId"] == ROLLER_ID
    assert not dest.action(ACTION_DESC.RollerShutterBlindDrive).model.is_travelling


@pytest.mark.parametrize("gateway", [ROLLER_SETUP], indirect=True)
@pytest.mark.usefixtures("clock")
async def test_rejected_command_keeps_the_state_and_checks_the_hub(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, gateway: FakeGateway
) -> None:
    """A command the hub refuses does not change the shown position."""
    assert await setup_config_entry(hass, mock_config_entry)
    gateway.action_response = {"errors": [1]}
    gateway.commands.clear()

    await _call(hass, SERVICE_OPEN_COVER, ROLLER)

    cover = hass.states.get(ROLLER)
    assert cover.state == "closed"
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=130))
    await hass.async_block_till_done(wait_background_tasks=True)
    assert len(gateway.commands_named("getStatus")) == 1


@pytest.mark.parametrize("gateway", [ROLLER_SETUP], indirect=True)
async def test_unreachable_hub_raises_an_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    gateway: FakeGateway,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """A failed request is reported to the caller."""
    assert await setup_config_entry(hass, mock_config_entry)
    aioclient_mock.clear_requests()
    aioclient_mock.post(COMMAND_URL, exc=TimeoutError)

    with pytest.raises(HomeAssistantError) as error:
        await _call(hass, SERVICE_OPEN_COVER, ROLLER)

    assert error.value.translation_key == "command_failed"


@pytest.mark.parametrize("gateway", [ROLLER_SETUP], indirect=True)
@pytest.mark.usefixtures("clock")
async def test_deviating_measurement_is_checked_again_a_limited_number_of_times(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, gateway: FakeGateway
) -> None:
    """A cover that moved on its own is asked again, but not forever."""
    assert await setup_config_entry(hass, mock_config_entry)
    coordinator = mock_config_entry.runtime_data.coordinator
    answers = [
        {
            "details": [
                {
                    "destinationId": ROLLER_ID,
                    "data": {
                        "productData": [
                            {"actionId": 0, "value": {"percentage": percentage}}
                        ]
                    },
                }
            ]
        }
        for percentage in (80, 60, 40, 20, 0)
    ]
    gateway.queue_status(ROLLER_ID, *answers)
    gateway.commands.clear()

    await coordinator.async_refresh()
    for step in range(1, 6):
        async_fire_time_changed(
            hass, dt_util.utcnow() + timedelta(seconds=FOLLOW_UP_POLL_DELAY * step + 1)
        )
        await hass.async_block_till_done(wait_background_tasks=True)

    # One regular request and three follow-up requests.
    asked = [
        c
        for c in gateway.commands_named("getStatus")
        if c["destinations"] == [ROLLER_ID]
    ]
    assert len(asked) == 4


@pytest.mark.parametrize("gateway", [SLAT_SETUP], indirect=True)
@pytest.mark.parametrize(
    ("service", "data", "rotation"),
    [
        (SERVICE_SET_COVER_TILT_POSITION, {ATTR_TILT_POSITION: 100}, -128),
        (SERVICE_SET_COVER_TILT_POSITION, {ATTR_TILT_POSITION: 0}, 127),
    ],
)
@pytest.mark.usefixtures("clock")
async def test_tilt_command_uses_the_rotation_range(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    gateway: FakeGateway,
    service: str,
    data: dict[str, Any],
    rotation: int,
) -> None:
    """Tilt 100 maps to the minimum rotation, tilt 0 to the maximum rotation."""
    assert await setup_config_entry(hass, mock_config_entry)
    gateway.commands.clear()

    await _call(hass, service, SLAT, **data)

    (command,) = _drive_commands(gateway)
    assert _parameters(command) == [{"rotation": rotation}]


@pytest.mark.parametrize("gateway", [SLAT_SETUP], indirect=True)
@pytest.mark.usefixtures("clock")
async def test_position_and_tilt_service_sends_both_in_one_request(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, gateway: FakeGateway
) -> None:
    """The service moves and tilts with a single request."""
    assert await setup_config_entry(hass, mock_config_entry)
    gateway.commands.clear()

    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_COVER_POSITION_AND_TILT,
        {ATTR_ENTITY_ID: SLAT, ATTR_POSITION: 40, ATTR_TILT_POSITION: 100},
        blocking=True,
    )

    (command,) = _drive_commands(gateway)
    assert _parameters(command) == [{"percentage": 60}, {"rotation": -128}]
    cover = hass.states.get(SLAT)
    assert cover.attributes[ATTR_CURRENT_POSITION] == 40
    assert cover.attributes[ATTR_CURRENT_TILT_POSITION] == 100
