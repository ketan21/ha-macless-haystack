"""Apple account coordinator for the Macless Haystack integration."""

from __future__ import annotations

import json
import logging
import time
from typing import Any

from findmy import (
    AsyncAppleAccount,
    InvalidCredentialsError,
    InvalidStateError,
    KeyPair,
    LoginState,
    UnauthorizedError,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed

from .account import restore_account
from .const import CONF_ACCOUNT, CONF_DAYS, DEFAULT_DAYS
from .coordinator import AccessoryState, BaseMaclessHaystackCoordinator

_LOGGER = logging.getLogger(__name__)

AUTH_ERRORS = (
    UnauthorizedError,
    InvalidCredentialsError,
    InvalidStateError,
    ValueError,
)


class AppleAccountCoordinator(BaseMaclessHaystackCoordinator):
    """Fetch the reports from Apple with the saved account session."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(hass, entry)
        self._account: AsyncAppleAccount | None = None
        self._days = entry.options.get(CONF_DAYS, DEFAULT_DAYS)

        self._keys: dict[str, KeyPair] = {}
        for accessory in self.accessories:
            for key_b64 in [
                accessory["privateKey"],
                *accessory.get("additionalKeys", []),
            ]:
                key = KeyPair.from_b64(key_b64)
                self._keys[key.hashed_adv_key_b64] = key

    async def _async_update_data(self) -> dict[str, AccessoryState]:
        account = await self._async_account()
        if account.login_state != LoginState.LOGGED_IN:
            raise ConfigEntryAuthFailed("The Apple ID session expired")

        reports = await self._async_fetch_reports(account)
        return self._merge_reports(reports)

    async def _async_account(self) -> AsyncAppleAccount:
        """Restore the saved account session one time."""
        if self._account is None:
            state = json.loads(self.config_entry.data[CONF_ACCOUNT])
            self._account = await self.hass.async_add_executor_job(
                restore_account, self.hass, state
            )
        return self._account

    async def _async_fetch_reports(
        self, account: AsyncAppleAccount
    ) -> list[dict[str, Any]]:
        """Fetch the reports of each key of the accessory.

        Apple caps the number of reports that one request can return. One
        request for each key keeps the newest points, as macless-haystack
        issue 194 shows.
        """
        start = time.time() - self._days * 86400
        reports: list[dict[str, Any]] = []
        failures = 0

        for key_id, key in self._keys.items():
            try:
                key_reports = await account.fetch_location_history(key)
            except AUTH_ERRORS as err:
                raise ConfigEntryAuthFailed(str(err)) from err
            except Exception as err:  # noqa: BLE001 - one key must not stop the poll
                failures += 1
                _LOGGER.warning("Could not fetch the reports of one key: %s", err)
                continue

            for report in key_reports:
                if report.timestamp.timestamp() < start:
                    continue
                status = report.status
                reports.append(
                    {
                        "hashed_key": key_id,
                        "timestamp": int(report.timestamp.timestamp()),
                        "latitude": report.latitude,
                        "longitude": report.longitude,
                        "accuracy": report.horizontal_accuracy,
                        "status": status,
                        "battery": (status >> 6) & 0x03,
                        "confidence": report.confidence,
                    }
                )

        if failures and failures == len(self._keys) and self.data:
            _LOGGER.warning("Could not fetch any reports, keeping the last position")
        return reports
