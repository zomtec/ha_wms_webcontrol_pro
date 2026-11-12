"""Tests for the numbers and buttons of the WMS WebControl pro integration."""

from datetime import timedelta
from typing import Any

import pytest
from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.components.number import (
    ATTR_VALUE,
    DOMAIN as NUMBER_DOMAIN,
    SERVICE_SET_VALUE,
)
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)

from pywmswebcontrolpro.const import (
    WMS_WebControl_pro_API_actionDescription as ACTION_DESC,
)
from pywmswebcontrolpro.store import TravelDirection

from .conftest import FakeGateway
from .helpers import setup_config_entry

ROLLER_ID = 18894
SLAT_ID = 413716
AWNING_ID = 58717

ROLLER_SETUP = ("config_prod_roller_shutter.json", "status_prod_roller_shutter.json")
SLAT_SETUP = ("config_prod_slat_rotate.json", "status_prod_slat_rotate.json")
AWNING_SETUP = ("config_prod_awning_valance.json", "status_prod_valance.json")


def _entity_id(hass: HomeAssistant, domain: str, unique_id: str) -> str:
    """Return the entity id of an entity by its unique id."""
    entity_id = er.async_get(hass).async_get_entity_id(
        domain, "wms_webcontrol_pro", unique_id
    )
    assert entity_id is not None
    return entity_id


@pytest.mark.parametrize(
    ("gateway", "unique_ids"),
    [
        (
            ROLLER_SETUP,
            [f"{ROLLER_ID}-travel-time-open", f"{ROLLER_ID}-travel-time-close"],
        ),
        (
            AWNING_SETUP,
            [
                f"{AWNING_ID}-travel-time-open",
                f"{AWNING_ID}-travel-time-close",
                f"{AWNING_ID}-valance-travel-time-open",
                f"{AWNING_ID}-valance-travel-time-close",
            ],
        ),
        (
            SLAT_SETUP,
            [f"{SLAT_ID}-travel-time-open", f"{SLAT_ID}-travel-time-close"],
        ),
    ],
    indirect=["gateway"],
)
@pytest.mark.usefixtures("gateway")
async def test_every_cover_drive_has_travel_time_numbers(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, unique_ids: list[str]
) -> None:
    """Awning, valance, roller shutter and blind each get their own travel times."""
    assert await setup_config_entry(hass, mock_config_entry)

    registry = er.async_get(hass)

    for unique_id in unique_ids:
        assert registry.async_get_entity_id(
            NUMBER_DOMAIN, "wms_webcontrol_pro", unique_id
        )


