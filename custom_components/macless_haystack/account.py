"""Apple account support for the Macless Haystack integration."""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any

from findmy import AsyncAppleAccount, LocalAnisetteProvider

from homeassistant.core import HomeAssistant

from .const import ANISETTE_LIBS_FILE, ANISETTE_STORAGE_DIR

_LOGGER = logging.getLogger(__name__)

HEADER_CACHE_SECONDS = 30


class CachedLocalAnisetteProvider(LocalAnisetteProvider):
    """Local anisette provider with a short header cache.

    One poll asks for the reports of every key of an accessory. A fresh
    header set for each key costs one emulated one-time password each time.
    """

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._header_cache: dict[str, tuple[float, dict[str, str]]] = {}

    async def get_headers(
        self,
        user_id: str,
        device_id: str,
        serial: str = "0",
        with_client_info: bool = False,
    ) -> dict[str, str]:
        """Return anisette headers, cached for a short time."""
        cache_key = f"{user_id}:{device_id}:{serial}:{with_client_info}"
        cached = self._header_cache.get(cache_key)
        now = time.monotonic()
        if cached is not None and now < cached[0]:
            return dict(cached[1])

        headers = await super().get_headers(
            user_id, device_id, serial, with_client_info
        )
        self._header_cache[cache_key] = (now + HEADER_CACHE_SECONDS, headers)
        return dict(headers)


def anisette_libs_path(hass: HomeAssistant) -> Path:
    """Return the path of the cached anisette library bundle."""
    return (
        Path(hass.config.config_dir) / ".storage" / ANISETTE_STORAGE_DIR / ANISETTE_LIBS_FILE
    )


def create_account(hass: HomeAssistant) -> AsyncAppleAccount:
    """Create a new account that uses the local anisette engine."""
    libs_path = anisette_libs_path(hass)
    libs_path.parent.mkdir(parents=True, exist_ok=True)
    _LOGGER.debug("Using the anisette libraries at %s", libs_path)
    return AsyncAppleAccount(CachedLocalAnisetteProvider(libs_path=libs_path))


def restore_account(hass: HomeAssistant, state: dict[str, Any]) -> AsyncAppleAccount:
    """Restore a saved account session."""
    return AsyncAppleAccount.from_json(
        state, anisette_libs_path=anisette_libs_path(hass)
    )


def account_state(account: AsyncAppleAccount) -> str:
    """Return the session state with the password removed."""
    state = account.to_json()
    if state.get("account"):
        state["account"]["password"] = None
    return json.dumps(state)
