"""Status polling of one WMS WebControl pro hub."""

import logging
from dataclasses import dataclass

import aiohttp
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from pywmswebcontrolpro.refresh import RefreshOutcome
from pywmswebcontrolpro.webcontrol import WebControlPro

from .const import BASE_POLL_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)

type WebControlProConfigEntry = ConfigEntry[WebControlProData]


@dataclass
class WebControlProData:
    """Runtime data of a config entry."""

    hub: WebControlPro
    coordinator: WebControlProCoordinator


class WebControlProCoordinator(DataUpdateCoordinator[dict[int, RefreshOutcome]]):
    """Poll the destinations of a hub rarely and once after each command."""

    config_entry: WebControlProConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: WebControlProConfigEntry,
        hub: WebControlPro,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=BASE_POLL_INTERVAL,
        )
        self.hub = hub
        self._pending: dict[int, CALLBACK_TYPE] = {}

    async def _async_setup(self) -> None:
        """Load the configuration of the hub."""
        await self._async_read_configuration()

    async def _async_read_configuration(self) -> None:
        """Read the configuration of the hub and drop what is gone."""
        try:
            changes = await self.hub.refresh()
        except (aiohttp.ClientError, TimeoutError) as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="cannot_connect",
                translation_placeholders={"host": self.hub.host},
            ) from err
        for dest_id in changes.removed:
            self.async_cancel_refresh(dest_id)
        if self.data:
            self.data = {k: v for k, v in self.data.items() if k in self.hub.dests}
        self.async_remove_stale_devices()

    def async_valid_identifiers(self) -> set[str]:
        """Return the device identifiers that belong to the hub."""
        return {
            self.config_entry.entry_id,
            *(str(dest_id) for dest_id in self.hub.dests),
            *(str(room_id) for room_id in self.hub.rooms),
        }

    @callback
    def async_remove_stale_devices(self) -> None:
        """Remove the devices of destinations and rooms that the hub dropped."""
        valid = self.async_valid_identifiers()
        registry = dr.async_get(self.hass)
        for device in dr.async_entries_for_config_entry(
            registry, self.config_entry.entry_id
        ):
            identifiers = {i for domain, i in device.identifiers if domain == DOMAIN}
            if identifiers and identifiers.isdisjoint(valid):
                registry.async_update_device(
                    device.id, remove_config_entry_id=self.config_entry.entry_id
                )

    def _is_travelling(self, dest_id: int) -> bool:
        """Return True while the library calculates a drive of a destination."""
        return any(
            action.model.is_travelling
            for action in self.hub.dests[dest_id].actions.values()
        )

    async def _async_update_data(self) -> dict[int, RefreshOutcome]:
        """Request the status of every destination that is not about to be polled."""
        first = self.data is None
        if not first:
            await self._async_read_configuration()
        outcomes = dict(self.data or {})
        for dest_id, dest in self.hub.dests.items():
            if dest_id in self._pending or self._is_travelling(dest_id):
                continue
            try:
                outcomes[dest_id] = await dest.refresh(retries=0, raise_on_error=first)
            except (aiohttp.ClientError, TimeoutError) as err:
                raise UpdateFailed(
                    translation_domain=DOMAIN,
                    translation_key="cannot_connect",
                    translation_placeholders={"host": self.hub.host},
                ) from err
        return outcomes

    @callback
    def async_schedule_refresh(self, dest_id: int, delay: float) -> None:
        """Request the status of one destination once after a delay.

        A pending request of the same destination is replaced.
        """
        self.async_cancel_refresh(dest_id)

        @callback
        def _fire(_now: object) -> None:
            self._pending.pop(dest_id, None)
            self.config_entry.async_create_background_task(
                self.hass,
                self.async_refresh_destination(dest_id),
                name=f"{DOMAIN} refresh {dest_id}",
            )

        self._pending[dest_id] = async_call_later(self.hass, delay, _fire)

    @callback
    def async_cancel_refresh(self, dest_id: int) -> None:
        """Cancel the pending request of a destination."""
        if unsub := self._pending.pop(dest_id, None):
            unsub()

    async def async_refresh_destination(self, dest_id: int) -> RefreshOutcome:
        """Request the status of one destination once and notify the entities.

        The regular interval keeps running, it is not reset by this request.
        """
        outcome: RefreshOutcome = await self.hub.dests[dest_id].refresh(retries=0)
        self.data = {**(self.data or {}), dest_id: outcome}
        self.async_update_listeners()
        return outcome

    @callback
    def async_stop(self) -> None:
        """Cancel all pending requests."""
        for dest_id in list(self._pending):
            self.async_cancel_refresh(dest_id)