@pytest.mark.parametrize("gateway", [AWNING_SETUP], indirect=True)
@pytest.mark.usefixtures("gateway")
async def test_travel_time_of_the_valance_is_stored_on_its_own_action(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Setting the valance time does not change the awning time."""
    assert await setup_config_entry(hass, mock_config_entry)
    entity_id = _entity_id(hass, NUMBER_DOMAIN, f"{AWNING_ID}-valance-travel-time-open")

    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: entity_id, ATTR_VALUE: 12.5},
        blocking=True,
    )

    dest = mock_config_entry.runtime_data.hub.dests[AWNING_ID]
    valance = dest.action(ACTION_DESC.ValanceDrive)
    awning = dest.action(ACTION_DESC.AwningDrive)
    assert valance.settings.travel_time(TravelDirection.OPEN) == 12.5
    assert awning.settings.travel_time(TravelDirection.OPEN) == 0
    assert float(hass.states.get(entity_id).state) == 12.5


@pytest.mark.parametrize("gateway", [SLAT_SETUP], indirect=True)
async def test_slat_range_numbers_default_and_reset(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, gateway: FakeGateway
) -> None:
    """The numbers show the limits that the library uses, the button resets them."""
    assert await setup_config_entry(hass, mock_config_entry)
    minimum = _entity_id(hass, NUMBER_DOMAIN, f"{SLAT_ID}-rotation-min")
    maximum = _entity_id(hass, NUMBER_DOMAIN, f"{SLAT_ID}-rotation-max")
    reset = _entity_id(hass, BUTTON_DOMAIN, f"{SLAT_ID}-rotation-reset")
    action = mock_config_entry.runtime_data.hub.dests[SLAT_ID].action(
        ACTION_DESC.SlatRotate
    )
    assert float(hass.states.get(minimum).state) == -75
    assert float(hass.states.get(maximum).state) == 75
    assert action.rotation_range == (-75, 75)

    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: minimum, ATTR_VALUE: -60},
        blocking=True,
    )
    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: maximum, ATTR_VALUE: 80},
        blocking=True,
    )
    assert float(hass.states.get(minimum).state) == -60
    assert float(hass.states.get(maximum).state) == 80
    assert action.rotation_range == (-60, 80)

    await hass.services.async_call(
        BUTTON_DOMAIN, SERVICE_PRESS, {ATTR_ENTITY_ID: reset}, blocking=True
    )
    assert float(hass.states.get(minimum).state) == -75
    assert float(hass.states.get(maximum).state) == 75
    assert action.rotation_range == (-75, 75)


@pytest.mark.parametrize("gateway", [SLAT_SETUP], indirect=True)
async def test_rotation_raw_is_disabled_by_default(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, gateway: FakeGateway
) -> None:
    """The raw rotation is a diagnostic value that has to be enabled."""
    assert await setup_config_entry(hass, mock_config_entry)

    entry = er.async_get(hass).async_get(
        _entity_id(hass, NUMBER_DOMAIN, f"{SLAT_ID}-rotation-raw")
    )

    assert entry is not None
    assert entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION


@pytest.mark.parametrize("gateway", [SLAT_SETUP], indirect=True)
async def test_rotation_raw_sends_the_rotation_and_requests_the_state(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, gateway: FakeGateway
) -> None:
    """The raw rotation is a command of the hub, the result is checked after."""
    mock_config_entry.add_to_hass(hass)
    er.async_get(hass).async_get_or_create(
        NUMBER_DOMAIN,
        "wms_webcontrol_pro",
        f"{SLAT_ID}-rotation-raw",
        config_entry=mock_config_entry,
    )
    assert await setup_config_entry(hass, mock_config_entry)
    raw = _entity_id(hass, NUMBER_DOMAIN, f"{SLAT_ID}-rotation-raw")
    gateway.commands.clear()

    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: raw, ATTR_VALUE: 20},
        blocking=True,
    )
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=10))
    await hass.async_block_till_done(wait_background_tasks=True)

    actions = [c for c in gateway.commands if c["command"] == "action"]
    parameters: list[dict[str, Any]] = [a["parameters"] for a in actions[0]["actions"]]
    assert parameters == [{"rotation": 20}]
    assert [c["destinations"] for c in gateway.commands_named("getStatus")] == [
        [SLAT_ID]
    ]


@pytest.mark.parametrize("gateway", [SLAT_SETUP], indirect=True)
async def test_measured_rotation_beyond_the_range_widens_it(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, gateway: FakeGateway
) -> None:
    """A rotation outside the stored range is learned as new limit."""
    assert await setup_config_entry(hass, mock_config_entry)
    maximum = _entity_id(hass, NUMBER_DOMAIN, f"{SLAT_ID}-rotation-max")
    gateway.queue_status(
        SLAT_ID,
        {
            "details": [
                {
                    "destinationId": SLAT_ID,
                    "data": {
                        "productData": [
                            {"actionId": 6, "value": {"rotation": 100}},
                        ]
                    },
                }
            ]
        },
    )

    await mock_config_entry.runtime_data.coordinator.async_refresh()
    await hass.async_block_till_done()

    assert float(hass.states.get(maximum).state) == 100


@pytest.mark.parametrize("gateway", [SLAT_SETUP], indirect=True)
async def test_identify_button_sends_the_identify_action(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, gateway: FakeGateway
) -> None:
    """The identify button triggers the identify action of the destination."""
    assert await setup_config_entry(hass, mock_config_entry)
    identify = _entity_id(hass, BUTTON_DOMAIN, str(SLAT_ID))
    gateway.commands.clear()

    await hass.services.async_call(
        BUTTON_DOMAIN, SERVICE_PRESS, {ATTR_ENTITY_ID: identify}, blocking=True
    )

    (command,) = [c for c in gateway.commands if c["command"] == "action"]
    assert command["actions"][0]["destinationId"] == SLAT_ID
