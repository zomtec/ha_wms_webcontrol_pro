"""Tests for the setup of the WMS WebControl pro integration."""

from pathlib import Path

import aiohttp
import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.storage import STORAGE_DIR
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import (
    AiohttpClientMocker,
)

from custom_components.wms_webcontrol_pro.const import DOMAIN

from .conftest import HOST, FakeGateway
from .helpers import remove_config_entry, setup_config_entry, unload_config_entry


@pytest.mark.parametrize("error", [aiohttp.ClientError, TimeoutError])
async def test_setup_is_retried_if_the_hub_is_unreachable(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
    error: type[Exception],
) -> None:
    """An unreachable hub makes the setup retry later."""
    aioclient_mock.post(f"http://{HOST}/commonCommand", exc=error)

    assert not await setup_config_entry(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    assert len(aioclient_mock.mock_calls) == 1


async def test_setup_is_retried_if_the_status_request_fails(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    gateway: FakeGateway,
) -> None:
    """A failing first status request makes the setup retry later."""
    gateway.stop_answering("getStatus")

    assert not await setup_config_entry(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_is_retried_if_the_ping_reports_an_error(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, gateway: FakeGateway
) -> None:
    """A hub that answers the ping with an error is not ready."""
    gateway.ping_status = 1

    assert not await setup_config_entry(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    assert not gateway.commands_named("getConfiguration")


async def test_setup_requests_every_destination_once(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    gateway: FakeGateway,
) -> None:
    """The setup asks the hub once per destination and never retries."""
    gateway.queue_status(18894, {"errors": [0x50005]})

    assert await setup_config_entry(hass, mock_config_entry)

    assert len(gateway.commands_named("getConfiguration")) == 1
    assert len(gateway.commands_named("getStatus")) == 6


async def test_hub_device(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    gateway: FakeGateway,
    device_registry: dr.DeviceRegistry,
) -> None:
    """The hub is registered as a device."""
    assert await setup_config_entry(hass, mock_config_entry)

    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, mock_config_entry.entry_id), mock_config_entry.entry_id
    )

    assert device is not None
    assert device.name == "WebControl"
    assert device.manufacturer == "WAREMA Renkhoff SE"
    assert device.model == "WMS WebControl pro"
    assert device.configuration_url == f"http://{HOST}/system"


async def test_stored_data_directory_is_removed_with_the_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    gateway: FakeGateway,
) -> None:
    """The directory of the entry is kept on unload and removed with the entry."""
    directory = Path(
        hass.config.path(STORAGE_DIR, f"{DOMAIN}-{mock_config_entry.entry_id}")
    )
    await hass.async_add_executor_job(
        lambda: (directory.mkdir(parents=True), (directory / "1.json").write_text("{}"))
    )

    assert await setup_config_entry(hass, mock_config_entry)
    assert await unload_config_entry(hass, mock_config_entry)
    assert await hass.async_add_executor_job(directory.is_dir)

    assert await remove_config_entry(hass, mock_config_entry)

    assert not await hass.async_add_executor_job(directory.exists)
