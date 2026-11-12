"""Status polling of one WMS WebControl pro hub."""

import logging
from dataclasses import dataclass

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from pywmswebcontrolpro.exceptions import (
    WebControlProConnectionError,
    WebControlProError,
    WebControlProResponseError,
)
from pywmswebcontrolpro.refresh import RefreshOutcome
from pywmswebcontrolpro.webcontrol import WebControlPro

from .const import BASE_POLL_INTERVAL, DOMAIN, RETRY_AFTER_FAILURE

_LOGGER = logging.getLogger(__name__)

type WebControlProConfigEntry = ConfigEntry[WebControlProData]


@dataclass
class WebControlProData:
    """Runtime data of a config entry."""

    hub: WebControlPro
    coordinator: WebControlProCoordinator


def room_identifier(room_id: int) -> str:
    """Return the device identifier of a room, it cannot match a destination."""
    return f"room-{room_id}"


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
        self.configuration_reads = 0
        self._pending: dict[tuple[int, str], CALLBACK_TYPE] = {}
        self._absent_devices: set[str] = set()
        self._configuration_warned = False

    def _update_failed(self) -> UpdateFailed:
        """Return the error for a hub that does not answer."""
        return UpdateFailed(
            translation_domain=DOMAIN,
            translation_key="cannot_connect",
            translation_placeholders={"host": self.hub.host},
            retry_after=RETRY_AFTER_FAILURE,
        )

    async def _async_setup(self) -> None:
        """Load the configuration of the hub."""
        try:
            await self.hub.refresh()
        except WebControlProError as err:
            raise self._update_failed() from err
        self._async_configuration_read()

    async def _async_read_configuration(self) -> None:
        """Read the configuration of the hub again, keep the known one on failure.

        A single request that fails must not make every entity unavailable
        until the next regular request. That only happens when the hub does
        not answer a ping either.
        """
        try:
            changes = await self.hub.refresh()
        except WebControlProResponseError as err:
            self._async_warn_configuration(err)
            return
        except WebControlProConnectionError as err:
            if not await self._async_hub_answers():
                raise self._update_failed() from err
            self._async_warn_configuration(err)
            return
        self._configuration_warned = False
        for dest_id in changes.removed:
            self.async_cancel_refresh(dest_id)
        self._async_rename_devices(changes.renamed)
        self._async_configuration_read()

    async def _async_hub_answers(self) -> bool:
        """Return True if the hub answers a ping."""
        try:
            await self.hub.ping()
        except WebControlProError:
            return False
        return True

    @callback
    def _async_warn_configuration(self, err: Exception) -> None:
        """Log once that the known configuration stays in use."""
        if self._configuration_warned:
            return
        self._configuration_warned = True
        _LOGGER.warning(
            "Could not read the configuration of %s, keeping the known one: %s",
            self.hub.host,
            err,
        )

    @callback
    def _async_rename_devices(self, dest_ids: frozenset[int]) -> None:
        """Take over the names of destinations that were renamed on the hub.

        Only the default name of the device changes. A name given in Home
        Assistant and the entity ids stay as they are.
        """
        registry = dr.async_get(self.hass)
        for dest_id in dest_ids:
            device = registry.async_get_device_by_identifier(
                (DOMAIN, str(dest_id)), self.config_entry.entry_id
            )
            if device is not None:
                registry.async_update_device(
                    device.id, name=self.hub.dests[dest_id].name
                )

    @callback
    def _async_configuration_read(self) -> None:
        """Count the read and drop the devices that are gone."""
        self.configuration_reads += 1
        self._async_remove_stale_devices()

    def async_valid_identifiers(self) -> set[str]:
        """Return the device identifiers that belong to the hub."""
        return {
            self.config_entry.entry_id,
            *(str(dest_id) for dest_id in self.hub.dests),
            *(room_identifier(room_id) for room_id in self.hub.rooms),
        }

    @callback
    def _async_remove_stale_devices(self) -> None:
        """Remove the devices of destinations and rooms that the hub dropped.

        A device is only removed when two readings of the configuration in a
        row did not contain it. One incomplete answer of the hub would
        otherwise delete devices together with the settings of their entities.
        """
        valid = self.async_valid_identifiers()
        registry = dr.async_get(self.hass)
        absent: set[str] = set()
        for device in dr.async_entries_for_config_entry(
            registry, self.config_entry.entry_id
        ):
            identifiers = {i for domain, i in device.identifiers if domain == DOMAIN}
            if not identifiers or not identifiers.isdisjoint(valid):
                continue
            if device.id in self._absent_devices:
                registry.async_update_device(
                    device.id, remove_config_entry_id=self.config_entry.entry_id
                )
            else:
                absent.add(device.id)
        self._absent_devices = absent

    def _is_travelling(self, dest_id: int) -> bool:
        """Return True while the library calculates a drive of a destination."""
        return any(
            action.model.is_travelling
            for action in self.hub.dests[dest_id].actions.values()
        )

    def _has_pending(self, dest_id: int) -> bool:
        """Return True if a request of the destination is scheduled."""
        return any(pending_id == dest_id for pending_id, _ in self._pending)

    async def _async_update_data(self) -> dict[int, RefreshOutcome]:
        """Request the status of every destination that is not about to be polled."""
        first = self.data is None
        if not first:
            await self._async_read_configuration()
        outcomes = {
            dest_id: outcome
            for dest_id, outcome in (self.data or {}).items()
            if dest_id in self.hub.dests
        }
        for dest_id, dest in self.hub.dests.items():
            if self._has_pending(dest_id) or self._is_travelling(dest_id):
                continue
            try:
                outcomes[dest_id] = await dest.refresh(raise_on_error=first)
            except WebControlProError as err:
                raise self._update_failed() from err
        return outcomes

    @callback
    def async_schedule_refresh(self, dest_id: int, delay: float, key: str = "") -> None:
        """Request the status of one destination once after a delay.

        A pending request with the same key is replaced. Two drives of one
        destination use their own key, so each of them gets its request.
        """
        self.async_cancel_refresh(dest_id, key)

        @callback
        def _fire(_now: object) -> None:
            self._pending.pop((dest_id, key), None)
            self.config_entry.async_create_background_task(
                self.hass,
                self.async_refresh_destination(dest_id),
                name=f"{DOMAIN} refresh {dest_id}",
            )

        self._pending[(dest_id, key)] = async_call_later(self.hass, delay, _fire)

    @callback
    def async_schedule_refresh_all(self, delay: float, key: str) -> None:
        """Request the status of every destination once after a delay."""
        for dest_id in self.hub.dests:
            self.async_schedule_refresh(dest_id, delay, key)

    @callback
    def async_cancel_refresh(self, dest_id: int, key: str | None = None) -> None:
        """Cancel the pending requests of a destination, all without a key."""
        for pending in [
            pending
            for pending in self._pending
            if pending[0] == dest_id and key in (None, pending[1])
        ]:
            self._pending.pop(pending)()

    async def async_refresh_destination(self, dest_id: int) -> RefreshOutcome | None:
        """Request the status of one destination once and notify the entities.

        The regular interval keeps running, it is not reset by this request.
        """
        if (dest := self.hub.dests.get(dest_id)) is None:
            return None
        outcome: RefreshOutcome = await dest.refresh()
        self.data = {**(self.data or {}), dest_id: outcome}
        self.async_update_listeners()
        return outcome

    @callback
    def async_stop(self) -> None:
        """Cancel all pending requests."""
        for dest_id in {pending_id for pending_id, _ in self._pending}:
            self.async_cancel_refresh(dest_id)
