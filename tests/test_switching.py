"""Tests for lights, switches and scenes of the WMS WebControl pro integration."""

from datetime import timedelta

import pytest
from homeassistant.components.light import DOMAIN as LIGHT_DOMAIN
from homeassistant.components.light.const import ATTR_BRIGHTNESS
from homeassistant.components.scene import DOMAIN as SCENE_DOMAIN
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)

from .conftest import FakeGateway
from .helpers import setup_config_entry

LIGHT_ID = 97358
SWITCH_ID = 499120
SCENE_ID = 687471

LIGHT_SETUP = ("config_prod_light_switch.json", "status_prod_light_switch.json")
DIMMER_SETUP = ("config_prod_awning_dimmer.json", "status_prod_dimmer.json")
SWITCH_SETUP = ("config_prod_load_switch.json", "status_prod_load_switch.json")
SCENE_SETUP = ("config_prod_awning_dimmer.json", "status_prod_dimmer.json")


def _entity_id(hass: HomeAssistant, domain: str, unique_id: str) -> str:
    """Return the entity id of an entity by its unique id."""
    entity_id = er.async_get(hass).async_get_entity_id(
        domain, "wms_webcontrol_pro", unique_id
    )
    assert entity_id is not None
    return entity_id


def _actions(gateway: FakeGateway) -> list[dict]:
    """Return the action requests sent to the hub."""
    return [c for c in gateway.commands if c["command"] == "action"]


@pytest.mark.parametrize(
    ("gateway", "domain", "unique_id"),
    [
        (LIGHT_SETUP, LIGHT_DOMAIN, str(LIGHT_ID)),
        (DIMMER_SETUP, LIGHT_DOMAIN, str(LIGHT_ID)),
        (SWITCH_SETUP, SWITCH_DOMAIN, str(SWITCH_ID)),
    ],
    indirect=["gateway"],
)
@pytest.mark.parametrize(
    ("service", "state"), [(SERVICE_TURN_ON, STATE_ON), (SERVICE_TURN_OFF, STATE_OFF)]
)
async def test_turning_shows_the_new_state_and_checks_it_later(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    gateway: FakeGateway,
    domain: str,
    unique_id: str,
    service: str,
    state: str,
) -> None:
    """A switched light or load shows the state at once and is asked afterwards."""
    assert await setup_config_entry(hass, mock_config_entry)
    entity_id = _entity_id(hass, domain, unique_id)
    gateway.commands.clear()

    await hass.services.async_call(
        domain, service, {ATTR_ENTITY_ID: entity_id}, blocking=True
    )
    assert hass.states.get(entity_id).state == state
    assert len(_actions(gateway)) == 1

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=5))
    await hass.async_block_till_done(wait_background_tasks=True)
    assert len(gateway.commands_named("getStatus")) == 1


@pytest.mark.parametrize("gateway", [DIMMER_SETUP], indirect=True)
async def test_dimmer_sends_the_brightness_as_percentage(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, gateway: FakeGateway
) -> None:
    """The brightness is converted to the percentage scale of the hub."""
    assert await setup_config_entry(hass, mock_config_entry)
    entity_id = _entity_id(hass, LIGHT_DOMAIN, str(LIGHT_ID))
    gateway.commands.clear()

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: entity_id, ATTR_BRIGHTNESS: 255},
        blocking=True,
    )

    (command,) = _actions(gateway)
    assert command["actions"][0]["parameters"] == {"percentage": 100}
    state = hass.states.get(entity_id)
    assert state.state == STATE_ON
    assert state.attributes[ATTR_BRIGHTNESS] == 255


@pytest.mark.parametrize("gateway", [SCENE_SETUP], indirect=True)
async def test_scene_activation_sends_the_scene(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, gateway: FakeGateway
) -> None:
    """Activating a scene executes it on the hub."""
    assert await setup_config_entry(hass, mock_config_entry)
    entity_id = _entity_id(hass, SCENE_DOMAIN, str(SCENE_ID))
    gateway.commands.clear()

    await hass.services.async_call(
        SCENE_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: entity_id}, blocking=True
    )

    assert len(gateway.commands_named("sceneActions")) == 1
