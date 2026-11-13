"""Shared test fixtures for the WMS WebControl pro integration."""

import json
import re
from collections.abc import Generator
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
from homeassistant.const import CONF_HOST
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import (
    AiohttpClientMocker,
    AiohttpClientMockResponse,
)

from custom_components.wms_webcontrol_pro.const import DOMAIN

FIXTURES = Path(__file__).parent / "fixtures"
HOST = "webcontrol"
# The hub is reachable under any host name in the tests.
COMMAND_URL = re.compile(r"^http://[^/]+/commonCommand$")
ENTRY_ID = "01JWMSPRO00000000000000000"
# Answer for a destination without a status fixture: the hub knows nothing.
NO_STATUS: dict[str, Any] = {"details": []}


class FakeGateway:
    """Answer the requests of the library like a WMS WebControl pro hub."""

    def __init__(
        self, config: dict[str, Any], statuses: dict[int, list[dict[str, Any]]]
    ) -> None:
        """Create a gateway with a configuration and queued status answers."""
        self.config = config
        self.statuses = statuses
        self.commands: list[dict[str, Any]] = []
        self.action_response: dict[str, Any] = {"status": 0}
        self.ping_status = 0
        self.unanswered: set[str] = set()

    def stop_answering(self, *commands: str) -> None:
        """Let the requests of the given commands time out, none answers again."""
        self.unanswered = set(commands)

    def queue_status(self, dest_id: int, *answers: dict[str, Any]) -> None:
        """Queue status answers for a destination, the last one is repeated."""
        self.statuses[dest_id] = list(answers)

    def commands_named(self, command: str) -> list[dict[str, Any]]:
        """Return the requests of one command."""
        return [c for c in self.commands if c["command"] == command]

    async def handle(
        self, method: str, url: object, data: dict[str, Any]
    ) -> AiohttpClientMockResponse:
        """Answer one request."""
        self.commands.append(data)
        command = data["command"]
        if command in self.unanswered:
            raise TimeoutError
        if command == "ping":
            body: dict[str, Any] = {"status": self.ping_status}
        elif command == "getConfiguration":
            body = self.config
        elif command == "getStatus":
            answers = self.statuses.get(data["destinations"][0], [NO_STATUS])
            body = answers.pop(0) if len(answers) > 1 else answers[0]
        else:
            body = self.action_response
        return AiohttpClientMockResponse(method, url, json=body)


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Load the integration from custom_components in every test."""


@pytest.fixture(autouse=True)
def no_request_spacing(monkeypatch: pytest.MonkeyPatch) -> None:
    """Do not wait between status requests in tests."""
    monkeypatch.setattr(
        "custom_components.wms_webcontrol_pro.STATUS_REQUEST_SPACING", 0
    )


@pytest.fixture
def entity_registry_enabled_by_default() -> Generator[None]:
    """Enable the entities that are disabled by default."""
    with patch(
        "homeassistant.helpers.entity.Entity.entity_registry_enabled_default",
        return_value=True,
    ):
        yield


@pytest.fixture
def hass_config_dir(hass_tmp_config_dir: str) -> str:
    """Use a temporary config directory for the stored data."""
    return hass_tmp_config_dir


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a config entry of a hub."""
    return MockConfigEntry(
        title="WebControl",
        entry_id=ENTRY_ID,
        domain=DOMAIN,
        data={CONF_HOST: HOST},
    )


def load_fixture_object(name: str) -> dict[str, Any]:
    """Return the content of a JSON fixture file."""
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


@pytest.fixture
def gateway(
    request: pytest.FixtureRequest,
    aioclient_mock: AiohttpClientMocker,
) -> FakeGateway:
    """Return a fake hub, parametrize with (configuration, *status fixtures)."""
    config_file, *status_files = getattr(
        request, "param", ("config_prod_roller_shutter.json",)
    )
    config = load_fixture_object(config_file)
    statuses: dict[int, list[dict[str, Any]]] = {}
    for status_file in status_files:
        status = load_fixture_object(status_file)
        statuses[status["details"][0]["destinationId"]] = [status]
    fake = FakeGateway(config, statuses)
    aioclient_mock.post(COMMAND_URL, side_effect=fake.handle)
    return fake
