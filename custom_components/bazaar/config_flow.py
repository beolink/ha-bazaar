"""Set up Bazaar: one entry, with the catalog's address as the only setting."""

from __future__ import annotations

from typing import Any

import aiohttp
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.core import HomeAssistant, callback

from .const import CONF_CATALOG_URL, DEFAULT_CATALOG_URL, DOMAIN
from .coordinator import InvalidCatalog, catalog_url, fetch_catalog, parse_catalog


async def _validate(hass: HomeAssistant, url: str) -> str | None:
    """An error key for the form, or None when the address gives a catalog."""
    try:
        result = await fetch_catalog(hass, url)
        if result is None:
            return "cannot_connect"
        await hass.async_add_executor_job(parse_catalog, result[0])
    except InvalidCatalog:
        return "invalid_catalog"
    except (aiohttp.ClientError, TimeoutError, ValueError):
        return "cannot_connect"
    return None


def _stored(url: str) -> dict[str, str]:
    """Only an address the user chose is kept; the default stays in the code.

    Should the catalog move, a new release then takes every installation that
    kept the default along with it.
    """
    return {} if url == DEFAULT_CATALOG_URL else {CONF_CATALOG_URL: url}


def _schema(default: str) -> vol.Schema:
    return vol.Schema({vol.Required(CONF_CATALOG_URL, default=default): str})


class BazaarConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            url = user_input[CONF_CATALOG_URL].strip()
            if (error := await _validate(self.hass, url)) is None:
                return self.async_create_entry(title="Bazaar", data=_stored(url))
            errors["base"] = error
        default = (user_input or {}).get(CONF_CATALOG_URL, DEFAULT_CATALOG_URL)
        return self.async_show_form(step_id="user", data_schema=_schema(default), errors=errors)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry) -> BazaarOptionsFlow:
        return BazaarOptionsFlow()


class BazaarOptionsFlow(OptionsFlow):
    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        current = catalog_url(self.config_entry)
        if user_input is not None:
            url = user_input[CONF_CATALOG_URL].strip()
            if (error := await _validate(self.hass, url)) is None:
                # The key stays, empty for the default, so it overrides what setup stored.
                return self.async_create_entry(data={CONF_CATALOG_URL: _stored(url).get(CONF_CATALOG_URL, "")})
            errors["base"] = error
            current = url
        return self.async_show_form(step_id="init", data_schema=_schema(current), errors=errors)
