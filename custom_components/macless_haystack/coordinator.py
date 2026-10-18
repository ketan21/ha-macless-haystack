"""Poll the macless-haystack endpoint and decrypt the reports."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from typing import Any

import aiohttp

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_ACCESSORIES,
    CONF_AUTH_PASS,
    CONF_AUTH_USER,
    CONF_DAYS,
    CONF_ENDPOINT,
    CONF_SCAN_INTERVAL,
    DEFAULT_DAYS,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    REQUEST_TIMEOUT,
)
from .crypto import accessory_keys, accessory_unique_id, decode_reports

_LOGGER = logging.getLogger(__name__)


@dataclass
class AccessoryState:
    """The latest location of one accessory."""

    name: str
    latitude: float | None = None
    longitude: float | None = None
    accuracy: int | None = None
    battery: int | None = None
    status: int | None = None
    confidence: int | None = None
    last_seen: datetime | None = None


class MaclessHaystackCoordinator(DataUpdateCoordinator[dict[str, AccessoryState]]):
    """Poll the local endpoint and merge the reports of all keys."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.endpoint = entry.data[CONF_ENDPOINT].rstrip("/")
        self.accessories: list[dict[str, Any]] = json.loads(entry.data[CONF_ACCESSORIES])

        self._key_map: dict[str, str] = {}
        self._key_to_accessory: dict[str, str] = {}
        for accessory in self.accessories:
            unique_id = accessory_unique_id(accessory)
            for key_id, private_key in accessory_keys(accessory).items():
                self._key_map[key_id] = private_key
                self._key_to_accessory[key_id] = unique_id

        user = entry.data.get(CONF_AUTH_USER)
        password = entry.data.get(CONF_AUTH_PASS)
        self._auth = aiohttp.BasicAuth(user, password) if user else None
        self._days = entry.options.get(CONF_DAYS, DEFAULT_DAYS)

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(
                seconds=entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
            ),
            config_entry=entry,
        )

    async def _async_update_data(self) -> dict[str, AccessoryState]:
        try:
            reports = await self._async_fetch()
        except Exception as err:  # noqa: BLE001 - keep the last position on any error
            if self.data:
                _LOGGER.warning("Could not update reports: %s", err)
                return self.data
            raise UpdateFailed(f"Could not reach {self.endpoint}: {err}") from err

        decoded = await self.hass.async_add_executor_job(
            decode_reports, reports, self._key_map
        )
        return self._build_states(decoded)

    async def _async_fetch(self) -> list[dict[str, Any]]:
        session = async_get_clientsession(self.hass)
        async with session.post(
            self.endpoint,
            json={"ids": list(self._key_map), "days": self._days},
            auth=self._auth,
            timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT),
        ) as response:
            response.raise_for_status()
            body = await response.json(content_type=None)
        results = body.get("results")
        return results if isinstance(results, list) else []

    def _build_states(
        self, reports: list[dict[str, Any]]
    ) -> dict[str, AccessoryState]:
        states: dict[str, AccessoryState] = {}
        for accessory in self.accessories:
            unique_id = accessory_unique_id(accessory)
            old = self.data.get(unique_id) if self.data else None
            states[unique_id] = (
                replace(old) if old is not None else AccessoryState(name=accessory["name"])
            )

        for report in reports:
            unique_id = self._key_to_accessory.get(report["hashed_key"])
            if unique_id is None:
                continue
            state = states[unique_id]
            seen = state.last_seen.timestamp() if state.last_seen else 0
            if report["timestamp"] <= seen:
                continue
            state.latitude = report["latitude"]
            state.longitude = report["longitude"]
            state.accuracy = report["accuracy"]
            state.battery = report["battery"]
            state.status = report["status"]
            state.confidence = report["gateway_confidence"]
            state.last_seen = datetime.fromtimestamp(report["timestamp"], tz=timezone.utc)

        return states
