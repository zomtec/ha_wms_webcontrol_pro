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
    STATE_UNAVAILABLE,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)

from custom_components.wms_webcontrol_pro.const import SETTLE_SCENE

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


@pytest.mark.parametrize("gateway", [SCENE_SETUP], indirect=True)
async def test_scene_asks_every_destination_afterwards(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, gateway: FakeGateway
) -> None:
    """The hub does not tell what a scene moves, so all destinations are asked."""
    assert await setup_config_entry(hass, mock_config_entry)
    entity_id = _entity_id(hass, SCENE_DOMAIN, str(SCENE_ID))
    gateway.commands.clear()

    await hass.services.async_call(
        SCENE_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: entity_id}, blocking=True
    )
    async_fire_time_changed(
        hass, dt_util.utcnow() + timedelta(seconds=SETTLE_SCENE - 1)
    )
    await hass.async_block_till_done(wait_background_tasks=True)
    assert not gateway.commands_named("getStatus")

    async_fire_time_changed(
        hass, dt_util.utcnow() + timedelta(seconds=SETTLE_SCENE + 1)
    )
    await hass.async_block_till_done(wait_background_tasks=True)
    assert len(gateway.commands_named("getStatus")) == 2


@pytest.mark.parametrize(
    ("gateway", "domain", "unique_id"),
    [
        (LIGHT_SETUP, LIGHT_DOMAIN, str(LIGHT_ID)),
        (SWITCH_SETUP, SWITCH_DOMAIN, str(SWITCH_ID)),
    ],
    indirect=["gateway"],
)
@pytest.mark.parametrize(
    ("answer", "unanswered", "translation_key"),
    [
        ({"errors": [0x50005]}, (), "command_rejected"),
        ({"status": 0}, ("action",), "command_failed"),
    ],
)
async def test_failed_command_is_an_error_and_keeps_the_state(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    gateway: FakeGateway,
    domain: str,
    unique_id: str,
    answer: dict[str, object],
    unanswered: tuple[str, ...],
    translation_key: str,
) -> None:
    """A command that the hub rejects or does not answer is reported."""
    assert await setup_config_entry(hass, mock_config_entry)
    entity_id = _entity_id(hass, domain, unique_id)
    before = hass.states.get(entity_id).state
    gateway.action_response = answer
    gateway.stop_answering(*unanswered)

    with pytest.raises(HomeAssistantError) as error:
        await hass.services.async_call(
            domain, SERVICE_TURN_ON, {ATTR_ENTITY_ID: entity_id}, blocking=True
        )

    assert error.value.translation_key == translation_key
    assert hass.states.get(entity_id).state == before


@pytest.mark.parametrize("gateway", [SCENE_SETUP], indirect=True)
@pytest.mark.parametrize(
    ("answer", "unanswered", "translation_key"),
    [
        ({"errors": [0x50005]}, (), "command_rejected"),
        ({"status": 0}, ("sceneActions",), "command_failed"),
    ],
)
async def test_failed_scene_is_an_error_and_asks_nothing(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    gateway: FakeGateway,
    answer: dict[str, object],
    unanswered: tuple[str, ...],
    translation_key: str,
) -> None:
    """A scene that the hub rejects or does not answer is reported."""
    assert await setup_config_entry(hass, mock_config_entry)
    entity_id = _entity_id(hass, SCENE_DOMAIN, str(SCENE_ID))
    gateway.action_response = answer
    gateway.stop_answering(*unanswered)
    gateway.commands.clear()

    with pytest.raises(HomeAssistantError) as error:
        await hass.services.async_call(
            SCENE_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: entity_id}, blocking=True
        )

    assert error.value.translation_key == translation_key
    async_fire_time_changed(
        hass, dt_util.utcnow() + timedelta(seconds=SETTLE_SCENE + 1)
    )
    await hass.async_block_till_done(wait_background_tasks=True)
    assert not gateway.commands_named("getStatus")


@pytest.mark.parametrize("gateway", [SCENE_SETUP], indirect=True)
async def test_scene_that_disappears_is_removed_after_two_readings(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    gateway: FakeGateway,
    entity_registry: er.EntityRegistry,
) -> None:
    """One reading without the scene removes the entity, the second its entry."""
    assert await setup_config_entry(hass, mock_config_entry)
    entity_id = _entity_id(hass, SCENE_DOMAIN, str(SCENE_ID))
    coordinator = mock_config_entry.runtime_data.coordinator
    gateway.config = {
        **gateway.config,
        "scenes": [s for s in gateway.config["scenes"] if s["id"] != SCENE_ID],
    }

    await coordinator.async_refresh()
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == STATE_UNAVAILABLE
    assert entity_registry.async_get(entity_id)

    await coordinator.async_refresh()
    await hass.async_block_till_done()
    assert entity_registry.async_get(entity_id) is None
    assert hass.states.get(entity_id) is None
