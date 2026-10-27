"""A stand-in for HACS with the two websocket commands Bazaar's panel uses.

Only for running Bazaar in a local Home Assistant: it remembers repositories in
memory and shows a page at /hacs/repository/<id> so navigation can be seen.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import voluptuous as vol

from homeassistant.components import panel_custom, websocket_api
from homeassistant.components.http import StaticPathConfig
from homeassistant.core import HomeAssistant

REPOS: list[dict] = []


async def async_setup(hass: HomeAssistant, config) -> bool:
    await hass.http.async_register_static_paths(
        [StaticPathConfig("/hacs_stub/panel.js", str(Path(__file__).parent / "panel.js"), False)]
    )
    await panel_custom.async_register_panel(
        hass, frontend_url_path="hacs", webcomponent_name="hacs-stub-panel",
        sidebar_title="HACS", sidebar_icon="mdi:package-variant", module_url="/hacs_stub/panel.js",
        require_admin=True,
    )
    websocket_api.async_register_command(hass, ws_list)
    websocket_api.async_register_command(hass, ws_add)
    return True


@websocket_api.websocket_command({vol.Required("type"): "hacs/repositories/list", vol.Optional("categories"): [str]})
@websocket_api.require_admin
def ws_list(hass, connection, msg):
    connection.send_result(msg["id"], REPOS)


@websocket_api.websocket_command(
    {vol.Required("type"): "hacs/repositories/add", vol.Required("repository"): str, vol.Required("category"): str}
)
@websocket_api.require_admin
@websocket_api.async_response
async def ws_add(hass, connection, msg):
    await asyncio.sleep(0.5)
    if msg["repository"].lower().endswith("/fail"):
        connection.send_result(msg["id"], {})
        return
    REPOS.append({
        "id": str(1000 + len(REPOS)), "full_name": msg["repository"], "category": msg["category"],
        "installed": False, "custom": True,
    })
    connection.send_result(msg["id"], {})
