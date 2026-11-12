"""Tests for the config flow of the WMS WebControl pro integration."""

import aiohttp
import pytest
from homeassistant.config_entries import (
    SOURCE_DHCP,
    SOURCE_IGNORE,
    SOURCE_USER,
    ConfigEntryState,
)
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import (
    AiohttpClientMocker,
)

from custom_components.wms_webcontrol_pro.const import DOMAIN

from .conftest import COMMAND_URL, HOST, FakeGateway, load_fixture_object
from .helpers import setup_config_entry

NEW_HOST = "1.2.3.4"
MAC = "001122334455"
UNIQUE_ID = "00:11:22:33:44:55"


def dhcp_info(ip: str = NEW_HOST) -> DhcpServiceInfo:
    """Return the discovery data of a hub."""
    return DhcpServiceInfo(ip=ip, hostname="webcontrol", macaddress=MAC)


async def test_user_step_creates_an_entry(
    hass: HomeAssistant, gateway: FakeGateway
) -> None:
    """A reachable hub creates a config entry that is set up."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: NEW_HOST}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == NEW_HOST
    assert result["data"] == {CONF_HOST: NEW_HOST}
    assert result["result"].state is ConfigEntryState.LOADED


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (aiohttp.ClientError, "cannot_connect"),
        (TimeoutError, "cannot_connect"),
        (RuntimeError, "unknown"),
    ],
)
async def test_user_step_shows_an_error_and_recovers(
    hass: HomeAssistant,
    gateway: FakeGateway,
    aioclient_mock: AiohttpClientMocker,
    error: type[Exception],
    expected: str,
) -> None:
    """An error is shown on the form and a new attempt can succeed."""
    aioclient_mock.clear_requests()
    aioclient_mock.post(COMMAND_URL, exc=error)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: NEW_HOST}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": expected}

    aioclient_mock.clear_requests()
    aioclient_mock.post(COMMAND_URL, side_effect=gateway.handle)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: NEW_HOST}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_user_step_rejects_a_hub_that_does_not_answer_the_ping(
    hass: HomeAssistant, gateway: FakeGateway
) -> None:
    """A hub that reports an error for the ping is not usable."""
    gateway.ping_status = 1
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: NEW_HOST}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_user_step_aborts_for_a_configured_host(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, gateway: FakeGateway
) -> None:
    """The same host cannot be configured twice."""
    mock_config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: HOST}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_user_step_aborts_for_a_hub_that_is_already_set_up(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, gateway: FakeGateway
) -> None:
    """A hub with the same rooms under another host is the same hub."""
    assert await setup_config_entry(hass, mock_config_entry)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: NEW_HOST}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_dhcp_discovery_suggests_the_address(
    hass: HomeAssistant, gateway: FakeGateway
) -> None:
    """A discovered hub creates an entry with its MAC address as unique id."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_DHCP}, data=dhcp_info()
    )
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: NEW_HOST}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == UNIQUE_ID


async def test_dhcp_discovery_adds_the_mac_to_an_entry_without_unique_id(
    hass: HomeAssistant, gateway: FakeGateway
) -> None:
    """An entry of the same address gets the MAC address as unique id."""
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_HOST: NEW_HOST})
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_DHCP}, data=dhcp_info()
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert entry.unique_id == UNIQUE_ID


async def test_dhcp_discovery_updates_the_ip_of_an_entry(
    hass: HomeAssistant, gateway: FakeGateway
) -> None:
    """A known hub with an address as host gets the new address."""
    entry = MockConfigEntry(
        domain=DOMAIN, unique_id=UNIQUE_ID, data={CONF_HOST: "192.0.2.5"}
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_DHCP}, data=dhcp_info()
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert entry.data[CONF_HOST] == NEW_HOST


@pytest.mark.parametrize(
    ("source", "host"),
    [(SOURCE_USER, HOST), (SOURCE_IGNORE, NEW_HOST)],
)
async def test_dhcp_discovery_keeps_name_based_and_ignored_entries(
    hass: HomeAssistant, gateway: FakeGateway, source: str, host: str
) -> None:
    """A host name and an ignored hub are not changed by the discovery."""
    entry = MockConfigEntry(
        domain=DOMAIN, unique_id=UNIQUE_ID, source=source, data={CONF_HOST: host}
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_DHCP}, data=dhcp_info("192.0.2.77")
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert entry.data[CONF_HOST] == host


async def test_reconfigure_changes_the_host(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, gateway: FakeGateway
) -> None:
    """A new host of the same hub is stored and the entry is reloaded."""
    assert await setup_config_entry(hass, mock_config_entry)

    result = await mock_config_entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: NEW_HOST}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_config_entry.data[CONF_HOST] == NEW_HOST
    assert mock_config_entry.state is ConfigEntryState.LOADED


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (aiohttp.ClientError, "cannot_connect"),
        (RuntimeError, "unknown"),
    ],
)
async def test_reconfigure_shows_an_error_and_recovers(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    gateway: FakeGateway,
    aioclient_mock: AiohttpClientMocker,
    error: type[Exception],
    expected: str,
) -> None:
    """An error is shown on the form and a new attempt can succeed."""
    assert await setup_config_entry(hass, mock_config_entry)
    result = await mock_config_entry.start_reconfigure_flow(hass)
    aioclient_mock.clear_requests()
    aioclient_mock.post(COMMAND_URL, exc=error)

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: NEW_HOST}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": expected}

    aioclient_mock.clear_requests()
    aioclient_mock.post(COMMAND_URL, side_effect=gateway.handle)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: NEW_HOST}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"


async def test_reconfigure_rejects_a_hub_that_does_not_answer_the_ping(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, gateway: FakeGateway
) -> None:
    """A hub that reports an error for the ping is not usable."""
    assert await setup_config_entry(hass, mock_config_entry)
    result = await mock_config_entry.start_reconfigure_flow(hass)
    gateway.ping_status = 1

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: NEW_HOST}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_reconfigure_rejects_another_hub(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, gateway: FakeGateway
) -> None:
    """A hub with other rooms is not the hub of the entry."""
    assert await setup_config_entry(hass, mock_config_entry)
    result = await mock_config_entry.start_reconfigure_flow(hass)
    gateway.config = load_fixture_object("config_prod_slat_rotate.json")

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: NEW_HOST}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "wrong_device"}
    assert mock_config_entry.data[CONF_HOST] == HOST


async def test_reconfigure_aborts_for_a_host_of_another_entry(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, gateway: FakeGateway
) -> None:
    """The host of another entry cannot be used."""
    MockConfigEntry(domain=DOMAIN, data={CONF_HOST: NEW_HOST}).add_to_hass(hass)
    mock_config_entry.add_to_hass(hass)
    result = await mock_config_entry.start_reconfigure_flow(hass)

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: NEW_HOST}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
