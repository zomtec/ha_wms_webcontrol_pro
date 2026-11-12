"""Tests for the diagnostics of the WMS WebControl pro integration."""

import pytest
from homeassistant.components.diagnostics import REDACTED
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.wms_webcontrol_pro.diagnostics import (
    async_get_config_entry_diagnostics,
)

from .conftest import FakeGateway
from .helpers import setup_config_entry


@pytest.mark.parametrize(
    "gateway",
    [("config_prod_roller_shutter.json", "status_prod_roller_shutter.json")],
    indirect=True,
)
async def test_diagnostics(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, gateway: FakeGateway
) -> None:
    """Diagnostics contain the hub data, the counters and no host."""
    assert await setup_config_entry(hass, mock_config_entry)

    diagnostics = await async_get_config_entry_diagnostics(hass, mock_config_entry)

    assert diagnostics["host"] == REDACTED
    dest = diagnostics["dests"][18894]
    assert dest["stats"]["ok"] == 1
    assert dest["status"]["details"][0]["destinationId"] == 18894
