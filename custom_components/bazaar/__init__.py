"""Bazaar: the repositories HACS can install but does not list, in a sidebar panel.

The integration only fetches the catalog and shows it. Adding a repository is
done by the panel over HACS's own websocket API, so HACS installs and updates
it like any other custom repository and Bazaar never touches files itself.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from aiohttp import web
import voluptuous as vol

from homeassistant.components import frontend, panel_custom, websocket_api
from homeassistant.components.http import HomeAssistantView, StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.http import KEY_HASS
from homeassistant.helpers.typing import ConfigType

from .const import (
    CATALOG_API_URL,
    DOMAIN,
    PANEL_COMPONENT,
    PANEL_ICON,
    PANEL_TITLE,
    PANEL_URL_PATH,
    STATIC_URL,
    VERSION,
)
from .coordinator import CatalogCoordinator

type BazaarConfigEntry = ConfigEntry[CatalogCoordinator]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)
FRONTEND_DIR = Path(__file__).parent / "frontend"


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """What can only be registered once per run: the files, the API and the commands."""
    await hass.http.async_register_static_paths(
        [StaticPathConfig(STATIC_URL, str(FRONTEND_DIR), cache_headers=False)]
    )
    hass.http.register_view(CatalogView())
    websocket_api.async_register_command(hass, ws_info)
    websocket_api.async_register_command(hass, ws_refresh)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: BazaarConfigEntry) -> bool:
    coordinator = CatalogCoordinator(hass, entry)
    if cached := await coordinator.async_load_cache():
        # The panel works at once from last run's copy; the fresh one follows.
        coordinator.async_set_updated_data(cached)
        entry.async_create_background_task(hass, coordinator.async_refresh(), "bazaar catalog refresh")
    else:
        await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    # A coordinator schedules its next refresh only while something listens,
    # and Bazaar has no entities to do that.
    entry.async_on_unload(coordinator.async_add_listener(lambda: None))
    entry.async_on_unload(entry.add_update_listener(_async_options_updated))

    await panel_custom.async_register_panel(
        hass,
        frontend_url_path=PANEL_URL_PATH,
        webcomponent_name=PANEL_COMPONENT,
        sidebar_title=PANEL_TITLE,
        sidebar_icon=PANEL_ICON,
        module_url=f"{STATIC_URL}/bazaar-panel.js?v={VERSION}",
        require_admin=True,
        config={},
    )
    return True


async def async_unload_entry(hass: HomeAssistant, entry: BazaarConfigEntry) -> bool:
    frontend.async_remove_panel(hass, PANEL_URL_PATH)
    return True


async def async_remove_entry(hass: HomeAssistant, entry: BazaarConfigEntry) -> None:
    await CatalogCoordinator(hass, entry).async_remove_cache()


async def _async_options_updated(hass: HomeAssistant, entry: BazaarConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


def _coordinator(hass: HomeAssistant) -> CatalogCoordinator | None:
    for entry in hass.config_entries.async_loaded_entries(DOMAIN):
        return entry.runtime_data
    return None


@callback
def _info(hass: HomeAssistant, coordinator: CatalogCoordinator) -> dict[str, Any]:
    catalog = coordinator.data
    error = coordinator.last_exception
    return {
        "source": coordinator.url,
        "generated": catalog.generated if catalog else None,
        "fetched": catalog.fetched.isoformat() if catalog else None,
        "counts": catalog.counts if catalog else {},
        "last_update_success": coordinator.last_update_success,
        "error": str(error) if error and not coordinator.last_update_success else None,
        "hacs": "hacs" in hass.config.components,
        "version": VERSION,
    }


@websocket_api.websocket_command({vol.Required("type"): "bazaar/info"})
@websocket_api.require_admin
@callback
def ws_info(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]) -> None:
    if (coordinator := _coordinator(hass)) is None:
        connection.send_error(msg["id"], "not_loaded", "Bazaar is not set up")
        return
    connection.send_result(msg["id"], _info(hass, coordinator))


@websocket_api.websocket_command({vol.Required("type"): "bazaar/refresh"})
@websocket_api.require_admin
@websocket_api.async_response
async def ws_refresh(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    if (coordinator := _coordinator(hass)) is None:
        connection.send_error(msg["id"], "not_loaded", "Bazaar is not set up")
        return
    await coordinator.async_refresh()
    connection.send_result(msg["id"], _info(hass, coordinator))


class CatalogView(HomeAssistantView):
    """The catalog as fetched, for the panel, to administrators only."""

    url = CATALOG_API_URL
    name = "api:bazaar:catalog"
    requires_auth = True

    async def get(self, request: web.Request) -> web.Response:
        hass = request.app[KEY_HASS]
        if not request["hass_user"].is_admin:
            return web.Response(status=403)
        coordinator = _coordinator(hass)
        if coordinator is None or coordinator.data is None:
            return web.Response(status=503, text="The catalog has not been fetched yet")
        response = web.Response(
            body=coordinator.data.raw,
            content_type="application/json",
            headers={"Cache-Control": "no-store"},
        )
        response.enable_compression()
        return response
