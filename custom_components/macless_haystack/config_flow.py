"""Config flow for the Macless Haystack integration."""

from __future__ import annotations

import base64
import json
from typing import Any

import aiohttp
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .const import (
    CONF_ACCESSORIES,
    CONF_AUTH_PASS,
    CONF_AUTH_USER,
    CONF_DAYS,
    CONF_ENDPOINT,
    CONF_SCAN_INTERVAL,
    DEFAULT_DAYS,
    DEFAULT_ENDPOINT,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MAX_DAYS,
    MAX_SCAN_INTERVAL,
    MIN_DAYS,
    MIN_SCAN_INTERVAL,
)
from .crypto import KEY_SIZE, accessory_unique_id


def _parse_accessories(raw: str) -> list[dict[str, Any]]:
    """Read one or more accessories from the portal JSON."""
    data = json.loads(raw)
    if isinstance(data, dict):
        data = [data]
    if not isinstance(data, list) or not data:
        raise ValueError("No accessory found")

    accessories = []
    for item in data:
        if not isinstance(item, dict) or not isinstance(item.get("privateKey"), str):
            raise ValueError("Missing private key")
        additional = item.get("additionalKeys") or []
        if not isinstance(additional, list):
            raise ValueError("Bad additional keys")
        for key in [item["privateKey"], *additional]:
            if len(base64.b64decode(key, validate=True)) != KEY_SIZE:
                raise ValueError("Bad key length")
        accessories.append(
            {
                "name": item.get("name") or "FindMy device",
                "privateKey": item["privateKey"],
                "additionalKeys": additional,
            }
        )
    return accessories


class MaclessHaystackConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the config flow."""

    VERSION = 1

    def __init__(self) -> None:
        self._endpoint = DEFAULT_ENDPOINT
        self._auth_user: str | None = None
        self._auth_pass: str | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for the endpoint."""
        errors: dict[str, str] = {}
        if user_input is not None:
            self._endpoint = user_input[CONF_ENDPOINT].rstrip("/")
            self._auth_user = user_input.get(CONF_AUTH_USER) or None
            self._auth_pass = user_input.get(CONF_AUTH_PASS) or None
            errors = await self._async_check_endpoint()
            if not errors:
                return await self.async_step_accessory()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_ENDPOINT, default=self._endpoint): TextSelector(
                        TextSelectorConfig(type=TextSelectorType.URL)
                    ),
                    vol.Optional(CONF_AUTH_USER, default=""): TextSelector(),
                    vol.Optional(CONF_AUTH_PASS, default=""): TextSelector(
                        TextSelectorConfig(type=TextSelectorType.PASSWORD)
                    ),
                }
            ),
            errors=errors,
        )

    async def async_step_accessory(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for the accessory JSON."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                accessories = _parse_accessories(user_input[CONF_ACCESSORIES])
            except (ValueError, json.JSONDecodeError):
                errors["base"] = "invalid_accessory"
            else:
                unique_id = accessory_unique_id(accessories[0])
                await self.async_set_unique_id(unique_id)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=accessories[0]["name"],
                    data={
                        CONF_ENDPOINT: self._endpoint,
                        CONF_AUTH_USER: self._auth_user or "",
                        CONF_AUTH_PASS: self._auth_pass or "",
                        CONF_ACCESSORIES: json.dumps(accessories),
                    },
                )

        return self.async_show_form(
            step_id="accessory",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_ACCESSORIES): TextSelector(
                        TextSelectorConfig(
                            type=TextSelectorType.TEXT,
                            multiline=True,
                        )
                    )
                }
            ),
            errors=errors,
        )

    async def _async_check_endpoint(self) -> dict[str, str]:
        """Return an error key when the endpoint does not answer."""
        session = async_get_clientsession(self.hass)
        auth = (
            aiohttp.BasicAuth(self._auth_user, self._auth_pass or "")
            if self._auth_user
            else None
        )
        try:
            async with session.get(
                self._endpoint,
                auth=auth,
                timeout=aiohttp.ClientTimeout(total=10),
            ) as response:
                if response.status == 401:
                    return {"base": "invalid_auth"}
                if response.status >= 400:
                    return {"base": "cannot_connect"}
        except (aiohttp.ClientError, TimeoutError):
            return {"base": "cannot_connect"}
        return {}

    @staticmethod
    def async_get_options_flow(config_entry) -> OptionsFlow:
        """Return the options flow."""
        return MaclessHaystackOptionsFlow()


class MaclessHaystackOptionsFlow(OptionsFlow):
    """Handle the options."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the poll interval and the report window."""
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        options = self.config_entry.options
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_SCAN_INTERVAL,
                        default=options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
                    ): NumberSelector(
                        NumberSelectorConfig(
                            min=MIN_SCAN_INTERVAL,
                            max=MAX_SCAN_INTERVAL,
                            step=30,
                            unit_of_measurement="s",
                            mode=NumberSelectorMode.BOX,
                        )
                    ),
                    vol.Optional(
                        CONF_DAYS,
                        default=options.get(CONF_DAYS, DEFAULT_DAYS),
                    ): NumberSelector(
                        NumberSelectorConfig(
                            min=MIN_DAYS,
                            max=MAX_DAYS,
                            step=1,
                            mode=NumberSelectorMode.BOX,
                        )
                    ),
                }
            ),
        )
