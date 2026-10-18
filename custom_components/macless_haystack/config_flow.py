"""Config flow for the Macless Haystack integration."""

from __future__ import annotations

import base64
import json
import logging
from typing import Any

import aiohttp
import voluptuous as vol

from findmy import (
    AsyncAppleAccount,
    InvalidCredentialsError,
    LoginState,
    SmsSecondFactorMethod,
    TrustedDeviceSecondFactorMethod,
    UnhandledProtocolError,
)

from homeassistant.config_entries import (
    SOURCE_REAUTH,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_PASSWORD
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .account import account_state, create_account
from .const import (
    CONF_ACCESSORIES,
    CONF_ACCOUNT,
    CONF_APPLE_ID,
    CONF_AUTH_PASS,
    CONF_AUTH_USER,
    CONF_DAYS,
    CONF_ENDPOINT,
    CONF_MODE,
    CONF_SCAN_INTERVAL,
    DEFAULT_DAYS,
    DEFAULT_ENDPOINT,
    DEFAULT_MODE,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MAX_DAYS,
    MAX_SCAN_INTERVAL,
    MIN_DAYS,
    MIN_SCAN_INTERVAL,
    MODE_APPLE,
    MODE_ENDPOINT,
)
from .crypto import KEY_SIZE, accessory_unique_id

_LOGGER = logging.getLogger(__name__)


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

    VERSION = 2

    def __init__(self) -> None:
        self._mode = DEFAULT_MODE
        self._endpoint = DEFAULT_ENDPOINT
        self._auth_user: str | None = None
        self._auth_pass: str | None = None
        self._apple_id = ""
        self._account: AsyncAppleAccount | None = None
        self._methods: list[Any] = []
        self._method: Any = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for the mode of operation."""
        if user_input is not None:
            self._mode = user_input[CONF_MODE]
            if self._mode == MODE_APPLE:
                return await self.async_step_apple()
            return await self.async_step_endpoint()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_MODE, default=DEFAULT_MODE): SelectSelector(
                        SelectSelectorConfig(
                            options=[
                                SelectOptionDict(
                                    value=MODE_APPLE, label="Apple ID (no other server)"
                                ),
                                SelectOptionDict(
                                    value=MODE_ENDPOINT,
                                    label="Existing macless-haystack endpoint",
                                ),
                            ],
                            mode=SelectSelectorMode.LIST,
                        )
                    )
                }
            ),
        )

    async def async_step_endpoint(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for the endpoint of an existing macless-haystack server."""
        errors: dict[str, str] = {}
        if user_input is not None:
            self._endpoint = user_input[CONF_ENDPOINT].rstrip("/")
            self._auth_user = user_input.get(CONF_AUTH_USER) or None
            self._auth_pass = user_input.get(CONF_AUTH_PASS) or None
            errors = await self._async_check_endpoint()
            if not errors:
                return await self.async_step_accessory()

        return self.async_show_form(
            step_id="endpoint",
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

    async def async_step_apple(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for the Apple ID and the password."""
        errors: dict[str, str] = {}
        if user_input is not None:
            errors = await self._async_apple_login(
                user_input[CONF_APPLE_ID], user_input[CONF_PASSWORD]
            )
            if not errors:
                return await self._async_after_login()

        return self.async_show_form(
            step_id="apple",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_APPLE_ID, default=self._apple_id): TextSelector(
                        TextSelectorConfig(type=TextSelectorType.EMAIL)
                    ),
                    vol.Required(CONF_PASSWORD): TextSelector(
                        TextSelectorConfig(type=TextSelectorType.PASSWORD)
                    ),
                }
            ),
            errors=errors,
        )

    async def async_step_two_factor(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask which second factor to use."""
        errors: dict[str, str] = {}
        account = self._account
        if account is None:
            return self.async_abort(reason="login_failed")

        if user_input is not None:
            try:
                self._method = self._methods[int(user_input["method"])]
            except (ValueError, IndexError):
                errors["base"] = "unknown"
            else:
                try:
                    await self._method.request()
                except Exception:  # noqa: BLE001 - show the failure in the form
                    _LOGGER.exception("Could not request the second factor")
                    errors["base"] = "cannot_connect"
                else:
                    return await self.async_step_two_factor_code()

        if not self._methods:
            try:
                self._methods = list(await account.get_2fa_methods())
            except Exception:  # noqa: BLE001 - show the failure in the form
                _LOGGER.exception("Could not get the second factor methods")
                errors["base"] = "cannot_connect"

        options = []
        for index, method in enumerate(self._methods):
            if isinstance(method, TrustedDeviceSecondFactorMethod):
                label = "Trusted device"
            elif isinstance(method, SmsSecondFactorMethod):
                label = f"SMS {method.phone_number}"
            else:
                label = "Second factor"
            options.append(SelectOptionDict(value=str(index), label=label))

        if not options:
            errors["base"] = "no_2fa_methods"

        return self.async_show_form(
            step_id="two_factor",
            data_schema=vol.Schema(
                {
                    vol.Required("method", default="0"): SelectSelector(
                        SelectSelectorConfig(options=options, mode=SelectSelectorMode.LIST)
                    )
                }
            ),
            errors=errors,
        )

    async def async_step_two_factor_code(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for the second factor code."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                state = await self._method.submit(user_input["code"].strip())
            except (InvalidCredentialsError, UnhandledProtocolError):
                errors["base"] = "invalid_2fa"
            except Exception:  # noqa: BLE001 - show the failure in the form
                _LOGGER.exception("Could not submit the second factor code")
                errors["base"] = "cannot_connect"
            else:
                if state == LoginState.LOGGED_IN:
                    return await self._async_after_login()
                errors["base"] = "invalid_2fa"

        return self.async_show_form(
            step_id="two_factor_code",
            data_schema=vol.Schema(
                {
                    vol.Required("code"): TextSelector(
                        TextSelectorConfig(type=TextSelectorType.TEXT)
                    )
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

                data: dict[str, Any] = {
                    CONF_MODE: self._mode,
                    CONF_ACCESSORIES: json.dumps(accessories),
                }
                if self._mode == MODE_APPLE:
                    if self._account is None:
                        return self.async_abort(reason="login_failed")
                    data[CONF_APPLE_ID] = self._apple_id
                    data[CONF_ACCOUNT] = account_state(self._account)
                else:
                    data[CONF_ENDPOINT] = self._endpoint
                    data[CONF_AUTH_USER] = self._auth_user or ""
                    data[CONF_AUTH_PASS] = self._auth_pass or ""

                return self.async_create_entry(
                    title=accessories[0]["name"], data=data
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

    async def async_step_reauth(
        self, entry_data: dict[str, Any]
    ) -> ConfigFlowResult:
        """Start a new Apple ID session for an existing entry."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for the Apple ID and the password again."""
        errors: dict[str, str] = {}
        entry = self._get_reauth_entry()
        if user_input is not None:
            errors = await self._async_apple_login(
                user_input[CONF_APPLE_ID], user_input[CONF_PASSWORD]
            )
            if not errors:
                return await self._async_after_login()

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_APPLE_ID,
                        default=entry.data.get(CONF_APPLE_ID, ""),
                    ): TextSelector(TextSelectorConfig(type=TextSelectorType.EMAIL)),
                    vol.Required(CONF_PASSWORD): TextSelector(
                        TextSelectorConfig(type=TextSelectorType.PASSWORD)
                    ),
                }
            ),
            errors=errors,
        )

    async def _async_apple_login(self, username: str, password: str) -> dict[str, str]:
        """Log in and return the form errors."""
        self._apple_id = username.strip()
        if self._account is None:
            try:
                self._account = await self.hass.async_add_executor_job(
                    create_account, self.hass
                )
            except Exception:  # noqa: BLE001 - show the failure in the form
                _LOGGER.exception("Could not create the Apple account")
                return {"base": "unknown"}
        try:
            await self._account.login(self._apple_id, password)
        except InvalidCredentialsError as err:
            _LOGGER.warning("Apple refused the login: %s", err)
            return {"base": "invalid_auth"}
        except (aiohttp.ClientError, TimeoutError, OSError):
            return {"base": "cannot_connect"}
        except Exception:  # noqa: BLE001 - show the failure in the form
            _LOGGER.exception("Unexpected error during the Apple ID login")
            return {"base": "unknown"}
        return {}

    async def _async_after_login(self) -> ConfigFlowResult:
        """Route the flow after a successful Apple ID login."""
        if self._account is not None and self._account.login_state == LoginState.REQUIRE_2FA:
            return await self.async_step_two_factor()
        if self.source == SOURCE_REAUTH:
            return await self._async_finish_reauth()
        return await self.async_step_accessory()

    async def _async_finish_reauth(self) -> ConfigFlowResult:
        """Save the new session and finish the reauth."""
        entry = self._get_reauth_entry()
        if self._account is not None:
            self.hass.config_entries.async_update_entry(
                entry,
                data={**entry.data, CONF_ACCOUNT: account_state(self._account)},
            )
        return self.async_abort(reason="reauth_successful")

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
